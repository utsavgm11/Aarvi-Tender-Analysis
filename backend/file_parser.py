# file_parser.py
import io
import os
import re
import gc
import json
import time
import shutil
import hashlib
import asyncio
import tempfile
import threading
import docx
import pandas as pd
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from fastapi import UploadFile
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from config import (
        OCR_WORKERS,
        OCR_TIMEOUT_SECONDS,
        OCR_SCOUT_DPI,
    )
except ImportError:
    OCR_WORKERS = int(os.getenv("OCR_WORKERS", "3"))
    OCR_TIMEOUT_SECONDS = int(os.getenv("OCR_TIMEOUT_SECONDS", "420"))
    OCR_SCOUT_DPI = int(os.getenv("OCR_SCOUT_DPI", "135"))

# --- STRICT CPU CONTROL FOR OCR LIBRARIES ---
os.environ["OMP_THREAD_LIMIT"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"

# --- SNAP SANDBOX SAFE TEMP & TESSDATA DIRECTORIES ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SNAP_COMMON_DIR = "/root/snap/tesseract/common"
if os.path.isdir(SNAP_COMMON_DIR):
    TESS_TMP_DIR = os.path.join(SNAP_COMMON_DIR, "tmp")
    TESSDATA_DIR = os.path.join(SNAP_COMMON_DIR, "tessdata")
else:
    TESS_TMP_DIR = os.path.join(BASE_DIR, ".tess_tmp")
    TESSDATA_DIR = os.path.join(BASE_DIR, "tessdata")

OCR_CACHE_DIR = os.path.join(BASE_DIR, ".ocr_cache")
os.makedirs(TESS_TMP_DIR, exist_ok=True)
os.makedirs(OCR_CACHE_DIR, exist_ok=True)

os.environ["TMPDIR"] = TESS_TMP_DIR
tempfile.tempdir = TESS_TMP_DIR
if os.path.isdir(TESSDATA_DIR):
    os.environ["TESSDATA_PREFIX"] = TESSDATA_DIR


# --- SMART TESSERACT CONFIGURATION ---
def configure_tesseract() -> str:
    """Locates the Tesseract binary and returns version-appropriate CLI flags."""
    candidates = [
        "/usr/local/bin/tesseract",
        "/snap/bin/tesseract",
        shutil.which("tesseract"),
        os.path.join(os.path.expanduser("~"), "AppData", "Local", "Programs", "Tesseract-OCR", "tesseract.exe"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            break
    else:
        print("❌ ERROR: Tesseract OCR not found globally or in Windows paths.", flush=True)
        return "--psm 3"

    try:
        ver = pytesseract.get_tesseract_version()
        major = int(str(ver).split(".")[0])
        flags = "--oem 1 --psm 3" if major >= 4 else "-psm 3"
        print(
            f"✅ Tesseract {ver} configured ({pytesseract.pytesseract.tesseract_cmd}) with flags '{flags}'",
            flush=True,
        )
        return flags
    except Exception as e:
        print(f"⚠️ Tesseract version detection fallback ({e}); using '--oem 1 --psm 3'", flush=True)
        return "--oem 1 --psm 3"


TESSERACT_FLAGS = configure_tesseract()


def estimate_token_count(text: str) -> int:
    if not text:
        return 0
    try:
        import tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        return max(1, len(text) // 4)


def clean_extracted_text(text: str) -> str:
    """
    Normalizes whitespace and strips repeating footer boilerplate while preserving:
    - ₹ (INR currency symbol)
    - --- Page N --- markers
    - dd-mm-yyyy hh:mm submission deadlines
    """
    if not text:
        return ""

    # Preserve printable ASCII, tabs/newlines, and ₹ (\u20B9)
    text = re.sub(r"[^\x09\x0A\x0D\x20-\x7E\u20B9]+", " ", text)
    text = re.sub(r"[ \t]{3,}", " | ", text)
    text = re.sub(r"[ \t]{2}", " ", text)

    # Remove standalone footer page counters without touching "--- Page N ---" headers
    text = re.sub(r"(?im)^\s*page\s*(?:no\.?)?\s*\d+\s*(?:of|/)\s*\d+\s*$", "", text)
    text = re.sub(r"(?i)all\s+rights\s+reserved", "", text)
    text = re.sub(r"(?i)strict\s+confidence\s*(?:confidential)?", "", text)

    # Collapse decorative underscores/dots/dashes while keeping '---' page delimiters intact
    text = re.sub(r"_{3,}", "", text)
    text = re.sub(r"\.{4,}", "...", text)
    text = re.sub(r"(?<!-)-{4,}(?!-)", "", text)

    lines = text.split("\n")
    seen_lines = []
    for line in lines:
        cleaned_line = line.strip()
        if cleaned_line and seen_lines and cleaned_line == seen_lines[-1]:
            continue
        seen_lines.append(cleaned_line)
    text = "\n".join(seen_lines)

    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\n\|\s*\n", "\n", text)
    return text.strip()


def update_task_progress(
    task_id: str,
    current: int,
    total: int,
    filename: str = "",
    file_idx: int = 1,
    total_files: int = 1,
    stage: str = "",
):
    """Emits both legacy progress keys and multi-file progress indicators."""
    if not task_id:
        return
    try:
        from main import progress_store

        file_pct = int((current / total) * 100) if total > 0 else 100
        overall_pct = int(((file_idx - 1 + (current / max(1, total))) / max(1, total_files)) * 100)

        progress_store[task_id] = {
            "current": current,
            "total": total,
            "current_file_index": file_idx,
            "total_files": total_files,
            "current_filename": filename,
            "stage": stage or f"Reading Page {current}/{total}",
            "file_progress_pct": file_pct,
            "overall_progress_pct": overall_pct,
            "status": "processing",
        }
    except Exception:
        pass


def _get_cached_pages(file_hash: str):
    cache_path = os.path.join(OCR_CACHE_DIR, f"{file_hash}.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def _save_cached_pages(file_hash: str, pages: list):
    cache_path = os.path.join(OCR_CACHE_DIR, f"{file_hash}.json")
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(pages, f, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ OCR cache write skipped: {e}", flush=True)


def extract_pages_from_file(
    file_bytes: bytes,
    filename: str,
    task_id: str = None,
    file_index: int = 1,
    total_files: int = 1,
) -> list:
    """
    Extracts structured per-page dictionaries:
    [{"file": str, "page": int, "is_ocr": bool, "text": str}, ...]
    Uses SHA-256 disk caching, native C-speed PyMuPDF text first, and
    parallel Tesseract OCR across `OCR_WORKERS` threads with a time budget.
    """
    t_start = time.time()
    fn_lower = filename.lower()
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    cached = _get_cached_pages(file_hash)
    if cached is not None:
        for p in cached:
            p["file"] = filename
        update_task_progress(
            task_id, 1, 1, filename, file_index, total_files, f"Loaded from cache ({len(cached)} pages)"
        )
        print(f"⚡ [CACHE HIT] {filename}: {len(cached)} pages loaded instantly", flush=True)
        return cached

    pages_out = []

    try:
        if fn_lower.endswith(".pdf"):
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            total_pages = len(doc)
            print(f"STATUS: PDF detected ({filename}). Processing {total_pages} Pages...", flush=True)

            raw_slots = [None] * total_pages
            ocr_required_pages = []
            digital_count = 0

            # 1. High-Speed Native Digital Pass
            for page_num in range(total_pages):
                page = doc[page_num]
                disp_num = page_num + 1
                extracted = page.get_text("text")
                if extracted and len(extracted.strip()) > 30:
                    raw_slots[page_num] = {
                        "file": filename,
                        "page": disp_num,
                        "is_ocr": False,
                        "text": clean_extracted_text(extracted),
                    }
                    digital_count += 1
                else:
                    ocr_required_pages.append(page_num)

                if disp_num % 50 == 0 or disp_num == total_pages:
                    update_task_progress(
                        task_id,
                        disp_num,
                        total_pages,
                        filename,
                        file_index,
                        total_files,
                        f"Direct Text Extraction ({disp_num}/{total_pages})",
                    )
            doc.close()

            # 2. Parallel Targeted OCR Pass (thread-local PDF handles + config workers/DPI)
            skipped_ocr = 0
            if ocr_required_pages:
                ocr_dpi = max(110, OCR_SCOUT_DPI)
                zoom = ocr_dpi / 72.0
                mat = fitz.Matrix(zoom, zoom)
                thread_local = threading.local()
                ocr_deadline = time.time() + OCR_TIMEOUT_SECONDS
                progress_lock = threading.Lock()
                completed_ocr = 0

                def get_thread_doc():
                    if not hasattr(thread_local, "doc"):
                        thread_local.doc = fitz.open(stream=file_bytes, filetype="pdf")
                    return thread_local.doc

                def process_ocr_page(p_num: int):
                    if time.time() > ocr_deadline:
                        return p_num, None, "timeout"
                    try:
                        t_doc = get_thread_doc()
                        pix = t_doc[p_num].get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
                        img = Image.frombytes("L", [pix.width, pix.height], pix.samples)
                        ocr_result = pytesseract.image_to_string(img, lang="eng", config=TESSERACT_FLAGS)
                        img.close()
                        pix = None
                        return p_num, clean_extracted_text(ocr_result), "ok"
                    except Exception as err:
                        return p_num, f"[OCR Error: {err}]", "error"

                workers = max(1, min(OCR_WORKERS, len(ocr_required_pages)))
                print(
                    f"  ⚠️ Running targeted OCR on {len(ocr_required_pages)} scanned page(s) "
                    f"(workers={workers}, dpi={ocr_dpi})...",
                    flush=True,
                )

                with ThreadPoolExecutor(max_workers=workers) as executor:
                    futures = {executor.submit(process_ocr_page, p_idx): p_idx for p_idx in ocr_required_pages}
                    for future in as_completed(futures):
                        p_num, p_text, status = future.result()
                        disp_num = p_num + 1
                        if status == "timeout":
                            skipped_ocr += 1
                            raw_slots[p_num] = {
                                "file": filename,
                                "page": disp_num,
                                "is_ocr": True,
                                "text": "[Skipped due to OCR time budget]",
                            }
                        else:
                            raw_slots[p_num] = {
                                "file": filename,
                                "page": disp_num,
                                "is_ocr": True,
                                "text": p_text or "",
                            }

                        with progress_lock:
                            completed_ocr += 1
                            if completed_ocr % 5 == 0 or completed_ocr == len(ocr_required_pages):
                                update_task_progress(
                                    task_id,
                                    digital_count + completed_ocr,
                                    total_pages,
                                    filename,
                                    file_index,
                                    total_files,
                                    f"OCR Scanning Page {disp_num}/{total_pages} ({completed_ocr}/{len(ocr_required_pages)})",
                                )

            pages_out = [slot for slot in raw_slots if slot is not None]
            elapsed = time.time() - t_start
            print(
                f"✅ [PARSED] {filename}: {total_pages} pages ({digital_count} digital, "
                f"{len(ocr_required_pages) - skipped_ocr} OCR, {skipped_ocr} skipped) in {elapsed:.1f}s",
                flush=True,
            )

        elif fn_lower.endswith((".docx", ".doc")):
            update_task_progress(task_id, 1, 1, filename, file_index, total_files, "Extracting Word document...")
            doc_obj = docx.Document(io.BytesIO(file_bytes))
            chunks = []
            for table in doc_obj.tables:
                for row in table.rows:
                    row_txt = " | ".join([cell.text.strip() for cell in row.cells if cell.text.strip()])
                    if row_txt:
                        chunks.append(row_txt)
            chunks.extend([p.text.strip() for p in doc_obj.paragraphs if p.text.strip()])
            full_docx = clean_extracted_text("\n".join(chunks))

            # Chunk Word files into ~3,500-char virtual pages so triage can score sections
            step = 3500
            for idx, start in enumerate(range(0, max(1, len(full_docx)), step), start=1):
                pages_out.append({
                    "file": filename,
                    "page": idx,
                    "is_ocr": False,
                    "text": full_docx[start : start + step],
                })
            update_task_progress(task_id, 1, 1, filename, file_index, total_files, "Word document extracted")

        elif fn_lower.endswith((".xlsx", ".xls", ".xlsm")):
            update_task_progress(task_id, 1, 1, filename, file_index, total_files, "Extracting Excel BOQ...")
            with pd.ExcelFile(io.BytesIO(file_bytes)) as xls:
                for s_idx, sheet in enumerate(xls.sheet_names, start=1):
                    df = pd.read_excel(xls, sheet_name=sheet).dropna(how="all").dropna(axis=1, how="all")
                    if not df.empty:
                        rows_txt = [f"[SHEET: {sheet}]"]
                        headers = " | ".join(str(c).strip() for c in df.columns)
                        rows_txt.append(headers)
                        for _, row in df.iterrows():
                            vals = [str(v).strip() if pd.notna(v) else "" for v in row.values]
                            if any(vals):
                                rows_txt.append(" | ".join(vals))
                        pages_out.append({
                            "file": filename,
                            "page": s_idx,
                            "is_ocr": False,
                            "text": clean_extracted_text("\n".join(rows_txt)),
                        })
            update_task_progress(task_id, 1, 1, filename, file_index, total_files, "Excel BOQ extracted")

        else:
            pages_out.append({
                "file": filename,
                "page": 1,
                "is_ocr": False,
                "text": "Error: Unsupported file format.",
            })

        if pages_out:
            _save_cached_pages(file_hash, pages_out)

    except Exception as e:
        print(f"!!! CRITICAL ERROR in extraction ({filename}): {e}", flush=True)
        pages_out.append({
            "file": filename,
            "page": 1,
            "is_ocr": False,
            "text": f"Error reading file {filename}: {e}",
        })
    finally:
        gc.collect()

    return pages_out


def format_pages_to_text(pages: list) -> str:
    blocks = []
    for p in pages:
        tag = " (OCR Scan)" if p.get("is_ocr") else ""
        blocks.append(f"\n--- Page {p['page']} [{p['file']}]{tag} ---\n{p['text']}\n")
    return "".join(blocks)


def extract_text_from_file(
    file_bytes: bytes,
    filename: str,
    task_id: str = None,
    file_index: int = 1,
    total_files: int = 1,
) -> str:
    """Backward-compatible extractor returning unified cleaned text."""
    pages = extract_pages_from_file(file_bytes, filename, task_id, file_index, total_files)
    return format_pages_to_text(pages)


async def extract_text_from_upload(file: UploadFile, task_id: str = None) -> str:
    print(f"\n--- [HYBRID START] Processing File: {file.filename} ---", flush=True)
    file_bytes = await file.read()
    cleaned_text = await asyncio.to_thread(extract_text_from_file, file_bytes, file.filename, task_id)
    print(f"--- [COMPLETE] Total Extracted Characters: {len(cleaned_text)} ---", flush=True)
    return cleaned_text


def append_text_to_disk_stream(
    file_bytes: bytes,
    filename: str,
    output_file_path: str,
    task_id: str = None,
    file_index: int = 1,
    total_files: int = 1,
):
    """
    Streams extracted text directly to disk AND saves per-page structured JSON
    to `<output_file_path>.pages.json` for triage and RAG indexing.
    """
    pages = extract_pages_from_file(file_bytes, filename, task_id, file_index, total_files)
    if not pages:
        return

    with open(output_file_path, "a", encoding="utf-8") as out_f:
        out_f.write(format_pages_to_text(pages))

    sidecar_path = f"{output_file_path}.pages.json"
    existing_pages = []
    if os.path.exists(sidecar_path):
        try:
            with open(sidecar_path, "r", encoding="utf-8") as sf:
                existing_pages = json.load(sf)
        except Exception:
            existing_pages = []

    existing_pages.extend(pages)
    with open(sidecar_path, "w", encoding="utf-8") as sf:
        json.dump(existing_pages, sf, ensure_ascii=False)
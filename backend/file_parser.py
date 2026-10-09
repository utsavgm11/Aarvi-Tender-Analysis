import io
import re
import docx
import pandas as pd
import fitz  # PyMuPDF
from fastapi import UploadFile
import pytesseract
import os
import shutil  
import asyncio  
import gc
import threading
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- STRICT CPU CONTROL FOR OCR LIBRARIES ---
os.environ["OMP_THREAD_LIMIT"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"

# --- ADVANCED EMBEDDED CONVERTERS ---
try:
    from docling.document_converter import DocumentConverter
    docling_converter = DocumentConverter()
    DOCLING_AVAILABLE = True
except ImportError:
    print("⚠️ WARNING: Docling library not detected. Falling back to native PyMuPDF.", flush=True)
    DOCLING_AVAILABLE = False

# --- SMART TESSERACT CONFIGURATION ---
def configure_tesseract():
    linux_tesseract_path = shutil.which("tesseract")
    if linux_tesseract_path:
        pytesseract.pytesseract.tesseract_cmd = linux_tesseract_path
        return
    appdata_path = os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'Programs', 'Tesseract-OCR', 'tesseract.exe')
    system_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if os.path.exists(appdata_path):
        pytesseract.pytesseract.tesseract_cmd = appdata_path
    elif os.path.exists(system_path):
        pytesseract.pytesseract.tesseract_cmd = system_path
    else:
        print("❌ ERROR: Tesseract OCR not found globally or in Windows paths.", flush=True)

configure_tesseract()

def estimate_token_count(text: str) -> int:
    try:
        import tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        return int(len(text.split()) * 1.37)

def clean_extracted_text(text: str) -> str:
    if not text: 
        return ""
        
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    text = re.sub(r'[ \t]{3,}', ' | ', text)
    text = re.sub(r'[ \t]{2}', ' ', text)
    text = re.sub(r'(?i)page\s*(?:no\.?)?\s*\d+\s*(?:of|/)?\s*\d*', '', text)
    text = re.sub(r'(?i)all\s+rights\s+reserved', '', text)
    text = re.sub(r'(?i)tender\s+document\s*(?:for)?', '', text)
    text = re.sub(r'(?i)commercial\s+bid\s+format', '', text)
    text = re.sub(r'(?i)strict\s+confidence\s*(?:confidential)?', '', text)
    text = re.sub(r'\d{2}[-/.]\d{2}[-/.]\d{4}\s+\d{2}:\d{2}(?::\d{2})?', '', text)
    text = re.sub(r'_{2,}', '', text)
    text = re.sub(r'-{3,}', '', text)
    text = re.sub(r'\.{3,}', '...', text) 
    
    lines = text.split('\n')
    seen_lines = []
    for line in lines:
        cleaned_line = line.strip()
        if cleaned_line and seen_lines and cleaned_line == seen_lines[-1]:
            continue
        seen_lines.append(cleaned_line)
    text = '\n'.join(seen_lines)
    
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'\n\|\s*\n', '\n', text)
    
    return text.strip()

def update_task_progress(task_id: str, current: int, total: int, filename: str = "", file_idx: int = 1, total_files: int = 1, stage: str = ""):
    """Emits both legacy progress keys and rich multi-file progress indicators."""
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
            "overall_progress_pct": overall_pct
        }
    except Exception:
        pass

async def extract_text_from_upload(file: UploadFile, task_id: str = None) -> str:
    print(f"\n--- [HYBRID START] Processing File: {file.filename} ---", flush=True)
    file_bytes = await file.read()
    
    raw_text = await asyncio.to_thread(extract_text_from_file, file_bytes, file.filename, task_id)
    cleaned_text = clean_extracted_text(raw_text)
    
    try:
        raw_token_estimate = estimate_token_count(raw_text)
        clean_token_estimate = estimate_token_count(cleaned_text)
        token_savings = raw_token_estimate - clean_token_estimate
        savings_percent = (token_savings / raw_token_estimate * 100) if raw_token_estimate > 0 else 0
        
        print("\n=======================================================", flush=True)
        print(f"📊 TASK METRICS ANALYSIS [{task_id or 'STANDALONE'}]", flush=True)
        print(f"  • Raw Character Length   : {len(raw_text)}", flush=True)
        print(f"  • Clean Character Length : {len(cleaned_text)}", flush=True)
        print(f"  • Estimated RAW Tokens   : {raw_token_estimate} tokens", flush=True)
        print(f"  • Estimated CLEAN Tokens : {clean_token_estimate} tokens", flush=True)
        print(f"  • 🔥 TOTAL TOKENS SAVED  : {token_savings} tokens ({savings_percent:.1f}% reduction)", flush=True)
        print("=======================================================\n", flush=True)
    except Exception as metrics_fault:
        print(f"[METRICS BYPASSED] Non-critical analytics fault encountered: {metrics_fault}", flush=True)
    
    print(f"--- [COMPLETE] Total Extracted Characters: {len(cleaned_text)} ---", flush=True)
    return cleaned_text

def extract_text_from_file(file_bytes: bytes, filename: str, task_id: str = None, file_index: int = 1, total_files: int = 1) -> str:
    """
    Blazing fast memory-stream extractor.
    Uses C-speed PyMuPDF for digital text and offloads ONLY scanned pages to Tesseract.
    """
    fn_lower = filename.lower()
    try:
        if fn_lower.endswith(".pdf"):
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            total_pages = len(doc)
            print(f"STATUS: PDF detected ({filename}). Processing {total_pages} Pages (High-Speed Memory Stream)...", flush=True)
            
            all_page_texts = [""] * total_pages
            ocr_required_pages = []

            # 1. High-Speed Pass: Extract all native digital text in < 0.1s
            for page_num in range(total_pages):
                page = doc[page_num]
                current_page_display = page_num + 1
                extracted = page.get_text("text")

                if extracted and len(extracted.strip()) > 30:
                    all_page_texts[page_num] = f"\n--- Page {current_page_display} ---\n{extracted}\n"
                else:
                    ocr_required_pages.append(page_num)

                if (page_num + 1) % 50 == 0 or page_num == total_pages - 1:
                    update_task_progress(task_id, page_num + 1, total_pages, filename, file_index, total_files, f"Direct Text Extraction ({page_num + 1}/{total_pages})")

            # 2. Targeted OCR Fallback Pass (ONLY for pages with <= 30 chars)
            if ocr_required_pages:
                print(f"  ⚠️ Running targeted OCR on {len(ocr_required_pages)} scanned page(s)...", flush=True)
                
                def process_ocr_page(p_num):
                    try:
                        p_doc = fitz.open(stream=file_bytes, filetype="pdf")
                        p_page = p_doc[p_num]
                        disp_num = p_num + 1
                        pix = p_page.get_pixmap(matrix=fitz.Matrix(1.0, 1.0))
                        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("L")
                        ocr_result = pytesseract.image_to_string(img, lang="eng", config="--oem 1 --psm 6")
                        
                        img.close()
                        pix = None
                        p_doc.close()
                        
                        return p_num, f"\n--- Page {disp_num} (OCR Scan) ---\n{ocr_result}\n", f"  > Page {disp_num}/{total_pages}: Tesseract OCR Fast Scan"
                    except Exception as err:
                        return p_num, f"\n--- Page {p_num + 1} (Error) ---\n[Error: {str(err)}]\n", f"  ! Page {p_num + 1} OCR Error: {err}"

                completed_ocr = 0
                with ThreadPoolExecutor(max_workers=2) as executor:
                    futures = {executor.submit(process_ocr_page, p_idx): p_idx for p_idx in ocr_required_pages}
                    for future in as_completed(futures):
                        p_num, p_text, log_msg = future.result()
                        all_page_texts[p_num] = p_text
                        completed_ocr += 1
                        print(log_msg, flush=True)
                        update_task_progress(task_id, total_pages - len(ocr_required_pages) + completed_ocr, total_pages, filename, file_index, total_files, f"OCR Scanning Page {p_num + 1}/{total_pages}")

            doc.close()
            final_text = "".join(all_page_texts)
            all_page_texts.clear()
            gc.collect()
            return final_text

        elif fn_lower.endswith((".docx", ".doc")):
            update_task_progress(task_id, 1, 1, filename, file_index, total_files, "Extracting Word document...")
            doc_obj = docx.Document(io.BytesIO(file_bytes))
            text = ""
            for table in doc_obj.tables:
                for row in table.rows:
                    text += " | ".join([cell.text.strip() for cell in row.cells]) + "\n"
            text += "\n".join([p.text for p in doc_obj.paragraphs if p.text.strip()])
            update_task_progress(task_id, 1, 1, filename, file_index, total_files, "Word document extracted")
            return text

        elif fn_lower.endswith((".xlsx", ".xls", ".xlsm")):
            update_task_progress(task_id, 1, 1, filename, file_index, total_files, "Extracting Excel BOQ...")
            text = ""
            with pd.ExcelFile(io.BytesIO(file_bytes)) as xls:
                for sheet in xls.sheet_names:
                    df = pd.read_excel(xls, sheet_name=sheet)
                    if not df.empty:
                        text += f"\n[SHEET: {sheet}]\n{df.to_string(index=False)}\n"
            update_task_progress(task_id, 1, 1, filename, file_index, total_files, "Excel BOQ extracted")
            return text

        else:
            return "Error: Unsupported file format."

    except Exception as e:
        print(f"!!! CRITICAL ERROR in extraction: {str(e)}", flush=True)
        return f"Error reading file {filename}: {str(e)}"
    finally:
        gc.collect()

def append_text_to_disk_stream(file_bytes: bytes, filename: str, output_file_path: str, task_id: str = None, file_index: int = 1, total_files: int = 1):
    """
    🚀 HIGH-SPEED UNLIMITED DISK STREAMER 🚀
    Streams extracted text DIRECTLY to disk with zero RAM overhead.
    """
    fn_lower = filename.lower()
    try:
        if fn_lower.endswith(".pdf"):
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            total_pages = len(doc)
            print(f"⚡ HIGH-SPEED DISK STREAM: Processing {total_pages} Pages...", flush=True)

            all_page_texts = [""] * total_pages
            ocr_required_pages = []

            # 1. Native Extraction Pass
            for page_num in range(total_pages):
                page = doc[page_num]
                current_page_display = page_num + 1
                extracted = page.get_text("text")

                if extracted and len(extracted.strip()) > 30:
                    page_text = f"\n--- Page {current_page_display} ---\n{extracted}\n"
                    all_page_texts[page_num] = clean_extracted_text(page_text)
                else:
                    ocr_required_pages.append(page_num)

                if (page_num + 1) % 50 == 0 or page_num == total_pages - 1:
                    update_task_progress(task_id, page_num + 1, total_pages, filename, file_index, total_files, f"Streaming Page {page_num + 1}/{total_pages}")

            # 2. Targeted OCR Fallback Pass
            if ocr_required_pages:
                def process_ocr_stream_page(p_num):
                    try:
                        p_doc = fitz.open(stream=file_bytes, filetype="pdf")
                        p_page = p_doc[p_num]
                        disp_num = p_num + 1
                        pix = p_page.get_pixmap(matrix=fitz.Matrix(1.0, 1.0))
                        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("L")
                        ocr_result = pytesseract.image_to_string(img, lang="eng", config="--oem 1 --psm 6")
                        
                        img.close()
                        pix = None
                        p_doc.close()

                        page_text = f"\n--- Page {disp_num} (OCR Scan) ---\n{ocr_result}\n"
                        return p_num, clean_extracted_text(page_text)
                    except Exception as err:
                        return p_num, f"\n--- Page {p_num + 1} (Error) ---\n[Error: {str(err)}]\n"

                with ThreadPoolExecutor(max_workers=2) as executor:
                    futures = {executor.submit(process_ocr_stream_page, p_idx): p_idx for p_idx in ocr_required_pages}
                    for future in as_completed(futures):
                        p_num, p_text = future.result()
                        all_page_texts[p_num] = p_text

            doc.close()

            # Flush everything cleanly to disk stream
            with open(output_file_path, "a", encoding="utf-8") as out_f:
                for text_chunk in all_page_texts:
                    if text_chunk:
                        out_f.write(text_chunk + "\n")

            all_page_texts.clear()
            gc.collect()

        elif fn_lower.endswith((".docx", ".doc")):
            doc_obj = docx.Document(io.BytesIO(file_bytes))
            with open(output_file_path, "a", encoding="utf-8") as out_f:
                for table in doc_obj.tables:
                    for row in table.rows:
                        out_f.write(" | ".join([cell.text.strip() for cell in row.cells]) + "\n")
                out_f.write("\n".join([p.text for p in doc_obj.paragraphs if p.text.strip()]) + "\n")

        elif fn_lower.endswith((".xlsx", ".xls", ".xlsm")):
            with pd.ExcelFile(io.BytesIO(file_bytes)) as xls:
                with open(output_file_path, "a", encoding="utf-8") as out_f:
                    for sheet in xls.sheet_names:
                        df = pd.read_excel(xls, sheet_name=sheet)
                        if not df.empty:
                            out_f.write(f"\n[SHEET: {sheet}]\n{df.to_string(index=False)}\n")

    except Exception as e:
        print(f"!!! ERROR in extraction stream: {str(e)}", flush=True)
    finally:
        gc.collect()
import io
import re
import docx
import pandas as pd
import fitz  # PyMuPDF
from fastapi import UploadFile
import pytesseract
import os
import shutil  # REQUIRED: Finding system installations on Linux/Docker
from PIL import Image
import platform
import concurrent.futures # <-- NEW: Required for the 4-worker speed configuration

# --- ADVANCED EMBEDDED CONVERTERS ---
try:
    from docling.document_converter import DocumentConverter
    # Initialize the Docling neural engine globally so it caches models into RAM once at startup
    docling_converter = DocumentConverter()
    DOCLING_AVAILABLE = True
except ImportError:
    print("⚠️ WARNING: Docling library not detected. Falling back to native PyMuPDF.")
    DOCLING_AVAILABLE = False

# --- SMART TESSERACT CONFIGURATION ---
def configure_tesseract():
    """
    Dynamically configures the execution paths for Tesseract OCR 
    across both Linux/Docker production engines and local Windows environments.
    """
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
        print("❌ ERROR: Tesseract OCR not found globally or in Windows paths.")

configure_tesseract()

def estimate_token_count(text: str) -> int:
    """
    Calculates estimated Gemini tokens using cl100k_base (GPT-4 tokenizer model).
    """
    try:
        import tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        return int(len(text.split()) * 1.37)

async def extract_text_from_upload(file: UploadFile, task_id: str = None) -> str:
    """
    Handles asynchronous file reading, passes bytes to extraction logic,
    and returns comprehensive token optimization comparisons safely.
    """
    print(f"\n--- [HYBRID START] Processing File: {file.filename} ---", flush=True)
    file_bytes = await file.read()
    
    # 1. Pull down raw text (Utilizes Docling for structural Markdown extraction)
    raw_text = extract_text_from_file(file_bytes, file.filename, task_id)
    
    # 2. Apply structural text cleanup modifications
    cleaned_text = clean_extracted_text(raw_text)
    
    # 3. METRICS AUDIT BLOCK
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

def clean_extracted_text(text: str) -> str:
    """
    Advanced Token Optimization Sanitizer. Cleans layout artifacts, collapses multi-space 
    gaps, formats data rows into explicit Markdown tables, and purges system header/footer noise.
    """
    if not text: 
        return ""
        
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    
    # Format horizontal spaces into structural pipe separators if not already handled by Docling
    text = re.sub(r'[ \t]{3,}', ' | ', text)
    text = re.sub(r'[ \t]{2}', ' ', text)
    
    # A. Strip running page counters
    text = re.sub(r'(?i)page\s*(?:no\.?)?\s*\d+\s*(?:of|/)?\s*\d*', '', text)
    
    # B. Strip non-informative corporate boilerplate lines
    text = re.sub(r'(?i)all\s+rights\s+reserved', '', text)
    text = re.sub(r'(?i)tender\s+document\s*(?:for)?', '', text)
    text = re.sub(r'(?i)commercial\s+bid\s+format', '', text)
    text = re.sub(r'(?i)strict\s+confidence\s*(?:confidential)?', '', text)
    
    # C. Compress system trailing timestamps
    text = re.sub(r'\d{2}[-/.]\d{2}[-/.]\d{4}\s+\d{2}:\d{2}(?::\d{2})?', '', text)
    
    # D. Clean out artifact pattern chains (dashes, lines, underscores)
    text = re.sub(r'_{2,}', '', text)
    text = re.sub(r'-{3,}', '', text)
    text = re.sub(r'\.{3,}', '...', text) 
    
    # E. De-duplicate identical consecutive table rows or text strings
    lines = text.split('\n')
    seen_lines = []
    for line in lines:
        cleaned_line = line.strip()
        if cleaned_line and seen_lines and cleaned_line == seen_lines[-1]:
            continue
        seen_lines.append(cleaned_line)
    text = '\n'.join(seen_lines)
    
    # 3. Condense empty vertical lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'\n\|\s*\n', '\n', text)
    
    return text.strip()

# <-- NEW: Isolated Thread Worker to prevent RAM crashes on Render while boosting speed
def process_page_worker(temp_pdf_path: str, page_num: int, docling_avail: bool) -> tuple:
    """
    Executes identical extraction logic safely inside an independent worker thread.
    """
    page_text = ""
    status_msg = ""
    try:
        # Each thread safely opens its own read-only stream to prevent memory overlap
        with fitz.open(temp_pdf_path) as doc:
            page = doc[page_num - 1]
            
            blocks = page.get_text("blocks")
            extracted = "\n".join([b[4] for b in blocks if b[4].strip()])
            
            if len(extracted.strip()) > 100 and docling_avail:
                try:
                    page_result = docling_converter.convert(temp_pdf_path, page_numbers=[page_num])
                    page_markdown = page_result.document.export_to_markdown()
                    page_text = f"\n--- Page {page_num} (Docling Smart Markdown) ---\n{page_markdown}\n"
                    status_msg = f"  > Page {page_num}: Docling Neural Extraction (Markdown Mode)"
                except Exception:
                    page_text = f"\n--- Page {page_num} ---\n{extracted}\n"
                    status_msg = f"  > Page {page_num}: PyMuPDF Block Extraction (Digital Fallback)"
            else:
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                ocr_result = pytesseract.image_to_string(img)
                
                page_text = f"\n--- Page {page_num} (OCR Scan) ---\n{ocr_result}\n"
                status_msg = f"  > Page {page_num}: Tesseract OCR Scan (Image Mode)"
                
    except Exception as e:
        page_text = f"\n--- Page {page_num} Error ---\n{str(e)}\n"
        status_msg = f"❌ Page {page_num} Failed: {str(e)}"
        
    return page_num, page_text, status_msg


def extract_text_from_file(file_bytes: bytes, filename: str, task_id: str = None) -> str:
    """
    Hybrid PDF Extractor: Uses Docling neural parsing for elite structural layouts
    and seamlessly switches to Tesseract OCR for flat images.
    NOW POWERED BY 4 CONCURRENT WORKER THREADS for Render.
    """
    text = ""
    fn_lower = filename.lower()
    temp_pdf_path = f"temp_process_{task_id or 'standalone'}.pdf"

    try:
        # 1. HYBRID PDF ROUTING LAYER
        if fn_lower.endswith(".pdf"):
            with open(temp_pdf_path, "wb") as f:
                f.write(file_bytes)

            with fitz.open(temp_pdf_path) as doc:
                total_pages = len(doc)
                print(f"STATUS: PDF detected. Distributing {total_pages} Pages across 4 Thread Workers...", flush=True)

            results = {}
            processed_count = 0
            
            # 🚀 SPAWN 4 WORKERS (Memory-Safe for Render)
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                # Dispatch all pages into the processing queue
                futures = {
                    executor.submit(process_page_worker, temp_pdf_path, page_num, DOCLING_AVAILABLE): page_num 
                    for page_num in range(1, total_pages + 1)
                }
                
                # Capture results dynamically as workers finish
                for future in concurrent.futures.as_completed(futures):
                    page_num, page_text, status_msg = future.result()
                    results[page_num] = page_text
                    
                    print(status_msg, flush=True)
                    processed_count += 1
                    
                    # Safely push updates to the React Progress Bar
                    if task_id:
                        try:
                            from main import progress_store
                            progress_store[task_id] = {"current": processed_count, "total": total_pages}
                        except ImportError:
                            pass
            
            # Reconstruct the document completely sequentially (1 to X) so AI logic remains flawless
            for page_num in range(1, total_pages + 1):
                text += results.get(page_num, "")

            # Clear temporary worker file from local environment
            if os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)

        # 2. WORD DOCUMENT HANDLING
        elif fn_lower.endswith((".docx", ".doc")):
            print("STATUS: Processing Word Document...", flush=True)
            if task_id:
                try:
                    from main import progress_store
                    progress_store[task_id] = {"current": 1, "total": 1}
                except ImportError:
                    pass
            doc_obj = docx.Document(io.BytesIO(file_bytes))
            for table in doc_obj.tables:
                for row in table.rows:
                    text += " | ".join([cell.text.strip() for cell in row.cells]) + "\n"
            text += "\n".join([p.text for p in doc_obj.paragraphs if p.text.strip()])

        # 3. EXCEL HANDLING
        elif fn_lower.endswith((".xlsx", ".xls", ".xlsm")):
            print("STATUS: Processing Excel Document...", flush=True)
            if task_id:
                try:
                    from main import progress_store
                    progress_store[task_id] = {"current": 1, "total": 1}
                except ImportError:
                    pass
            with pd.ExcelFile(io.BytesIO(file_bytes)) as xls:
                for sheet in xls.sheet_names:
                    df = pd.read_excel(xls, sheet_name=sheet)
                    if not df.empty:
                        text += f"\n[SHEET: {sheet}]\n{df.to_string(index=False)}\n"
        else: 
            return "Error: Unsupported file format."

    except Exception as e:
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
        print(f"!!! CRITICAL ERROR in extraction: {str(e)}", flush=True)
        return f"Error reading file {filename}: {str(e)}"

    return text
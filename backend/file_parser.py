import io
import re
import docx
import pandas as pd
import fitz  # PyMuPDF
from fastapi import UploadFile
import pytesseract
import os
import shutil  
from PIL import Image

# --- ADVANCED EMBEDDED CONVERTERS ---
try:
    from docling.document_converter import DocumentConverter
    docling_converter = DocumentConverter()
    DOCLING_AVAILABLE = True
except ImportError:
    print("⚠️ WARNING: Docling library not detected. Falling back to native PyMuPDF.")
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
        print("❌ ERROR: Tesseract OCR not found globally or in Windows paths.")

configure_tesseract()

def estimate_token_count(text: str) -> int:
    try:
        import tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        return int(len(text.split()) * 1.37)

async def extract_text_from_upload(file: UploadFile, task_id: str = None) -> str:
    print(f"\n--- [HYBRID START] Processing File: {file.filename} ---", flush=True)
    file_bytes = await file.read()
    
    raw_text = extract_text_from_file(file_bytes, file.filename, task_id)
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

def extract_text_from_file(file_bytes: bytes, filename: str, task_id: str = None) -> str:
    """
    Cloud-Safe Hybrid PDF Extractor: Uses Docling for structural layouts
    and seamlessly switches to Tesseract OCR for flat images.
    Executes sequentially to prevent Render CPU Starvation / Deadlocks.
    """
    text = ""
    fn_lower = filename.lower()
    temp_pdf_path = f"temp_process_{task_id or 'standalone'}.pdf"

    try:
        if fn_lower.endswith(".pdf"):
            with open(temp_pdf_path, "wb") as f:
                f.write(file_bytes)

            with fitz.open(temp_pdf_path) as doc:
                total_pages = len(doc)
                print(f"STATUS: PDF detected. Processing {total_pages} Pages Sequentially for Cloud Stability...", flush=True)

                for i, page in enumerate(doc):
                    current_page = i + 1
                    
                    if task_id:
                        try:
                            from main import progress_store
                            progress_store[task_id] = {"current": current_page, "total": total_pages}
                        except ImportError:
                            pass
                    
                    blocks = page.get_text("blocks")
                    extracted = "\n".join([b[4] for b in blocks if b[4].strip()])
                    
                    if len(extracted.strip()) > 100 and DOCLING_AVAILABLE:
                        try:
                            page_result = docling_converter.convert(temp_pdf_path, page_numbers=[current_page])
                            page_markdown = page_result.document.export_to_markdown()
                            text += f"\n--- Page {current_page} (Docling Smart Markdown) ---\n{page_markdown}\n"
                            print(f"  > Page {current_page}/{total_pages}: Docling Neural Extraction (Markdown Mode)", flush=True)
                        except Exception:
                            text += f"\n--- Page {current_page} ---\n{extracted}\n"
                            print(f"  > Page {current_page}/{total_pages}: PyMuPDF Block Extraction (Digital Fallback)", flush=True)
                    else:
                        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                        img = Image.open(io.BytesIO(pix.tobytes("png")))
                        ocr_result = pytesseract.image_to_string(img)
                        
                        text += f"\n--- Page {current_page} (OCR Scan) ---\n{ocr_result}\n"
                        print(f"  > Page {current_page}/{total_pages}: Tesseract OCR Scan (Image Mode)", flush=True)

            if os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)

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
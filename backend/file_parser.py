import io
import re
import docx
import pandas as pd
import fitz  # PyMuPDF
from fastapi import UploadFile
import pytesseract
import os
from PIL import Image

# --- SMART TESSERACT CONFIGURATION ---
def configure_tesseract():
    # 1. Check AppData (User-level install like on your office laptop)
    appdata_path = os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'Programs', 'Tesseract-OCR', 'tesseract.exe')
    
    # 2. Check Program Files (System-level install - common for home laptops)
    system_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

    if os.path.exists(appdata_path):
        pytesseract.pytesseract.tesseract_cmd = appdata_path
    elif os.path.exists(system_path):
        pytesseract.pytesseract.tesseract_cmd = system_path
    else:
        print("❌ ERROR: Tesseract OCR not found in AppData or Program Files.")

configure_tesseract()

# <-- UPDATED: Added task_id parameter -->
async def extract_text_from_upload(file: UploadFile, task_id: str = None) -> str:
    """
    Handles asynchronous file reading and passes bytes to extraction logic.
    """
    print(f"\n--- [START] Processing File: {file.filename} ---")
    file_bytes = await file.read()
    
    # Pass task_id down to the physical extractor
    raw_text = extract_text_from_file(file_bytes, file.filename, task_id)
    
    cleaned_text = clean_extracted_text(raw_text)
    print(f"--- [COMPLETE] Total Extracted Characters: {len(cleaned_text)} ---")
    return cleaned_text

def clean_extracted_text(text: str) -> str:
    """
    Optimizes text for AI analysis by removing artifacts and excessive whitespace.
    """
    if not text: return ""
    # Remove non-standard ASCII junk common in PSU scanned documents
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    # Collapse multiple newlines and spaces to save AI tokens
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()

# <-- UPDATED: Added task_id parameter -->
def extract_text_from_file(file_bytes: bytes, filename: str, task_id: str = None) -> str:
    """
    Extracts text from PDF, Word, and Excel with specialized PDF table handling.
    Includes live terminal page tracking AND React Progress Bar updating.
    """
    text = ""
    fn_lower = filename.lower()

    try:
        # 1. ENHANCED PDF HANDLING (Tesseract Powered)
        if fn_lower.endswith(".pdf"):
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                total_pages = len(doc)
                print(f"STATUS: PDF detected. Total Pages: {total_pages}")
                
                for i, page in enumerate(doc):
                    current_page = i + 1
                    
                    # --- NEW: UPDATE REACT PROGRESS BAR ---
                    if task_id:
                        try:
                            # Imported here locally to avoid Circular Import crashes
                            from main import progress_store
                            progress_store[task_id] = {
                                "current": current_page,
                                "total": total_pages
                            }
                        except ImportError:
                            pass
                    
                    # Try high-speed structural text extraction first
                    # 'blocks' preserves paragraph and table-row relationships
                    blocks = page.get_text("blocks")
                    blocks.sort(key=lambda b: (b[1], b[0]))
                    extracted = "\n".join([b[4] for b in blocks if b[4].strip()])
                    
                    # Page contains viable text layer
                    if len(extracted.strip()) > 100:
                        text += f"\n--- Page {current_page} ---\n{extracted}\n"
                        # Print terminal update
                        print(f"  > Page {current_page}/{total_pages}: Digital Extraction (Fast)")
                    else:
                        # OCR FALLBACK: Page is a scanned image (common for BQC pages)
                        # matrix=fitz.Matrix(1.5, 1.5) provides balance of speed/accuracy
                        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                        img = Image.open(io.BytesIO(pix.tobytes("png")))
                        
                        # Run Tesseract
                        ocr_result = pytesseract.image_to_string(img)
                        text += f"\n--- Page {current_page} (OCR Scan) ---\n{ocr_result}\n"
                        print(f"  > Page {current_page}/{total_pages}: Tesseract OCR Scan")

        # 2. WORD DOCUMENT HANDLING
        elif fn_lower.endswith((".docx", ".doc")):
            print("STATUS: Processing Word Document...")
            
            # Update progress for single files
            if task_id:
                try:
                    from main import progress_store
                    progress_store[task_id] = {"current": 1, "total": 1}
                except ImportError:
                    pass

            doc_obj = docx.Document(io.BytesIO(file_bytes))
            # Extract from tables (BQC is often in tables in Word docs)
            for table in doc_obj.tables:
                for row in table.rows:
                    text += " | ".join([cell.text.strip() for cell in row.cells]) + "\n"
            # Extract standard paragraphs
            text += "\n".join([p.text for p in doc_obj.paragraphs if p.text.strip()])

        # 3. EXCEL HANDLING
        elif fn_lower.endswith((".xlsx", ".xls", ".xlsm")):
            print("STATUS: Processing Excel Document...")
            
            # Update progress for single files
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
        print(f"!!! CRITICAL ERROR in extraction: {str(e)}")
        return f"Error reading file {filename}: {str(e)}"

    return text
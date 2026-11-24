# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# --- API & DATABASE ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

# --- GEMINI MODEL ROUTING ---
GEMINI_PRIMARY_MODEL = os.getenv("GEMINI_PRIMARY_MODEL", "gemini-3.5-flash-lite")
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.8-flash")
GEMINI_TIMEOUT_SECONDS = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "90"))

# --- OCR & PARSER TUNING (4-Core CentOS Server + Tesseract 5.5.4) ---
OCR_WORKERS = int(os.getenv("OCR_WORKERS", "3"))
OCR_TIMEOUT_SECONDS = int(os.getenv("OCR_TIMEOUT_SECONDS", "420"))  # 7-minute safety cap
OCR_SCOUT_DPI = int(os.getenv("OCR_SCOUT_DPI", "135"))             # Balanced speed & table accuracy

# --- TRIAGE & TOKEN BUDGETS ---
TRIAGE_ENABLED = os.getenv("TRIAGE_ENABLED", "1").strip().lower() not in ("0", "false", "no")
TRIAGE_TOKEN_BUDGET = int(os.getenv("TRIAGE_TOKEN_BUDGET", "65000"))
SECOND_PASS_TOKEN_BUDGET = int(os.getenv("SECOND_PASS_TOKEN_BUDGET", "45000"))

# --- TOKEN COST RATES (INR per token) ---
INPUT_COST_PER_TOKEN_INR = float(os.getenv("INPUT_COST_PER_TOKEN_INR", "0.00001"))
OUTPUT_COST_PER_TOKEN_INR = float(os.getenv("OUTPUT_COST_PER_TOKEN_INR", "0.00003"))

# --- COMPANY SERVICE OFFERINGS ---
SERVICES = [
    "Construction Supervision", "Engineering Services", "Expediting Services",
    "Inspection Services", "IT Staffing", "Manpower Outsourcing",
    "Operation & Maintenance", "Pre-Commissioning & Commissioning",
    "Pre-Commissioning & Commissioning Services", "Procurement Assistance",
    "Project Management", "Shutdown", "Technical Staffing Services"
]

# --- TARGET SECTORS ---
SECTORS = [
    "Cement", "CGD", "CNG", "Engineering", "EPC", "Infrastructure",
    "IT", "Metals & Minerals", "Metro", "Mono Rail", "Oil & Gas", "Power",
    "Renewable Energy", "Petrochemical", "Pipeline", "Refinery", "Railways", "Telecom"
]

# --- TECHNICAL MANPOWER CAPABILITIES ---
TECHNICAL_CAPABILITIES = [
    "Engineering Design", "Project Management", "Construction Management",
    "Safety / QHSE", "Store Warehousing", "Pre Commissioning and Commissioning",
    "Operation and Maintenance"
]
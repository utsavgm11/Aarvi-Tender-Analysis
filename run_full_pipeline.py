import os
import re
import sqlite3
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# --- LOAD ENVIRONMENT VARIABLES FROM BACKEND/.ENV ---
env_path = os.path.join('backend', '.env')
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()  # Fallback to root directory if present

# --- CONFIGURATION ---
SQLITE_DB = os.path.join('backend', 'tender_data.db')

# Pull connection string directly from .env (Checks DATABASE_URL first, then POSTGRES_URL)
POSTGRES_URL = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")

if not POSTGRES_URL:
    raise ValueError("❌ Error: DATABASE_URL is missing from backend/.env file!")

# Folders to check for raw Excel files
SEARCH_FOLDERS = [
    './historical_data',
    os.path.join('backend', 'knowledge_base')
]

COLUMN_VARIANTS = {
    'tender_no': ['tender_no', 'tender_no_', 'tender_no.', 'tender_number', 'ref_no', 'tender_ref', 'sr_no'],
    'name_of_client': ['client', 'client_name', 'name_of_client', 'customer'],
    'tender_status': ['status', 'tender_status', 'current_status'],
    'tender_open_price': ['value', 'estimated_value', 'tender_value', 'tender_price', 'amount'],
    'quoted_value': ['quoted_amount', 'our_quote', 'quoted_value'],
    'received_date': ['date', 'received_date', 'inward_date'],
    'due_date': ['due_date', 'closing_date', 'submission_date'],
    'location': ['location', 'place', 'site']
}

def clean_currency(value):
    if pd.isna(value) or value == "" or str(value).strip() == '-': 
        return 0.0
    text_val = str(value).upper().replace(',', '').replace('RS.', '').replace('/-', '').strip()
    num = re.findall(r"[-+]?\d*\.\d+|\d+", text_val)
    return float(num[0]) if num else 0.0

def standardize_status(val):
    val = str(val).lower().strip()
    if 'won' in val: return "Tender Won"
    if 'lost' in val: return "Tender Lost"
    if 'quote' in val: return "Tender Quoted"
    if 'cancel' in val: return "Cancelled"
    return "Tender Received"

def run_pipeline():
    print("🚀 === STARTING MASTER TENDER PIPELINE ===")

    # 1. FIND AND LOAD ALL EXCEL FILES
    all_dfs = []
    for folder in SEARCH_FOLDERS:
        if os.path.exists(folder):
            for file in os.listdir(folder):
                if file.endswith(('.xlsx', '.xlsm')) and not file.startswith('Cleaned_'):
                    file_path = os.path.join(folder, file)
                    print(f"📂 Found raw Excel: {file_path}")
                    try:
                        df = pd.read_excel(file_path, engine='openpyxl')
                        # Clean column headers
                        df.columns = [re.sub(r'[\s/.]+', '_', str(c).strip().lower()).strip('_') for c in df.columns]
                        
                        # Match variants
                        rename_dict = {}
                        for std_col, variants in COLUMN_VARIANTS.items():
                            for v in variants:
                                if v in df.columns:
                                    rename_dict[v] = std_col
                                    break
                        df = df.rename(columns=rename_dict)
                        all_dfs.append(df)
                    except Exception as e:
                        print(f"⚠️ Error loading {file_path}: {e}")

    if not all_dfs:
        print("❌ No raw Excel files found in historical_data or backend/knowledge_base/")
        return

    # 2. CLEAN & AGGREGATE DATA
    print("🧹 Cleaning and standardizing tender data...")
    raw_df = pd.concat(all_dfs, ignore_index=True)

    if 'tender_no' not in raw_df.columns:
        print("❌ Error: Could not identify 'tender_no' column in your Excel files.")
        return

    raw_df['tender_no'] = raw_df['tender_no'].astype(str).str.strip().str.upper()
    raw_df = raw_df[~raw_df['tender_no'].isin(['NAN', 'NONE', '', 'SR_NO'])]

    for col in ['received_date', 'due_date']:
        if col in raw_df.columns:
            raw_df[col] = pd.to_datetime(raw_df[col], errors='coerce')

    for col in ['tender_open_price', 'quoted_value']:
        if col in raw_df.columns:
            raw_df[col] = raw_df[col].apply(clean_currency)

    if 'tender_status' in raw_df.columns:
        raw_df['tender_status'] = raw_df['tender_status'].apply(standardize_status)

    # Deduplicate within the Excel data, keeping latest
    sort_cols = ['tender_no', 'received_date'] if 'received_date' in raw_df.columns else ['tender_no']
    clean_df = raw_df.sort_values(by=sort_cols, ascending=True).groupby('tender_no', as_index=False).last()

    print(f"✨ Cleaned {len(clean_df)} unique records from Excel files.")

    # 3. UPDATE LOCAL SQLITE (DEDUPLICATED)
    os.makedirs(os.path.dirname(SQLITE_DB), exist_ok=True)
    sqlite_conn = sqlite3.connect(SQLITE_DB)
    
    # Check if table exists to prevent duplicate entries
    table_exists = sqlite_conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tenders'").fetchone()
    
    if table_exists:
        existing_df = pd.read_sql("SELECT tender_no FROM tenders", sqlite_conn)
        existing_ids = set(existing_df['tender_no'].astype(str).str.upper().tolist())
        new_records = clean_df[~clean_df['tender_no'].isin(existing_ids)].copy()
        print(f"ℹ️ Found {len(existing_ids)} existing tenders in local DB.")
        print(f"➕ Adding {len(new_records)} NEW tenders to local DB...")
        if not new_records.empty:
            new_records.to_sql('tenders', sqlite_conn, if_exists='append', index=False)
    else:
        print("⚙️ Initializing new 'tenders' table in local SQLite...")
        clean_df.to_sql('tenders', sqlite_conn, if_exists='replace', index=False)
        new_records = clean_df

    sqlite_conn.close()

    # 4. MIGRATE EVERYTHING TO NEON CLOUD POSTGRESQL
    print("☁️ Syncing local database to Neon Cloud PostgreSQL...")
    try:
        sqlite_conn = sqlite3.connect(SQLITE_DB)
        pg_engine = create_engine(POSTGRES_URL)

        cursor = sqlite_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [t[0] for t in cursor.fetchall()]

        for tbl in tables:
            df_table = pd.read_sql(f"SELECT * FROM {tbl}", sqlite_conn)
            df_table.to_sql(tbl, pg_engine, if_exists='replace', index=False)
            print(f"✅ Table '{tbl}' successfully pushed to Cloud Neon ({len(df_table)} rows).")

        sqlite_conn.close()
        print("\n🎉 ALL DONE! Your 2025–26 data is cleaned, stored locally, and live in Neon Cloud!")

    except Exception as e:
        print(f"❌ Cloud migration error: {e}")

if __name__ == "__main__":
    run_pipeline()
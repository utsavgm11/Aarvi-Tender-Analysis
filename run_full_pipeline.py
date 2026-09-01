import os
import re
import sqlite3
import pandas as pd
import numpy as np
import psycopg2
from dotenv import load_dotenv

# --- LOAD ENVIRONMENT VARIABLES ---
env_path = os.path.join('backend', '.env')
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

# --- CONFIGURATION ---
SQLITE_DB = os.path.join('backend', 'tender_data.db')
POSTGRES_URL = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")

if not POSTGRES_URL:
    raise ValueError("❌ Error: DATABASE_URL is missing from backend/.env file!")

SEARCH_FOLDERS = [
    './historical_data',
    os.path.join('backend', 'knowledge_base')
]

# Comprehensive mappings for 2019 through 2027 data variations
COLUMN_VARIANTS = {
    'tender_no': ['tender_no', 'tender_no_', 'tender_no.', 'tender_number', 'ref_no', 'tender_ref', 'sr_no', 'rfq_no'],
    'name_of_client': ['client', 'client_name', 'name_of_client', 'customer', 'operator', 'company'],
    'tender_status': ['status', 'tender_status', 'current_status', 'stage'],
    'tender_open_price': ['value', 'estimated_value', 'tender_value', 'tender_price', 'amount', 'cost', 'project_value'],
    'quoted_value': ['quoted_amount', 'our_quote', 'quoted_value', 'final_quote', 'bid_value'],
    'received_date': ['date', 'received_date', 'inward_date', 'receipt_date', 'issue_date'],
    'due_date': ['due_date', 'closing_date', 'submission_date', 'expiry_date'],
    'pre_bidding_date': ['pre_bid_date', 'pre_bidding_date', 'meeting_date'],
    'location': ['location', 'place', 'site', 'region', 'state'],
    'project_manager': ['project_manager', 'manager', 'pm', 'lead', 'handled_by'],
    'financial_year': ['financial_year', 'fy', 'fin_year', 'year'],
    'emd': ['emd', 'emd_amount', 'earnest_money'],
    'description': ['description', 'scope', 'work_description', 'subject', 'particulars'],
    'comments': ['comments', 'remarks', 'notes', 'loss_reason']
}

def clean_currency(value):
    if pd.isna(value) or value == "" or str(value).strip() in ['-', 'N/A', 'None']: 
        return 0.0
    text_val = str(value).upper().replace(',', '').replace('RS.', '').replace('/-', '').strip()
    num = re.findall(r"[-+]?\d*\.\d+|\d+", text_val)
    return float(num[0]) if num else 0.0

def standardize_status(val):
    val = str(val).lower().strip()
    if 'won' in val or 'award' in val: return "Tender Won"
    if 'lost' in val or 'reject' in val: return "Tender Lost"
    if 'quote' in val or 'submitted' in val or 'participate' in val: return "Tender Quoted"
    if 'cancel' in val or 'retender' in val: return "Cancelled"
    return "Tender Received"

def clean_empty_str(val):
    if pd.isna(val) or str(val).strip().lower() in ['nan', 'none', 'null', '']:
        return None
    return str(val).strip()

def calculate_financial_year(date_val):
    """Dynamically calculates Indian Financial Year (April - March) if missing in Excel."""
    if pd.isna(date_val) or not date_val: 
        return None
    try:
        d = pd.to_datetime(date_val)
        if d.month >= 4:
            return f"{d.year}-{d.year+1}"
        else:
            return f"{d.year-1}-{d.year}"
    except:
        return None

def run_pipeline():
    print("🚀 === STARTING INTELLIGENT DATA CLEANING & SYNC PIPELINE ===")

    # 1. LOAD RAW EXCEL FILES
    all_dfs = []
    for folder in SEARCH_FOLDERS:
        if os.path.exists(folder):
            for file in os.listdir(folder):
                if file.endswith(('.xlsx', '.xlsm', '.xls')) and not file.startswith('~'):
                    file_path = os.path.join(folder, file)
                    print(f"📂 Scanning: {file_path}")
                    try:
                        df = pd.read_excel(file_path, engine='openpyxl')
                        df.columns = [re.sub(r'[\s/.]+', '_', str(c).strip().lower()).strip('_') for c in df.columns]
                        
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
        print("❌ No raw Excel files found in historical_data/ or backend/knowledge_base/")
        return

    # 2. AGGREGATE & CLEAN
    print("🧹 Cleaning and standardizing historical tender data...")
    raw_df = pd.concat(all_dfs, ignore_index=True)

    if 'tender_no' not in raw_df.columns:
        print("❌ Error: Could not identify 'tender_no' column. Sync aborted.")
        return

    # Strip whitespace, drop completely blank tender numbers
    raw_df['tender_no'] = raw_df['tender_no'].astype(str).str.strip().str.upper()
    raw_df = raw_df[~raw_df['tender_no'].isin(['NAN', 'NONE', '', 'SR_NO', 'NULL', 'NA'])]

    # Date normalization
    for col in ['received_date', 'due_date', 'pre_bidding_date']:
        if col in raw_df.columns:
            raw_df[col] = pd.to_datetime(raw_df[col], errors='coerce').dt.strftime('%Y-%m-%d')

    # Currency normalization
    for col in ['tender_open_price', 'quoted_value']:
        if col in raw_df.columns:
            raw_df[col] = raw_df[col].apply(clean_currency)

    # Status normalization
    if 'tender_status' in raw_df.columns:
        raw_df['tender_status'] = raw_df['tender_status'].apply(standardize_status)

    # 3. DEDUPLICATION (Keep most recent record per tender_no)
    sort_cols = [c for c in ['received_date', 'due_date'] if c in raw_df.columns]
    if sort_cols:
        clean_df = raw_df.sort_values(by=sort_cols, ascending=True).groupby('tender_no', as_index=False).last()
    else:
        clean_df = raw_df.groupby('tender_no', as_index=False).last()

    # Sanitize dataframe to prevent PostgreSQL crashes on NaN
    clean_df = clean_df.replace({np.nan: None})

    print(f"✨ Extracted {len(clean_df)} UNIQUE, cleaned records across all years.")

    # 4. UPDATE LOCAL SQLITE (Append Only)
    os.makedirs(os.path.dirname(SQLITE_DB), exist_ok=True)
    try:
        sqlite_conn = sqlite3.connect(SQLITE_DB)
        table_exists = sqlite_conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tenders'").fetchone()
        
        if table_exists:
            existing_df = pd.read_sql("SELECT tender_no FROM tenders", sqlite_conn)
            existing_ids = set(existing_df['tender_no'].astype(str).str.upper().tolist())
            new_records = clean_df[~clean_df['tender_no'].isin(existing_ids)].copy()
            if not new_records.empty:
                new_records.to_sql('tenders', sqlite_conn, if_exists='append', index=False)
        else:
            clean_df.to_sql('tenders', sqlite_conn, if_exists='replace', index=False)
        sqlite_conn.close()
    except Exception as e:
        print(f"⚠️ Local SQLite update skipped or failed: {e}")

    # 5. SAFE UPSERT TO NEON CLOUD POSTGRESQL (NON-DESTRUCTIVE)
    print("☁️ Safely merging line-by-line into Neon Cloud PostgreSQL...")
    try:
        pg_conn = psycopg2.connect(POSTGRES_URL)
        cur = pg_conn.cursor()

        synced_count = 0
        for _, row in clean_df.iterrows():
            t_no = clean_empty_str(row.get('tender_no'))
            if not t_no: continue

            # Smart Financial Year Assignment
            fin_year = clean_empty_str(row.get('financial_year'))
            if not fin_year:
                fin_year = calculate_financial_year(row.get('received_date')) or calculate_financial_year(row.get('due_date')) or 'Unknown'

            cur.execute("""
                INSERT INTO tenders (
                    tender_no, name_of_client, tender_status, 
                    received_date, due_date, pre_bidding_date,
                    tender_open_price, quoted_value, location, 
                    project_manager, financial_year, emd, description, comments
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (tender_no) DO UPDATE SET
                    financial_year = COALESCE(EXCLUDED.financial_year, tenders.financial_year),
                    tender_status = EXCLUDED.tender_status,
                    tender_open_price = COALESCE(EXCLUDED.tender_open_price, tenders.tender_open_price),
                    quoted_value = COALESCE(EXCLUDED.quoted_value, tenders.quoted_value),
                    project_manager = COALESCE(EXCLUDED.project_manager, tenders.project_manager),
                    comments = COALESCE(EXCLUDED.comments, tenders.comments),
                    due_date = COALESCE(EXCLUDED.due_date, tenders.due_date);
            """, (
                t_no,
                clean_empty_str(row.get('name_of_client')) or 'Unknown Client',
                clean_empty_str(row.get('tender_status')) or 'Tender Received',
                clean_empty_str(row.get('received_date')),
                clean_empty_str(row.get('due_date')),
                clean_empty_str(row.get('pre_bidding_date')),
                float(row.get('tender_open_price') or 0.0),
                float(row.get('quoted_value') or 0.0),
                clean_empty_str(row.get('location')),
                clean_empty_str(row.get('project_manager')),
                fin_year,
                clean_empty_str(row.get('emd')),
                clean_empty_str(row.get('description')),
                clean_empty_str(row.get('comments'))
            ))
            synced_count += 1

        pg_conn.commit()
        cur.close()
        pg_conn.close()

        print(f"\n🎉 ALL DONE! Successfully extracted and synced {synced_count} unique records into Neon Cloud.")

    except Exception as e:
        print(f"❌ Cloud sync error: {e}")

if __name__ == "__main__":
    run_pipeline()
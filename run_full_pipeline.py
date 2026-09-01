import os
import re
import sqlite3
import pandas as pd
import numpy as np
import psycopg2
import time
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

    all_dfs = []
    for folder in SEARCH_FOLDERS:
        if os.path.exists(folder):
            for file in os.listdir(folder):
                if file.endswith(('.xlsx', '.xlsm', '.xls')) and not file.startswith('~'):
                    file_path = os.path.join(folder, file)
                    print(f"📂 Scanning: {file_path}")
                    try:
                        import warnings
                        import openpyxl
                        warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')
                        
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
        print("❌ No raw Excel files found.")
        return

    print("🧹 Cleaning and standardizing historical tender data...")
    raw_df = pd.concat(all_dfs, ignore_index=True)

    if 'tender_no' not in raw_df.columns:
        print("❌ Error: Could not identify 'tender_no' column. Sync aborted.")
        return

    raw_df['tender_no'] = raw_df['tender_no'].astype(str).str.strip().str.upper()
    raw_df = raw_df[~raw_df['tender_no'].isin(['NAN', 'NONE', '', 'SR_NO', 'NULL', 'NA'])]

    for col in ['received_date', 'due_date', 'pre_bidding_date']:
        if col in raw_df.columns:
            raw_df[col] = pd.to_datetime(raw_df[col], errors='coerce').dt.strftime('%Y-%m-%d')

    for col in ['tender_open_price', 'quoted_value']:
        if col in raw_df.columns:
            raw_df[col] = raw_df[col].apply(clean_currency)

    if 'tender_status' in raw_df.columns:
        raw_df['tender_status'] = raw_df['tender_status'].apply(standardize_status)

    sort_cols = [c for c in ['received_date', 'due_date'] if c in raw_df.columns]
    if sort_cols:
        clean_df = raw_df.sort_values(by=sort_cols, ascending=True).groupby('tender_no', as_index=False).last()
    else:
        clean_df = raw_df.groupby('tender_no', as_index=False).last()

    clean_df = clean_df.replace({np.nan: None})
    total_records = len(clean_df)
    print(f"✨ Extracted {total_records} UNIQUE, cleaned records across all years.")

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

    print("☁️ Safely merging into Neon Cloud PostgreSQL in batches to prevent timeouts...")
    
    synced_count = 0
    inserted_count = 0
    updated_count = 0
    batch_size = 100

    for start_idx in range(0, total_records, batch_size):
        end_idx = min(start_idx + batch_size, total_records)
        batch_df = clean_df.iloc[start_idx:end_idx]
        
        retries = 3
        while retries > 0:
            try:
                pg_conn = psycopg2.connect(POSTGRES_URL)
                cur = pg_conn.cursor()
                
                batch_inserted = 0
                batch_updated = 0

                for _, row in batch_df.iterrows():
                    t_no = clean_empty_str(row.get('tender_no'))
                    if not t_no: continue

                    fin_year = clean_empty_str(row.get('financial_year'))
                    if not fin_year:
                        fin_year = calculate_financial_year(row.get('received_date')) or calculate_financial_year(row.get('due_date')) or 'Unknown'

                    t_price_val = float(row.get('tender_open_price') or 0.0)
                    q_price_val = float(row.get('quoted_value') or 0.0)
                    t_price_str = str(t_price_val) if t_price_val > 0 else None
                    q_price_str = str(q_price_val) if q_price_val > 0 else None

                    cur.execute("SELECT tender_no FROM tenders WHERE tender_no = %s", (t_no,))
                    exists = cur.fetchone()

                    if exists:
                        cur.execute("""
                            UPDATE tenders SET
                                financial_year = COALESCE(%s, financial_year),
                                tender_status = %s,
                                tender_open_price = COALESCE(%s, tender_open_price),
                                quoted_value = COALESCE(%s, quoted_value),
                                project_manager = COALESCE(%s, project_manager),
                                comments = COALESCE(%s, comments),
                                due_date = COALESCE(%s, due_date)
                            WHERE tender_no = %s;
                        """, (
                            fin_year,
                            clean_empty_str(row.get('tender_status')) or 'Tender Received',
                            t_price_str,
                            q_price_str,
                            clean_empty_str(row.get('project_manager')),
                            clean_empty_str(row.get('comments')),
                            clean_empty_str(row.get('due_date')),
                            t_no
                        ))
                        batch_updated += 1
                    else:
                        cur.execute("""
                            INSERT INTO tenders (
                                tender_no, name_of_client, tender_status, 
                                received_date, due_date, pre_bidding_date,
                                tender_open_price, quoted_value, location, 
                                project_manager, financial_year, emd, description, comments
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            t_no,
                            clean_empty_str(row.get('name_of_client')) or 'Unknown Client',
                            clean_empty_str(row.get('tender_status')) or 'Tender Received',
                            clean_empty_str(row.get('received_date')),
                            clean_empty_str(row.get('due_date')),
                            clean_empty_str(row.get('pre_bidding_date')),
                            t_price_str,
                            q_price_str,
                            clean_empty_str(row.get('location')),
                            clean_empty_str(row.get('project_manager')),
                            fin_year,
                            clean_empty_str(row.get('emd')),
                            clean_empty_str(row.get('description')),
                            clean_empty_str(row.get('comments'))
                        ))
                        batch_inserted += 1

                pg_conn.commit()
                cur.close()
                pg_conn.close()
                
                inserted_count += batch_inserted
                updated_count += batch_updated
                synced_count += len(batch_df)
                
                print(f"🔄 Progress: Synced {synced_count} out of {total_records} records...")
                break # Success, break out of retry loop

            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                print(f"⚠️ Connection dropped by Neon. Retrying batch... ({retries} retries left)")
                retries -= 1
                time.sleep(2)
            except Exception as e:
                print(f"❌ Unhandled error in batch: {e}")
                break

    print(f"\n🎉 ALL DONE! Synced {synced_count} records (Added: {inserted_count}, Updated: {updated_count}) into Neon Cloud.")

if __name__ == "__main__":
    run_pipeline()
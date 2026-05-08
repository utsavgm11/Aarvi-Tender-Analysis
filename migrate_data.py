import pandas as pd
import numpy as np
import os
import re

# --- CONFIGURATION ---
DATA_FOLDER = "./historical_data"
OUTPUT_FILE = "Master_Tender_Cleaned_2018_2024.xlsx"

COLUMN_NAME_VARIANTS = {
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
    if pd.isna(value) or value == "" or str(value).strip() == '-': return 0.0
    text = str(value).upper().replace(',', '').replace('RS.', '').replace('/-', '').strip()
    num = re.findall(r"[-+]?\d*\.\d+|\d+", text)
    return float(num[0]) if num else 0.0

def standardize_status(val):
    val = str(val).lower().strip()
    if 'won' in val: return "Tender Won"
    if 'lost' in val: return "Tender Lost"
    if 'quote' in val: return "Tender Quoted"
    if 'cancel' in val: return "Cancelled"
    return "Tender Received"

def start_enterprise_cleaning():
    print("🚀 Starting Enterprise Data Cleaning Pipeline...")
    all_dfs = []
    
    if not os.path.exists(DATA_FOLDER):
        print(f"❌ Error: Folder {DATA_FOLDER} not found.")
        return

    files = [f for f in os.listdir(DATA_FOLDER) if f.endswith((".xlsx", ".xlsm"))]
    
    for filename in files:
        print(f"📂 Reading: {filename}...")
        path = os.path.join(DATA_FOLDER, filename)
        try:
            df = pd.read_excel(path, engine='openpyxl')
            # Standardize columns: remove dots, spaces, make lowercase
            df.columns = [re.sub(r'[\s/.]+', '_', str(col).strip().lower()).strip('_') for col in df.columns]
            
            rename_dict = {}
            for standard_name, variants in COLUMN_NAME_VARIANTS.items():
                for v in variants:
                    if v in df.columns:
                        rename_dict[v] = standard_name
                        break 
            
            df = df.rename(columns=rename_dict)
            df['source_file'] = filename
            all_dfs.append(df)
        except Exception as e:
            print(f"⚠️ Error reading {filename}: {e}")

    if not all_dfs:
        print("❌ No data loaded.")
        return

    master_df = pd.concat(all_dfs, ignore_index=True)

    # 1. Standardize Key
    master_df['tender_no'] = master_df['tender_no'].astype(str).str.strip().str.upper()
    master_df = master_df[~master_df['tender_no'].isin(['NAN', 'NONE', '', 'SR_NO'])]

    # 2. Clean Dates
    for col in ['received_date', 'due_date', 'pre_bidding_date']:
        if col in master_df.columns:
            master_df[col] = pd.to_datetime(master_df[col], errors='coerce')

    # 3. Clean Money
    for col in ['tender_open_price', 'quoted_value']:
        if col in master_df.columns:
            master_df[col] = master_df[col].apply(clean_currency)

    # 4. STABLE SURVIVORSHIP LOGIC
    print("💎 Merging records and preserving history...")
    
    # Sort by tender_no and date so latest info is at the bottom of the group
    sort_cols = []
    if 'received_date' in master_df.columns:
        sort_cols = ['tender_no', 'received_date']
    else:
        sort_cols = ['tender_no']
        
    master_df = master_df.sort_values(by=sort_cols, ascending=True)

    # Instead of apply(), we use groupby + last() 
    # This keeps 'tender_no' as a column and takes the latest available info
    master_df = master_df.groupby('tender_no', as_index=False).last()

    # 5. Normalization
    master_df['tender_status'] = master_df['tender_status'].apply(standardize_status)

    # 6. Final Save
    master_df.to_excel(OUTPUT_FILE, index=False)
    
    print("\n--- SUCCESS ---")
    print(f"Final Golden Records: {len(master_df)}")
    print(f"Clean Master Generated: {OUTPUT_FILE}")
    print("----------------\n")

if __name__ == "__main__":
    start_enterprise_cleaning()
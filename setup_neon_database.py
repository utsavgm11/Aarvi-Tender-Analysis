import os
import sqlite3
import pandas as pd
from dotenv import load_dotenv
from passlib.context import CryptContext
from sqlalchemy import create_engine, text

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

# Password Hashing matching main.py's CryptContext setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 10 Official User Credentials matching main.py requirements
USERS_DATA = [
    {"email": "utsavm@aarviencon.com", "role": "admin", "password": "Utsav@506506", "manager_name": "Utsav"},
    {"email": "aditya@aarviencon.com", "role": "admin", "password": "Aditya@1111", "manager_name": "Aditya"},
    {"email": "jaydev@aarviencon.com", "role": "admin", "password": "Jaydev@1705", "manager_name": "Jaydev"},
    {"email": "shreyas@aarviencon.com", "role": "admin", "password": "Shreyas@1705", "manager_name": "Shreyas"},
    {"email": "mahesh@aarviencon.com", "role": "project_manager", "password": "Mahesh@2345", "manager_name": "Mahesh"},
    {"email": "reyaz@aarviencon.com", "role": "project_manager", "password": "Reyaz@5467", "manager_name": "Reyaz"},
    {"email": "manvendra@aarviencon.com", "role": "project_manager", "password": "Manvendra@9087", "manager_name": "Manvendra"},
    {"email": "rakesh@aarviencon.com", "role": "project_manager", "password": "Rakesh@2678", "manager_name": "Rakesh"},
    {"email": "tushar@aarviencon.com", "role": "project_manager", "password": "Tushar@1405", "manager_name": "Tushar"},
    {"email": "rahul@aarviencon.com", "role": "admin", "password": "RahulK@64378", "manager_name": "Rahul"}
]

def initialize_neon_db():
    print("🚀 === INITIALIZING COMPLETE NEON CLOUD DATABASE ===")
    pg_engine = create_engine(POSTGRES_URL)

    with pg_engine.connect() as conn:
        # 1. CREATE USERS TABLE & AUTO-PATCH MISSING COLUMNS
        print("🛠️ Setting up 'users' table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(50) DEFAULT 'project_manager',
                manager_name VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        # Fix for pre-existing tables missing manager_name:
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS manager_name VARCHAR(255);"))
        conn.commit()

        # Seed Users with bcrypt hashed passwords
        print("👥 Seeding user accounts...")
        for user in USERS_DATA:
            p_hash = pwd_context.hash(user["password"])
            conn.execute(text("""
                INSERT INTO users (email, password_hash, role, manager_name)
                VALUES (:email, :password_hash, :role, :manager_name)
                ON CONFLICT (email) DO UPDATE SET
                    password_hash = EXCLUDED.password_hash,
                    role = EXCLUDED.role,
                    manager_name = EXCLUDED.manager_name;
            """), {
                "email": user["email"].lower(), 
                "password_hash": p_hash, 
                "role": user["role"],
                "manager_name": user["manager_name"]
            })
        conn.commit()
        print("✅ 'users' table created and seeded with 10 accounts!")

        # 2. CREATE AI_USAGE_LOGS TABLE
        print("🛠️ Setting up 'ai_usage_logs' table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ai_usage_logs (
                id SERIAL PRIMARY KEY,
                user_email VARCHAR(255),
                action_type VARCHAR(255),
                tender_no VARCHAR(255),
                input_tokens INT DEFAULT 0,
                output_tokens INT DEFAULT 0,
                estimated_cost_inr NUMERIC DEFAULT 0.0,
                usage_date DATE DEFAULT CURRENT_DATE
            );
        """))
        conn.commit()
        print("✅ 'ai_usage_logs' table ready!")

        # 3. CREATE CHAT_SESSIONS TABLE
        print("🛠️ Setting up 'chat_sessions' table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                session_id VARCHAR(255) PRIMARY KEY,
                title VARCHAR(255) DEFAULT 'New Analysis',
                user_email VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        conn.commit()
        print("✅ 'chat_sessions' table ready!")

        # 4. CREATE CHAT_MESSAGES TABLE
        print("🛠️ Setting up 'chat_messages' table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(255) REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
                role VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        conn.commit()
        print("✅ 'chat_messages' table ready!")

    # 5. MIGRATE TENDERS TABLE FROM LOCAL SQLITE
    print("🛠️ Syncing 'tenders' table to Neon...")
    if os.path.exists(SQLITE_DB):
        sqlite_conn = sqlite3.connect(SQLITE_DB)
        try:
            df_tenders = pd.read_sql("SELECT * FROM tenders", sqlite_conn)
            df_tenders.to_sql('tenders', pg_engine, if_exists='replace', index=False)
            
            # Ensure post-bid analytics columns exist on 'tenders' table
            with pg_engine.connect() as conn:
                conn.execute(text("ALTER TABLE tenders ADD COLUMN IF NOT EXISTS aarvi_rank VARCHAR(50);"))
                conn.execute(text("ALTER TABLE tenders ADD COLUMN IF NOT EXISTS reason_for_loss TEXT;"))
                conn.execute(text("ALTER TABLE tenders ADD COLUMN IF NOT EXISTS post_bid_remarks TEXT;"))
                conn.execute(text("ALTER TABLE tenders ADD COLUMN IF NOT EXISTS competitor_list JSONB;"))
                conn.commit()

            print(f"✅ 'tenders' table created and loaded with {len(df_tenders)} records!")
        except Exception as e:
            print(f"⚠️ Could not sync local tenders: {e}")
        finally:
            sqlite_conn.close()

    print("\n🎉 ALL 5 TABLES SUCCESSFULLY CREATED & LIVE IN NEON CLOUD!")

if __name__ == "__main__":
    initialize_neon_db()
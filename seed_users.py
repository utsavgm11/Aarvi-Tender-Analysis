import os
import sqlite3
from dotenv import load_dotenv
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

# User Credentials Data with Manager Names (Matching main.py requirements)
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

# Password Hashing Helper matching main.py's bcrypt setup
def hash_password(password):
    try:
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        return pwd_context.hash(password)
    except ImportError:
        try:
            from werkzeug.security import generate_password_hash
            return generate_password_hash(password)
        except ImportError:
            import hashlib
            return hashlib.sha256(password.encode('utf-8')).hexdigest()

def seed_database_users():
    print("👥 Starting User Seeding Process...")

    # 1. ENSURE LOCAL SQLITE USERS TABLE
    os.makedirs(os.path.dirname(SQLITE_DB), exist_ok=True)
    sqlite_conn = sqlite3.connect(SQLITE_DB)
    sqlite_cursor = sqlite_conn.cursor()

    sqlite_cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'project_manager',
            manager_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Patch local SQLite schema if manager_name column is missing
    try:
        sqlite_cursor.execute("ALTER TABLE users ADD COLUMN manager_name TEXT;")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Insert into local SQLite
    inserted_sqlite = 0
    for user in USERS_DATA:
        p_hash = hash_password(user["password"])
        try:
            sqlite_cursor.execute("""
                INSERT INTO users (email, password_hash, role, manager_name)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    password_hash=excluded.password_hash,
                    role=excluded.role,
                    manager_name=excluded.manager_name;
            """, (user["email"].lower(), p_hash, user["role"], user["manager_name"]))
            inserted_sqlite += 1
        except Exception as e:
            print(f"⚠️ SQLite insert issue for {user['email']}: {e}")

    sqlite_conn.commit()
    sqlite_conn.close()
    print(f"✅ Saved {inserted_sqlite} user credentials to local SQLite.")

    # 2. ENSURE NEON CLOUD POSTGRESQL USERS TABLE & SYNC
    print("☁️ Syncing user credentials to Neon Cloud...")
    try:
        pg_engine = create_engine(POSTGRES_URL)
        with pg_engine.connect() as conn:
            # Create table in Postgres
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

            # Auto-patch Postgres schema if manager_name column is missing from previous runs
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS manager_name VARCHAR(255);"))

            # Upsert into PostgreSQL
            for user in USERS_DATA:
                p_hash = hash_password(user["password"])
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
        print("🎉 ALL 10 USER ACCOUNTS SUCCESSFULLY UPDATED IN NEON CLOUD!")

    except Exception as e:
        print(f"❌ Failed to sync users to Neon: {e}")

if __name__ == "__main__":
    seed_database_users()
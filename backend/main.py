from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr
from datetime import datetime, date
from passlib.context import CryptContext

import csv
import io
import os
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional, List

# ----------------- IMPORTS -----------------
from ai_service import (
    generate_tender_summary,
    chat_with_tender,
    generate_chat_title
)
from file_parser import extract_text_from_upload

# ----------------- APP -----------------
app = FastAPI()

# ----------------- LIVE OCR PROGRESS STORE -----------------
progress_store = {}

# ----------------- CORS (UPDATED FOR PRODUCTION) -----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- DATABASE (UPDATED FOR PRODUCTION) -----------------
def get_db_connection():
    try:
        # Your live Neon Cloud URL
        NEON_URL = "postgresql://neondb_owner:npg_djW0Dm5HAPOa@ep-twilight-block-apopzllz-pooler.c-7.us-east-1.aws.neon.tech/neondb?sslmode=require"
        
        # Pulls from Render Environment if available, otherwise uses the Neon URL automatically
        db_url = os.getenv("DATABASE_URL", NEON_URL)
        
        # CRITICAL FIX: If your local Windows PC has an old "sqlite" URL stuck in its memory/env variables, 
        # this will ignore it and force the Cloud URL instead.
        if db_url and db_url.startswith("sqlite"):
            db_url = NEON_URL
            
        # Connect strictly to the cloud
        conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
        
        return conn
        
    except Exception as e:
        print(f"❌ Database Connection Error: {e}")
        return None

# ----------------- MODELS -----------------

# Auth Models
class AuthRequest(BaseModel):
    email: str
    password: str    

class Tender(BaseModel):
    tender_status: str
    received_date: Optional[str] = None
    due_date: Optional[str] = None
    name_of_client: str
    location: Optional[str] = None
    tender_no: str
    tender_open_price: Optional[float] = None
    quoted_value: Optional[float] = 0.0
    description: Optional[str] = None
    project_manager: Optional[str] = None
    emd: Optional[str] = None
    emd_status: Optional[str] = None
    tender_fee_status: Optional[str] = None
    price_status: Optional[str] = None
    source: Optional[str] = None
    comments: Optional[str] = None
    docs_prepared_by: Optional[str] = None
    financial_year: Optional[str] = "2023-2024"
    pre_bidding_date: Optional[str] = None
    pre_bid_time: Optional[str] = None
    mode_of_conduct: Optional[str] = None
    platform_or_address: Optional[str] = None

class ChatRequest(BaseModel):
    query: str
    context: dict
    full_text: Optional[str] = ""

class SaveMessage(BaseModel):
    session_id: str
    role: str
    content: str
    title: Optional[str] = None

class TitleRequest(BaseModel):
    first_message: str

class SessionRename(BaseModel):
    title: str

class StatusUpdate(BaseModel):
    tender_status: str

# Setup Password Hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ----------------- STARTUP -----------------
@app.on_event("startup")
def print_routes():
    # Detect if we are on Render via the PORT env var
    port = os.getenv("PORT", "8001")
    print("\n==============================================")
    print("   AARVI ENCON TENDER SYSTEM ONLINE")
    print(f"   PORT: {port}")
    print("   DB: POSTGRESQL")
    print("   OCR ENGINE: TESSERACT")
    print("   AI ENGINE: GEMINI FLASH")
    print("==============================================\n")

# ----------------- HEALTH -----------------
@app.get("/health")
async def health_check():
    return {
        "status": "online",
        "timestamp": date.today().isoformat()
    }

# ----------------- OCR PROGRESS -----------------
@app.get("/progress/{task_id}")
async def get_progress(task_id: str):
    return progress_store.get(task_id, {
        "current": 0,
        "total": 1
    })

# ----------------- AI ANALYSIS -----------------
@app.post("/analyze-tender")
async def analyze_tender(
    files: List[UploadFile] = File(...),
    task_id: str = Form(...)
):
    print(f"\n[DEBUG] Analysis Started: {task_id}")
    try:
        combined_text = ""
        for file in files:
            tender_text = await extract_text_from_upload(
                file,
                task_id=task_id
            )
            if tender_text:
                combined_text += (
                    f"\n\n--- Document: {file.filename} ---\n"
                    f"{tender_text}\n"
                )
                
        if not combined_text.strip():
            raise HTTPException(
                status_code=400,
                detail="Could not extract text from uploaded files."
            )
            
        result = generate_tender_summary(combined_text)
        return {"aarvi_intelligence": result}

    except Exception as e:
        print(f"PIPELINE ERROR: {e}")
        return {"error": str(e)}

    finally:
        if task_id in progress_store:
            del progress_store[task_id]


# ----------------- AUTH ROUTES -----------------
@app.post("/signup")
def signup(req: AuthRequest):
    # Strict Company Domain Filter
    if not req.email.lower().endswith("@aarviencon.com"):
        raise HTTPException(
            status_code=400, 
            detail="Registration denied. Only @aarviencon.com emails allowed."
        )
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        hashed_pw = pwd_context.hash(req.password)
        
        # New users default to 'project_manager' role
        cur.execute(
            "INSERT INTO users (email, password_hash, role) VALUES (%s, %s, %s)",
            (req.email.lower(), hashed_pw, "project_manager")
        )
        conn.commit()
        return {"message": "Account created successfully as Project Manager."}
    except Exception as e:
        raise HTTPException(status_code=400, detail="Email already registered.")
    finally:
        if conn: conn.close()

@app.post("/login")
def login(req: AuthRequest):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        # Find user by email
        cur.execute("SELECT email, password_hash, role FROM users WHERE email = %s", (req.email.lower(),))
        user = cur.fetchone()

        if not user or not pwd_context.verify(req.password, user['password_hash']):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Return info that the frontend will store in localStorage
        return {
            "status": "success",
            "email": user['email'],
            "role": user['role']
        }
    finally:
        if conn: conn.close()            

# ----------------- CHAT -----------------
@app.post("/chat/")
async def chat_endpoint(req: ChatRequest):
    try:
        reply = chat_with_tender(
            query=req.query,
            context=req.context,
            full_text=req.full_text
        )
        return {"reply": reply}
    except Exception as e:
        return {"error": str(e)}

# ----------------- CHAT HISTORY -----------------
@app.get("/chats/sessions")
def get_sessions(q: Optional[str] = None):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        if q:
            query = """
                SELECT * FROM chat_sessions
                WHERE title ILIKE %s
                ORDER BY created_at DESC
            """
            cur.execute(query, (f"%{q}%",))
        else:
            cur.execute("SELECT * FROM chat_sessions ORDER BY created_at DESC")
        
        sessions = cur.fetchall()
        return [dict(s) for s in sessions]
    finally:
        if conn: conn.close()

@app.get("/chats/history/{session_id}")
def get_history(session_id: str):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT role, content
            FROM chat_messages
            WHERE session_id = %s
            ORDER BY timestamp ASC
            """,
            (session_id,)
        )
        messages = cur.fetchall()
        return [dict(m) for m in messages]
    finally:
        if conn: conn.close()

@app.post("/chats/message")
def save_chat_message(data: SaveMessage):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        # PostgreSQL syntax for INSERT OR IGNORE
        cur.execute(
            """
            INSERT INTO chat_sessions (session_id, title)
            VALUES (%s, %s)
            ON CONFLICT (session_id) DO NOTHING
            """,
            (data.session_id, data.title or "New Analysis")
        )

        cur.execute(
            """
            INSERT INTO chat_messages (session_id, role, content)
            VALUES (%s, %s, %s)
            """,
            (data.session_id, data.role, data.content)
        )
        conn.commit()
        return {"status": "saved"}
    finally:
        if conn: conn.close()

@app.post("/chats/generate-title")
def generate_title(req: TitleRequest):
    try:
        title = generate_chat_title(req.first_message)
        return {"title": title}
    except Exception:
        return {"title": "New Analysis"}

@app.put("/chats/sessions/{session_id}")
def rename_session(session_id: str, data: SessionRename):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE chat_sessions
            SET title = %s
            WHERE session_id = %s
            """,
            (data.title, session_id)
        )
        conn.commit()
        return {"status": "renamed"}
    finally:
        if conn: conn.close()

@app.post("/chats/clone/{session_id}")
def clone_chat(session_id: str):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        new_session_id = str(uuid.uuid4())

        cur.execute(
            """
            SELECT title
            FROM chat_sessions
            WHERE session_id = %s
            """,
            (session_id,)
        )
        original = cur.fetchone()

        title = (
            original["title"] + " (Imported)"
            if original else "Imported Chat"
        )

        cur.execute(
            """
            INSERT INTO chat_sessions (session_id, title)
            VALUES (%s, %s)
            """,
            (new_session_id, title)
        )

        cur.execute(
            """
            INSERT INTO chat_messages (session_id, role, content)
            SELECT %s, role, content
            FROM chat_messages
            WHERE session_id = %s
            """,
            (new_session_id, session_id)
        )
        conn.commit()
        return {"new_session_id": new_session_id}

    except Exception as e:
        return {"error": str(e)}

    finally:
        if conn: conn.close()

@app.delete("/chats/sessions/{session_id}")
def delete_session(session_id: str):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM chat_messages WHERE session_id = %s", (session_id,))
        cur.execute("DELETE FROM chat_sessions WHERE session_id = %s", (session_id,))
        conn.commit()
        return {"status": "deleted"}
    except Exception as e:
        return {"error": str(e)}
    finally:
        if conn: conn.close()

# ----------------- KPI -----------------
@app.get("/kpi-stats")
def get_kpi_stats(year: str = "All"):
    conn = get_db_connection()
    if not conn:
        return {"total_count": 0, "win_rate": 0, "total_won_value": 0, "active_pipeline": 0}
    
    try:
        cur = conn.cursor()
        query = """
        SELECT
            COUNT(*) AS total_count,
            ROUND(
                CAST(
                    SUM(CASE WHEN tender_status = 'Tender Won' THEN 1 ELSE 0 END) AS NUMERIC
                ) * 100.0 /
                NULLIF(
                    CAST(
                        SUM(CASE WHEN tender_status IN ('Tender Won', 'Tender Lost') THEN 1 ELSE 0 END) AS NUMERIC
                    ), 0
                ),
            1) AS win_rate,
            
            SUM(
                CASE
                    WHEN tender_status = 'Tender Won' THEN CAST(NULLIF(tender_open_price::text, '') AS NUMERIC)
                    ELSE 0.0
                END
            ) AS total_won_value,
            
            SUM(
                CASE
                    WHEN tender_status IN ('Tender Quoted', 'Quoted', 'Quoted Active')
                    AND (due_date::text >= CURRENT_DATE::text OR due_date IS NULL)
                    THEN 1
                    ELSE 0
                END
            ) AS active_pipeline
        FROM tenders
        WHERE (%s = 'All' OR financial_year = %s)
        AND tender_status != 'Quoted Legacy'
        """
        cur.execute(query, (year, year))
        row = cur.fetchone()
        
        # --- CRITICAL FIX: Explicit Type Conversion for React Charts ---
        if row:
            return {
                "total_count": int(row.get("total_count") or 0),
                "win_rate": float(row.get("win_rate") or 0.0),
                "total_won_value": float(row.get("total_won_value") or 0.0),
                "active_pipeline": int(row.get("active_pipeline") or 0)
            }
        
        return {"total_count": 0, "win_rate": 0, "total_won_value": 0, "active_pipeline": 0}

    except Exception as e:
        print(f"❌ KPI Error: {e}")
        return {"error": str(e)}
    finally:
        if conn: conn.close()

# ----------------- UPCOMING PREBID -----------------
@app.get("/tenders/upcoming-prebid")
def get_upcoming_prebids():
    today = date.today().isoformat()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        query = """
            SELECT * FROM tenders
            WHERE pre_bidding_date >= %s
            AND pre_bidding_date IS NOT NULL
            ORDER BY pre_bidding_date ASC
        """
        cur.execute(query, (today,))
        tenders = cur.fetchall()
        return [dict(t) for t in tenders]
    finally:
        if conn: conn.close()

# ----------------- GET TENDERS -----------------
@app.get("/tenders")
def get_tenders():
    conn = get_db_connection()
    today = datetime.now().strftime('%Y-%m-%d')
    try:
        cur = conn.cursor()
        query = f"""
            SELECT * FROM tenders
            ORDER BY 
                CASE 
                    WHEN due_date >= '{today}' THEN 0 
                    ELSE 1 
                END ASC,
                CASE 
                    WHEN due_date >= '{today}' THEN due_date 
                END ASC,
                CASE 
                    WHEN due_date < '{today}' THEN due_date 
                END DESC
        """
        cur.execute(query)
        tenders = cur.fetchall()
        return [dict(t) for t in tenders]
    finally:
        if conn: conn.close()

# ----------------- ADD TENDER -----------------
@app.post("/tenders")
def add_tender(t: Tender):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        query = """
            INSERT INTO tenders (
                tender_status, received_date, due_date, name_of_client, location,
                tender_no, tender_open_price, quoted_value, description, project_manager,
                emd, emd_status, tender_fee_status, price_status, source,
                comments, docs_prepared_by, financial_year, pre_bidding_date, pre_bid_time,
                mode_of_conduct, platform_or_address
            )
            VALUES (
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                %s,%s
            )
        """
        cur.execute(
            query,
            (
                t.tender_status, t.received_date, t.due_date, t.name_of_client, t.location,
                t.tender_no, t.tender_open_price, t.quoted_value, t.description, t.project_manager,
                t.emd, t.emd_status, t.tender_fee_status, t.price_status, t.source,
                t.comments, t.docs_prepared_by, t.financial_year, t.pre_bidding_date, t.pre_bid_time,
                t.mode_of_conduct, t.platform_or_address
            )
        )
        conn.commit()
        return {"message": "Success"}

    except Exception as e:
        print(f"DATABASE ERROR: {e}")
        return {"error": str(e)}

    finally:
        if conn: conn.close()

# ----------------- EXPORT -----------------
@app.get("/export-tenders")
def export_tenders():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tenders")
        tenders = cur.fetchall()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Tender No", "Client", "Status", "Received Date",
            "Due Date", "Pre-Bid Date", "Quoted Value", "Project Manager"
        ])

        for t in tenders:
            writer.writerow([
                t["tender_no"], t["name_of_client"], t["tender_status"], t["received_date"],
                t["due_date"], t["pre_bidding_date"], t["quoted_value"], t["project_manager"]
            ])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=tenders_export.csv"
            }
        )

    finally:
        if conn: conn.close()

# ----------------- QUICK STATUS UPDATE -----------------
@app.patch("/tenders/{tender_no:path}/status")
def quick_update_status(tender_no: str, update: StatusUpdate):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE tenders
            SET tender_status = %s
            WHERE tender_no = %s
            """,
            (update.tender_status, tender_no)
        )
        conn.commit()
        return {"message": "Status updated successfully"}

    except Exception as e:
        return {"error": str(e)}

    finally:
        if conn: conn.close()

# ----------------- DELETE TENDER -----------------
@app.delete("/tenders/{tender_no:path}")
def delete_tender(tender_no: str):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM tenders
            WHERE tender_no = %s
            """,
            (tender_no,)
        )
        conn.commit()

        if cur.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Tender not found"
            )

        return {"message": "Tender deleted successfully"}

    except Exception as e:
        return {"error": str(e)}

    finally:
        if conn: conn.close()

# ----------------- UPDATE TENDER -----------------
@app.put("/tenders/{tender_no:path}")
def update_tender(tender_no: str, t: Tender):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE tenders SET
                name_of_client=%s, tender_status=%s, received_date=%s, due_date=%s,
                pre_bidding_date=%s, pre_bid_time=%s, mode_of_conduct=%s, platform_or_address=%s,
                location=%s, tender_open_price=%s, quoted_value=%s, description=%s,
                project_manager=%s, emd=%s, emd_status=%s, tender_fee_status=%s,
                price_status=%s, source=%s, comments=%s, docs_prepared_by=%s,
                financial_year=%s
            WHERE tender_no=%s
            """,
            (
                t.name_of_client, t.tender_status, t.received_date, t.due_date,
                t.pre_bidding_date, t.pre_bid_time, t.mode_of_conduct, t.platform_or_address,
                t.location, t.tender_open_price, t.quoted_value, t.description,
                t.project_manager, t.emd, t.emd_status, t.tender_fee_status,
                t.price_status, t.source, t.comments, t.docs_prepared_by,
                t.financial_year, tender_no
            )
        )
        conn.commit()
        return {"message": "Updated successfully"}

    except Exception as e:
        return {"error": str(e)}

    finally:
        if conn: conn.close()

# ----------------- MAIN -----------------
if __name__ == "__main__":
    import uvicorn
    # Use environment variables for port to support cloud hosting properly
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
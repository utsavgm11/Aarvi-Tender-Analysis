from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr
from datetime import datetime, date
from passlib.context import CryptContext
from psycopg2.extras import RealDictCursor
from typing import Optional, List

import csv
import io
import os
import uuid
import psycopg2

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
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "https://attract-appeals-recorded-able.trycloudflare.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- DATABASE (UPDATED FOR PRODUCTION) -----------------
def get_db_connection():
    try:
        # 🎯 Pull strictly from your .env file or hosting environment variables
        db_url = os.getenv("DATABASE_URL")
        
        # Safety fallback check: If the environment variable is completely empty
        if not db_url:
            print("❌ Database Connection Error: DATABASE_URL is missing from environment!")
            return None
            
        # CRITICAL FIX: If your local machine has an old "sqlite" URL stuck in memory,
        # this safely flags it out so it doesn't crash the psycopg2 engine.
        if db_url.startswith("sqlite"):
            print("⚠️ Warning: Detected an invalid SQLite string in DATABASE_URL environment.")
            return None
            
        # Establish a clean dictionary-mapped connection to the cloud
        conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
        return conn
        
    except Exception as e:
        print(f"❌ Database Connection Error: {e}")
        return None
# ----------------- NEW: USAGE LOGGING HELPER -----------------
def log_system_ai_usage(user_email: str, action_type: str, tender_no: str, input_tokens: int, output_tokens: int, estimated_cost: float):
    conn = get_db_connection()
    if not conn:
        print("❌ DB LOGGING FAILED: Could not establish database connection.")
        return
    try:
        conn.autocommit = True
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        print(f"⚙️ [DB DEBUG] Attempting insert into table for User: {user_email}, Tender: {tender_no}")
        
        # 🎯 FIX: We removed 'id' from the INSERT. PostgreSQL will auto-increment its own integer id!
        cur.execute("""
            INSERT INTO ai_usage_logs (user_email, action_type, tender_no, input_tokens, output_tokens, estimated_cost_inr, usage_date)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_DATE);
        """, (
            user_email.lower().strip(),  
            action_type,                 
            tender_no or 'N/A',          
            int(input_tokens or 0),      
            int(output_tokens or 0),     
            float(estimated_cost or 0.0) 
        ))
        print("✅ [DB DEBUG] SUCCESS! Insertion statement completed cleanly. Row added to database!")
        
    except Exception as e:
        print(f"❌ [DB CRITICAL FAILURE] Database insertion rejected: {e}")
    finally:
        if conn: conn.close()
# ----------------- MODELS -----------------

# Auth Models
class AuthRequest(BaseModel):
    email: str
    password: str    

class NewUser(BaseModel):
    email: str
    password: str
    role: str

class PasswordReset(BaseModel):
    email: str
    newPassword: str  

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
    user_email: str # ✅ Added to track chat costs

class SaveMessage(BaseModel):
    session_id: str
    role: str
    content: str
    title: Optional[str] = None
    user_email: str

class TitleRequest(BaseModel):
    first_message: str

class SessionRename(BaseModel):
    title: str

class StatusUpdate(BaseModel):
    tender_status: str

# ---> PASTE THESE NEW MODELS HERE <---
class CompetitorEntry(BaseModel):
    rank: str
    company: str
    amount: Optional[float] = 0.00
    percent_diff: Optional[float] = 0.00

class FullPostBidPayload(BaseModel):
    aarvi_rank: str
    reason_for_loss: str
    post_bid_remarks: Optional[str] = "No Remarks"
    competitors: List[CompetitorEntry]

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
    task_id: str = Form(...),
    user_email: str = Form(...) 
):
    print(f"\n[DEBUG] Analysis Started for Task: {task_id} by User: {user_email}")
    try:
        combined_text = ""
        for file in files:
            tender_text = await extract_text_from_upload(file, task_id=task_id)
            if tender_text:
                combined_text += f"\n\n--- Document: {file.filename} ---\n{tender_text}\n"
                
        if not combined_text.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from uploaded files.")
            
        # Fire the ai_service function
        result = generate_tender_summary(combined_text)
        
        # 📊 MATCHING THE AI_SERVICE KEY STRUCTURE PERFECTLY
        in_tokens = result.get("input_tokens", 4500)
        out_tokens = result.get("output_tokens", 1200)
        t_no = result.get("tender_no", "N/A")
        ui_payload = result.get("ui_data", result)

        # Force baseline simulation tokens if they evaluate to zero
        if not in_tokens or in_tokens == 0: in_tokens = 4500
        if not out_tokens or out_tokens == 0: out_tokens = 1200

        # Calculate exact financial rates
        computed_cost = (in_tokens * 0.00001) + (out_tokens * 0.00003)
        
        # Log to postgres database cleanly
        log_system_ai_usage(user_email, "Tender Scan Analysis", t_no, in_tokens, out_tokens, computed_cost)

        return {"aarvi_intelligence": ui_payload}

    except Exception as e:
        print(f"❌ PIPELINE ERROR inside analyze-tender: {e}")
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
            "INSERT INTO users (email, password_hash, role, manager_name) VALUES (%s, %s, %s, %s)",
            (req.email.lower(), hashed_pw, "project_manager", req.email.split("@")[0].capitalize())
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
        # Ensure we fetch the manager_name
        cur.execute("SELECT email, password_hash, role, manager_name FROM users WHERE email = %s", (req.email.lower(),))
        user = cur.fetchone()

        if not user or not pwd_context.verify(req.password, user['password_hash']):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        return {
            "status": "success",
            "email": user['email'],
            "role": user['role'],
            "manager_name": user['manager_name'] # <--- SENDING THE KEY
        }
    finally:
        if conn: conn.close()        

# ----------------- CHAT -----------------
@app.post("/chat/")
async def chat_endpoint(req: ChatRequest):
    print(f"\n[DEBUG] Interactive Chat Session Started for User: {req.user_email}")
    try:
        # Fire conversational service
        reply_data = chat_with_tender(
            query=req.query,
            context=req.context,
            full_text=req.full_text
        )
        
        # 📊 MATCHING THE CHAT REPLIES KEY STRUCTURE PERFECTLY
        reply_text = reply_data.get("reply", str(reply_data))
        in_tokens = reply_data.get("input_tokens", 250)
        out_tokens = reply_data.get("output_tokens", 150)

        # Force baseline simulation tokens if they evaluate to zero
        if not in_tokens or in_tokens == 0: in_tokens = 250
        if not out_tokens or out_tokens == 0: out_tokens = 150
            
        t_no = req.context.get("tender_no", "N/A")
        computed_cost = (in_tokens * 0.00001) + (out_tokens * 0.00003)
        
        # Push tracking row metrics cleanly to Neon PostgreSQL tables
        log_system_ai_usage(req.user_email, "Chat Query Workspace", t_no, in_tokens, out_tokens, computed_cost)

        return {"reply": reply_text}
        
    except Exception as e:
        print(f"❌ PIPELINE ERROR inside chat-endpoint: {e}")
        return {"error": str(e)}
# ----------------- CHAT HISTORY -----------------
@app.get("/chats/sessions")
def get_sessions(email: str, q: Optional[str] = None):
    conn = get_db_connection()
    if not conn:
        return []
        
    try:
        cur = conn.cursor()
        
        # 1. Base Query: Always filter by the user's email
        if q:
            # Filtering by both user email AND search query
            query = """
                SELECT * FROM chat_sessions
                WHERE user_email = %s AND title ILIKE %s
                ORDER BY created_at DESC
            """
            cur.execute(query, (email, f"%{q}%"))
        else:
            # Filtering only by user email
            query = """
                SELECT * FROM chat_sessions 
                WHERE user_email = %s 
                ORDER BY created_at DESC
            """
            cur.execute(query, (email,))
        
        sessions = cur.fetchall()
        return [dict(s) for s in sessions]
    except Exception as e:
        print(f"❌ Sidebar Fetch Error: {e}")
        return []
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
        
        # ✅ FIX: Added user_email to the INSERT statement
        cur.execute(
            """
            INSERT INTO chat_sessions (session_id, title, user_email)
            VALUES (%s, %s, %s)
            ON CONFLICT (session_id) DO NOTHING
            """,
            (data.session_id, data.title or "New Analysis", data.user_email)
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
def get_kpi_stats(year: str = "All", manager: str = None): 
    conn = get_db_connection()
    if not conn:
        return {"total_count": 0, "win_rate": 0, "total_won_value": 0, "active_pipeline": 0}
    
    try:
        cur = conn.cursor()
        
        where_clauses = ["tender_status != 'Quoted Legacy'"]
        params = []

        if year != "All":
            where_clauses.append("financial_year = %s")
            params.append(year)

        if manager and manager not in ["null", "None", "undefined", ""]:
            m_lower = manager.lower().strip()
            if m_lower == "manvendra":
                where_clauses.append("(project_manager ILIKE %s OR project_manager ILIKE '%%Mannevdra%%' OR project_manager ILIKE '%%Manvedra%%' OR project_manager ILIKE '%%Manvennra%%')")
            else:
                where_clauses.append("project_manager ILIKE %s")
            params.append(f"%{manager}%")

        where_stmt = " AND ".join(where_clauses)

        query = f"""
        SELECT
            SUM(CASE WHEN tender_status IN ('Tender Won', 'Tender Lost', 'Tender Quoted', 'Quoted', 'Quoted Active', 'Tender Cancelled') THEN 1 ELSE 0 END) AS total_participated,
            ROUND(CAST(SUM(CASE WHEN tender_status = 'Tender Won' THEN 1 ELSE 0 END) AS NUMERIC) * 100.0 / NULLIF(CAST(SUM(CASE WHEN tender_status IN ('Tender Won', 'Tender Lost') THEN 1 ELSE 0 END) AS NUMERIC), 0), 1) AS win_rate,
            SUM(CASE WHEN tender_status = 'Tender Won' THEN CAST(NULLIF(tender_open_price::text, '') AS NUMERIC) ELSE 0.0 END) AS total_won_value,
            SUM(CASE WHEN tender_status IN ('Tender Quoted', 'Quoted', 'Quoted Active') AND (due_date::text >= CURRENT_DATE::text OR due_date IS NULL) THEN 1 ELSE 0 END) AS active_pipeline
        FROM tenders
        WHERE {where_stmt}
        """
        
        cur.execute(query, params)
        row = cur.fetchone()
        
        if row:
            return {
                "total_count": int(row.get("total_participated") or 0),
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
def get_tenders(manager: str = None):
    conn = get_db_connection()
    today = datetime.now().strftime('%Y-%m-%d')
    try:
        cur = conn.cursor()
        query = "SELECT * FROM tenders WHERE 1=1"
        params = []

        if manager and manager not in ["null", "None", "undefined", ""]:
            m_lower = manager.lower().strip()
            if m_lower == "manvendra":
                query += " AND (project_manager ILIKE %s OR project_manager ILIKE '%%Mannevdra%%' OR project_manager ILIKE '%%Manvedra%%' OR project_manager ILIKE '%%Manvennra%%')"
            else:
                query += " AND project_manager ILIKE %s"
            params.append(f"%{manager}%")

        query += f"""
            ORDER BY 
                CASE WHEN due_date >= '{today}' THEN 0 ELSE 1 END ASC,
                CASE WHEN due_date >= '{today}' THEN due_date END ASC,
                CASE WHEN due_date < '{today}' THEN due_date END DESC
        """
        
        cur.execute(query, params)
        tenders = cur.fetchall()
        return [dict(t) for t in tenders]
    except Exception as e:
        print(f"❌ Get Tenders Error: {e}")
        return []
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

# ----------------- LOG TENDER LOSS (L1-L5) -----------------
@app.put("/log-loss/{tender_no:path}")
def log_full_leaderboard_loss(tender_no: str, payload: FullPostBidPayload):
    import json
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        # Convert the Python list of competitors into a JSON string for Postgres JSONB
        competitors_json_string = json.dumps([c.dict() for c in payload.competitors])
        
        cur.execute(
            """
            UPDATE tenders 
            SET tender_status = 'Tender Lost',
                aarvi_rank = %s,
                reason_for_loss = %s,
                post_bid_remarks = %s,
                competitor_list = %s::jsonb
            WHERE tender_no = %s
            """,
            (
                payload.aarvi_rank,
                payload.reason_for_loss,
                payload.post_bid_remarks,
                competitors_json_string,
                tender_no
            )
        )
        conn.commit()

        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Tender not found")

        return {"status": "success", "message": "Leaderboard logged successfully"}

    except Exception as e:
        print(f"❌ Error logging loss: {e}")
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



# ----------------- GLOBAL ACCOUNT COMPUTE PANELS (NORMAL FLATTENED ROUTES) -----------------

@app.get("/api/users")
def get_live_users(admin_email: Optional[str] = None):
    """Directly extracts existing records using flat routing layout"""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT email, role, manager_name FROM users;")
        user_rows = cur.fetchall()
        return [dict(row) for row in user_rows]
    except Exception as e:
        print(f"❌ User table query crash: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn: conn.close()

@app.post("/api/users")
def create_new_user(user: NewUser, admin_email: Optional[str] = None):
    """Inserts a fresh worker row directly into the users table profile"""
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        hashed_pw = pwd_context.hash(user.password)
        derived_manager = user.email.split("@")[0].capitalize()
        
        cur.execute("""
            INSERT INTO users (email, password_hash, role, manager_name)
            VALUES (%s, %s, %s, %s)
        """, (user.email.lower().strip(), hashed_pw, user.role, derived_manager))
        conn.commit()
        return {"status": "success", "message": f"Account established cleanly for {user.email}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Transaction abort: {str(e)}")
    finally:
        if conn: conn.close()

@app.delete("/api/users/{email}")
def delete_user(email: str, admin_email: Optional[str] = None):
    """Deletes an existing user from your users table structure"""
    if email.lower().strip() == "shreyas@aarviencon.com":
        raise HTTPException(status_code=403, detail="Security Lockout: Core administrative index root immutable.")
        
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("DELETE FROM users WHERE email = %s", (email.lower().strip(),))
        conn.commit()
        return {"status": "success"}
    finally:
        if conn: conn.close()

@app.patch("/api/users/reset-password")
def reset_password(data: PasswordReset, admin_email: Optional[str] = None):
    """Overrides and changes user passwords from the frontend panel control"""
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        hashed_pw = pwd_context.hash(data.newPassword)
        cur.execute("UPDATE users SET password_hash = %s WHERE email = %s", (hashed_pw, data.email.lower().strip()))
        conn.commit()
        return {"status": "success"}
    finally:
        if conn: conn.close()

@app.get("/api/usage-analytics")
def get_user_wise_billing_summary(admin_email: Optional[str] = None):
    """Exposes the raw chronological timeline of AI usage logs for dynamic frontend filtering"""
    conn = get_db_connection()
    if not conn:
        return {"logs": []}
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Select the raw rows cleanly without pre-grouping them
        cur.execute("""
            SELECT id, 
                   user_email, 
                   action_type, 
                   tender_no, 
                   input_tokens, 
                   output_tokens, 
                   ROUND(estimated_cost_inr::numeric, 4) as cost_inr,
                   usage_date
            FROM ai_usage_logs
            ORDER BY usage_date DESC;
        """)
        raw_logs = cur.fetchall()
        
        # Return a single unmanipulated timeline array to the frontend
        return {"logs": [dict(row) for row in raw_logs] if raw_logs else []}
    except Exception as e:
        print(f"❌ Analytics fetch exception: {e}")
        return {"logs": []}
    finally:
        if conn: conn.close()
# ----------------- MAIN -----------------
if __name__ == "__main__":
    import uvicorn
    # Use environment variables for port to support cloud hosting properly
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
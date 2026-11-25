from fastapi import FastAPI, UploadFile, File, HTTPException, Form, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from datetime import datetime, date
from passlib.context import CryptContext
from psycopg2.extras import RealDictCursor
from typing import Optional, List
import csv
import io
import os
import uuid
import json
import shutil
import psycopg2
import asyncio

# ----------------- IMPORTS -----------------
from config import INPUT_COST_PER_TOKEN_INR, OUTPUT_COST_PER_TOKEN_INR
from models import TenderFeedbackPayload
from ai_service import (
    generate_tender_summary,
    chat_with_tender,
    generate_chat_title,
)
from file_parser import append_text_to_disk_stream
from knowledge_service import get_knowledge_store, sync_tender_to_excel

# ----------------- APP & FILE STORAGE SETUP -----------------
os.makedirs("uploads", exist_ok=True)
app = FastAPI()
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# ----------------- CORS -----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------- DATABASE CONNECTION -----------------
def get_db_connection():
    try:
        db_url = os.getenv("DATABASE_URL")

        if not db_url:
            print("❌ Database Connection Error: DATABASE_URL is missing from environment!", flush=True)
            return None

        if db_url.startswith("sqlite"):
            print("⚠️ Warning: Detected an invalid SQLite string in DATABASE_URL environment.", flush=True)
            return None

        conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
        return conn

    except Exception as e:
        print(f"❌ Database Connection Error: {e}", flush=True)
        return None


def clean_empty(val):
    return None if val in ["", "null", "None", None] else val


def _format_competitors_for_storage(raw_competitors) -> Optional[str]:
    """Serializes L1-L5 competitor entries cleanly for PostgreSQL JSONB storage."""
    if not raw_competitors:
        return None
    cleaned = []
    for c in raw_competitors:
        c_dict = c.dict() if hasattr(c, "dict") else (c if isinstance(c, dict) else {})
        company = str(c_dict.get("company") or "").strip()
        if not company or company == "Unknown Competitor":
            continue
        cleaned.append({
            "rank": str(c_dict.get("rank") or "L1").strip(),
            "company": company,
            "amount": float(c_dict.get("amount") or 0.0),
            "percent_diff": float(c_dict.get("percent_diff") or 0.0),
        })
    return json.dumps(cleaned) if cleaned else None


def _build_excel_sync_payload(base_dict: dict) -> dict:
    """Prepares a clean dictionary for append/update sync into Cleaned_Tender_Data.xlsx."""
    payload = dict(base_dict)
    comps = payload.get("competitors") or []
    existing_comments = str(payload.get("comments") or "").strip()

    ranked_lines = []
    for idx, c in enumerate(comps, start=1):
        c_dict = c.dict() if hasattr(c, "dict") else (c if isinstance(c, dict) else {})
        comp_name = str(c_dict.get("company") or "").strip()
        if not comp_name or comp_name == "Unknown Competitor":
            continue
        amt = float(c_dict.get("amount") or 0.0)
        rank = str(c_dict.get("rank") or "").strip()
        diff = float(c_dict.get("percent_diff") or 0.0)
        diff_suffix = f" [{diff}%]" if diff else ""
        ranked_lines.append(f"{idx}) {comp_name}: Rs. {amt:,.2f}/- ({rank}){diff_suffix}")

    if ranked_lines and not existing_comments:
        reason_loss = str(payload.get("reason_for_loss") or "").strip()
        if reason_loss:
            ranked_lines.append(f"Loss Reason: {reason_loss}")
        payload["comments"] = "\n".join(ranked_lines)

    return payload


# ----------------- MULTI-WORKER SAFE PROGRESS & RESULT STORE -----------------
def _sync_task_db(task_id: str, kind: str, payload: dict):
    conn = get_db_connection()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO analysis_tasks (task_id, kind, payload, updated_at)
            VALUES (%s, %s, %s::jsonb, CURRENT_TIMESTAMP)
            ON CONFLICT (task_id) DO UPDATE
            SET kind = EXCLUDED.kind,
                payload = EXCLUDED.payload,
                updated_at = CURRENT_TIMESTAMP;
            """,
            (task_id, kind, json.dumps(payload)),
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def _fetch_task_db(task_id: str):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        cur.execute("SELECT kind, payload FROM analysis_tasks WHERE task_id = %s;", (task_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    except Exception:
        return None
    finally:
        conn.close()


def _delete_task_db(task_id: str):
    conn = get_db_connection()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM analysis_tasks WHERE task_id = %s;", (task_id,))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


class MultiWorkerStore(dict):
    """Mirrors task progress/results to PostgreSQL so --workers 3 share state cleanly."""

    def __init__(self, kind: str):
        super().__init__()
        self.kind = kind

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        _sync_task_db(str(key), self.kind, value)

    def __delitem__(self, key):
        if key in self:
            super().__delitem__(key)
        if self.kind == "result":
            _delete_task_db(str(key))


progress_store = MultiWorkerStore("progress")
result_store = MultiWorkerStore("result")


# ----------------- RAG PAGE INDEXING & RETRIEVAL -----------------
def index_pages_for_rag(tender_no: str, pages: list):
    if not pages or not tender_no or tender_no in ("N/A", "Not Specified"):
        return
    conn = get_db_connection()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM tender_document_pages WHERE tender_no = %s;", (tender_no,))
        for p in pages:
            txt = (p.get("text") or "").strip()
            if not txt:
                continue
            cur.execute(
                """
                INSERT INTO tender_document_pages (tender_no, file_name, page_num, is_ocr, page_text)
                VALUES (%s, %s, %s, %s, %s);
                """,
                (tender_no, p.get("file", ""), int(p.get("page", 1)), bool(p.get("is_ocr", False)), txt),
            )
        conn.commit()
        print(f"📚 [RAG INDEXED] Stored {len(pages)} pages for Tender '{tender_no}'", flush=True)
    except Exception as e:
        conn.rollback()
        print(f"⚠️ RAG indexing skipped: {e}", flush=True)
    finally:
        conn.close()


def retrieve_rag_chunks(tender_no: str, query: str, limit: int = 8) -> str:
    if not tender_no or tender_no in ("N/A", "Not Specified") or not query:
        return ""
    conn = get_db_connection()
    if not conn:
        return ""
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT file_name, page_num, page_text,
                   ts_rank_cd(to_tsvector('english', page_text), plainto_tsquery('english', %s)) AS rank
            FROM tender_document_pages
            WHERE tender_no = %s
              AND to_tsvector('english', page_text) @@ plainto_tsquery('english', %s)
            ORDER BY rank DESC, page_num ASC
            LIMIT %s;
            """,
            (query, tender_no, query, limit),
        )
        rows = cur.fetchall()
        if not rows:
            cur.execute(
                """
                SELECT file_name, page_num, page_text
                FROM tender_document_pages
                WHERE tender_no = %s
                ORDER BY page_num ASC
                LIMIT 6;
                """,
                (tender_no,),
            )
            rows = cur.fetchall()

        blocks = []
        for r in rows:
            blocks.append(f"--- Page {r['page_num']} [{r['file_name']}] ---\n{r['page_text']}")
        return "\n\n".join(blocks)
    except Exception as e:
        print(f"⚠️ RAG retrieval fallback: {e}", flush=True)
        return ""
    finally:
        conn.close()


# ----------------- USAGE LOGGING HELPER -----------------
def log_system_ai_usage(
    user_email: str,
    action_type: str,
    tender_no: str,
    input_tokens: int,
    output_tokens: int,
    estimated_cost: float,
):
    conn = get_db_connection()
    if not conn:
        print("❌ DB LOGGING FAILED: Could not establish database connection.", flush=True)
        return
    try:
        conn.autocommit = True
        cur = conn.cursor(cursor_factory=RealDictCursor)

        print(f"⚙️ [DB DEBUG] Attempting insert into table for User: {user_email}, Tender: {tender_no}", flush=True)

        # 🎯 FIX: Force IST Timestamp for Analytics Logging
        cur.execute(
            """
            INSERT INTO ai_usage_logs (user_email, action_type, tender_no, input_tokens, output_tokens, estimated_cost_inr, usage_date)
            VALUES (%s, %s, %s, %s, %s, %s, (NOW() AT TIME ZONE 'Asia/Kolkata'));
            """,
            (
                user_email.lower().strip(),
                action_type,
                tender_no or "N/A",
                int(input_tokens or 0),
                int(output_tokens or 0),
                float(estimated_cost or 0.0),
            ),
        )
        print("✅ [DB DEBUG] SUCCESS! Insertion statement completed cleanly. Row added to database!", flush=True)

    except Exception as e:
        print(f"❌ [DB CRITICAL FAILURE] Database insertion rejected: {e}", flush=True)
    finally:
        if conn:
            conn.close()


# ----------------- MODELS -----------------
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


class CompetitorEntry(BaseModel):
    rank: str
    company: str
    amount: Optional[float] = 0.00
    percent_diff: Optional[float] = 0.00


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
    aarvi_rank: Optional[str] = None
    reason_for_loss: Optional[str] = None
    post_bid_remarks: Optional[str] = None
    competitors: Optional[List[CompetitorEntry]] = None


class ChatRequest(BaseModel):
    query: str
    context: dict
    full_text: Optional[str] = ""
    user_email: str


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


class FullPostBidPayload(BaseModel):
    aarvi_rank: str
    reason_for_loss: str
    post_bid_remarks: Optional[str] = "No Remarks"
    competitors: List[CompetitorEntry]


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ----------------- STARTUP -----------------
@app.on_event("startup")
def on_startup():
    port = os.getenv("PORT", "8001")
    print("\n==============================================", flush=True)
    print("   AARVI ENCON TENDER SYSTEM ONLINE", flush=True)
    print(f"   PORT: {port}", flush=True)
    print("   DB: POSTGRESQL", flush=True)
    print("   OCR ENGINE: TESSERACT 5 (HYBRID PARALLEL)", flush=True)
    print("   AI ENGINE: GEMINI TRIAGED 2-PASS + UNIFIED KB", flush=True)
    print("==============================================\n", flush=True)

    # Preload Excel + Aarvi JSON Profiles + Reference Rules into memory
    get_knowledge_store()

    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("ALTER TABLE tenders ADD COLUMN IF NOT EXISTS summary_file_url TEXT;")
            cur.execute("ALTER TABLE tenders ADD COLUMN IF NOT EXISTS aarvi_rank TEXT;")
            cur.execute("ALTER TABLE tenders ADD COLUMN IF NOT EXISTS reason_for_loss TEXT;")
            cur.execute("ALTER TABLE tenders ADD COLUMN IF NOT EXISTS post_bid_remarks TEXT;")
            cur.execute("ALTER TABLE tenders ADD COLUMN IF NOT EXISTS competitor_list JSONB;")
            cur.execute("ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS user_email TEXT;")
            cur.execute("ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS analysis_tasks (
                    task_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    payload JSONB NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS tender_document_pages (
                    id SERIAL PRIMARY KEY,
                    tender_no TEXT NOT NULL,
                    file_name TEXT,
                    page_num INT,
                    is_ocr BOOLEAN DEFAULT FALSE,
                    page_text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tender_pages_fts
                ON tender_document_pages USING GIN (to_tsvector('english', page_text));
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tender_pages_tender_no
                ON tender_document_pages (tender_no);
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS tender_feedback (
                    id SERIAL PRIMARY KEY,
                    document_id TEXT,
                    tender_no TEXT,
                    client_name TEXT,
                    rating INT,
                    wrong_fields JSONB,
                    corrections JSONB,
                    user_email TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            conn.commit()
            print("✅ DB Schema Verified (File storage, Chat, Multi-Worker Tasks, RAG Index & Feedback ready).", flush=True)
        except Exception as e:
            conn.rollback()
            print(f"⚠️ DB Schema Warning: {e}", flush=True)
        finally:
            conn.close()


# ----------------- HEALTH -----------------
@app.get("/health")
async def health_check():
    return {
        "status": "online",
        "timestamp": date.today().isoformat(),
    }


# ----------------- OCR PROGRESS & RESULT POLLING -----------------
@app.get("/progress/{task_id}")
async def get_progress(task_id: str):
    # 1. Check if background AI worker completed or threw an error in local memory
    if task_id in result_store:
        task_info = result_store[task_id]
        if task_info["status"] == "completed":
            data = task_info["data"]
            del result_store[task_id]
            return {"status": "completed", "result": data}
        elif task_info["status"] == "error":
            err = task_info.get("error", "Unknown error encountered")
            del result_store[task_id]
            return {"status": "error", "error": err}

    # 2. Return live processing progress from local memory
    prog = progress_store.get(task_id)
    if prog:
        return prog

    # 3. Cross-worker PostgreSQL fallback (for --workers 3)
    db_row = await asyncio.to_thread(_fetch_task_db, task_id)
    if db_row:
        kind = db_row.get("kind")
        payload = db_row.get("payload") or {}
        if kind == "result":
            if payload.get("status") == "completed":
                await asyncio.to_thread(_delete_task_db, task_id)
                return {"status": "completed", "result": payload.get("data")}
            elif payload.get("status") == "error":
                await asyncio.to_thread(_delete_task_db, task_id)
                return {"status": "error", "error": payload.get("error", "Unknown error encountered")}
        elif kind == "progress":
            return payload

    return {
        "current": 0,
        "total": 1,
        "status": "processing",
        "stage": "Initializing analysis...",
    }


# ----------------- BACKGROUND AI WORKER -----------------
async def run_analysis_background(files_data: list, task_id: str, user_email: str):
    """Runs in background, streaming text to disk, triaging pages, and indexing for RAG."""
    stream_file_path = f"stream_{task_id}.txt"
    sidecar_path = f"{stream_file_path}.pages.json"
    try:
        for p in (stream_file_path, sidecar_path):
            if os.path.exists(p):
                os.remove(p)

        total_files = len(files_data)
        for idx, (file_name, file_bytes) in enumerate(files_data):
            file_num = idx + 1
            await asyncio.to_thread(
                append_text_to_disk_stream,
                file_bytes,
                file_name,
                stream_file_path,
                task_id,
                file_num,
                total_files,
            )

        if not os.path.exists(stream_file_path) or os.path.getsize(stream_file_path) == 0:
            result_store[task_id] = {"status": "error", "error": "Could not extract text from uploaded files."}
            return

        # Notify UI of transition to Gemini AI reasoning
        progress_store[task_id] = {
            "current": total_files,
            "total": total_files,
            "current_file_index": total_files,
            "total_files": total_files,
            "current_filename": "All Files Read",
            "stage": "Triaging Key Pages & Running Gemini AI Extraction...",
            "file_progress_pct": 100,
            "overall_progress_pct": 90,
            "status": "processing",
        }

        # Non-blocking AI execution
        result = await asyncio.to_thread(generate_tender_summary, stream_file_path)

        in_tokens = result.get("input_tokens", 4500)
        out_tokens = result.get("output_tokens", 1200)
        t_no = result.get("tender_no", "N/A")
        ui_payload = result.get("ui_data", result)
        if not in_tokens or in_tokens == 0:
            in_tokens = 4500
        if not out_tokens or out_tokens == 0:
            out_tokens = 1200

        # Index parsed pages into PostgreSQL for fast follow-up RAG chat
        if os.path.exists(sidecar_path):
            try:
                with open(sidecar_path, "r", encoding="utf-8") as sf:
                    parsed_pages = json.load(sf)
                await asyncio.to_thread(index_pages_for_rag, t_no, parsed_pages)
            except Exception as idx_err:
                print(f"⚠️ Sidecar RAG indexing warning: {idx_err}", flush=True)

        computed_cost = (in_tokens * INPUT_COST_PER_TOKEN_INR) + (out_tokens * OUTPUT_COST_PER_TOKEN_INR)
        await asyncio.to_thread(
            log_system_ai_usage, user_email, "Tender Scan Analysis", t_no, in_tokens, out_tokens, computed_cost
        )
        result_store[task_id] = {"status": "completed", "data": {"aarvi_intelligence": ui_payload}}

    except Exception as e:
        print(f"❌ PIPELINE ERROR inside background worker: {e}", flush=True)
        result_store[task_id] = {"status": "error", "error": str(e)}
    finally:
        for p in (stream_file_path, sidecar_path):
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

        if task_id in progress_store:
            del progress_store[task_id]


# ----------------- AI ANALYSIS -----------------
@app.post("/analyze-tender")
async def analyze_tender(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    task_id: str = Form(...),
    user_email: str = Form(...),
):
    print(f"\n[DEBUG] Queueing Task: {task_id} by User: {user_email}", flush=True)
    try:
        files_data = []
        for file in files:
            file_bytes = await file.read()
            files_data.append((file.filename, file_bytes))

        result_store[task_id] = {"status": "processing"}
        background_tasks.add_task(run_analysis_background, files_data, task_id, user_email)

        return {"status": "queued", "task_id": task_id}

    except Exception as e:
        print(f"❌ PIPELINE ERROR inside analyze-tender: {e}", flush=True)
        return {"error": str(e)}


# ----------------- FEEDBACK -----------------
@app.post("/api/feedback")
def submit_tender_feedback(payload: TenderFeedbackPayload):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO tender_feedback (document_id, tender_no, client_name, rating, wrong_fields, corrections, user_email)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s);
            """,
            (
                payload.document_id,
                payload.tender_no,
                payload.client_name,
                payload.rating,
                json.dumps(payload.wrong_fields),
                json.dumps(payload.corrections),
                payload.user_email,
            ),
        )
        conn.commit()
        return {"status": "recorded"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# ----------------- AUTH ROUTES -----------------
@app.post("/signup")
def signup(req: AuthRequest):
    if not req.email.lower().endswith("@aarviencon.com"):
        raise HTTPException(
            status_code=400,
            detail="Registration denied. Only @aarviencon.com emails allowed.",
        )

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        hashed_pw = pwd_context.hash(req.password)

        cur.execute(
            "INSERT INTO users (email, password_hash, role, manager_name) VALUES (%s, %s, %s, %s)",
            (req.email.lower(), hashed_pw, "project_manager", req.email.split("@")[0].capitalize()),
        )
        conn.commit()
        return {"message": "Account created successfully as Project Manager."}
    except Exception:
        raise HTTPException(status_code=400, detail="Email already registered.")
    finally:
        if conn:
            conn.close()


@app.post("/login")
def login(req: AuthRequest):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT email, password_hash, role, manager_name FROM users WHERE email = %s", (req.email.lower(),))
        user = cur.fetchone()

        if not user or not pwd_context.verify(req.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        return {
            "status": "success",
            "email": user["email"],
            "role": user["role"],
            "manager_name": user["manager_name"],
        }
    finally:
        if conn:
            conn.close()


# ----------------- CHAT -----------------
@app.post("/chat/")
async def chat_endpoint(req: ChatRequest):
    print(f"\n[DEBUG] Interactive Chat Session Started for User: {req.user_email}", flush=True)
    try:
        t_no = (req.context or {}).get("tender_no", "N/A")
        rag_context = await asyncio.to_thread(retrieve_rag_chunks, t_no, req.query, 8)
        doc_slice = rag_context if rag_context else (req.full_text or "")

        reply_data = await asyncio.to_thread(
            chat_with_tender,
            req.query,
            req.context,
            doc_slice,
        )

        reply_text = reply_data.get("reply", str(reply_data))
        in_tokens = reply_data.get("input_tokens", 250)
        out_tokens = reply_data.get("output_tokens", 150)
        if not in_tokens or in_tokens == 0:
            in_tokens = 250
        if not out_tokens or out_tokens == 0:
            out_tokens = 150

        computed_cost = (in_tokens * INPUT_COST_PER_TOKEN_INR) + (out_tokens * OUTPUT_COST_PER_TOKEN_INR)

        await asyncio.to_thread(
            log_system_ai_usage, req.user_email, "Chat Query Workspace", t_no, in_tokens, out_tokens, computed_cost
        )
        return {"reply": reply_text}

    except Exception as e:
        print(f"❌ PIPELINE ERROR inside chat-endpoint: {e}", flush=True)
        return {"error": str(e)}


# ----------------- CHAT HISTORY -----------------
@app.get("/chats/sessions")
def get_sessions(email: str, q: Optional[str] = None):
    conn = get_db_connection()
    if not conn:
        return []

    try:
        cur = conn.cursor()
        clean_email = email.lower().strip() if email else ""

        if q:
            query = """
                SELECT * FROM chat_sessions
                WHERE (LOWER(TRIM(user_email)) = %s OR user_email IS NULL) AND title ILIKE %s
                ORDER BY COALESCE(updated_at, created_at) DESC
            """
            cur.execute(query, (clean_email, f"%{q}%"))
        else:
            query = """
                SELECT * FROM chat_sessions
                WHERE (LOWER(TRIM(user_email)) = %s OR user_email IS NULL)
                ORDER BY COALESCE(updated_at, created_at) DESC
            """
            cur.execute(query, (clean_email,))

        sessions = cur.fetchall()
        return [dict(s) for s in sessions]

    except Exception as e:
        print(f"❌ Sidebar Fetch Error: {e}", flush=True)
        return []
    finally:
        if conn:
            conn.close()


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
            ORDER BY id ASC
            """,
            (session_id,),
        )
        messages = cur.fetchall()
        return [dict(m) for m in messages]
    finally:
        if conn:
            conn.close()


@app.post("/chats/message")
def save_chat_message(data: SaveMessage):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        clean_email = data.user_email.lower().strip() if data.user_email else None

        # 🎯 FIX: Force IST Timestamp when creating or updating chat sessions
        cur.execute(
            """
            INSERT INTO chat_sessions (session_id, title, user_email, updated_at)
            VALUES (%s, COALESCE(%s, 'New Analysis'), %s, TO_CHAR(NOW() AT TIME ZONE 'Asia/Kolkata', 'YYYY-MM-DD HH24:MI:SS'))
            ON CONFLICT (session_id) DO UPDATE
            SET user_email = COALESCE(EXCLUDED.user_email, chat_sessions.user_email),
                title = CASE
                    WHEN EXCLUDED.title IS NOT NULL AND EXCLUDED.title != '' AND EXCLUDED.title != 'New Analysis'
                    THEN EXCLUDED.title
                    ELSE COALESCE(chat_sessions.title, EXCLUDED.title, 'New Analysis')
                END,
                updated_at = TO_CHAR(NOW() AT TIME ZONE 'Asia/Kolkata', 'YYYY-MM-DD HH24:MI:SS');
            """,
            (data.session_id, data.title, clean_email),
        )

        cur.execute(
            """
            INSERT INTO chat_messages (session_id, role, content, timestamp)
            VALUES (%s, %s, %s, TO_CHAR(NOW() AT TIME ZONE 'Asia/Kolkata', 'YYYY-MM-DD HH24:MI:SS'))
            """,
            (data.session_id, data.role, data.content),
        )
        conn.commit()
        return {"status": "saved"}
    except Exception as e:
        print(f"❌ Error saving message: {e}", flush=True)
        return {"error": str(e)}
    finally:
        if conn:
            conn.close()


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
        # 🎯 FIX: Force IST Timestamp on session rename
        cur.execute(
            """
            UPDATE chat_sessions
            SET title = %s, updated_at = TO_CHAR(NOW() AT TIME ZONE 'Asia/Kolkata', 'YYYY-MM-DD HH24:MI:SS')
            WHERE session_id = %s
            """,
            (data.title, session_id),
        )
        conn.commit()
        return {"status": "renamed"}
    finally:
        if conn:
            conn.close()


@app.post("/chats/clone/{session_id}")
def clone_chat(session_id: str):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        new_session_id = str(uuid.uuid4())

        # 🎯 FIX: Force IST Timestamp when cloning chat sessions
        cur.execute(
            """
            INSERT INTO chat_sessions (session_id, title, user_email, updated_at)
            SELECT %s, title || ' (Imported)', user_email, TO_CHAR(NOW() AT TIME ZONE 'Asia/Kolkata', 'YYYY-MM-DD HH24:MI:SS')
            FROM chat_sessions
            WHERE session_id = %s
            """,
            (new_session_id, session_id),
        )

        cur.execute(
            """
            INSERT INTO chat_messages (session_id, role, content, timestamp)
            SELECT %s, role, content, TO_CHAR(NOW() AT TIME ZONE 'Asia/Kolkata', 'YYYY-MM-DD HH24:MI:SS')
            FROM chat_messages
            WHERE session_id = %s
            """,
            (new_session_id, session_id),
        )
        conn.commit()
        return {"new_session_id": new_session_id}
    except Exception as e:
        return {"error": str(e)}
    finally:
        if conn:
            conn.close()


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
        if conn:
            conn.close()


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
                where_clauses.append(
                    "(project_manager ILIKE %s OR project_manager ILIKE '%%Mannevdra%%' OR project_manager ILIKE '%%Manvedra%%' OR project_manager ILIKE '%%Manvennra%%')"
                )
            else:
                where_clauses.append("project_manager ILIKE %s")
            params.append(f"%{manager}%")

        where_stmt = " AND ".join(where_clauses)

        query = f"""
        SELECT
            SUM(CASE WHEN tender_status IN ('Tender Won', 'Tender Lost', 'Tender Quoted', 'Quoted', 'Quoted Active', 'Tender Cancelled', 'PENDING', 'Pending', 'Active') THEN 1 ELSE 0 END) AS total_participated,
            ROUND(CAST(SUM(CASE WHEN tender_status = 'Tender Won' THEN 1 ELSE 0 END) AS NUMERIC) * 100.0 / NULLIF(CAST(SUM(CASE WHEN tender_status IN ('Tender Won', 'Tender Lost') THEN 1 ELSE 0 END) AS NUMERIC), 0), 1) AS win_rate,
            SUM(CASE WHEN tender_status = 'Tender Won' THEN CAST(NULLIF(tender_open_price::text, '') AS NUMERIC) ELSE 0.0 END) AS total_won_value,
            SUM(CASE WHEN tender_status IN ('Tender Quoted', 'Quoted', 'Quoted Active', 'PENDING', 'Pending', 'Active') AND (due_date::text >= CURRENT_DATE::text OR due_date IS NULL) THEN 1 ELSE 0 END) AS active_pipeline
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
                "active_pipeline": int(row.get("active_pipeline") or 0),
            }

        return {"total_count": 0, "win_rate": 0, "total_won_value": 0, "active_pipeline": 0}

    except Exception as e:
        print(f"❌ KPI Error: {e}", flush=True)
        return {"error": str(e)}
    finally:
        if conn:
            conn.close()


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
        if conn:
            conn.close()


# ----------------- GET TENDERS -----------------
@app.get("/tenders")
def get_tenders(manager: str = None):
    conn = get_db_connection()
    today = datetime.now().strftime("%Y-%m-%d")
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

        query += """
            ORDER BY
                CASE WHEN due_date >= %s THEN 0 ELSE 1 END ASC,
                CASE WHEN due_date >= %s THEN due_date END ASC,
                CASE WHEN due_date < %s THEN due_date END DESC
        """
        params.extend([today, today, today])

        cur.execute(query, params)
        tenders = cur.fetchall()

        formatted_rows = []
        for t in tenders:
            row_dict = dict(t)
            comp_raw = row_dict.get("competitor_list")
            if isinstance(comp_raw, str) and comp_raw.strip():
                try:
                    row_dict["competitors"] = json.loads(comp_raw)
                except Exception:
                    row_dict["competitors"] = []
            elif isinstance(comp_raw, list):
                row_dict["competitors"] = comp_raw
            else:
                row_dict["competitors"] = []
            formatted_rows.append(row_dict)

        return formatted_rows
    except Exception as e:
        print(f"❌ Get Tenders Error: {e}", flush=True)
        return []
    finally:
        if conn:
            conn.close()


# ----------------- ADD TENDER -----------------
@app.post("/tenders")
def add_tender(t: Tender, background_tasks: BackgroundTasks):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        comp_json = _format_competitors_for_storage(t.competitors)
        query = """
            INSERT INTO tenders (
                tender_status, received_date, due_date, name_of_client, location,
                tender_no, tender_open_price, quoted_value, description, project_manager,
                emd, emd_status, tender_fee_status, price_status, source,
                comments, docs_prepared_by, financial_year, pre_bidding_date, pre_bid_time,
                mode_of_conduct, platform_or_address, aarvi_rank, reason_for_loss,
                post_bid_remarks, competitor_list
            )
            VALUES (
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s::jsonb
            )
        """
        cur.execute(
            query,
            (
                t.tender_status,
                clean_empty(t.received_date),
                clean_empty(t.due_date),
                t.name_of_client,
                clean_empty(t.location),
                t.tender_no,
                clean_empty(t.tender_open_price),
                clean_empty(t.quoted_value),
                clean_empty(t.description),
                clean_empty(t.project_manager),
                clean_empty(t.emd),
                clean_empty(t.emd_status),
                clean_empty(t.tender_fee_status),
                clean_empty(t.price_status),
                clean_empty(t.source),
                clean_empty(t.comments),
                clean_empty(t.docs_prepared_by),
                clean_empty(t.financial_year),
                clean_empty(t.pre_bidding_date),
                clean_empty(t.pre_bid_time),
                clean_empty(t.mode_of_conduct),
                clean_empty(t.platform_or_address),
                clean_empty(t.aarvi_rank),
                clean_empty(t.reason_for_loss),
                clean_empty(t.post_bid_remarks),
                comp_json,
            ),
        )
        conn.commit()
        background_tasks.add_task(sync_tender_to_excel, _build_excel_sync_payload(t.dict()))
        return {"message": "Success"}
    except Exception as e:
        print(f"DATABASE ERROR: {e}", flush=True)
        return {"error": str(e)}
    finally:
        if conn:
            conn.close()


# ----------------- ADD TENDER (WITH FILE UPLOAD) -----------------
@app.post("/tenders-with-file")
async def add_tender_with_file(
    request: Request,
    background_tasks: BackgroundTasks,
    tender_data: str = Form(...),
    summary_file: UploadFile = File(...),
):
    try:
        t = json.loads(tender_data)
        comp_json = _format_competitors_for_storage(t.get("competitors"))

        safe_filename = summary_file.filename.replace(" ", "_")
        unique_filename = f"{uuid.uuid4()}_{safe_filename}"
        file_path = os.path.join("uploads", unique_filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(summary_file.file, buffer)

        scheme = request.headers.get("x-forwarded-proto", "http")
        host = request.headers.get("x-forwarded-host", request.headers.get("host"))
        file_url = f"{scheme}://{host}/uploads/{unique_filename}"

        conn = get_db_connection()
        if not conn:
            return {"error": "Database disconnected"}

        cur = conn.cursor()
        query = """
            INSERT INTO tenders (
                tender_status, received_date, due_date, name_of_client, location,
                tender_no, tender_open_price, quoted_value, description, project_manager,
                emd, emd_status, tender_fee_status, price_status, source,
                comments, docs_prepared_by, financial_year, pre_bidding_date, pre_bid_time,
                mode_of_conduct, platform_or_address, summary_file_url,
                aarvi_rank, reason_for_loss, post_bid_remarks, competitor_list
            )
            VALUES (
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s::jsonb
            )
        """
        cur.execute(
            query,
            (
                t.get("tender_status"),
                clean_empty(t.get("received_date")),
                clean_empty(t.get("due_date")),
                t.get("name_of_client"),
                clean_empty(t.get("location")),
                t.get("tender_no"),
                clean_empty(t.get("tender_open_price")),
                clean_empty(t.get("quoted_value")),
                clean_empty(t.get("description")),
                clean_empty(t.get("project_manager")),
                clean_empty(t.get("emd")),
                clean_empty(t.get("emd_status")),
                clean_empty(t.get("tender_fee_status")),
                clean_empty(t.get("price_status")),
                clean_empty(t.get("source")),
                clean_empty(t.get("comments")),
                clean_empty(t.get("docs_prepared_by")),
                clean_empty(t.get("financial_year")),
                clean_empty(t.get("pre_bidding_date")),
                clean_empty(t.get("pre_bid_time")),
                clean_empty(t.get("mode_of_conduct")),
                clean_empty(t.get("platform_or_address")),
                file_url,
                clean_empty(t.get("aarvi_rank")),
                clean_empty(t.get("reason_for_loss")),
                clean_empty(t.get("post_bid_remarks")),
                comp_json,
            ),
        )
        conn.commit()
        background_tasks.add_task(sync_tender_to_excel, _build_excel_sync_payload(t))
        return {"message": "Success with file"}

    except Exception as e:
        print(f"FILE UPLOAD ERROR: {e}", flush=True)
        return {"error": str(e)}
    finally:
        if "conn" in locals() and conn:
            conn.close()


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
            "Tender No",
            "Client",
            "Status",
            "Received Date",
            "Due Date",
            "Pre-Bid Date",
            "Quoted Value",
            "Project Manager",
        ])
        for t in tenders:
            writer.writerow([
                t["tender_no"],
                t["name_of_client"],
                t["tender_status"],
                t["received_date"],
                t["due_date"],
                t["pre_bidding_date"],
                t["quoted_value"],
                t["project_manager"],
            ])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=tenders_export.csv"},
        )
    finally:
        if conn:
            conn.close()


# ----------------- QUICK STATUS UPDATE -----------------
@app.patch("/tenders/{tender_no:path}/status")
def quick_update_status(tender_no: str, update: StatusUpdate, background_tasks: BackgroundTasks):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE tenders
            SET tender_status = %s
            WHERE tender_no = %s
            """,
            (update.tender_status, tender_no),
        )
        conn.commit()
        background_tasks.add_task(sync_tender_to_excel, {"tender_no": tender_no, "tender_status": update.tender_status})
        return {"message": "Status updated successfully"}
    except Exception as e:
        return {"error": str(e)}
    finally:
        if conn:
            conn.close()


# ----------------- LOG TENDER LOSS (L1-L5) -----------------
@app.put("/log-loss/{tender_no:path}")
def log_full_leaderboard_loss(tender_no: str, payload: FullPostBidPayload, background_tasks: BackgroundTasks):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
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
                tender_no,
            ),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Tender not found")

        ranked_lines = []
        for idx, c in enumerate(payload.competitors, start=1):
            diff_suffix = f" [{c.percent_diff}%]" if c.percent_diff else ""
            ranked_lines.append(f"{idx}) {c.company}: Rs. {float(c.amount or 0.0):,.2f}/- ({c.rank}){diff_suffix}")
        if payload.reason_for_loss:
            ranked_lines.append(f"Loss Reason: {payload.reason_for_loss}")

        background_tasks.add_task(
            sync_tender_to_excel,
            {
                "tender_no": tender_no,
                "tender_status": "Tender Lost",
                "comments": "\n".join(ranked_lines),
            },
        )
        return {"status": "success", "message": "Leaderboard logged successfully"}
    except Exception as e:
        print(f"❌ Error logging loss: {e}", flush=True)
        return {"error": str(e)}
    finally:
        if conn:
            conn.close()


# ----------------- DELETE TENDER (NEVER DELETES FROM EXCEL ARCHIVE) -----------------
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
            (tender_no,),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Tender not found")
        return {"message": "Tender deleted successfully"}
    except Exception as e:
        return {"error": str(e)}
    finally:
        if conn:
            conn.close()


# ----------------- UPDATE TENDER -----------------
@app.put("/tenders/{tender_no:path}")
def update_tender(tender_no: str, t: Tender, background_tasks: BackgroundTasks):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        comp_json = _format_competitors_for_storage(t.competitors)
        cur.execute(
            """
            UPDATE tenders SET
                name_of_client=%s, tender_status=%s, received_date=%s, due_date=%s,
                pre_bidding_date=%s, pre_bid_time=%s, mode_of_conduct=%s, platform_or_address=%s,
                location=%s, tender_open_price=%s, quoted_value=%s, description=%s,
                project_manager=%s, emd=%s, emd_status=%s, tender_fee_status=%s,
                price_status=%s, source=%s, comments=%s, docs_prepared_by=%s,
                financial_year=%s,
                aarvi_rank=COALESCE(%s, aarvi_rank),
                reason_for_loss=COALESCE(%s, reason_for_loss),
                post_bid_remarks=COALESCE(%s, post_bid_remarks),
                competitor_list=COALESCE(%s::jsonb, competitor_list)
            WHERE tender_no=%s
            """,
            (
                t.name_of_client,
                t.tender_status,
                clean_empty(t.received_date),
                clean_empty(t.due_date),
                clean_empty(t.pre_bidding_date),
                clean_empty(t.pre_bid_time),
                clean_empty(t.mode_of_conduct),
                clean_empty(t.platform_or_address),
                clean_empty(t.location),
                clean_empty(t.tender_open_price),
                clean_empty(t.quoted_value),
                clean_empty(t.description),
                clean_empty(t.project_manager),
                clean_empty(t.emd),
                clean_empty(t.emd_status),
                clean_empty(t.tender_fee_status),
                clean_empty(t.price_status),
                clean_empty(t.source),
                clean_empty(t.comments),
                clean_empty(t.docs_prepared_by),
                clean_empty(t.financial_year),
                clean_empty(t.aarvi_rank),
                clean_empty(t.reason_for_loss),
                clean_empty(t.post_bid_remarks),
                comp_json,
                tender_no,
            ),
        )
        conn.commit()
        payload_dict = t.dict()
        payload_dict["tender_no"] = tender_no
        background_tasks.add_task(sync_tender_to_excel, _build_excel_sync_payload(payload_dict))
        return {"message": "Updated successfully"}
    except Exception as e:
        return {"error": str(e)}
    finally:
        if conn:
            conn.close()


# ----------------- UPDATE TENDER (WITH FILE UPLOAD) -----------------
@app.put("/tenders-with-file/{tender_no:path}")
async def update_tender_with_file(
    tender_no: str,
    request: Request,
    background_tasks: BackgroundTasks,
    tender_data: str = Form(...),
    summary_file: UploadFile = File(...),
):
    try:
        t = json.loads(tender_data)
        comp_json = _format_competitors_for_storage(t.get("competitors"))

        safe_filename = summary_file.filename.replace(" ", "_")
        unique_filename = f"{uuid.uuid4()}_{safe_filename}"
        file_path = os.path.join("uploads", unique_filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(summary_file.file, buffer)

        scheme = request.headers.get("x-forwarded-proto", "http")
        host = request.headers.get("x-forwarded-host", request.headers.get("host"))
        file_url = f"{scheme}://{host}/uploads/{unique_filename}"

        conn = get_db_connection()
        if not conn:
            return {"error": "Database disconnected"}

        cur = conn.cursor()
        cur.execute(
            """
            UPDATE tenders SET
                name_of_client=%s, tender_status=%s, received_date=%s, due_date=%s,
                pre_bidding_date=%s, pre_bid_time=%s, mode_of_conduct=%s, platform_or_address=%s,
                location=%s, tender_open_price=%s, quoted_value=%s, description=%s,
                project_manager=%s, emd=%s, emd_status=%s, tender_fee_status=%s,
                price_status=%s, source=%s, comments=%s, docs_prepared_by=%s,
                financial_year=%s, summary_file_url=%s,
                aarvi_rank=COALESCE(%s, aarvi_rank),
                reason_for_loss=COALESCE(%s, reason_for_loss),
                post_bid_remarks=COALESCE(%s, post_bid_remarks),
                competitor_list=COALESCE(%s::jsonb, competitor_list)
            WHERE tender_no=%s
            """,
            (
                clean_empty(t.get("name_of_client")),
                t.get("tender_status"),
                clean_empty(t.get("received_date")),
                clean_empty(t.get("due_date")),
                clean_empty(t.get("pre_bidding_date")),
                clean_empty(t.get("pre_bid_time")),
                clean_empty(t.get("mode_of_conduct")),
                clean_empty(t.get("platform_or_address")),
                clean_empty(t.get("location")),
                clean_empty(t.get("tender_open_price")),
                clean_empty(t.get("quoted_value")),
                clean_empty(t.get("description")),
                clean_empty(t.get("project_manager")),
                clean_empty(t.get("emd")),
                clean_empty(t.get("emd_status")),
                clean_empty(t.get("tender_fee_status")),
                clean_empty(t.get("price_status")),
                clean_empty(t.get("source")),
                clean_empty(t.get("comments")),
                clean_empty(t.get("docs_prepared_by")),
                clean_empty(t.get("financial_year")),
                file_url,
                clean_empty(t.get("aarvi_rank")),
                clean_empty(t.get("reason_for_loss")),
                clean_empty(t.get("post_bid_remarks")),
                comp_json,
                tender_no,
            ),
        )
        conn.commit()
        t["tender_no"] = tender_no
        background_tasks.add_task(sync_tender_to_excel, _build_excel_sync_payload(t))
        return {"message": "Updated successfully with file"}

    except Exception as e:
        print(f"FILE UPLOAD UPDATE ERROR: {e}", flush=True)
        return {"error": str(e)}
    finally:
        if "conn" in locals() and conn:
            conn.close()


# ----------------- GLOBAL ACCOUNT COMPUTE PANELS -----------------
@app.get("/api/users")
def get_live_users(admin_email: Optional[str] = None):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT email, role, manager_name FROM users;")
        user_rows = cur.fetchall()
        return [dict(row) for row in user_rows]
    except Exception as e:
        print(f"❌ User table query crash: {e}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.post("/api/users")
def create_new_user(user: NewUser, admin_email: Optional[str] = None):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        hashed_pw = pwd_context.hash(user.password)
        derived_manager = user.email.split("@")[0].capitalize()

        cur.execute(
            """
            INSERT INTO users (email, password_hash, role, manager_name)
            VALUES (%s, %s, %s, %s)
            """,
            (user.email.lower().strip(), hashed_pw, user.role, derived_manager),
        )
        conn.commit()
        return {"status": "success", "message": f"Account established cleanly for {user.email}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Transaction abort: {str(e)}")
    finally:
        if conn:
            conn.close()


@app.delete("/api/users/{email}")
def delete_user(email: str, admin_email: Optional[str] = None):
    if email.lower().strip() == "shreyas@aarviencon.com":
        raise HTTPException(status_code=403, detail="Security Lockout: Core administrative index root immutable.")

    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("DELETE FROM users WHERE email = %s", (email.lower().strip(),))
        conn.commit()
        return {"status": "success"}
    finally:
        if conn:
            conn.close()


@app.patch("/api/users/reset-password")
def reset_password(data: PasswordReset, admin_email: Optional[str] = None):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        hashed_pw = pwd_context.hash(data.newPassword)
        cur.execute("UPDATE users SET password_hash = %s WHERE email = %s", (hashed_pw, data.email.lower().strip()))
        conn.commit()
        return {"status": "success"}
    finally:
        if conn:
            conn.close()


@app.get("/api/usage-analytics")
def get_user_wise_billing_summary(admin_email: Optional[str] = None):
    conn = get_db_connection()
    if not conn:
        return {"logs": []}
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
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
            """
        )
        raw_logs = cur.fetchall()
        return {"logs": [dict(row) for row in raw_logs] if raw_logs else []}
    except Exception as e:
        print(f"❌ Analytics fetch exception: {e}", flush=True)
        return {"logs": []}
    finally:
        if conn:
            conn.close()


# ----------------- MAIN -----------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
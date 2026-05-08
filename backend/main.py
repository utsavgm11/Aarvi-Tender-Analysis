from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import csv
import io
import sqlite3
import os
import uuid

from typing import Optional, List
from datetime import date

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

# ----------------- CORS -----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- DATABASE -----------------
def get_db_connection():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "tender_data.db")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    return conn

# ----------------- MODELS -----------------
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

# ----------------- STARTUP -----------------
@app.on_event("startup")
def print_routes():
    print("\n==============================================")
    print("   AARVI ENCON TENDER SYSTEM ONLINE")
    print("   PORT: 8001")
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

        return {
            "aarvi_intelligence": result
        }

    except Exception as e:
        print(f"PIPELINE ERROR: {e}")

        return {
            "error": str(e)
        }

    finally:
        if task_id in progress_store:
            del progress_store[task_id]

# ----------------- CHAT -----------------
@app.post("/chat/")
async def chat_endpoint(req: ChatRequest):
    try:
        reply = chat_with_tender(
            query=req.query,
            context=req.context,
            full_text=req.full_text
        )

        return {
            "reply": reply
        }

    except Exception as e:
        return {
            "error": str(e)
        }

# ----------------- CHAT HISTORY -----------------
@app.get("/chats/sessions")
def get_sessions(q: Optional[str] = None):
    conn = get_db_connection()

    try:
        if q:
            query = """
                SELECT * FROM chat_sessions
                WHERE title LIKE ?
                ORDER BY created_at DESC
            """

            sessions = conn.execute(
                query,
                (f"%{q}%",)
            ).fetchall()

        else:
            sessions = conn.execute(
                "SELECT * FROM chat_sessions ORDER BY created_at DESC"
            ).fetchall()

        return [dict(s) for s in sessions]

    finally:
        conn.close()

@app.get("/chats/history/{session_id}")
def get_history(session_id: str):
    conn = get_db_connection()

    try:
        messages = conn.execute(
            """
            SELECT role, content
            FROM chat_messages
            WHERE session_id = ?
            ORDER BY timestamp ASC
            """,
            (session_id,)
        ).fetchall()

        return [dict(m) for m in messages]

    finally:
        conn.close()

@app.post("/chats/message")
def save_chat_message(data: SaveMessage):
    conn = get_db_connection()

    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO chat_sessions
            (session_id, title)
            VALUES (?, ?)
            """,
            (
                data.session_id,
                data.title or "New Analysis"
            )
        )

        conn.execute(
            """
            INSERT INTO chat_messages
            (session_id, role, content)
            VALUES (?, ?, ?)
            """,
            (
                data.session_id,
                data.role,
                data.content
            )
        )

        conn.commit()

        return {
            "status": "saved"
        }

    finally:
        conn.close()

@app.post("/chats/generate-title")
def generate_title(req: TitleRequest):
    try:
        title = generate_chat_title(req.first_message)

        return {
            "title": title
        }

    except Exception:
        return {
            "title": "New Analysis"
        }

@app.put("/chats/sessions/{session_id}")
def rename_session(session_id: str, data: SessionRename):
    conn = get_db_connection()

    try:
        conn.execute(
            """
            UPDATE chat_sessions
            SET title = ?
            WHERE session_id = ?
            """,
            (
                data.title,
                session_id
            )
        )

        conn.commit()

        return {
            "status": "renamed"
        }

    finally:
        conn.close()

@app.post("/chats/clone/{session_id}")
def clone_chat(session_id: str):
    conn = get_db_connection()

    try:
        new_session_id = str(uuid.uuid4())

        original = conn.execute(
            """
            SELECT title
            FROM chat_sessions
            WHERE session_id = ?
            """,
            (session_id,)
        ).fetchone()

        title = (
            original["title"] + " (Imported)"
            if original
            else "Imported Chat"
        )

        conn.execute(
            """
            INSERT INTO chat_sessions
            (session_id, title)
            VALUES (?, ?)
            """,
            (
                new_session_id,
                title
            )
        )

        conn.execute(
            """
            INSERT INTO chat_messages
            (session_id, role, content)

            SELECT ?, role, content
            FROM chat_messages
            WHERE session_id = ?
            """,
            (
                new_session_id,
                session_id
            )
        )

        conn.commit()

        return {
            "new_session_id": new_session_id
        }

    except Exception as e:
        return {
            "error": str(e)
        }

    finally:
        conn.close()

@app.delete("/chats/sessions/{session_id}")
def delete_session(session_id: str):
    conn = get_db_connection()

    try:
        conn.execute(
            "DELETE FROM chat_messages WHERE session_id = ?",
            (session_id,)
        )

        conn.execute(
            "DELETE FROM chat_sessions WHERE session_id = ?",
            (session_id,)
        )

        conn.commit()

        return {
            "status": "deleted"
        }

    except Exception as e:
        return {
            "error": str(e)
        }

    finally:
        conn.close()

# ----------------- KPI -----------------
@app.get("/kpi-stats")
def get_kpi_stats(year: str = "All"):
    conn = get_db_connection()

    try:
        cur = conn.cursor()

        query = """
        SELECT
            COUNT(*) AS total_count,

            ROUND(
                CAST(
                    SUM(
                        CASE
                            WHEN tender_status = 'Tender Won'
                            THEN 1
                            ELSE 0
                        END
                    ) AS FLOAT
                ) * 100 /

                NULLIF(
                    SUM(
                        CASE
                            WHEN tender_status IN (
                                'Tender Won',
                                'Tender Lost'
                            )
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ),
            1) AS win_rate,

            SUM(
                CASE
                    WHEN tender_status = 'Tender Won'
                    THEN tender_open_price
                    ELSE 0
                END
            ) AS total_won_value,

            SUM(
                CASE
                    WHEN tender_status IN (
                        'Tender Quoted',
                        'Quoted',
                        'Quoted Active'
                    )

                    AND (
                        due_date >= date('now')
                        OR due_date IS NULL
                        OR due_date = ''
                    )

                    THEN 1
                    ELSE 0
                END
            ) AS active_pipeline

        FROM tenders

        WHERE
            (? = 'All' OR financial_year = ?)

        AND tender_status != 'Quoted Legacy'
        """

        cur.execute(query, (year, year))

        row = cur.fetchone()

        result = dict(row) if row else {}

        if result.get("active_pipeline") is None:
            result["active_pipeline"] = 0

        return result

    finally:
        conn.close()

# ----------------- UPCOMING PREBID -----------------
@app.get("/tenders/upcoming-prebid")
def get_upcoming_prebids():
    today = date.today().isoformat()

    conn = get_db_connection()

    try:
        query = """
            SELECT *
            FROM tenders

            WHERE pre_bidding_date >= ?
            AND pre_bidding_date IS NOT NULL
            AND pre_bidding_date != ''

            ORDER BY pre_bidding_date ASC
        """

        tenders = conn.execute(
            query,
            (today,)
        ).fetchall()

        return [dict(t) for t in tenders]

    finally:
        conn.close()

# ----------------- GET TENDERS -----------------
@app.get("/tenders")
def get_tenders():
    conn = get_db_connection()

    try:
        tenders = conn.execute(
            "SELECT * FROM tenders"
        ).fetchall()

        return [dict(t) for t in tenders]

    finally:
        conn.close()

# ----------------- ADD TENDER -----------------
@app.post("/tenders")
def add_tender(t: Tender):
    conn = get_db_connection()

    try:
        query = """
            INSERT INTO tenders (
                tender_status,
                received_date,
                due_date,
                name_of_client,
                location,
                tender_no,
                tender_open_price,
                quoted_value,
                description,
                project_manager,
                emd,
                emd_status,
                tender_fee_status,
                price_status,
                source,
                comments,
                docs_prepared_by,
                financial_year,
                pre_bidding_date,
                pre_bid_time,
                mode_of_conduct,
                platform_or_address
            )

            VALUES (
                ?,?,?,?,?,?,?,?,?,?,
                ?,?,?,?,?,?,?,?,?,?,
                ?,?
            )
        """

        conn.execute(
            query,
            (
                t.tender_status,
                t.received_date,
                t.due_date,
                t.name_of_client,
                t.location,
                t.tender_no,
                t.tender_open_price,
                t.quoted_value,
                t.description,
                t.project_manager,
                t.emd,
                t.emd_status,
                t.tender_fee_status,
                t.price_status,
                t.source,
                t.comments,
                t.docs_prepared_by,
                t.financial_year,
                t.pre_bidding_date,
                t.pre_bid_time,
                t.mode_of_conduct,
                t.platform_or_address
            )
        )

        conn.commit()

        return {
            "message": "Success"
        }

    except Exception as e:
        print(f"DATABASE ERROR: {e}")

        return {
            "error": str(e)
        }

    finally:
        conn.close()

# ----------------- EXPORT -----------------
@app.get("/export-tenders")
def export_tenders():
    conn = get_db_connection()

    try:
        tenders = conn.execute(
            "SELECT * FROM tenders"
        ).fetchall()

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
            "Project Manager"
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
                t["project_manager"]
            ])

        output.seek(0)

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition":
                "attachment; filename=tenders_export.csv"
            }
        )

    finally:
        conn.close()

# ----------------- QUICK STATUS UPDATE -----------------
@app.patch("/tenders/{tender_no:path}/status")
def quick_update_status(
    tender_no: str,
    update: StatusUpdate
):
    conn = get_db_connection()

    try:
        conn.execute(
            """
            UPDATE tenders
            SET tender_status = ?
            WHERE tender_no = ?
            """,
            (
                update.tender_status,
                tender_no
            )
        )

        conn.commit()

        return {
            "message": "Status updated successfully"
        }

    except Exception as e:
        return {
            "error": str(e)
        }

    finally:
        conn.close()

# ----------------- DELETE TENDER -----------------
@app.delete("/tenders/{tender_no:path}")
def delete_tender(tender_no: str):
    conn = get_db_connection()

    try:
        cursor = conn.execute(
            """
            DELETE FROM tenders
            WHERE tender_no = ?
            """,
            (tender_no,)
        )

        conn.commit()

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Tender not found"
            )

        return {
            "message": "Tender deleted successfully"
        }

    except Exception as e:
        return {
            "error": str(e)
        }

    finally:
        conn.close()

# ----------------- UPDATE TENDER -----------------
@app.put("/tenders/{tender_no:path}")
def update_tender(
    tender_no: str,
    t: Tender
):
    conn = get_db_connection()

    try:
        conn.execute(
            """
            UPDATE tenders SET

            name_of_client=?,
            tender_status=?,
            received_date=?,
            due_date=?,
            pre_bidding_date=?,
            pre_bid_time=?,
            mode_of_conduct=?,
            platform_or_address=?,
            location=?,
            tender_open_price=?,
            quoted_value=?,
            description=?,
            project_manager=?,
            emd=?,
            emd_status=?,
            tender_fee_status=?,
            price_status=?,
            source=?,
            comments=?,
            docs_prepared_by=?,
            financial_year=?

            WHERE tender_no=?
            """,

            (
                t.name_of_client,
                t.tender_status,
                t.received_date,
                t.due_date,
                t.pre_bidding_date,
                t.pre_bid_time,
                t.mode_of_conduct,
                t.platform_or_address,
                t.location,
                t.tender_open_price,
                t.quoted_value,
                t.description,
                t.project_manager,
                t.emd,
                t.emd_status,
                t.tender_fee_status,
                t.price_status,
                t.source,
                t.comments,
                t.docs_prepared_by,
                t.financial_year,
                tender_no
            )
        )

        conn.commit()

        return {
            "message": "Updated successfully"
        }

    except Exception as e:
        return {
            "error": str(e)
        }

    finally:
        conn.close()

# ----------------- MAIN -----------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8001
    )
# knowledge_service.py
import os
import re
import json
import glob
import threading
from typing import List, Dict, Optional
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KB_DIR = os.path.join(BASE_DIR, "knowledge_base")
AARVI_JSON_DIR = os.path.join(KB_DIR, "Aarvi_Encon")
EXCEL_PATH = os.path.join(KB_DIR, "Cleaned_Tender_Data.xlsx")
REF_TXT_PATH = os.path.join(KB_DIR, "reference_knowledge.txt")

_EXCEL_LOCK = threading.Lock()
_CACHE_LOCK = threading.Lock()
_KB_CACHE = {
    "loaded": False,
    "excel_rows": [],
    "client_profiles": [],
    "reference_rules": "",
}

# Multi-alias mapping so full names and short PSU acronyms always match both Excel & DB
CLIENT_ALIAS_GROUPS = [
    ["mrpl", "mangalore refinery"],
    ["hpcl", "hindustan petroleum"],
    ["bpcl", "bharat petroleum"],
    ["iocl", "indian oil"],
    ["ongc", "oil & natural gas", "oil and natural gas"],
    ["gail", "gas authority"],
    ["cpcl", "chennai petroleum"],
    ["nrl", "numaligarh refinery"],
    ["ril", "reliance industries", "reliance"],
    ["hmel", "hpcl mittal"],
    ["ntpc", "national thermal"],
    ["bhel", "bharat heavy"],
    ["eil", "engineers india"],
    ["mngl", "maharashtra natural gas"],
    ["igl", "indraprastha gas"],
    ["opal", "ongc petro additions"],
    ["hurl", "hindustan urvarak"],
    ["rfcl", "ramagundam fertilisers"],
    ["gsfc", "gujarat state fertilisers"],
    ["borl", "bharat oman refineries"],
    ["bcpl", "brahmaputra cracker"],
]


def get_client_aliases(client_name: str) -> List[str]:
    """Returns all known search aliases for a client name (acronym + full name)."""
    if not client_name or str(client_name).strip().lower() in ("not specified", "n/a", ""):
        return []
    raw = str(client_name).strip()
    lower = raw.lower()

    aliases = {lower}
    # Strip parenthetical suffixes like "(MRPL)" or "(India) Limited"
    cleaned = re.sub(r"\([^)]*\)", "", lower).strip()
    if cleaned and len(cleaned) >= 3:
        aliases.add(cleaned)

    for group in CLIENT_ALIAS_GROUPS:
        if any(alias in lower for alias in group):
            aliases.update(group)

    # Sort longest-first, keeping aliases >= 3 chars to prevent false substring hits
    return sorted([a for a in aliases if len(a) >= 3], key=len, reverse=True)


def _safe_float(val) -> float:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0.0
    try:
        return float(str(val).replace(",", "").strip())
    except Exception:
        return 0.0


def _load_excel_rows() -> List[Dict]:
    if not os.path.exists(EXCEL_PATH):
        return []
    try:
        df = pd.read_excel(EXCEL_PATH, sheet_name=0)
        records = []
        for _, r in df.iterrows():
            rec = {}
            for col in df.columns:
                v = r[col]
                if pd.isna(v):
                    rec[col] = None
                elif hasattr(v, "strftime"):
                    rec[col] = v.strftime("%Y-%m-%d")
                else:
                    rec[col] = v
            records.append(rec)
        return records
    except Exception as e:
        print(f"⚠️ Knowledge Excel load error: {e}", flush=True)
        return []


def _load_client_profiles() -> List[Dict]:
    profiles = []
    for path in sorted(glob.glob(os.path.join(AARVI_JSON_DIR, "*.json"))):
        if os.path.basename(path).startswith("~$"):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                data["_source_file"] = os.path.basename(path)
                profiles.append(data)
        except Exception as e:
            print(f"⚠️ Skipping malformed KB JSON {path}: {e}", flush=True)
    return profiles


def _load_reference_rules() -> str:
    if not os.path.exists(REF_TXT_PATH):
        return ""
    try:
        with open(REF_TXT_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def get_knowledge_store(force_reload: bool = False) -> Dict:
    with _CACHE_LOCK:
        if not _KB_CACHE["loaded"] or force_reload:
            _KB_CACHE["excel_rows"] = _load_excel_rows()
            _KB_CACHE["client_profiles"] = _load_client_profiles()
            _KB_CACHE["reference_rules"] = _load_reference_rules()
            _KB_CACHE["loaded"] = True
            print(
                f"🧠 [KNOWLEDGE BASE READY] Excel rows: {len(_KB_CACHE['excel_rows'])} | "
                f"Client JSON profiles: {len(_KB_CACHE['client_profiles'])} | "
                f"Reference rules: {len(_KB_CACHE['reference_rules'])} chars",
                flush=True,
            )
        return _KB_CACHE


def _parse_competitors_from_text(comments_text: str) -> List[Dict]:
    """
    Parses ranked L1-L5 competitor lines from Excel `comments` such as:
    '1) Sinclus Engineering and Consulting Pvt Ltd: Rs. 1,50,20,038.13/- (L1) [+4.54%]'
    """
    if not comments_text:
        return []
    parsed = []
    for line in str(comments_text).splitlines():
        line_s = line.strip()
        m = re.match(
            r"^\d+\)\s*([^:(\n]+?)(?::\s*(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\.\d+)?)/?-?)?\s*(?:\((L\d+)\))?\s*(?:\[([+-]?\d+(?:\.\d+)?)%\])?",
            line_s,
            re.IGNORECASE,
        )
        if m:
            comp_name = m.group(1).strip()
            amt = _safe_float(m.group(2))
            rank = (m.group(3) or "").upper()
            diff = abs(_safe_float(m.group(4))) if m.group(4) else 0.0
            if comp_name and len(comp_name) > 2:
                parsed.append({
                    "company": comp_name,
                    "rank": rank,
                    "amount": amt,
                    "percent_diff": diff,
                })
    return parsed


def build_unified_client_intelligence(client_name: str, neon_url: str) -> Dict:
    """
    Merges historical records from BOTH `Cleaned_Tender_Data.xlsx` AND live
    PostgreSQL `tenders` using multi-alias matching (e.g., MRPL <-> Mangalore Refinery).
    Uses strictly parameterized SQL (`%s`) with read-only SELECT.
    """
    aliases = get_client_aliases(client_name)
    if not aliases:
        return {"kpi": "No Past Record", "competitors": "No historical competitor data found for this client."}

    store = get_knowledge_store()
    merged_by_tender: Dict[str, Dict] = {}

    # 1. Match from Knowledge Base Excel
    for row in store["excel_rows"]:
        c_val = str(row.get("name_of_client") or "").lower()
        if any(alias in c_val for alias in aliases):
            t_key = str(row.get("tender_no") or f"xl_{len(merged_by_tender)}").strip().upper()
            merged_by_tender[t_key] = dict(row)

    # 2. Merge / override with live PostgreSQL Master Dashboard rows (read-only parameterized query)
    if neon_url:
        try:
            conn = psycopg2.connect(neon_url, cursor_factory=RealDictCursor)
            cur = conn.cursor()
            like_clauses = " OR ".join(["name_of_client ILIKE %s" for _ in aliases])
            params = [f"%{a}%" for a in aliases]
            cur.execute(
                f"""
                SELECT tender_no, name_of_client, tender_status, received_date, due_date,
                       tender_open_price, quoted_value, description, competitor_list, comments,
                       reason_for_loss, post_bid_remarks
                FROM tenders
                WHERE {like_clauses};
                """,
                params,
            )
            for db_row in cur.fetchall():
                t_key = str(db_row.get("tender_no") or f"db_{len(merged_by_tender)}").strip().upper()
                merged_by_tender[t_key] = dict(db_row)
            cur.close()
            conn.close()
        except Exception as db_err:
            print(f"⚠️ DB intelligence lookup fallback to Excel only: {db_err}", flush=True)

    records = list(merged_by_tender.values())
    if not records:
        return {"kpi": "No Past Record", "competitors": "No historical competitor data found for this client."}

    won_bids = sum(1 for r in records if str(r.get("tender_status")).strip() == "Tender Won")
    lost_bids = sum(1 for r in records if str(r.get("tender_status")).strip() == "Tender Lost")
    quoted_bids = sum(1 for r in records if str(r.get("tender_status")).strip() in ("Tender Quoted", "Quoted", "Quoted Active"))
    regret_bids = sum(1 for r in records if str(r.get("tender_status")).strip() == "Tender Regret")
    cancelled_bids = sum(1 for r in records if str(r.get("tender_status")).strip() in ("Cancelled", "Tender Cancelled"))

    decided = won_bids + lost_bids
    win_rate = round((won_bids / decided) * 100) if decided > 0 else 0
    loss_rate = (100 - win_rate) if decided > 0 else 0

    kpi_text = (
        f"[ ❌ {loss_rate}% | 🎉 {win_rate}% ] (Total History: {len(records)} tenders)\n"
        f"Won: {won_bids} | Lost: {lost_bids} | Quoted: {quoted_bids} | Regret: {regret_bids} | Cancelled: {cancelled_bids}"
    )

    threats: Dict[str, Dict] = {}
    qualitative_notes: List[str] = []
    records_with_intel = 0

    for row in records:
        status = str(row.get("tender_status") or "").strip()
        t_no = str(row.get("tender_no") or "N/A").strip()
        has_intel = False

        # A. Structured JSON competitors (from Master Dashboard Log Loss modal)
        comp_json_raw = row.get("competitor_list")
        comp_entries = []
        if comp_json_raw and isinstance(comp_json_raw, str) and comp_json_raw.strip() not in ("[]", ""):
            try:
                loaded = json.loads(comp_json_raw)
                if isinstance(loaded, list):
                    comp_entries.extend(loaded)
            except Exception:
                pass
        elif isinstance(comp_json_raw, list):
            comp_entries.extend(comp_json_raw)

        # B. Text L1-L5 leaderboard inside `comments` (from Cleaned_Tender_Data.xlsx)
        comments_str = str(row.get("comments") or "").strip()
        if comments_str and comments_str.lower() not in ("nan", "none", ""):
            text_comps = _parse_competitors_from_text(comments_str)
            if text_comps:
                comp_entries.extend(text_comps)
            else:
                qualitative_notes.append(f"[{status} | {t_no}] {comments_str}")
                has_intel = True

        reason_loss = str(row.get("reason_for_loss") or "").strip()
        if reason_loss and reason_loss.lower() not in ("nan", "none", ""):
            qualitative_notes.append(f"[Loss Reason | {t_no}] {reason_loss}")
            has_intel = True

        # Aggregate competitor stats (excluding Aarvi itself)
        aarvi_price = 0.0
        l1_price = 0.0
        for c in comp_entries:
            c_name = str(c.get("company") or "").strip()
            if "aarvi" in c_name.lower():
                aarvi_price = _safe_float(c.get("amount"))
            if str(c.get("rank") or "").upper() == "L1" and _safe_float(c.get("amount")) > 0:
                if l1_price == 0.0:
                    l1_price = _safe_float(c.get("amount"))

        for c in comp_entries:
            c_name = str(c.get("company") or "").strip()
            if not c_name or "aarvi" in c_name.lower():
                continue
            has_intel = True
            rank = str(c.get("rank") or "").upper()
            gap = _safe_float(c.get("percent_diff"))
            if gap == 0.0 and rank == "L1" and aarvi_price > 0 and l1_price > 0 and aarvi_price > l1_price:
                gap = round(((aarvi_price - l1_price) / l1_price) * 100, 2)

            if c_name not in threats:
                threats[c_name] = {"encounters": 0, "wins": 0, "gaps": []}
            threats[c_name]["encounters"] += 1
            if rank == "L1":
                threats[c_name]["wins"] += 1
            if gap > 0:
                threats[c_name]["gaps"].append(gap)

        if has_intel:
            records_with_intel += 1

    if records_with_intel == 0:
        comp_text = (
            f"Found {len(records)} past tenders for this client, with no detailed competitor breakdown logged yet."
        )
    else:
        comp_text = f"Matched {len(records)} historical tenders ({records_with_intel} with competitor/qualification logs):\n\n"
        if threats:
            comp_text += "**Quantitative Competitor Threats:**\n"
            sorted_threats = sorted(threats.items(), key=lambda x: (x[1]["wins"], x[1]["encounters"]), reverse=True)
            medals = ["🥇 1.", "🥈 2.", "🥉 3."]
            for i, (c_name, d) in enumerate(sorted_threats[:5]):
                avg_gap = round(sum(d["gaps"]) / len(d["gaps"]), 2) if d["gaps"] else 0.0
                medal = medals[i] if i < 3 else f"• {i + 1}."
                comp_text += f"{medal} **{c_name}**\n"
                comp_text += f"   - Encountered: {d['encounters']} times | L1 Wins: {d['wins']} times\n"
                if avg_gap > 0:
                    comp_text += f"   - Average Price Gap vs Aarvi: {avg_gap}%\n"
        if qualitative_notes:
            comp_text += "\n**Historical Qualification & Bid Notes:**\n"
            for note in list(dict.fromkeys(qualitative_notes))[:6]:
                comp_text += f"• {note}\n"

    return {"kpi": kpi_text, "competitors": comp_text.strip()}


def find_similar_past_projects(scope_text: str, client_name: str = "", limit: int = 5) -> List[Dict]:
    """
    Searches `Aarvi_Encon/*.json` project cost/execution records to prove Similar Work
    and Financial PQ (1 PO > 1.38 Cr or 2 POs > 86.25 Lac).
    """
    store = get_knowledge_store()
    keywords = set(re.findall(r"[a-z]{4,}", f"{scope_text} {client_name}".lower()))
    stopwords = {"that", "with", "from", "this", "shall", "will", "have", "been", "work", "tender", "services", "for"}
    keywords -= stopwords

    scored_projects = []
    for prof in store["client_profiles"]:
        p_client = prof.get("client", "")
        p_industry = prof.get("industry", "")
        total_val = _safe_float(prof.get("total_contract_value_inr"))
        tech_caps = " ".join(prof.get("technical_capabilities", []))

        for proj in prof.get("projects", []):
            po = proj.get("po_details") or {}
            po_val = _safe_float(po.get("contract_value_inr")) or total_val
            blob = (
                f"{p_client} {p_industry} {proj.get('project_name', '')} "
                f"{' '.join(proj.get('scope_of_work', []))} {' '.join(proj.get('roles_deployed', []))} {tech_caps}"
            ).lower()
            overlap = sum(1 for kw in keywords if kw in blob)
            if overlap > 0:
                scored_projects.append({
                    "score": overlap + (3 if po_val >= 8625000 else 0),
                    "client": p_client,
                    "industry": p_industry,
                    "project_name": proj.get("project_name", "N/A"),
                    "po_number": po.get("po_number", "N/A"),
                    "po_date": po.get("date", "N/A"),
                    "contract_value_inr": po_val,
                    "roles_deployed": proj.get("roles_deployed", []),
                    "execution_model": proj.get("execution_model", ""),
                })

    scored_projects.sort(key=lambda x: (x["score"], x["contract_value_inr"]), reverse=True)
    return scored_projects[:limit]


def query_knowledge_for_chat(query: str, client_hint: str = "") -> str:
    """
    Provides read-only context from `Cleaned_Tender_Data.xlsx`, `Aarvi_Encon/*.json`,
    and `reference_knowledge.txt` whenever a user asks questions in Chat.
    """
    store = get_knowledge_store()
    q_lower = f"{query} {client_hint}".lower()
    aliases = get_client_aliases(client_hint)
    for group in CLIENT_ALIAS_GROUPS:
        if any(a in q_lower for a in group):
            aliases.extend(group)
    aliases = list(dict.fromkeys(aliases))

    sections = []

    # 1. Matching Excel Historical Tenders
    matched_excel = []
    tokens = [w for w in re.findall(r"[a-z0-9]{3,}", q_lower) if w not in ("what", "with", "have", "from", "that", "tender", "tenders")]
    for row in store["excel_rows"]:
        c_str = str(row.get("name_of_client") or "").lower()
        row_blob = f"{c_str} {row.get('tender_no', '')} {row.get('description', '')} {row.get('comments', '')}".lower()
        if (aliases and any(a in c_str for a in aliases)) or (len(tokens) >= 2 and sum(1 for t in tokens if t in row_blob) >= 2):
            matched_excel.append(row)

    if matched_excel:
        lines = [f"### Historical Tender Records (`Cleaned_Tender_Data.xlsx` — {len(matched_excel)} matches):"]
        for r in matched_excel[:15]:
            lines.append(
                f"- **{r.get('name_of_client')}** | Tender: `{r.get('tender_no')}` | Status: **{r.get('tender_status')}** | "
                f"Date: {r.get('received_date')} | Est: {r.get('tender_open_price')} | Quoted: {r.get('quoted_value')} | "
                f"Notes: {str(r.get('comments') or 'N/A').replace(chr(10), ' ; ')}"
            )
        sections.append("\n".join(lines))

    # 2. Matching Project Cost & PO Execution Profiles (`Aarvi_Encon/*.json`)
    matched_projs = find_similar_past_projects(query, client_hint, limit=6)
    if matched_projs:
        lines = ["### Past Executed Projects & PO Values (`Aarvi_Encon` Knowledge Base):"]
        for p in matched_projs:
            lines.append(
                f"- **{p['client']}** — *{p['project_name']}* | PO: `{p['po_number']}` ({p['po_date']}) | "
                f"Value: **₹{p['contract_value_inr']:,.0f}** | Roles: {', '.join(p['roles_deployed'])}"
            )
        sections.append("\n".join(lines))

    # 3. Reference Costing & Policy Rules (`reference_knowledge.txt`)
    if store["reference_rules"] and any(
        k in q_lower for k in ("cost", "profit", "margin", "ctc", "wage", "salary", "score", "rule", "policy", "pq", "emd", "msme", "mii", "service charge")
    ):
        sections.append(f"### Aarvi Encon Costing & Strategy Rules (`reference_knowledge.txt`):\n{store['reference_rules'][:3500]}")

    return "\n\n".join(sections)


def sync_tender_to_excel(tender_dict: Dict):
    """
    Append/Update-ONLY sync from Master Dashboard into `Cleaned_Tender_Data.xlsx`.
    Never deletes historical rows even if a tender is removed from the dashboard.
    """
    if not tender_dict or not tender_dict.get("tender_no"):
        return

    with _EXCEL_LOCK:
        try:
            if os.path.exists(EXCEL_PATH):
                df = pd.read_excel(EXCEL_PATH, sheet_name=0)
            else:
                cols = [
                    "sr_no", "tender_status", "received_date", "due_date", "name_of_client",
                    "location", "tender_no", "tender_open_price", "quoted_value", "description",
                    "project_manager", "emd", "emd_status", "tender_fee_status", "price_status",
                    "source", "comments", "docs_prepared_by",
                ]
                df = pd.DataFrame(columns=cols)

            t_no = str(tender_dict.get("tender_no")).strip()
            mask = df["tender_no"].astype(str).str.strip() == t_no

            if mask.any():
                idx = df.index[mask][0]
                for col in df.columns:
                    if col != "sr_no" and col in tender_dict and tender_dict[col] is not None:
                        df.at[idx, col] = tender_dict[col]
            else:
                next_sr = int(pd.to_numeric(df["sr_no"], errors="coerce").max() or 0) + 1 if "sr_no" in df.columns else len(df) + 1
                new_row = {col: tender_dict.get(col) for col in df.columns}
                if "sr_no" in df.columns:
                    new_row["sr_no"] = next_sr
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

            df.to_excel(EXCEL_PATH, index=False)
            get_knowledge_store(force_reload=True)
            print(f"📗 [EXCEL SYNCED] Tender '{t_no}' saved to Cleaned_Tender_Data.xlsx", flush=True)
        except Exception as e:
            print(f"⚠️ Excel sync warning for tender '{tender_dict.get('tender_no')}': {e}", flush=True)
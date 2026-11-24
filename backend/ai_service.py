# ai_service.py
import os
import re
import gc
import glob
import json
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
from google import genai
from google.genai import types

from config import (
    GEMINI_API_KEY,
    GEMINI_PRIMARY_MODEL,
    GEMINI_FALLBACK_MODEL,
    GEMINI_TIMEOUT_SECONDS,
    TRIAGE_ENABLED,
    TRIAGE_TOKEN_BUDGET,
)
from models import TenderExtractionSchema, StrategyExtractionSchema
from logic import evaluate_tender_rules
from triage import select_triaged_pages, select_pages_for_missing_fields

# --- DATABASE CONNECTION ---
load_dotenv()
NEON_URL = os.getenv("DATABASE_URL")
if not NEON_URL:
    raise ValueError("❌ CRITICAL ERROR: DATABASE_URL is missing from your environment variables!")

# 1. Initialize the Client
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

ALL_15_FIELDS = [
    "tender_no", "client_name", "due_date", "tender_open_price", "emd",
    "financial_qualification", "technical_qualification", "mandatory_compliance",
    "scope_of_work", "manpower_count", "manpower_qual", "shift_duty",
    "payment_terms", "penalty_terms", "similar_work",
]


# 2. SDK Wrapper with Timeout & Automatic Fallback
class ModelWrapper:
    def __init__(self, primary_model: str, fallback_model: str = None, timeout_sec: int = 90):
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.timeout_sec = timeout_sec

    def _call_single_model(self, model_name: str, contents: str, config_obj):
        def _invoke():
            return client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config_obj,
            )

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_invoke)
            try:
                return future.result(timeout=self.timeout_sec)
            except FuturesTimeoutError:
                raise TimeoutError(f"Model '{model_name}' timed out after {self.timeout_sec}s")

    def generate_content(self, contents: str, **kwargs):
        if not client:
            raise ValueError("Gemini API Key is missing!")

        raw_cfg = kwargs.get("config") or kwargs.get("generation_config") or {}
        if isinstance(raw_cfg, dict):
            cfg_dict = {"temperature": 0.0, **raw_cfg}
            config_obj = types.GenerateContentConfig(**cfg_dict)
        else:
            config_obj = raw_cfg

        models_to_try = [self.primary_model]
        if self.fallback_model and self.fallback_model != self.primary_model:
            models_to_try.append(self.fallback_model)

        last_err = None
        for idx, m_name in enumerate(models_to_try):
            try:
                return self._call_single_model(m_name, contents, config_obj)
            except Exception as err:
                last_err = err
                if idx + 1 < len(models_to_try):
                    print(
                        f"⚠️ [AI RETRY] '{m_name}' failed ({err}). Falling back to '{models_to_try[idx + 1]}'...",
                        flush=True,
                    )
        raise RuntimeError(f"All Gemini models failed ({models_to_try}): {last_err}")


def get_model() -> ModelWrapper:
    return ModelWrapper(
        primary_model=GEMINI_PRIMARY_MODEL,
        fallback_model=GEMINI_FALLBACK_MODEL,
        timeout_sec=GEMINI_TIMEOUT_SECONDS,
    )


def get_knowledge_base() -> str:
    path = os.path.join("knowledge_base", "Aarvi_Encon", "*.json")
    knowledge = []
    for file_path in glob.glob(path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                knowledge.append(json.load(f))
        except Exception:
            pass
    return json.dumps(knowledge)


def clean_price_to_float(price_str) -> float:
    """Converts price strings like '25 Lakh', '2,500,000', or '25,00,000' to a float."""
    if not price_str or price_str == "Not Specified":
        return 0.0

    text = str(price_str).lower().replace(",", "")
    num = re.findall(r"[-+]?\d*\.\d+|\d+", text)
    if not num:
        return 0.0
    val = float(num[0])

    if "lakh" in text or "lac" in text:
        val *= 100000
    elif "crore" in text or "cr" in text:
        val *= 10000000

    return val


def format_for_ui(value) -> str:
    if not value or value == "Not Specified" or value == []:
        return "Not Specified"
    if isinstance(value, list):
        formatted = ""
        for item in value:
            if isinstance(item, str):
                formatted += f"• {item.strip()}\n"
            elif isinstance(item, dict):
                formatted += "\n".join([f"**{str(k).replace('_', ' ').title()}**: {v}" for k, v in item.items()]) + "\n"
        return formatted.strip()
    return str(value).strip()


def normalize_client_name(extracted_name: str) -> str:
    """Translates full company names into core acronyms to group joint ventures."""
    if not extracted_name or extracted_name == "Not Specified":
        return extracted_name

    name = str(extracted_name).upper().strip()

    if "HINDUSTAN PETROLEUM" in name:
        return "HPCL"
    if "INDIAN OIL" in name:
        return "IOCL"
    if "OIL & NATURAL GAS" in name or "OIL AND NATURAL GAS" in name:
        return "ONGC"
    if "BHARAT PETROLEUM" in name:
        return "BPCL"
    if "GAIL" in name or "GAS AUTHORITY" in name:
        return "GAIL"

    return extracted_name.strip()


def fetch_client_intelligence(client_name: str) -> dict:
    """
    Connects to Neon to extract Win/Loss ratios, structured Competitor Threats,
    AND unstructured qualitative comments for Lost bids.
    """
    search_name = normalize_client_name(client_name)

    if not search_name or search_name == "Not Specified":
        return {"kpi": "No Past Record", "competitors": "No historical competitor data found for this client."}

    try:
        conn = psycopg2.connect(NEON_URL, cursor_factory=RealDictCursor)
        cur = conn.cursor()

        cur.execute(
            """
            SELECT tender_status, competitor_list, comments
            FROM tenders
            WHERE name_of_client ILIKE %s
            """,
            (f"%{search_name}%",),
        )

        records = cur.fetchall()
        cur.close()
        conn.close()

        if not records:
            return {"kpi": "No Past Record", "competitors": "No historical competitor data found for this client."}

        won_bids = sum(1 for r in records if r["tender_status"] == "Tender Won")
        lost_bids = sum(1 for r in records if r["tender_status"] == "Tender Lost")
        quoted_bids = sum(1 for r in records if r["tender_status"] in ["Tender Quoted", "Quoted"])
        cancelled_bids = sum(1 for r in records if r["tender_status"] in ["Cancelled", "Tender Cancelled"])

        total_bids = won_bids + lost_bids + quoted_bids + cancelled_bids
        win_rate = round((won_bids / total_bids) * 100) if total_bids > 0 else 0
        loss_rate = 100 - win_rate

        kpi_text = (
            f"[ ❌ {loss_rate}% | 🎉 {win_rate}% ]\n"
            f"Total Bids: {total_bids} (Won: {won_bids} | Lost: {lost_bids} | Quoted: {quoted_bids} | Cancelled: {cancelled_bids})"
        )

        threats = {}
        raw_comments = []
        lost_records_with_data = 0

        for row in records:
            if row["tender_status"] == "Tender Lost":
                has_extracted_something = False

                competitors = row.get("competitor_list")
                if competitors and isinstance(competitors, str) and competitors.strip() not in ["[]", ""]:
                    try:
                        comp_list = json.loads(competitors)
                        if isinstance(comp_list, list) and len(comp_list) > 0:
                            has_extracted_something = True
                            for comp in comp_list:
                                name = comp.get("company", "")
                                rank = comp.get("rank", "")
                                gap = comp.get("percent_diff") or 0.0

                                if name and name.lower() not in ["aarvi encon", "aarvi encon ltd", "aarvi"]:
                                    if name not in threats:
                                        threats[name] = {"encounters": 0, "wins": 0, "gaps": []}

                                    threats[name]["encounters"] += 1
                                    if rank == "L1":
                                        threats[name]["wins"] += 1
                                    if gap > 0:
                                        threats[name]["gaps"].append(gap)
                    except json.JSONDecodeError:
                        raw_comments.append(f"Competitor Note: {competitors.strip()}")
                        has_extracted_something = True

                comments = row.get("comments")
                if comments and str(comments).strip().lower() not in ["nan", "none", ""]:
                    raw_comments.append(str(comments).strip())
                    has_extracted_something = True

                if has_extracted_something:
                    lost_records_with_data += 1

        if lost_records_with_data == 0:
            comp_text = (
                f"We have {total_bids} bids on record, but no competitor history or loss comments were found for these past losses."
            )
        else:
            comp_text = (
                f"Our backend records indicate we have logged qualitative data on {lost_records_with_data} lost tenders for this operator.\n\n"
            )

            if threats:
                comp_text += "**Quantitative Competitor Threats:**\n"
                sorted_threats = sorted(threats.items(), key=lambda x: (x[1]["wins"], x[1]["encounters"]), reverse=True)
                medals = ["🥇 1.", "🥈 2.", "🥉 3."]

                for i, (comp_name, data) in enumerate(sorted_threats[:3]):
                    avg_gap = round(sum(data["gaps"]) / len(data["gaps"]), 2) if data["gaps"] else 0.0
                    medal = medals[i] if i < 3 else f"• {i + 1}."

                    comp_text += f"{medal} **{comp_name}**\n"
                    comp_text += f"   - Encountered: {data['encounters']} times | Has taken L1 Rank: {data['wins']} times\n"
                    if avg_gap > 0:
                        comp_text += f"   - Average Margin Disadvantage: We typically lose to them by a gap of {avg_gap}%\n\n"
                    else:
                        comp_text += "   - Average Margin Disadvantage: Baseline benchmark maker (0.00% variance)\n\n"

            if raw_comments:
                comp_text += "**Qualitative Loss Reasons & Background:**\n"
                for comment in set(raw_comments):
                    comp_text += f"• {comment}\n"

        return {"kpi": kpi_text, "competitors": comp_text.strip()}

    except Exception as db_err:
        print(f"Database background intelligence lookup skipped: {db_err}", flush=True)
        return {"kpi": "Database Offline", "competitors": "Could not retrieve competitor history."}


def ensure_ui_schema(ai_data: dict, logic_data: dict, intel_data: dict, error_msg: str = None) -> dict:
    template = {
        "tender_no": "Not Specified",
        "client_name": "Not Specified",
        "description": "Not Specified",
        "due_date": "Not Specified",
        "tender_open_price": "Not Specified",
        "emd": "Not Specified",
        "financial_qualification": "Not Specified",
        "technical_qualification": "Not Specified",
        "mandatory_compliance": "Not Specified",
        "scope_of_work": "Not Specified",
        "manpower_count": "Not Specified",
        "manpower_qual": "Not Specified",
        "shift_duty": "Not Specified",
        "payment_terms": "Not Specified",
        "penalty_terms": "Not Specified",
        "similar_work": "Not Specified",
        "bid_decision": "PENDING",
        "pq_status": "PENDING",
        "win_probability": "PENDING",
        "profit_forecast": "PENDING",
        "win_loss_kpi": "Not Specified",
        "historical_competitors": "Not Specified",
        "strategic_advice": "Not Specified",
        "compliance_status": "Not Specified",
        "compliance_reason": "Not Specified",
    }

    if error_msg:
        template["strategic_advice"] = f"Error: {error_msg}"
        return template

    for key in ai_data:
        if key in template:
            template[key] = format_for_ui(ai_data[key])

    if template["description"] == "Not Specified" and template["scope_of_work"] != "Not Specified":
        template["description"] = template["scope_of_work"]

    for key in logic_data:
        if key in template:
            template[key] = str(logic_data[key])

    template["win_loss_kpi"] = intel_data.get("kpi", "No Past Record")
    template["historical_competitors"] = intel_data.get("competitors", "No Data")
    return template


def _parse_json_response(response_obj) -> dict:
    raw_text = getattr(response_obj, "text", "") or ""
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ValueError(f"Gemini returned non-JSON output: {raw_text[:200]}")


def _extract_tokens(response_obj) -> tuple:
    meta = getattr(response_obj, "usage_metadata", None)
    if not meta:
        return 0, 0
    return (
        int(getattr(meta, "prompt_token_count", 0) or 0),
        int(getattr(meta, "candidates_token_count", 0) or 0),
    )


def _is_missing_val(val) -> bool:
    if val is None:
        return True
    s = str(val).strip().lower()
    return s in ("", "not specified", "n/a", "none", "null")


# ==============================================================================
# 🚀 TRIAGED TWO-PASS STRUCTURED TENDER GENERATOR
# ==============================================================================
def generate_tender_summary(tender_text: str = None):
    """
    Triaged two-pass AI extractor using structured Pydantic schemas,
    model fallback, timing logs, and loud error propagation.
    """
    t0 = time.time()
    total_input_tokens = 0
    total_output_tokens = 0

    if not tender_text:
        raise ValueError("Empty tender document stream provided.")

    pages_list = None
    source_path = None

    # Read from disk stream + per-page JSON sidecar if passed a file path
    if len(tender_text) < 1000 and os.path.exists(tender_text):
        source_path = tender_text
        sidecar_path = f"{source_path}.pages.json"
        if os.path.exists(sidecar_path):
            try:
                with open(sidecar_path, "r", encoding="utf-8") as sf:
                    pages_list = json.load(sf)
            except Exception as e:
                print(f"⚠️ Could not load pages sidecar ({e}); using flat stream.", flush=True)

        with open(source_path, "r", encoding="utf-8") as f:
            tender_text = f.read()

    if not tender_text or len(tender_text.strip()) == 0:
        raise ValueError("Extracted tender text is empty.")

    # 1. Triage Selection
    t_triage = time.time()
    selected_keys = set()
    if TRIAGE_ENABLED and pages_list:
        prompt_doc_text, selected_keys, t_stats = select_triaged_pages(pages_list, TRIAGE_TOKEN_BUDGET)
        print(
            f"🎯 [TRIAGE] Selected {t_stats['selected_pages']}/{t_stats['total_pages']} pages "
            f"(~{t_stats['triaged_tokens']} tokens vs ~{t_stats['raw_tokens']} raw) in {time.time() - t_triage:.2f}s",
            flush=True,
        )
    else:
        max_chars = TRIAGE_TOKEN_BUDGET * 4
        prompt_doc_text = tender_text[:max_chars]
        print(
            f"📄 [DIRECT STREAM] Triage disabled or no sidecar; sending {len(prompt_doc_text)} chars.",
            flush=True,
        )

    model = get_model()
    kb_data = get_knowledge_base()

    # 2. Pass 1: Structured Extraction on High-Signal Pages
    t_pass1 = time.time()
    pass1_prompt = f"""
ROLE: Chief Bidding & Tender Analysis Specialist for Aarvi Encon Ltd.
TASK: Extract exact tender parameters from the provided triaged tender pages into the required JSON schema.

RULES:
1. Extract factual details strictly from the provided text. Do NOT invent or assume numbers.
2. Preserve exact currency symbols (₹ / Rs.), units (Lakh / Crore), percentages, and submission date + time.
3. For `manpower_count`, list every role and headcount using bullet points (`• Role: Count`).
4. For `scope_of_work`, summarize the core technical/manpower deliverables clearly.
5. Output `"Not Specified"` ONLY if a field is genuinely absent from the provided pages.

TRIAGED TENDER PAGES:
{prompt_doc_text}
"""
    response_p1 = model.generate_content(
        pass1_prompt,
        config={
            "temperature": 0.0,
            "response_mime_type": "application/json",
            "response_schema": TenderExtractionSchema,
        },
    )
    in_1, out_1 = _extract_tokens(response_p1)
    total_input_tokens += in_1
    total_output_tokens += out_1
    final_ai_data = _parse_json_response(response_p1)
    print(
        f"⏱️ [TIMINGS] Pass 1 ({GEMINI_PRIMARY_MODEL}): {time.time() - t_pass1:.2f}s "
        f"(in={in_1}, out={out_1})",
        flush=True,
    )

    # 3. Pass 2: Targeted Recovery for Any Missing Fields from Un-Sent Pages
    missing_fields = [f for f in ALL_15_FIELDS if _is_missing_val(final_ai_data.get(f))]
    if missing_fields and pages_list and selected_keys:
        recovery_text = select_pages_for_missing_fields(pages_list, missing_fields, selected_keys)
        if recovery_text.strip():
            t_pass2 = time.time()
            pass2_prompt = f"""
ROLE: Chief Bidding & Tender Analysis Specialist for Aarvi Encon Ltd.
TASK: A first scan missed these specific fields: {", ".join(missing_fields)}.
Search the additional tender pages below and extract ONLY the missing fields if present.
If a field is still not found in these pages, keep its value as `"Not Specified"`.

ADDITIONAL TENDER PAGES:
{recovery_text}
"""
            try:
                response_p2 = model.generate_content(
                    pass2_prompt,
                    config={
                        "temperature": 0.0,
                        "response_mime_type": "application/json",
                        "response_schema": TenderExtractionSchema,
                    },
                )
                in_2, out_2 = _extract_tokens(response_p2)
                total_input_tokens += in_2
                total_output_tokens += out_2
                pass2_data = _parse_json_response(response_p2)

                recovered = []
                for field in missing_fields:
                    candidate = pass2_data.get(field)
                    if not _is_missing_val(candidate):
                        final_ai_data[field] = candidate
                        recovered.append(field)

                print(
                    f"⏱️ [TIMINGS] Pass 2 Recovery: {time.time() - t_pass2:.2f}s | "
                    f"Recovered {len(recovered)}/{len(missing_fields)} fields {recovered}",
                    flush=True,
                )
            except Exception as p2_err:
                print(f"⚠️ Pass 2 recovery skipped due to non-fatal error: {p2_err}", flush=True)

    # 4. Business Scoring Rules & Client Historical Intelligence
    t_intel = time.time()
    sample_text = tender_text[:50000]
    logic_decisions = evaluate_tender_rules(final_ai_data, kb_data, sample_text)

    extracted_client = final_ai_data.get("client_name", "Not Specified")
    historical_intel = fetch_client_intelligence(extracted_client)

    if (
        historical_intel.get("kpi") != "No Past Record"
        and "No historical competitor data" not in historical_intel.get("competitors", "")
    ):
        strategy_prompt = f"""
ROLE: Senior Bidding Strategist & Consultant for Aarvi Encon.
CLIENT: {extracted_client}
RAW HISTORICAL LOSS DATA (Competitors & Pricing):
{historical_intel.get('competitors')}

TASK: Analyze the raw competitor data above and return a concise JSON breakdown with:
1. `top_3_competitors`: Clean bulleted list (`• `) of the Top 3 recurring competitors stating encounters, L1 wins, and specific loss reasons.
2. `strategic_advice`: Analytical 4-5 sentence recommendation to beat them on this bid.
"""
        try:
            ai_strat_obj = model.generate_content(
                strategy_prompt,
                config={
                    "temperature": 0.1,
                    "response_mime_type": "application/json",
                    "response_schema": StrategyExtractionSchema,
                },
            )
            in_s, out_s = _extract_tokens(ai_strat_obj)
            total_input_tokens += in_s
            total_output_tokens += out_s
            strategy_json = _parse_json_response(ai_strat_obj)

            historical_intel["competitors"] = strategy_json.get(
                "top_3_competitors", historical_intel["competitors"]
            )
            ai_advice = strategy_json.get("strategic_advice", "")
            base_advice = logic_decisions.get("strategic_advice", "")

            if ai_advice:
                if base_advice and base_advice != "Not Specified":
                    logic_decisions["strategic_advice"] = (
                        f"{base_advice}\n\n**🤖 Senior Consultant Strategy:**\n{ai_advice}"
                    )
                else:
                    logic_decisions["strategic_advice"] = f"**🤖 Senior Consultant Strategy:**\n{ai_advice}"
        except Exception as e:
            print(f"⚠️ Competitive strategy call skipped: {e}", flush=True)

    print(
        f"⏱️ [TIMINGS] Rules + Client Intel: {time.time() - t_intel:.2f}s | "
        f"TOTAL AI PIPELINE: {time.time() - t0:.2f}s",
        flush=True,
    )

    gc.collect()
    final_ui_data = ensure_ui_schema(final_ai_data, logic_decisions, historical_intel)

    return {
        "ui_data": final_ui_data,
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "tender_no": final_ai_data.get("tender_no", "N/A"),
    }


def chat_with_tender(query: str, context: dict, full_text: str = ""):
    model = get_model()
    prompt = (
        f"Context Summary: {json.dumps(context)}\n"
        f"Relevant Tender Excerpts: {full_text[:250000]}\n"
        f"User Question: {query}\n\n"
        "Answer strictly based on the tender text above using concise Markdown bullet points. "
        "Cite page numbers when visible in the excerpts."
    )

    response = model.generate_content(prompt, config={"temperature": 0.1})
    in_tokens, out_tokens = _extract_tokens(response)

    return {
        "reply": response.text,
        "input_tokens": in_tokens,
        "output_tokens": out_tokens,
    }


def generate_chat_title(first_message: str) -> str:
    if not first_message:
        return "New Analysis"

    model = get_model()
    prompt = f"""
Generate a short, concise, 3 to 4 word title for a business chat session based on this snippet:
"{first_message[:1000]}"

Rules:
- Output ONLY the title.
- Do not use quotes, punctuation, or conversational filler.
- Focus on the Client Name or primary subject.
"""
    try:
        response = model.generate_content(prompt, config={"temperature": 0.2})
        title = response.text.strip().replace('"', "").replace("\n", "")
        if len(title) > 35:
            title = title[:32] + "..."
        return title or "New Analysis"
    except Exception:
        return "New Analysis"
import json
import os
import glob
import re
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
from config import GEMINI_API_KEY
from logic import evaluate_tender_rules 
from google import genai
from concurrent.futures import ThreadPoolExecutor, as_completed
import gc

# --- DATABASE CONNECTION ---
# Load the environment variables from your local .env file
load_dotenv()

# Securely pull the connection string into your application engine memory
NEON_URL = os.getenv("DATABASE_URL")
if not NEON_URL:
    raise ValueError("❌ CRITICAL ERROR: DATABASE_URL is missing from your environment variables!")

# 1. Initialize the new Client
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# 2. Wrapper to keep old model.generate_content() logic working seamlessly
class ModelWrapper:
    def __init__(self, model_name):
        self.model_name = model_name
        
    def generate_content(self, contents, **kwargs):
        if not client:
            raise ValueError("Gemini API Key is missing!")
        
        # Map old 'generation_config' to new 'config' for the new SDK
        if 'generation_config' in kwargs:
            kwargs['config'] = kwargs.pop('generation_config')
            
        return client.models.generate_content(
            model=self.model_name,
            contents=contents,
            **kwargs
        )

def get_model():
    try:
        # Fallback to standard 2.0 or 1.5 flash models for stability
        return ModelWrapper('gemini-2.5-flash-lite')
    except:
        return ModelWrapper('gemini-2.5-flash')

def get_knowledge_base():
    path = os.path.join("knowledge_base", "Aarvi_Encon", "*.json")
    knowledge = []
    for file_path in glob.glob(path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                knowledge.append(json.load(f))
        except:
            pass
    return json.dumps(knowledge)

def clean_price_to_float(price_str):
    """Converts price strings like '25 Lakh', '2,500,000', or '25,00,000' to a float."""
    if not price_str or price_str == "Not Specified":
        return 0.0
    
    # Remove commas and convert to lower
    text = str(price_str).lower().replace(',', '')
    
    # Simple regex to get the number
    num = re.findall(r"[-+]?\d*\.\d+|\d+", text)
    if not num:
        return 0.0
    val = float(num[0])
    
    # Handle multipliers
    if 'lakh' in text or 'lac' in text:
        val *= 100000
    elif 'crore' in text or 'cr' in text:
        val *= 10000000
        
    return val

def format_for_ui(value):
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

def normalize_client_name(extracted_name):
    """Translates full company names into core acronyms to group joint ventures."""
    if not extracted_name or extracted_name == "Not Specified":
        return extracted_name
        
    name = str(extracted_name).upper().strip()
    
    # Existing rules
    if "HINDUSTAN PETROLEUM" in name:
        return "HPCL"
    if "INDIAN OIL" in name:
        return "IOCL"
    if "OIL & NATURAL GAS" in name or "OIL AND NATURAL GAS" in name:
        return "ONGC"
    if "BHARAT PETROLEUM" in name:
        return "BPCL"
        
    # --- SIMPLIFIED DIRECT GAIL RULE ---
    if "GAIL" in name or "GAS AUTHORITY" in name:
        return "GAIL"
        
    return extracted_name.strip()

def fetch_client_intelligence(client_name: str):
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
        
        cur.execute("""
            SELECT tender_status, competitor_list, comments 
            FROM tenders 
            WHERE name_of_client ILIKE %s
        """, (f"%{search_name}%",))
        
        records = cur.fetchall()
        cur.close()
        conn.close()
        
        if not records:
            return {"kpi": "No Past Record", "competitors": "No historical competitor data found for this client."}
            
        # 2. Calculate Win/Loss KPIs
        won_bids = sum(1 for r in records if r['tender_status'] == 'Tender Won')
        lost_bids = sum(1 for r in records if r['tender_status'] == 'Tender Lost')
        quoted_bids = sum(1 for r in records if r['tender_status'] in ['Tender Quoted', 'Quoted'])
        cancelled_bids = sum(1 for r in records if r['tender_status'] in ['Cancelled', 'Tender Cancelled'])
        
        total_bids = won_bids + lost_bids + quoted_bids + cancelled_bids
        win_rate = round((won_bids / total_bids) * 100) if total_bids > 0 else 0
        loss_rate = 100 - win_rate
        
        kpi_text = f"[ ❌ {loss_rate}% | 🎉 {win_rate}% ]\nTotal Bids: {total_bids} (Won: {won_bids} | Lost: {lost_bids} | Quoted: {quoted_bids} | Cancelled: {cancelled_bids})"
        
        # 3. Extract Top 3 Competitor Threats AND Qualitative Comments
        threats = {}
        raw_comments = []
        lost_records_with_data = 0
        
        for row in records:
            if row['tender_status'] == 'Tender Lost':
                has_extracted_something = False
                
                competitors = row.get('competitor_list')
                if competitors and isinstance(competitors, str) and competitors.strip() not in ['[]', '']:
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

                comments = row.get('comments')
                if comments and str(comments).strip().lower() not in ['nan', 'none', '']:
                    raw_comments.append(str(comments).strip())
                    has_extracted_something = True

                if has_extracted_something:
                    lost_records_with_data += 1
                    
        # 4. Format the Competitor UI Text Block
        if lost_records_with_data == 0:
            comp_text = f"We have {total_bids} bids on record, but no competitor history or loss comments were found for these past losses."
        else:
            comp_text = f"Our backend records indicate we have logged qualitative data on {lost_records_with_data} lost tenders for this operator.\n\n"
            
            if threats:
                comp_text += "**Quantitative Competitor Threats:**\n"
                sorted_threats = sorted(threats.items(), key=lambda x: (x[1]['wins'], x[1]['encounters']), reverse=True)
                medals = ["🥇 1.", "🥈 2.", "🥉 3."]
                
                for i, (comp_name, data) in enumerate(sorted_threats[:3]):
                    avg_gap = round(sum(data["gaps"]) / len(data["gaps"]), 2) if data["gaps"] else 0.0
                    medal = medals[i] if i < 3 else f"• {i+1}."
                    
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
        print(f"Database background intelligence lookup skipped: {db_err}")
        return {"kpi": "Database Offline", "competitors": "Could not retrieve competitor history."}

def ensure_ui_schema(ai_data: dict, logic_data: dict, intel_data: dict, error_msg: str = None) -> dict:
    template = {
        "tender_no": "Not Specified", "client_name": "Not Specified", "description": "Not Specified", 
        "due_date": "Not Specified", "tender_open_price": "Not Specified", "emd": "Not Specified",
        "financial_qualification": "Not Specified", "technical_qualification": "Not Specified",
        "mandatory_compliance": "Not Specified", "scope_of_work": "Not Specified",
        "manpower_count": "Not Specified", "manpower_qual": "Not Specified",
        "shift_duty": "Not Specified", "payment_terms": "Not Specified",
        "penalty_terms": "Not Specified", "similar_work": "Not Specified",
        "bid_decision": "PENDING", "pq_status": "PENDING", 
        "win_probability": "PENDING", "profit_forecast": "PENDING", 
        "win_loss_kpi": "Not Specified", "historical_competitors": "Not Specified",
        "strategic_advice": "Not Specified", "compliance_status": "Not Specified", 
        "compliance_reason": "Not Specified"
    }
    
    if error_msg:
        template["strategic_advice"] = f"Error: {error_msg}"
        return template

    for key in ai_data:
        if key in template:
            template[key] = format_for_ui(ai_data[key])
            
    for key in logic_data:
        if key in template:
            template[key] = str(logic_data[key])

    template["win_loss_kpi"] = intel_data.get("kpi", "No Past Record")
    template["historical_competitors"] = intel_data.get("competitors", "No Data")

    return template


# ==============================================================================
# 🚀 PARALLEL AI WORKER (For processing chunks concurrently)
# ==============================================================================
def process_chunk_with_ai(chunk_text: str, chunk_idx: int, total_chunks: int):
    """Worker function to process a single document chunk concurrently using Gemini Flash."""
    print(f"⚡ [PARALLEL AI] Sending Chunk {chunk_idx}/{total_chunks} to Gemini...", flush=True)
    model = get_model()
    
    prompt = f"""
    ROLE: Expert Tender Data Extractor.
    TASK: Scan the following PARTIAL segment of a massive Tender Document and map findings to the JSON schema.
    If a detail is missing from this specific segment, output "Not Specified" for that field. Do not invent data.

    CRITICAL INSTRUCTIONS:
    1. Use '•' (bullet points) and newlines for arrays.
    2. description: Provide a summary of the project based ONLY on this chunk.
    3. manpower_count: Output a clean bulleted list using escaped newlines ('\\n').

    JSON SCHEMA (Output ONLY valid JSON):
    {{
      "tender_no": "Find the Tender/RFQ number",
      "client_name": "Extract Client Name",
      "due_date": "Extract the exact submission deadline",
      "tender_open_price": "Extract total tender value",
      "emd": "Extract the EMD amount or percentage",
      "financial_qualification": "Extract financial conditions (Turnover, Net Worth, PBG)",
      "technical_qualification": "Extract Experience and Competency requirements",
      "mandatory_compliance": "Extract PF/ESI/Statutory rules",
      "scope_of_work": "Extract major deliverables and tasks",
      "manpower_count": "Map an explicit bulleted list breakdown of every required role",
      "manpower_qual": "Extract educational requirements and experience criteria",
      "shift_duty": "Extract shift/working hours",
      "payment_terms": "Extract payment timeline",
      "penalty_terms": "Extract LD clauses",
      "similar_work": "Extract similar work required"
    }}

    TENDER TEXT SEGMENT: {chunk_text}
    """
    
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        
        in_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0) if hasattr(response, 'usage_metadata') and response.usage_metadata else 0
        out_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0) if hasattr(response, 'usage_metadata') and response.usage_metadata else 0
        
        try:
            ai_data = json.loads(response.text)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', response.text, re.DOTALL)
            ai_data = json.loads(match.group(0)) if match else {}
            
        return chunk_idx, ai_data, in_tokens, out_tokens
        
    except Exception as e:
        print(f"⚠️ Warning: Chunk {chunk_idx} processing failed: {e}", flush=True)
        return chunk_idx, {}, 0, 0


# ==============================================================================
# 🚀 MAIN GENERATOR (Auto-Detects String & Processes Unlimited Size)
# ==============================================================================
def generate_tender_summary(tender_text: str = None):
    """
    Safely processes massive extracted text strings in memory.
    Uses Map-Reduce to parse 20,000+ page strings perfectly.
    """
    total_input_tokens = 0
    total_output_tokens = 0

    if not tender_text:
        return {
            "ui_data": ensure_ui_schema({}, {}, {}, "Empty tender document stream provided."),
            "input_tokens": 0, "output_tokens": 0, "tender_no": "N/A"
        }

    # If by chance it is passed a file path instead of a string, read it.
    if len(tender_text) < 1000:
        try:
            if os.path.exists(tender_text):
                with open(tender_text, "r", encoding="utf-8") as f:
                    tender_text = f.read()
        except Exception:
            pass

    if len(tender_text.strip()) == 0:
        return {
            "ui_data": ensure_ui_schema({}, {}, {}, "Empty tender document stream provided."),
            "input_tokens": 0, "output_tokens": 0, "tender_no": "N/A"
        }

    model = get_model()
    kb_data = get_knowledge_base()

    # Slice the massive string into safe 1,000,000 character chunks
    CHUNK_SIZE = 1000000 
    chunks = [tender_text[i:i + CHUNK_SIZE] for i in range(0, len(tender_text), CHUNK_SIZE)]

    total_chunks = len(chunks)
    partial_extractions = [None] * total_chunks

    print(f"🚀 Running Parallel Map Pass across {total_chunks} AI chunk(s)...", flush=True)

    # --- PHASE 1: PARALLEL MAP (Send chapters to Gemini concurrently) ---
    with ThreadPoolExecutor(max_workers=min(4, total_chunks if total_chunks > 0 else 1)) as executor:
        futures = [executor.submit(process_chunk_with_ai, chunks[i], i + 1, total_chunks) for i in range(total_chunks)]
        for future in as_completed(futures):
            idx, result_json, in_tok, out_tok = future.result()
            # idx is 1-based, list is 0-based
            partial_extractions[idx - 1] = result_json
            total_input_tokens += in_tok
            total_output_tokens += out_tok

    # Filter out empty dicts from failed chunks
    valid_extractions = [ext for ext in partial_extractions if ext]

    # --- PHASE 2: REDUCE (Merge everything into one master JSON) ---
    if len(valid_extractions) == 0:
        final_ai_data = {}
    elif len(valid_extractions) == 1:
        final_ai_data = valid_extractions[0]
    else:
        print(f"🧩 Merging {len(valid_extractions)} chunk extractions into one master summary...", flush=True)
        merge_prompt = f"""
        ROLE: Senior Data Aggregator.
        TASK: You are given an array of JSON objects extracted from different chapters of the same massive document.
        Merge them into ONE final, comprehensive JSON object. 
        - If multiple chunks found the same "tender_no" or "client_name", keep the clearest one.
        - Combine all bullet points for arrays like "scope_of_work", "financial_qualification", and "manpower_count" into a single exhaustive list. Remove duplicates.
        - NEVER output "Not Specified" if the valid data exists in ANY of the chunks.

        JSON SCHEMA REQUIRED (Output ONLY valid JSON):
        {{
          "tender_no": "Not Specified", "client_name": "Not Specified", "due_date": "Not Specified", "tender_open_price": "Not Specified", "emd": "Not Specified",
          "financial_qualification": "Not Specified", "technical_qualification": "Not Specified", "mandatory_compliance": "Not Specified",
          "scope_of_work": "Not Specified", "manpower_count": "Not Specified", "manpower_qual": "Not Specified", "shift_duty": "Not Specified",
          "payment_terms": "Not Specified", "penalty_terms": "Not Specified", "similar_work": "Not Specified"
        }}

        PARTIAL EXTRACTIONS TO MERGE: {json.dumps(valid_extractions)}
        """
        try:
            merge_response = model.generate_content(merge_prompt, generation_config={"response_mime_type": "application/json"})
            if hasattr(merge_response, 'usage_metadata') and merge_response.usage_metadata:
                total_input_tokens += getattr(merge_response.usage_metadata, 'prompt_token_count', 0)
                total_output_tokens += getattr(merge_response.usage_metadata, 'candidates_token_count', 0)
            
            try:
                final_ai_data = json.loads(merge_response.text)
            except json.JSONDecodeError:
                match = re.search(r'\{.*\}', merge_response.text, re.DOTALL)
                final_ai_data = json.loads(match.group(0)) if match else {}
        except Exception as e:
            print(f"⚠️ Warning: Merge failed. Using first chunk as fallback.", flush=True)
            final_ai_data = valid_extractions[0] if valid_extractions else {}

    # --- PHASE 3: DATABASE INTELLIGENCE & LOGIC RULES ---
    sample_text = tender_text[:50000]
    
    logic_decisions = evaluate_tender_rules(final_ai_data, kb_data, sample_text)
    extracted_client = final_ai_data.get("client_name", "Not Specified")
    historical_intel = fetch_client_intelligence(extracted_client)

    if historical_intel.get("kpi") != "No Past Record" and "No historical competitor data" not in historical_intel.get("competitors", ""):
        strategy_prompt = f"""
        ROLE: Senior Bidding Strategist & Consultant.
        CLIENT: {extracted_client}
        RAW HISTORICAL LOSS DATA (Competitors & Pricing):
        {historical_intel.get('competitors')}
        
        TASK: Analyze the raw competitor data above and return your response EXACTLY in this JSON format.
        {{
            "top_3_competitors": "A clean, bulleted list of the Top 3 most dangerous recurring competitors. State explicitly: 1) Encounters, 2) L1 wins, 3) Specific loss reason.",
            "strategic_advice": "Write a highly analytical, 5-sentence strategic recommendation to management to beat them."
        }}
        """
        try:
            ai_strat_obj = model.generate_content(strategy_prompt, generation_config={"response_mime_type": "application/json"})
            if hasattr(ai_strat_obj, 'usage_metadata') and ai_strat_obj.usage_metadata:
                total_input_tokens += getattr(ai_strat_obj.usage_metadata, 'prompt_token_count', 0)
                total_output_tokens += getattr(ai_strat_obj.usage_metadata, 'candidates_token_count', 0)
            
            try:
                strategy_json = json.loads(ai_strat_obj.text)
            except json.JSONDecodeError:
                match = re.search(r'\{.*\}', ai_strat_obj.text, re.DOTALL)
                strategy_json = json.loads(match.group(0)) if match else {}

            historical_intel["competitors"] = strategy_json.get("top_3_competitors", "Could not extract top competitors.")
            ai_advice = strategy_json.get("strategic_advice", "Strategy generation failed.")
            base_advice = logic_decisions.get("strategic_advice", "")
            
            if base_advice and base_advice != "Not Specified":
                logic_decisions["strategic_advice"] = f"{base_advice}\n\n**🤖 Senior Consultant Strategy:**\n{ai_advice}"
            else:
                logic_decisions["strategic_advice"] = f"**🤖 Senior Consultant Strategy:**\n{ai_advice}"
        except Exception as e:
            print(f"Failed to generate competitive strategy: {e}", flush=True)

    # Reclaim RAM explicitly
    del chunks
    gc.collect()

    final_ui_data = ensure_ui_schema(final_ai_data, logic_decisions, historical_intel)
    
    return {
        "ui_data": final_ui_data,
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "tender_no": final_ai_data.get("tender_no", "N/A")
    }


def chat_with_tender(query: str, context: dict, full_text: str = ""):
    model = get_model()
    prompt = f"Context: {json.dumps(context)}\nFull Doc: {full_text[:3500000]}\nQuery: {query}\n\nStrictly answer based on Full Doc using Markdown bullets."
    
    response = model.generate_content(prompt)
    
    in_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0) if hasattr(response, 'usage_metadata') and response.usage_metadata else 0
    out_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0) if hasattr(response, 'usage_metadata') and response.usage_metadata else 0
    
    return {
        "reply": response.text,
        "input_tokens": in_tokens,
        "output_tokens": out_tokens
    }

def generate_chat_title(first_message: str) -> str:
    if not first_message:
        return "New Analysis"
        
    model = get_model()
    prompt = f"""
    Generate a short, concise, 3 to 4 word title for a business chat session based on this first message or document snippet:
    "{first_message[:1000]}"
    
    Rules:
    - Output ONLY the title.
    - Do not use quotes, punctuation, or conversational filler.
    - Focus on the Client Name or primary subject.
    """
    try:
        response = model.generate_content(prompt)
        title = response.text.strip().replace('"', '').replace('\n', '')
        if len(title) > 35:
            title = title[:32] + "..."
        return title
    except Exception as e:
        return "New Analysis"
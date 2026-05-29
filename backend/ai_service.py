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
    # If the text contains "GAIL" anywhere (or the old "GAS AUTHORITY"), it belongs to GAIL
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
        
        # 1. Added 'comments' to the SQL SELECT statement
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
        
        # 3. Extract Top 3 Competitor Threats AND Qualitative Comments from lost tenders
        threats = {}
        raw_comments = []
        lost_records_with_data = 0
        
        for row in records:
            if row['tender_status'] == 'Tender Lost':
                has_extracted_something = False
                
                # --- A: Try to extract structured Competitor Data ---
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
                        # If it's plain text instead of JSON, treat it as a comment!
                        raw_comments.append(f"Competitor Note: {competitors.strip()}")
                        has_extracted_something = True

                # --- B: Extract unstructured qualitative comments ---
                comments = row.get('comments')
                if comments and str(comments).strip().lower() not in ['nan', 'none', '']:
                    raw_comments.append(str(comments).strip())
                    has_extracted_something = True

                if has_extracted_something:
                    lost_records_with_data += 1
                    
        # 4. Format the Competitor UI Text Block & Strategy Feed
        if lost_records_with_data == 0:
            comp_text = f"We have {total_bids} bids on record, but no competitor history or loss comments were found for these past losses."
        else:
            comp_text = f"Our backend records indicate we have logged qualitative data on {lost_records_with_data} lost tenders for this operator.\n\n"
            
            # Add Structured Threats (if any exist)
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

            # Add Unstructured Comments (if any exist)
            if raw_comments:
                comp_text += "**Qualitative Loss Reasons & Background:**\n"
                for comment in set(raw_comments): # set() removes duplicates
                    comp_text += f"• {comment}\n"
                    
        return {"kpi": kpi_text, "competitors": comp_text.strip()}
        
    except Exception as db_err:
        print(f"Database background intelligence lookup skipped: {db_err}")
        return {"kpi": "Database Offline", "competitors": "Could not retrieve competitor history."}

def ensure_ui_schema(ai_data: dict, logic_data: dict, intel_data: dict, error_msg: str = None) -> dict:
    template = {
        "tender_no": "Not Specified", "client_name": "Not Specified", "description": "Not Specified", 
        "tender_open_price": "Not Specified", "emd": "Not Specified",
        "financial_qualification": "Not Specified", "technical_qualification": "Not Specified",
        "mandatory_compliance": "Not Specified", "scope_of_work": "Not Specified",
        "manpower_count": "Not Specified", "manpower_qual": "Not Specified",
        "shift_duty": "Not Specified", "payment_terms": "Not Specified",
        "penalty_terms": "Not Specified", "similar_work": "Not Specified",
        "bid_decision": "PENDING", "pq_status": "PENDING", 
        "win_probability": "PENDING", "profit_forecast": "PENDING", 
        
        # --- NEW INTEL FIELDS FOR UI LAYOUT ---
        "win_loss_kpi": "Not Specified",
        "historical_competitors": "Not Specified",
        
        "strategic_advice": "Not Specified", "compliance_status": "Not Specified", 
        "compliance_reason": "Not Specified"
    }
    
    if error_msg:
        template["strategic_advice"] = f"Error: {error_msg}"
        return template

    # Merge AI Extraction Data
    for key in ai_data:
        if key in template:
            template[key] = format_for_ui(ai_data[key])
            
    # Merge Logic Evaluation Data (Overrides AI)
    for key in logic_data:
        if key in template:
            template[key] = str(logic_data[key])

    # Inject the database intelligence directly into the new layout fields
    template["win_loss_kpi"] = intel_data.get("kpi", "No Past Record")
    template["historical_competitors"] = intel_data.get("competitors", "No Data")

    return template

def generate_tender_summary(tender_text: str = None):
    # ✅ NEW: Initialize token counters for tracking
    total_input_tokens = 0
    total_output_tokens = 0

    if not tender_text:
        return {
            "ui_data": ensure_ui_schema({}, {}, {}, "Empty tender document provided."),
            "input_tokens": 0, "output_tokens": 0, "tender_no": "N/A"
        }

    model = get_model()
    kb_data = get_knowledge_base()

    prompt = f"""
    ROLE: Expert Tender Data Extractor and Senior Strategic Bid Consultant.
    PACING DIRECTION: Treat this analysis as a high-value corporate audit. Take all the time needed to thoroughly evaluate details. Do not skim or skip lines. Depth, granularity, and strategic sharpness are mandatory.
    
    KNOWLEDGE BASE (Past Projects & Competitor Records): {kb_data}

    TASK: Scan the TENDER TEXT and map findings to the JSON schema below.
    
    CRITICAL INSTRUCTIONS (DO NOT OMIT ANY STEP):
    1. Use '•' (bullet points) and newlines for: financial_qualification, technical_qualification, mandatory_compliance, and scope_of_work.
    2. description: Provide a 3-bullet point summary of the overall project.
    3. financial_qualification: COMBINE all explicit "Turnover", "Net Worth", "Security Deposit", and "PBG" conditions. Use bullets for each requirement.
    4. technical_qualification: COMBINE all "Similar Work" and "Experience" requirements into a bulleted list.
    5. If exact keywords are not found, identify equivalent financial or value-related statements and extract them. Do NOT return empty if partial financial information exists.
    6. manpower_count:Always format this field as a clean, human-readable bulleted list. NEVER output raw Python dictionaries, JSON data blobs, or stringified code blocks (e.g., do NOT output things like "{{'total_proposed_ta': 13...}}"). State the total grand headcount clearly on the first line, followed by a clean bulleted location-wise or role-wise volume breakdown using escaped newlines ('\\n') for structural clarity
    7. COMPETITIVE HISTORICAL AUDIT: Cross-examine the current TENDER TEXT against the past project records and competitor tendencies in the KNOWLEDGE BASE. Identify structural traps, eligibility friction points, and competitor pricing baselines.
    8. NO TRUNCATION RULE: Do not truncate summaries or compress critical technical clauses to close the JSON schema quickly. Build complete, exhaustive data arrays for all fields.
    JSON SCHEMA (Output ONLY valid JSON):
    {{
      "tender_no": "Find the Tender/RFQ number",
      "client_name": "Extract Client Name",
      "tender_open_price": "Extract total tender value. Look for terms like 'Total Financial Limit', 'Estimated Value', 'Contract Value', 'SOR Value', or any total cost mentioned. If found, return numeric value. If not explicitly labeled, infer from context.",
      "emd": "Extract the EMD amount or percentage",
      "financial_qualification": "Extract Bulleted list of ANY financial conditions including Turnover, Net Worth, PBG, Security Deposit, Tender Value, or pricing constraints. If Turnover/Net Worth are missing, still extract PBG/SD and mark as 'No explicit turnover requirement'.",
      "technical_qualification": "Bulleted list of Experience and Competency requirements",
      "mandatory_compliance": "Bulleted list of PF/ESI/Statutory rules",
      "scope_of_work": "Bulleted list of major deliverables and tasks",
      "manpower_count": "State total headcount summary on line 1, then map an explicit bulleted list breakdown of every required role or location and its corresponding staffing quantity. Separate lines using escaped newlines ('\\n').",
      "manpower_qual": "Bulleted list of exact educational requirements, age limits, vehicle requirements, and experience criteria required per profile.",
      "shift_duty": "Extract shift/working hours",
      "payment_terms": "Extract payment timeline",
      "penalty_terms": "Extract LD clauses",
      "similar_work": "Match with Knowledge Base"
    }}

    TENDER TEXT: {tender_text}
    """
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        
        # ✅ NEW: Capture Pass 1 Token Footprint
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            total_input_tokens += getattr(response.usage_metadata, 'prompt_token_count', 0)
            total_output_tokens += getattr(response.usage_metadata, 'candidates_token_count', 0)
        
        try:
            ai_extracted_data = json.loads(response.text)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', response.text, re.DOTALL)
            ai_extracted_data = json.loads(match.group(0)) if match else {}
        
        # Pass to logic.py for basic rule checks
        logic_decisions = evaluate_tender_rules(ai_extracted_data, kb_data, tender_text)

        # Look up Win/Loss Gauge Data & Top 3 Competitors from the Database!
        extracted_client = ai_extracted_data.get("client_name", "Not Specified")
        historical_intel = fetch_client_intelligence(extracted_client)

        # --- NEW: AI COMPETITIVE STRATEGY GENERATION (PASS 2) ---
        if historical_intel.get("kpi") != "No Past Record" and "No historical competitor data" not in historical_intel.get("competitors", ""):
            strategy_prompt = f"""
            ROLE: Senior Bidding Strategist & Consultant for Aarvi Encon.
            CLIENT: {extracted_client}
            
            RAW HISTORICAL LOSS DATA (Competitors & Pricing):
            {historical_intel.get('competitors')}
            
            TASK: Analyze the raw competitor data above and return your response EXACTLY in this JSON format.
            
            {{
                "top_3_competitors": "A clean, bulleted list of the Top 3 most dangerous recurring competitors. For EACH competitor, you MUST explicitly state: 1) How many times we encountered them, 2) How many times they took the L1 rank, and 3) The specific reason we lost (e.g., pricing gaps, service charges).",
                "strategic_advice": "Act as a Senior Consultant. Look at ALL the competitors and pricing trends in the raw data. Write a highly analytical, 5-sentence strategic recommendation. Tell our management team exactly what pricing, margins, or technical strategy we must adopt to beat them on this new bid."
            }}
            """
            try:
                # Ask Gemini to parse the messy text, find the Top 3, AND write the strategy
                ai_strat_obj = model.generate_content(strategy_prompt, generation_config={"response_mime_type": "application/json"})
                ai_strategy_response = ai_strat_obj.text
                
                # ✅ NEW: Capture Pass 2 Token Footprint
                if hasattr(ai_strat_obj, 'usage_metadata') and ai_strat_obj.usage_metadata:
                    total_input_tokens += getattr(ai_strat_obj.usage_metadata, 'prompt_token_count', 0)
                    total_output_tokens += getattr(ai_strat_obj.usage_metadata, 'candidates_token_count', 0)
                
                try:
                    strategy_json = json.loads(ai_strategy_response)
                except json.JSONDecodeError:
                    match = re.search(r'\{.*\}', ai_strategy_response, re.DOTALL)
                    strategy_json = json.loads(match.group(0)) if match else {}

                # 1. OVERWRITE the messy wall of text with the clean Top 3 AI summary
                historical_intel["competitors"] = strategy_json.get("top_3_competitors", "Could not extract top competitors.")
                
                # 2. Extract the Senior Consultant Advice
                ai_advice = strategy_json.get("strategic_advice", "Strategy generation failed.")
                
                base_advice = logic_decisions.get("strategic_advice", "")
                if base_advice and base_advice != "Not Specified":
                    logic_decisions["strategic_advice"] = f"{base_advice}\n\n**🤖 Senior Consultant Strategy:**\n{ai_advice}"
                else:
                    logic_decisions["strategic_advice"] = f"**🤖 Senior Consultant Strategy:**\n{ai_advice}"
                    
            except Exception as e:
                print(f"Failed to generate competitive strategy: {e}")
                pass

        # ✅ NEW: Package everything together including token counts for main.py to log
        final_ui_data = ensure_ui_schema(ai_extracted_data, logic_decisions, historical_intel)
        return {
            "ui_data": final_ui_data,
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "tender_no": ai_extracted_data.get("tender_no", "N/A")
        }
        
    except Exception as e:
        return {
            "ui_data": ensure_ui_schema({}, {}, {}, error_msg=str(e)),
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "tender_no": "N/A"
        }

def chat_with_tender(query: str, context: dict, full_text: str = ""):
    model = get_model()
    prompt = f"Context: {json.dumps(context)}\nFull Doc: {full_text[:50000]}\nQuery: {query}\n\nStrictly answer based on Full Doc using Markdown bullets."
    
    response = model.generate_content(prompt)
    
    # ✅ NEW: Capture chat tokens
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
    - Focus on the Client Name or primary subject (e.g., "ONGC Maintenance Tender" or "HPCL Manpower Bid").
    """
    try:
        response = model.generate_content(prompt)
        title = response.text.strip().replace('"', '').replace('\n', '')
        
        if len(title) > 35:
            title = title[:32] + "..."
            
        return title
    except Exception as e:
        print(f"Error generating chat title: {e}")
        return "New Analysis"
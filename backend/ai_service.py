import json
import os
import glob
import re
import psycopg2
from psycopg2.extras import RealDictCursor
from config import GEMINI_API_KEY
from logic import evaluate_tender_rules 
from google import genai

# --- DATABASE CONNECTION ---
NEON_URL = "postgresql://neondb_owner:npg_djW0Dm5HAPOa@ep-twilight-block-apopzllz-pooler.c-7.us-east-1.aws.neon.tech/neondb?sslmode=require"

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
    
    # If the AI reads "Hindustan Petroleum", convert it to "HPCL"
    # This ensures we catch HPCL Mittal, HPCL Rajasthan, etc., but IGNORE Hindustan Aeronautics!
    if "HINDUSTAN PETROLEUM" in name:
        return "HPCL"
        
    if "INDIAN OIL" in name:
        return "IOCL"
    if "OIL & NATURAL GAS" in name or "OIL AND NATURAL GAS" in name:
        return "ONGC"
    if "BHARAT PETROLEUM" in name:
        return "BPCL"
        
    return extracted_name.strip()

def fetch_client_intelligence(client_name: str):
    """
    Connects to Neon to extract Win/Loss ratios and Competitor Threats.
    Returns a dictionary with formatted strings for the UI.
    """
    # 1. Translate long names (like Hindustan Petroleum) into the base acronym (HPCL)
    search_name = normalize_client_name(client_name)
    
    if not search_name or search_name == "Not Specified":
        return {"kpi": "No Past Record", "competitors": "No historical competitor data found for this client."}
        
    try:
        conn = psycopg2.connect(NEON_URL, cursor_factory=RealDictCursor)
        cur = conn.cursor()
        
        # 2. Fetch all historical tenders for this client to calculate win/loss and threats
        # Wildcard search ILIKE %HPCL% catches HPCL, HPCL Mittal, HPCL Rajasthan, etc.
        cur.execute("""
            SELECT tender_status, competitor_list 
            FROM tenders 
            WHERE name_of_client ILIKE %s
        """, (f"%{search_name}%",))
        
        records = cur.fetchall()
        cur.close()
        conn.close()
        
        if not records:
            return {"kpi": "No Past Record", "competitors": "No historical competitor data found for this client."}
            
        # 1. Calculate Win/Loss KPIs
        # 1. Calculate explicit statuses for the new Total Bids logic
        won_bids = sum(1 for r in records if r['tender_status'] == 'Tender Won')
        lost_bids = sum(1 for r in records if r['tender_status'] == 'Tender Lost')
        quoted_bids = sum(1 for r in records if r['tender_status'] in ['Tender Quoted', 'Quoted'])
        cancelled_bids = sum(1 for r in records if r['tender_status'] in ['Cancelled', 'Tender Cancelled'])
        
        # Calculate new explicit total
        total_bids = won_bids + lost_bids + quoted_bids + cancelled_bids
        
        win_rate = round((won_bids / total_bids) * 100) if total_bids > 0 else 0
        loss_rate = 100 - win_rate
        
        kpi_text = f"[ ❌ {loss_rate}% | 🎉 {win_rate}% ]\nTotal Bids: {total_bids} (Won: {won_bids} | Lost: {lost_bids} | Quoted: {quoted_bids} | Cancelled: {cancelled_bids})"
        # 2. Extract Top 3 Competitor Threats from the lost tenders
        threats = {}
        lost_records_with_data = 0
        
        for row in records:
            if row['tender_status'] == 'Tender Lost' and row['competitor_list']:
                competitors = row['competitor_list']
                if isinstance(competitors, str) and competitors != '[]':
                    try:
                        competitors = json.loads(competitors)
                    except:
                        continue
                
                if isinstance(competitors, list) and len(competitors) > 0:
                    lost_records_with_data += 1
                    for comp in competitors:
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
                                
        # Format the Competitor UI Text Block
        if lost_records_with_data == 0 or not threats:
            comp_text = f"We have {total_bids} bids on record, but no L1-L5 leaderboard history was mapped for these past losses."
        else:
            comp_text = f"Our backend records indicate we have competed on {lost_records_with_data} logged losing tenders for this operator. The following persistent market threats have been discovered:\n\n"
            
            # Sort threats by L1 wins, then by encounters
            sorted_threats = sorted(threats.items(), key=lambda x: (x[1]['wins'], x[1]['encounters']), reverse=True)
            medals = ["🥇 1.", "🥈 2.", "🥉 3."]
            
            for i, (comp_name, data) in enumerate(sorted_threats[:3]):
                avg_gap = round(sum(data["gaps"]) / len(data["gaps"]), 2) if data["gaps"] else 0.0
                medal = medals[i] if i < 3 else f"• {i+1}."
                
                comp_text += f"• {medal} **{comp_name}**\n"
                comp_text += f"  - Encountered: {data['encounters']} times | Has taken L1 Rank: {data['wins']} times\n"
                if avg_gap > 0:
                    comp_text += f"  - Average Margin Disadvantage: We typically lose to them by a gap of {avg_gap}%\n\n"
                else:
                    comp_text += "  - Average Margin Disadvantage: Baseline benchmark maker (0.00% variance)\n\n"
                    
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
    if not tender_text:
        return ensure_ui_schema({}, {}, {}, "Empty tender document provided.")

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
    6. manpower_count: If a direct grand total is not explicitly stated, extract the detailed breakdown of individual roles and their required quantities (e.g., '• Level 1 Engineer: 5 \\n• Safety Officer: 2'). Do NOT return 'Not Specified' if partial role breakdowns exist.
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
      "manpower_count": "Extract total headcount. If total is missing, extract a bulleted list of specific roles and their required quantities.",
      "manpower_qual": "Extract educational requirements",
      "shift_duty": "Extract shift/working hours",
      "payment_terms": "Extract payment timeline",
      "penalty_terms": "Extract LD clauses",
      "similar_work": "Match with Knowledge Base"
    }}

    TENDER TEXT: {tender_text}
    """
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        
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
        # Only run this if we actually have competitor history to analyze
        if historical_intel.get("kpi") != "No Past Record" and "No historical competitor data" not in historical_intel.get("competitors", ""):
            strategy_prompt = f"""
            ROLE: Chief Bidding Strategist for Aarvi Encon.
            CLIENT: {extracted_client}
            PROJECT SCOPE: {ai_extracted_data.get('scope_of_work', 'Not specified')}
            
            OUR HISTORICAL WIN/LOSS KPI WITH THIS CLIENT:
            {historical_intel.get('kpi')}
            
            THE COMPETITOR THREATS WE LOST TO PREVIOUSLY:
            {historical_intel.get('competitors')}
            
            TASK: Based on the historical database intelligence above, write a highly analytical, 5-sentence strategic recommendation for our management team. 
            Hypothesize *why* we lost to these specific competitors in the past (e.g., margin compression, local mobilization advantage, acting as the L1 baseline) and tell our team exactly what pricing or technical strategy we must adopt to beat them on this new bid. Be authoritative, actionable, and concise. Do not use conversational filler.
            """
            try:
                # Ask Gemini to write the tactical strategy
                ai_strategy = model.generate_content(strategy_prompt).text.strip()
                
                # Combine the basic compliance advice from logic.py with this new AI brain-power insight
                base_advice = logic_decisions.get("strategic_advice", "")
                if base_advice and base_advice != "Not Specified":
                    logic_decisions["strategic_advice"] = f"{base_advice}\n\n**🤖 AI Competitive Strategy Assessment:**\n{ai_strategy}"
                else:
                    logic_decisions["strategic_advice"] = f"**🤖 AI Competitive Strategy Assessment:**\n{ai_strategy}"
            except Exception as e:
                print(f"Failed to generate competitive strategy: {e}")
                pass

        # Pass all three data sources (AI + Logic + DB) to the UI formatter
        return ensure_ui_schema(ai_extracted_data, logic_decisions, historical_intel)
        
    except Exception as e:
        return ensure_ui_schema({}, {}, {}, error_msg=str(e))

def chat_with_tender(query: str, context: dict, full_text: str = ""):
    model = get_model()
    prompt = f"Context: {json.dumps(context)}\nFull Doc: {full_text[:50000]}\nQuery: {query}\n\nStrictly answer based on Full Doc using Markdown bullets."
    return model.generate_content(prompt).text  

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
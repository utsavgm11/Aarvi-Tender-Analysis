import json
import os
import glob
import re
from config import GEMINI_API_KEY
from logic import evaluate_tender_rules 
from google import genai

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

def ensure_ui_schema(ai_data: dict, logic_data: dict, error_msg: str = None) -> dict:
    # --- UPDATED: Replaced BQC/PQC with Financial and Technical Quals ---
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

    return template

def generate_tender_summary(tender_text: str = None):
    if not tender_text:
        return ensure_ui_schema({}, {}, "Empty tender document provided.")

    model = get_model()
    kb_data = get_knowledge_base()

    # --- UPDATED PROMPT: Combined Qualification Extraction ---
    # --- UPDATED PROMPT: Requesting Bullet Points for Specific Fields ---
    prompt = f"""
    ROLE: Expert Tender Data Extractor.
    KNOWLEDGE BASE (Past Projects): {kb_data}

    TASK: Scan the TENDER TEXT and map findings to the JSON schema below.
    
    CRITICAL INSTRUCTIONS:
    1. Use '•' (bullet points) and newlines for: financial_qualification, technical_qualification, mandatory_compliance, and scope_of_work.
    2. description: Provide a 3-bullet point summary of the overall project.
    3. financial_qualification: COMBINE all explicit "Turnover", "Net Worth", "Security Deposit", and "PBG" conditions. Use bullets for each requirement.
    4. technical_qualification: COMBINE all "Similar Work" and "Experience" requirements into a bulleted list.
    5. If exact keywords are not found, identify equivalent financial or value-related statements and extract them. Do NOT return empty if partial financial information exists.
    
    JSON SCHEMA (Output ONLY valid JSON):
    {{
      "tender_no": "Find the Tender/RFQ number",
      "client_name": "Extract Client Name",
      "tender_open_price": "Extract total tender value. Look for terms like 'Total Financial Limit', 'Estimated Value', 'Contract Value', 'SOR Value', or any total cost mentioned. If found, return numeric value. If not explicitly labeled, infer from context."
      "emd": "Extract the EMD amount or percentage",
      "financial_qualification": "Extract Bulleted list of ANY financial conditions including Turnover, Net Worth, PBG, Security Deposit, Tender Value, or pricing constraints. If Turnover/Net Worth are missing, still extract PBG/SD and mark as "No explicit turnover requirement".",
      "technical_qualification": "Bulleted list of Experience and Competency requirements",
      "mandatory_compliance": "Bulleted list of PF/ESI/Statutory rules",
      "scope_of_work": "Bulleted list of major deliverables and tasks",
      "manpower_count": "Extract headcount",
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
        
        # Robust JSON extraction
        try:
            ai_extracted_data = json.loads(response.text)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', response.text, re.DOTALL)
            ai_extracted_data = json.loads(match.group(0)) if match else {}
        
        # Pass to logic.py
        logic_decisions = evaluate_tender_rules(ai_extracted_data, kb_data, tender_text)

        return ensure_ui_schema(ai_extracted_data, logic_decisions)
    except Exception as e:
        return ensure_ui_schema({}, {}, error_msg=str(e))

def chat_with_tender(query: str, context: dict, full_text: str = ""):
    model = get_model()
    prompt = f"Context: {json.dumps(context)}\nFull Doc: {full_text[:50000]}\nQuery: {query}\n\nStrictly answer based on Full Doc using Markdown bullets."
    return model.generate_content(prompt).text  

# ----------------- CHAT HISTORY TITLE GENERATOR -----------------
def generate_chat_title(first_message: str) -> str:
    """
    Generates a concise, 3-4 word title for the sidebar based on the first interaction.
    """
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
import json
import re

# --- CORE BUSINESS KNOWLEDGE & CAPABILITIES ---
CAPABILITIES = [
    "mechanical engineering", "electrical commissioning", "instrumentation", 
    "piping engineering", "industrial manpower", "manpower deployment", 
    "epc", "shutdown support", "boq", "field engineering", "testing", "qc"
]

SECTOR_KEYWORDS = [
    "bpcl", "bharat petroleum", "hpcl", "hindustan petroleum", "iocl", 
    "ongc", "gail", "refinery", "petrochemical", "oil & gas", 
    "terminal", "mahul", "eastern region", "reliance", "ril", "hmel", "mrpl"
]

def clean_price_local(price_str):
    """Helper to ensure we always have a float for the 25L check."""
    if not price_str or str(price_str).lower() == "not specified":
        return 0.0
    text = str(price_str).lower().replace(',', '')
    num = re.findall(r"[-+]?\d*\.\d+|\d+", text)
    if not num: return 0.0
    val = float(num[0])
    if 'lakh' in text or 'lac' in text: val *= 100000
    elif 'crore' in text or 'cr' in text: val *= 10000000
    return val

def evaluate_tender_rules(extracted_data: dict, kb_data_str: str, raw_text: str = "") -> dict:
    """
    Intelligent AI Tender Profitability & Bid Decision Logic.
    Based on Historical Match, Capability Fit, and Risk Evaluation.
    """
    if not extracted_data:
        extracted_data = {}

    text_lower = str(raw_text).lower()
    kb_lower = str(kb_data_str).lower()
    
    # Extract fields safely
    client_name = str(extracted_data.get("client_name", "")).lower()
    scope_text = str(extracted_data.get("scope_of_work", "")).lower()
    manpower_text = str(extracted_data.get("manpower_count", "")).lower()
    shift_text = str(extracted_data.get("shift_duty", "")).lower()
    penalty_text = str(extracted_data.get("penalty_terms", "")).lower()
    payment_text = str(extracted_data.get("payment_terms", "")).lower()
    comp_text = str(extracted_data.get("mandatory_compliance", "")).lower()
    
    fin_qual_raw = str(extracted_data.get("financial_qualification", "Not Specified")).strip()
    tech_qual_raw = str(extracted_data.get("technical_qualification", "Not Specified")).strip()
    tender_open_price = clean_price_local(extracted_data.get("tender_open_price"))
    
    # Initialize Scoring variables
    profit_score = 50  # Base neutral score
    risks = []
    capabilities_matched = []
    similar_projects = []
    
    # ---------------------------------------------------------
    # 1. HISTORICAL SIMILARITY & CLIENT INTELLIGENCE (+ up to 35 points)
    # ---------------------------------------------------------
    matched_sectors = [s for s in SECTOR_KEYWORDS if s in text_lower or s in scope_text or s in client_name]
    if matched_sectors:
        profit_score += 15
        similar_projects.append(f"Proven sector experience in: {', '.join(set(matched_sectors)).upper()}")
        
    if client_name and (client_name in kb_lower or any(s in client_name for s in SECTOR_KEYWORDS)):
        profit_score += 10
        similar_projects.append("Repeat/High-Value Industrial Client Match")
        
    if tender_open_price > 10000000: # High value bonus (> 1 Crore)
        profit_score += 10

    # ---------------------------------------------------------
    # 2. CAPABILITY FIT (+ up to 20 points)
    # ---------------------------------------------------------
    for cap in CAPABILITIES:
        if cap in scope_text or cap in text_lower:
            capabilities_matched.append(cap.title())
            profit_score += 5
            
    # Cap positive additions to prevent overflow before deductions
    profit_score = min(95, profit_score) 

    # ---------------------------------------------------------
    # 3. RISK EVALUATION (Deductions - up to -45 points)
    # ---------------------------------------------------------
    # Heavy Manpower Dependency / Complexity
    if " 50" in manpower_text or "100" in manpower_text or "large" in manpower_text:
        risks.append("Heavy manpower dependency")
        profit_score -= 10
        
    # Long Shifts
    if "12 hour" in shift_text or "12 hr" in shift_text or "night" in shift_text or "24x7" in shift_text:
        risks.append("Long working shifts / Continuous operations")
        profit_score -= 5
        
    # High Compliance Burden
    if "deviation" in comp_text or "strict" in comp_text or "cannot comply" in comp_text:
        risks.append("High compliance burden / Statutory complexity")
        profit_score -= 10
        
    # Strict Penalty Clauses
    if "10%" in penalty_text or "10 percent" in penalty_text or "liquidated damages" in penalty_text:
        risks.append("Strict penalty/LD clauses detected")
        profit_score -= 10
        
    # Unfavorable Payment Terms
    if any(days in payment_text for days in ["60 days", "90 days", "120 days", "delayed", "back to back"]):
        risks.append("Unfavorable payment terms (Negative cash flow risk)")
        profit_score -= 10

    # Normalize final score between 0 and 100
    profit_score = max(0, min(100, profit_score))

    # ---------------------------------------------------------
    # 4. BID RECOMMENDATION LOGIC (Replaces old Bid/No Bid rules)
    # ---------------------------------------------------------
    is_fin_missing = (fin_qual_raw.lower() == "not specified" or fin_qual_raw == "")
    is_tech_missing = (tech_qual_raw.lower() == "not specified" or tech_qual_raw == "")

    if 0 < tender_open_price < 2500000:
        bid_decision = "No Bid"
        reason = f"Tender value (₹{tender_open_price:,.0f}) is below the minimum viability threshold."
    elif not capabilities_matched and not matched_sectors:
        bid_decision = "No Bid"
        reason = "No historical similarity or capability fit found in the company Knowledge Base."
    elif profit_score < 45:
        bid_decision = "No Bid"
        reason = "Rejected due to high operational risk and low profitability potential."
    elif is_fin_missing or is_tech_missing or profit_score < 75:
        bid_decision = "Consider with Caution"
        reason = "Moderate profit potential or missing explicit qualification criteria requiring manual review."
    else:
        bid_decision = "Recommended"
        reason = "Strong historical match, verified capabilities, and high profitability potential."

    # ---------------------------------------------------------
    # 5. FINAL AI OUTPUT COMPILATION
    # ---------------------------------------------------------
    if profit_score >= 75: win_prob = "High"
    elif profit_score >= 45: win_prob = "Medium"
    else: win_prob = "Low"

    # Compile the advanced Strategic Advice formatting for the UI
    cap_summary = ", ".join(set(capabilities_matched)) if capabilities_matched else "No core engineering/manpower capabilities explicitly matched."
    sim_projects_summary = ", ".join(set(similar_projects)) if similar_projects else "No direct historical matches utilized."
    risk_summary = "\n".join([f"⚠️ {r}" for r in risks]) if risks else "✅ No major operational or commercial risks detected."

    adv_lines = [
        f"**Decision Reasoning:** {reason}",
        "",
        f"**Capability Match Summary:** {cap_summary}",
        "",
        f"**Historical Data Used:** {sim_projects_summary}",
        "",
        f"**Key Risk Factors:**\n{risk_summary}"
    ]

    return {
        "bid_decision": bid_decision,
        "pq_status": "Pass" if bid_decision == "Recommended" else "Pending Review",
        "win_probability": f"{win_prob} ({profit_score}% Profile Match)",
        "profit_forecast": f"{profit_score} / 100", 
        "suitability_score": profit_score,
        "strategic_advice": "\n".join(adv_lines),
        "compliance_status": "Pass" if "High compliance burden" not in risks else "Fail",
        "compliance_reason": "No major compliance issues." if "High compliance burden" not in risks else "Strict compliance requirements detected."
    }
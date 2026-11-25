# logic.py
import re
from knowledge_service import find_similar_past_projects, get_client_aliases

CAPABILITIES = [
    "mechanical engineering",
    "electrical commissioning",
    "instrumentation",
    "piping engineering",
    "industrial manpower",
    "manpower deployment",
    "manpower supply",
    "technical staffing",
    "operation & maintenance",
    "o&m",
    "pmc",
    "project management",
    "shutdown support",
    "field engineering",
    "inspection",
    "commissioning",
    "isometric",
    "dimensional measurement",
]

TIER1_PSU_KEYWORDS = [
    "bpcl", "bharat petroleum", "hpcl", "hindustan petroleum", "iocl", "indian oil",
    "ongc", "oil & natural gas", "gail", "mrpl", "mangalore refinery", "cpcl",
    "chennai petroleum", "nrl", "numaligarh refinery", "ntpc", "bhel", "eil",
    "engineers india", "hmel", "reliance", "ril", "ongc petro additions", "opal",
]

SERVICEABLE_SECTORS = [
    "oil & gas", "petrochemical", "refinery", "pipeline", "metro", "mono rail",
    "railways", "infrastructure", "power", "renewable energy", "cgd", "cng",
    "cement", "fertilizer", "fertiliser", "metals & minerals", "epc",
    "engineering", "it", "telecom",
]


def clean_price_local(price_str) -> float:
    """Converts currency strings like '25 Lakh' or '1.5 Crore' into float INR."""
    if not price_str or str(price_str).strip().lower() in ("not specified", "not applicable", "n/a", ""):
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


def _word_match(term: str, text: str) -> bool:
    return bool(re.search(rf"\b{re.escape(term)}\b", text))


def evaluate_tender_rules(extracted_data: dict, kb_data_str: str, raw_text: str = "") -> dict:
    """
    Aarvi Encon Weighted Scoring & Profitability Logic (Reference Knowledge v3.0):
    - Financial PQ & Past PO Proof (up to 30 pts)
    - Service & Technical Capability Fit (up to 25 pts)
    - Client Reputation & PSU Tier (up to 20 pts)
    - Sector & Regional Alignment (up to 15 pts)
    - Contract Longevity & Pattern Boost (up to 10 pts)
    - Commercial & Statutory Red-Flag Deductions
    """
    if not extracted_data:
        extracted_data = {}

    text_lower = str(raw_text).lower()
    client_raw = str(extracted_data.get("client_name", "")).strip()
    client_lower = client_raw.lower()
    scope_text = str(extracted_data.get("scope_of_work", "")).lower()
    manpower_text = str(extracted_data.get("manpower_count", "")).lower()
    manpower_qual = str(extracted_data.get("manpower_qual", "")).lower()
    shift_text = str(extracted_data.get("shift_duty", "")).lower()
    penalty_text = str(extracted_data.get("penalty_terms", "")).lower()
    payment_text = str(extracted_data.get("payment_terms", "")).lower()
    comp_text = str(extracted_data.get("mandatory_compliance", "")).lower()

    fin_qual_raw = str(extracted_data.get("financial_qualification", "Not Specified")).strip()
    tech_qual_raw = str(extracted_data.get("technical_qualification", "Not Specified")).strip()
    tender_open_price = clean_price_local(extracted_data.get("tender_open_price"))

    combined_search = f"{client_lower} {scope_text} {text_lower[:25000]}"

    risks = []
    capabilities_matched = []
    similar_projects = []

    # 1. FINANCIAL PQ & PAST EXECUTION PROOF (30 pts)
    matched_pos = find_similar_past_projects(scope_text, client_raw, limit=5)
    pos_above_138cr = [p for p in matched_pos if p["contract_value_inr"] >= 13800000]
    pos_above_86lac = [p for p in matched_pos if p["contract_value_inr"] >= 8625000]

    if pos_above_138cr:
        pq_pts = 30
        top_po = pos_above_138cr[0]
        similar_projects.append(
            f"PQ Qualified (1 PO > ₹1.38 Cr): {top_po['client']} — {top_po['project_name']} (₹{top_po['contract_value_inr']:,.0f})"
        )
    elif len(pos_above_86lac) >= 2:
        pq_pts = 22
        similar_projects.append(
            f"PQ Qualified (2 POs > ₹86.25 Lac): {pos_above_86lac[0]['client']} & {pos_above_86lac[1]['client']}"
        )
    elif matched_pos:
        pq_pts = 15
        top_po = matched_pos[0]
        similar_projects.append(
            f"Similar Executed Work: {top_po['client']} — {top_po['project_name']} (₹{top_po['contract_value_inr']:,.0f})"
        )
    else:
        pq_pts = 8

    # 2. SERVICE & CAPABILITY FIT (25 pts)
    for cap in CAPABILITIES:
        if _word_match(cap, scope_text) or _word_match(cap, text_lower[:20000]):
            capabilities_matched.append(cap.upper() if cap in ("o&m", "pmc") else cap.title())

    is_highly_skilled = any(
        k in f"{scope_text} {manpower_qual} {manpower_text}"
        for k in ("b.e", "b.tech", "engineer", "graduate", "analyst", "asnt", "post-qualification", "pg")
    )
    cap_pts = min(25, (15 if is_highly_skilled else 8) + len(set(capabilities_matched)) * 3)

    # 3. CLIENT REPUTATION & TIER-1 PSU MATCH (20 pts)
    aliases = get_client_aliases(client_raw)
    is_tier1_psu = any(k in client_lower for k in TIER1_PSU_KEYWORDS) or any(
        a in TIER1_PSU_KEYWORDS for a in aliases
    )
    client_pts = 20 if is_tier1_psu else (12 if client_lower and client_lower != "not specified" else 5)
    if is_tier1_psu:
        similar_projects.append(f"Tier-1 PSU / Repeat Industrial Client ({client_raw})")

    # 4. SECTOR & LOCATION ALIGNMENT (15 pts)
    matched_sectors = [s for s in SERVICEABLE_SECTORS if _word_match(s, combined_search)]
    sector_pts = 15 if matched_sectors else 5
    if matched_sectors:
        similar_projects.append(f"Serviceable Sector Fit: {', '.join(sorted(set(matched_sectors))).upper()}")

    # 5. CONTRACT LONGEVITY & PATTERN RECOGNITION (10 pts)
    longevity_pts = 10 if any(m in combined_search for m in ("24 months", "36 months", "2 years", "3 years")) else 6

    profit_score = pq_pts + cap_pts + client_pts + sector_pts + longevity_pts

    # 6. NEGATIVE FILTERS & RED FLAGS (Reference Knowledge Section 5 & 6)
    if "reverse auction" in combined_search and not re.findall(
        r"reverse auction\s*[:\-]?\s*(no|not applicable)", combined_search
    ):
        risks.append("Reverse Auction (RA) detected (-15% win margin pressure)")
        profit_score -= 10

    if any(days in payment_text for days in ("60 days", "90 days", "120 days", "back to back")):
        risks.append("Payment cycle >= 60 days (Aarvi standard is 7-21 days)")
        profit_score -= 10

    if "unlimited liability" in combined_search:
        risks.append("Unlimited liability clause detected (Aarvi cap is 100% of PO value)")
        profit_score -= 10

    if any(p in penalty_text for p in ("15%", "20%", "as deemed fit", "unlimited")):
        risks.append("Discretionary or >10% LD/penalty clause detected")
        profit_score -= 7
    elif "10%" in penalty_text or "liquidated damages" in penalty_text:
        risks.append("Standard 10% LD cap clause (Aarvi preferred benchmark is 5%)")
        profit_score -= 3

    if "12 hour" in shift_text or "12 hr" in shift_text or "24x7" in shift_text:
        risks.append("Continuous / 12-hr shift operations (factor overtime & reliever cost)")
        profit_score -= 5

    if "no esi" in comp_text or ("esi" in comp_text and "undertaking" in comp_text):
        risks.append("Include ₹5L Group Insurance buffer if ESI registration is pending")

    profit_score = max(0, min(100, profit_score))

    # 7. BID DECISION GATEKEEPER
    is_fin_missing = fin_qual_raw.lower() in ("not specified", "")
    is_tech_missing = tech_qual_raw.lower() in ("not specified", "")

    if 0 < tender_open_price < 2500000:
        bid_decision = "No Bid"
        reason = f"Tender value (₹{tender_open_price:,.0f}) is below Aarvi's ₹25 Lakh minimum viability floor."
    elif not capabilities_matched and not matched_sectors:
        bid_decision = "No Bid"
        reason = "Outside Aarvi Encon's 19 serviceable sectors and core technical staffing capabilities."
    elif profit_score < 45:
        bid_decision = "No Bid"
        reason = "High commercial/operational risk score below threshold."
    elif is_fin_missing or is_tech_missing or profit_score < 75:
        bid_decision = "Consider with Caution"
        reason = (
            "Strong sector/client fit, but missing explicit turnover/headcount figures or commercial flags require review. "
            "Maintain >= 3.85% service charge floor (₹36,465/mo Highly Skilled CTC benchmark)."
        )
    else:
        bid_decision = "Recommended"
        reason = (
            "Strong Tier-1 PSU & PQ match with verified past POs. Target >= 3.85% service charge floor "
            "on ₹36,465/mo Highly Skilled CTC benchmark."
        )

    if profit_score >= 75:
        win_prob = "High"
    elif profit_score >= 45:
        win_prob = "Medium"
    else:
        win_prob = "Low"

    cap_summary = (
        ", ".join(sorted(set(capabilities_matched)))
        if capabilities_matched
        else "General Industrial / Technical Support"
    )
    sim_projects_summary = (
        " | ".join(dict.fromkeys(similar_projects))
        if similar_projects
        else "No direct historical matches utilized."
    )
    risk_summary = (
        "\n".join([f"⚠️ {r}" for r in risks])
        if risks
        else "✅ No major operational or commercial red flags detected."
    )

    adv_lines = [
        f"**Decision Reasoning:** {reason}",
        "",
        f"**Capability Match Summary:** {cap_summary}",
        "",
        f"**Historical Data & PQ Proof Used:** {sim_projects_summary}",
        "",
        f"**Key Risk & Costing Factors:**\n{risk_summary}",
    ]

    return {
        "bid_decision": bid_decision,
        "pq_status": "Pass" if (pos_above_138cr or len(pos_above_86lac) >= 2 or bid_decision == "Recommended") else "Pending Review",
        "win_probability": f"{win_prob} ({profit_score}% Profile Match)",
        "profit_forecast": f"{profit_score} / 100",
        "suitability_score": profit_score,
        "strategic_advice": "\n".join(adv_lines),
        "compliance_status": "Pass" if "Unlimited liability" not in " ".join(risks) else "Fail",
        "compliance_reason": "Meets Aarvi statutory & PF/ESIC/GST baseline." if not risks else risks[0],
    }
# triage.py
import os
import re
from typing import List, Dict, Tuple, Set

try:
    from config import TRIAGE_TOKEN_BUDGET, SECOND_PASS_TOKEN_BUDGET
except ImportError:
    TRIAGE_TOKEN_BUDGET = int(os.getenv("TRIAGE_TOKEN_BUDGET", "65000"))
    SECOND_PASS_TOKEN_BUDGET = int(os.getenv("SECOND_PASS_TOKEN_BUDGET", "45000"))

# Weighted keyword patterns aligned with Aarvi's 15 extraction fields
FIELD_PATTERNS: Dict[str, List[Tuple[str, float]]] = {
    "tender_no": [
        (r"\b(?:tender|rfq|nit|gem|enquiry|inquiry|bid)\s*(?:no\.?|number|id|ref)\b", 4.0),
        (r"\bnotice\s+inviting\s+tender\b", 3.5),
    ],
    "client_name": [
        (r"\b(?:hpcl|bpcl|iocl|ongc|gail|ntpc|bhel|hmel|mrpl|reliance|l&t|tata)\b", 3.0),
        (r"\b(?:name\s+of\s+(?:the\s+)?(?:client|owner|employer|company|corporation))\b", 3.5),
    ],
    "due_date": [
        (r"\b(?:due\s+date|closing\s+date|submission\s+deadline|last\s+date|bid\s+end\s+date)\b", 4.5),
        (r"\b(?:opening\s+date|pre[- ]?bid\s+meeting)\b", 2.5),
    ],
    "tender_open_price": [
        (r"\b(?:estimated\s+(?:cost|value)|tender\s+value|contract\s+value|put\s+to\s+tender)\b", 4.5),
        (r"(?:₹|\brs\.?\b|\binr\b)\s*[\d,.]+\s*(?:lakh|lac|crore|cr)?", 2.5),
    ],
    "emd": [
        (r"\b(?:emd|earnest\s+money|bid\s+security|bid\s+bond)\b", 5.0),
        (r"\b(?:msme|nsic|udyam)\s+exemption\b", 2.5),
    ],
    "financial_qualification": [
        (r"\b(?:annual\s+turnover|average\s+turnover|net\s+worth|solvency|working\s+capital)\b", 4.5),
        (r"\b(?:pbg|performance\s+bank\s+guarantee|security\s+deposit|financial\s+criteria|bec|bqc)\b", 3.5),
    ],
    "technical_qualification": [
        (r"\b(?:technical\s+(?:qualification|eligibility|criteria)|bid\s+evaluation\s+criteria)\b", 4.5),
        (r"\b(?:years\s+of\s+experience|work\s+order|completion\s+certificate)\b", 3.0),
    ],
    "mandatory_compliance": [
        (r"\b(?:epf|pf\b|esic|esi\b|gst|labor\s+licen[cs]e|clra|statutory\s+compliance|iso\s*9001)\b", 4.0),
    ],
    "scope_of_work": [
        (r"\b(?:scope\s+of\s+work|brief\s+description|schedule\s+of\s+rates|sor\b|boq\b|deliverables)\b", 4.0),
    ],
    "manpower_count": [
        (r"\b(?:manpower|personnel|deployment|headcount|qty|quantity|no\.?\s+of\s+persons)\b", 4.5),
        (r"\b(?:engineer|supervisor|technician|fitter|welder|rigger|helper|operator|coordinator)\b", 3.0),
    ],
    "manpower_qual": [
        (r"\b(?:qualification|b\.?e\.?|b\.?tech|diploma|iti\b|graduate|degree|experience\s+required)\b", 4.0),
    ],
    "shift_duty": [
        (r"\b(?:shift|working\s+hours|duty\s+hours|8\s*hours|12\s*hours|24x7|general\s+shift|overtime)\b", 4.5),
    ],
    "payment_terms": [
        (r"\b(?:payment\s+terms|terms\s+of\s+payment|running\s+account|ra\s+bill|invoice|within\s+\d+\s+days)\b", 4.5),
    ],
    "penalty_terms": [
        (r"\b(?:liquidated\s+damages|l\.?d\.?\s+clause|penalty|penalties|deduction|absenteeism)\b", 5.0),
    ],
    "similar_work": [
        (r"\b(?:similar\s+work|similar\s+nature\s+of\s+work|single\s+work\s+order|two\s+work\s+orders|three\s+work\s+orders)\b", 5.0),
    ],
}

BOILERPLATE_PATTERNS = [
    r"\bforce\s+majeure\b",
    r"\barbitration\s+and\s+conciliation\b",
    r"\bcorrupt\s+or\s+fraudulent\s+practices\b",
    r"\bsettlement\s+of\s+disputes\b",
    r"\bpatent\s+indemnity\b",
]


def _est_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def score_page_by_field(text: str) -> Dict[str, float]:
    """Returns per-field relevance scores for a single page."""
    if not text or len(text.strip()) < 25:
        return {}
    lower = text.lower()
    scores: Dict[str, float] = {}
    for field, patterns in FIELD_PATTERNS.items():
        field_score = 0.0
        for pat, weight in patterns:
            matches = len(re.findall(pat, lower))
            if matches:
                # Diminishing returns for repeated mentions on the same page
                field_score += weight * (1.0 + min(2.0, (matches - 1) * 0.35))
        if field_score > 0:
            scores[field] = field_score
    return scores


def select_triaged_pages(
    pages: List[Dict],
    token_budget: int = None,
) -> Tuple[str, Set[Tuple[str, int]], Dict]:
    """
    Selects the highest-value pages within `token_budget` while locking
    anchor pages (first 8 and last 3 per file) and boosting neighbors of hits.
    Returns: (combined_prompt_text, selected_keys, stats_dict)
    """
    budget = token_budget or TRIAGE_TOKEN_BUDGET
    if not pages:
        return "", set(), {"total_pages": 0, "selected_pages": 0, "raw_tokens": 0, "triaged_tokens": 0}

    raw_tokens = sum(_est_tokens(p.get("text", "")) for p in pages)

    # Group pages by filename to identify per-file anchors & neighbors
    by_file: Dict[str, List[int]] = {}
    for idx, p in enumerate(pages):
        by_file.setdefault(p["file"], []).append(idx)

    total_scores = [0.0] * len(pages)
    anchor_indices: Set[int] = set()

    for fname, idx_list in by_file.items():
        n = len(idx_list)
        # Lock first 8 pages (NIT / cover summary) and last 3 pages per file
        for pos in range(min(8, n)):
            anchor_indices.add(idx_list[pos])
        for pos in range(max(0, n - 3), n):
            anchor_indices.add(idx_list[pos])

    # Score every page
    for idx, p in enumerate(pages):
        txt = p.get("text", "")
        f_scores = score_page_by_field(txt)
        base = sum(f_scores.values())
        # Bonus for multi-field density (e.g., NIT summary tables)
        if len(f_scores) >= 3:
            base += len(f_scores) * 2.5

        # Penalize pure legal boilerplate if no commercial/technical fields matched
        lower = txt.lower()
        bp_hits = sum(1 for pat in BOILERPLATE_PATTERNS if re.search(pat, lower))
        if bp_hits >= 2 and base < 6.0:
            base *= 0.35

        total_scores[idx] += base

    # Neighbor boost (+35% score bleed to page-1 and page+1 within same file)
    boosted_scores = list(total_scores)
    for fname, idx_list in by_file.items():
        for pos, idx in enumerate(idx_list):
            if total_scores[idx] >= 6.0:
                if pos > 0:
                    boosted_scores[idx_list[pos - 1]] += total_scores[idx] * 0.35
                if pos + 1 < len(idx_list):
                    boosted_scores[idx_list[pos + 1]] += total_scores[idx] * 0.35

    # Order candidates: anchors first (in document order), then highest-scoring pages
    ordered_candidates = sorted(anchor_indices) + [
        idx for idx in sorted(range(len(pages)), key=lambda i: boosted_scores[i], reverse=True)
        if idx not in anchor_indices and boosted_scores[idx] > 0
    ]

    # Backfill sequentially if very few keyword hits occurred (unusual wording)
    if len(ordered_candidates) < len(pages):
        seen_set = set(ordered_candidates)
        for idx in range(len(pages)):
            if idx not in seen_set:
                ordered_candidates.append(idx)

    chosen_indices: List[int] = []
    used_tokens = 0
    for idx in ordered_candidates:
        p_tokens = _est_tokens(pages[idx].get("text", "")) + 20
        if used_tokens + p_tokens > budget and chosen_indices:
            continue
        chosen_indices.append(idx)
        used_tokens += p_tokens
        if used_tokens >= budget:
            break

    # Sort chosen pages back into natural reading order
    chosen_indices.sort()
    selected_keys = {(pages[i]["file"], pages[i]["page"]) for i in chosen_indices}

    formatted_blocks = []
    for i in chosen_indices:
        p = pages[i]
        tag = " [OCR]" if p.get("is_ocr") else ""
        formatted_blocks.append(f"\n--- Page {p['page']} | File: {p['file']}{tag} ---\n{p['text']}\n")

    triaged_text = "".join(formatted_blocks)
    stats = {
        "total_pages": len(pages),
        "selected_pages": len(chosen_indices),
        "raw_tokens": raw_tokens,
        "triaged_tokens": _est_tokens(triaged_text),
    }
    return triaged_text, selected_keys, stats


def select_pages_for_missing_fields(
    pages: List[Dict],
    missing_fields: List[str],
    already_selected: Set[Tuple[str, int]],
    token_budget: int = None,
) -> str:
    """
    Pass-2 helper: searches ONLY pages not sent in Pass 1 to recover
    specific fields that came back 'Not Specified'.
    """
    budget = token_budget or SECOND_PASS_TOKEN_BUDGET
    if not pages or not missing_fields:
        return ""

    target_set = set(missing_fields)
    scored_unseen: List[Tuple[float, int]] = []

    for idx, p in enumerate(pages):
        if (p["file"], p["page"]) in already_selected:
            continue
        f_scores = score_page_by_field(p.get("text", ""))
        relevant_score = sum(val for k, val in f_scores.items() if k in target_set)
        if relevant_score > 0:
            scored_unseen.append((relevant_score, idx))

    if not scored_unseen:
        return ""

    scored_unseen.sort(key=lambda x: x[0], reverse=True)
    chosen: List[int] = []
    used = 0
    for _, idx in scored_unseen:
        t_cnt = _est_tokens(pages[idx].get("text", "")) + 20
        if used + t_cnt > budget and chosen:
            continue
        chosen.append(idx)
        used += t_cnt
        if used >= budget:
            break

    chosen.sort()
    blocks = []
    for i in chosen:
        p = pages[i]
        blocks.append(f"\n--- Page {p['page']} | File: {p['file']} ---\n{p['text']}\n")
    return "".join(blocks)
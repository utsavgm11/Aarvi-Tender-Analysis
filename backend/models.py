# models.py
from pydantic import BaseModel, Field
from typing import Optional, List


class TenderExtractionSchema(BaseModel):
    """Strict 15-field schema enforced via Gemini Structured Outputs."""
    tender_no: str = Field(
        default="Not Specified",
        description="Exact Tender, RFQ, NIT, or GeM Bid number."
    )
    client_name: str = Field(
        default="Not Specified",
        description="Full name of the issuing client or organization."
    )
    due_date: str = Field(
        default="Not Specified",
        description="Exact bid submission deadline including date and time if present."
    )
    tender_open_price: str = Field(
        default="Not Specified",
        description="Estimated tender value, budget, or contract price (preserve currency/units like Lakh/Crore)."
    )
    emd: str = Field(
        default="Not Specified",
        description="Earnest Money Deposit (EMD) / Bid Security amount, percentage, or exemption details."
    )
    financial_qualification: str = Field(
        default="Not Specified",
        description="Minimum annual turnover, net worth, solvency, or PBG financial criteria."
    )
    technical_qualification: str = Field(
        default="Not Specified",
        description="Technical eligibility, years of experience, and competency criteria."
    )
    mandatory_compliance: str = Field(
        default="Not Specified",
        description="Statutory requirements such as PF, ESIC, GST, labor licenses, or ISO certifications."
    )
    scope_of_work: str = Field(
        default="Not Specified",
        description="Clear, concise summary of major deliverables, services, and project scope."
    )
    manpower_count: str = Field(
        default="Not Specified",
        description="Bulleted list (using '• ') of every required role, discipline, and headcount."
    )
    manpower_qual: str = Field(
        default="Not Specified",
        description="Educational qualifications and minimum experience required for deployed personnel."
    )
    shift_duty: str = Field(
        default="Not Specified",
        description="Working hours, shift pattern (e.g., 8-hr, 12-hr, general, 24x7), or duty roster."
    )
    payment_terms: str = Field(
        default="Not Specified",
        description="Billing cycle, invoice clearance timeline (e.g., 30/60 days), and retention terms."
    )
    penalty_terms: str = Field(
        default="Not Specified",
        description="Liquidated Damages (LD), SLA deductions, or penalty percentages."
    )
    similar_work: str = Field(
        default="Not Specified",
        description="Definition and value thresholds of qualifying 'Similar Work' or past work orders."
    )


class StrategyExtractionSchema(BaseModel):
    """Structured output for historical competitor and bid strategy analysis."""
    top_3_competitors: str = Field(
        description="Bulleted list of the top 3 recurring competitors with encounter counts, L1 wins, and loss reasons."
    )
    strategic_advice: str = Field(
        description="Concise 4-5 sentence analytical recommendation to win against these competitors."
    )


class TenderFeedbackPayload(BaseModel):
    """User rating and optional field-level corrections for the learning loop."""
    document_id: str
    tender_no: Optional[str] = "N/A"
    client_name: Optional[str] = "Not Specified"
    rating: int = Field(..., ge=1, le=5)
    wrong_fields: List[str] = []
    corrections: dict = {}
    user_email: Optional[str] = None
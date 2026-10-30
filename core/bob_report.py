from pydantic import BaseModel
from typing import Optional
from datetime import date


class BenefitFrequency(BaseModel):
    procedure_code: str
    description: str
    raw_frequency_text: str          # e.g. "Once every 6 months"
    normalized_months: Optional[int] # e.g. 6
    last_service_date: Optional[date]
    next_eligible_date: Optional[date]
    is_eligible: bool
    notes: Optional[str] = None      # AI-generated flag for ambiguous rules


class BOBReport(BaseModel):
    # Patient & Plan
    patient_name: str
    date_of_birth: Optional[date]
    subscriber_id: str
    member_id: Optional[str]
    group_number: str
    insurance_plan: str
    portal: str
    verified_date: date

    # Coverage
    coverage_status: str             # "Active" | "Inactive" | "Unknown"
    coverage_effective_date: Optional[date]
    coverage_termination_date: Optional[date]

    # Financials
    annual_maximum: Optional[float]
    deductible_amount: Optional[float]
    deductible_used: Optional[float]
    deductible_remaining: Optional[float]

    # Benefits
    benefits: list[BenefitFrequency]

    # Workflow
    requires_human_review: bool = False
    human_review_reasons: list[str] = []
    raw_portal_data: Optional[dict] = None  # Store scraped raw data for audit

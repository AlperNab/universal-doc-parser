from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional, Any


@dataclass
class ParsedDocument:
    """Generic extraction result — raw fields from any document."""
    source_file: str
    page_count: int
    document_type: str           # "bank_statement" | "loan_criteria" | "identity" | "unknown"
    extracted_fields: dict       # Raw key-value pairs
    confidence: float            # 0.0 – 1.0
    model_used: str
    parsed_at: datetime
    raw_text: Optional[str] = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class LoanCriteria:
    """Normalized loan eligibility criteria extracted from a banking document."""
    # Identity
    bank_name: str
    product_name: Optional[str] = None
    document_date: Optional[str] = None

    # Loan parameters
    min_loan_amount: Optional[Decimal] = None
    max_loan_amount: Optional[Decimal] = None
    min_interest_rate: Optional[float] = None
    max_interest_rate: Optional[float] = None
    interest_rate_type: Optional[str] = None     # "fixed" | "variable" | "both"
    min_term_months: Optional[int] = None
    max_term_months: Optional[int] = None

    # Borrower requirements
    min_income: Optional[Decimal] = None
    min_employment_months: Optional[int] = None
    employment_types_accepted: list[str] = field(default_factory=list)
    min_credit_score: Optional[int] = None
    max_dti_ratio: Optional[float] = None         # Debt-to-income ratio
    citizenship_requirements: list[str] = field(default_factory=list)
    age_min: Optional[int] = None
    age_max: Optional[int] = None

    # Collateral / security
    requires_collateral: Optional[bool] = None
    accepted_collateral_types: list[str] = field(default_factory=list)
    max_ltv_ratio: Optional[float] = None         # Loan-to-value

    # Fees
    origination_fee_pct: Optional[float] = None
    early_repayment_penalty: Optional[bool] = None
    other_fees: dict = field(default_factory=dict)

    # Geography
    available_regions: list[str] = field(default_factory=list)
    excluded_regions: list[str] = field(default_factory=list)

    # Raw extras
    additional_notes: list[str] = field(default_factory=list)
    confidence: float = 0.0
    source_file: str = ""


@dataclass
class BankingDocument:
    """Parsed banking document with both raw and normalized data."""
    raw: ParsedDocument
    criteria: Optional[LoanCriteria] = None       # Populated if doc_type == loan_criteria
    match_score: Optional[float] = None           # Set by LoanMatcher

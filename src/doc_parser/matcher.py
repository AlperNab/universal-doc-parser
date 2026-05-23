"""LoanMatcher — scores banks against a client profile."""
from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional
from .models import LoanCriteria


class MatchStatus(str, Enum):
    BEST_FIT     = "best_fit"
    POSSIBLE_FIT = "possible_fit"
    NOT_SUITABLE = "not_suitable"


@dataclass
class ClientProfile:
    loan_amount_needed: Decimal
    monthly_income: Decimal
    employment_type: str           # "employed" | "self_employed" | "contractor" | "retired"
    employment_months: int
    credit_score: Optional[int] = None
    age: Optional[int] = None
    nationality: Optional[str] = None
    has_collateral: bool = False
    collateral_type: Optional[str] = None
    collateral_value: Optional[Decimal] = None
    existing_debt_monthly: Decimal = Decimal("0")
    desired_term_months: Optional[int] = None
    region: Optional[str] = None


@dataclass
class MatchResult:
    bank_name: str
    product_name: Optional[str]
    status: MatchStatus
    score: float                  # 0.0 – 1.0
    reasons: list[str] = field(default_factory=list)
    dealbreakers: list[str] = field(default_factory=list)
    source_file: str = ""


class LoanMatcher:
    """Score a list of LoanCriteria against a ClientProfile."""

    def match(self, profile: ClientProfile, banks: list[LoanCriteria]) -> list[MatchResult]:
        results = [self._score(profile, bank) for bank in banks]
        return sorted(results, key=lambda r: r.score, reverse=True)

    def _score(self, p: ClientProfile, c: LoanCriteria) -> MatchResult:
        reasons: list[str] = []
        dealbreakers: list[str] = []
        score = 1.0

        # ── Hard disqualifiers ────────────────────────────────────────────────
        if c.min_loan_amount and p.loan_amount_needed < c.min_loan_amount:
            dealbreakers.append(f"Loan needed ({p.loan_amount_needed}) below minimum ({c.min_loan_amount})")
        if c.max_loan_amount and p.loan_amount_needed > c.max_loan_amount:
            dealbreakers.append(f"Loan needed ({p.loan_amount_needed}) exceeds maximum ({c.max_loan_amount})")

        if c.min_income and p.monthly_income < c.min_income:
            dealbreakers.append(f"Income ({p.monthly_income}/mo) below minimum ({c.min_income}/mo)")

        if c.min_employment_months and p.employment_months < c.min_employment_months:
            dealbreakers.append(f"Employment {p.employment_months} months < required {c.min_employment_months}")

        if c.employment_types_accepted and p.employment_type not in c.employment_types_accepted:
            dealbreakers.append(f"Employment type '{p.employment_type}' not accepted (accepts: {c.employment_types_accepted})")

        if c.min_credit_score and p.credit_score and p.credit_score < c.min_credit_score:
            dealbreakers.append(f"Credit score {p.credit_score} below minimum {c.min_credit_score}")

        if c.age_min and p.age and p.age < c.age_min:
            dealbreakers.append(f"Age {p.age} below minimum {c.age_min}")
        if c.age_max and p.age and p.age > c.age_max:
            dealbreakers.append(f"Age {p.age} above maximum {c.age_max}")

        if c.requires_collateral and not p.has_collateral:
            dealbreakers.append("Collateral required but client has none")

        if c.citizenship_requirements and p.nationality:
            if p.nationality.lower() not in [r.lower() for r in c.citizenship_requirements]:
                dealbreakers.append(f"Nationality '{p.nationality}' not in accepted list")

        if c.excluded_regions and p.region:
            if any(p.region.lower() in ex.lower() for ex in c.excluded_regions):
                dealbreakers.append(f"Region '{p.region}' is excluded")

        if dealbreakers:
            return MatchResult(
                bank_name=c.bank_name, product_name=c.product_name,
                status=MatchStatus.NOT_SUITABLE, score=0.0,
                dealbreakers=dealbreakers, source_file=c.source_file,
            )

        # ── Soft scoring ──────────────────────────────────────────────────────
        # DTI check
        if c.max_dti_ratio and p.monthly_income > 0:
            current_dti = float(p.existing_debt_monthly / p.monthly_income)
            if current_dti > c.max_dti_ratio:
                score -= 0.3
                reasons.append(f"DTI {current_dti:.1%} above preferred {c.max_dti_ratio:.1%}")
            else:
                reasons.append(f"DTI {current_dti:.1%} within limit")

        # Term match
        if c.desired_term := getattr(p, "desired_term_months", None):
            if c.min_term_months and c.desired_term < c.min_term_months:
                score -= 0.1
            elif c.max_term_months and c.desired_term > c.max_term_months:
                score -= 0.1
            else:
                reasons.append("Desired term within range")

        # Collateral bonus
        if c.requires_collateral and p.has_collateral:
            score = min(1.0, score + 0.1)
            reasons.append("Has required collateral")

        # Rate competitiveness (lower is better)
        if c.max_interest_rate:
            if c.max_interest_rate < 5.0:
                score = min(1.0, score + 0.1)
                reasons.append(f"Competitive rate ≤ {c.max_interest_rate}%")

        score = max(0.0, min(1.0, score * c.confidence))
        status = MatchStatus.BEST_FIT if score >= 0.75 else MatchStatus.POSSIBLE_FIT

        return MatchResult(
            bank_name=c.bank_name, product_name=c.product_name,
            status=status, score=round(score, 3),
            reasons=reasons, dealbreakers=[],
            source_file=c.source_file,
        )

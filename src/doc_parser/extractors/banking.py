"""Banking-specific extractor — maps raw fields to normalized LoanCriteria."""
from __future__ import annotations
import json
import re
from decimal import Decimal, InvalidOperation
from typing import Optional
import anthropic

from ..models import LoanCriteria, ParsedDocument


class BankingExtractor:
    """Converts raw document extraction into normalized LoanCriteria."""

    NORMALIZATION_PROMPT = """
Given these raw fields extracted from a banking/loan document, produce a normalized JSON object.

Raw fields:
{raw_fields}

Output a JSON object with these exact keys (use null for missing/unclear values):
{{
  "bank_name": string,
  "product_name": string | null,
  "document_date": string | null,
  "min_loan_amount": number | null,
  "max_loan_amount": number | null,
  "min_interest_rate": number | null,
  "max_interest_rate": number | null,
  "interest_rate_type": "fixed" | "variable" | "both" | null,
  "min_term_months": number | null,
  "max_term_months": number | null,
  "min_income": number | null,
  "min_employment_months": number | null,
  "employment_types_accepted": [string],
  "min_credit_score": number | null,
  "max_dti_ratio": number | null,
  "citizenship_requirements": [string],
  "age_min": number | null,
  "age_max": number | null,
  "requires_collateral": boolean | null,
  "accepted_collateral_types": [string],
  "max_ltv_ratio": number | null,
  "origination_fee_pct": number | null,
  "early_repayment_penalty": boolean | null,
  "other_fees": {{}},
  "available_regions": [string],
  "excluded_regions": [string],
  "additional_notes": [string],
  "confidence": number
}}

Return ONLY the JSON object. No markdown, no explanation.
"""

    def __init__(self, client: anthropic.Anthropic, model: str, max_tokens: int):
        self._client = client
        self._model = model
        self._max_tokens = max_tokens

    def extract_criteria(self, encoded: str, media_type: str, raw: ParsedDocument) -> LoanCriteria:
        """Normalize raw extracted fields into a LoanCriteria object."""
        prompt = self.NORMALIZATION_PROMPT.format(
            raw_fields=json.dumps(raw.extracted_fields, indent=2, default=str)
        )

        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            data = json.loads(match.group()) if match else {}

        return self._map_to_criteria(data, raw.source_file)

    def _map_to_criteria(self, data: dict, source_file: str) -> LoanCriteria:
        def dec(val) -> Optional[Decimal]:
            if val is None:
                return None
            try:
                return Decimal(str(val))
            except InvalidOperation:
                return None

        def flt(val) -> Optional[float]:
            try:
                return float(val) if val is not None else None
            except (TypeError, ValueError):
                return None

        def intt(val) -> Optional[int]:
            try:
                return int(val) if val is not None else None
            except (TypeError, ValueError):
                return None

        return LoanCriteria(
            bank_name=data.get("bank_name", "Unknown"),
            product_name=data.get("product_name"),
            document_date=data.get("document_date"),
            min_loan_amount=dec(data.get("min_loan_amount")),
            max_loan_amount=dec(data.get("max_loan_amount")),
            min_interest_rate=flt(data.get("min_interest_rate")),
            max_interest_rate=flt(data.get("max_interest_rate")),
            interest_rate_type=data.get("interest_rate_type"),
            min_term_months=intt(data.get("min_term_months")),
            max_term_months=intt(data.get("max_term_months")),
            min_income=dec(data.get("min_income")),
            min_employment_months=intt(data.get("min_employment_months")),
            employment_types_accepted=data.get("employment_types_accepted") or [],
            min_credit_score=intt(data.get("min_credit_score")),
            max_dti_ratio=flt(data.get("max_dti_ratio")),
            citizenship_requirements=data.get("citizenship_requirements") or [],
            age_min=intt(data.get("age_min")),
            age_max=intt(data.get("age_max")),
            requires_collateral=data.get("requires_collateral"),
            accepted_collateral_types=data.get("accepted_collateral_types") or [],
            max_ltv_ratio=flt(data.get("max_ltv_ratio")),
            origination_fee_pct=flt(data.get("origination_fee_pct")),
            early_repayment_penalty=data.get("early_repayment_penalty"),
            other_fees=data.get("other_fees") or {},
            available_regions=data.get("available_regions") or [],
            excluded_regions=data.get("excluded_regions") or [],
            additional_notes=data.get("additional_notes") or [],
            confidence=flt(data.get("confidence")) or 0.7,
            source_file=source_file,
        )

"""DocumentParser — main entry point. PDF → base64 → Claude vision → structured JSON."""
from __future__ import annotations
import base64
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import anthropic

from .models import ParsedDocument, BankingDocument, LoanCriteria
from .extractors.banking import BankingExtractor


class DocumentParser:
    """
    Parse any financial PDF document into structured data using Claude vision.

    Supports: bank criteria sheets, loan term documents, rate cards,
    bank statements, identity documents, insurance schedules.
    """

    DEFAULT_MODEL = "claude-sonnet-4-20250514"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 4096,
    ):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens
        self._banking_extractor = BankingExtractor(self._client, model, max_tokens)

    def parse(self, file_path: str | Path, document_type: str = "auto") -> BankingDocument:
        """
        Parse a PDF or image document.

        Args:
            file_path: Path to PDF, PNG, JPG, or TIFF file
            document_type: "auto" | "loan_criteria" | "bank_statement" | "identity"

        Returns:
            BankingDocument with raw extracted fields and normalized criteria
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        media_type, encoded = self._encode_file(path)
        detected_type = document_type

        if document_type == "auto":
            detected_type = self._detect_document_type(encoded, media_type, path.name)

        raw = self._extract_raw(encoded, media_type, detected_type, path.name)

        criteria = None
        if detected_type == "loan_criteria":
            criteria = self._banking_extractor.extract_criteria(encoded, media_type, raw)

        return BankingDocument(raw=raw, criteria=criteria)

    def parse_bytes(
        self,
        content: bytes,
        filename: str,
        media_type: str = "application/pdf",
        document_type: str = "auto",
    ) -> BankingDocument:
        """Parse document from raw bytes — useful in web APIs."""
        encoded = base64.standard_b64encode(content).decode("utf-8")
        detected_type = document_type

        if document_type == "auto":
            detected_type = self._detect_document_type(encoded, media_type, filename)

        raw = self._extract_raw(encoded, media_type, detected_type, filename)

        criteria = None
        if detected_type == "loan_criteria":
            criteria = self._banking_extractor.extract_criteria(encoded, media_type, raw)

        return BankingDocument(raw=raw, criteria=criteria)

    # ─── Internal ──────────────────────────────────────────────────────────────

    def _encode_file(self, path: Path) -> tuple[str, str]:
        suffix = path.suffix.lower()
        type_map = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".tiff": "image/tiff",
            ".tif": "image/tiff",
            ".webp": "image/webp",
        }
        media_type = type_map.get(suffix, "application/pdf")
        with open(path, "rb") as f:
            encoded = base64.standard_b64encode(f.read()).decode("utf-8")
        return media_type, encoded

    def _detect_document_type(self, encoded: str, media_type: str, filename: str) -> str:
        """Quick classification call — cheap, low token usage."""
        response = self._client.messages.create(
            model=self._model,
            max_tokens=50,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document" if "pdf" in media_type else "image",
                        "source": {"type": "base64", "media_type": media_type, "data": encoded},
                    },
                    {
                        "type": "text",
                        "text": (
                            "Classify this document. Reply with exactly one of these words:\n"
                            "loan_criteria | bank_statement | identity | rate_card | unknown\n"
                            "No explanation. One word only."
                        ),
                    },
                ],
            }],
        )
        detected = response.content[0].text.strip().lower()
        valid = {"loan_criteria", "bank_statement", "identity", "rate_card", "unknown"}
        return detected if detected in valid else "unknown"

    def _extract_raw(
        self,
        encoded: str,
        media_type: str,
        document_type: str,
        filename: str,
    ) -> ParsedDocument:
        """Extract all fields from document as raw key-value pairs."""
        prompt = self._build_extraction_prompt(document_type)

        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document" if "pdf" in media_type else "image",
                        "source": {"type": "base64", "media_type": media_type, "data": encoded},
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )

        text = response.content[0].text
        fields = self._parse_json_response(text)

        return ParsedDocument(
            source_file=filename,
            page_count=fields.pop("page_count", 1),
            document_type=document_type,
            extracted_fields=fields,
            confidence=fields.pop("confidence", 0.8),
            model_used=self._model,
            parsed_at=datetime.now(timezone.utc),
        )

    def _build_extraction_prompt(self, document_type: str) -> str:
        base = (
            "Extract ALL information from this document into a JSON object. "
            "Return ONLY valid JSON — no markdown, no explanation, no backticks. "
            "Use null for fields that are missing or unclear. "
            "Add a 'confidence' field (0.0–1.0) reflecting overall extraction quality. "
        )
        specifics = {
            "loan_criteria": (
                "Focus on: interest rates, loan amounts, term lengths, eligibility requirements "
                "(income, employment, credit score, age, nationality), fees, collateral requirements, "
                "available regions, product name, bank name, document date."
            ),
            "bank_statement": (
                "Focus on: account holder name, account number (last 4 digits only), "
                "bank name, statement period, opening/closing balance, "
                "transaction count, total credits, total debits."
            ),
            "identity": (
                "Focus on: document type, issuing country, expiry date (not the ID number). "
                "Do NOT extract the ID/passport number for privacy."
            ),
        }
        return base + specifics.get(document_type, "Extract all visible fields.")

    def _parse_json_response(self, text: str) -> dict:
        """Robustly parse JSON from Claude's response."""
        text = text.strip()
        # Strip markdown fences if present
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON object within text
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group())
            return {"raw_text": text, "confidence": 0.3}

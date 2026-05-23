"""universal-doc-parser — any financial PDF → clean structured JSON via Claude."""
from .parser import DocumentParser
from .models import ParsedDocument, BankingDocument, LoanCriteria
from .extractors.banking import BankingExtractor

__version__ = "0.1.0"
__all__ = ["DocumentParser", "ParsedDocument", "BankingDocument", "LoanCriteria", "BankingExtractor"]

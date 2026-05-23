# universal-doc-parser

> **Any financial PDF → clean structured JSON** using Claude vision. Purpose-built for banking documents, loan criteria sheets, and financial due diligence.

[![PyPI](https://img.shields.io/pypi/v/universal-doc-parser?style=flat)](https://pypi.org/project/universal-doc-parser/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat&logo=python)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Claude](https://img.shields.io/badge/Powered_by-Claude-D97757?style=flat)](https://anthropic.com)

The fintech dev community has no clean OSS solution for extracting structured data from arbitrary financial PDFs. This is it.

## What it does

```python
from doc_parser import DocumentParser, LoanMatcher, ClientProfile
from decimal import Decimal

parser = DocumentParser(api_key="YOUR_ANTHROPIC_KEY")

# Parse a bank's loan criteria PDF
result = parser.parse("bank_of_cairo_personal_loan_2025.pdf")

print(result.criteria.bank_name)           # "Bank of Cairo"
print(result.criteria.max_loan_amount)     # Decimal("500000")
print(result.criteria.min_interest_rate)   # 12.5
print(result.criteria.min_income)          # Decimal("5000")
print(result.criteria.employment_types_accepted)  # ["employed", "self_employed"]
```

## Match clients to banks

```python
from doc_parser import LoanMatcher, ClientProfile
from decimal import Decimal
import glob

# Parse all bank PDFs in a folder
banks = [parser.parse(f).criteria for f in glob.glob("banks/*.pdf")]

# Define your client's profile
client = ClientProfile(
    loan_amount_needed=Decimal("150000"),
    monthly_income=Decimal("12000"),
    employment_type="employed",
    employment_months=24,
    credit_score=720,
    age=34,
    nationality="Egyptian",
    region="Cairo",
)

# Get ranked results
matcher = LoanMatcher()
results = matcher.match(client, banks)

for r in results:
    print(f"{r.status.value:15} {r.bank_name:30} score={r.score:.2f}")
    for reason in r.reasons:
        print(f"  ✓ {reason}")
    for block in r.dealbreakers:
        print(f"  ✗ {block}")
```

```
best_fit        Bank of Cairo                  score=0.91
  ✓ DTI 18.3% within limit
  ✓ Competitive rate ≤ 14.5%
possible_fit    CIB Egypt                      score=0.68
  ✓ Has required collateral
not_suitable    HSBC Egypt                     score=0.00
  ✗ Income (12000/mo) below minimum (15000/mo)
```

## Supported document types

| Type | Extracted fields |
|------|-----------------|
| `loan_criteria` | Interest rates, loan limits, eligibility rules, fees, collateral, regions |
| `bank_statement` | Holder name, period, opening/closing balance, transaction summary |
| `identity` | Document type, issuing country, expiry (ID number NOT extracted — privacy) |
| `rate_card` | Product names, pricing tiers, validity dates |

## CLI

```bash
pip install universal-doc-parser

# Parse a single document
doc-parse bank_criteria.pdf --type loan_criteria --output criteria.json

# Match client to a folder of bank PDFs
doc-match --client client_profile.json --banks ./bank_pdfs/ --output report.json

# Auto-detect document type
doc-parse statement.pdf
```

## Output format

```json
{
  "bank_name": "Bank of Cairo",
  "product_name": "Personal Finance - Premium",
  "min_loan_amount": 10000,
  "max_loan_amount": 500000,
  "min_interest_rate": 12.5,
  "max_interest_rate": 18.0,
  "interest_rate_type": "variable",
  "min_term_months": 12,
  "max_term_months": 84,
  "min_income": 5000,
  "min_employment_months": 12,
  "employment_types_accepted": ["employed", "self_employed"],
  "citizenship_requirements": ["Egyptian", "GCC National"],
  "age_min": 21,
  "age_max": 60,
  "requires_collateral": false,
  "confidence": 0.94
}
```

## License

MIT © [Alper Nabil Gabra Zakher](https://github.com/AlperNab)

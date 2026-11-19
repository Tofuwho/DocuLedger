# ProcuLedger

**Automated Document-to-Ledger Extraction & Compliance Audit Engine**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Django 5.2](https://img.shields.io/badge/django-5.2-green.svg)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests: 17 Passed](https://img.shields.io/badge/pytest-17%20passed-brightgreen.svg)](tests/)

ProcuLedger converts digital supplier **Sales Invoices**, **Purchase Orders (POs)**, and **BIR Form 2307** certificates into verified, accounting-ready ledger entries. Built specifically for tax and accounting compliance under the **TRAIN Law**, **EOPT (Ease of Paying Taxes Act)**, and statutory Revenue Regulations.

---

## 🚀 Key Features

* **Zero-Login Recruiter Sandbox (`/`):** The root route loads straight into an interactive split-screen workspace pre-seeded with 3 authentic sample PDFs. Test the entire 1-click extract, audit, and export pipeline with zero login or API keys.
* **Lightweight Spatial Extraction:** Built on `PyMuPDF` (`fitz`) and `Pydantic` v2. Extracts spatial blocks, lines, and bounding boxes without heavy local ML/OCR dependencies (`torch`, `tesseract`, `easyocr`).
* **Offline / Demo Resilience:** Automatic deterministic rule and regex parser fallback when `OPENAI_API_KEY` or `GEMINI_API_KEY` is unset. The entire test suite and recruiter sandbox run 100% offline.
* **Strict Financial Precision:** All financial calculations and tax validations strictly use Python's `decimal.Decimal` (`ROUND_HALF_UP`). Floats are never used for currency.
* **Interactive Bounding Box Overlays:** Hover over any extracted field in the web workspace to visually illuminate its exact bounding box coordinates on the PDF preview.
* **1-Click Accounting & Statutory Exporters:**
  * **QuickBooks Online / Desktop CSV:** Formatted Bill import with account codes and 12% input tax mapping.
  * **Xero Accounting CSV:** Multi-line bill import with tax classifications.
  * **BIR SLSP Purchases (Schedule 3) CSV:** Official Summary List of Sales and Purchases submission format.

---

## 🏛️ Audit & Tax Rules Engine

ProcuLedger implements deterministic audit rules covering key statutory requirements:

| Rule Category | Description | Severity |
| :--- | :--- | :--- |
| **12% VAT Audit** | Validates `Vatable Sales * 0.12 == VAT Amount` with item-rounding tolerance (`±₱0.02`). Verifies reconciling sum `Vatable + VAT + Exempt + Zero-Rated == Total Due`. | `FAIL` |
| **TIN Format & Branch** | Enforces 12 to 14 digit format (`XXX-XXX-XXX-XXX`), checks branch code (`000` Head Office), flags legacy 9-digit TINs, and rejects dummy numbers. | `FAIL` / `WARN` |
| **Statutory Markers** | Verifies mandatory markers under the Tax Code: "VAT-Registered TIN" and Authority to Print ("ATP No.") or Permit to Use ("PTU No."). | `WARN` |
| **Duplicate Check** | Dual-tier protection: SHA-256 binary hash duplicate check + composite database match on `(supplier_tin, invoice_number)`. | `FAIL` |
| **PO 2-Way Match** | Reconciles Sales Invoice against Purchase Order totals and line-item unit prices to flag overbilling or unapproved price hikes. | `FAIL` / `WARN` |
| **BIR 2307 3-Way Match** | Cross-validates Creditable Withholding Tax (EWT): checks ATC code (e.g. `WC158` for 1%, `WI158` for 2%), matches income base against invoice net vatable sales, and verifies tax withheld. | `FAIL` |

---

## 📁 Repository Architecture

```text
ProcuLedger/
├── config/                     # Django project settings, URLs, WSGI, ASGI
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/
│   ├── ledger/                 # Core relational models, audit logs & admin
│   │   ├── models.py           # Document, InvoiceLedgerEntry, PurchaseOrderEntry, TaxCertificate2307Entry, AuditLog
│   │   └── admin.py
│   ├── extractor/              # Tier 1 PyMuPDF spatial parser + Tier 2 Pydantic mapper
│   │   ├── schemas.py          # Pydantic v2 extraction schemas & BoundingBox
│   │   ├── pdf_parser.py       # Spatial text, block, and coordinate extractor
│   │   └── llm_mapper.py       # Structured extractor + deterministic offline fallback
│   ├── auditor/                # Tax & compliance audit engine
│   │   ├── rules.py            # 12% VAT, TIN validation, BIR markers, PO & 2307 matching
│   │   └── exporters.py        # QuickBooks, Xero, and BIR SLSP Schedule 3 CSV generators
│   ├── api/                    # Django REST Framework endpoints
│   │   ├── serializers.py      # REST serializers
│   │   ├── views.py            # Upload, extract, audit, 1-click pipeline, export views
│   │   └── urls.py
│   └── web/                    # Zero-login split-screen UI & sample seeding
│       ├── management/commands/
│       │   └── seed_ph_samples.py # Programmatic ReportLab generator for 3 authentic sample PDFs
│       ├── templates/web/
│       │   └── workspace.html  # Split-screen responsive recruiter workspace
│       ├── static/web/
│       │   ├── css/workspace.css
│       │   └── js/workspace.js
│       └── views.py
├── tests/                      # Automated test suite (17 passed)
│   ├── conftest.py             # Shared fixtures & sample seeding
│   ├── test_pdf_parser.py      # PyMuPDF spatial & coordinate tests
│   ├── test_audit_rules.py     # 12% VAT math, TIN formats, duplicate checks
│   ├── test_po_matching.py     # 2-way PO & 3-way BIR 2307 withholding tax tests
│   └── test_api_sandbox.py     # End-to-end sandbox REST endpoints & export tests
├── manage.py
├── requirements.txt
├── pytest.ini
└── README.md
```

---

## 🛠️ Quickstart Installation

### 1. Clone & Set Up Virtual Environment

```bash
git clone https://github.com/Tofuwho/DocuLedger.git
cd DocuLedger

# Create Python 3.11 virtual environment
python -m venv .venv
```

```bash
# Activate on Windows:
.venv\Scripts\activate
# Activate on Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Apply Migrations & Seed Samples

```bash
python manage.py migrate
python manage.py seed_ph_samples
```

This generates three authentic test PDFs using ReportLab:
1. `PH_Sample_Invoice_Compliant.pdf`: 100% compliant Sales Invoice with 12% VAT, valid 12-digit TIN, and BIR ATP.
2. `PH_Sample_Invoice_VAT_Discrepancy.pdf`: Non-compliant invoice featuring an intentional 10% VAT calculation error and defective TIN.
3. `PH_Sample_PO_and_2307_Pack.pdf`: 3-Way Match test pack including Purchase Order `PO-2024-8891` and BIR Form 2307 Creditable Withholding Tax certificate.

### 3. Run Development Server

```bash
python manage.py runserver
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) in your browser. The zero-login recruiter sandbox will load immediately.

---

## 🧪 Running the Test Suite

Run the full pytest suite:

```bash
pytest
```

---

## 🔌 REST API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/documents/extract-and-audit/` | **1-Click Recruiter Sandbox Pipeline:** Uploads or selects document, extracts spatial fields, evaluates audit rules, and returns unified ledger data. |
| `GET` | `/api/documents/samples/` | Lists pre-seeded sample PDFs with metadata. |
| `POST` | `/api/documents/upload/` | Uploads a PDF, hashes it via SHA-256, and extracts spatial layout. |
| `POST` | `/api/documents/<id>/extract/` | Executes schema extraction and maps to Pydantic models. |
| `POST` | `/api/documents/<id>/audit/` | Executes tax compliance rules and writes audit logs. |
| `GET` | `/api/documents/<id>/export/quickbooks/` | Downloads QuickBooks Online/Desktop Bill CSV. |
| `GET` | `/api/documents/<id>/export/xero/` | Downloads Xero Accounting Bill CSV. |
| `GET` | `/api/documents/export/slsp/` | Downloads official BIR SLSP Schedule 3 Purchases CSV. |
| `GET` | `/api/ledger/` | Lists all ledger entries. |
| `GET` | `/api/schema/` | Returns OpenAPI 3.0 specification. |

---

## ⚖️ License

MIT License. Designed and engineered for businesses, accounting professionals, and enterprise compliance.

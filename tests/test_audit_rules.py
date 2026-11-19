"""
Unit tests for Philippine Tax, TIN, VAT, and Duplicate Audit Rules.
Verifies strict Decimal precision and compliance rule logic.
"""

from decimal import Decimal
import pytest

from apps.auditor.rules import (
    PhilippineTaxAuditor,
    run_full_compliance_audit,
)
from apps.extractor.schemas import ExtractedInvoice
from apps.ledger.models import Document, InvoiceLedgerEntry


def test_12_percent_vat_calculation_pass():
    # ₱100,000.00 vatable sales -> ₱12,000.00 VAT -> ₱112,000.00 Total
    results = PhilippineTaxAuditor.audit_12_percent_vat(
        vatable_sales=Decimal("100000.00"),
        vat_amount=Decimal("12000.00"),
        vat_exempt_sales=Decimal("0.00"),
        zero_rated_sales=Decimal("0.00"),
        total_amount=Decimal("112000.00"),
    )
    assert len(results) == 2
    assert results[0].status == "PASS"
    assert results[1].status == "PASS"


def test_12_percent_vat_calculation_rounding_tolerance():
    # Small rounding variance of ₱0.01 must be tolerated under BIR rules
    results = PhilippineTaxAuditor.audit_12_percent_vat(
        vatable_sales=Decimal("150000.00"),
        vat_amount=Decimal("18000.01"),  # 1 centavo variance
        total_amount=Decimal("168000.01"),
    )
    assert results[0].status == "PASS"
    assert results[1].status == "PASS"


def test_12_percent_vat_calculation_fail_discrepancy():
    # Defective invoice states 10% VAT instead of 12%
    results = PhilippineTaxAuditor.audit_12_percent_vat(
        vatable_sales=Decimal("50000.00"),
        vat_amount=Decimal("5000.00"),  # Expected 6,000.00
        total_amount=Decimal("55000.00"),
    )
    assert results[0].status == "FAIL"
    assert "Discrepancy" in results[0].message
    assert results[0].details["expected_vat"] == "6000.00"


def test_tin_validation_rules():
    # 1. Valid 12-digit standard TIN with Head Office branch code
    r1 = PhilippineTaxAuditor.validate_tin("123-456-789-000")
    assert r1.status == "PASS"
    assert r1.details["branch_code"] == "000"

    # 2. Legacy 9-digit TIN without branch code -> WARNING
    r2 = PhilippineTaxAuditor.validate_tin("123-456-789")
    assert r2.status == "WARNING"

    # 3. Defective digit count (e.g. 8 digits) -> FAIL
    r3 = PhilippineTaxAuditor.validate_tin("999-111-22")
    assert r3.status == "FAIL"

    # 4. Dummy TIN (all zeros) -> FAIL
    r4 = PhilippineTaxAuditor.validate_tin("000-000-000-000")
    assert r4.status == "FAIL"

    # 5. Empty TIN -> FAIL
    r5 = PhilippineTaxAuditor.validate_tin("")
    assert r5.status == "FAIL"


def test_bir_compliance_markers():
    # Compliant invoice text with VAT-Registered and ATP
    text_ok = "MEGAWORLD TECH INC. VAT-REGISTERED TIN: 123-456-789-000 BIR ATP NO: ATP-2024-001"
    r_ok = PhilippineTaxAuditor.audit_bir_compliance(text_ok, atp_number="ATP-2024-001")
    assert r_ok.status == "PASS"

    # Missing ATP
    text_no_atp = "QUEZON CORP. VAT-REGISTERED TIN: 123-456-789-000"
    r_warn = PhilippineTaxAuditor.audit_bir_compliance(text_no_atp, atp_number=None)
    assert r_warn.status == "WARNING"


@pytest.mark.django_db
def test_duplicate_invoice_detection():
    # Create test document and entry
    doc = Document.objects.create(
        file_name="invoice_test.pdf",
        file_hash="abcde12345hash00000000000000000000000000000000000000000000000000",
        file_size=1024,
        status="AUDITED"
    )
    InvoiceLedgerEntry.objects.create(
        document=doc,
        supplier_name="Test Supplier",
        supplier_tin="123-456-789-000",
        invoice_number="INV-DUPLICATE-001",
        total_amount=Decimal("1000.00")
    )

    # 1. Exact SHA-256 duplicate
    r_hash = PhilippineTaxAuditor.audit_duplicate(
        file_hash="abcde12345hash00000000000000000000000000000000000000000000000000",
        supplier_tin="999-888-777-000",
        invoice_number="INV-OTHER-999"
    )
    assert r_hash.status == "FAIL"
    assert "Exact binary duplicate" in r_hash.message

    # 2. Composite key duplicate (same supplier_tin + invoice_number)
    r_comp = PhilippineTaxAuditor.audit_duplicate(
        file_hash="different_hash_1111111111111111111111111111111111111111111111111111",
        supplier_tin="123-456-789-000",
        invoice_number="INV-DUPLICATE-001"
    )
    assert r_comp.status == "FAIL"
    assert "Duplicate Invoice Number" in r_comp.message

"""
Unit tests for 2-Way and 3-Way Cross Reconciliation (Invoice vs PO vs BIR Form 2307).
"""

from decimal import Decimal
import pytest

from apps.auditor.rules import PhilippineTaxAuditor
from apps.extractor.schemas import ExtractedInvoice, Extracted2307
from apps.ledger.models import PurchaseOrderEntry, PurchaseOrderLineItem, Document


@pytest.mark.django_db
def test_po_2way_matching_success():
    # Setup PO
    po = PurchaseOrderEntry.objects.create(
        po_number="PO-TEST-001",
        vendor_name="Megaworld Tech Distributors Inc.",
        buyer_name="Acme Philippines Corporation",
        total_amount=Decimal("168000.00")
    )

    inv = ExtractedInvoice(
        invoice_number="SI-001",
        supplier_name="Megaworld Tech Distributors Inc.",
        supplier_tin="123-456-789-000",
        buyer_name="Acme Philippines Corporation",
        vatable_sales=Decimal("150000.00"),
        vat_amount=Decimal("18000.00"),
        total_amount=Decimal("168000.00"),
        po_reference="PO-TEST-001"
    )

    res = PhilippineTaxAuditor.audit_po_matching(inv)
    assert res.status == "PASS"
    assert "successfully reconciled" in res.message


@pytest.mark.django_db
def test_po_2way_matching_overbilling_fail():
    po = PurchaseOrderEntry.objects.create(
        po_number="PO-TEST-002",
        vendor_name="Megaworld Tech Distributors Inc.",
        buyer_name="Acme Philippines Corporation",
        total_amount=Decimal("100000.00")
    )

    inv = ExtractedInvoice(
        invoice_number="SI-002",
        supplier_name="Megaworld Tech Distributors Inc.",
        supplier_tin="123-456-789-000",
        buyer_name="Acme Philippines Corporation",
        vatable_sales=Decimal("150000.00"),
        vat_amount=Decimal("18000.00"),
        total_amount=Decimal("168000.00"),  # Exceeds PO by 68,000.00!
        po_reference="PO-TEST-002"
    )

    res = PhilippineTaxAuditor.audit_po_matching(inv)
    assert res.status == "FAIL"
    assert "exceeds Purchase Order" in res.message
    assert res.details["variance"] == "68000.00"


def test_form_2307_3way_matching_success():
    inv = ExtractedInvoice(
        invoice_number="SI-001",
        supplier_name="Megaworld Tech Distributors Inc.",
        supplier_tin="123-456-789-000",
        buyer_name="Acme Philippines Corporation",
        vatable_sales=Decimal("150000.00"),
        vat_amount=Decimal("18000.00"),
        total_amount=Decimal("168000.00"),
    )

    cert = Extracted2307(
        payor_name="Acme Philippines Corporation",
        payor_tin="987-654-321-000",
        payee_name="Megaworld Tech Distributors Inc.",
        payee_tin="123-456-789-000",
        atc_code="WC158",
        income_payment=Decimal("150000.00"),
        tax_rate=Decimal("0.01"),  # 1%
        tax_withheld=Decimal("1500.00"),  # 1% of 150,000.00
    )

    res = PhilippineTaxAuditor.audit_form_2307_ewt(inv, cert)
    assert res.status == "PASS"
    assert "perfectly balances" in res.message


def test_form_2307_3way_matching_discrepancy_fail():
    inv = ExtractedInvoice(
        invoice_number="SI-001",
        supplier_name="Megaworld Tech Distributors Inc.",
        supplier_tin="123-456-789-000",
        buyer_name="Acme Philippines Corporation",
        vatable_sales=Decimal("150000.00"),
        vat_amount=Decimal("18000.00"),
        total_amount=Decimal("168000.00"),
    )

    # Defective 2307 with wrong withholding tax (₱1,000 instead of ₱1,500)
    cert = Extracted2307(
        payor_name="Acme Philippines Corporation",
        payor_tin="987-654-321-000",
        payee_name="Megaworld Tech Distributors Inc.",
        payee_tin="123-456-789-000",
        atc_code="WC158",
        income_payment=Decimal("150000.00"),
        tax_rate=Decimal("0.01"),
        tax_withheld=Decimal("1000.00"),
    )

    res = PhilippineTaxAuditor.audit_form_2307_ewt(inv, cert)
    assert res.status == "FAIL"
    assert "Expected withholding" in res.message

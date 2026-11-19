"""
End-to-End REST API Sandbox Tests for DocuLedger PH.
Runs completely offline with zero external API dependencies.
"""

import io
from decimal import Decimal
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.ledger.models import Document, InvoiceLedgerEntry


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
def test_root_workspace_loads_zero_login(api_client):
    """Verifies that the root route (/) renders the recruiter sandbox workspace with HTTP 200."""
    response = api_client.get('/')
    assert response.status_code == 200
    assert b"ProcuLedger" in response.content
    assert b"1-Click Extract & Audit" in response.content


@pytest.mark.django_db
def test_sample_documents_endpoint(api_client):
    """Verifies pre-seeded Philippine sample documents listing."""
    url = reverse('api:document_samples')
    response = api_client.get(url)
    assert response.status_code == 200
    data = response.json()
    assert 'samples' in data
    assert len(data['samples']) >= 3
    names = [s['file_name'] for s in data['samples']]
    assert any("Compliant" in n for n in names)
    assert any("VAT_Discrepancy" in n for n in names)
    assert any("PO_and_2307_Pack" in n for n in names)


@pytest.mark.django_db
def test_1click_extract_and_audit_compliant_invoice(api_client):
    """
    Tests the primary 1-click recruiter sandbox endpoint on the compliant invoice.
    Must achieve 100% compliance score with PASSED status.
    """
    doc = Document.objects.filter(file_name="PH_Sample_Invoice_Compliant.pdf").first()
    assert doc is not None

    url = reverse('api:document_extract_and_audit')
    response = api_client.post(url, {'document_id': doc.id}, format='json')
    assert response.status_code == 200
    data = response.json()

    assert data['document']['id'] == doc.id
    assert data['extraction']['document_type'] == 'SALES_INVOICE'
    
    # Verify extraction accuracy
    ext = data['extraction']['extracted_data']
    assert ext['invoice_number'] == 'SI-2024-8891'
    assert '123-456-789-000' in ext['supplier_tin']
    assert Decimal(str(ext['vatable_sales'])) == Decimal('150000.00')
    assert Decimal(str(ext['vat_amount'])) == Decimal('18000.00')
    assert Decimal(str(ext['total_amount'])) == Decimal('168000.00')

    # Verify Audit results: 100% compliant!
    audit = data['audit']
    assert audit['status'] == 'PASSED'
    assert audit['score'] == 100
    assert "100% Compliant" in audit['summary']

    # Verify Ledger entry persisted
    ledger = data['ledger_entry']
    assert ledger is not None
    assert ledger['invoice_number'] == 'SI-2024-8891'
    assert len(ledger['line_items']) == 2


@pytest.mark.django_db
def test_1click_extract_and_audit_vat_discrepancy(api_client):
    """
    Tests 1-click extract & audit on the non-compliant invoice.
    Must catch the 10% VAT calculation error and defective TIN.
    """
    doc = Document.objects.filter(file_name="PH_Sample_Invoice_VAT_Discrepancy.pdf").first()
    assert doc is not None

    url = reverse('api:document_extract_and_audit')
    response = api_client.post(url, {'document_id': doc.id}, format='json')
    assert response.status_code == 200
    data = response.json()

    audit = data['audit']
    assert audit['status'] == 'FAILED'
    assert audit['score'] < 70

    # Ensure rule failures are explicitly recorded
    rule_names = [r['rule_name'] for r in audit['results'] if r['status'] == 'FAIL']
    assert any("12% Philippine VAT Calculation" in n for n in rule_names)
    assert any("TIN Format" in n for n in rule_names)


@pytest.mark.django_db
def test_exporters_endpoints(api_client):
    """Verifies QuickBooks, Xero, and BIR SLSP CSV exports."""
    doc = Document.objects.filter(file_name="PH_Sample_Invoice_Compliant.pdf").first()

    # Run extract and audit to ensure ledger entry exists
    api_client.post(reverse('api:document_extract_and_audit'), {'document_id': doc.id}, format='json')

    # 1. QuickBooks CSV
    qb_url = reverse('api:export_quickbooks', kwargs={'pk': doc.id})
    qb_res = api_client.get(qb_url)
    assert qb_res.status_code == 200
    assert qb_res['Content-Type'] == 'text/csv'
    assert b"Bill No,Vendor,Bill Date" in qb_res.content
    assert b"SI-2024-8891" in qb_res.content

    # 2. Xero CSV
    xero_url = reverse('api:export_xero', kwargs={'pk': doc.id})
    xero_res = api_client.get(xero_url)
    assert xero_res.status_code == 200
    assert xero_res['Content-Type'] == 'text/csv'
    assert b"*ContactName,*InvoiceNumber" in xero_res.content

    # 3. BIR SLSP Schedule 3 CSV
    slsp_url = reverse('api:export_slsp') + f"?document_id={doc.id}"
    slsp_res = api_client.get(slsp_url)
    assert slsp_res.status_code == 200
    assert slsp_res['Content-Type'] == 'text/csv'
    assert b"Taxable Month,Taxpayer TIN,Branch Code" in slsp_res.content
    assert b"150000.00,18000.00" in slsp_res.content

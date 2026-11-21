"""
Tests for ProcuLedger AI Auditor Copilot.
Verifies automated briefing generation, contextual tax Q&A, and REST endpoint.
"""

import pytest
from rest_framework.test import APIClient
from django.urls import reverse
from apps.ledger.models import Document
from apps.auditor.copilot import generate_audit_briefing, answer_copilot_question


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
def test_copilot_briefing_generation():
    doc = Document.objects.filter(file_name__contains='Compliant').first()
    assert doc is not None

    extraction = {
        'document_type': 'SALES_INVOICE',
        'extracted_data': {
            'supplier_name': 'MEGAWORLD TECH DISTRIBUTORS INC.',
            'supplier_tin': '123-456-789-000',
            'buyer_name': 'Acme Philippines Corporation',
            'buyer_tin': '987-654-321-000',
            'invoice_number': 'SI-2024-8891',
            'vatable_sales': 150000.0,
            'vat_amount': 18000.0,
            'total_amount': 168000.0,
            'po_reference': 'PO-2024-8891',
        }
    }
    audit = {
        'status': 'PASSED',
        'score': 100,
        'results': [
            {'rule_name': '12% Philippine VAT Calculation', 'status': 'PASS', 'message': 'VAT matches 12%'}
        ]
    }

    briefing = generate_audit_briefing(doc, extraction, audit)
    assert briefing['status'] == 'PASSED'
    assert briefing['score'] == 100
    assert briefing['verdict_badge'] == 'COMPLIANT'
    assert len(briefing['points_to_know']) > 0
    assert len(briefing['recommended_actions']) > 0
    assert len(briefing['suggested_questions']) > 0


@pytest.mark.django_db
def test_copilot_discrepancy_explanation():
    doc = Document.objects.filter(file_name__contains='VAT_Discrepancy').first()
    assert doc is not None

    extraction = {
        'document_type': 'SALES_INVOICE',
        'extracted_data': {
            'supplier_name': 'Acme Office Supplies Inc.',
            'supplier_tin': '12-345-678',
            'invoice_number': 'SI-2024-9902',
            'vatable_sales': 80000.0,
            'vat_amount': 8000.0,
            'total_amount': 88000.0,
        }
    }
    audit = {
        'status': 'FAILED',
        'score': 20,
        'results': [
            {'rule_name': '12% Philippine VAT Calculation', 'status': 'FAIL', 'message': 'VAT calculation failed'},
            {'rule_name': 'Supplier TIN Format & Checksum', 'status': 'FAIL', 'message': 'Invalid 8-digit TIN'}
        ]
    }

    briefing = generate_audit_briefing(doc, extraction, audit)
    assert briefing['status'] == 'FAILED'
    assert briefing['score'] == 20
    assert briefing['verdict_badge'] == 'NON_COMPLIANT'
    # Must flag the critical VAT discrepancy
    assert any('VAT' in p['title'] for p in briefing['points_to_know'])


@pytest.mark.django_db
def test_copilot_contextual_qa():
    doc = Document.objects.first()
    extraction = {
        'extracted_data': {
            'supplier_name': 'Test Supplier',
            'invoice_number': 'SI-001',
            'vatable_sales': 100000.0,
            'vat_amount': 12000.0,
            'total_amount': 112000.0,
            'supplier_tin': '123-456-789-000'
        }
    }
    audit = {'status': 'PASSED', 'score': 100, 'results': []}

    # Test VAT question
    ans_vat = answer_copilot_question("How is the 12% VAT computed?", doc, extraction, audit)
    assert "12% Philippine VAT Breakdown" in ans_vat
    assert "₱100,000.00" in ans_vat

    # Test Input Tax question
    ans_tax = answer_copilot_question("Can we claim input tax?", doc, extraction, audit)
    assert "Input Tax Claim Eligibility" in ans_tax

    # Test 2307 question
    ans_2307 = answer_copilot_question("What is BIR Form 2307 and WC158?", doc, extraction, audit)
    assert "BIR Form 2307" in ans_2307
    assert "WC158" in ans_2307


@pytest.mark.django_db
def test_copilot_chat_endpoint(api_client):
    doc = Document.objects.filter(file_name__contains='Compliant').first()
    assert doc is not None

    url = reverse('api:copilot_chat')
    
    # 1. Initial briefing request (no message)
    res_briefing = api_client.post(url, {'document_id': doc.id}, format='json')
    assert res_briefing.status_code == 200
    assert 'briefing' in res_briefing.data
    assert res_briefing.data['briefing']['score'] == 100

    # 2. Contextual question
    res_q = api_client.post(url, {
        'document_id': doc.id,
        'message': 'Can we legally claim input tax on this invoice?'
    }, format='json')
    assert res_q.status_code == 200
    assert 'reply' in res_q.data
    assert 'Input Tax' in res_q.data['reply']
    assert len(res_q.data['suggested_questions']) > 0


@pytest.mark.django_db
def test_copilot_vat_discrepancy_math_breakdown(api_client):
    doc = Document.objects.filter(file_name__contains='VAT_Discrepancy').first()
    assert doc is not None

    url = reverse('api:copilot_chat')
    res = api_client.post(url, {
        'document_id': doc.id,
        'message': 'Explain the 12% VAT calculation in detail'
    }, format='json')

    assert res.status_code == 200
    reply = res.data['reply']
    assert '12% Philippine VAT Breakdown' in reply
    assert '₱50,000.00' in reply
    assert '₱5,000.00' in reply
    assert '10.00%' in reply
    assert 'Severe discrepancy' in reply

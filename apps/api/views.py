"""
REST API Views for DocuLedger PH.
Includes upload, extraction, audit, 1-click sandbox pipeline, and export endpoints.
"""

import os
from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.core.files.base import ContentFile
from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from apps.ledger.models import (
    Document,
    InvoiceLedgerEntry,
    InvoiceLineItem,
    PurchaseOrderEntry,
    TaxCertificate2307Entry,
    AuditLog,
)
from apps.extractor.pdf_parser import SpatialPDFParser
from apps.extractor.llm_mapper import DocumentExtractor
from apps.extractor.schemas import ExtractedInvoice
from apps.auditor.rules import run_full_compliance_audit
from apps.auditor.exporters import LedgerExporter
from .serializers import (
    DocumentSerializer,
    InvoiceLedgerEntrySerializer,
    AuditLogSerializer,
)


class DocumentUploadView(views.APIView):
    """Uploads a PDF document and computes SHA-256 binary hash."""
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'No file was uploaded.'}, status=status.HTTP_400_BAD_REQUEST)

        file_bytes = file_obj.read()
        file_size = len(file_bytes)
        file_hash = Document.calculate_sha256(file_bytes)

        # Parse spatial data and raw text
        with SpatialPDFParser(file_bytes) as parser:
            raw_text = parser.extract_full_text()
            page_count = parser.page_count
            extractor = DocumentExtractor(parser)
            doc_type = extractor.detect_document_type()
            
            blocks = []
            if page_count > 0:
                blocks = parser.extract_spatial_blocks(0)
            dims = parser.get_page_dimensions(0) if page_count > 0 else (612, 792)

        file_obj.seek(0)
        doc = Document.objects.create(
            file=file_obj,
            file_name=file_obj.name,
            file_hash=file_hash,
            file_size=file_size,
            document_type=doc_type,
            raw_text=raw_text,
            spatial_data={
                "page_count": page_count,
                "width": dims[0],
                "height": dims[1],
                "blocks": blocks,
            },
            status='PENDING'
        )

        serializer = DocumentSerializer(doc, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DocumentExtractView(views.APIView):
    """Executes spatial extraction and Pydantic schema mapping."""

    def post(self, request, pk, *args, **kwargs):
        doc = get_object_or_404(Document, pk=pk)
        
        # Read file bytes
        doc.file.seek(0)
        file_bytes = doc.file.read()

        with SpatialPDFParser(file_bytes) as parser:
            extractor = DocumentExtractor(parser)
            result = extractor.extract()

        # Update document record
        doc.document_type = result.document_type
        doc.status = 'EXTRACTED'
        doc.save()

        # If Sales Invoice, persist into InvoiceLedgerEntry
        ledger_entry = None
        if result.document_type == 'SALES_INVOICE':
            inv_data: ExtractedInvoice = result.data
            
            # Format dates safely
            inv_date = None
            if inv_data.invoice_date:
                try:
                    from django.utils.dateparse import parse_date
                    inv_date = parse_date(inv_data.invoice_date)
                except Exception:
                    pass

            ledger_entry, created = InvoiceLedgerEntry.objects.update_or_create(
                document=doc,
                defaults={
                    'supplier_name': inv_data.supplier_name,
                    'supplier_tin': inv_data.supplier_tin,
                    'supplier_address': inv_data.supplier_address or '',
                    'buyer_name': inv_data.buyer_name,
                    'buyer_tin': inv_data.buyer_tin or '',
                    'invoice_number': inv_data.invoice_number,
                    'invoice_date': inv_date,
                    'vatable_sales': inv_data.vatable_sales,
                    'vat_amount': inv_data.vat_amount,
                    'vat_exempt_sales': inv_data.vat_exempt_sales,
                    'zero_rated_sales': inv_data.zero_rated_sales,
                    'total_amount': inv_data.total_amount,
                    'atp_number': inv_data.atp_number or '',
                    'po_reference': inv_data.po_reference or '',
                }
            )

            # Recreate line items
            ledger_entry.line_items.all().delete()
            for item in inv_data.line_items:
                InvoiceLineItem.objects.create(
                    ledger_entry=ledger_entry,
                    item_code=item.item_code or '',
                    description=item.description,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    amount=item.amount,
                    bbox=item.bbox.model_dump() if item.bbox else {}
                )

        return Response({
            'document_id': doc.id,
            'document_type': result.document_type,
            'extracted_data': result.data.model_dump(),
            'bounding_boxes': result.bounding_boxes,
            'ledger_entry_id': ledger_entry.id if ledger_entry else None,
        })


class DocumentAuditView(views.APIView):
    """Executes deterministic Philippine tax, TIN, duplicate, and PO compliance rules."""

    def post(self, request, pk, *args, **kwargs):
        doc = get_object_or_404(Document, pk=pk)
        ledger_entry = getattr(doc, 'invoice_entry', None)

        if not ledger_entry:
            # Trigger extract first if not yet extracted
            extract_view = DocumentExtractView()
            extract_view.post(request, pk)
            doc.refresh_from_db()
            ledger_entry = getattr(doc, 'invoice_entry', None)

        if not ledger_entry:
            return Response({'error': 'Document could not be converted to a Sales Invoice ledger entry.'}, status=status.HTTP_400_BAD_REQUEST)

        # Build ExtractedInvoice schema from ledger entry
        inv_data = ExtractedInvoice(
            invoice_number=ledger_entry.invoice_number,
            invoice_date=ledger_entry.invoice_date.strftime("%Y-%m-%d") if ledger_entry.invoice_date else None,
            supplier_name=ledger_entry.supplier_name,
            supplier_tin=ledger_entry.supplier_tin,
            supplier_address=ledger_entry.supplier_address,
            buyer_name=ledger_entry.buyer_name,
            buyer_tin=ledger_entry.buyer_tin,
            vatable_sales=ledger_entry.vatable_sales,
            vat_amount=ledger_entry.vat_amount,
            vat_exempt_sales=ledger_entry.vat_exempt_sales,
            zero_rated_sales=ledger_entry.zero_rated_sales,
            total_amount=ledger_entry.total_amount,
            atp_number=ledger_entry.atp_number,
            po_reference=ledger_entry.po_reference
        )

        # Check for 2307 companion
        cert_2307 = None
        tax_cert = TaxCertificate2307Entry.objects.filter(payee_tin=ledger_entry.supplier_tin).first()
        if tax_cert:
            from apps.extractor.schemas import Extracted2307
            cert_2307 = Extracted2307(
                payor_name=tax_cert.payor_name,
                payor_tin=tax_cert.payor_tin,
                payee_name=tax_cert.payee_name,
                payee_tin=tax_cert.payee_tin,
                atc_code=tax_cert.atc_code,
                income_payment=tax_cert.income_payment,
                tax_rate=tax_cert.tax_rate,
                tax_withheld=tax_cert.tax_withheld
            )

        # Execute Audit
        audit_report = run_full_compliance_audit(
            document_id=doc.id,
            extracted_invoice=inv_data,
            raw_text=doc.raw_text,
            file_hash=doc.file_hash,
            po_reference=ledger_entry.po_reference,
            cert_2307=cert_2307
        )

        # Clear existing logs for this document and save new ones
        doc.audit_logs.all().delete()
        for r in audit_report.results:
            AuditLog.objects.create(
                document=doc,
                rule_name=r.rule_name,
                rule_category=r.rule_category,
                status=r.status,
                message=r.message,
                details=r.details
            )

        # Update ledger entry and document status
        ledger_entry.audit_status = audit_report.status
        ledger_entry.audit_score = audit_report.score
        ledger_entry.save()

        doc.status = 'AUDITED'
        doc.save()

        return Response(audit_report.to_dict())


class DocumentExtractAndAuditView(views.APIView):
    """
    1-Click Recruiter Sandbox Pipeline:
    Uploads or selects document -> Extracts spatial text -> Maps schema ->
    Runs compliance audit -> Saves ledger entry -> Returns unified payload.
    """
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, *args, **kwargs):
        doc = None
        doc_id = request.data.get('document_id')
        file_obj = request.FILES.get('file')

        if doc_id:
            doc = get_object_or_404(Document, pk=doc_id)
        elif file_obj:
            upload_view = DocumentUploadView()
            upload_res = upload_view.post(request)
            if upload_res.status_code != status.HTTP_201_CREATED:
                return upload_res
            doc = Document.objects.get(pk=upload_res.data['id'])
        else:
            return Response({'error': 'Either document_id or file must be provided.'}, status=status.HTTP_400_BAD_REQUEST)

        # Run extraction
        extract_view = DocumentExtractView()
        extract_res = extract_view.post(request, pk=doc.id)

        # Run audit
        audit_view = DocumentAuditView()
        audit_res = audit_view.post(request, pk=doc.id)

        doc.refresh_from_db()
        ledger_entry = getattr(doc, 'invoice_entry', None)
        ledger_data = InvoiceLedgerEntrySerializer(ledger_entry).data if ledger_entry else None

        return Response({
            'document': DocumentSerializer(doc, context={'request': request}).data,
            'extraction': extract_res.data,
            'audit': audit_res.data,
            'ledger_entry': ledger_data,
        })


class SampleDocumentsView(views.APIView):
    """Lists pre-seeded Philippine sample documents for the zero-login recruiter sandbox."""

    def get(self, request, *args, **kwargs):
        samples = Document.objects.filter(file_name__startswith='PH_Sample_').order_by('id')
        data = []
        for s in samples:
            data.append({
                'id': s.id,
                'file_name': s.file_name,
                'file_url': request.build_absolute_uri(s.file.url) if s.file else '',
                'document_type': s.document_type,
                'status': s.status,
                'description': (
                    "Clean Compliant Invoice with 12% VAT, valid TIN, and BIR ATP"
                    if "Compliant" in s.file_name else
                    "Non-Compliant Invoice with intentional 10% VAT error and malformed TIN"
                    if "VAT_Discrepancy" in s.file_name else
                    "Complete 3-Way Match Pack (Sales Invoice + PO-2024-8891 + BIR Form 2307)"
                )
            })
        return Response({'samples': data})


class ExportQuickBooksView(views.APIView):
    """Downloads QuickBooks Online/Desktop compatible Bill CSV."""

    def get(self, request, pk, *args, **kwargs):
        doc = get_object_or_404(Document, pk=pk)
        ledger_entry = getattr(doc, 'invoice_entry', None)
        if not ledger_entry:
            return Response({'error': 'Invoice ledger entry not found.'}, status=status.HTTP_404_NOT_FOUND)

        csv_content = LedgerExporter.export_quickbooks_csv(ledger_entry)
        response = HttpResponse(csv_content, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="QuickBooks_Bill_{ledger_entry.invoice_number}.csv"'
        return response


class ExportXeroView(views.APIView):
    """Downloads Xero compatible Bill CSV."""

    def get(self, request, pk, *args, **kwargs):
        doc = get_object_or_404(Document, pk=pk)
        ledger_entry = getattr(doc, 'invoice_entry', None)
        if not ledger_entry:
            return Response({'error': 'Invoice ledger entry not found.'}, status=status.HTTP_404_NOT_FOUND)

        csv_content = LedgerExporter.export_xero_csv(ledger_entry)
        response = HttpResponse(csv_content, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="Xero_Bill_{ledger_entry.invoice_number}.csv"'
        return response


class ExportSLSPView(views.APIView):
    """Downloads BIR SLSP (Summary List of Sales and Purchases) Schedule 3 CSV."""

    def get(self, request, *args, **kwargs):
        doc_id = request.query_params.get('document_id')
        if doc_id:
            entries = list(InvoiceLedgerEntry.objects.filter(document_id=doc_id))
        else:
            entries = list(InvoiceLedgerEntry.objects.all())

        csv_content = LedgerExporter.export_bir_slsp_csv(entries)
        response = HttpResponse(csv_content, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="BIR_SLSP_Purchases_Schedule3.csv"'
        return response


class LedgerListView(views.APIView):
    """Lists all ledger entries."""

    def get(self, request, *args, **kwargs):
        entries = InvoiceLedgerEntry.objects.all().select_related('document').prefetch_related('line_items')
        serializer = InvoiceLedgerEntrySerializer(entries, many=True)
        return Response({'count': entries.count(), 'entries': serializer.data})


class OpenAPISchemaView(views.APIView):
    """Returns OpenAPI schema definition for ProcuLedger REST API."""

    def get(self, request, *args, **kwargs):
        schema = {
            "openapi": "3.0.3",
            "info": {
                "title": "ProcuLedger REST API",
                "version": "1.1.0",
                "description": "Automated Document-to-Ledger Extraction and Compliance Audit Engine"
            },
            "paths": {
                "/api/documents/upload/": {"post": {"summary": "Upload a PDF document"}},
                "/api/documents/{id}/extract/": {"post": {"summary": "Extract spatial text and map schema"}},
                "/api/documents/{id}/audit/": {"post": {"summary": "Run Philippine compliance audit"}},
                "/api/documents/extract-and-audit/": {"post": {"summary": "1-Click upload/select, extract, and audit pipeline"}},
                "/api/documents/samples/": {"get": {"summary": "List pre-seeded Philippine sample documents"}},
                "/api/documents/{id}/export/quickbooks/": {"get": {"summary": "Export QuickBooks Bill CSV"}},
                "/api/documents/{id}/export/xero/": {"get": {"summary": "Export Xero Bill CSV"}},
                "/api/documents/export/slsp/": {"get": {"summary": "Export BIR SLSP Purchases CSV"}},
                "/api/ledger/": {"get": {"summary": "List all ledger entries"}},
            }
        }
        return Response(schema)

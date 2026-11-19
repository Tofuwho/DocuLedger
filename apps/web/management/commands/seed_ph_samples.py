"""
Management command to programmatically generate 3 authentic Philippine sample documents
and seed the zero-login recruiter sandbox database.
"""

import os
from io import BytesIO
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from apps.ledger.models import (
    Document,
    InvoiceLedgerEntry,
    InvoiceLineItem,
    PurchaseOrderEntry,
    PurchaseOrderLineItem,
    TaxCertificate2307Entry,
)
from apps.extractor.pdf_parser import SpatialPDFParser


class Command(BaseCommand):
    help = "Generate authentic Philippine sample PDFs and seed the recruiter sandbox database"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding Philippine sample documents..."))

        # Clean existing sample documents
        Document.objects.filter(file_name__startswith="PH_Sample_").delete()
        PurchaseOrderEntry.objects.filter(po_number="PO-2024-8891").delete()
        TaxCertificate2307Entry.objects.filter(payor_tin="987-654-321-000").delete()

        # 1. Clean Compliant Sales Invoice
        pdf1_bytes = self._build_compliant_invoice()
        doc1 = self._save_document(
            file_name="PH_Sample_Invoice_Compliant.pdf",
            file_bytes=pdf1_bytes,
            doc_type="SALES_INVOICE"
        )
        self.stdout.write(self.style.SUCCESS(f"Created {doc1.file_name} (ID: {doc1.id})"))

        # 2. Non-Compliant Invoice with VAT Discrepancy & Malformed TIN
        pdf2_bytes = self._build_discrepancy_invoice()
        doc2 = self._save_document(
            file_name="PH_Sample_Invoice_VAT_Discrepancy.pdf",
            file_bytes=pdf2_bytes,
            doc_type="SALES_INVOICE"
        )
        self.stdout.write(self.style.SUCCESS(f"Created {doc2.file_name} (ID: {doc2.id})"))

        # 3. 3-Way Match Pack: PO + BIR Form 2307
        pdf3_bytes = self._build_po_and_2307_pack()
        doc3 = self._save_document(
            file_name="PH_Sample_PO_and_2307_Pack.pdf",
            file_bytes=pdf3_bytes,
            doc_type="PURCHASE_ORDER"
        )
        self.stdout.write(self.style.SUCCESS(f"Created {doc3.file_name} (ID: {doc3.id})"))

        # Pre-seed matching PO and 2307 entries in ledger for 3-way matching
        self._seed_reference_ledger_entries(doc3)

        self.stdout.write(self.style.SUCCESS("All Philippine sample documents successfully seeded!"))

    def _save_document(self, file_name: str, file_bytes: bytes, doc_type: str) -> Document:
        file_hash = Document.calculate_sha256(file_bytes)
        with SpatialPDFParser(file_bytes) as parser:
            raw_text = parser.extract_full_text()
            page_count = parser.page_count
            blocks = parser.extract_spatial_blocks(0) if page_count > 0 else []
            dims = parser.get_page_dimensions(0) if page_count > 0 else (612, 792)

        doc = Document(
            file_name=file_name,
            file_hash=file_hash,
            file_size=len(file_bytes),
            document_type=doc_type,
            raw_text=raw_text,
            spatial_data={
                "page_count": page_count,
                "width": dims[0],
                "height": dims[1],
                "blocks": blocks,
            },
            status="PENDING",
        )
        doc.file.save(file_name, ContentFile(file_bytes), save=True)
        return doc

    def _build_compliant_invoice(self) -> bytes:
        """Clean 100% compliant Philippine Sales Invoice with 12% VAT and BIR ATP."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'InvoiceTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            textColor=colors.HexColor('#0F172A'),
            alignment=1, # Center
        )
        sub_style = ParagraphStyle(
            'SubHeader',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#475569'),
            alignment=1,
        )
        body_bold = ParagraphStyle('BoldText', fontName='Helvetica-Bold', fontSize=9, leading=12)
        body_norm = ParagraphStyle('NormText', fontName='Helvetica', fontSize=9, leading=12)

        story = []

        # Header
        story.append(Paragraph("MEGAWORLD TECH DISTRIBUTORS INC.", title_style))
        story.append(Paragraph("VAT-REGISTERED TIN: 123-456-789-000", body_bold))
        story.append(Paragraph("32nd Floor, Alliance Global Tower, Uptown Bonifacio, Taguig City, Philippines", sub_style))
        story.append(Paragraph("Tel: +63 (2) 8888-5500 | Email: billing@megaworldtech.ph", sub_style))
        story.append(Spacer(1, 14))

        # Invoice Banner
        story.append(Paragraph("SALES INVOICE", ParagraphStyle('Banner', fontName='Helvetica-Bold', fontSize=14, leading=16, alignment=1, textColor=colors.HexColor('#1E3A8A'))))
        story.append(Spacer(1, 10))

        # Meta & Customer Table
        meta_data = [
            [
                Paragraph("<b>SOLD TO:</b> Acme Philippines Corporation", body_norm),
                Paragraph("<b>INVOICE NO:</b> SI-2024-8891", body_norm),
            ],
            [
                Paragraph("<b>BUYER TIN:</b> 987-654-321-000", body_norm),
                Paragraph("<b>DATE:</b> 2024-11-15", body_norm),
            ],
            [
                Paragraph("<b>ADDRESS:</b> Ayala Triangle Gardens, Makati City", body_norm),
                Paragraph("<b>PO REFERENCE:</b> PO-2024-8891", body_norm),
            ],
            [
                Paragraph("<b>PAYMENT TERMS:</b> Net 30 Days", body_norm),
                Paragraph("<b>BIR ATP NO:</b> ATP-2024-0091823", body_norm),
            ],
        ]
        meta_table = Table(meta_data, colWidths=[320, 220])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 14))

        # Line Items Table
        items_data = [
            ["Description", "Quantity", "Unit Price", "Total Amount"],
            ["Dell PowerEdge R750 Enterprise Server", "1", "100,000.00", "100,000.00"],
            ["Cisco Catalyst 9200 Managed Switch", "2", "25,000.00", "50,000.00"],
        ]
        items_table = Table(items_data, colWidths=[280, 70, 95, 95])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(items_table)
        story.append(Spacer(1, 14))

        # Tax Breakdown Table (Standard Philippine BIR Breakdown)
        tax_data = [
            ["VATABLE SALES:", "PHP 150,000.00"],
            ["12% VALUE-ADDED TAX (VAT):", "PHP 18,000.00"],
            ["VAT-EXEMPT SALES:", "PHP 0.00"],
            ["ZERO-RATED SALES:", "PHP 0.00"],
            ["TOTAL AMOUNT DUE:", "PHP 168,000.00"],
        ]
        tax_table = Table(tax_data, colWidths=[380, 160])
        tax_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -2), 'Helvetica'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('LINEBELOW', (0, -2), (-1, -2), 1, colors.HexColor('#94A3B8')),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#EFF6FF')),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(tax_table)
        story.append(Spacer(1, 20))

        # Footer Statutory Notes
        notes = (
            "BIR Authority to Print No. ATP-2024-0091823 Issued on 01/15/2024 Valid until 01/15/2029. "
            "Series from SI-2024-0001 to SI-2024-9999. THIS DOCUMENT IS NOT VALID FOR CLAIM OF INPUT TAX "
            "UNLESS FULLY ACCOMPLISHED AND SIGNED."
        )
        story.append(Paragraph(notes, sub_style))

        doc.build(story)
        return buffer.getvalue()

    def _build_discrepancy_invoice(self) -> bytes:
        """Non-compliant invoice: defective TIN, 10% VAT calculation error, missing ATP."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'InvTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            textColor=colors.HexColor('#7F1D1D'),
            alignment=1,
        )
        body_norm = ParagraphStyle('NormText', fontName='Helvetica', fontSize=9, leading=12)

        story = []

        # Header with malformed TIN (only 8 digits!)
        story.append(Paragraph("QUEZON ENTERPRISE SOLUTIONS CORP.", title_style))
        story.append(Paragraph("TIN: 999-111-22", ParagraphStyle('TIN', fontName='Helvetica-Bold', fontSize=9, alignment=1, textColor=colors.red)))
        story.append(Paragraph("12 Scout Gandia, Diliman, Quezon City, Metro Manila", ParagraphStyle('Sub', fontSize=9, alignment=1)))
        story.append(Spacer(1, 14))

        story.append(Paragraph("BILLING SALES INVOICE", ParagraphStyle('Banner', fontName='Helvetica-Bold', fontSize=14, alignment=1, textColor=colors.HexColor('#991B1B'))))
        story.append(Spacer(1, 10))

        # Metadata
        meta_data = [
            [
                Paragraph("<b>SOLD TO:</b> Acme Philippines Corporation", body_norm),
                Paragraph("<b>INVOICE NO:</b> SI-2024-4012", body_norm),
            ],
            [
                Paragraph("<b>CUSTOMER TIN:</b> 987-654-321-000", body_norm),
                Paragraph("<b>DATE:</b> 2024-11-18", body_norm),
            ],
            [
                Paragraph("<b>PAYMENT:</b> Cash on Delivery", body_norm),
                Paragraph("<b>PO REF:</b> PO-2024-UNRECORDED", body_norm),
            ],
        ]
        meta_table = Table(meta_data, colWidths=[320, 220])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FEF2F2')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#FCA5A5')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#FEE2E2')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 14))

        # Line Items
        items_data = [
            ["Description", "Quantity", "Unit Price", "Total Amount"],
            ["Office Ergonomic Swivel Mesh Chairs", "10", "5,000.00", "50,000.00"],
        ]
        items_table = Table(items_data, colWidths=[280, 70, 95, 95])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#991B1B')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#FCA5A5')),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(items_table)
        story.append(Spacer(1, 14))

        # Defective Tax Breakdown: 10% VAT instead of legal 12% VAT!
        tax_data = [
            ["VATABLE SALES:", "PHP 50,000.00"],
            ["12% VALUE-ADDED TAX (VAT):", "PHP 5,000.00"], # Incorrect: should be 6,000.00!
            ["VAT-EXEMPT SALES:", "PHP 0.00"],
            ["ZERO-RATED SALES:", "PHP 0.00"],
            ["TOTAL AMOUNT DUE:", "PHP 55,000.00"], # Incorrect: should be 56,000.00!
        ]
        tax_table = Table(tax_data, colWidths=[380, 160])
        tax_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('LINEBELOW', (0, -2), (-1, -2), 1, colors.HexColor('#EF4444')),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#FEE2E2')),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(tax_table)
        story.append(Spacer(1, 20))

        # Note missing ATP completely
        story.append(Paragraph("System Generated Invoice. No BIR Permit to Print Attached.", ParagraphStyle('Warn', textColor=colors.red, fontSize=8, alignment=1)))

        doc.build(story)
        return buffer.getvalue()

    def _build_po_and_2307_pack(self) -> bytes:
        """Generates 2-page document containing PO-2024-8891 and BIR Form 2307."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
        styles = getSampleStyleSheet()

        body_norm = ParagraphStyle('NormText', fontName='Helvetica', fontSize=9, leading=12)
        title_style = ParagraphStyle('POTitle', fontName='Helvetica-Bold', fontSize=16, leading=20, alignment=1, textColor=colors.HexColor('#065F46'))

        story = []

        # PAGE 1: Purchase Order
        story.append(Paragraph("ACME PHILIPPINES CORPORATION", ParagraphStyle('BuyerTitle', fontName='Helvetica-Bold', fontSize=16, alignment=1)))
        story.append(Paragraph("Ayala Triangle Gardens, Tower 2, Makati City, Philippines", ParagraphStyle('BuyerSub', fontSize=9, alignment=1)))
        story.append(Spacer(1, 10))

        story.append(Paragraph("PURCHASE ORDER", title_style))
        story.append(Spacer(1, 10))

        po_meta = [
            [
                Paragraph("<b>PO NUMBER:</b> PO-2024-8891", body_norm),
                Paragraph("<b>DATE:</b> 2024-11-10", body_norm),
            ],
            [
                Paragraph("<b>VENDOR:</b> Megaworld Tech Distributors Inc.", body_norm),
                Paragraph("<b>PAYMENT TERMS:</b> 30 Days", body_norm),
            ],
            [
                Paragraph("<b>VENDOR TIN:</b> 123-456-789-000", body_norm),
                Paragraph("<b>STATUS:</b> APPROVED", body_norm),
            ],
        ]
        po_table = Table(po_meta, colWidths=[270, 270])
        po_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#ECFDF5')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#6EE7B7')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#A7F3D0')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(po_table)
        story.append(Spacer(1, 14))

        po_items = [
            ["Description", "Quantity", "Unit Price", "Total Amount"],
            ["Dell PowerEdge R750 Enterprise Server", "1", "100,000.00", "100,000.00"],
            ["Cisco Catalyst 9200 Managed Switch", "2", "25,000.00", "50,000.00"],
            ["12% Input Value-Added Tax", "1", "18,000.00", "18,000.00"],
        ]
        po_items_table = Table(po_items, colWidths=[280, 70, 95, 95])
        po_items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#065F46')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#6EE7B7')),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(po_items_table)
        story.append(Spacer(1, 10))

        po_total = Table([["TOTAL AUTHORIZED AMOUNT:", "PHP 168,000.00"]], colWidths=[380, 160])
        po_total.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#D1FAE5')),
        ]))
        story.append(po_total)

        # PAGE BREAK
        story.append(PageBreak())

        # PAGE 2: BIR Form 2307 Certificate
        story.append(Paragraph("BUREAU OF INTERNAL REVENUE", ParagraphStyle('BIR1', fontName='Helvetica-Bold', fontSize=12, alignment=1)))
        story.append(Paragraph("BIR Form No. 2307 — Certificate of Creditable Tax Withheld at Source", ParagraphStyle('BIR2', fontName='Helvetica-Bold', fontSize=13, alignment=1, textColor=colors.HexColor('#1E3A8A'))))
        story.append(Spacer(1, 12))

        b2307_data = [
            [
                Paragraph("<b>PAYOR (Withholding Agent):</b> Acme Philippines Corporation", body_norm),
                Paragraph("<b>PAYOR TIN:</b> 987-654-321-000", body_norm),
            ],
            [
                Paragraph("<b>PAYEE (Recipient):</b> Megaworld Tech Distributors Inc.", body_norm),
                Paragraph("<b>PAYEE TIN:</b> 123-456-789-000", body_norm),
            ],
            [
                Paragraph("<b>PERIOD COVERED:</b> 2024-10-01 to 2024-12-31", body_norm),
                Paragraph("<b>ATC CODE:</b> WC158 (1% Goods)", body_norm),
            ],
        ]
        b2307_table = Table(b2307_data, colWidths=[270, 270])
        b2307_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#EFF6FF')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#93C5FD')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BFDBFE')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(b2307_table)
        story.append(Spacer(1, 14))

        ewt_details = [
            ["ATC Description", "Gross Income Payment", "Tax Rate", "Amount of Tax Withheld"],
            ["WC158: Purchase of Goods by Top Withholding Agents", "150,000.00", "1%", "1,500.00"],
        ]
        ewt_table = Table(ewt_details, colWidths=[250, 110, 80, 100])
        ewt_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#93C5FD')),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(ewt_table)

        doc.build(story)
        return buffer.getvalue()

    def _seed_reference_ledger_entries(self, doc_po: Document):
        """Creates PO and Form 2307 database records so cross-matching works instantly."""
        # 1. Purchase Order Entry
        po_entry = PurchaseOrderEntry.objects.create(
            document=doc_po,
            po_number="PO-2024-8891",
            po_date="2024-11-10",
            vendor_name="Megaworld Tech Distributors Inc.",
            vendor_tin="123-456-789-000",
            buyer_name="Acme Philippines Corporation",
            total_amount=Decimal("168000.00"),
            status="OPEN"
        )
        PurchaseOrderLineItem.objects.create(
            po_entry=po_entry,
            description="Dell PowerEdge R750 Enterprise Server",
            quantity=Decimal("1.00"),
            unit_price=Decimal("100000.00"),
            amount=Decimal("100000.00")
        )
        PurchaseOrderLineItem.objects.create(
            po_entry=po_entry,
            description="Cisco Catalyst 9200 Managed Switch",
            quantity=Decimal("2.00"),
            unit_price=Decimal("25000.00"),
            amount=Decimal("50000.00")
        )

        # 2. BIR Form 2307 Entry
        TaxCertificate2307Entry.objects.create(
            document=doc_po,
            payor_name="Acme Philippines Corporation",
            payor_tin="987-654-321-000",
            payee_name="Megaworld Tech Distributors Inc.",
            payee_tin="123-456-789-000",
            period_from="2024-10-01",
            period_to="2024-12-31",
            atc_code="WC158",
            income_payment=Decimal("150000.00"),
            tax_rate=Decimal("0.01"),
            tax_withheld=Decimal("1500.00")
        )

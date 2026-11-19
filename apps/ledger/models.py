import hashlib
from decimal import Decimal
from django.db import models


class Document(models.Model):
    """Uploaded or seeded PDF document records."""
    
    DOCUMENT_TYPES = [
        ('SALES_INVOICE', 'Sales Invoice'),
        ('PURCHASE_ORDER', 'Purchase Order'),
        ('BIR_2307', 'BIR Form 2307 (Creditable Tax Withheld)'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Extraction'),
        ('EXTRACTED', 'Extracted'),
        ('AUDITED', 'Audited'),
        ('FAILED', 'Failed'),
    ]
    
    file = models.FileField(upload_to='documents/%Y/%m/')
    file_name = models.CharField(max_length=255)
    file_hash = models.CharField(max_length=64, db_index=True, help_text="SHA-256 binary hash")
    file_size = models.PositiveIntegerField(default=0)
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPES, default='SALES_INVOICE')
    raw_text = models.TextField(blank=True, default='')
    spatial_data = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-uploaded_at']
        
    def __str__(self):
        return f"{self.file_name} ({self.get_document_type_display()}) [{self.status}]"
        
    @staticmethod
    def calculate_sha256(file_bytes: bytes) -> str:
        return hashlib.sha256(file_bytes).hexdigest()


class InvoiceLedgerEntry(models.Model):
    """
    Extracted Philippine Sales Invoice converted into a structured accounting ledger entry.
    All financial amounts use strict 2-decimal precision (ROUND_HALF_UP).
    """
    AUDIT_STATUS_CHOICES = [
        ('PASSED', 'Passed All Compliance Checks'),
        ('WARNING', 'Passed With Warnings'),
        ('FAILED', 'Failed Compliance / Tax Audit'),
    ]
    
    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        related_name='invoice_entry',
        help_text="Source document PDF"
    )
    supplier_name = models.CharField(max_length=255)
    supplier_tin = models.CharField(max_length=50, db_index=True, help_text="PH Tax Identification Number")
    supplier_address = models.TextField(blank=True, default='')
    
    buyer_name = models.CharField(max_length=255)
    buyer_tin = models.CharField(max_length=50, blank=True, default='')
    
    invoice_number = models.CharField(max_length=100, db_index=True)
    invoice_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=10, default='PHP')
    
    # Philippine 12% VAT Breakdown Fields
    vatable_sales = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    vat_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    vat_exempt_sales = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    zero_rated_sales = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # BIR Compliance Information
    atp_number = models.CharField(max_length=100, blank=True, default='', help_text="BIR Authority to Print / PTU No.")
    po_reference = models.CharField(max_length=100, blank=True, default='', help_text="Associated Purchase Order Number")
    
    # Audit Results
    audit_status = models.CharField(max_length=20, choices=AUDIT_STATUS_CHOICES, default='PASSED')
    audit_score = models.IntegerField(default=100, help_text="0 to 100 Compliance Score")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-invoice_date', '-created_at']
        verbose_name_plural = 'Invoice ledger entries'
        
    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.supplier_name} (PHP {self.total_amount})"


class InvoiceLineItem(models.Model):
    """Individual line item from a Philippine Sales Invoice."""
    ledger_entry = models.ForeignKey(InvoiceLedgerEntry, on_delete=models.CASCADE, related_name='line_items')
    item_code = models.CharField(max_length=50, blank=True, default='')
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('1.00'))
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    bbox = models.JSONField(default=dict, blank=True, help_text="Spatial bounding box on source PDF")
    
    def __str__(self):
        return f"{self.description} ({self.quantity} x {self.unit_price} = {self.amount})"


class PurchaseOrderEntry(models.Model):
    """Purchase Order record for 2-Way and 3-Way matching."""
    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        related_name='po_entry',
        null=True,
        blank=True
    )
    po_number = models.CharField(max_length=100, unique=True, db_index=True)
    po_date = models.DateField(null=True, blank=True)
    vendor_name = models.CharField(max_length=255)
    vendor_tin = models.CharField(max_length=50, blank=True, default='')
    buyer_name = models.CharField(max_length=255)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, default='OPEN')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"PO #{self.po_number} - {self.vendor_name} (PHP {self.total_amount})"


class PurchaseOrderLineItem(models.Model):
    """Line items for Purchase Orders."""
    po_entry = models.ForeignKey(PurchaseOrderEntry, on_delete=models.CASCADE, related_name='line_items')
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('1.00'))
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    def __str__(self):
        return f"{self.description} ({self.quantity} x {self.unit_price})"


class TaxCertificate2307Entry(models.Model):
    """BIR Form 2307 Creditable Tax Withheld certificate entry."""
    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        related_name='tax_cert_entry',
        null=True,
        blank=True
    )
    payor_name = models.CharField(max_length=255, help_text="Withholding Agent / Customer")
    payor_tin = models.CharField(max_length=50)
    payee_name = models.CharField(max_length=255, help_text="Supplier / Recipient")
    payee_tin = models.CharField(max_length=50)
    period_from = models.DateField(null=True, blank=True)
    period_to = models.DateField(null=True, blank=True)
    atc_code = models.CharField(max_length=20, default='WC158', help_text="Alphanumeric Tax Code (e.g. WC158, WI010)")
    income_payment = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.01'), help_text="e.g. 0.01 for 1%, 0.02 for 2%")
    tax_withheld = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"BIR 2307 [{self.atc_code}] - {self.payee_name} (PHP {self.tax_withheld})"


class AuditLog(models.Model):
    """Audit rule evaluation log record for compliance diagnosis."""
    
    STATUS_CHOICES = [
        ('PASS', 'Pass'),
        ('WARNING', 'Warning'),
        ('FAIL', 'Fail'),
    ]
    
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='audit_logs')
    rule_name = models.CharField(max_length=100)
    rule_category = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    message = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['id']
        
    def __str__(self):
        return f"[{self.status}] {self.rule_name}: {self.message[:60]}"

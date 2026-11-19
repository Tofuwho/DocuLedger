from django.contrib import admin
from .models import (
    Document,
    InvoiceLedgerEntry,
    InvoiceLineItem,
    PurchaseOrderEntry,
    PurchaseOrderLineItem,
    TaxCertificate2307Entry,
    AuditLog,
)

class InvoiceLineItemInline(admin.TabularInline):
    model = InvoiceLineItem
    extra = 0

class PurchaseOrderLineItemInline(admin.TabularInline):
    model = PurchaseOrderLineItem
    extra = 0

class AuditLogInline(admin.TabularInline):
    model = AuditLog
    extra = 0
    readonly_fields = ('rule_name', 'rule_category', 'status', 'message', 'details', 'created_at')
    can_delete = False

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'document_type', 'status', 'file_size', 'uploaded_at')
    list_filter = ('document_type', 'status', 'uploaded_at')
    search_fields = ('file_name', 'file_hash')
    inlines = [AuditLogInline]

@admin.register(InvoiceLedgerEntry)
class InvoiceLedgerEntryAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'supplier_name', 'invoice_date', 'total_amount', 'vat_amount', 'audit_status', 'audit_score')
    list_filter = ('audit_status', 'invoice_date')
    search_fields = ('invoice_number', 'supplier_name', 'supplier_tin', 'buyer_name')
    inlines = [InvoiceLineItemInline]

@admin.register(PurchaseOrderEntry)
class PurchaseOrderEntryAdmin(admin.ModelAdmin):
    list_display = ('po_number', 'vendor_name', 'po_date', 'total_amount', 'status')
    search_fields = ('po_number', 'vendor_name')
    inlines = [PurchaseOrderLineItemInline]

@admin.register(TaxCertificate2307Entry)
class TaxCertificate2307EntryAdmin(admin.ModelAdmin):
    list_display = ('atc_code', 'payor_name', 'payee_name', 'income_payment', 'tax_rate', 'tax_withheld')
    search_fields = ('payor_name', 'payee_name', 'payee_tin', 'atc_code')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('document', 'rule_name', 'rule_category', 'status', 'created_at')
    list_filter = ('status', 'rule_category')
    search_fields = ('rule_name', 'message')

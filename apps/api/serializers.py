"""
Django REST Framework serializers for DocuLedger PH.
"""

from rest_framework import serializers
from apps.ledger.models import (
    Document,
    InvoiceLedgerEntry,
    InvoiceLineItem,
    PurchaseOrderEntry,
    PurchaseOrderLineItem,
    TaxCertificate2307Entry,
    AuditLog,
)


class DocumentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Document
        fields = [
            'id',
            'file',
            'file_url',
            'file_name',
            'file_hash',
            'file_size',
            'document_type',
            'status',
            'spatial_data',
            'uploaded_at',
        ]
        read_only_fields = ['file_hash', 'file_size', 'status', 'spatial_data', 'uploaded_at']

    def get_file_url(self, obj) -> str:
        if obj.file and hasattr(obj.file, 'url'):
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return ""


class InvoiceLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLineItem
        fields = ['id', 'item_code', 'description', 'quantity', 'unit_price', 'amount', 'bbox']


class InvoiceLedgerEntrySerializer(serializers.ModelSerializer):
    line_items = InvoiceLineItemSerializer(many=True, read_only=True)
    document_id = serializers.IntegerField(source='document.id', read_only=True)

    class Meta:
        model = InvoiceLedgerEntry
        fields = [
            'id',
            'document_id',
            'supplier_name',
            'supplier_tin',
            'supplier_address',
            'buyer_name',
            'buyer_tin',
            'invoice_number',
            'invoice_date',
            'due_date',
            'currency',
            'vatable_sales',
            'vat_amount',
            'vat_exempt_sales',
            'zero_rated_sales',
            'total_amount',
            'atp_number',
            'po_reference',
            'audit_status',
            'audit_score',
            'line_items',
            'created_at',
            'updated_at',
        ]


class PurchaseOrderLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseOrderLineItem
        fields = ['id', 'description', 'quantity', 'unit_price', 'amount']


class PurchaseOrderEntrySerializer(serializers.ModelSerializer):
    line_items = PurchaseOrderLineItemSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseOrderEntry
        fields = [
            'id',
            'po_number',
            'po_date',
            'vendor_name',
            'vendor_tin',
            'buyer_name',
            'total_amount',
            'status',
            'line_items',
            'created_at',
        ]


class TaxCertificate2307EntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxCertificate2307Entry
        fields = [
            'id',
            'payor_name',
            'payor_tin',
            'payee_name',
            'payee_tin',
            'period_from',
            'period_to',
            'atc_code',
            'income_payment',
            'tax_rate',
            'tax_withheld',
            'created_at',
        ]


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = [
            'id',
            'rule_name',
            'rule_category',
            'status',
            'message',
            'details',
            'created_at',
        ]

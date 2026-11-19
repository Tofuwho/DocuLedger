"""
URL patterns for DocuLedger REST API.
"""

from django.urls import path
from .views import (
    DocumentUploadView,
    DocumentExtractView,
    DocumentAuditView,
    DocumentExtractAndAuditView,
    SampleDocumentsView,
    ExportQuickBooksView,
    ExportXeroView,
    ExportSLSPView,
    LedgerListView,
    OpenAPISchemaView,
)

app_name = 'api'

urlpatterns = [
    # Document Lifecycle
    path('documents/upload/', DocumentUploadView.as_view(), name='document_upload'),
    path('documents/<int:pk>/extract/', DocumentExtractView.as_view(), name='document_extract'),
    path('documents/<int:pk>/audit/', DocumentAuditView.as_view(), name='document_audit'),
    
    # 1-Click Recruiter Sandbox Pipeline
    path('documents/extract-and-audit/', DocumentExtractAndAuditView.as_view(), name='document_extract_and_audit'),
    path('documents/samples/', SampleDocumentsView.as_view(), name='document_samples'),
    
    # Exporters
    path('documents/<int:pk>/export/quickbooks/', ExportQuickBooksView.as_view(), name='export_quickbooks'),
    path('documents/<int:pk>/export/xero/', ExportXeroView.as_view(), name='export_xero'),
    path('documents/export/slsp/', ExportSLSPView.as_view(), name='export_slsp'),
    
    # Accounting Ledger
    path('ledger/', LedgerListView.as_view(), name='ledger_list'),
    
    # API Schema
    path('schema/', OpenAPISchemaView.as_view(), name='api_schema'),
]

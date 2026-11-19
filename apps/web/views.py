"""
Web views for DocuLedger PH.
Serves the zero-login recruiter sandbox interactive split-screen workspace.
"""

from django.shortcuts import render
from apps.ledger.models import Document, InvoiceLedgerEntry


def workspace_view(request):
    """
    Renders the zero-login recruiter sandbox.
    Loads pre-seeded Philippine sample documents directly so visitors
    can test 1-click extraction and audit immediately without signing in.
    """
    samples = Document.objects.filter(file_name__startswith='PH_Sample_').order_by('id')
    recent_entries = InvoiceLedgerEntry.objects.all().select_related('document').order_by('-created_at')[:10]

    context = {
        'samples': samples,
        'recent_entries': recent_entries,
        'default_sample_id': samples.first().id if samples.exists() else None,
    }
    return render(request, 'web/workspace.html', context)

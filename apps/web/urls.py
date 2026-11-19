"""
Web URL routing for DocuLedger PH.
"""

from django.urls import path
from .views import workspace_view

app_name = 'web'

urlpatterns = [
    path('', workspace_view, name='workspace'),
]

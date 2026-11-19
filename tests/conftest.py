"""
Pytest configuration and shared fixtures for DocuLedger PH.
Automatically seeds Philippine sample documents into the test database.
"""

import pytest
from django.core.management import call_command


@pytest.fixture(autouse=True)
def seed_test_database(db):
    """Ensures Philippine sample documents and PO records are available in every test."""
    call_command('seed_ph_samples')

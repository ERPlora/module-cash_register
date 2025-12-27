"""
Pytest configuration for cash_register module tests.

This conftest ensures Django is properly configured when running tests
from within the module directory.
"""
import os
import sys
from pathlib import Path

# Ensure Django settings are configured before any imports
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Add the hub directory to Python path
HUB_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / 'hub'
if str(HUB_DIR) not in sys.path:
    sys.path.insert(0, str(HUB_DIR))

# Add the modules directory to Python path
MODULES_DIR = Path(__file__).resolve().parent.parent.parent
if str(MODULES_DIR) not in sys.path:
    sys.path.insert(0, str(MODULES_DIR))

# Now setup Django
import django
django.setup()

# Disable debug toolbar during tests to avoid namespace errors
from django.conf import settings
if 'debug_toolbar' in settings.INSTALLED_APPS:
    settings.INSTALLED_APPS = [
        app for app in settings.INSTALLED_APPS if app != 'debug_toolbar'
    ]
if hasattr(settings, 'MIDDLEWARE'):
    settings.MIDDLEWARE = [
        m for m in settings.MIDDLEWARE if 'debug_toolbar' not in m
    ]

# Import pytest and fixtures
import pytest
from decimal import Decimal
from django.test import Client
from django.utils import timezone

from apps.accounts.models import LocalUser
from cash_register.models import CashSession


@pytest.fixture
def client():
    """Create test client."""
    return Client()


@pytest.fixture
def user(db):
    """Create a test user."""
    from django.contrib.auth.hashers import make_password
    return LocalUser.objects.create(
        name="Test User",
        email="testuser@example.com",
        pin_hash=make_password("1234"),
        is_active=True
    )


@pytest.fixture
def open_session(db, user):
    """Create an open cash session."""
    return CashSession.objects.create(
        user=user,
        opening_balance=Decimal('100.00'),
        status='open'
    )


@pytest.fixture
def closed_session(db, user):
    """Create a closed cash session."""
    return CashSession.objects.create(
        user=user,
        opening_balance=Decimal('100.00'),
        closing_balance=Decimal('150.00'),
        status='closed',
        closed_at=timezone.now()
    )

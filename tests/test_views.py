"""
Integration tests for Cash Register views.
"""

import json
import uuid
import pytest
from decimal import Decimal
from django.test import Client
from django.utils import timezone

from cash_register.models import (
    CashRegisterSettings, CashRegister, CashSession,
    CashMovement, CashCount,
)


pytestmark = [pytest.mark.django_db, pytest.mark.unit]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _set_hub_config(db, settings):
    """Ensure HubConfig + StoreConfig exist so middleware won't redirect."""
    from apps.configuration.models import HubConfig, StoreConfig
    config = HubConfig.get_solo()
    config.save()
    store = StoreConfig.get_solo()
    store.business_name = 'Test Business'
    store.is_configured = True
    store.save()


@pytest.fixture
def hub_id(db):
    from apps.configuration.models import HubConfig
    return HubConfig.get_solo().hub_id


@pytest.fixture
def employee(db):
    """Create a local user (employee)."""
    from apps.accounts.models import LocalUser
    return LocalUser.objects.create(
        name='Test Employee',
        email='employee@test.com',
        role='admin',
        is_active=True,
    )


@pytest.fixture
def auth_client(employee):
    """Authenticated Django test client."""
    client = Client()
    session = client.session
    session['local_user_id'] = str(employee.id)
    session['user_name'] = employee.name
    session['user_email'] = employee.email
    session['user_role'] = employee.role
    session['store_config_checked'] = True
    session.save()
    return client


@pytest.fixture
def register(hub_id):
    """Create a cash register."""
    return CashRegister.objects.create(
        hub_id=hub_id,
        name='Register 1',
        is_active=True,
    )


@pytest.fixture
def open_session(hub_id, employee):
    """Create an open cash session for the employee."""
    return CashSession.objects.create(
        hub_id=hub_id,
        user=employee,
        opening_balance=Decimal('100.00'),
        status='open',
    )


@pytest.fixture
def closed_session(hub_id, employee):
    """Create a closed cash session."""
    return CashSession.objects.create(
        hub_id=hub_id,
        user=employee,
        opening_balance=Decimal('100.00'),
        closing_balance=Decimal('150.00'),
        status='closed',
        closed_at=timezone.now(),
    )


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class TestDashboard:

    def test_requires_login(self):
        client = Client()
        response = client.get('/m/cash_register/')
        assert response.status_code == 302

    def test_dashboard_loads(self, auth_client):
        response = auth_client.get('/m/cash_register/')
        assert response.status_code == 200

    def test_dashboard_htmx(self, auth_client):
        response = auth_client.get('/m/cash_register/', HTTP_HX_REQUEST='true')
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

class TestHistory:

    def test_history_loads(self, auth_client, closed_session):
        response = auth_client.get('/m/cash_register/history/')
        assert response.status_code == 200

    def test_history_htmx(self, auth_client, closed_session):
        response = auth_client.get('/m/cash_register/history/', HTTP_HX_REQUEST='true')
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Session Detail
# ---------------------------------------------------------------------------

class TestSessionDetail:

    def test_session_detail_loads(self, auth_client, closed_session):
        response = auth_client.get(f'/m/cash_register/session/{closed_session.pk}/')
        assert response.status_code == 200

    def test_session_detail_not_found(self, auth_client):
        fake_uuid = uuid.uuid4()
        response = auth_client.get(f'/m/cash_register/session/{fake_uuid}/')
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class TestSettingsView:

    def test_settings_loads(self, auth_client):
        response = auth_client.get('/m/cash_register/settings/')
        assert response.status_code == 200

    def test_settings_htmx(self, auth_client):
        response = auth_client.get('/m/cash_register/settings/', HTTP_HX_REQUEST='true')
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# API: Open Session
# ---------------------------------------------------------------------------

class TestAPIOpenSession:

    def test_open_session(self, auth_client):
        response = auth_client.post(
            '/m/cash_register/api/session/open/',
            data=json.dumps({
                'opening_balance': 100.00,
                'notes': 'Start of day',
            }),
            content_type='application/json',
        )
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True


# ---------------------------------------------------------------------------
# API: Close Session
# ---------------------------------------------------------------------------

class TestAPICloseSession:

    def test_close_session(self, auth_client, open_session):
        response = auth_client.post(
            '/m/cash_register/api/session/close/',
            data=json.dumps({
                'closing_balance': 150.00,
                'notes': 'End of day',
            }),
            content_type='application/json',
        )
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True


# ---------------------------------------------------------------------------
# API: Current Session
# ---------------------------------------------------------------------------

class TestAPICurrentSession:

    def test_get_current_session(self, auth_client, open_session):
        response = auth_client.get('/m/cash_register/api/session/current/')
        assert response.status_code == 200

    def test_no_current_session(self, auth_client):
        response = auth_client.get('/m/cash_register/api/session/current/')
        # Should still return 200 with appropriate response
        assert response.status_code in [200, 404]


# ---------------------------------------------------------------------------
# API: Add Movement
# ---------------------------------------------------------------------------

class TestAPIAddMovement:

    def test_add_sale_movement(self, auth_client, open_session):
        response = auth_client.post(
            '/m/cash_register/api/movement/add/',
            data=json.dumps({
                'movement_type': 'sale',
                'amount': 50.00,
                'sale_reference': 'SALE-001',
                'description': 'Test sale',
            }),
            content_type='application/json',
        )
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

    def test_add_cash_in(self, auth_client, open_session):
        response = auth_client.post(
            '/m/cash_register/api/movement/add/',
            data=json.dumps({
                'movement_type': 'in',
                'amount': 100.00,
                'description': 'Extra change',
            }),
            content_type='application/json',
        )
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

    def test_add_cash_out(self, auth_client, open_session):
        response = auth_client.post(
            '/m/cash_register/api/movement/add/',
            data=json.dumps({
                'movement_type': 'out',
                'amount': 30.00,
                'description': 'Supplier payment',
            }),
            content_type='application/json',
        )
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

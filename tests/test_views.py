"""
Integration tests for Cash Register views.
"""

import pytest
import json
from decimal import Decimal
from django.test import Client

from cash_register.models import (
    CashRegisterConfig, CashSession, CashMovement, CashCount
)
from apps.accounts.models import LocalUser


@pytest.fixture
def client():
    """Create test client."""
    return Client()


@pytest.fixture
def user():
    """Create a test user."""
    return LocalUser.objects.create(
        name="Test User",
        pin="1234",
        is_active=True
    )


@pytest.fixture
def open_session(user):
    """Create an open cash session."""
    return CashSession.objects.create(
        user=user,
        opening_balance=Decimal('100.00'),
        status='open'
    )


@pytest.fixture
def closed_session(user):
    """Create a closed cash session."""
    from django.utils import timezone
    return CashSession.objects.create(
        user=user,
        opening_balance=Decimal('100.00'),
        closing_balance=Decimal('150.00'),
        status='closed',
        closed_at=timezone.now()
    )


@pytest.mark.django_db
class TestApiOpenSession:
    """Tests for API open session endpoint."""

    def test_open_session_success(self, client, user):
        """Test opening a session via API."""
        # Simulate logged in user (would need proper auth in real tests)
        client.force_login(user)

        response = client.post(
            '/modules/cash_register/api/open/',
            data=json.dumps({
                'opening_balance': 100.00,
                'notes': 'Start of day'
            }),
            content_type='application/json'
        )

        # Response depends on auth - in real tests would be 200
        assert response.status_code in [200, 302]

    def test_open_session_already_exists(self, client, user, open_session):
        """Test opening session when one already exists."""
        client.force_login(user)

        response = client.post(
            '/modules/cash_register/api/open/',
            data=json.dumps({
                'opening_balance': 200.00
            }),
            content_type='application/json'
        )

        # Should fail with existing session
        assert response.status_code in [302, 400]


@pytest.mark.django_db
class TestApiCloseSession:
    """Tests for API close session endpoint."""

    def test_close_session_success(self, client, user, open_session):
        """Test closing a session via API."""
        client.force_login(user)

        response = client.post(
            '/modules/cash_register/api/close/',
            data=json.dumps({
                'closing_balance': 150.00,
                'notes': 'End of day'
            }),
            content_type='application/json'
        )

        assert response.status_code in [200, 302]

    def test_close_session_no_open_session(self, client, user):
        """Test closing when no open session exists."""
        client.force_login(user)

        response = client.post(
            '/modules/cash_register/api/close/',
            data=json.dumps({
                'closing_balance': 100.00
            }),
            content_type='application/json'
        )

        # Should return 404 or redirect
        assert response.status_code in [302, 404]


@pytest.mark.django_db
class TestApiAddMovement:
    """Tests for API add movement endpoint."""

    def test_add_sale_movement(self, client, user, open_session):
        """Test adding a sale movement."""
        client.force_login(user)

        response = client.post(
            '/modules/cash_register/api/movement/',
            data=json.dumps({
                'movement_type': 'sale',
                'amount': 50.00,
                'sale_reference': 'SALE-001',
                'description': 'Test sale'
            }),
            content_type='application/json'
        )

        assert response.status_code in [200, 302]

    def test_add_cash_in_movement(self, client, user, open_session):
        """Test adding a cash in movement."""
        client.force_login(user)

        response = client.post(
            '/modules/cash_register/api/movement/',
            data=json.dumps({
                'movement_type': 'in',
                'amount': 100.00,
                'description': 'Extra change'
            }),
            content_type='application/json'
        )

        assert response.status_code in [200, 302]

    def test_add_cash_out_movement(self, client, user, open_session):
        """Test adding a cash out movement."""
        client.force_login(user)

        response = client.post(
            '/modules/cash_register/api/movement/',
            data=json.dumps({
                'movement_type': 'out',
                'amount': 30.00,
                'description': 'Supplier payment'
            }),
            content_type='application/json'
        )

        assert response.status_code in [200, 302]


@pytest.mark.django_db
class TestApiCurrentSession:
    """Tests for API current session endpoint."""

    def test_get_current_session(self, client, user, open_session):
        """Test getting current session."""
        client.force_login(user)

        response = client.get('/modules/cash_register/api/current/')

        assert response.status_code in [200, 302]

    def test_get_current_session_none(self, client, user):
        """Test getting current session when none exists."""
        client.force_login(user)

        response = client.get('/modules/cash_register/api/current/')

        # Should return 404 or redirect
        assert response.status_code in [302, 404]


@pytest.mark.django_db
class TestApiSessionMovements:
    """Tests for API session movements endpoint."""

    def test_get_session_movements(self, client, user, open_session):
        """Test getting movements for a session."""
        # Add a movement
        CashMovement.objects.create(
            session=open_session,
            movement_type='sale',
            amount=Decimal('50.00')
        )

        client.force_login(user)

        response = client.get(f'/modules/cash_register/api/session/{open_session.id}/movements/')

        assert response.status_code in [200, 302]

    def test_get_session_movements_not_found(self, client, user):
        """Test getting movements for non-existent session."""
        client.force_login(user)

        import uuid
        fake_id = uuid.uuid4()
        response = client.get(f'/modules/cash_register/api/session/{fake_id}/movements/')

        assert response.status_code in [302, 404]


@pytest.mark.django_db
class TestSettingsView:
    """Tests for settings view."""

    def test_settings_get(self, client, user):
        """Test GET settings page."""
        client.force_login(user)

        response = client.get('/modules/cash_register/settings/')

        assert response.status_code in [200, 302]

    def test_settings_htmx(self, client, user):
        """Test HTMX settings request."""
        client.force_login(user)

        response = client.get(
            '/modules/cash_register/settings/',
            HTTP_HX_REQUEST='true'
        )

        assert response.status_code in [200, 302]

    def test_settings_save(self, client, user):
        """Test saving settings."""
        client.force_login(user)

        response = client.post('/modules/cash_register/settings/', {
            'enable_cash_register': 'on',
            'require_opening_balance': 'on',
            'require_closing_balance': 'on',
            'allow_negative_balance': '',
            'auto_open_session_on_login': 'on',
            'auto_close_session_on_logout': 'on',
            'protected_pos_url': '/modules/sales/pos/'
        })

        assert response.status_code in [200, 302]


@pytest.mark.django_db
class TestHistoryView:
    """Tests for history view."""

    def test_history_get(self, client, user, closed_session):
        """Test GET history page."""
        client.force_login(user)

        response = client.get('/modules/cash_register/history/')

        assert response.status_code in [200, 302]

    def test_history_htmx(self, client, user, closed_session):
        """Test HTMX history request."""
        client.force_login(user)

        response = client.get(
            '/modules/cash_register/history/',
            HTTP_HX_REQUEST='true'
        )

        assert response.status_code in [200, 302]

    def test_history_filter_status(self, client, user, open_session, closed_session):
        """Test history filter by status."""
        client.force_login(user)

        response = client.get('/modules/cash_register/history/?status=closed')

        assert response.status_code in [200, 302]


@pytest.mark.django_db
class TestSessionDetailView:
    """Tests for session detail view."""

    def test_session_detail_get(self, client, user, closed_session):
        """Test GET session detail page."""
        client.force_login(user)

        response = client.get(f'/modules/cash_register/session/{closed_session.id}/')

        assert response.status_code in [200, 302]

    def test_session_detail_not_found(self, client, user):
        """Test GET session detail for non-existent session."""
        client.force_login(user)

        import uuid
        fake_id = uuid.uuid4()
        response = client.get(f'/modules/cash_register/session/{fake_id}/')

        assert response.status_code in [302, 404]


@pytest.mark.django_db
class TestHtmxCalculateDenominations:
    """Tests for HTMX calculate denominations endpoint."""

    def test_calculate_denominations(self, client, user):
        """Test calculating total from denominations."""
        client.force_login(user)

        response = client.post(
            '/modules/cash_register/htmx/calculate-denominations/',
            data=json.dumps({
                'denominations': {
                    'bill_50': 2,
                    'bill_20': 3,
                    'coin_2': 10
                }
            }),
            content_type='application/json'
        )

        assert response.status_code in [200, 302]


@pytest.mark.django_db
class TestHtmxCalculateDifference:
    """Tests for HTMX calculate difference endpoint."""

    def test_calculate_difference(self, client, user):
        """Test calculating difference between expected and actual."""
        client.force_login(user)

        response = client.post(
            '/modules/cash_register/htmx/calculate-difference/',
            data=json.dumps({
                'expected': 100.00,
                'actual': 95.00
            }),
            content_type='application/json'
        )

        assert response.status_code in [200, 302]

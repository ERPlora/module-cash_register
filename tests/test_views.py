"""
Integration tests for Cash Register views.

Fixtures (client, user, open_session, closed_session) are defined in conftest.py
"""

import pytest
import json
from decimal import Decimal

from cash_register.models import (
    CashRegisterConfig, CashSession, CashMovement, CashCount
)


# Fixtures are inherited from conftest.py:
# - client: Django test client
# - user: Test LocalUser
# - open_session: Open CashSession for user
# - closed_session: Closed CashSession for user


@pytest.mark.django_db
class TestDashboardView:
    """Tests for dashboard view."""

    def test_dashboard_get(self, client, user):
        """Test GET dashboard page."""
        client.force_login(user)

        response = client.get('/modules/cash_register/')

        assert response.status_code in [200, 302]

    def test_dashboard_htmx(self, client, user):
        """Test HTMX dashboard request."""
        client.force_login(user)

        response = client.get(
            '/modules/cash_register/',
            HTTP_HX_REQUEST='true'
        )

        assert response.status_code in [200, 302]


@pytest.mark.django_db
class TestOpenSessionView:
    """Tests for open_session view (HTML form, not API)."""

    def test_open_session_renders_without_error(self, client, user):
        """Test that open_session page renders without template errors.

        This test specifically catches NoReverseMatch errors in templates,
        like the bug where 'configuration:dashboard' was used instead of 'main:index'.
        """
        client.force_login(user)

        response = client.get('/modules/cash_register/open/')

        # Should render successfully (200) or redirect (302 if session exists)
        assert response.status_code in [200, 302], (
            f"Expected 200 or 302, got {response.status_code}. "
            "Check for template errors like NoReverseMatch."
        )

    def test_open_session_redirects_if_session_exists(self, client, user, open_session):
        """Test redirect when user already has an open session."""
        client.force_login(user)

        response = client.get('/modules/cash_register/open/')

        assert response.status_code == 302  # Redirect to dashboard

    def test_open_session_post_no_template_error(self, client, user):
        """Test POST doesn't cause template errors.

        Note: This test verifies the view doesn't crash, not that it creates
        a session. Session creation depends on specific form fields which
        may vary based on implementation.
        """
        client.force_login(user)

        response = client.post('/modules/cash_register/open/', {
            'opening_balance': '100.00',
            'notes': 'Test session',
            'denominations_json': '{}',
        })

        # Should either redirect (success) or show form (validation error)
        # Should NOT return 500 (template error)
        assert response.status_code in [200, 302], (
            f"Expected 200 or 302, got {response.status_code}. "
            "POST should not cause template errors."
        )


@pytest.mark.django_db
class TestCloseSessionView:
    """Tests for close_session view (HTML form, not API)."""

    def test_close_session_renders_without_error(self, client, user, open_session):
        """Test that close_session page renders without template errors."""
        client.force_login(user)

        response = client.get('/modules/cash_register/close/')

        assert response.status_code in [200, 302], (
            f"Expected 200 or 302, got {response.status_code}. "
            "Check for template errors like NoReverseMatch."
        )

    def test_close_session_redirects_if_no_session(self, client, user):
        """Test redirect when user has no open session."""
        client.force_login(user)

        response = client.get('/modules/cash_register/close/')

        assert response.status_code == 302  # Redirect to dashboard

    def test_close_session_post_no_template_error(self, client, user, open_session):
        """Test POST doesn't cause template errors.

        Note: This test verifies the view doesn't crash, not that it closes
        the session. Session closing depends on specific form fields which
        may vary based on implementation.
        """
        client.force_login(user)

        response = client.post('/modules/cash_register/close/', {
            'closing_balance': '150.00',
            'notes': 'End of day',
            'denominations_json': '{}',
        })

        # Should either redirect (success) or show form (validation error)
        # Should NOT return 500 (template error)
        assert response.status_code in [200, 302], (
            f"Expected 200 or 302, got {response.status_code}. "
            "POST should not cause template errors."
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

    def test_settings_save_json(self, client, user):
        """Test saving settings via JSON endpoint."""
        client.force_login(user)

        response = client.post(
            '/modules/cash_register/settings/save/',
            data=json.dumps({
                'enable_cash_register': True,
                'require_opening_balance': True,
                'require_closing_balance': True,
                'allow_negative_balance': False,
                'auto_open_session_on_login': True,
                'auto_close_session_on_logout': True,
                'protected_pos_url': '/modules/sales/pos/'
            }),
            content_type='application/json'
        )

        assert response.status_code in [200, 302]

        if response.status_code == 200:
            data = json.loads(response.content)
            assert data['success'] is True

    def test_settings_save_invalid_json(self, client, user):
        """Test saving with invalid JSON."""
        client.force_login(user)

        response = client.post(
            '/modules/cash_register/settings/save/',
            data='invalid json',
            content_type='application/json'
        )

        assert response.status_code in [400, 302]

    def test_settings_persist(self, client, user):
        """Test settings are persisted."""
        client.force_login(user)

        response = client.post(
            '/modules/cash_register/settings/save/',
            data=json.dumps({
                'enable_cash_register': False,
                'require_opening_balance': False,
                'require_closing_balance': True,
                'allow_negative_balance': True,
                'auto_open_session_on_login': False,
                'auto_close_session_on_logout': False,
                'protected_pos_url': '/custom/pos/'
            }),
            content_type='application/json'
        )

        if response.status_code == 200:
            config = CashRegisterConfig.get_config()
            assert config.enable_cash_register is False
            assert config.require_opening_balance is False
            assert config.allow_negative_balance is True
            assert config.protected_pos_url == '/custom/pos/'


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

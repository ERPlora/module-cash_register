"""
Unit tests for Cash Register models.
"""

import pytest
from decimal import Decimal
from django.utils import timezone

from cash_register.models import (
    CashRegisterSettings, CashRegister, CashSession,
    CashMovement, CashCount,
)


pytestmark = [pytest.mark.django_db, pytest.mark.unit]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def hub_id(hub_config):
    """Hub ID from HubConfig singleton."""
    return hub_config.hub_id


@pytest.fixture
def user(db):
    """Create a test user."""
    from apps.accounts.models import LocalUser
    return LocalUser.objects.create(
        name='Test Cashier',
        email='cashier@test.com',
        role='cashier',
        is_active=True,
    )


@pytest.fixture
def register(hub_id):
    """Create a cash register."""
    return CashRegister.objects.create(
        hub_id=hub_id,
        name='Register 1',
        is_active=True,
    )


@pytest.fixture
def open_session(hub_id, user, register):
    """Create an open cash session."""
    return CashSession.objects.create(
        hub_id=hub_id,
        user=user,
        register=register,
        opening_balance=Decimal('100.00'),
        status='open',
    )


@pytest.fixture
def closed_session(hub_id, user, register):
    """Create a closed cash session."""
    return CashSession.objects.create(
        hub_id=hub_id,
        user=user,
        register=register,
        opening_balance=Decimal('100.00'),
        closing_balance=Decimal('150.00'),
        expected_balance=Decimal('150.00'),
        difference=Decimal('0.00'),
        status='closed',
        closed_at=timezone.now(),
    )


# ---------------------------------------------------------------------------
# CashRegisterSettings
# ---------------------------------------------------------------------------

class TestCashRegisterSettings:
    """Tests for CashRegisterSettings model."""

    def test_get_settings_creates(self, hub_id):
        s = CashRegisterSettings.get_settings(hub_id)
        assert s is not None
        assert s.hub_id == hub_id

    def test_get_settings_returns_existing(self, hub_id):
        s1 = CashRegisterSettings.get_settings(hub_id)
        s2 = CashRegisterSettings.get_settings(hub_id)
        assert s1.pk == s2.pk

    def test_default_values(self, hub_id):
        s = CashRegisterSettings.get_settings(hub_id)
        assert s.enable_cash_register is True
        assert s.require_opening_balance is False
        assert s.require_closing_balance is True
        assert s.allow_negative_balance is False
        assert s.auto_open_session_on_login is True
        assert s.auto_close_session_on_logout is True
        assert s.protected_pos_url == '/m/sales/pos/'

    def test_str(self, hub_id):
        s = CashRegisterSettings.get_settings(hub_id)
        assert 'Cash Register Settings' in str(s)

    def test_update_settings(self, hub_id):
        s = CashRegisterSettings.get_settings(hub_id)
        s.enable_cash_register = False
        s.require_opening_balance = True
        s.save()
        refreshed = CashRegisterSettings.get_settings(hub_id)
        assert refreshed.enable_cash_register is False
        assert refreshed.require_opening_balance is True


# ---------------------------------------------------------------------------
# CashRegister
# ---------------------------------------------------------------------------

class TestCashRegister:
    """Tests for CashRegister model."""

    def test_create(self, register):
        assert register.name == 'Register 1'
        assert register.is_active is True

    def test_str(self, register):
        assert str(register) == 'Register 1'

    def test_ordering(self, hub_id):
        r1 = CashRegister.objects.create(hub_id=hub_id, name='Z Register')
        r2 = CashRegister.objects.create(hub_id=hub_id, name='A Register')
        registers = list(CashRegister.objects.filter(hub_id=hub_id))
        assert registers[0].pk == r2.pk

    def test_current_session_when_open(self, register, open_session):
        assert register.current_session == open_session

    def test_current_session_when_closed(self, register, closed_session):
        assert register.current_session is None

    def test_is_open(self, register, open_session):
        assert register.is_open is True

    def test_is_not_open(self, register, closed_session):
        assert register.is_open is False

    def test_soft_delete(self, register):
        register.delete()
        assert register.is_deleted is True
        assert CashRegister.objects.filter(pk=register.pk).count() == 0
        assert CashRegister.all_objects.filter(pk=register.pk).count() == 1


# ---------------------------------------------------------------------------
# CashSession
# ---------------------------------------------------------------------------

class TestCashSession:
    """Tests for CashSession model."""

    def test_create(self, open_session):
        assert open_session.status == 'open'
        assert open_session.opening_balance == Decimal('100.00')

    def test_session_number_auto_generated(self, open_session):
        assert open_session.session_number is not None
        assert open_session.session_number.startswith('CS-')

    def test_str(self, open_session):
        result = str(open_session)
        assert open_session.session_number in result
        assert 'open' in result

    def test_close_session(self, open_session):
        open_session.close_session(
            closing_balance=Decimal('150.00'),
            notes='End of day',
        )
        open_session.refresh_from_db()
        assert open_session.status == 'closed'
        assert open_session.closing_balance == Decimal('150.00')
        assert open_session.closed_at is not None
        assert open_session.closing_notes == 'End of day'

    def test_close_calculates_expected_balance(self, hub_id, open_session):
        CashMovement.objects.create(
            hub_id=hub_id, session=open_session,
            movement_type='sale', amount=Decimal('50.00'),
        )
        open_session.close_session(closing_balance=Decimal('150.00'))
        open_session.refresh_from_db()
        # expected: 100 + 50 = 150
        assert open_session.expected_balance == Decimal('150.00')
        assert open_session.difference == Decimal('0.00')

    def test_close_calculates_difference(self, open_session):
        # No movements, expected = 100
        open_session.close_session(closing_balance=Decimal('95.00'))
        open_session.refresh_from_db()
        assert open_session.expected_balance == Decimal('100.00')
        assert open_session.difference == Decimal('-5.00')

    def test_get_total_sales(self, hub_id, open_session):
        CashMovement.objects.create(
            hub_id=hub_id, session=open_session,
            movement_type='sale', amount=Decimal('25.00'),
        )
        CashMovement.objects.create(
            hub_id=hub_id, session=open_session,
            movement_type='sale', amount=Decimal('35.00'),
        )
        assert open_session.get_total_sales() == Decimal('60.00')

    def test_get_total_in(self, hub_id, open_session):
        CashMovement.objects.create(
            hub_id=hub_id, session=open_session,
            movement_type='in', amount=Decimal('50.00'),
        )
        assert open_session.get_total_in() == Decimal('50.00')

    def test_get_total_out(self, hub_id, open_session):
        CashMovement.objects.create(
            hub_id=hub_id, session=open_session,
            movement_type='out', amount=Decimal('-30.00'),
        )
        assert open_session.get_total_out() == Decimal('30.00')

    def test_get_total_refunds(self, hub_id, open_session):
        CashMovement.objects.create(
            hub_id=hub_id, session=open_session,
            movement_type='refund', amount=Decimal('-15.00'),
        )
        assert open_session.get_total_refunds() == Decimal('15.00')

    def test_get_current_balance(self, hub_id, open_session):
        CashMovement.objects.create(
            hub_id=hub_id, session=open_session,
            movement_type='sale', amount=Decimal('50.00'),
        )
        CashMovement.objects.create(
            hub_id=hub_id, session=open_session,
            movement_type='out', amount=Decimal('-20.00'),
        )
        # 100 + 50 - 20 = 130
        assert open_session.get_current_balance() == Decimal('130.00')

    def test_get_current_session(self, hub_id, user, open_session):
        current = CashSession.get_current_session(hub_id, user)
        assert current == open_session

    def test_get_current_session_none(self, hub_id, user, closed_session):
        current = CashSession.get_current_session(hub_id, user)
        assert current is None

    def test_open_for_user_creates_new(self, hub_id, user):
        session = CashSession.open_for_user(
            hub_id=hub_id, user=user,
            opening_balance=Decimal('200.00'),
        )
        assert session.user == user
        assert session.status == 'open'
        assert session.opening_balance == Decimal('200.00')

    def test_open_for_user_returns_existing(self, hub_id, user, open_session):
        session = CashSession.open_for_user(hub_id=hub_id, user=user)
        assert session == open_session

    def test_open_for_user_uses_last_closing_balance(self, hub_id, user, closed_session):
        new_session = CashSession.open_for_user(hub_id=hub_id, user=user)
        assert new_session.opening_balance == Decimal('150.00')

    def test_get_duration_open(self, open_session):
        duration = open_session.get_duration()
        assert isinstance(duration, str)
        # Should contain minutes format
        assert 'm' in duration

    def test_ordering_newest_first(self, hub_id, user):
        s1 = CashSession.objects.create(
            hub_id=hub_id, user=user, opening_balance=Decimal('100.00'),
        )
        s2 = CashSession.objects.create(
            hub_id=hub_id, user=user, opening_balance=Decimal('200.00'),
        )
        sessions = list(CashSession.objects.filter(hub_id=hub_id))
        assert sessions[0].pk == s2.pk

    def test_indexes(self):
        index_fields = [idx.fields for idx in CashSession._meta.indexes]
        assert ['user', 'status'] in index_fields
        assert ['status', 'opened_at'] in index_fields


# ---------------------------------------------------------------------------
# CashMovement
# ---------------------------------------------------------------------------

class TestCashMovement:
    """Tests for CashMovement model."""

    def test_create_sale(self, hub_id, open_session):
        mov = CashMovement.objects.create(
            hub_id=hub_id, session=open_session,
            movement_type='sale', amount=Decimal('50.00'),
            sale_reference='SALE-001', description='Test sale',
        )
        assert mov.movement_type == 'sale'
        assert mov.amount == Decimal('50.00')
        assert mov.sale_reference == 'SALE-001'

    def test_create_cash_in(self, hub_id, open_session):
        mov = CashMovement.objects.create(
            hub_id=hub_id, session=open_session,
            movement_type='in', amount=Decimal('100.00'),
            description='Extra change',
        )
        assert mov.movement_type == 'in'

    def test_create_cash_out(self, hub_id, open_session):
        mov = CashMovement.objects.create(
            hub_id=hub_id, session=open_session,
            movement_type='out', amount=Decimal('-50.00'),
            description='Supplier payment',
        )
        assert mov.movement_type == 'out'
        assert mov.amount == Decimal('-50.00')

    def test_create_refund(self, hub_id, open_session):
        mov = CashMovement.objects.create(
            hub_id=hub_id, session=open_session,
            movement_type='refund', amount=Decimal('-25.00'),
            description='Customer refund',
        )
        assert mov.movement_type == 'refund'

    def test_str(self, hub_id, open_session):
        mov = CashMovement.objects.create(
            hub_id=hub_id, session=open_session,
            movement_type='sale', amount=Decimal('75.00'),
        )
        assert 'Sale' in str(mov)
        assert '75.00' in str(mov)

    def test_payment_methods(self, hub_id, open_session):
        for method, _ in CashMovement.PAYMENT_METHODS:
            mov = CashMovement.objects.create(
                hub_id=hub_id, session=open_session,
                movement_type='sale', amount=Decimal('10.00'),
                payment_method=method,
            )
            assert mov.payment_method == method

    def test_default_payment_method(self, hub_id, open_session):
        mov = CashMovement.objects.create(
            hub_id=hub_id, session=open_session,
            movement_type='sale', amount=Decimal('10.00'),
        )
        assert mov.payment_method == 'cash'

    def test_record_sale_classmethod(self, hub_id, open_session, user):
        """Test the record_sale class method."""
        from unittest.mock import MagicMock
        sale = MagicMock()
        sale.total = Decimal('42.50')
        sale.sale_number = '20260218-0001'

        mov = CashMovement.record_sale(
            hub_id=hub_id, sale=sale,
            session=open_session, employee=user,
        )
        assert mov is not None
        assert mov.amount == Decimal('42.50')
        assert mov.movement_type == 'sale'
        assert mov.sale_reference == '20260218-0001'
        assert mov.employee == user

    def test_record_sale_no_session(self, hub_id):
        """record_sale returns None when no session provided."""
        from unittest.mock import MagicMock
        sale = MagicMock()
        sale.total = Decimal('10.00')
        result = CashMovement.record_sale(hub_id=hub_id, sale=sale, session=None)
        assert result is None

    def test_ordering_newest_first(self, hub_id, open_session):
        mov1 = CashMovement.objects.create(
            hub_id=hub_id, session=open_session,
            movement_type='sale', amount=Decimal('10.00'),
        )
        mov2 = CashMovement.objects.create(
            hub_id=hub_id, session=open_session,
            movement_type='in', amount=Decimal('20.00'),
        )
        movements = list(CashMovement.objects.filter(hub_id=hub_id))
        assert movements[0].pk == mov2.pk

    def test_indexes(self):
        index_fields = [idx.fields for idx in CashMovement._meta.indexes]
        assert ['session', 'movement_type'] in index_fields
        assert ['sale_reference'] in index_fields


# ---------------------------------------------------------------------------
# CashCount
# ---------------------------------------------------------------------------

class TestCashCount:
    """Tests for CashCount model (denomination breakdown)."""

    def test_create_opening_count(self, hub_id, open_session):
        count = CashCount.objects.create(
            hub_id=hub_id, session=open_session,
            count_type='opening',
            denominations={
                'bills': {'50': 1, '20': 2},
                'coins': {'2': 5},
            },
            total=Decimal('100.00'),
        )
        assert count.count_type == 'opening'
        assert count.total == Decimal('100.00')

    def test_create_closing_count(self, hub_id, open_session):
        count = CashCount.objects.create(
            hub_id=hub_id, session=open_session,
            count_type='closing',
            total=Decimal('150.00'),
        )
        assert count.count_type == 'closing'

    def test_str(self, hub_id, open_session):
        count = CashCount.objects.create(
            hub_id=hub_id, session=open_session,
            count_type='opening',
            total=Decimal('100.00'),
        )
        assert 'Opening' in str(count)
        assert '100.00' in str(count)

    def test_calculate_total_from_denominations(self, hub_id, open_session):
        count = CashCount(
            hub_id=hub_id, session=open_session,
            count_type='opening',
            denominations={
                'bills': {'50': 2, '20': 3},  # 100 + 60 = 160
                'coins': {'2': 10, '1': 5},   # 20 + 5 = 25
            },
        )
        total = count.calculate_total_from_denominations()
        assert total == Decimal('185.00')

    def test_auto_calculate_total_on_save(self, hub_id, open_session):
        """Total is auto-calculated on save if denominations provided and total is 0."""
        count = CashCount.objects.create(
            hub_id=hub_id, session=open_session,
            count_type='opening',
            denominations={
                'bills': {'20': 5},  # 100
                'coins': {'1': 10},  # 10
            },
        )
        assert count.total == Decimal('110.00')

    def test_explicit_total_not_overridden(self, hub_id, open_session):
        """When explicit total is provided, it should not be overridden."""
        count = CashCount.objects.create(
            hub_id=hub_id, session=open_session,
            count_type='opening',
            denominations={'bills': {'20': 5}},
            total=Decimal('99.00'),  # intentionally different
        )
        assert count.total == Decimal('99.00')

    def test_empty_denominations(self, hub_id, open_session):
        count = CashCount(
            hub_id=hub_id, session=open_session,
            count_type='closing',
            denominations={},
        )
        total = count.calculate_total_from_denominations()
        assert total == Decimal('0.00')

    def test_denomination_with_all_bill_types(self, hub_id, open_session):
        """Test a realistic denomination count with various bills and coins."""
        count = CashCount.objects.create(
            hub_id=hub_id, session=open_session,
            count_type='closing',
            denominations={
                'bills': {'500': 0, '200': 1, '100': 0, '50': 2, '20': 3, '10': 5, '5': 2},
                'coins': {'2': 10, '1': 15, '0.50': 4, '0.20': 10, '0.10': 5, '0.05': 0, '0.02': 0, '0.01': 0},
            },
        )
        # 200 + 100 + 60 + 50 + 10 + 20 + 15 + 2 + 2 + 0.5 = 459.50
        expected = Decimal('200') + Decimal('100') + Decimal('60') + Decimal('50') + Decimal('10')
        expected += Decimal('20') + Decimal('15') + Decimal('2') + Decimal('2') + Decimal('0.5')
        assert count.total == expected

    def test_ordering_newest_first(self, hub_id, open_session):
        c1 = CashCount.objects.create(
            hub_id=hub_id, session=open_session,
            count_type='opening', total=Decimal('100.00'),
        )
        c2 = CashCount.objects.create(
            hub_id=hub_id, session=open_session,
            count_type='closing', total=Decimal('150.00'),
        )
        counts = list(CashCount.objects.filter(hub_id=hub_id))
        assert counts[0].pk == c2.pk

"""
Unit tests for Cash Register models.
"""

import pytest
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

from cash_register.models import (
    CashRegisterConfig, CashSession, CashMovement, CashCount
)
from apps.accounts.models import LocalUser


@pytest.mark.django_db
class TestCashRegisterConfig:
    """Tests for CashRegisterConfig singleton model."""

    def test_get_config_creates_singleton(self):
        """Test get_config creates singleton if not exists."""
        config = CashRegisterConfig.get_config()

        assert config is not None
        assert config.pk == 1

    def test_get_config_returns_existing(self):
        """Test get_config returns existing config."""
        config1 = CashRegisterConfig.get_config()
        config2 = CashRegisterConfig.get_config()

        assert config1.pk == config2.pk

    def test_default_values(self):
        """Test default configuration values."""
        config = CashRegisterConfig.get_config()

        assert config.enable_cash_register is True
        assert config.require_opening_balance is False
        assert config.require_closing_balance is True
        assert config.allow_negative_balance is False
        assert config.auto_open_session_on_login is True
        assert config.auto_close_session_on_logout is True

    def test_str_representation(self):
        """Test string representation."""
        config = CashRegisterConfig.get_config()

        assert str(config) == "Cash Register Configuration"


@pytest.mark.django_db
class TestCashSession:
    """Tests for CashSession model."""

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return LocalUser.objects.create(
            name="Test User",
            pin="1234",
            is_active=True
        )

    def test_create_session(self, user):
        """Test creating a cash session."""
        session = CashSession.objects.create(
            user=user,
            opening_balance=Decimal('100.00')
        )

        assert session.id is not None
        assert session.status == 'open'
        assert session.opening_balance == Decimal('100.00')

    def test_session_number_auto_generated(self, user):
        """Test session number is auto-generated."""
        session = CashSession.objects.create(
            user=user,
            opening_balance=Decimal('100.00')
        )

        assert session.session_number is not None
        assert session.session_number.startswith('CS-')

    def test_str_representation(self, user):
        """Test string representation."""
        session = CashSession.objects.create(
            user=user,
            opening_balance=Decimal('100.00')
        )

        assert user.name in str(session)
        assert 'open' in str(session)

    def test_close_session(self, user):
        """Test closing a session."""
        session = CashSession.objects.create(
            user=user,
            opening_balance=Decimal('100.00')
        )

        session.close_session(
            closing_balance=Decimal('150.00'),
            notes='End of day'
        )

        session.refresh_from_db()
        assert session.status == 'closed'
        assert session.closing_balance == Decimal('150.00')
        assert session.closed_at is not None
        assert session.closing_notes == 'End of day'

    def test_close_session_calculates_expected_balance(self, user):
        """Test closing session calculates expected balance."""
        session = CashSession.objects.create(
            user=user,
            opening_balance=Decimal('100.00')
        )

        # Add some movements
        CashMovement.objects.create(
            session=session,
            movement_type='sale',
            amount=Decimal('50.00'),
            description='Sale 1'
        )

        session.close_session(closing_balance=Decimal('150.00'))

        session.refresh_from_db()
        assert session.expected_balance == Decimal('150.00')  # 100 + 50
        assert session.difference == Decimal('0.00')  # 150 - 150

    def test_close_session_calculates_difference(self, user):
        """Test closing session calculates difference."""
        session = CashSession.objects.create(
            user=user,
            opening_balance=Decimal('100.00')
        )

        # Expected should be 100, but we report 95 (shortage)
        session.close_session(closing_balance=Decimal('95.00'))

        session.refresh_from_db()
        assert session.difference == Decimal('-5.00')

    def test_get_total_sales(self, user):
        """Test get_total_sales method."""
        session = CashSession.objects.create(
            user=user,
            opening_balance=Decimal('100.00')
        )

        CashMovement.objects.create(
            session=session,
            movement_type='sale',
            amount=Decimal('25.00')
        )
        CashMovement.objects.create(
            session=session,
            movement_type='sale',
            amount=Decimal('35.00')
        )

        assert session.get_total_sales() == Decimal('60.00')

    def test_get_total_in(self, user):
        """Test get_total_in method."""
        session = CashSession.objects.create(
            user=user,
            opening_balance=Decimal('100.00')
        )

        CashMovement.objects.create(
            session=session,
            movement_type='in',
            amount=Decimal('50.00')
        )

        assert session.get_total_in() == Decimal('50.00')

    def test_get_total_out(self, user):
        """Test get_total_out method."""
        session = CashSession.objects.create(
            user=user,
            opening_balance=Decimal('100.00')
        )

        CashMovement.objects.create(
            session=session,
            movement_type='out',
            amount=Decimal('-30.00')  # Negative for out
        )

        assert session.get_total_out() == Decimal('30.00')  # Returns positive

    def test_get_current_balance(self, user):
        """Test get_current_balance method."""
        session = CashSession.objects.create(
            user=user,
            opening_balance=Decimal('100.00')
        )

        CashMovement.objects.create(
            session=session,
            movement_type='sale',
            amount=Decimal('50.00')
        )
        CashMovement.objects.create(
            session=session,
            movement_type='out',
            amount=Decimal('-20.00')
        )

        # 100 + 50 - 20 = 130
        assert session.get_current_balance() == Decimal('130.00')

    def test_get_current_session(self, user):
        """Test get_current_session class method."""
        session = CashSession.objects.create(
            user=user,
            opening_balance=Decimal('100.00'),
            status='open'
        )

        current = CashSession.get_current_session()

        assert current == session

    def test_get_current_session_none_when_all_closed(self, user):
        """Test get_current_session returns None when no open session."""
        CashSession.objects.create(
            user=user,
            opening_balance=Decimal('100.00'),
            status='closed'
        )

        current = CashSession.get_current_session()

        assert current is None

    def test_open_for_user(self, user):
        """Test open_for_user class method."""
        session = CashSession.open_for_user(
            user=user,
            opening_balance=Decimal('200.00')
        )

        assert session.user == user
        assert session.status == 'open'
        assert session.opening_balance == Decimal('200.00')

    def test_open_for_user_returns_existing(self, user):
        """Test open_for_user returns existing open session."""
        existing = CashSession.objects.create(
            user=user,
            opening_balance=Decimal('100.00'),
            status='open'
        )

        session = CashSession.open_for_user(user=user)

        assert session == existing

    def test_open_for_user_uses_last_closing_balance(self, user):
        """Test open_for_user uses last closing balance if none provided."""
        # Create and close a session
        old_session = CashSession.objects.create(
            user=user,
            opening_balance=Decimal('100.00'),
            status='closed',
            closing_balance=Decimal('250.00'),
            closed_at=timezone.now()
        )

        # Open new session without specifying balance
        new_session = CashSession.open_for_user(user=user)

        assert new_session.opening_balance == Decimal('250.00')

    def test_ordering_by_opened_at(self, user):
        """Test sessions are ordered by opened_at descending."""
        session1 = CashSession.objects.create(user=user, opening_balance=100)
        session2 = CashSession.objects.create(user=user, opening_balance=100)

        sessions = list(CashSession.objects.all())

        assert sessions[0] == session2
        assert sessions[1] == session1


@pytest.mark.django_db
class TestCashMovement:
    """Tests for CashMovement model."""

    @pytest.fixture
    def session(self):
        """Create a test session."""
        user = LocalUser.objects.create(name="Test", pin="1234")
        return CashSession.objects.create(
            user=user,
            opening_balance=Decimal('100.00')
        )

    def test_create_sale_movement(self, session):
        """Test creating a sale movement."""
        movement = CashMovement.objects.create(
            session=session,
            movement_type='sale',
            amount=Decimal('50.00'),
            sale_reference='SALE-001',
            description='Test sale'
        )

        assert movement.id is not None
        assert movement.movement_type == 'sale'
        assert movement.amount == Decimal('50.00')

    def test_create_cash_in_movement(self, session):
        """Test creating a cash in movement."""
        movement = CashMovement.objects.create(
            session=session,
            movement_type='in',
            amount=Decimal('100.00'),
            description='Extra change'
        )

        assert movement.movement_type == 'in'

    def test_create_cash_out_movement(self, session):
        """Test creating a cash out movement."""
        movement = CashMovement.objects.create(
            session=session,
            movement_type='out',
            amount=Decimal('-50.00'),
            description='Supplier payment'
        )

        assert movement.movement_type == 'out'
        assert movement.amount == Decimal('-50.00')

    def test_str_representation(self, session):
        """Test string representation."""
        movement = CashMovement.objects.create(
            session=session,
            movement_type='sale',
            amount=Decimal('75.00')
        )

        assert 'Sale' in str(movement)
        assert '75.00' in str(movement)

    def test_ordering_by_created_at(self, session):
        """Test movements are ordered by created_at descending."""
        mov1 = CashMovement.objects.create(
            session=session,
            movement_type='sale',
            amount=10
        )
        mov2 = CashMovement.objects.create(
            session=session,
            movement_type='in',
            amount=20
        )

        movements = list(CashMovement.objects.all())

        assert movements[0] == mov2
        assert movements[1] == mov1


@pytest.mark.django_db
class TestCashCount:
    """Tests for CashCount model."""

    @pytest.fixture
    def session(self):
        """Create a test session."""
        user = LocalUser.objects.create(name="Test", pin="1234")
        return CashSession.objects.create(
            user=user,
            opening_balance=Decimal('100.00')
        )

    def test_create_opening_count(self, session):
        """Test creating an opening count."""
        count = CashCount.objects.create(
            session=session,
            count_type='opening',
            denominations={
                'bills': {'50': 1, '20': 2},
                'coins': {'2': 5}
            },
            total=Decimal('100.00')
        )

        assert count.id is not None
        assert count.count_type == 'opening'

    def test_create_closing_count(self, session):
        """Test creating a closing count."""
        count = CashCount.objects.create(
            session=session,
            count_type='closing',
            total=Decimal('150.00')
        )

        assert count.count_type == 'closing'

    def test_str_representation(self, session):
        """Test string representation."""
        count = CashCount.objects.create(
            session=session,
            count_type='opening',
            total=Decimal('100.00')
        )

        assert 'Opening' in str(count)
        assert '100.00' in str(count)

    def test_calculate_total_from_denominations(self, session):
        """Test calculating total from denominations."""
        count = CashCount(
            session=session,
            count_type='opening',
            denominations={
                'bills': {'50': 2, '20': 3},  # 100 + 60 = 160
                'coins': {'2': 10, '1': 5}    # 20 + 5 = 25
            }
        )

        total = count.calculate_total_from_denominations()

        assert total == Decimal('185.00')

    def test_auto_calculate_total_on_save(self, session):
        """Test total is auto-calculated on save if not provided."""
        count = CashCount.objects.create(
            session=session,
            count_type='opening',
            denominations={
                'bills': {'20': 5},  # 100
                'coins': {'1': 10}   # 10
            }
        )

        assert count.total == Decimal('110.00')


@pytest.mark.django_db
class TestCashSessionIndexes:
    """Tests for CashSession model indexes."""

    def test_user_status_index_exists(self):
        """Test user-status index exists."""
        indexes = CashSession._meta.indexes
        index_fields = [idx.fields for idx in indexes]

        assert ['user', 'status'] in index_fields

    def test_status_opened_at_index_exists(self):
        """Test status-opened_at index exists."""
        indexes = CashSession._meta.indexes
        index_fields = [idx.fields for idx in indexes]

        assert ['status', 'opened_at'] in index_fields


@pytest.mark.django_db
class TestCashMovementIndexes:
    """Tests for CashMovement model indexes."""

    def test_session_movement_type_index_exists(self):
        """Test session-movement_type index exists."""
        indexes = CashMovement._meta.indexes
        index_fields = [idx.fields for idx in indexes]

        assert ['session', 'movement_type'] in index_fields

    def test_sale_reference_index_exists(self):
        """Test sale_reference index exists."""
        indexes = CashMovement._meta.indexes
        index_fields = [idx.fields for idx in indexes]

        assert ['sale_reference'] in index_fields

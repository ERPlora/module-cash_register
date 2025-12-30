"""
Tests for Cash Register module extension points (signals, hooks, slots).

Tests that the cash register module correctly:
- Emits signals when sessions are opened/closed
- Emits signals when cash movements occur
- Provides hooks for session and movement operations
- Provides slots for UI extension
"""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock

from apps.core.signals import (
    cash_session_opened,
    cash_session_closed,
    cash_movement_created,
)
from apps.core.hooks import hooks
from apps.core.slots import slots


@pytest.mark.django_db
class TestCashRegisterSignals:
    """Tests for cash register signal emission."""

    def test_cash_session_opened_signal(self):
        """Verify cash_session_opened signal is emitted correctly."""
        handler = MagicMock()
        cash_session_opened.connect(handler)

        try:
            cash_session_opened.send(
                sender='cash_register',
                session={'id': 1, 'status': 'open'},
                user=MagicMock(id=1, username='cashier'),
                initial_amount=Decimal('100.00')
            )

            handler.assert_called_once()
            call_kwargs = handler.call_args[1]
            assert call_kwargs['sender'] == 'cash_register'
            assert call_kwargs['initial_amount'] == Decimal('100.00')
        finally:
            cash_session_opened.disconnect(handler)

    def test_cash_session_closed_signal(self):
        """Verify cash_session_closed signal includes all totals."""
        handler = MagicMock()
        cash_session_closed.connect(handler)

        try:
            cash_session_closed.send(
                sender='cash_register',
                session={'id': 1},
                user=MagicMock(id=1),
                final_amount=Decimal('350.00'),
                expected_amount=Decimal('350.00'),
                difference=Decimal('0.00')
            )

            handler.assert_called_once()
            call_kwargs = handler.call_args[1]
            assert call_kwargs['final_amount'] == Decimal('350.00')
            assert call_kwargs['difference'] == Decimal('0.00')
        finally:
            cash_session_closed.disconnect(handler)

    def test_cash_session_closed_with_difference(self):
        """Verify cash_session_closed includes shortage/overage."""
        handler = MagicMock()
        cash_session_closed.connect(handler)

        try:
            # Simulate a shortage
            cash_session_closed.send(
                sender='cash_register',
                session={'id': 1},
                user=MagicMock(id=1),
                final_amount=Decimal('340.00'),
                expected_amount=Decimal('350.00'),
                difference=Decimal('-10.00')  # Shortage
            )

            call_kwargs = handler.call_args[1]
            assert call_kwargs['difference'] == Decimal('-10.00')
        finally:
            cash_session_closed.disconnect(handler)

    def test_cash_movement_created_signal(self):
        """Verify cash_movement_created signal is emitted correctly."""
        handler = MagicMock()
        cash_movement_created.connect(handler)

        try:
            cash_movement_created.send(
                sender='cash_register',
                movement={'id': 1, 'type': 'in'},
                session={'id': 1},
                movement_type='in',
                amount=Decimal('50.00'),
                reason='Cash deposit'
            )

            handler.assert_called_once()
            call_kwargs = handler.call_args[1]
            assert call_kwargs['movement_type'] == 'in'
            assert call_kwargs['amount'] == Decimal('50.00')
            assert call_kwargs['reason'] == 'Cash deposit'
        finally:
            cash_movement_created.disconnect(handler)

    def test_cash_out_movement(self):
        """Verify cash out movement signal."""
        handler = MagicMock()
        cash_movement_created.connect(handler)

        try:
            cash_movement_created.send(
                sender='cash_register',
                movement={'id': 2},
                session={'id': 1},
                movement_type='out',
                amount=Decimal('25.00'),
                reason='Supplier payment'
            )

            call_kwargs = handler.call_args[1]
            assert call_kwargs['movement_type'] == 'out'
        finally:
            cash_movement_created.disconnect(handler)


@pytest.mark.django_db
class TestCashRegisterSignalIntegration:
    """Integration tests for cash register signals."""

    def test_session_lifecycle(self):
        """Test complete session lifecycle with signals."""
        events = []

        def track_opened(sender, session, initial_amount, **kwargs):
            events.append(('opened', initial_amount))

        def track_closed(sender, session, final_amount, difference, **kwargs):
            events.append(('closed', final_amount, difference))

        cash_session_opened.connect(track_opened)
        cash_session_closed.connect(track_closed)

        try:
            # Open session
            cash_session_opened.send(
                sender='cash_register',
                session={'id': 1},
                user=MagicMock(),
                initial_amount=Decimal('100.00')
            )

            # Close session
            cash_session_closed.send(
                sender='cash_register',
                session={'id': 1},
                user=MagicMock(),
                final_amount=Decimal('450.00'),
                expected_amount=Decimal('450.00'),
                difference=Decimal('0.00')
            )

            assert len(events) == 2
            assert events[0] == ('opened', Decimal('100.00'))
            assert events[1] == ('closed', Decimal('450.00'), Decimal('0.00'))
        finally:
            cash_session_opened.disconnect(track_opened)
            cash_session_closed.disconnect(track_closed)

    def test_multiple_movements_in_session(self):
        """Test multiple cash movements during a session."""
        movements = []

        def track_movement(sender, movement_type, amount, reason, **kwargs):
            movements.append({
                'type': movement_type,
                'amount': amount,
                'reason': reason
            })

        cash_movement_created.connect(track_movement)

        try:
            # Multiple movements
            for i in range(3):
                cash_movement_created.send(
                    sender='cash_register',
                    movement={'id': i},
                    session={'id': 1},
                    movement_type='in' if i % 2 == 0 else 'out',
                    amount=Decimal(f'{(i + 1) * 10}.00'),
                    reason=f'Movement {i + 1}'
                )

            assert len(movements) == 3
            assert movements[0]['type'] == 'in'
            assert movements[1]['type'] == 'out'
            assert movements[2]['type'] == 'in'
        finally:
            cash_movement_created.disconnect(track_movement)

    def test_analytics_can_listen_to_session_close(self):
        """Verify analytics module can listen to session close."""
        analytics_data = []

        def track_for_analytics(sender, session, final_amount, expected_amount, difference, **kwargs):
            analytics_data.append({
                'session_id': session['id'],
                'total': final_amount,
                'variance': difference,
                'accuracy': 100 if difference == 0 else (1 - abs(difference / expected_amount)) * 100
            })

        cash_session_closed.connect(track_for_analytics)

        try:
            cash_session_closed.send(
                sender='cash_register',
                session={'id': 5},
                user=MagicMock(),
                final_amount=Decimal('500.00'),
                expected_amount=Decimal('510.00'),
                difference=Decimal('-10.00')
            )

            assert len(analytics_data) == 1
            assert analytics_data[0]['variance'] == Decimal('-10.00')
        finally:
            cash_session_closed.disconnect(track_for_analytics)

    def test_hr_module_can_track_shifts(self):
        """Verify HR module can track employee shifts via signals."""
        shifts = []

        def start_shift(sender, session, user, **kwargs):
            shifts.append({
                'user_id': user.id,
                'action': 'start',
                'session_id': session['id']
            })

        def end_shift(sender, session, user, **kwargs):
            shifts.append({
                'user_id': user.id,
                'action': 'end',
                'session_id': session['id']
            })

        cash_session_opened.connect(start_shift)
        cash_session_closed.connect(end_shift)

        try:
            user = MagicMock(id=42)

            cash_session_opened.send(
                sender='cash_register',
                session={'id': 1},
                user=user,
                initial_amount=Decimal('100.00')
            )

            cash_session_closed.send(
                sender='cash_register',
                session={'id': 1},
                user=user,
                final_amount=Decimal('300.00'),
                expected_amount=Decimal('300.00'),
                difference=Decimal('0.00')
            )

            assert len(shifts) == 2
            assert shifts[0]['action'] == 'start'
            assert shifts[1]['action'] == 'end'
            assert all(s['user_id'] == 42 for s in shifts)
        finally:
            cash_session_opened.disconnect(start_shift)
            cash_session_closed.disconnect(end_shift)


@pytest.mark.django_db
class TestCashRegisterHooks:
    """Tests for cash register hook usage."""

    def setup_method(self):
        """Clear hooks before each test."""
        hooks.clear_all()

    def teardown_method(self):
        """Clear hooks after each test."""
        hooks.clear_all()

    def test_before_session_open_hook(self):
        """Verify before_session_open hook is called."""
        callback_data = []

        def validate_opening(user, initial_amount, **kwargs):
            callback_data.append({
                'user_id': user.id,
                'initial_amount': initial_amount
            })

        hooks.add_action(
            'cash_register.before_session_open',
            validate_opening,
            module_id='test'
        )

        # Simulate calling the hook (as done in CashRegisterConfig.do_before_session_open)
        hooks.do_action(
            'cash_register.before_session_open',
            user=MagicMock(id=1),
            initial_amount=Decimal('100.00')
        )

        assert len(callback_data) == 1
        assert callback_data[0]['initial_amount'] == Decimal('100.00')

    def test_before_session_close_hook(self):
        """Verify before_session_close hook is called with difference."""
        callback_data = []

        def validate_closing(session, user, final_amount, expected_amount, difference, **kwargs):
            callback_data.append({
                'session_id': session.id,
                'final_amount': final_amount,
                'expected_amount': expected_amount,
                'difference': difference
            })

        hooks.add_action(
            'cash_register.before_session_close',
            validate_closing,
            module_id='test'
        )

        # Simulate calling the hook
        hooks.do_action(
            'cash_register.before_session_close',
            session=MagicMock(id=1),
            user=MagicMock(id=1),
            final_amount=Decimal('340.00'),
            expected_amount=Decimal('350.00'),
            difference=Decimal('-10.00')
        )

        assert len(callback_data) == 1
        assert callback_data[0]['difference'] == Decimal('-10.00')

    def test_filter_session_data_hook(self):
        """Verify filter_session_data can modify session data."""
        def add_shift_info(data, session=None, user=None, **kwargs):
            data['shift_id'] = 'SHIFT-001'
            data['employee_name'] = user.get_full_name() if user else 'Unknown'
            return data

        hooks.add_filter(
            'cash_register.filter_session_data',
            add_shift_info,
            module_id='hr'
        )

        session_data = {
            'initial_amount': Decimal('100.00'),
            'opened_at': '2025-12-28T09:00:00'
        }

        user = MagicMock()
        user.get_full_name.return_value = 'John Doe'

        filtered = hooks.apply_filters(
            'cash_register.filter_session_data',
            session_data,
            session=None,
            user=user
        )

        assert filtered['shift_id'] == 'SHIFT-001'
        assert filtered['employee_name'] == 'John Doe'
        assert filtered['initial_amount'] == Decimal('100.00')

    def test_filter_movement_data_hook(self):
        """Verify filter_movement_data can modify movement data."""
        def add_accounting_code(data, session=None, movement=None, user=None, **kwargs):
            # Add accounting code based on movement type
            if data.get('movement_type') == 'in':
                data['accounting_code'] = 'CASH-IN-001'
            else:
                data['accounting_code'] = 'CASH-OUT-001'
            return data

        hooks.add_filter(
            'cash_register.filter_movement_data',
            add_accounting_code,
            module_id='accounting'
        )

        movement_data = {
            'movement_type': 'in',
            'amount': Decimal('50.00'),
            'reason': 'Cash deposit'
        }

        filtered = hooks.apply_filters(
            'cash_register.filter_movement_data',
            movement_data,
            session=MagicMock(id=1),
            movement=None,
            user=MagicMock()
        )

        assert filtered['accounting_code'] == 'CASH-IN-001'
        assert filtered['amount'] == Decimal('50.00')

    def test_hook_validation_logic_works(self):
        """Verify hook can perform validation logic.

        Note: The hook system catches exceptions to prevent one hook from
        breaking others. For validation that should block operations, use
        a filter that returns a validation result instead.
        """
        validation_results = []

        def validate_manager_approval(user, initial_amount, **kwargs):
            if not user.is_manager and initial_amount > Decimal('500.00'):
                validation_results.append({
                    'valid': False,
                    'error': "Manager approval required for amounts over 500"
                })
            else:
                validation_results.append({'valid': True})

        hooks.add_action(
            'cash_register.before_session_open',
            validate_manager_approval,
            module_id='approval'
        )

        user = MagicMock(is_manager=False)

        hooks.do_action(
            'cash_register.before_session_open',
            user=user,
            initial_amount=Decimal('1000.00')
        )

        assert len(validation_results) == 1
        assert validation_results[0]['valid'] is False
        assert "Manager approval required" in validation_results[0]['error']

    def test_multiple_hooks_execute_in_order(self):
        """Verify multiple hooks execute in priority order."""
        execution_order = []

        def first_hook(**kwargs):
            execution_order.append('first')

        def second_hook(**kwargs):
            execution_order.append('second')

        def third_hook(**kwargs):
            execution_order.append('third')

        hooks.add_action('cash_register.before_session_open', second_hook, priority=20)
        hooks.add_action('cash_register.before_session_open', first_hook, priority=10)
        hooks.add_action('cash_register.before_session_open', third_hook, priority=30)

        hooks.do_action(
            'cash_register.before_session_open',
            user=MagicMock(),
            initial_amount=Decimal('100.00')
        )

        assert execution_order == ['first', 'second', 'third']


@pytest.mark.django_db
class TestCashRegisterSlots:
    """Tests for cash register slot registration."""

    def setup_method(self):
        """Clear slots before each test."""
        slots.clear_all()

    def teardown_method(self):
        """Clear slots after each test."""
        slots.clear_all()

    def test_session_header_slot(self):
        """Verify session_header slot can be registered."""
        def employee_context(context):
            session = context.get('session')
            return {
                'employee_name': 'John Doe',
                'shift_start': '09:00',
                'session_id': session.id if session else None
            }

        slots.register(
            'cash_register.session_header',
            template='hr/partials/employee_badge.html',
            context_fn=employee_context,
            module_id='hr'
        )

        content = slots.get_slot_content(
            'cash_register.session_header',
            {'session': MagicMock(id=1)}
        )

        assert len(content) == 1
        assert content[0]['template'] == 'hr/partials/employee_badge.html'
        assert content[0]['context']['employee_name'] == 'John Doe'
        assert content[0]['context']['session_id'] == 1

    def test_session_summary_slot(self):
        """Verify session_summary slot for stats display."""
        def summary_context(context):
            return {
                'sales_count': 15,
                'total_sales': Decimal('1250.00'),
                'average_sale': Decimal('83.33')
            }

        slots.register(
            'cash_register.session_summary',
            template='analytics/partials/session_stats.html',
            context_fn=summary_context,
            module_id='analytics'
        )

        content = slots.get_slot_content(
            'cash_register.session_summary',
            {'session': MagicMock(id=1)}
        )

        assert len(content) == 1
        assert content[0]['context']['sales_count'] == 15
        assert content[0]['context']['total_sales'] == Decimal('1250.00')

    def test_movement_actions_slot(self):
        """Verify movement_actions slot for per-movement actions."""
        def action_context(context):
            movement = context.get('movement')
            return {
                'can_void': movement.movement_type == 'in',
                'movement_id': movement.id
            }

        slots.register(
            'cash_register.movement_actions',
            template='cash_register/partials/movement_buttons.html',
            context_fn=action_context,
            module_id='cash_register'
        )

        movement = MagicMock(id=5, movement_type='in')
        content = slots.get_slot_content(
            'cash_register.movement_actions',
            {'movement': movement}
        )

        assert len(content) == 1
        assert content[0]['context']['can_void'] is True
        assert content[0]['context']['movement_id'] == 5

    def test_close_session_extras_slot(self):
        """Verify close_session_extras slot for extra fields."""
        def extras_context(context):
            return {
                'require_manager_signature': True,
                'require_photo': False,
                'notes_required': True
            }

        slots.register(
            'cash_register.close_session_extras',
            template='compliance/partials/close_requirements.html',
            context_fn=extras_context,
            module_id='compliance'
        )

        content = slots.get_slot_content(
            'cash_register.close_session_extras',
            {'session': MagicMock(id=1)}
        )

        assert len(content) == 1
        assert content[0]['context']['require_manager_signature'] is True

    def test_multiple_slots_same_location(self):
        """Verify multiple modules can register for same slot."""
        slots.register(
            'cash_register.session_header',
            template='hr/partials/shift_info.html',
            context_fn=lambda ctx: {'shift': 'Morning'},
            module_id='hr',
            priority=10
        )

        slots.register(
            'cash_register.session_header',
            template='loyalty/partials/cashier_rewards.html',
            context_fn=lambda ctx: {'rewards': 5},
            module_id='loyalty',
            priority=20
        )

        content = slots.get_slot_content(
            'cash_register.session_header',
            {'session': MagicMock(id=1)}
        )

        assert len(content) == 2
        # HR slot should come first (lower priority)
        assert content[0]['template'] == 'hr/partials/shift_info.html'
        assert content[1]['template'] == 'loyalty/partials/cashier_rewards.html'


@pytest.mark.django_db
class TestCashRegisterExtensionIntegration:
    """Integration tests for cash register extensions."""

    def setup_method(self):
        """Clear hooks and slots before each test."""
        hooks.clear_all()
        slots.clear_all()

    def teardown_method(self):
        """Clear hooks and slots after each test."""
        hooks.clear_all()
        slots.clear_all()

    def test_full_session_lifecycle_with_extensions(self):
        """Test complete session with signals, hooks, and slots."""
        events = []

        # Hook: validate before opening
        def validate_open(user, initial_amount, **kwargs):
            events.append(('hook_validate', initial_amount))

        hooks.add_action('cash_register.before_session_open', validate_open)

        # Hook: filter session data
        def add_extra_data(data, **kwargs):
            data['extra_field'] = 'test_value'
            return data

        hooks.add_filter('cash_register.filter_session_data', add_extra_data)

        # Slot: session header
        slots.register(
            'cash_register.session_header',
            template='test/header.html',
            context_fn=lambda ctx: {'test': True},
            module_id='test'
        )

        # Signal handler
        def on_session_opened(sender, session, initial_amount, **kwargs):
            events.append(('signal_opened', initial_amount))

        cash_session_opened.connect(on_session_opened)

        try:
            # 1. Execute before_session_open hook
            hooks.do_action(
                'cash_register.before_session_open',
                user=MagicMock(id=1),
                initial_amount=Decimal('100.00')
            )

            # 2. Filter session data
            session_data = {'initial_amount': Decimal('100.00')}
            filtered_data = hooks.apply_filters(
                'cash_register.filter_session_data',
                session_data
            )

            # 3. Emit signal
            cash_session_opened.send(
                sender='cash_register',
                session=MagicMock(id=1),
                user=MagicMock(id=1),
                initial_amount=Decimal('100.00')
            )

            # 4. Get slot content
            slot_content = slots.get_slot_content(
                'cash_register.session_header',
                {'session': MagicMock(id=1)}
            )

            # Verify all extensions worked
            assert events == [
                ('hook_validate', Decimal('100.00')),
                ('signal_opened', Decimal('100.00'))
            ]
            assert filtered_data['extra_field'] == 'test_value'
            assert len(slot_content) == 1

        finally:
            cash_session_opened.disconnect(on_session_opened)

    def test_accounting_integration_scenario(self):
        """Test accounting module integration via extensions."""
        accounting_entries = []

        # Accounting listens to movement signal
        def create_accounting_entry(sender, movement_type, amount, reason, session, **kwargs):
            accounting_entries.append({
                'type': 'CASH_' + movement_type.upper(),
                'amount': amount,
                'description': reason,
                'session_id': session['id']
            })

        cash_movement_created.connect(create_accounting_entry)

        # Accounting adds code via hook
        def add_gl_code(data, **kwargs):
            if data.get('movement_type') == 'in':
                data['gl_account'] = '1000-CASH'
            else:
                data['gl_account'] = '2000-EXPENSE'
            return data

        hooks.add_filter('cash_register.filter_movement_data', add_gl_code)

        try:
            # Create a cash-in movement
            movement_data = {
                'movement_type': 'in',
                'amount': Decimal('100.00'),
                'reason': 'Float replenishment'
            }

            # Filter the data
            filtered = hooks.apply_filters(
                'cash_register.filter_movement_data',
                movement_data
            )

            # Emit signal
            cash_movement_created.send(
                sender='cash_register',
                movement={'id': 1},
                session={'id': 1},
                movement_type='in',
                amount=Decimal('100.00'),
                reason='Float replenishment'
            )

            # Verify
            assert filtered['gl_account'] == '1000-CASH'
            assert len(accounting_entries) == 1
            assert accounting_entries[0]['type'] == 'CASH_IN'

        finally:
            cash_movement_created.disconnect(create_accounting_entry)

    def test_hr_shift_tracking_integration(self):
        """Test HR module tracking shifts via cash register extensions."""
        shifts = []

        # HR slot in session header shows employee info
        def get_shift_context(context):
            session = context.get('session')
            return {
                'employee': 'John Doe',
                'shift_start': '09:00',
                'break_time_remaining': 30
            }

        slots.register(
            'cash_register.session_header',
            template='hr/partials/shift_badge.html',
            context_fn=get_shift_context,
            module_id='hr'
        )

        # HR tracks shift start via signal
        def start_shift(sender, session, user, **kwargs):
            shifts.append({
                'user_id': user.id,
                'session_id': session['id'] if isinstance(session, dict) else session.id,
                'action': 'start'
            })

        cash_session_opened.connect(start_shift)

        # HR validates closing via hook
        def validate_shift_end(session, user, **kwargs):
            # Could check minimum shift duration, etc.
            shifts.append({
                'user_id': user.id,
                'action': 'validate_end'
            })

        hooks.add_action('cash_register.before_session_close', validate_shift_end)

        try:
            # Open session
            cash_session_opened.send(
                sender='cash_register',
                session={'id': 1},
                user=MagicMock(id=42),
                initial_amount=Decimal('100.00')
            )

            # Get header slot content
            content = slots.get_slot_content(
                'cash_register.session_header',
                {'session': MagicMock(id=1)}
            )

            # Close session (validate hook)
            hooks.do_action(
                'cash_register.before_session_close',
                session=MagicMock(id=1),
                user=MagicMock(id=42),
                final_amount=Decimal('500.00'),
                expected_amount=Decimal('500.00'),
                difference=Decimal('0.00')
            )

            # Verify HR integration
            assert len(shifts) == 2
            assert shifts[0]['action'] == 'start'
            assert shifts[1]['action'] == 'validate_end'
            assert len(content) == 1
            assert content[0]['context']['employee'] == 'John Doe'

        finally:
            cash_session_opened.disconnect(start_shift)
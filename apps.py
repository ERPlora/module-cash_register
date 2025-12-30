from django.apps import AppConfig


class CashRegisterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cash_register'
    verbose_name = 'Cash Register'

    def ready(self):
        """
        Register extension points for the Cash Register module.

        This module EMITS signals:
        - cash_session_opened: When a cash session/shift starts
        - cash_session_closed: When a cash session/shift ends
        - cash_movement_created: When cash is added/removed from register

        This module LISTENS to:
        - sale_completed: To record cash movements for cash sales

        This module provides HOOKS:
        - cash_register.before_session_open: Before opening a session
        - cash_register.before_session_close: Before closing a session
        - cash_register.filter_session_data: Filter session data before save
        - cash_register.filter_movement_data: Filter movement data before save

        This module provides SLOTS:
        - cash_register.session_header: Header area in session view
        - cash_register.session_summary: Summary area with stats
        - cash_register.movement_actions: Actions per movement
        - cash_register.close_session_extras: Extra fields when closing
        """
        self._register_signal_handlers()
        self._register_hooks()
        self._register_slots()

    def _register_signal_handlers(self):
        """Register handlers for signals from other modules."""
        from django.dispatch import receiver
        from apps.core.signals import sale_completed

        @receiver(sale_completed)
        def on_sale_completed(sender, sale, user, payment_method, **kwargs):
            """
            When a cash sale completes, it's already handled in sales module.
            This handler is for additional processing if needed.
            """
            # The cash movement is already created in sales/views.py
            # This is here for future extensions (e.g., analytics, reporting)
            pass

    def _register_hooks(self):
        """
        Register hooks that this module OFFERS to other modules.

        Other modules can use these hooks to:
        - Validate session open/close operations
        - Add data to sessions/movements
        - Integrate with HR (shifts), accounting, etc.
        """
        # Hooks are defined here but called from views
        # This method documents what hooks cash_register offers
        pass

    def _register_slots(self):
        """
        Register slots that this module OFFERS to other modules.

        Slots are template injection points where other modules
        can add their content.
        """
        # Slots are defined in templates using {% render_slot %}
        # This method documents what slots cash_register offers
        pass

    # =========================================================================
    # Hook Helper Methods (called from views)
    # =========================================================================

    @staticmethod
    def do_before_session_open(user, initial_amount):
        """
        Execute before_session_open hook.

        Called before opening a new cash session. Other modules can:
        - Validate the opening (raise ValidationError to block)
        - Check employee status
        - Log shift start

        Args:
            user: User opening the session
            initial_amount: Starting cash amount

        Raises:
            ValidationError: If a hook wants to block the opening
        """
        from apps.core.hooks import hooks

        hooks.do_action(
            'cash_register.before_session_open',
            user=user,
            initial_amount=initial_amount
        )

    @staticmethod
    def do_before_session_close(session, user, final_amount, expected_amount):
        """
        Execute before_session_close hook.

        Called before closing a cash session. Other modules can:
        - Validate the closing
        - Check for pending sales
        - Alert on discrepancies

        Args:
            session: CashSession instance
            user: User closing the session
            final_amount: Actual cash counted
            expected_amount: System-calculated expected amount

        Raises:
            ValidationError: If a hook wants to block the closing
        """
        from apps.core.hooks import hooks

        hooks.do_action(
            'cash_register.before_session_close',
            session=session,
            user=user,
            final_amount=final_amount,
            expected_amount=expected_amount,
            difference=final_amount - expected_amount
        )

    @staticmethod
    def filter_session_data(data, session=None, user=None):
        """
        Apply filter_session_data hook.

        Called before saving session data. Other modules can:
        - Add calculated fields
        - Validate data
        - Include HR shift info

        Args:
            data: Dict of session data
            session: Existing session (None for new)
            user: User performing the action

        Returns:
            Modified data dict
        """
        from apps.core.hooks import hooks

        return hooks.apply_filters(
            'cash_register.filter_session_data',
            data,
            session=session,
            user=user
        )

    @staticmethod
    def filter_movement_data(data, session=None, movement=None, user=None):
        """
        Apply filter_movement_data hook.

        Called before saving movement data. Other modules can:
        - Add accounting codes
        - Validate amounts
        - Add approval requirements

        Args:
            data: Dict of movement data
            session: Related session
            movement: Existing movement (None for new)
            user: User performing the action

        Returns:
            Modified data dict
        """
        from apps.core.hooks import hooks

        return hooks.apply_filters(
            'cash_register.filter_movement_data',
            data,
            session=session,
            movement=movement,
            user=user
        )

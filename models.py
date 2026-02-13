from decimal import Decimal

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator

from apps.core.models import HubBaseModel


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class CashRegisterSettings(HubBaseModel):
    """Per-hub cash register configuration."""

    enable_cash_register = models.BooleanField(
        _('Enable Cash Register'),
        default=True,
    )
    require_opening_balance = models.BooleanField(
        _('Require Opening Balance'),
        default=False,
        help_text=_('Require manual cash count when opening a session.'),
    )
    require_closing_balance = models.BooleanField(
        _('Require Closing Balance'),
        default=True,
        help_text=_('Require manual cash count when closing a session.'),
    )
    allow_negative_balance = models.BooleanField(
        _('Allow Negative Balance'),
        default=False,
    )
    auto_open_session_on_login = models.BooleanField(
        _('Auto Open on Login'),
        default=True,
        help_text=_('Automatically open a cash session when user logs in.'),
    )
    auto_close_session_on_logout = models.BooleanField(
        _('Auto Close on Logout'),
        default=True,
        help_text=_('Automatically close session when user logs out.'),
    )
    protected_pos_url = models.CharField(
        _('Protected POS URL'),
        max_length=200,
        default='/m/sales/pos/',
        blank=True,
        help_text=_('URL that requires an open cash session.'),
    )

    class Meta(HubBaseModel.Meta):
        db_table = 'cash_register_settings'
        verbose_name = _('Cash Register Settings')
        verbose_name_plural = _('Cash Register Settings')
        unique_together = [('hub_id',)]

    def __str__(self):
        return f"Cash Register Settings (hub {self.hub_id})"

    @classmethod
    def get_settings(cls, hub_id):
        settings, _ = cls.all_objects.get_or_create(hub_id=hub_id)
        return settings


# ---------------------------------------------------------------------------
# Cash Register (physical device)
# ---------------------------------------------------------------------------

class CashRegister(HubBaseModel):
    """Physical cash register or terminal."""

    name = models.CharField(_('Name'), max_length=100)
    is_active = models.BooleanField(_('Active'), default=True)

    class Meta(HubBaseModel.Meta):
        db_table = 'cash_register_register'
        verbose_name = _('Cash Register')
        verbose_name_plural = _('Cash Registers')
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def current_session(self):
        return self.sessions.filter(status='open', is_deleted=False).first()

    @property
    def is_open(self):
        return self.current_session is not None


# ---------------------------------------------------------------------------
# Cash Session
# ---------------------------------------------------------------------------

class CashSession(HubBaseModel):
    """
    Cash register session from opening to closing.
    User-centric: one session per user.
    """

    STATUS_CHOICES = [
        ('open', _('Open')),
        ('closed', _('Closed')),
        ('suspended', _('Suspended')),
    ]

    user = models.ForeignKey(
        'accounts.LocalUser',
        on_delete=models.CASCADE,
        related_name='cash_sessions',
        verbose_name=_('User'),
    )
    register = models.ForeignKey(
        CashRegister,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sessions',
        verbose_name=_('Register'),
    )
    session_number = models.CharField(
        _('Session Number'),
        max_length=50,
        db_index=True,
    )
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='open',
    )

    # Opening
    opened_at = models.DateTimeField(_('Opened At'), auto_now_add=True)
    opening_balance = models.DecimalField(
        _('Opening Balance'),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    opening_notes = models.TextField(_('Opening Notes'), blank=True, default='')

    # Closing
    closed_at = models.DateTimeField(_('Closed At'), null=True, blank=True)
    closing_balance = models.DecimalField(
        _('Closing Balance'),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    expected_balance = models.DecimalField(
        _('Expected Balance'),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    difference = models.DecimalField(
        _('Difference'),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    closing_notes = models.TextField(_('Closing Notes'), blank=True, default='')

    class Meta(HubBaseModel.Meta):
        db_table = 'cash_register_session'
        verbose_name = _('Cash Session')
        verbose_name_plural = _('Cash Sessions')
        ordering = ['-opened_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'opened_at']),
        ]

    def __str__(self):
        return f"Session {self.session_number} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.session_number:
            self.session_number = self.generate_session_number()
        super().save(*args, **kwargs)

    def generate_session_number(self):
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        initials = ''
        if self.user:
            initials = getattr(self.user, 'get_initials', lambda: 'XX')()
        return f"CS-{initials}-{timestamp}"

    def close_session(self, closing_balance, notes=''):
        """Close session and calculate differences."""
        self.status = 'closed'
        self.closed_at = timezone.now()
        self.closing_balance = Decimal(str(closing_balance))
        self.closing_notes = notes

        movements_total = self.movements.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
        self.expected_balance = self.opening_balance + movements_total
        self.difference = self.closing_balance - self.expected_balance
        self.save()

    def get_total_sales(self):
        return self.movements.filter(
            movement_type='sale',
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    def get_total_in(self):
        return self.movements.filter(
            movement_type='in',
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    def get_total_out(self):
        total = self.movements.filter(
            movement_type='out',
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        return abs(total)

    def get_total_refunds(self):
        total = self.movements.filter(
            movement_type='refund',
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        return abs(total)

    def get_current_balance(self):
        movements_total = self.movements.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
        return self.opening_balance + movements_total

    def get_duration(self):
        if self.status == 'open':
            duration = timezone.now() - self.opened_at
        elif self.closed_at:
            duration = self.closed_at - self.opened_at
        else:
            return "N/A"
        hours = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)
        return f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"

    @classmethod
    def get_current_session(cls, hub_id, user):
        """Get the currently open session for this user in this hub."""
        return cls.objects.filter(
            hub_id=hub_id, user=user, status='open', is_deleted=False,
        ).first()

    @classmethod
    def open_for_user(cls, hub_id, user, opening_balance=None, register=None):
        """Open a new session. Reuses last closing balance if none given."""
        existing = cls.objects.filter(
            hub_id=hub_id, user=user, status='open', is_deleted=False,
        ).first()
        if existing:
            return existing

        if opening_balance is None:
            last = cls.objects.filter(
                hub_id=hub_id, user=user, status='closed', is_deleted=False,
            ).order_by('-closed_at').first()
            opening_balance = last.closing_balance if last and last.closing_balance else Decimal('0.00')

        return cls.objects.create(
            hub_id=hub_id,
            user=user,
            register=register,
            opening_balance=opening_balance,
        )


# ---------------------------------------------------------------------------
# Cash Movement
# ---------------------------------------------------------------------------

class CashMovement(HubBaseModel):
    """Cash movement within a session."""

    MOVEMENT_TYPES = [
        ('sale', _('Sale')),
        ('refund', _('Refund')),
        ('in', _('Cash In')),
        ('out', _('Cash Out')),
    ]

    PAYMENT_METHODS = [
        ('cash', _('Cash')),
        ('card', _('Card')),
        ('transfer', _('Transfer')),
        ('other', _('Other')),
    ]

    session = models.ForeignKey(
        CashSession,
        on_delete=models.CASCADE,
        related_name='movements',
        verbose_name=_('Session'),
    )
    movement_type = models.CharField(
        _('Type'),
        max_length=20,
        choices=MOVEMENT_TYPES,
    )
    amount = models.DecimalField(
        _('Amount'),
        max_digits=12,
        decimal_places=2,
        help_text=_('Positive for in/sale, negative for out/refund.'),
    )
    payment_method = models.CharField(
        _('Payment Method'),
        max_length=20,
        choices=PAYMENT_METHODS,
        default='cash',
    )
    sale_reference = models.CharField(
        _('Sale Reference'),
        max_length=100,
        blank=True,
        default='',
    )
    description = models.TextField(_('Description'), blank=True, default='')
    employee = models.ForeignKey(
        'accounts.LocalUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cash_movements',
        verbose_name=_('Employee'),
    )

    class Meta(HubBaseModel.Meta):
        db_table = 'cash_register_movement'
        verbose_name = _('Cash Movement')
        verbose_name_plural = _('Cash Movements')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session', 'movement_type']),
            models.Index(fields=['sale_reference']),
        ]

    def __str__(self):
        return f"{self.get_movement_type_display()} - {self.amount}"

    @classmethod
    def record_sale(cls, hub_id, sale, session=None, employee=None):
        """Record a cash sale as a movement."""
        if session is None:
            return None
        return cls.objects.create(
            hub_id=hub_id,
            session=session,
            movement_type='sale',
            amount=sale.total,
            sale_reference=getattr(sale, 'sale_number', ''),
            description=f"Sale {getattr(sale, 'sale_number', '')}",
            employee=employee,
        )


# ---------------------------------------------------------------------------
# Cash Count (denomination breakdown)
# ---------------------------------------------------------------------------

class CashCount(HubBaseModel):
    """Cash denomination count at open/close."""

    COUNT_TYPES = [
        ('opening', _('Opening Count')),
        ('closing', _('Closing Count')),
    ]

    session = models.ForeignKey(
        CashSession,
        on_delete=models.CASCADE,
        related_name='counts',
        verbose_name=_('Session'),
    )
    count_type = models.CharField(
        _('Count Type'),
        max_length=20,
        choices=COUNT_TYPES,
    )
    denominations = models.JSONField(
        _('Denominations'),
        default=dict,
        help_text=_('{"bills": {"50": 2, "20": 5}, "coins": {"2": 10, "1": 20}}'),
    )
    total = models.DecimalField(
        _('Total'),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    notes = models.TextField(_('Notes'), blank=True, default='')
    counted_at = models.DateTimeField(_('Counted At'), auto_now_add=True)

    class Meta(HubBaseModel.Meta):
        db_table = 'cash_register_count'
        verbose_name = _('Cash Count')
        verbose_name_plural = _('Cash Counts')
        ordering = ['-counted_at']

    def __str__(self):
        return f"{self.get_count_type_display()} - {self.total}"

    def calculate_total_from_denominations(self):
        total = Decimal('0.00')
        for section in ('bills', 'coins'):
            if section in self.denominations:
                for denom, count in self.denominations[section].items():
                    total += Decimal(str(denom)) * Decimal(str(count))
        return total

    def save(self, *args, **kwargs):
        if (not self.total or self.total == Decimal('0.00')) and self.denominations:
            self.total = self.calculate_total_from_denominations()
        super().save(*args, **kwargs)

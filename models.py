from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal
from apps.accounts.models import LocalUser
import uuid


class CashRegisterConfig(models.Model):
    """
    Configuración del plugin Cash Register (Singleton).

    En esta versión simplificada:
    - El Hub ES la caja registradora única
    - Las sesiones se abren/cierran automáticamente con login/logout de usuarios
    """
    id = models.AutoField(primary_key=True)

    # Plugin settings
    enable_cash_register = models.BooleanField(
        default=True,
        help_text="Enable/disable cash register functionality"
    )
    require_opening_balance = models.BooleanField(
        default=False,
        help_text="Require manual cash count when user logs in (if False, uses previous closing balance)"
    )
    require_closing_balance = models.BooleanField(
        default=True,
        help_text="Require manual cash count when user logs out"
    )
    allow_negative_balance = models.BooleanField(
        default=False,
        help_text="Allow cash balance to go negative"
    )
    auto_open_session_on_login = models.BooleanField(
        default=True,
        help_text="Automatically open cash session when user logs in"
    )
    auto_close_session_on_logout = models.BooleanField(
        default=True,
        help_text="Automatically close cash session when user logs out"
    )
    protected_pos_url = models.CharField(
        max_length=200,
        default='/plugins/sales/pos/',
        blank=True,
        help_text="URL that requires open cash session (default: /plugins/sales/pos/)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'cash_register_config'
        verbose_name = 'Cash Register Configuration'
        verbose_name_plural = 'Cash Register Configuration'

    def __str__(self):
        return "Cash Register Configuration"

    @classmethod
    def get_config(cls):
        """Get or create singleton config"""
        config, created = cls.objects.get_or_create(pk=1)
        return config


class CashSession(models.Model):
    """
    Sesión de caja de un usuario.

    Flujo simplificado:
    1. Usuario hace login con PIN → Se abre CashSession automáticamente
    2. Usuario trabaja (ventas se registran automáticamente)
    3. Usuario hace logout → Se cierra CashSession con conteo final
    """
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Usuario que tiene la sesión
    user = models.ForeignKey(
        LocalUser,
        on_delete=models.CASCADE,
        related_name='cash_sessions',
        help_text="User who owns this session"
    )

    # Session info
    session_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Auto-generated session number"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='open'
    )

    # Opening
    opened_at = models.DateTimeField(auto_now_add=True)
    opening_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Cash in register at session opening"
    )
    opening_notes = models.TextField(blank=True)

    # Closing
    closed_at = models.DateTimeField(null=True, blank=True)
    closing_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Cash in register at session closing"
    )
    expected_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Expected balance based on movements"
    )
    difference = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Difference between expected and actual closing balance"
    )
    closing_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'cash_register_session'
        ordering = ['-opened_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'opened_at']),
        ]

    def __str__(self):
        return f"Session {self.session_number} - {self.user.name} ({self.status})"

    def save(self, *args, **kwargs):
        # Auto-generate session number
        if not self.session_number:
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            user_initials = self.user.get_initials()
            self.session_number = f"CS-{user_initials}-{timestamp}"
        super().save(*args, **kwargs)

    def close_session(self, closing_balance, notes=''):
        """Close the session and calculate differences"""
        self.status = 'closed'
        self.closed_at = timezone.now()
        self.closing_balance = closing_balance
        self.closing_notes = notes

        # Calculate expected balance
        movements_total = self.movements.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')

        self.expected_balance = self.opening_balance + movements_total
        self.difference = closing_balance - self.expected_balance

        self.save()

    def get_total_sales(self):
        """Get total sales for this session"""
        return self.movements.filter(
            movement_type='sale'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    def get_total_in(self):
        """Get total cash in movements"""
        return self.movements.filter(
            movement_type='in'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    def get_total_out(self):
        """Get total cash out movements (returned as positive number)"""
        total = self.movements.filter(
            movement_type='out'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        return abs(total)

    def get_current_balance(self):
        """Get current balance (opening + all movements)"""
        movements_total = self.movements.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
        return self.opening_balance + movements_total

    def get_duration(self):
        """Get session duration as formatted string"""
        if self.status == 'open':
            duration = timezone.now() - self.opened_at
        elif self.closed_at:
            duration = self.closed_at - self.opened_at
        else:
            return "N/A"

        hours = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)

        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

    def get_difference(self):
        """Get the difference (for compatibility)"""
        return self.difference if self.difference else Decimal('0.00')

    @classmethod
    def get_current_session(cls):
        """Get the currently open session (if any)"""
        return cls.objects.filter(status='open').first()

    @classmethod
    def open_for_user(cls, user, opening_balance=None):
        """
        Open a new cash session for a user.
        If opening_balance is None, uses last closing balance.
        """
        # Check if user already has an open session
        existing = cls.objects.filter(user=user, status='open').first()
        if existing:
            return existing

        # Get opening balance
        if opening_balance is None:
            # Use last closing balance from this user's previous session
            last_session = cls.objects.filter(
                user=user,
                status='closed'
            ).order_by('-closed_at').first()

            opening_balance = last_session.closing_balance if last_session else Decimal('0.00')

        # Create new session
        session = cls.objects.create(
            user=user,
            opening_balance=opening_balance
        )

        return session


class CashMovement(models.Model):
    """
    Movimiento de dinero en la caja.
    Se registra automáticamente cuando hay una venta.
    """
    MOVEMENT_TYPE_CHOICES = [
        ('sale', 'Sale'),           # Venta en efectivo
        ('in', 'Cash In'),          # Entrada de dinero (cambio, depósito)
        ('out', 'Cash Out'),        # Salida de dinero (gastos, retiro)
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        CashSession,
        on_delete=models.CASCADE,
        related_name='movements'
    )

    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPE_CHOICES)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Amount (positive for in/sale, negative for out)"
    )

    # Reference to sale (if movement is from a sale)
    sale_reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Sale number if movement is from a sale"
    )

    description = models.TextField(
        blank=True,
        help_text="Description of the movement"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'cash_register_movement'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session', 'movement_type']),
            models.Index(fields=['sale_reference']),
        ]

    def __str__(self):
        return f"{self.get_movement_type_display()} - {self.amount}"

    @classmethod
    def record_sale(cls, sale, session=None):
        """
        Record a sale as a cash movement.
        If session is None, uses the currently open session.
        """
        if session is None:
            session = CashSession.get_current_session()

        if not session:
            # No open session, can't record
            return None

        # Only record if payment was cash
        if sale.payment_method != 'cash':
            return None

        movement = cls.objects.create(
            session=session,
            movement_type='sale',
            amount=sale.total,
            sale_reference=sale.sale_number,
            description=f"Sale {sale.sale_number}"
        )

        return movement


class CashCount(models.Model):
    """
    Conteo de dinero (desglose por denominaciones).
    Se usa al abrir y cerrar sesión (opcional).
    """
    COUNT_TYPE_CHOICES = [
        ('opening', 'Opening Count'),
        ('closing', 'Closing Count'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        CashSession,
        on_delete=models.CASCADE,
        related_name='counts'
    )
    count_type = models.CharField(max_length=20, choices=COUNT_TYPE_CHOICES)

    # Count details (stored as JSON)
    # Example: {"bills": {"50": 2, "20": 5}, "coins": {"2": 10, "1": 20}}
    denominations = models.JSONField(
        default=dict,
        help_text="Cash count by denomination"
    )

    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Total counted"
    )

    notes = models.TextField(blank=True)
    counted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'cash_register_count'
        ordering = ['-counted_at']

    def __str__(self):
        return f"{self.get_count_type_display()} - {self.total}"

    def calculate_total_from_denominations(self):
        """Calculate total from denominations"""
        total = Decimal('0.00')

        # Bills
        if 'bills' in self.denominations:
            for denomination, count in self.denominations['bills'].items():
                total += Decimal(denomination) * Decimal(count)

        # Coins
        if 'coins' in self.denominations:
            for denomination, count in self.denominations['coins'].items():
                total += Decimal(denomination) * Decimal(count)

        return total

    def save(self, *args, **kwargs):
        # Auto-calculate total from denominations if not provided
        if not self.total and self.denominations:
            self.total = self.calculate_total_from_denominations()
        super().save(*args, **kwargs)

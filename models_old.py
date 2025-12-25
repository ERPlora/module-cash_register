from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid


class CashRegisterConfig(models.Model):
    """
    Configuración del plugin Cash Register (Singleton).

    NOTA: Config global (currency, etc.) se obtiene de HubConfig.
    Esta config es específica del plugin.
    """
    id = models.AutoField(primary_key=True)

    # Plugin-specific settings
    enable_cash_register = models.BooleanField(default=True, help_text="Enable/disable cash register functionality")
    require_opening_balance = models.BooleanField(default=True, help_text="Require cash count when opening session")
    require_closing_balance = models.BooleanField(default=True, help_text="Require cash count when closing session")
    allow_negative_movements = models.BooleanField(default=False, help_text="Allow cash register to have negative balance")

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


class CashRegister(models.Model):
    """
    Caja registradora física.
    Cada terminal POS tiene su propia caja.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="Name of the cash register (e.g., 'Main Counter', 'POS 1')")
    location = models.CharField(max_length=255, blank=True, help_text="Physical location")

    # Current state
    current_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Current cash balance in the register"
    )
    is_active = models.BooleanField(default=True, help_text="Is this register active?")

    # Session tracking
    has_open_session = models.BooleanField(default=False, help_text="Does this register have an open session?")
    current_session = models.OneToOneField(
        'CashSession',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='active_register'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'cash_register'
        ordering = ['name']

    def __str__(self):
        status = "Open" if self.has_open_session else "Closed"
        return f"{self.name} ({status})"

    def get_expected_balance(self):
        """Calculate expected balance based on session + movements"""
        if not self.current_session:
            return self.current_balance

        session = self.current_session
        movements_total = session.movements.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')

        return session.opening_balance + movements_total


class CashSession(models.Model):
    """
    Sesión de caja (turno de trabajo).
    Se abre al inicio del turno y se cierra al final.
    """
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cash_register = models.ForeignKey(CashRegister, on_delete=models.CASCADE, related_name='sessions')

    # Session info
    session_number = models.CharField(max_length=50, unique=True, help_text="Auto-generated session number")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')

    # Employee
    employee_name = models.CharField(max_length=255, help_text="Employee who opened the session")

    # Opening
    opened_at = models.DateTimeField(auto_now_add=True)
    opening_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
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

    def __str__(self):
        return f"Session {self.session_number} - {self.status}"

    def save(self, *args, **kwargs):
        # Auto-generate session number
        if not self.session_number:
            from django.utils import timezone
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            self.session_number = f"CS-{timestamp}"
        super().save(*args, **kwargs)

    def close_session(self, closing_balance, notes=''):
        """Close the session and calculate differences"""
        from django.utils import timezone

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

        # Update cash register
        self.cash_register.has_open_session = False
        self.cash_register.current_session = None
        self.cash_register.current_balance = closing_balance
        self.cash_register.save()

    def get_total_sales(self):
        """Get total sales (movements from sales) for this session"""
        return self.movements.filter(
            movement_type='sale'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    def get_total_in(self):
        """Get total cash in movements"""
        return self.movements.filter(
            movement_type='in'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    def get_total_out(self):
        """Get total cash out movements"""
        return self.movements.filter(
            movement_type='out'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')


class CashMovement(models.Model):
    """
    Movimiento de dinero en la caja.
    Puede ser: venta, entrada de dinero, salida de dinero.
    """
    MOVEMENT_TYPE_CHOICES = [
        ('sale', 'Sale'),
        ('in', 'Cash In'),
        ('out', 'Cash Out'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(CashSession, on_delete=models.CASCADE, related_name='movements')

    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPE_CHOICES)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Amount (positive for in/sale, can be negative for out)"
    )

    # Reference to sale (optional, if movement is from a sale)
    sale_reference = models.CharField(max_length=100, blank=True, help_text="Sale number if movement is from a sale")

    description = models.TextField(blank=True, help_text="Description of the movement")
    employee_name = models.CharField(max_length=255, help_text="Employee who made the movement")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'cash_register_movement'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_movement_type_display()} - {self.amount}"


class CashCount(models.Model):
    """
    Conteo de dinero (desglose por denominaciones).
    Se usa al abrir y cerrar sesión.
    """
    COUNT_TYPE_CHOICES = [
        ('opening', 'Opening Count'),
        ('closing', 'Closing Count'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(CashSession, on_delete=models.CASCADE, related_name='counts')
    count_type = models.CharField(max_length=20, choices=COUNT_TYPE_CHOICES)

    # Count details (stored as JSON for flexibility)
    # Example: {"bills": {"500": 2, "200": 5}, "coins": {"2": 10, "1": 20}}
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
    counted_by = models.CharField(max_length=255, help_text="Employee who counted")
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

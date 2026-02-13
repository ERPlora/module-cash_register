from django.contrib import admin
from .models import (
    CashRegisterSettings,
    CashSession,
    CashMovement,
    CashCount
)


@admin.register(CashRegisterSettings)
class CashRegisterSettingsAdmin(admin.ModelAdmin):
    list_display = [
        'enable_cash_register',
        'require_opening_balance',
        'require_closing_balance',
        'allow_negative_balance',
        'auto_open_session_on_login',
        'auto_close_session_on_logout'
    ]
    fieldsets = (
        ('Settings', {
            'fields': (
                'enable_cash_register',
                'require_opening_balance',
                'require_closing_balance',
                'allow_negative_balance',
                'auto_open_session_on_login',
                'auto_close_session_on_logout'
            )
        }),
    )

    def has_add_permission(self, request):
        # Singleton: only allow one instance
        return not CashRegisterSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of singleton
        return False


class CashMovementInline(admin.TabularInline):
    model = CashMovement
    extra = 0
    readonly_fields = ['id', 'created_at']
    fields = ['movement_type', 'amount', 'description', 'sale_reference', 'created_at']


class CashCountInline(admin.TabularInline):
    model = CashCount
    extra = 0
    readonly_fields = ['id', 'counted_at']
    fields = ['count_type', 'total', 'denominations', 'notes', 'counted_at']


@admin.register(CashSession)
class CashSessionAdmin(admin.ModelAdmin):
    list_display = [
        'session_number',
        'user',
        'status',
        'opening_balance',
        'closing_balance',
        'difference',
        'opened_at',
        'closed_at'
    ]
    list_filter = ['status', 'opened_at', 'closed_at']
    search_fields = ['session_number', 'user__name', 'user__email']
    readonly_fields = [
        'id',
        'session_number',
        'expected_balance',
        'difference',
        'created_at',
        'updated_at'
    ]
    inlines = [CashMovementInline, CashCountInline]

    fieldsets = (
        ('Session Information', {
            'fields': ('id', 'session_number', 'user', 'status')
        }),
        ('Opening', {
            'fields': ('opened_at', 'opening_balance', 'opening_notes')
        }),
        ('Closing', {
            'fields': ('closed_at', 'closing_balance', 'expected_balance', 'difference', 'closing_notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        # If session is closed, make everything readonly
        if obj and obj.status == 'closed':
            return [f.name for f in self.model._meta.fields]
        return self.readonly_fields


@admin.register(CashMovement)
class CashMovementAdmin(admin.ModelAdmin):
    list_display = [
        'session',
        'movement_type',
        'amount',
        'sale_reference',
        'created_at'
    ]
    list_filter = ['movement_type', 'created_at']
    search_fields = ['description', 'sale_reference']
    readonly_fields = ['id', 'created_at']

    fieldsets = (
        ('Movement Information', {
            'fields': ('id', 'session', 'movement_type', 'amount')
        }),
        ('Details', {
            'fields': ('description', 'sale_reference')
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )


@admin.register(CashCount)
class CashCountAdmin(admin.ModelAdmin):
    list_display = [
        'session',
        'count_type',
        'total',
        'counted_at'
    ]
    list_filter = ['count_type', 'counted_at']
    search_fields = ['notes']
    readonly_fields = ['id', 'counted_at']

    fieldsets = (
        ('Count Information', {
            'fields': ('id', 'session', 'count_type', 'total')
        }),
        ('Details', {
            'fields': ('denominations', 'notes')
        }),
        ('Timestamp', {
            'fields': ('counted_at',)
        }),
    )

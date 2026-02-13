from django import forms
from django.utils.translation import gettext_lazy as _

from .models import CashRegister, CashRegisterSettings


class CashRegisterForm(forms.ModelForm):
    class Meta:
        model = CashRegister
        fields = ['name', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': _('Register name'),
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'toggle',
            }),
        }


class CashRegisterSettingsForm(forms.ModelForm):
    class Meta:
        model = CashRegisterSettings
        fields = [
            'enable_cash_register', 'require_opening_balance',
            'require_closing_balance', 'allow_negative_balance',
            'auto_open_session_on_login', 'auto_close_session_on_logout',
            'protected_pos_url',
        ]
        widgets = {
            'enable_cash_register': forms.CheckboxInput(attrs={'class': 'toggle'}),
            'require_opening_balance': forms.CheckboxInput(attrs={'class': 'toggle'}),
            'require_closing_balance': forms.CheckboxInput(attrs={'class': 'toggle'}),
            'allow_negative_balance': forms.CheckboxInput(attrs={'class': 'toggle'}),
            'auto_open_session_on_login': forms.CheckboxInput(attrs={'class': 'toggle'}),
            'auto_close_session_on_logout': forms.CheckboxInput(attrs={'class': 'toggle'}),
            'protected_pos_url': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': '/m/sales/pos/',
            }),
        }


class OpenSessionForm(forms.Form):
    opening_balance = forms.DecimalField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'input',
            'step': '0.01',
            'min': '0',
            'placeholder': '0.00',
        }),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'textarea',
            'rows': 2,
            'placeholder': _('Opening notes (optional)'),
        }),
    )


class CloseSessionForm(forms.Form):
    closing_balance = forms.DecimalField(
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'input',
            'step': '0.01',
            'min': '0',
            'placeholder': '0.00',
        }),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'textarea',
            'rows': 2,
            'placeholder': _('Closing notes (optional)'),
        }),
    )


class CashMovementForm(forms.Form):
    MOVEMENT_TYPES = [
        ('in', _('Cash In')),
        ('out', _('Cash Out')),
    ]

    movement_type = forms.ChoiceField(
        choices=MOVEMENT_TYPES,
        widget=forms.RadioSelect(attrs={'class': 'radio'}),
    )
    amount = forms.DecimalField(
        min_value=0.01,
        widget=forms.NumberInput(attrs={
            'class': 'input',
            'step': '0.01',
            'min': '0.01',
            'placeholder': '0.00',
        }),
    )
    description = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'input',
            'placeholder': _('Description'),
        }),
    )

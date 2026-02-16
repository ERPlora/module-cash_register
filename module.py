from django.utils.translation import gettext_lazy as _

MODULE_ID = 'cash_register'
MODULE_NAME = _('Cash Register')
MODULE_VERSION = '1.0.0'

MENU = {
    'label': _('Cash Register'),
    'icon': 'cash-outline',
    'order': 6,
}

NAVIGATION = [
    {'id': 'dashboard', 'label': _('Dashboard'), 'icon': 'speedometer-outline', 'view': ''},
    {'id': 'history', 'label': _('History'), 'icon': 'time-outline', 'view': 'history'},
    {'id': 'settings', 'label': _('Settings'), 'icon': 'settings-outline', 'view': 'settings'},
]

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CashRegisterAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cash_register'
    label = 'cash_register'
    verbose_name = _('Cash Register')

    def ready(self):
        pass

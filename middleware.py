from urllib.parse import urlencode

from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin


class CashRegisterMiddleware(MiddlewareMixin):
    """
    Middleware that requires users to open a cash session before accessing the POS.

    Flow:
    1. User logs in → auto-opens session if enabled
    2. User tries to access the protected POS URL
    3. Middleware detects no open cash session
    4. User is redirected to /m/cash_register/open/?next=/m/sales/pos/
    5. User opens a cash session with opening balance
    6. User is redirected back to POS
    """

    EXEMPT_URLS = [
        '/accounts/login/',
        '/accounts/logout/',
        '/m/cash_register/open/',
        '/m/cash_register/close/',
        '/m/cash_register/api/',
        '/static/',
        '/media/',
    ]

    def process_request(self, request):
        hub_id = request.session.get('hub_id')
        if not hub_id:
            return None

        local_user_id = request.session.get('local_user_id')
        if not local_user_id:
            return None

        path = request.path
        if any(path.startswith(url) for url in self.EXEMPT_URLS):
            return None

        try:
            from .models import CashRegisterSettings
            config = CashRegisterSettings.get_settings(hub_id)

            if not config.enable_cash_register:
                return None

            protected_url = config.protected_pos_url or '/m/sales/pos/'
        except Exception:
            return None

        if not path.startswith(protected_url):
            return None

        try:
            from apps.accounts.models import LocalUser
            user = LocalUser.objects.get(pk=local_user_id)

            from .models import CashSession
            open_session = CashSession.get_current_session(hub_id, user)

            if not open_session:
                # Auto-open if configured
                if config.auto_open_session_on_login:
                    open_session = CashSession.open_for_user(
                        hub_id=hub_id, user=user,
                    )
                    request.cash_session = open_session
                    return None

                # Manual open: redirect with next param so user returns to POS
                open_url = '/m/cash_register/open/?' + urlencode({'next': path})
                return redirect(open_url)

            request.cash_session = open_session

        except Exception:
            return None

        return None

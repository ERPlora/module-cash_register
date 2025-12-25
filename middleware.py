from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
from apps.accounts.models import LocalUser


class CashRegisterMiddleware(MiddlewareMixin):
    """
    Middleware que fuerza a los usuarios a abrir una sesión de caja antes de acceder al POS.

    Flujo:
    1. Usuario hace login → Puede acceder al dashboard, historial, etc.
    2. Usuario intenta acceder a /plugins/sales/pos/
    3. Middleware detecta que no tiene sesión abierta
    4. Usuario es redirigido a /plugins/cash_register/open/
    5. Usuario abre sesión de caja con balance inicial
    6. Usuario puede usar el POS normalmente
    7. Al hacer logout → Usuario es redirigido a /plugins/cash_register/close/
    8. Usuario cierra sesión con conteo final
    """

    # URLs siempre accesibles (para evitar loops de redirección)
    EXEMPT_URLS = [
        '/accounts/login/',
        '/accounts/logout/',
        '/plugins/cash_register/open/',
        '/plugins/cash_register/close/',
        '/plugins/cash_register/api/',
        '/static/',
        '/media/',
    ]

    def process_request(self, request):
        # 1. Skip si el usuario no está autenticado
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return None

        # 2. Skip URLs siempre accesibles
        path = request.path
        if any(path.startswith(url) for url in self.EXEMPT_URLS):
            return None

        # 3. Obtener URL protegida desde configuración
        try:
            from .models import CashRegisterConfig
            config = CashRegisterConfig.objects.first()
            protected_url = config.protected_pos_url if config and config.protected_pos_url else '/plugins/sales/pos/'
        except:
            protected_url = '/plugins/sales/pos/'

        # 4. Solo verificar sesión de caja para URL protegida
        if not path.startswith(protected_url):
            return None

        # 5. Skip si el plugin cash_register no está activo
        if not self._is_plugin_active():
            return None

        # 6. Verificar si el usuario es LocalUser con sesión de caja
        try:
            local_user = request.user
            if not isinstance(local_user, LocalUser):
                return None

            # 7. Verificar si hay una sesión de caja abierta
            from .models import CashSession

            open_session = CashSession.objects.filter(
                user=local_user,
                status='open'
            ).first()

            # 8. Si NO hay sesión abierta → Redirigir a abrir sesión
            if not open_session:
                return redirect('cash_register:open_session')

            # 9. Guardar sesión actual en request para uso en views
            request.cash_session = open_session

        except Exception as e:
            # En caso de error (ej: tabla no existe aún), permitir acceso
            print(f"[CASH REGISTER MIDDLEWARE] Error: {e}")
            return None

        # Todo OK, permitir acceso
        return None

    def _is_plugin_active(self):
        """Verificar si el plugin cash_register está activo"""
        try:
            from apps.plugins_admin.models import Plugin
            plugin = Plugin.objects.filter(
                plugin_id='cash_register',
                is_active=True
            ).first()
            return plugin is not None
        except:
            # Si no existe la tabla plugins, asumir que está activo
            return True

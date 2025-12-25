# Cash Register Plugin

Plugin para gestión de caja registradora con sesiones por usuario, movimientos y conteo de dinero.

## Características

- ✅ **Sesiones de caja por usuario**: Cada empleado tiene su propia sesión de caja
- ✅ **Apertura y cierre de turnos**: Con conteo de dinero opcional
- ✅ **Movimientos de efectivo**: Registro de entradas/salidas de dinero
- ✅ **Integración con ventas**: Registro automático de ventas en caja
- ✅ **Conteo de denominaciones**: Calculadora de billetes y monedas
- ✅ **Diferencias**: Cálculo automático de diferencias al cierre
- ✅ **Middleware de protección**: URLs que requieren sesión abierta
- ✅ **Configuración flexible**: Via HTMX con auto-save
- ✅ **Historial de sesiones**: Por usuario con filtros

## Modelos

### CashRegisterConfig (Singleton)
Configuración global del plugin.

**Campos:**
- `enable_cash_register`: Activar/desactivar funcionalidad (bool)
- `require_opening_balance`: Requerir conteo al abrir sesión (bool)
- `require_closing_balance`: Requerir conteo al cerrar sesión (bool)
- `allow_negative_movements`: Permitir balance negativo (bool)
- `protected_pos_url`: URL que requiere sesión abierta (str, default: `/plugins/sales/pos/`)

**Métodos:**
- `get_config()`: Obtiene la instancia singleton (con caché)
- `CashRegisterConfig.objects.get_solo()`: Alias de get_config()

### CashSession
Sesión de caja por usuario.

**Campos principales:**
- `user`: Usuario (LocalUser) que abrió la sesión
- `session_number`: Número de sesión (auto-generado: CSH-YYYYMMDD-XXXX)
- `status`: 'open' o 'closed'
- `opening_balance`: Balance al abrir (Decimal)
- `closing_balance`: Balance al cerrar (Decimal)
- `expected_balance`: Balance esperado según movimientos (Decimal)
- `difference`: Diferencia entre esperado y real (Decimal)
- `opened_at`: Timestamp de apertura
- `closed_at`: Timestamp de cierre
- `opening_notes`: Notas al abrir
- `closing_notes`: Notas al cerrar

**Métodos de clase:**
- `open_for_user(user, opening_balance)`: Crea nueva sesión para usuario
- `get_user_open_session(user)`: Obtiene sesión abierta del usuario

**Métodos de instancia:**
- `close_session(closing_balance, notes)`: Cierra sesión y calcula diferencias
- `get_current_balance()`: Balance actual (apertura + movimientos)
- `get_total_sales()`: Total de ventas en la sesión
- `get_total_in()`: Total de entradas de efectivo
- `get_total_out()`: Total de salidas de efectivo

### CashMovement
Movimiento de dinero en la caja.

**Tipos de movimiento:**
- `sale`: Venta (positivo)
- `in`: Entrada de efectivo (positivo)
- `out`: Salida de efectivo (negativo)

**Campos:**
- `movement_type`: Tipo de movimiento
- `amount`: Cantidad (positivo/negativo según tipo)
- `description`: Descripción del movimiento
- `sale_reference`: Referencia a venta (opcional)
- `employee_name`: Empleado que realizó el movimiento

### CashCount
Conteo de dinero por denominaciones.

**Tipos:**
- `opening`: Conteo al abrir sesión
- `closing`: Conteo al cerrar sesión

**Campos:**
- `count_type`: Tipo de conteo
- `denominations`: JSON con desglose por billetes/monedas
- `total`: Total contado
- `counted_by`: Empleado que contó

**Ejemplo de denominations:**
```json
{
  "bill_500": 2,    // 2 billetes de 500
  "bill_200": 5,    // 5 billetes de 200
  "bill_100": 10,   // 10 billetes de 100
  "coin_2": 10,     // 10 monedas de 2
  "coin_1": 20,     // 20 monedas de 1
  "coin_0.5": 15    // 15 monedas de 0.5
}
```

## Vistas Principales

### Dashboard (`/plugins/cash_register/`)
- Muestra sesión abierta del usuario actual
- Botones para abrir/cerrar sesión
- Estadísticas de sesiones de hoy
- Historial de últimas 10 sesiones

### Open Session (`/plugins/cash_register/open/`)
- Formulario de apertura de sesión
- Calculadora de denominaciones (Alpine.js)
- Balance sugerido (último cierre)
- Notas opcionales

### Close Session (`/plugins/cash_register/close/`)
- Resumen de la sesión (ventas, entradas, salidas)
- Balance esperado vs real
- Calculadora de denominaciones
- Indicador de diferencias (Exact/Surplus/Shortage)
- Confirmación si diferencia > 10

### Session Detail (`/plugins/cash_register/session/<id>/`)
- Detalles de la sesión
- Lista de movimientos agrupados por tipo
- Conteos de apertura y cierre

### Settings (`/plugins/cash_register/settings/`)
- Configuración del plugin (HTMX con auto-save)
- Toggles para opciones principales
- URL protegida configurable
- Muestra config global (moneda, negocio)

### History (`/plugins/cash_register/history/`)
- Historial de sesiones del usuario
- Filtros por estado y fecha
- Paginación

## API Endpoints (JSON)

### POST `/plugins/cash_register/api/session/open/`
Abre nueva sesión para el usuario actual.

**Body:**
```json
{
  "opening_balance": 100.00,
  "notes": "Opening notes",
  "denominations": {"bill_500": 2, "coin_1": 10}
}
```

**Response:**
```json
{
  "success": true,
  "session": {
    "id": "uuid",
    "session_number": "CSH-20250124-0001",
    "opening_balance": 100.00
  }
}
```

### POST `/plugins/cash_register/api/session/close/`
Cierra la sesión abierta del usuario.

**Body:**
```json
{
  "closing_balance": 150.00,
  "notes": "All good",
  "denominations": {...}
}
```

### POST `/plugins/cash_register/api/movement/add/`
Añade un movimiento a la sesión abierta.

**Body:**
```json
{
  "movement_type": "in|out|sale",
  "amount": 50.00,
  "description": "Cash deposit",
  "sale_reference": "SALE-123"
}
```

### GET `/plugins/cash_register/api/session/current/`
Obtiene la sesión abierta del usuario actual.

### GET `/plugins/cash_register/api/session/<id>/movements/`
Lista movimientos de una sesión.

## Middleware de Protección de URLs

El plugin incluye middleware para proteger URLs que requieren sesión abierta.

### CashSessionRequiredMiddleware

Intercepta requests a URLs configuradas y verifica que el usuario tenga sesión abierta.

**Configuración:**
```python
# settings.py
MIDDLEWARE = [
    # ... otros middlewares
    'cash_register.middleware.CashSessionRequiredMiddleware',
]
```

**Funcionamiento:**
1. Lee `CashRegisterConfig.protected_pos_url` (default: `/plugins/sales/pos/`)
2. Si user accede a esa URL sin sesión abierta → redirect a `/plugins/cash_register/open/`
3. Excluye URLs del propio plugin (`/plugins/cash_register/*`)
4. Solo actúa si `enable_cash_register = True`

**Ejemplo de uso:**
```python
# En Settings del plugin
protected_pos_url = "/plugins/sales/pos/"

# Usuario sin sesión abierta intenta acceder a /plugins/sales/pos/
# → Redirect automático a /plugins/cash_register/open/?next=/plugins/sales/pos/
```

## Integración con Sales Plugin

Para registrar ventas en caja automáticamente:

```python
# Después de completar una venta
try:
    from cash_register.models import CashMovement, CashSession

    # Obtener sesión abierta del usuario
    session = CashSession.get_user_open_session(request.user)

    if session:
        CashMovement.objects.create(
            session=session,
            movement_type='sale',
            amount=sale.total,
            sale_reference=sale.sale_number,
            description=f"Sale {sale.sale_number}"
        )
except ImportError:
    # Plugin cash_register no instalado, ignorar
    pass
```

## Configuración

El plugin tiene configuración flexible via HTMX con auto-save.

### Opciones Disponibles

1. **Enable Cash Register**: Activar/desactivar funcionalidad (bool)
2. **Require Opening Balance**: Requerir conteo al abrir sesión (bool)
3. **Require Closing Balance**: Requerir conteo al cerrar sesión (bool)
4. **Allow Negative Balance**: Permitir balance negativo (bool)
5. **Protected POS URL**: URL que requiere sesión abierta (str, default: `/plugins/sales/pos/`)

### Características de Settings Page

- ✅ **Auto-save con HTMX**: Los toggles se guardan automáticamente 500ms después del cambio
- ✅ **Sin Alpine.js state management**: Usa HTMX puro para máxima simplicidad
- ✅ **Botón icon-only**: Para guardar URL protegida
- ✅ **Muestra config global**: Moneda y nombre del negocio (solo lectura)
- ✅ **Feedback visual**: Mensaje de éxito que desaparece automáticamente

## Uso

### 1. Abrir Sesión

1. Usuario hace login en el Hub
2. Si no tiene sesión abierta y accede a URL protegida → redirect automático
3. En página de apertura:
   - Balance sugerido = último cierre del usuario
   - Opcional: usar calculadora de denominaciones
   - Añadir notas opcionales
4. Click "Open Session" → redirect a página original

### 2. Trabajar con Sesión Abierta

- Todas las ventas se registran automáticamente como movimientos
- Usuario puede añadir entradas/salidas de efectivo manualmente
- Dashboard muestra balance actual y estadísticas

### 3. Cerrar Sesión

1. Click en "Close Session"
2. Ver resumen de la sesión (ventas, entradas, salidas)
3. Balance esperado calculado automáticamente
4. Ingresar balance real:
   - Manual: escribir cantidad
   - O usar calculadora de denominaciones
5. Sistema muestra diferencia en tiempo real:
   - Verde (Exact): Diferencia = 0
   - Amarillo (Surplus): Diferencia > 0
   - Rojo (Shortage): Diferencia < 0
6. Si diferencia > 10 → confirmación requerida
7. Click "Close Session" → redirect a detalle de sesión

## Estructura de Archivos

```
cash_register/
├── plugin.json              # Metadata del plugin
├── models.py               # Modelos: CashRegisterConfig, CashSession, CashMovement, CashCount
├── views.py                # Vistas y API endpoints
├── urls.py                 # URLs del plugin
├── admin.py                # Admin de Django
├── middleware.py           # CashSessionRequiredMiddleware
├── templates/
│   └── cash_register/
│       ├── index.html              # Dashboard (Alpine.js)
│       ├── open_session.html       # Apertura (Alpine.js + calculadora)
│       ├── close_session.html      # Cierre (Alpine.js + calculadora)
│       ├── session_detail.html     # Detalle de sesión
│       ├── history.html            # Historial
│       └── settings.html           # Configuración (HTMX puro)
├── migrations/
└── README.md
```

## Stack Tecnológico

### Backend
- Django 5.1+
- Solo-models para singleton config
- DecimalField para precisión monetaria

### Frontend
- **Settings page**: HTMX puro con auto-save (0 líneas de Alpine.js)
- **Open/Close session**: Alpine.js para calculadora interactiva de denominaciones
- **Dashboard**: Alpine.js para UI reactiva
- Ionic Framework 8 (Web Components)
- Tailwind CSS para estilos utility

### Por qué diferentes enfoques:

**Settings usa HTMX:**
- Toggles simples que se guardan automáticamente
- Sin cálculos complejos ni interactividad avanzada
- HTMX perfecto para auto-save declarativo
- Reducción de código: ~280 líneas JS → ~10 líneas

**Open/Close usan Alpine.js:**
- Calculadora de denominaciones altamente interactiva
- Cálculos en tiempo real (total, diferencias)
- Toggle de mostrar/ocultar calculadora
- Confirmaciones y validaciones complejas
- Sería contraproducente forzar HTMX aquí

## Configuración Global

El plugin usa configuración global del Hub:

- **Currency** (`HUB_CONFIG.currency`): Moneda para mostrar importes
- **Business Name** (`STORE_CONFIG.business_name`): Nombre del negocio

Ver [`hub/apps/configuration/README.md`](../../apps/configuration/README.md) para más detalles.

## Permisos

El plugin define los siguientes permisos:

- `cash_register.view_cashsession`
- `cash_register.open_cashsession`
- `cash_register.close_cashsession`
- `cash_register.add_cashmovement`
- `cash_register.view_cashmovement`

## Cambios Recientes (2025-01-24)

### ✅ Settings Page convertida a HTMX
- Eliminado Alpine.js state management completamente
- Auto-save con `hx-trigger="change delay:500ms"`
- Botón icon-only para guardar URL protegida
- Feedback visual con auto-hide
- Reducción de ~280 líneas de JS a ~10 líneas

### ✅ Fix de bloques de scripts
- Cambiado `{% block scripts %}` → `{% block extra_scripts %}` en:
  - `open_session.html`
  - `close_session.html`
- Resuelto error `closingBalance is not defined`

### ✅ Documentación actualizada
- README completo con arquitectura actual
- Explicación de decisiones HTMX vs Alpine.js
- Ejemplos de integración con Sales plugin
- Middleware de protección documentado

## TODO Futuro

- [ ] Reportes de caja por período (gráficos con Chart.js)
- [ ] Export a Excel/PDF usando HTMX
- [ ] Alertas de diferencias grandes (WebSocket?)
- [ ] Múltiples turnos por día
- [ ] Integración con impresora fiscal (python-escpos)
- [ ] Dashboard en tiempo real (HTMX polling)
- [ ] Reconciliación bancaria

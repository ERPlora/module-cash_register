#!/usr/bin/env python3
"""
Script to automatically translate cash_register plugin strings to Spanish
"""

translations = {
    # Session actions
    "Close Cash Session": "Cerrar Sesión de Caja",
    "Open Cash Session": "Abrir Sesión de Caja",
    "Open Session": "Abrir Sesión",
    "Close Session": "Cerrar Sesión",
    "Closing...": "Cerrando...",

    # Session information
    "Opened At": "Abierto",
    "Opened": "Abierto",
    "Closed At": "Cerrado",
    "Duration": "Duración",
    "Session": "Sesión",
    "Session Number": "Número de Sesión",
    "Session History": "Historial de Sesiones",

    # Balance and money
    "Opening Balance": "Balance de Apertura",
    "Actual Closing Balance": "Balance de Cierre Real",
    "Expected Balance": "Balance Esperado",
    "Closing Balance": "Balance de Cierre",
    "Current Balance": "Balance Actual",
    "Difference": "Diferencia",
    "Opening": "Apertura",
    "Closing": "Cierre",

    # Money movements
    "Total Sales": "Total de Ventas",
    "Cash In": "Entradas de Efectivo",
    "Cash Out": "Salidas de Efectivo",
    "Total Cash In": "Total Entradas",
    "Total Cash Out": "Total Salidas",

    # Status indicators
    "Exact!": "¡Exacto!",
    "Surplus": "Excedente",
    "Shortage": "Faltante",
    "Status": "Estado",
    "All": "Todos",
    "Open": "Abierto",
    "Closed": "Cerrado",

    # Calculator
    "Hide Calculator": "Ocultar Calculadora",
    "Count Denominations": "Contar Denominaciones",
    "Cash Count": "Conteo de Efectivo",
    "Coins": "Monedas",
    "Bills": "Billetes",
    "Calculated Total": "Total Calculado",
    "Use This Amount": "Usar Esta Cantidad",

    # Notes and comments
    "Closing Notes (Optional)": "Notas de Cierre (Opcional)",
    "Opening Notes (Optional)": "Notas de Apertura (Opcional)",
    "Notes (Optional)": "Notas (Opcional)",
    "Any discrepancies or notes...": "Cualquier discrepancia o nota...",
    "Any additional notes...": "Cualquier nota adicional...",

    # Actions
    "Actions": "Acciones",
    "Cancel": "Cancelar",
    "Confirm": "Confirmar",
    "Filter": "Filtrar",
    "Clear": "Limpiar",
    "View Details": "Ver Detalles",

    # Filters and dates
    "From Date": "Desde Fecha",
    "To Date": "Hasta Fecha",

    # Messages
    "Closing balance is required": "El balance de cierre es obligatorio",
    "Large Discrepancy": "Diferencia Grande",
    "There is a difference of": "Hay una diferencia de",
    "Are you sure you want to close the session?": "¿Estás seguro de que deseas cerrar la sesión?",
    "No sessions found": "No se encontraron sesiones",
    "Try adjusting your filters or open a new session": "Intenta ajustar tus filtros o abre una nueva sesión",

    # Plugin info
    "Cash Register": "Caja Registradora",
    "Cash session and movement management": "Gestión de sesiones de caja y movimientos",

    # Settings
    "Settings": "Configuración",
    "Cash Register Settings": "Configuración de Caja Registradora",
    "Enable Cash Register": "Activar Caja Registradora",
    "Require Opening Balance": "Requerir Balance de Apertura",
    "Require Closing Balance": "Requerir Balance de Cierre",
    "Allow Negative Balance": "Permitir Balance Negativo",
    "Protected POS URL": "URL del POS Protegida",
    "Activate cash register functionality": "Activar funcionalidad de caja registradora",
    "Require balance count when opening session": "Requerir conteo de balance al abrir sesión",
    "Require balance count when closing session": "Requerir conteo de balance al cerrar sesión",
    "Allow negative cash balance": "Permitir balance de efectivo negativo",
    "URL that requires open cash session": "URL que requiere sesión de caja abierta",
    "URL that requires open cash session (default: /plugins/sales/pos/)": "URL que requiere sesión de caja abierta (por defecto: /plugins/sales/pos/)",

    # Dashboard
    "Dashboard": "Panel de Control",
    "Open New Session": "Abrir Nueva Sesión",
    "Your Cash Session": "Tu Sesión de Caja",
    "No active session": "Sin sesión activa",
    "Start a new cash session to begin operations": "Inicia una nueva sesión de caja para comenzar operaciones",
    "Recent Sessions": "Sesiones Recientes",
    "View All": "Ver Todo",
    "Today's Sessions": "Sesiones de Hoy",

    # Session details
    "Session Details": "Detalles de Sesión",
    "Cash Movements": "Movimientos de Efectivo",
    "Type": "Tipo",
    "Amount": "Cantidad",
    "Description": "Descripción",
    "Timestamp": "Marca de Tiempo",
    "Sale": "Venta",
    "Cash In Movement": "Entrada de Efectivo",
    "Cash Out Movement": "Salida de Efectivo",
    "No movements recorded": "No hay movimientos registrados",
    "Opening Count": "Conteo de Apertura",
    "Closing Count": "Conteo de Cierre",
    "Counted by": "Contado por",
    "No count recorded": "No hay conteo registrado",
}

def update_po_file(po_file):
    """Update .po file with Spanish translations"""
    import re

    with open(po_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Update header
    content = content.replace('#, fuzzy', '')
    content = content.replace('YEAR-MO-DA HO:MI+ZONE', '2025-11-24 12:00+0000')
    content = content.replace('FULL NAME <EMAIL@ADDRESS>', 'CPOS Team <info@erplora.com>')
    content = content.replace('Language: \\n', 'Language: es\\n')

    # Update translations
    for english, spanish in translations.items():
        # Escape special characters for regex
        english_escaped = re.escape(english)
        # Find msgid and empty msgstr pattern
        pattern = f'msgid "{english_escaped}"\\nmsgstr ""'
        replacement = f'msgid "{english}"\\nmsgstr "{spanish}"'
        content = re.sub(pattern, replacement, content)

    with open(po_file, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✅ Updated {po_file}")
    print(f"✅ Translated {len(translations)} strings")

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        update_po_file(sys.argv[1])
    else:
        update_po_file('es/LC_MESSAGES/django.po')

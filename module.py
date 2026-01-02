"""
Cash Register Module Configuration

This file defines the module metadata and navigation for the Cash Register module.
Used by the @module_view decorator to automatically render navigation tabs.
"""
from django.utils.translation import gettext_lazy as _

# Module Identification
MODULE_ID = "cash_register"
MODULE_NAME = _("Cash Register")
MODULE_ICON = "cash-outline"
MODULE_VERSION = "1.0.0"
MODULE_CATEGORY = "pos"

# Target Industries (business verticals this module is designed for)
MODULE_INDUSTRIES = [
    "retail",     # Retail stores
    "restaurant", # Restaurants
    "bar",        # Bars & pubs
    "cafe",       # Cafes & bakeries
    "fast_food",  # Fast food
    "salon",      # Beauty & wellness
]

# Sidebar Menu Configuration
MENU = {
    "label": _("Cash Register"),
    "icon": "cash-outline",
    "order": 15,
    "show": True,
}

# Internal Navigation (Tabs)
NAVIGATION = [
    {
        "id": "dashboard",
        "label": _("Overview"),
        "icon": "home-outline",
        "view": "",
    },
    {
        "id": "history",
        "label": _("History"),
        "icon": "time-outline",
        "view": "history",
    },
    {
        "id": "settings",
        "label": _("Settings"),
        "icon": "settings-outline",
        "view": "settings",
    },
]

# Module Dependencies
DEPENDENCIES = []

# Default Settings
SETTINGS = {
    "enable_cash_register": True,
    "require_opening_balance": True,
    "require_closing_balance": True,
    "allow_negative_movements": False,
}

# Permissions
PERMISSIONS = [
    "cash_register.view_cashsession",
    "cash_register.open_cashsession",
    "cash_register.close_cashsession",
    "cash_register.add_cashmovement",
    "cash_register.view_cashmovement",
]

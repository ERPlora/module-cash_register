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
    "beauty",     # Beauty & wellness
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
# Format: (action_suffix, display_name) -> becomes "cash_register.action_suffix"
PERMISSIONS = [
    ("view_cashsession", _("Can view cash sessions")),
    ("open_cashsession", _("Can open cash sessions")),
    ("close_cashsession", _("Can close cash sessions")),
    ("add_cashmovement", _("Can add cash movements")),
    ("view_cashmovement", _("Can view cash movements")),
    ("delete_cashmovement", _("Can delete cash movements")),
    ("view_reports", _("Can view cash reports")),
]

# Role Permissions - Default permissions for each system role in this module
# Keys are role names, values are lists of permission suffixes (without module prefix)
# Use ["*"] to grant all permissions in this module
ROLE_PERMISSIONS = {
    "admin": ["*"],  # Full access to all cash register permissions
    "manager": [
        "view_cashsession",
        "open_cashsession",
        "close_cashsession",
        "add_cashmovement",
        "view_cashmovement",
        "delete_cashmovement",
        "view_reports",
    ],
    "employee": [
        "view_cashsession",
        "open_cashsession",
        "add_cashmovement",
        "view_cashmovement",
    ],
}

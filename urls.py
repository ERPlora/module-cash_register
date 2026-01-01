from django.urls import path
from . import views

app_name = 'cash_register'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Session management
    path('open/', views.open_session, name='open_session'),
    path('close/', views.close_session, name='close_session'),
    path('session/<uuid:session_id>/', views.session_detail, name='session_detail'),

    # History & Settings
    path('history/', views.history, name='history'),
    path('settings/', views.settings_view, name='settings'),
    path('settings/save/', views.settings_save, name='settings_save'),
    path('settings/toggle/', views.settings_toggle, name='settings_toggle'),
    path('settings/reset/', views.settings_reset, name='settings_reset'),

    # API Endpoints
    path('api/session/open/', views.api_open_session, name='api_open_session'),
    path('api/session/close/', views.api_close_session, name='api_close_session'),
    path('api/session/current/', views.api_current_session, name='api_current_session'),
    path('api/session/<uuid:session_id>/movements/', views.api_session_movements, name='api_session_movements'),
    path('api/movement/add/', views.api_add_movement, name='api_add_movement'),

    # HTMX Endpoints
    path('htmx/calculate-denominations/', views.htmx_calculate_denominations, name='htmx_calculate_denominations'),
    path('htmx/calculate-difference/', views.htmx_calculate_difference, name='htmx_calculate_difference'),
]

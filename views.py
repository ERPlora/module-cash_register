from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Sum, Count
from decimal import Decimal, InvalidOperation
import json

from apps.accounts.decorators import login_required
from apps.configuration.models import HubConfig, StoreConfig
from apps.core.htmx import htmx_view
from .models import (
    CashRegisterConfig,
    CashSession,
    CashMovement,
    CashCount
)


@login_required
@htmx_view('cash_register/pages/index.html', 'cash_register/partials/dashboard_content.html')
def dashboard(request):
    """
    Main dashboard for cash register.
    Shows current user session and stats.
    Supports HTMX for SPA navigation.
    """
    from django.urls import reverse
    from apps.core.services.currency_service import format_currency

    config = CashRegisterConfig.get_config()

    # Get user's current open session
    open_session = CashSession.objects.filter(
        user=request.user,
        status='open'
    ).first()

    # Get today's closed sessions for this user
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_sessions_qs = CashSession.objects.filter(
        user=request.user,
        status='closed',
        closed_at__gte=today_start
    )

    # Add formatted values to today's sessions
    today_sessions = []
    for session in today_sessions_qs:
        session.closing_balance_formatted = format_currency(session.closing_balance or Decimal('0'))
        diff = session.get_difference() if hasattr(session, 'get_difference') else Decimal('0')
        session.difference = diff
        session.difference_formatted = format_currency(abs(diff))
        today_sessions.append(session)

    # Recent sessions (last 10)
    recent_sessions = CashSession.objects.filter(
        user=request.user
    ).order_by('-opened_at')[:10]

    # Build context with formatted values
    context = {
        'config': config,
        'open_session': open_session,
        'today_sessions': today_sessions,
        'recent_sessions': recent_sessions,
        'open_session_url': reverse('cash_register:open_session'),
    }

    # Add formatted values for open session
    if open_session:
        context['current_balance_formatted'] = format_currency(open_session.get_current_balance())
        context['total_sales_formatted'] = format_currency(open_session.get_total_sales())
        context['opening_balance_formatted'] = format_currency(open_session.opening_balance)
        context['total_in_formatted'] = format_currency(open_session.get_total_in())
        context['total_out_formatted'] = format_currency(open_session.get_total_out())

    return context


@login_required
def open_session(request):
    """
    View to open a cash session.
    Called by middleware when user has no open session.
    """
    config = CashRegisterConfig.get_config()
    hub_config = HubConfig.get_config()
    store_config = StoreConfig.get_config()

    # Check if user already has an open session
    existing_session = CashSession.objects.filter(
        user=request.user,
        status='open'
    ).first()

    if existing_session:
        # User already has an open session, redirect to dashboard
        return redirect('cash_register:dashboard')

    # Get suggested opening balance (last closing balance)
    last_session = CashSession.objects.filter(
        user=request.user,
        status='closed'
    ).order_by('-closed_at').first()

    suggested_balance = last_session.closing_balance if last_session else Decimal('0.00')

    if request.method == 'POST':
        # Handle session opening
        opening_balance_str = request.POST.get('opening_balance', '0').strip()
        if not opening_balance_str or opening_balance_str == '':
            opening_balance_str = '0'

        try:
            opening_balance = Decimal(opening_balance_str)
        except (ValueError, InvalidOperation):
            opening_balance = Decimal('0.00')

        notes = request.POST.get('notes', '')

        # Create new session
        session = CashSession.open_for_user(
            user=request.user,
            opening_balance=opening_balance
        )
        session.opening_notes = notes
        session.save()

        # Create opening count if denominations provided
        denominations_json = request.POST.get('denominations_json', '{}')
        if denominations_json and denominations_json != '{}':
            try:
                denominations = json.loads(denominations_json)
                CashCount.objects.create(
                    session=session,
                    count_type='opening',
                    denominations=denominations,
                    total=opening_balance,
                    notes=notes
                )
            except json.JSONDecodeError:
                pass

        # Redirect to the page they were trying to access
        next_url = request.GET.get('next', 'configuration:dashboard')
        return redirect(next_url)

    context = {
        'config': config,
        'suggested_balance': suggested_balance,
        'last_session': last_session,
        'require_opening_balance': config.require_opening_balance,
    }

    return render(request, 'cash_register/pages/open_session.html', context)


@login_required
def close_session(request):
    """
    View to close the current cash session.
    """
    config = CashRegisterConfig.get_config()
    hub_config = HubConfig.get_config()
    store_config = StoreConfig.get_config()

    # Get user's open session
    session = CashSession.objects.filter(
        user=request.user,
        status='open'
    ).first()

    if not session:
        # No open session to close
        return redirect('cash_register:dashboard')

    # Calculate expected balance
    expected_balance = session.get_current_balance()

    if request.method == 'POST':
        # Handle session closing
        closing_balance = Decimal(request.POST.get('closing_balance', '0'))
        notes = request.POST.get('notes', '')

        # Create closing count if denominations provided
        denominations_json = request.POST.get('denominations_json', '{}')
        if denominations_json and denominations_json != '{}':
            try:
                denominations = json.loads(denominations_json)
                CashCount.objects.create(
                    session=session,
                    count_type='closing',
                    denominations=denominations,
                    total=closing_balance,
                    notes=notes
                )
            except json.JSONDecodeError:
                pass

        # Close the session
        session.close_session(closing_balance, notes)

        # Redirect to session detail or dashboard
        return redirect('cash_register:session_detail', session_id=session.id)

    context = {
        'config': config,
        'session': session,
        'expected_balance': expected_balance,
        'require_closing_balance': config.require_closing_balance,
    }

    return render(request, 'cash_register/pages/close_session.html', context)


@login_required
def session_detail(request, session_id):
    """Detail view for a specific session"""
    session = get_object_or_404(
        CashSession.objects.select_related('user'),
        id=session_id,
        user=request.user  # Only show user's own sessions
    )

    # Get movements grouped by type
    movements = session.movements.all()
    sales_movements = movements.filter(movement_type='sale')
    in_movements = movements.filter(movement_type='in')
    out_movements = movements.filter(movement_type='out')

    # Get counts
    counts = session.counts.all()

    context = {
        'session': session,
        'movements': movements,
        'sales_movements': sales_movements,
        'in_movements': in_movements,
        'out_movements': out_movements,
        'counts': counts,
    }

    return render(request, 'cash_register/pages/session_detail.html', context)


@login_required
@htmx_view('cash_register/pages/settings.html', 'cash_register/partials/settings_content.html')
def settings_view(request):
    """Settings page for cash register plugin. Supports HTMX."""
    config = CashRegisterConfig.get_config()

    # Get open_session for tabbar
    open_session = CashSession.objects.filter(
        user=request.user,
        status='open'
    ).first()

    return {
        'config': config,
        'open_session': open_session,
    }


@login_required
@require_http_methods(["POST"])
def settings_save(request):
    """Save cash register settings via JSON."""
    try:
        data = json.loads(request.body)
        config = CashRegisterConfig.get_config()

        config.enable_cash_register = data.get('enable_cash_register', True)
        config.require_opening_balance = data.get('require_opening_balance', True)
        config.require_closing_balance = data.get('require_closing_balance', True)
        config.allow_negative_balance = data.get('allow_negative_balance', False)
        config.protected_pos_url = data.get('protected_pos_url', '/modules/sales/pos/').strip() or '/modules/sales/pos/'
        config.save()

        return JsonResponse({'success': True, 'message': 'Settings saved'})
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@htmx_view('cash_register/pages/history.html', 'cash_register/partials/history_content.html')
def history(request):
    """
    Session history view with pagination and filters.
    Supports HTMX for SPA navigation.
    """
    # Get open_session for tabbar
    open_session = CashSession.objects.filter(
        user=request.user,
        status='open'
    ).first()

    # Get all user sessions ordered by date
    sessions = CashSession.objects.filter(
        user=request.user
    ).order_by('-opened_at')

    # Filter by status if provided
    status_filter = request.GET.get('status', '')
    if status_filter:
        sessions = sessions.filter(status=status_filter)

    # Filter by date range if provided
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if date_from:
        sessions = sessions.filter(opened_at__gte=date_from)
    if date_to:
        sessions = sessions.filter(opened_at__lte=date_to)

    return {
        'sessions': sessions,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'open_session': open_session,
    }


# ============================================================================
# API Endpoints
# ============================================================================

@login_required
@require_http_methods(["POST"])
def api_open_session(request):
    """Open a new cash session for current user"""
    try:
        data = json.loads(request.body)
        opening_balance = Decimal(str(data.get('opening_balance', 0)))
        notes = data.get('notes', '')
        denominations = data.get('denominations', {})

        # Check if already has open session
        existing = CashSession.objects.filter(
            user=request.user,
            status='open'
        ).first()

        if existing:
            return JsonResponse({
                'success': False,
                'error': 'You already have an open session'
            }, status=400)

        # Create session
        session = CashSession.open_for_user(
            user=request.user,
            opening_balance=opening_balance
        )
        session.opening_notes = notes
        session.save()

        # Create opening count if denominations provided
        if denominations:
            CashCount.objects.create(
                session=session,
                count_type='opening',
                denominations=denominations,
                total=opening_balance
            )

        return JsonResponse({
            'success': True,
            'message': 'Session opened successfully',
            'session': {
                'id': str(session.id),
                'session_number': session.session_number,
                'opening_balance': float(session.opening_balance)
            }
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@require_http_methods(["POST"])
def api_close_session(request):
    """Close the current open cash session"""
    try:
        data = json.loads(request.body)
        closing_balance = Decimal(str(data.get('closing_balance', 0)))
        notes = data.get('notes', '')
        denominations = data.get('denominations', {})

        # Get user's open session
        session = CashSession.objects.filter(
            user=request.user,
            status='open'
        ).first()

        if not session:
            return JsonResponse({
                'success': False,
                'error': 'No open session found'
            }, status=404)

        # Create closing count if denominations provided
        if denominations:
            CashCount.objects.create(
                session=session,
                count_type='closing',
                denominations=denominations,
                total=closing_balance
            )

        # Close session
        session.close_session(closing_balance, notes)

        return JsonResponse({
            'success': True,
            'message': 'Session closed successfully',
            'session': {
                'id': str(session.id),
                'session_number': session.session_number,
                'closing_balance': float(session.closing_balance),
                'expected_balance': float(session.expected_balance),
                'difference': float(session.difference)
            }
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@require_http_methods(["POST"])
def api_add_movement(request):
    """Add a cash movement to the current session"""
    try:
        data = json.loads(request.body)
        movement_type = data.get('movement_type')  # 'sale', 'in', 'out'
        amount = Decimal(str(data.get('amount', 0)))
        description = data.get('description', '')
        sale_reference = data.get('sale_reference', '')

        # Get user's open session
        session = CashSession.objects.filter(
            user=request.user,
            status='open'
        ).first()

        if not session:
            return JsonResponse({
                'success': False,
                'error': 'No open session found'
            }, status=404)

        # For 'out' movements, make amount negative
        if movement_type == 'out' and amount > 0:
            amount = -amount

        # Create movement
        movement = CashMovement.objects.create(
            session=session,
            movement_type=movement_type,
            amount=amount,
            description=description,
            sale_reference=sale_reference
        )

        return JsonResponse({
            'success': True,
            'message': 'Movement added successfully',
            'movement': {
                'id': str(movement.id),
                'type': movement.movement_type,
                'amount': float(movement.amount),
                'description': movement.description
            },
            'new_balance': float(session.get_current_balance())
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@require_http_methods(["GET"])
def api_current_session(request):
    """Get current open session for current user"""
    session = CashSession.objects.filter(
        user=request.user,
        status='open'
    ).first()

    if not session:
        return JsonResponse({
            'success': False,
            'error': 'No open session found'
        }, status=404)

    return JsonResponse({
        'success': True,
        'session': {
            'id': str(session.id),
            'session_number': session.session_number,
            'opening_balance': float(session.opening_balance),
            'current_balance': float(session.get_current_balance()),
            'total_sales': float(session.get_total_sales()),
            'total_in': float(session.get_total_in()),
            'total_out': float(session.get_total_out()),
            'opened_at': session.opened_at.isoformat(),
        }
    })


@login_required
@require_http_methods(["GET"])
def api_session_movements(request, session_id):
    """Get all movements for a session"""
    session = get_object_or_404(
        CashSession,
        id=session_id,
        user=request.user  # Only user's own sessions
    )

    movements = session.movements.all()

    data = [{
        'id': str(mov.id),
        'type': mov.movement_type,
        'type_display': mov.get_movement_type_display(),
        'amount': float(mov.amount),
        'description': mov.description,
        'sale_reference': mov.sale_reference,
        'created_at': mov.created_at.isoformat(),
    } for mov in movements]

    return JsonResponse({
        'success': True,
        'movements': data,
        'total_sales': float(session.get_total_sales()),
        'total_in': float(session.get_total_in()),
        'total_out': float(session.get_total_out()),
    })


# ============================================================================
# HTMX Endpoints for denomination calculator
# ============================================================================

@login_required
@require_http_methods(["POST"])
def htmx_calculate_denominations(request):
    """Calculate total from denominations (HTMX endpoint)"""
    try:
        data = json.loads(request.body)
        denominations = data.get('denominations', {})

        total = Decimal('0.00')
        for key, count in denominations.items():
            if count and count != '':
                value = Decimal(key.replace('coin_', '').replace('bill_', ''))
                total += value * Decimal(count)

        hub_config = HubConfig.get_config()
        currency = hub_config.currency
        symbols = {'EUR': '€', 'USD': '$', 'GBP': '£'}
        symbol = symbols.get(currency, currency)

        return JsonResponse({
            'total': float(total),
            'formatted': f"{symbol}{total:.2f}"
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def htmx_calculate_difference(request):
    """Calculate difference between expected and actual balance (HTMX endpoint)"""
    try:
        data = json.loads(request.body)
        expected = Decimal(str(data.get('expected', 0)))
        actual = Decimal(str(data.get('actual', 0)))

        difference = actual - expected

        hub_config = HubConfig.get_config()
        currency = hub_config.currency
        symbols = {'EUR': '€', 'USD': '$', 'GBP': '£'}
        symbol = symbols.get(currency, currency)

        # Determine color based on difference
        if difference == 0:
            color = 'success'
            label = 'Exact!'
            icon = 'checkmark-circle'
        elif difference > 0:
            color = 'warning'
            label = 'Surplus'
            icon = 'trending-up'
        else:
            color = 'danger'
            label = 'Shortage'
            icon = 'trending-down'

        return JsonResponse({
            'difference': float(difference),
            'formatted': f"{symbol}{abs(difference):.2f}",
            'color': color,
            'label': label,
            'icon': icon
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

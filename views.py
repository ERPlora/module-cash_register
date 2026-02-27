import json
from decimal import Decimal, InvalidOperation

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.decorators import login_required, permission_required
from apps.core.htmx import htmx_view
from apps.modules_runtime.navigation import with_module_nav

from .models import (
    CashRegisterSettings, CashRegister,
    CashSession, CashMovement, CashCount,
)


def _hub_id(request):
    return request.session.get('hub_id')


def _employee(request):
    from apps.accounts.models import LocalUser
    uid = request.session.get('local_user_id')
    if uid:
        try:
            return LocalUser.objects.get(pk=uid)
        except LocalUser.DoesNotExist:
            pass
    return None


# ============================================================================
# Dashboard
# ============================================================================

@login_required
@with_module_nav('cash_register', 'dashboard')
@htmx_view('cash_register/pages/index.html', 'cash_register/partials/dashboard_content.html')
def dashboard(request):
    hub = _hub_id(request)
    user = _employee(request)
    config = CashRegisterSettings.get_settings(hub)

    open_session = CashSession.get_current_session(hub, user) if user else None

    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_sessions = CashSession.objects.filter(
        hub_id=hub, user=user, status='closed', is_deleted=False,
        closed_at__gte=today_start,
    ) if user else CashSession.objects.none()

    recent_sessions = CashSession.objects.filter(
        hub_id=hub, user=user, is_deleted=False,
    ).order_by('-opened_at')[:10] if user else CashSession.objects.none()

    return {
        'config': config,
        'open_session': open_session,
        'today_sessions': today_sessions,
        'recent_sessions': recent_sessions,
    }


# ============================================================================
# Open / Close Session
# ============================================================================

@login_required
@with_module_nav('cash_register', 'dashboard')
@htmx_view('cash_register/pages/open_session.html', 'cash_register/partials/open_session_content.html')
def open_session(request):
    hub = _hub_id(request)
    user = _employee(request)
    config = CashRegisterSettings.get_settings(hub)

    existing = CashSession.get_current_session(hub, user) if user else None
    if existing:
        return redirect('cash_register:dashboard')

    last_session = CashSession.objects.filter(
        hub_id=hub, user=user, status='closed', is_deleted=False,
    ).order_by('-closed_at').first() if user else None

    suggested_balance = last_session.closing_balance if last_session and last_session.closing_balance else Decimal('0.00')

    if request.method == 'POST':
        balance_str = request.POST.get('opening_balance', '0').strip() or '0'
        try:
            opening_balance = Decimal(balance_str)
        except (ValueError, InvalidOperation):
            opening_balance = Decimal('0.00')

        notes = request.POST.get('notes', '')

        session = CashSession.open_for_user(
            hub_id=hub, user=user, opening_balance=opening_balance,
        )
        session.opening_notes = notes
        session.save(update_fields=['opening_notes', 'updated_at'])

        # Denomination count
        denom_json = request.POST.get('denominations_json', '{}')
        if denom_json and denom_json != '{}':
            try:
                CashCount.objects.create(
                    hub_id=hub,
                    session=session,
                    count_type='opening',
                    denominations=json.loads(denom_json),
                    total=opening_balance,
                    notes=notes,
                )
            except json.JSONDecodeError:
                pass

        next_url = request.GET.get('next', 'cash_register:dashboard')
        return redirect(next_url)

    return {
        'config': config,
        'suggested_balance': suggested_balance,
        'last_session': last_session,
    }


@login_required
@with_module_nav('cash_register', 'dashboard')
@htmx_view('cash_register/pages/close_session.html', 'cash_register/partials/close_session_content.html')
def close_session(request):
    hub = _hub_id(request)
    user = _employee(request)
    config = CashRegisterSettings.get_settings(hub)

    session = CashSession.get_current_session(hub, user) if user else None
    if not session:
        return redirect('cash_register:dashboard')

    expected_balance = session.get_current_balance()

    if request.method == 'POST':
        closing_balance = Decimal(request.POST.get('closing_balance', '0'))
        notes = request.POST.get('notes', '')

        denom_json = request.POST.get('denominations_json', '{}')
        if denom_json and denom_json != '{}':
            try:
                CashCount.objects.create(
                    hub_id=hub,
                    session=session,
                    count_type='closing',
                    denominations=json.loads(denom_json),
                    total=closing_balance,
                    notes=notes,
                )
            except json.JSONDecodeError:
                pass

        session.close_session(closing_balance, notes)
        return redirect('cash_register:session_detail', session_id=session.id)

    return {
        'config': config,
        'session': session,
        'expected_balance': expected_balance,
    }


# ============================================================================
# Session Detail & History
# ============================================================================

@login_required
@with_module_nav('cash_register', 'dashboard')
@htmx_view('cash_register/pages/session_detail.html', 'cash_register/partials/session_detail_content.html')
def session_detail(request, session_id):
    hub = _hub_id(request)
    session = get_object_or_404(
        CashSession.objects.select_related('user', 'register'),
        id=session_id, hub_id=hub, is_deleted=False,
    )

    movements = session.movements.filter(is_deleted=False)
    counts = session.counts.filter(is_deleted=False)

    return {
        'session': session,
        'movements': movements,
        'sales_movements': movements.filter(movement_type='sale'),
        'in_movements': movements.filter(movement_type='in'),
        'out_movements': movements.filter(movement_type='out'),
        'refund_movements': movements.filter(movement_type='refund'),
        'counts': counts,
    }


@login_required
@with_module_nav('cash_register', 'history')
@htmx_view('cash_register/pages/history.html', 'cash_register/partials/history_content.html')
def history(request):
    hub = _hub_id(request)
    user = _employee(request)

    sessions = CashSession.objects.filter(
        hub_id=hub, user=user, is_deleted=False,
    ).order_by('-opened_at') if user else CashSession.objects.none()

    status_filter = request.GET.get('status', '')
    if status_filter:
        sessions = sessions.filter(status=status_filter)

    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        sessions = sessions.filter(opened_at__gte=date_from)
    if date_to:
        sessions = sessions.filter(opened_at__lte=date_to)

    open_session = CashSession.get_current_session(hub, user) if user else None

    return {
        'sessions': sessions,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'open_session': open_session,
    }


# ============================================================================
# Settings
# ============================================================================

@login_required
@permission_required('cash_register.manage_settings')
@with_module_nav('cash_register', 'settings')
@htmx_view('cash_register/pages/settings.html', 'cash_register/partials/settings_content.html')
def settings_view(request):
    hub = _hub_id(request)
    user = _employee(request)
    config = CashRegisterSettings.get_settings(hub)

    registers = CashRegister.objects.filter(
        hub_id=hub, is_deleted=False,
    ).order_by('name')

    open_session = CashSession.get_current_session(hub, user) if user else None

    if request.method == 'POST':
        config.enable_cash_register = request.POST.get('enable_cash_register') == 'on'
        config.require_opening_balance = request.POST.get('require_opening_balance') == 'on'
        config.require_closing_balance = request.POST.get('require_closing_balance') == 'on'
        config.allow_negative_balance = request.POST.get('allow_negative_balance') == 'on'
        config.auto_open_session_on_login = request.POST.get('auto_open_session_on_login') == 'on'
        config.auto_close_session_on_logout = request.POST.get('auto_close_session_on_logout') == 'on'
        config.protected_pos_url = request.POST.get('protected_pos_url', '').strip() or '/m/sales/pos/'
        config.save()

        is_htmx = request.headers.get('HX-Request') == 'true'
        if is_htmx:
            return HttpResponse('<span class="badge color-success">Saved</span>')
        return JsonResponse({'success': True})

    return {
        'config': config,
        'registers': registers,
        'open_session': open_session,
    }


@login_required
@require_http_methods(["POST"])
def add_register(request):
    hub = _hub_id(request)
    try:
        name = request.POST.get('name', '').strip()
        if not name:
            return JsonResponse({'success': False, 'error': _('Name required')}, status=400)
        CashRegister.objects.create(hub_id=hub, name=name)
        return redirect('cash_register:settings')
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def toggle_register(request, register_id):
    hub = _hub_id(request)
    reg = get_object_or_404(CashRegister, id=register_id, hub_id=hub, is_deleted=False)
    reg.is_active = not reg.is_active
    reg.save(update_fields=['is_active', 'updated_at'])
    return redirect('cash_register:settings')


# ============================================================================
# API Endpoints
# ============================================================================

@login_required
@require_http_methods(["POST"])
def api_open_session(request):
    hub = _hub_id(request)
    user = _employee(request)
    try:
        data = json.loads(request.body)
        opening_balance = Decimal(str(data.get('opening_balance', 0)))
        notes = data.get('notes', '')
        denominations = data.get('denominations', {})

        existing = CashSession.get_current_session(hub, user) if user else None
        if existing:
            return JsonResponse({'success': False, 'error': _('Session already open')}, status=400)

        session = CashSession.open_for_user(hub_id=hub, user=user, opening_balance=opening_balance)
        session.opening_notes = notes
        session.save(update_fields=['opening_notes', 'updated_at'])

        if denominations:
            CashCount.objects.create(
                hub_id=hub, session=session, count_type='opening',
                denominations=denominations, total=opening_balance,
            )

        return JsonResponse({
            'success': True,
            'session': {
                'id': str(session.id),
                'session_number': session.session_number,
                'opening_balance': float(session.opening_balance),
            },
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def api_close_session(request):
    hub = _hub_id(request)
    user = _employee(request)
    try:
        data = json.loads(request.body)
        closing_balance = Decimal(str(data.get('closing_balance', 0)))
        notes = data.get('notes', '')
        denominations = data.get('denominations', {})

        session = CashSession.get_current_session(hub, user) if user else None
        if not session:
            return JsonResponse({'success': False, 'error': _('No open session')}, status=404)

        if denominations:
            CashCount.objects.create(
                hub_id=hub, session=session, count_type='closing',
                denominations=denominations, total=closing_balance,
            )

        session.close_session(closing_balance, notes)

        return JsonResponse({
            'success': True,
            'session': {
                'id': str(session.id),
                'session_number': session.session_number,
                'closing_balance': float(session.closing_balance),
                'expected_balance': float(session.expected_balance),
                'difference': float(session.difference),
            },
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def api_add_movement(request):
    hub = _hub_id(request)
    user = _employee(request)
    try:
        data = json.loads(request.body)
        movement_type = data.get('movement_type')
        amount = Decimal(str(data.get('amount', 0)))
        description = data.get('description', '')
        sale_reference = data.get('sale_reference', '')

        session = CashSession.get_current_session(hub, user) if user else None
        if not session:
            return JsonResponse({'success': False, 'error': _('No open session')}, status=404)

        if movement_type == 'out' and amount > 0:
            amount = -amount

        movement = CashMovement.objects.create(
            hub_id=hub,
            session=session,
            movement_type=movement_type,
            amount=amount,
            description=description,
            sale_reference=sale_reference,
            employee=user,
        )

        return JsonResponse({
            'success': True,
            'movement': {
                'id': str(movement.id),
                'type': movement.movement_type,
                'amount': float(movement.amount),
            },
            'new_balance': float(session.get_current_balance()),
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_http_methods(["GET"])
def api_current_session(request):
    hub = _hub_id(request)
    user = _employee(request)

    session = CashSession.get_current_session(hub, user) if user else None
    if not session:
        return JsonResponse({'success': False, 'error': _('No open session')}, status=404)

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
        },
    })


@login_required
@require_http_methods(["GET"])
def api_session_movements(request, session_id):
    hub = _hub_id(request)
    session = get_object_or_404(
        CashSession, id=session_id, hub_id=hub, is_deleted=False,
    )

    movements = session.movements.filter(is_deleted=False)
    data = [{
        'id': str(m.id),
        'type': m.movement_type,
        'type_display': m.get_movement_type_display(),
        'amount': float(m.amount),
        'description': m.description,
        'sale_reference': m.sale_reference,
        'created_at': m.created_at.isoformat(),
    } for m in movements]

    return JsonResponse({
        'success': True,
        'movements': data,
        'total_sales': float(session.get_total_sales()),
        'total_in': float(session.get_total_in()),
        'total_out': float(session.get_total_out()),
    })


# ============================================================================
# HTMX Endpoints (denomination calculator)
# ============================================================================

@login_required
@require_http_methods(["POST"])
def htmx_calculate_denominations(request):
    try:
        data = json.loads(request.body)
        denominations = data.get('denominations', {})

        total = Decimal('0.00')
        for key, count in denominations.items():
            if count and str(count).strip():
                value = Decimal(key.replace('coin_', '').replace('bill_', ''))
                total += value * Decimal(str(count))

        return JsonResponse({'total': float(total), 'formatted': f"{total:.2f}"})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def htmx_calculate_difference(request):
    try:
        data = json.loads(request.body)
        expected = Decimal(str(data.get('expected', 0)))
        actual = Decimal(str(data.get('actual', 0)))
        difference = actual - expected

        if difference == 0:
            color, label = 'success', 'Exact'
        elif difference > 0:
            color, label = 'warning', 'Surplus'
        else:
            color, label = 'danger', 'Shortage'

        return JsonResponse({
            'difference': float(difference),
            'formatted': f"{abs(difference):.2f}",
            'color': color,
            'label': label,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

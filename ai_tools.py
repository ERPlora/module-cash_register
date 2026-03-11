"""AI tools for the Cash Register module."""
from assistant.tools import AssistantTool, register_tool


@register_tool
class ListCashSessions(AssistantTool):
    name = "list_cash_sessions"
    description = "List cash register sessions (open/closed). Shows opening/closing balances, differences."
    module_id = "cash_register"
    required_permission = "cash_register.view_cashsession"
    parameters = {
        "type": "object",
        "properties": {
            "status": {"type": "string", "description": "Filter: open, closed, suspended"},
            "limit": {"type": "integer", "description": "Max results (default 20)"},
        },
        "required": [],
        "additionalProperties": False,
    }

    def execute(self, args, request):
        from cash_register.models import CashSession
        qs = CashSession.objects.select_related('user', 'register').all()
        if args.get('status'):
            qs = qs.filter(status=args['status'])
        limit = args.get('limit', 20)
        return {
            "sessions": [
                {
                    "id": str(s.id), "session_number": s.session_number, "status": s.status,
                    "register": s.register.name if s.register else None,
                    "user": s.user.display_name if s.user else None,
                    "opened_at": s.opened_at.isoformat() if s.opened_at else None,
                    "opening_balance": str(s.opening_balance),
                    "closing_balance": str(s.closing_balance) if s.closing_balance else None,
                    "expected_balance": str(s.expected_balance) if s.expected_balance else None,
                    "difference": str(s.difference) if s.difference else None,
                }
                for s in qs.order_by('-opened_at')[:limit]
            ]
        }


@register_tool
class GetCashSessionSummary(AssistantTool):
    name = "get_cash_session_summary"
    description = "Get summary of a cash session: total sales, cash in/out, refunds."
    module_id = "cash_register"
    required_permission = "cash_register.view_cashsession"
    parameters = {
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "description": "Cash session ID"},
        },
        "required": ["session_id"],
        "additionalProperties": False,
    }

    def execute(self, args, request):
        from cash_register.models import CashSession, CashMovement
        from django.db.models import Sum
        session = CashSession.objects.get(id=args['session_id'])
        movements = CashMovement.objects.filter(session=session)
        sales = movements.filter(movement_type='sale').aggregate(total=Sum('amount'))['total'] or 0
        refunds = movements.filter(movement_type='refund').aggregate(total=Sum('amount'))['total'] or 0
        cash_in = movements.filter(movement_type='in').aggregate(total=Sum('amount'))['total'] or 0
        cash_out = movements.filter(movement_type='out').aggregate(total=Sum('amount'))['total'] or 0
        return {
            "session_number": session.session_number, "status": session.status,
            "opening_balance": str(session.opening_balance),
            "total_sales": str(sales), "total_refunds": str(refunds),
            "total_cash_in": str(cash_in), "total_cash_out": str(cash_out),
            "movement_count": movements.count(),
        }


@register_tool
class ListCashRegisters(AssistantTool):
    name = "list_cash_registers"
    description = "List cash registers."
    module_id = "cash_register"
    required_permission = "cash_register.view_cashregister"
    parameters = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}

    def execute(self, args, request):
        from cash_register.models import CashRegister
        return {
            "registers": [
                {"id": str(r.id), "name": r.name, "is_active": r.is_active}
                for r in CashRegister.objects.all()
            ]
        }


@register_tool
class CreateCashRegister(AssistantTool):
    name = "create_cash_register"
    description = "Create a new cash register."
    module_id = "cash_register"
    required_permission = "cash_register.add_cashregister"
    requires_confirmation = True
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Register name (e.g., 'Caja 1')"},
        },
        "required": ["name"],
        "additionalProperties": False,
    }

    def execute(self, args, request):
        from cash_register.models import CashRegister
        r = CashRegister.objects.create(name=args['name'])
        return {"id": str(r.id), "name": r.name, "created": True}


@register_tool
class CloseCashSession(AssistantTool):
    name = "close_cash_session"
    description = (
        "Close an open cash register session. Provide session_id and the physical "
        "closing_balance (the actual cash counted in the drawer). The difference "
        "between expected and closing balance is calculated automatically."
    )
    module_id = "cash_register"
    required_permission = "cash_register.change_cashsession"
    requires_confirmation = True
    parameters = {
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "description": "Cash session ID to close"},
            "closing_balance": {"type": "number", "description": "Physical cash counted in the drawer"},
            "notes": {"type": "string", "description": "Optional closing notes"},
        },
        "required": ["session_id", "closing_balance"],
        "additionalProperties": False,
    }

    def get_confirmation_data(self, args, request):
        """Return a rich session summary so the user can review before closing."""
        try:
            from cash_register.models import CashSession
            from decimal import Decimal

            session = CashSession.objects.select_related('user', 'register').get(
                id=args['session_id'],
            )

            opening = session.opening_balance
            total_sales = session.get_total_sales()
            total_in = session.get_total_in()
            total_out = session.get_total_out()
            total_refunds = session.get_total_refunds()
            current_balance = session.get_current_balance()
            closing = Decimal(str(args['closing_balance']))
            difference = closing - current_balance

            def fmt(amount):
                return f"€{amount:,.2f}"

            rows = [
                {"label": "Session", "value": session.session_number},
                {"label": "Register", "value": session.register.name if session.register else "—"},
                {"label": "Cashier", "value": session.user.display_name if session.user else "—"},
                {"label": "Duration", "value": session.get_duration()},
                {"label": "Opening balance", "value": fmt(opening)},
                {"label": "Total sales", "value": fmt(total_sales)},
            ]
            if total_in:
                rows.append({"label": "Cash in", "value": fmt(total_in)})
            if total_out:
                rows.append({"label": "Cash out", "value": fmt(total_out)})
            if total_refunds:
                rows.append({"label": "Refunds", "value": fmt(total_refunds)})

            rows.append({"label": "Expected balance", "value": fmt(current_balance)})
            rows.append({
                "label": "Closing balance",
                "value": fmt(closing),
                "highlight": "color-primary",
            })

            diff_str = fmt(abs(difference))
            if difference < 0:
                diff_display = f"−{diff_str}"
                diff_highlight = "color-error"
            elif difference > 0:
                diff_display = f"+{diff_str}"
                diff_highlight = "color-warning"
            else:
                diff_display = "€0.00"
                diff_highlight = "color-success"

            rows.append({
                "label": "Difference",
                "value": diff_display,
                "highlight": diff_highlight,
            })

            warning = "This action will permanently close the session and cannot be undone."
            if abs(difference) > Decimal('50'):
                warning = (
                    f"Large difference detected ({diff_display}). "
                    "Please verify the closing balance before confirming."
                )

            return {
                "title": "Cash Register Summary",
                "badge": "color-warning",
                "rows": rows,
                "warning": warning,
            }
        except Exception:
            return None

    def execute(self, args, request):
        from cash_register.models import CashSession
        session = CashSession.objects.get(id=args['session_id'])
        if session.status != 'open':
            return {"error": f"Session {session.session_number} is not open (status: {session.status})"}
        session.close_session(
            closing_balance=args['closing_balance'],
            notes=args.get('notes', ''),
        )
        return {
            "id": str(session.id),
            "session_number": session.session_number,
            "status": session.status,
            "closing_balance": str(session.closing_balance),
            "expected_balance": str(session.expected_balance),
            "difference": str(session.difference),
            "closed": True,
        }

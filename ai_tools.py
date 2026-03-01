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
        from django.db.models import Sum, Q
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

# Cash Register Module

Cash register session management with per-user sessions, movements, and denomination counting.

## Features

- Per-user cash sessions with opening and closing balances
- Cash denomination calculator (bills and coins breakdown)
- Cash movements: sale, refund, cash in, cash out
- Automatic sale recording from sales module integration
- Expected vs actual balance with difference calculation
- Multiple physical registers support
- Middleware protection for URLs requiring open session
- Auto open/close session on login/logout (configurable)
- Session history with filtering by status and date
- HTMX auto-save settings

## Installation

This module is installed automatically via the ERPlora Marketplace.

## Configuration

Access settings via: **Menu > Cash Register > Settings**

Settings include:
- Enable/disable cash register
- Require opening balance (cash count at open)
- Require closing balance (cash count at close)
- Allow negative balance
- Auto open session on login
- Auto close session on logout
- Protected POS URL (default: `/m/sales/pos/`)

## Usage

Access via: **Menu > Cash Register**

### Views

| View | URL | Description |
|------|-----|-------------|
| Dashboard | `/m/cash_register/` | Current session status, open/close buttons, today's stats |
| Open Session | `/m/cash_register/open/` | Open session form with denomination calculator |
| Close Session | `/m/cash_register/close/` | Close session with balance reconciliation |
| Session Detail | `/m/cash_register/session/<id>/` | Session details with movements and counts |
| History | `/m/cash_register/history/` | Session history with filters |
| Settings | `/m/cash_register/settings/` | Module configuration (HTMX auto-save) |

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/m/cash_register/api/session/open/` | POST | Open new session (body: opening_balance, notes, denominations) |
| `/m/cash_register/api/session/close/` | POST | Close current session (body: closing_balance, notes, denominations) |
| `/m/cash_register/api/session/current/` | GET | Get current open session for user |
| `/m/cash_register/api/session/<id>/movements/` | GET | List movements for a session |
| `/m/cash_register/api/movement/add/` | POST | Add movement (body: movement_type, amount, description) |

### HTMX Endpoints

| Endpoint | Description |
|----------|-------------|
| `/m/cash_register/htmx/calculate-denominations/` | Calculate total from denomination breakdown |
| `/m/cash_register/htmx/calculate-difference/` | Calculate expected vs actual difference |

### Middleware

`CashSessionRequiredMiddleware` protects URLs that require an open cash session. If a user accesses the protected POS URL without an open session, they are redirected to `/m/cash_register/open/`.

## Models

| Model | Description |
|-------|-------------|
| `CashRegisterSettings` | Per-hub configuration (require balance, auto open/close, protected URL) |
| `CashRegister` | Physical cash register or terminal |
| `CashSession` | Session from open to close with balances, expected balance, and difference |
| `CashMovement` | Movement within a session (sale, refund, in, out) with payment method |
| `CashCount` | Denomination count at open or close (JSON breakdown of bills/coins) |

## Permissions

| Permission | Description |
|------------|-------------|
| `cash_register.view_session` | View sessions |
| `cash_register.add_session` | Open sessions |
| `cash_register.close_session` | Close sessions |
| `cash_register.view_movement` | View movements |
| `cash_register.add_movement` | Add movements |
| `cash_register.view_count` | View cash counts |
| `cash_register.add_count` | Add cash counts |
| `cash_register.view_reports` | View reports |
| `cash_register.manage_settings` | Manage settings |

## Integration with Other Modules

| Module | Integration |
|--------|-------------|
| `sales` | Automatic sale recording via `CashMovement.record_sale()` |

## Dependencies

None

## License

MIT

## Author

ERPlora Team - support@erplora.com

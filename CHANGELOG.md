# Changelog

All notable changes to the Cash Register module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-12-25

### Added

- Initial release of Cash Register module
- **Core Features**
  - Cash session management (open/close)
  - Cash in/out movements
  - Cash count at session end
  - Session reports and summaries
  - Discrepancy detection

- **Models**
  - `CashSession`: Daily cash session with opening/closing amounts
  - `CashMovement`: Cash in/out transactions
  - `CashCount`: Denomination counts for verification
  - `CashRegisterConfig`: Module configuration

- **Views**
  - Current session status
  - Open/close session wizard
  - Cash movements list
  - Session history
  - Cash count form

- **Internationalization**
  - English translations (base)
  - Spanish translations

### Technical Details

- Automatic session opening detection
- Expected vs actual cash calculation
- Integration with Sales module for payment tracking
- Supports multiple payment methods tracking

---

## [Unreleased]

### Planned

- Multiple cash drawers support
- Blind counts (without showing expected)
- Cash reconciliation reports
- Bank deposit tracking
- Safe management

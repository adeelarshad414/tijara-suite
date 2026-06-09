# Tijara Suite Screenshot User Guide

Generated from live local Odoo screenshots on 2026-06-09 09:05 UTC.

## Live Verification Snapshot

- Database: `tijara_dev`
- Localization: Pakistan country, PKR currency, GST 18% sales tax verified
- Demo users: seeded from `docs/TEST_CREDENTIALS.csv`
- Screenshot source: `docs/screenshots/INDEX.md`

## Demo Roles

| Role | Login | Primary use |
|---|---|---|
| `platform_superadmin` | `superadmin@demo.tijara-suite.local` | Provision tenants, control SaaS plans, review protected release evidence, and manage platform configuration. |
| `tenant_admin` | `tenant-admin@demo.tijara-suite.local` | Configure company settings, feature flags, staff access, POS hardware, receipt templates, dashboards, and approvals. |
| `cashier` | `cashier@demo.tijara-suite.local` | Run B2C/B2B checkout, bill discounts, barcode refund scans, receipt print, and offline queue retry. |
| `inventory_manager` | `inventory-manager@demo.tijara-suite.local` | Maintain products, low-stock/expiry alerts, racks, shelves, bins, warehouses, and bulk import/export. |
| `accountant` | `accountant@demo.tijara-suite.local` | Review settlements, refunds, chargebacks, draft accounting moves, and FBR queue evidence. |
| `expense_manager` | `expense-manager@demo.tijara-suite.local` | Submit, approve, pay, and export business expense records. |
| `salary_manager` | `salary-manager@demo.tijara-suite.local` | Review gross pay, deductions, bonuses, approvals, and payroll payment status. |
| `loyalty_manager` | `loyalty-manager@demo.tijara-suite.local` | Manage walk-in customers, B2B/B2C details, loyalty tiers, point balances, and retention history. |
| `vertical_manager` | `vertical-manager@demo.tijara-suite.local` | Maintain vertical catalog settings, B2B/B2C prices, GST, service charge, delivery charge, and food-service tax policy. |
| `promotion_manager` | `promotion-manager@demo.tijara-suite.local` | Publish promotions, menu boards, deals boards, queue displays, and customer-facing messages. |
| `analytics_manager` | `analytics-manager@demo.tijara-suite.local` | Review dashboards, KPI history, trend charts, vertical sales, loyalty, expenses, salaries, and charge policy analytics. |
| `restaurant_operator` | `restaurant@demo.tijara-suite.local` | Operate dine-in, takeaway, pickup, kiosk orders, queue tickets, kitchen status, menu boards, and pickup screens. |
| `public_display` | `public-display@demo.tijara-suite.local` | Run public display routes for kiosk, customer display, queue, menu, deals, and promotions. |

## Screenshot Walkthrough

### Login And Authenticated App Shell

Start from the Odoo login page, select the `tijara_dev` database when prompted, and sign in with the role account assigned to your workflow.

![Login And Authenticated App Shell](screenshots/platform-superadmin/odoo-login.png)

1. Open `http://localhost:8069/web/login?db=tijara_dev`.
2. Use the role account from `docs/TEST_CREDENTIALS.csv`.
3. After login, confirm the top Odoo navigation and company switcher are visible.

### Back Office App Shell

The authenticated Odoo shell is the entry point for Apps, POS, Inventory, Sales, Purchases, Accounting, SaaS control, analytics, and configuration menus.

![Back Office App Shell](screenshots/platform-superadmin/odoo-app-shell.png)

1. Use the app switcher to open the required module.
2. Use role-specific menus for daily work and manager approvals.
3. Keep demo operations in the local `tijara_dev` database.

### Expense Management

Expense managers submit, approve, cancel, mark paid, and audit back-office expense requests in PKR with tax amounts and receipt references.

![Expense Management](screenshots/expense-manager/expense-management.png)

1. Open Retail Operations > Back Office > Expenses.
2. Create or review an expense with vendor or employee, category, payment method, amount, tax, and receipt reference.
3. Move the request through submitted, approved, and paid states so finance dashboards can collect the expense pipeline.

### Salary Management

Salary batches track employees, roles, gross pay, deductions, bonuses, net payable, approval, and paid status.

![Salary Management](screenshots/salary-manager/salary-management.png)

1. Open Retail Operations > Back Office > Salaries.
2. Review salary lines for the month or payroll period.
3. Approve the batch and mark it paid after finance sign-off.

### Loyalty Customer Records

Customer records support walk-in details, B2B/B2C customer type, CNIC/NTN/STRN fields, loyalty opt-in, tier, and points.

![Loyalty Customer Records](screenshots/loyalty-manager/loyalty-customer-records.png)

1. Open Contacts or the Loyalty Customer Records screen.
2. Search by name, mobile, email, loyalty number, or customer type.
3. Update tier and verify points after POS or kiosk purchases.

### Business Policy Settings

Company policy fields control Pakistan GST, cafe service charge, delivery charge, cafe/restaurant card and cash tax, FBR flags, and loyalty earning.

![Business Policy Settings](screenshots/vertical-manager/business-policy-settings.png)

1. Open the business policy settings screen from the tenant admin or vertical manager account.
2. Enable or disable GST, service charge, delivery charge, and food-service payment tax according to the business type.
3. Save policy changes and rerun kiosk/POS checkout tests before rollout.

### Analytics Dashboards

Analytics dashboards organize owner, inventory, POS, back-office, restaurant, vertical, loyalty, and promotion KPIs with SaaS feature-aware widgets.

![Analytics Dashboards](screenshots/analytics-manager/analytics-dashboards.png)

1. Open Analytics > Dashboards.
2. Review dashboard widgets by audience and feature flag.
3. Use dashboard notes to map each KPI to operational reports and collectors.

### KPI History

KPI history stores daily automated collector snapshots for POS, inventory, queue, expenses, salaries, loyalty, vertical catalog, and food-service tax policy.

![KPI History](screenshots/analytics-manager/kpi-history.png)

1. Open Analytics > KPI History.
2. Group by business area, metric, date, or warehouse.
3. Use graph and pivot views to inspect trends, history, records, charts, and reporting evidence.

### Kiosk Self Ordering

The kiosk route supports dine-in, takeaway, pickup, B2C/B2B pricing, PKR prices, customer details, payment selection, and checkout.

![Kiosk Self Ordering](screenshots/public-display/kiosk-display.png)

1. Open `/tijara/display/tijara-demo-kiosk?db=tijara_dev` on a kiosk or tablet.
2. Choose the service mode and customer type.
3. Tap products to add them to the cart, enter customer details when needed, and press Checkout.

### Customer Display

The customer-facing display shows the live order reference, item lines, quantities, PKR subtotal, discount, tax, and total.

![Customer Display](screenshots/public-display/customer-display.png)

1. Open `/tijara/display/tijara-demo-customer-display?db=tijara_dev` on the customer-side display.
2. Keep it full screen near the POS counter.
3. Use it to verify cart lines, discounts, GST, and totals with the customer before payment.

### Queue Display

The queue display shows waiting, preparing, ready, and called tickets in large, readable cards for restaurant, bakery, and pickup counters.

![Queue Display](screenshots/public-display/queue-display.png)

1. Open `/tijara/display/tijara-demo-queue-display?db=tijara_dev` on a public screen.
2. Use queue tickets from kiosk or POS orders.
3. Advance ticket state from the operator workflow so the display reflects pickup readiness.

### Menu Board

The menu board displays active menu items and promotions for restaurant, bakery, and food-service verticals.

![Menu Board](screenshots/public-display/menu-board.png)

1. Open `/tijara/display/tijara-demo-menu-board?db=tijara_dev`.
2. Maintain menu items, Urdu/English names, and prices in display content or products.
3. Use active start/end dates for timed menu or campaign changes.

### Deals And Promotions Board

The deals board highlights discount campaigns and promotion messages for in-store screens.

![Deals And Promotions Board](screenshots/public-display/deals-board.png)

1. Open `/tijara/display/tijara-demo-deals-board?db=tijara_dev`.
2. Create promotions with display visibility enabled.
3. Review price, discount, and availability before running the campaign in store.

## Workflow Checklist

### Back Office Expenses, Salaries, And Approvals

- Use expense requests for rent, utilities, transport, delivery, maintenance, marketing, salary advances, and other operating costs.
- Approve and mark expenses paid so the back-office finance dashboard can collect state totals.
- Use salary batches for gross pay, deductions, bonuses, net payable, approval, and paid status.
- Run the daily KPI collector after approvals to update expense and salary analytics.

### Customers, Loyalty, And Vertical Retail Mix

- Capture walk-in customer details at POS, kiosk, or back office when the customer wants history or loyalty points.
- Maintain B2C, wholesale, corporate, and supplier customer types with NTN/STRN where needed.
- Set product vertical tags for superstore, grocery, cosmetics, cloth, garments, uniform, shoes, pharmacy, fast food, restaurant, bakery, mobile, and electronics stores.
- Review vertical catalog coverage, B2B/B2C price spread, loyalty points liability, and repeat-customer KPI history.

### POS Checkout, Discounts, Refunds, And Print

- Open POS from the app shell and select the active Tijara Demo POS session.
- Choose B2C or B2B when the feature is enabled for the tenant.
- Add products by search, barcode scanner, QR scanner, or touch product cards.
- Apply an overall bill discount by percentage or amount; the paired value recalculates automatically.
- Take payment, validate the sale, print the receipt, and use the receipt barcode for future refund/exchange lookup.

### Inventory, Expiry, Shelves, And Bulk Data

- Use product forms for B2C/B2B prices, Urdu names, GST category, barcode aliases, and quick-sale flags.
- Use inventory intelligence for low-stock alerts, expiry alerts, warehouses, store rooms, racks, shelves, and bins.
- Use CSV import/export for products, prices, stock, contacts, hardware devices, receipt templates, storage positions, and promotions.
- Review import validation messages before applying data to a tenant database.

### Restaurant, Bakery, And Pickup Operations

- Use dine-in, takeaway, and pickup modes on kiosk or POS flows.
- Use delivery mode when delivery charge is enabled for the tenant.
- For cafe tenants, enable service charge; for cafe/restaurant tenants, enable card 5% and cash 16% payment tax policy when applicable.
- Send kiosk orders into queue tickets and linked POS payments when the profile has a POS register and payment method.
- Use queue display for public ticket status and kitchen/operator views for preparation stages.
- Use menu and deals boards for active promotions, food menus, bakery offers, and pickup announcements.

### SaaS Controls And Tenant Operations

- Enable or disable B2B sales, queue display, promotion display, customer display, kiosk, and vertical packs by tenant plan.
- Use tenant provisioning manifests for DNS, ingress, admin bootstrap, backup, monitoring, and smoke evidence.
- Keep secrets in `secrets/.env.secrets`; keep non-secret runtime configuration in `.env` and deploy templates.

### Payments, FBR, Analytics, And Production Evidence

- Use payment provider records for JazzCash, Easypaisa, Stripe, generic/manual webhooks, settlement imports, refunds, and chargebacks.
- Use FBR queue records for dry-run/live adapter evidence until certified-provider credentials are available.
- Use analytics dashboards for POS, inventory, queue, promotions, trends, history, KPI snapshots, charts, and report catalogs.
- Use protected release evidence, security scans, monitoring evidence, backups, restore drills, and load tests before production sign-off.

## Production Readiness Notes

- Physical printer, scanner, drawer, scale, and display certification still needs real device evidence.
- FBR live operation still needs certified-provider credentials and compliance sign-off.
- Payment providers still need PSP certification, settlement reconciliation, refunds, and chargeback sign-off.
- Assumption-mode evidence can document dummy hardware/FBR/PSP readiness but does not replace production certification.
- Full staging browser E2E should run against seeded users and real staging URLs before customer deployment.
- Monitoring, alerting, restore drills, load tests, and security scans should be attached to release sign-off.

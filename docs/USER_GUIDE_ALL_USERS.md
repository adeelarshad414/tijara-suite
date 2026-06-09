# Tijara Suite All-User Guide

Version: 2026-06-09
Audience: platform owners, tenant admins, cashiers, inventory teams, ecommerce teams, accountants, restaurant operators, display/kiosk operators, and business managers.

## 1. Purpose

Tijara Suite is a Pakistan-focused retail and restaurant business platform built
on Odoo Community. It supports POS, B2B/B2C selling, inventory, procurement,
customers, suppliers, refunds, exchanges, restaurant dine-in/takeaway/pickup,
kiosk, queue screens, customer display, promotion/menu/deal screens, analytics,
ecommerce storefront and checkout, hardware bridge readiness, and SaaS feature
control.

This guide explains how each user role should use the application during daily
operations. It is written for local demo, pilot, and training use.

## System And Workflow Diagrams

Use `docs/DIAGRAMS.md` when training users or reviewing a rollout. It includes
deployment architecture, system design, module/component diagrams, UML, POS
checkout, ecommerce checkout, restaurant/kiosk, offline POS, hardware print,
tenant provisioning, analytics, and release evidence flows.

## 2. Local Access

Open the application:

```text
http://localhost:8069/web/login?db=tijara_dev
```

Project directory:

```text
/Users/adeel.arshad/Documents/Codex/2026-06-04/what-do-you-know-about-odoo/outputs/tijara-suite
```

Credentials file:

```text
docs/TEST_CREDENTIALS.csv
```

Start the local application:

```bash
bash scripts/dev-start.sh
```

Start, install modules, and seed POS demo data:

```bash
TIJARA_DEV_INSTALL_SUITE=1 TIJARA_DEV_SEED_POS_DEMO=1 bash scripts/dev-start.sh
```

Stop the local application:

```bash
bash scripts/dev-stop.sh
```

## 3. Demo Users

Use these local demo accounts for training and testing. `docs/TEST_CREDENTIALS.csv`
is the canonical credentials matrix; this guide mirrors it for operators.
These credentials are for local demo only and must not be used in production.

| Role | Login | Password | Main Use |
|---|---|---|---|
| Platform Superadmin | `superadmin@demo.tijara-suite.local` | `Demo@Superadmin2024!` | Platform setup, SaaS plans, tenants, release evidence, settings |
| Tenant Admin | `tenant-admin@demo.tijara-suite.local` | `Demo@TenantAdmin2024!` | Business setup, users, plans, inventory/POS configuration |
| Cashier | `cashier@demo.tijara-suite.local` | `Demo@Cashier2024!` | POS checkout, refund, exchange, receipt printing |
| Inventory Manager | `inventory-manager@demo.tijara-suite.local` | `Demo@InventoryManager2024!` | Products, stock, racks, shelves, expiry and low-stock alerts |
| Accountant | `accountant@demo.tijara-suite.local` | `Demo@Accountant2024!` | Invoices, settlements, refunds, chargebacks, FBR queue review |
| Expense Manager | `expense-manager@demo.tijara-suite.local` | `Demo@Expense2024!` | Back-office expenses, approvals, utility bills, delivery settlements |
| Salary Manager | `salary-manager@demo.tijara-suite.local` | `Demo@Salary2024!` | Salary batches, deductions, bonuses, monthly payroll evidence |
| Loyalty Manager | `loyalty-manager@demo.tijara-suite.local` | `Demo@Loyalty2024!` | Customer profiles, walk-in conversion, loyalty points, B2B customer history |
| Vertical Manager | `vertical-manager@demo.tijara-suite.local` | `Demo@Vertical2024!` | Vertical catalogs, business policies, B2C/B2B prices, stock policy |
| Promotion Manager | `promotion-manager@demo.tijara-suite.local` | `Demo@Promo2024!` | Promotions, menu boards, deals boards, customer/queue display content |
| Ecommerce Manager | `ecommerce-manager@demo.tijara-suite.local` | `Demo@Ecommerce2024!` | Online catalog, storefront channels, pickup/delivery orders, ecommerce reports |
| Analytics Manager | `analytics-manager@demo.tijara-suite.local` | `Demo@Analytics2024!` | Dashboards, trends, reports, KPI history, owner analytics |
| Restaurant Operator | `restaurant@demo.tijara-suite.local` | `Demo@Restaurant2024!` | Dine-in, takeaway, pickup, kiosk, queue and kitchen tickets |
| Public Display | `public-display@demo.tijara-suite.local` | `Demo@Display2024!` | Public display route smoke testing; many display URLs are public |

## 4. First Login Checklist

1. Open the login URL and select database `tijara_dev` if prompted.
2. Enter the assigned email and password.
3. Confirm the main Odoo dashboard loads.
4. Use the app launcher/menu to open the assigned area: POS, Inventory, Tijara,
   Analytics, Restaurant, SaaS Control, or Accounting.
5. If the expected menu is missing, ask the tenant admin or platform admin to
   verify user groups and SaaS feature flags.

## 5. Role Responsibilities

### Platform Superadmin

Owns the platform-level configuration and production-readiness controls.

Primary tasks:

- Manage SaaS plans, feature flags, tenant readiness, and platform settings.
- Review protected release evidence, certification status, operations reports,
  and security/DevOps readiness notes.
- Confirm that production secrets, provider credentials, backups, monitoring,
  and incident runbooks are configured before a real customer launch.
- Keep demo/staging users separate from production users.

Daily checks:

- SaaS feature flags are correct for each tenant.
- Protected evidence bundles and release gates are current.
- No placeholder credentials are used outside local demo.
- Monitoring, backups, and restore drills are scheduled for production.

### Tenant Admin

Owns business setup for one company or tenant.

Primary tasks:

- Configure business details, branches, warehouses, POS settings, receipt
  profiles, users, payment methods, and allowed SaaS features.
- Enable vertical-specific workflows such as superstore, grocery, cosmetics,
  bakery, cafe, fast food, restaurant, pharmacy, cloth, garments, uniform,
  shoes, mobile shop, and electronics.
- Assign user permissions and review cashier/inventory/accounting activity.
- Maintain customer, supplier, product, tax, and price setup.

Setup checklist:

- Confirm company name, Urdu name, NTN/STRN, branch code, and receipt language.
- Configure B2C and B2B product prices.
- Configure GST on/off, delivery charge on/off, cafe service charge on/off,
  and cafe/restaurant card/cash tax policy.
- Configure receipt/invoice templates and return policy text.
- Configure POS sessions, cash shifts, payment methods, and barcode settings.
- Configure warehouses, racks, shelves, bins, and expiry tracking.
- Enable subscribed SaaS features such as B2B POS, queue display, customer
  display, ecommerce store, and promotion/menu/deal screens.

### Ecommerce Manager

Owns the public online store workflow.

Primary tasks:

- Manage Ecommerce > Storefront Channels.
- Publish products to the online catalog.
- Confirm B2C and B2B prices before promotions go live.
- Review online orders, payment status, delivery address, pickup code, and
  queue ticket handoff.
- Coordinate with inventory when online products are low stock.
- Coordinate with accounting before live payment provider activation.

Storefront setup workflow:

1. Open Tijara > Ecommerce > Storefront Channels.
2. Create or review the channel name, code, URL slug, website, warehouse, and
   stock location.
3. Enable B2C, B2B, guest checkout, pickup, store pickup, takeaway, delivery,
   courier, and payment methods according to the tenant plan.
4. Confirm the tenant plan has `ecommerce_store`; B2B online sales also need
   `b2b_sales`.
5. Open products and enable Publish on Tijara Ecommerce.
6. Confirm online sequence, featured flag, Urdu/English description, barcode,
   SKU, GST policy, B2C price, and B2B price.
7. Attach active promotions to the ecommerce channel when required.
8. Open the storefront route and test catalog search, cart, checkout, pickup,
   delivery, and queue ticket creation.

Online order workflow:

1. Customer adds items from the storefront.
2. Customer chooses B2C or B2B where enabled.
3. Customer selects pickup, delivery, store pickup, takeaway, courier, or dine
   in if the channel allows it.
4. System creates an Odoo sale order with the ecommerce channel, customer,
   payment method, charge-policy amounts, estimated GST, and payload snapshot.
5. Pickup/delivery orders create queue tickets when the queue SaaS feature is
   available.
6. Staff confirm stock, prepare the order, update queue status, collect or
   reconcile payment, and print invoice/receipt as needed.

Ecommerce smoke-test workflow:

1. Confirm the local/staging database has `tijara_ecommerce` installed and the
   `ecommerce_store` SaaS feature enabled.
2. Set `TIJARA_ECOMMERCE_SLUG=tijara-demo-web` for the seeded demo channel.
3. Use the ecommerce manager account for authenticated review:
   `ecommerce-manager@demo.tijara-suite.local`.
4. Run the ecommerce Playwright spec to verify catalog payloads, Urdu names,
   B2C/B2B prices, pickup checkout, delivery checkout, charge policy, sale
   order creation, and queue ticket handoff.
5. Regenerate screenshot guide evidence after checkout routes or storefront
   copy/layout changes.

### Cashier

Runs the counter POS for retail and wholesale customers.

Primary tasks:

- Open the assigned POS session.
- Scan products with barcode scanner or search manually.
- Select B2C or B2B selling mode when available.
- Add customer when required for B2B, refund, exchange, invoice, or loyalty.
- Apply line discounts or overall bill discount by percentage or amount.
- Collect payment and print or share receipt.
- Process refunds and exchanges using invoice barcode scan where available.

Checkout workflow:

1. Open POS.
2. Confirm cashier name, active session, and correct shop/branch.
3. Scan product barcode or select item from the product list.
4. Confirm quantity, price, discount, and tax.
5. Select customer if required.
6. For B2B sale, switch to B2B price mode before payment.
7. Add overall bill discount if approved.
8. Take payment.
9. Print receipt and close the order.

Keyboard-only counter workflow:

- Use barcode scanner input or type a product barcode/SKU/name, then press
  `Enter` to add the product when the POS screen is focused.
- Use `F2` to focus product search, `F4` for payment, and `F5` for receipt
  print.
- Use arrow keys to move between cart lines, `+`/`-` to adjust quantity, and
  `Delete`/`Backspace` to remove the selected line.
- Use `F7` to switch B2B/B2C pricing and `F8` to cycle dine-in, takeaway,
  pickup, and delivery service mode where enabled.

Bill discount rule:

- If percentage is entered, amount should update automatically.
- If amount is entered, percentage should update automatically.
- Always confirm manager approval for high-value discounts.

Refund and exchange workflow:

1. Open the refund/exchange screen.
2. Scan the invoice barcode or enter invoice/reference manually.
3. Confirm original order, date, customer, items, and payment method.
4. Select return reason.
5. For refund, choose returned items and refund amount.
6. For exchange, add replacement items and confirm price difference.
7. Ask manager approval when policy requires it.
8. Print refund/exchange receipt.

Cashier safety rules:

- Do not share login credentials.
- Do not leave a POS session unattended.
- Count cash drawer before and after shift.
- Escalate failed payments, suspicious refunds, and printer issues.

### Inventory Manager

Maintains stock quality, location accuracy, and bulk product data.

Primary tasks:

- Create and maintain products, barcodes, categories, B2C/B2B prices, units,
  expiry dates, and storage positions.
- Track warehouse, store, rack, shelf, bin, aisle, and placement.
- Review low-stock and expiry alerts.
- Import/export product and inventory data for bulk updates.
- Coordinate receiving, transfers, stock adjustments, and cycle counts.
- Print inventory barcode/QR labels in English, Urdu, or bilingual mode.

Product setup checklist:

- Product name and Urdu/local display name where needed.
- Barcode/QR code.
- Inventory label template when a product needs a specific Urdu or bilingual
  print layout.
- Category and vertical fields.
- B2C price and B2B price.
- Cost, vendor, tax, and unit of measure.
- Expiry tracking for pharmacy, grocery, bakery, and perishable items.
- Warehouse/store/rack/shelf/bin placement.
- Low-stock threshold and reorder quantity.

Low-stock workflow:

1. Open Inventory Intelligence.
2. Review low-stock alerts.
3. Check current stock, reserved stock, and incoming purchase orders.
4. Create replenishment request or purchase order.
5. Update alert notes after action.

Expiry workflow:

1. Open expiry alerts.
2. Filter by date, category, branch, or supplier.
3. Move near-expiry items to review, promotion, return, or wastage workflow.
4. Record action taken for audit.

Bulk import/export:

- Export current data before bulk changes.
- Use CSV templates where available.
- Validate barcode uniqueness.
- Import in small batches first.
- Recheck stock, price, and category after import.

### Vertical Catalog Manager

Maintains product and policy readiness for each business type.

Primary tasks:

- Tag products by vertical: superstore, grocery, cosmetics, cloth, garments,
  uniform, shoes, pharmacy, bakery, cafe, fast food, restaurant, mobile shop,
  electronics, and wholesale.
- Maintain separate B2C and B2B prices.
- Check that each vertical has the right unit, barcode, tax category, stock
  alert, and display-screen pricing.
- Coordinate tenant policy changes with the tenant admin before go-live.

Policy checklist:

- GST can be enabled or disabled at company level.
- Delivery charge can be enabled for any business where delivery is offered.
- Service charge applies only to cafe policy.
- Card 5% and cash 16% food payment tax applies only to cafe/restaurant policy.
- Restaurants and fast-food counters should confirm dine-in, takeaway, pickup,
  and delivery visibility before launch.

### Customer And Loyalty Manager

Maintains customer details, walk-in conversion, and loyalty programs.

Primary tasks:

- Review customer profiles, phone, email, CNIC/NTN/STRN where required.
- Keep walk-in, retail, wholesale, corporate, and supplier customer types clean.
- Maintain loyalty opt-in, loyalty number, tier, and points.
- Review B2B customer credit limits and customer history.

Loyalty workflow:

1. Open the customer profile.
2. Confirm customer type and contact details.
3. Enable loyalty opt-in where the customer agrees.
4. Assign or verify loyalty number and tier.
5. Review loyalty points after POS or kiosk orders.

### Accountant

Reviews financial records, invoices, settlements, refunds, disputes, and FBR
readiness evidence.

Primary tasks:

- Review invoices, payments, refunds, exchanges, settlements, and chargebacks.
- Monitor draft accounting actions from payment adapters.
- Review FBR invoice queue and submission status.
- Reconcile payment provider statements.
- Validate tax, accounts, journals, and audit records.

Daily checks:

- POS cash and digital payments match end-of-day records.
- Refunds and exchanges have approved reasons.
- Settlement batches are reconciled.
- Chargebacks/disputes have assigned owner and next action.
- FBR queue has no unexpected failed records.

Settlement workflow:

1. Open payment settlement batches.
2. Import or review provider statement.
3. Match provider transaction reference to POS/order/payment event.
4. Mark matched, partial, disputed, or failed.
5. Create draft accounting action where required.
6. Submit for finance approval.

FBR queue workflow:

1. Open FBR invoice queue.
2. Filter pending, failed, dry-run, or live-mode records.
3. Review invoice payload and business identifiers.
4. Retry only when provider credentials and endpoint are configured.
5. Keep dry-run evidence separate from live compliance evidence.

### Back Office Expense And Salary Manager

Runs non-POS office operations such as expenses, petty cash, delivery
settlements, and salary batches.

Primary tasks:

- Submit, approve, pay, and audit expense requests.
- Maintain receipt reference, vendor/employee, category, payment method, tax,
  and notes for each expense.
- Review salary batches, employee lines, gross pay, deductions, bonuses, and net
  payable.
- Keep monthly paid/unpaid status ready for owner and accountant review.

Expense workflow:

1. Open Back Office > Expenses.
2. Create or review an expense request.
3. Add category, vendor/employee, payment method, amount, tax, and receipt
   reference.
4. Submit for approval.
5. Manager approves, then marks paid after payment evidence is confirmed.

Salary workflow:

1. Open Back Office > Salaries.
2. Review the period start/end and employee salary lines.
3. Confirm gross, deduction, bonus, and net totals.
4. Approve the batch after manager review.
5. Mark paid after salary disbursement evidence is available.

### Restaurant Operator

Runs restaurant, bakery, and food-service operations.

Primary tasks:

- Manage dine-in, takeaway, pickup, and delivery orders.
- Use kiosk/self-order flow for customer ordering where enabled.
- Track queue tickets and kitchen status.
- Update menu, deals, and promotion display screens.
- Coordinate tables, service type, and order readiness.
- Confirm cafe/restaurant tax policy, delivery charge, and service charge rules
  before opening a live session.

Service workflow:

1. Select service type: dine-in, takeaway, pickup, or delivery.
2. For dine-in, assign table or service area.
3. Add menu items and modifiers.
4. Confirm order and send to kitchen queue.
5. Move status from waiting to preparing, ready, and called.
6. Close order after payment or pickup.

Kiosk workflow:

1. Confirm kiosk profile is enabled for the tenant.
2. Customer selects dine-in, takeaway, pickup, or delivery.
3. Customer chooses menu items and deals.
4. Customer confirms order.
5. Queue ticket is created.
6. Staff prepares and calls order.

Queue display workflow:

- Waiting means order is received.
- Preparing means kitchen or counter is working.
- Ready means order can be collected.
- Called means the customer has been notified.

### Display And Kiosk Operator

Maintains customer-facing screens and public routes.

Primary tasks:

- Open customer display, queue display, menu board, deals board, and promotion
  display routes.
- Confirm screens are on the correct tenant, branch, and profile.
- Keep browser full screen on display devices.
- Refresh screens after profile, promotion, or menu changes.

Display checklist:

- Customer display shows current cart lines, totals, and receipt context.
- Queue display shows latest ticket status.
- Menu screen shows correct branch menu.
- Deals screen shows active deals only.
- Promotion screen shows current campaign.
- No private admin data is visible on public display devices.

### Business Owner Or Manager

Uses dashboards, reports, and audit records to run the business.

Primary tasks:

- Review sales trends, margin, inventory movement, low stock, expiry, refunds,
  discounts, queue performance, and promotion performance.
- Compare B2C and B2B sales.
- Review daily cash and settlement status.
- Use analytics for branch, category, cashier, and vertical decisions.

Daily dashboard checklist:

- Total sales and order count.
- Cash, card, wallet, and other payment totals.
- Top-selling and slow-moving products.
- Low-stock and near-expiry items.
- Refunds, exchanges, voids, and high discounts.
- Queue wait time and restaurant order status.
- Promotion/deal performance.
- Back-office expenses, salary payable, delivery charges, service charges,
  card/cash food tax, loyalty movement, and vertical catalog performance.

## 6. SaaS Feature Flags

Some features should be enabled or disabled per tenant plan. Typical SaaS
controlled features include:

- B2B selling mode.
- Queue system and queue display.
- Customer display.
- Promotion display.
- Menu and deals display screens.
- Kiosk/self-ordering.
- Advanced analytics.
- Hardware bridge access.

If a screen is not available, check the tenant plan and feature flag before
assuming the user has a permission problem.

## 7. Hardware Usage

Supported integration foundation:

- Barcode scanner.
- QR code and barcode receipt scanning.
- Receipt printer.
- Invoice/receipt/inventory-label template printing in English, Urdu, or
  bilingual mode.
- Customer display.
- Cash drawer.
- Scale.
- CUPS/ESC-POS/ZPL readiness through the hardware bridge foundation.

Hardware checklist:

1. Confirm the device is connected to the local shop machine.
2. Confirm the hardware bridge is running if required.
3. Confirm the device profile is registered.
4. Run a test print/scan/display job.
5. Record certification result for real production devices.

Troubleshooting:

- If scanner does not work, test it in a text field first.
- If receipt does not print, check printer power, paper, queue, and bridge logs.
- If cash drawer does not open, confirm printer/drawer cable and command profile.
- If scale does not report weight, confirm serial/USB configuration.

## 8. Reports And Analytics

Use analytics to understand trends, history, and business performance.

Important reports:

- Daily sales summary.
- Cashier sales report.
- B2C versus B2B sales.
- Product/category performance.
- Inventory movement.
- Low-stock and expiry report.
- Refund/exchange report.
- Discount audit report.
- Queue and restaurant service report.
- Promotion/deal performance report.
- Payment settlement and dispute report.
- FBR queue readiness report.

Good reporting practice:

- Review operational dashboards daily.
- Export reports before major stock or price changes.
- Keep audit records for refunds, high discounts, and stock adjustments.
- Compare trends by branch, category, cashier, and service type.

## 9. Security Rules For All Users

- Use your own login only.
- Do not share passwords.
- Do not save demo passwords in production browsers.
- Lock the device when leaving the counter or office.
- Report suspicious refunds, discounts, failed payments, or admin changes.
- Use production secret managers for real deployments.
- Keep customer and payment data private.

## 10. Common Problems

| Problem | What To Check |
|---|---|
| Cannot log in | Correct database, email, password, and active user status |
| Menu is missing | User groups, SaaS feature flags, installed modules |
| POS will not open | POS config, open session, cashier permissions |
| Product not found | Barcode, product active status, category, POS availability |
| Wrong price | B2C/B2B mode, price list, product price, discount |
| Receipt does not print | Printer profile, hardware bridge, browser permissions, paper |
| Refund cannot find invoice | Invoice barcode, order reference, database, customer |
| Stock looks wrong | Warehouse/location filter, pending transfers, stock adjustments |
| Expiry alert missing | Expiry date, tracking settings, alert cron/configuration |
| Display screen empty | Public route, tenant feature flag, screen profile, active content |
| FBR submit fails | Adapter mode, credentials, endpoint, provider status, payload |

## 11. Local Demo Notes

The local environment is for development and demonstration:

- Local URL: `http://localhost:8069/web/login?db=tijara_dev`
- Local DB: `tijara_dev`
- Local services: Odoo, PostgreSQL, optional hardware bridge and monitoring.
- Demo credentials are in `docs/TEST_CREDENTIALS.csv`.
- Generated local secrets are ignored by git.
- Real production needs real passwords, provider credentials, backups,
  monitoring, hardware certification, and compliance testing.

## 12. Escalation Guide

Escalate to the tenant admin when:

- User permissions or menus are missing.
- Product, price, tax, or receipt configuration is wrong.
- POS session or cash shift is blocked.
- Discount, refund, or exchange needs approval.

Escalate to the platform superadmin when:

- SaaS feature flags or plans are wrong.
- Tenant provisioning, billing, or release evidence is blocked.
- Production monitoring, backups, secrets, or provider integrations fail.

Escalate to technical support when:

- Docker/Odoo services are down.
- Hardware bridge does not respond.
- Database, module upgrade, or schema errors appear.
- Browser E2E, security, load, or deployment checks fail.

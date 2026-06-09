# Tijara Suite Step-by-Step Visual User Guide

Version: 2026-06-09

Audience: platform owners, tenant admins, cashiers, inventory teams, ecommerce teams, accountants, restaurant operators, display/kiosk operators, and business managers.

This guide uses visual maps, workflow lanes, step cards, and quick checks so every user knows where to go, what to do, what success looks like, and when to escalate.

## Local Access

| Item | Value |
| --- | --- |
| Local URL | http://localhost:8069/web/login?db=tijara_dev |
| Database | tijara_dev |
| Credentials | docs/TEST_CREDENTIALS.csv |
| Start | TIJARA_DEV_INSTALL_SUITE=1 TIJARA_DEV_SEED_POS_DEMO=1 bash scripts/dev-start.sh |
| Stop | bash scripts/dev-stop.sh |
| Currency and tax | PKR with GST 18% after affected modules are upgraded |

## System Map

| Stage | What happens |
| --- | --- |
| 1. Configure | Company, users, roles, SaaS features |
| 2. Build catalog | Products, prices, taxes, stock locations |
| 3. Sell | POS, kiosk, B2C/B2B, restaurant modes |
| 4. Fulfill | Receipt, queue, delivery/pickup, hardware |
| 5. Control | Refunds, exchange, settlements, FBR queue |
| 6. Improve | Dashboards, reports, trends, alerts |

For architecture, module, UML, activity, deployment, POS, ecommerce, kiosk,
offline, hardware, tenant, analytics, and release diagrams, use
`docs/DIAGRAMS.md` as the canonical visual design pack.

## Role Map

| Role | Open these areas | Primary work |
| --- | --- | --- |
| Platform superadmin | SaaS Control, Deploy, Evidence | Plans, tenants, feature flags, production readiness |
| Tenant admin | Tijara, Settings, POS, Inventory | Company setup, users, branches, warehouses, receipts |
| Cashier | Point of Sale, Refunds | Checkout, B2C/B2B sales, discounts, receipt print, refund/exchange |
| Inventory manager | Inventory, Inventory Intelligence | Products, stock, racks, shelves, low-stock and expiry alerts |
| Accountant | Accounting, Settlements, FBR Queue | Invoices, payments, refunds, settlements, tax review |
| Restaurant operator | Restaurant, POS, Kiosk, Queue | Dine-in, takeaway, pickup, kitchen status, order calling |
| Ecommerce manager | Ecommerce, Delivery Providers, Delivery Operations, Online Orders | Storefront setup, catalog publishing, tracking, account order history, saved addresses, portal returns/exchanges, retry/SLA exceptions, delivery reconciliation, delivery labels/manifests/webhooks, pickup/delivery handoff |
| Display/kiosk operator | Display Screens, Public Routes | Customer display, queue, menu, deals, promotion screens |
| Business owner/manager | Analytics, Reports, Dashboards | Sales trends, margins, inventory health, discount and refund audit |

## Feature Control Map

| Function | Main user | Control | Business purpose |
| --- | --- | --- | --- |
| POS checkout | Cashier | Core | Counter sales, payment, receipt |
| B2B selling | Cashier/admin | SaaS flag | Wholesale pricing and customer handling |
| Queue system | Restaurant/display | SaaS flag | Waiting/preparing/ready/called flow |
| Customer display | Cashier/display | SaaS flag | Live order lines and totals |
| Promotion/menu/deals screens | Display operator | SaaS flag | Public campaigns and menus |
| Kiosk | Restaurant/display | SaaS flag | Self-ordering route |
| Inventory intelligence | Inventory manager | SaaS flag | Low stock, expiry, placement |
| Analytics/reporting | Owner/manager | SaaS flag | Trends, dashboards, KPIs |
| Hardware bridge | Admin/support | Plan/config | Printers, scanners, drawer, scale |
| FBR queue | Accountant/admin | Config/provider | Invoice compliance readiness |

Pakistan default: training/demo data should use PKR and GST 18% after the affected modules are upgraded. Production tax policy still needs owner and compliance sign-off.

## First Login And Navigation

| Owner | Primary screen | Success signal |
| --- | --- | --- |
| All users | Odoo login and app launcher | Correct dashboard, correct menus, no shared credentials. |

Visual lane:

| Lane | Step |
| --- | --- |
| Open URL | Step 1 |
| Choose database | Step 2 |
| Login | Step 3 |
| Open app | Step 4 |
| Confirm menu | Step 5 |

Steps:

| Step | Action | Visual check |
| --- | --- | --- |
| 1 | Open the local or tenant URL. | Use the assigned database. |
| 2 | Enter your assigned email and password. | Use only your own login. |
| 3 | Confirm the Odoo dashboard loads. | If it fails, check active user status. |
| 4 | Open the assigned app area. | Menus depend on role and SaaS flags. |
| 5 | Start daily work from the role checklist. | Escalate missing menus to tenant admin. |

## Tenant Setup

| Owner | Primary screen | Success signal |
| --- | --- | --- |
| Tenant admin | Tijara / Settings / Company / POS Configuration | Business can sell, print, track stock, and control subscribed features. |

Visual lane:

| Lane | Step |
| --- | --- |
| Company | Step 1 |
| Branches | Step 2 |
| Users | Step 3 |
| POS | Step 4 |
| Receipts | Step 5 |
| Features | Step 6 |

Steps:

| Step | Action | Visual check |
| --- | --- | --- |
| 1 | Set company name, Pakistan identifiers, Urdu name, branch code. | Confirm country/currency are Pakistan/PKR. |
| 2 | Create users and assign role groups. | Cashier sees POS; inventory sees stock menus. |
| 3 | Configure warehouses, locations, racks, shelves, and bins. | Inventory alerts can locate items. |
| 4 | Configure POS sessions, payment methods, tax, and cash shift rules. | Cashier can open a session. |
| 5 | Choose invoice/receipt template and return policy. | Receipt preview has tax and barcode. |
| 6 | Enable subscribed SaaS features. | B2B, queue, display, kiosk appear only when enabled. |

## Product And Price Setup

| Owner | Primary screen | Success signal |
| --- | --- | --- |
| Inventory manager / tenant admin | Products and Inventory Intelligence | Product sells in POS with correct price, tax, barcode, and stock placement. |

Visual lane:

| Lane | Step |
| --- | --- |
| Product | Step 1 |
| Barcode | Step 2 |
| Prices | Step 3 |
| Tax | Step 4 |
| Location | Step 5 |
| Alerts | Step 6 |

Steps:

| Step | Action | Visual check |
| --- | --- | --- |
| 1 | Create product with barcode, SKU, Urdu/local name, category. | Barcode scanner can find it. |
| 2 | Enter B2C retail price and B2B trade price. | POS can switch audience pricing. |
| 3 | Confirm GST 18% or correct product tax category. | Totals display PKR and tax correctly. |
| 4 | Set warehouse, store, aisle, rack, shelf, bin. | Staff can locate stock. |
| 5 | Set low-stock threshold, reorder quantity, expiry fields. | Alerts are meaningful. |
| 6 | Export before bulk changes and import in small batches. | Rollback is possible if data is wrong. |

## POS Checkout: B2C And B2B

| Owner | Primary screen | Success signal |
| --- | --- | --- |
| Cashier | Point of Sale | Paid order, correct customer type, correct tax, correct receipt. |

Visual lane:

| Lane | Step |
| --- | --- |
| Open session | Step 1 |
| Scan items | Step 2 |
| B2C/B2B | Step 3 |
| Discount | Step 4 |
| Payment | Step 5 |
| Receipt | Step 6 |

Steps:

| Step | Action | Visual check |
| --- | --- | --- |
| 1 | Open POS and confirm active session, cashier, branch. | Wrong branch means wrong stock and cash. |
| 2 | Scan barcode or search product manually. | Quantity and product name are visible. |
| 3 | Select B2C or B2B mode when sale type changes. | Existing lines reprice when supported. |
| 4 | Apply line discount or bill discount by percent/amount. | Amount and percent stay synchronized. |
| 5 | Take payment and confirm method. | Cash/card/wallet totals are correct. |
| 6 | Print or share receipt. | Receipt shows PKR, GST, barcode/QR, return policy. |

## Refund And Exchange

| Owner | Primary screen | Success signal |
| --- | --- | --- |
| Cashier / manager | Tijara > Retail Operations > Refunds and Exchanges | Clean audit record, correct stock effect, customer receives proof. |

Visual lane:

| Lane | Step |
| --- | --- |
| Scan invoice | Step 1 |
| Verify sale | Step 2 |
| Reason | Step 3 |
| Items | Step 4 |
| Approval | Step 5 |
| Receipt | Step 6 |

Steps:

| Step | Action | Visual check |
| --- | --- | --- |
| 1 | Open refund/exchange and scan invoice barcode or QR. | Order/invoice is matched. |
| 2 | Confirm customer, original sale, payment, and item list. | Wrong invoice must not continue. |
| 3 | Choose refund or exchange and select returned items. | Stock effect is clear. |
| 4 | Add replacement items for exchange. | Price difference is calculated. |
| 5 | Request manager approval where policy requires it. | High-value or suspicious cases are reviewed. |
| 6 | Print refund/exchange receipt. | Audit trail has reason, user, and reference. |

## Restaurant Dine-In, Takeaway, Pickup

| Owner | Primary screen | Success signal |
| --- | --- | --- |
| Restaurant operator | Restaurant POS, service profile, queue | Order moves through service status without losing payment or queue context. |

Visual lane:

| Lane | Step |
| --- | --- |
| Service type | Step 1 |
| Table/pickup | Step 2 |
| Menu | Step 3 |
| Kitchen | Step 4 |
| Ready | Step 5 |
| Close | Step 6 |

Steps:

| Step | Action | Visual check |
| --- | --- | --- |
| 1 | Select dine-in, takeaway, or pickup. | Service mode prints and displays correctly. |
| 2 | Assign table/service area for dine-in or pickup code for pickup. | Staff can route the order. |
| 3 | Add menu items, modifiers, and deals. | Customer sees correct order. |
| 4 | Send order to kitchen/counter queue. | Queue ticket is waiting/preparing. |
| 5 | Move ticket to ready and called. | Customer display/queue updates. |
| 6 | Close order after payment or pickup. | Sales and queue metrics are complete. |

## Kiosk Self-Ordering

| Owner | Primary screen | Success signal |
| --- | --- | --- |
| Customer with operator support | Public kiosk route | Self-order exists, queue ticket exists, payment status is clear. |

Visual lane:

| Lane | Step |
| --- | --- |
| Open kiosk | Step 1 |
| Service type | Step 2 |
| Items | Step 3 |
| Confirm | Step 4 |
| Queue | Step 5 |
| Payment | Step 6 |

Steps:

| Step | Action | Visual check |
| --- | --- | --- |
| 1 | Operator opens kiosk route full screen. | Correct tenant/branch profile is active. |
| 2 | Customer chooses dine-in, takeaway, or pickup. | Allowed choices follow profile settings. |
| 3 | Customer selects menu items and deals. | Prices display in PKR. |
| 4 | Customer confirms order. | Queue ticket is created. |
| 5 | Staff prepares and calls order. | Queue display changes status. |
| 6 | Payment is recorded at counter or terminal path. | No unpaid order is treated as paid. |

## Customer Display, Queue, Menu, Deals, Promotion Screens

| Owner | Primary screen | Success signal |
| --- | --- | --- |
| Display/kiosk operator | Public display routes | Display shows current public information for the right branch. |

Visual lane:

| Lane | Step |
| --- | --- |
| Profile | Step 1 |
| Route | Step 2 |
| Full screen | Step 3 |
| Live state | Step 4 |
| Refresh | Step 5 |
| Privacy | Step 6 |

Steps:

| Step | Action | Visual check |
| --- | --- | --- |
| 1 | Choose the correct display screen profile. | Tenant, branch, language, and price mode match. |
| 2 | Open public display route on target device. | Screen loads without admin login when designed public. |
| 3 | Use full-screen browser mode. | No address bar distracts customers. |
| 4 | Confirm live order/queue/menu/deal state. | Wrong data means wrong profile or feature flag. |
| 5 | Refresh after menu/promotion changes. | Customer view stays current. |
| 6 | Verify no private admin data is visible. | Public screens remain safe. |

## Inventory Alerts And Stock Placement

| Owner | Primary screen | Success signal |
| --- | --- | --- |
| Inventory manager | Inventory Intelligence | No blind stockouts, no missed expiry risk, stock location is traceable. |

Visual lane:

| Lane | Step |
| --- | --- |
| Stock | Step 1 |
| Low alert | Step 2 |
| Expiry | Step 3 |
| Placement | Step 4 |
| Action | Step 5 |
| Audit | Step 6 |

Steps:

| Step | Action | Visual check |
| --- | --- | --- |
| 1 | Review low-stock and critical-stock alerts. | Prioritize items below reorder level. |
| 2 | Open expiry alerts for pharmacy/grocery/bakery/perishables. | Near-expiry stock is visible. |
| 3 | Check warehouse, store, rack, shelf, bin, aisle. | Physical location matches system. |
| 4 | Create purchase request, transfer, adjustment, promotion, or wastage action. | Action matches business rule. |
| 5 | Record notes and close alert when resolved. | History explains the decision. |

## Bulk Import And Export

| Owner | Primary screen | Success signal |
| --- | --- | --- |
| Tenant admin / inventory manager | Bulk Import / Export | Bulk changes are controlled, reviewed, and reversible. |

Visual lane:

| Lane | Step |
| --- | --- |
| Export | Step 1 |
| Edit CSV | Step 2 |
| Small batch | Step 3 |
| Import | Step 4 |
| Validate | Step 5 |
| Archive | Step 6 |

Steps:

| Step | Action | Visual check |
| --- | --- | --- |
| 1 | Export current data or template first. | You have a rollback reference. |
| 2 | Edit products, prices, stock, contacts, templates, hardware, locations, promotions. | Use exact column names. |
| 3 | Import a small test batch. | Catch barcode/category/tax mistakes early. |
| 4 | Run full import. | Processed count and errors are reviewed. |
| 5 | Recheck products, stock, prices, and reports. | System matches business records. |
| 6 | Archive CSV and result file. | Audit trail is preserved. |

## Hardware: Scanner, Printer, Drawer, Scale, Display

| Owner | Primary screen | Success signal |
| --- | --- | --- |
| Tenant admin / technical support | Hardware Devices and local hardware bridge | Devices are registered, tested, assigned, and auditable. |

Visual lane:

| Lane | Step |
| --- | --- |
| Register | Step 1 |
| Configure | Step 2 |
| Health | Step 3 |
| Test | Step 4 |
| Certify | Step 5 |
| Operate | Step 6 |

Steps:

| Step | Action | Visual check |
| --- | --- | --- |
| 1 | Register hardware device with type and code. | Device appears in configuration. |
| 2 | Set connection type: browser bridge, USB, serial, network, CUPS, ESC/POS, ZPL. | Required fields are complete. |
| 3 | Run device configuration test. | Status becomes ready. |
| 4 | Run bridge health and test job for bridge devices. | Job id and response are stored. |
| 5 | Record physical certification for real device model. | Production evidence exists. |
| 6 | Assign printer/display to POS or receipt profile. | Cashier workflow uses correct device. |

## Reports, Dashboards, Analytics

| Owner | Primary screen | Success signal |
| --- | --- | --- |
| Business owner / manager | Analytics dashboards and reports | Owner can see performance, risk, and action items in one routine. |

Visual lane:

| Lane | Step |
| --- | --- |
| Daily sales | Step 1 |
| Payments | Step 2 |
| Inventory | Step 3 |
| Refunds | Step 4 |
| Queue | Step 5 |
| Trends | Step 6 |

Steps:

| Step | Action | Visual check |
| --- | --- | --- |
| 1 | Open daily sales and cashier summary. | Sales/order count match day-end. |
| 2 | Review payment totals and settlement status. | Cash/card/wallet differences are clear. |
| 3 | Check top sellers, slow movers, low stock, near expiry. | Operational action is visible. |
| 4 | Review refunds, exchanges, voids, discounts. | Approvals and suspicious activity are visible. |
| 5 | Check queue and restaurant performance. | Wait time and pickup status are visible. |
| 6 | Compare trend by branch, category, cashier, B2C/B2B. | Business decisions use history, not guesswork. |

## SaaS Feature Flags And Tenant Plans

| Owner | Primary screen | Success signal |
| --- | --- | --- |
| Platform superadmin / tenant admin | SaaS Control | Tenant gets exactly the features they are subscribed for. |

Visual lane:

| Lane | Step |
| --- | --- |
| Plan | Step 1 |
| Subscription | Step 2 |
| Flags | Step 3 |
| Enforce | Step 4 |
| Verify | Step 5 |
| Audit | Step 6 |

Steps:

| Step | Action | Visual check |
| --- | --- | --- |
| 1 | Choose plan and tenant subscription. | Tenant has correct package. |
| 2 | Enable feature flags such as B2B, queue, customer display, promotion display, kiosk, analytics. | Only paid/allowed features appear. |
| 3 | Turn runtime enforcement on when ready. | Blocked features cannot be used accidentally. |
| 4 | Verify menus and public routes. | Tenant sees only subscribed capabilities. |
| 5 | Record billing/provisioning/evidence status. | Admin console stays audit-ready. |

## Payments, Settlements, Chargebacks

| Owner | Primary screen | Success signal |
| --- | --- | --- |
| Accountant | Payment settlements, disputes, accounting actions | Payments reconcile and exceptions have owners. |

Visual lane:

| Lane | Step |
| --- | --- |
| Import | Step 1 |
| Match | Step 2 |
| Review | Step 3 |
| Dispute | Step 4 |
| Approve | Step 5 |
| Post | Step 6 |

Steps:

| Step | Action | Visual check |
| --- | --- | --- |
| 1 | Import or receive provider settlement batch. | Provider reference is present. |
| 2 | Match provider event to POS order/payment. | Matched, partial, failed, or disputed status is clear. |
| 3 | Review provider fee and net amount. | Accounting action can be drafted. |
| 4 | Assign chargebacks/disputes with owner and next action. | No unresolved money movement is hidden. |
| 5 | Approve draft accounting action when policy allows. | Finance has sign-off trail. |

## FBR Queue And Tax Evidence

| Owner | Primary screen | Success signal |
| --- | --- | --- |
| Accountant / platform superadmin | FBR invoice queue | FBR readiness is auditable; live compliance still requires certified provider sign-off. |

Visual lane:

| Lane | Step |
| --- | --- |
| Invoice | Step 1 |
| Queue | Step 2 |
| Dry run | Step 3 |
| Provider | Step 4 |
| Retry | Step 5 |
| Evidence | Step 6 |

Steps:

| Step | Action | Visual check |
| --- | --- | --- |
| 1 | Open FBR queue and filter pending/failed/dry-run/live. | Queue status is visible. |
| 2 | Review invoice payload, NTN/STRN, branch, POS id. | Identifiers are correct. |
| 3 | Use dry-run evidence until certified provider credentials exist. | Do not confuse dry-run with compliance. |
| 4 | Retry only after endpoint and credentials are confirmed. | Failures are not blindly retried. |
| 5 | Keep provider response and queue audit. | Tax/compliance owner can review. |

## Offline POS Capture And Conflict Review

| Owner | Primary screen | Success signal |
| --- | --- | --- |
| Cashier / manager / technical support | Offline POS Queue and conflict review | Internet issues do not silently lose sales or create uncontrolled duplicates. |

Visual lane:

| Lane | Step |
| --- | --- |
| Capture | Step 1 |
| Replay | Step 2 |
| Duplicate | Step 3 |
| Conflict | Step 4 |
| Action | Step 5 |
| Audit | Step 6 |

Steps:

| Step | Action | Visual check |
| --- | --- | --- |
| 1 | Offline browser capture stores order locally or submits queued payload. | Order has source device and uid. |
| 2 | Replay creates POS order when online. | Duplicate checks use source uid. |
| 3 | Open conflict review for failed or duplicate orders. | Manager sees error and payload. |
| 4 | Retry, cancel, merge, mark duplicate, or replay. | Action matches business evidence. |
| 5 | Review replay audit report. | Offline selling is traceable. |

## Security, Troubleshooting, Escalation

| Owner | Primary screen | Success signal |
| --- | --- | --- |
| All users | All areas | Users solve common issues quickly and escalate risky issues cleanly. |

Visual lane:

| Lane | Step |
| --- | --- |
| Own login | Step 1 |
| Check role | Step 2 |
| Check feature | Step 3 |
| Check device | Step 4 |
| Escalate | Step 5 |
| Record | Step 6 |

Steps:

| Step | Action | Visual check |
| --- | --- | --- |
| 1 | Use your own login; never share passwords. | Audit records remain trustworthy. |
| 2 | If a menu is missing, check user group and feature flag. | Permission and SaaS issues are separated. |
| 3 | If price/tax is wrong, check B2C/B2B mode, product price, GST/tax, discount. | Receipt total is explainable. |
| 4 | If hardware fails, test power, paper, browser permissions, bridge health. | Device issue is isolated. |
| 5 | Escalate to tenant admin, platform admin, or technical support. | Right owner handles the fix. |
| 6 | Record incident notes for refunds, high discounts, failed payments, security events. | Business has a trail. |

## Troubleshooting Wall

| Problem | What to check first | Escalate to |
| --- | --- | --- |
| Cannot log in | Database, email, password, active user, browser session | Tenant admin |
| POS will not open | POS config, open session, cashier group, payment method | Tenant admin |
| Amount shows USD | Company currency, module upgrade, posted accounting entries | Tenant admin/platform admin |
| GST missing | Product tax, standard GST 18% tax, module upgrade, fiscal settings | Accountant/tenant admin |
| Wrong B2B/B2C price | Sale mode, product B2C/B2B fields, pricelist, discount | Tenant admin |
| Receipt does not print | Printer profile, paper, bridge health, browser permissions | Technical support |
| Scanner not finding product | Barcode field, product active, POS availability, scanner wedge mode | Inventory manager |
| Refund cannot find invoice | Barcode prefix, order reference, database, customer | Cashier/manager |
| Display route empty | Feature flag, screen profile, active content, slug | Display operator |
| FBR queue fails | Adapter mode, credentials, endpoint, provider status | Accountant/platform admin |

Escalation rule: tenant admin owns users, menus, products, taxes, POS setup, discounts, and refunds. Platform admin owns SaaS plans, tenants, protected evidence, provider readiness, and production controls. Technical support owns Docker/Odoo, hardware bridge, database/module errors, and deployment checks.

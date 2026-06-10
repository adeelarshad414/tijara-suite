# Tijara Suite Customer Walkthrough Video Script

This script supports the generated customer-facing sales and training video:

- Video output: `docs/PRODUCT_DEMO_CUSTOMER.webm`
- Voiceover output: `docs/video-clips/customer-demo/customer-demo-voiceover.wav`
- Generator: `python3 scripts/generate_customer_demo_video.py`
- Shortcut: `make customer-demo-video`
- Default encoder: `ffmpeg` when available, with browser recorder fallback

The generated media files are intentionally ignored by git. Commit the
repeatable script and this source script, then attach the generated WebM to a
release, customer handoff package, or sales team drive.

## Audience

Use this video for first customer calls, sales qualification, demo booking,
pilot onboarding, and internal sales training.

Primary buyer personas:

- Business owner or director
- Store, branch, or restaurant manager
- Finance or accounts lead
- Inventory or purchase manager
- IT, DevOps, or implementation lead

Primary user personas shown:

- Platform superadmin
- Tenant admin
- Cashier
- Inventory manager
- Accountant
- Expense manager
- Salary manager
- Loyalty manager
- Promotion manager
- Ecommerce manager
- Analytics manager
- Restaurant operator
- Public display/kiosk operator
- Business manager or owner
- DevOps/support operator

## Sales Positioning

Tijara Suite is a Pakistan-focused, open-source-first business suite built on
Odoo Community. It helps retailers, restaurants, and multi-branch businesses run
POS, inventory, ecommerce, back office, displays, analytics, SaaS features,
hardware readiness, FBR readiness, and payment provider readiness from one
platform.

The sales promise should stay honest:

- The suite is strong for pilots, demos, module development, and staged
  implementation.
- Real production go-live still requires certified hardware, FBR provider
  credentials, PSP certification, courier sign-off, protected staging evidence,
  monitoring, backups, restore drills, security checks, and load testing.
- Dummy and assumed integrations are clearly marked as demo or readiness mode.

## Scene 1: Customer Sales Walkthrough

**Visual**: Login and onboarding screen.

**Purpose**: Establish that this is a Pakistan-focused enterprise suite, not a
generic POS.

**Voiceover**:
"Welcome to Tijara Suite, a Pakistan-focused business platform built on Odoo
Community. This customer walkthrough shows how one suite can cover point of
sale, inventory, restaurant service, ecommerce, back office, analytics, SaaS
controls, and hardware readiness for real Pakistani businesses."

**Sales notes**:

- Mention PKR, GST, Urdu/English print support, barcode workflows, and local
  business verticals early.
- Position the product as modular: start with one vertical, then expand.

## Scene 2: Persona-Led Training

**Visual**: Role-based app shell.

**Purpose**: Help the sales team explain the application through user roles.

**Voiceover**:
"The easiest way to sell and train Tijara is by persona. Owners look at trends
and margins, cashiers run fast checkout, inventory teams control stock,
accountants review payments and taxes, restaurant teams manage queues, and
DevOps teams run the release and monitoring process."

**Sales notes**:

- Tie each buyer concern to a persona.
- For customer demos, open the relevant guide and credentials after the video:
  `docs/USER_GUIDE_ALL_USERS.md` and `docs/TEST_CREDENTIALS.csv`.

## Scene 3: POS Cashier Workflow

**Visual**: POS and customer display.

**Purpose**: Show the counter value proposition.

**Voiceover**:
"At the counter, cashiers can sell to walk-in retail customers or wholesale B2B
customers, scan products, use keyboard shortcuts, apply a discount by amount or
percentage, print receipts, and process refunds or exchanges by scanning the
invoice barcode."

**Sales notes**:

- Mention touch, keyboard, scanner, and Enter-friendly workflows.
- Mention separate B2B and B2C pricing.
- Mention receipt/invoice template customization and Urdu/English printing.

## Scene 4: Restaurant, Cafe, And Bakery

**Visual**: Kiosk ordering.

**Purpose**: Show restaurant and food-service coverage.

**Voiceover**:
"For restaurants, cafes, fast food, and bakeries, Tijara supports dine-in,
takeaway, pickup, and delivery. Customers can use a kiosk, managers can publish
menu and deal screens, and the business can control GST, card and cash tax
rules, service charges, and delivery charges."

**Sales notes**:

- For restaurants and cafes, highlight dine-in, takeaway, pickup, delivery,
  queue, kiosk, service charge, and tax policy.
- For bakeries, highlight perishable stock, production batch foundations, menu
  boards, deals, and pickup.

## Scene 5: Queue And Display Screens

**Visual**: Queue display.

**Purpose**: Explain customer-facing screens as SaaS features.

**Voiceover**:
"Tijara also gives businesses customer-facing screens. A queue display keeps
restaurant and pickup flow clear, a customer display shows cart and total
information, and promotion, menu, and deal boards help sell more from the same
counter."

**Sales notes**:

- B2B, queue display, customer display, promotion display, kiosk, and ecommerce
  can be sold as plan-controlled features.
- These features are useful for restaurants, cafes, superstores, bakeries, and
  high-volume pickup counters.

## Scene 6: Inventory And Vertical Control

**Visual**: Business policy settings.

**Purpose**: Show that one suite adapts to many business types.

**Voiceover**:
"Inventory managers can control products, prices, stock, expiry, and locations
such as warehouse, rack, shelf, bin, and aisle. Tenant admins can also manage
business policies for GST, service charges, delivery fees, cafe rules,
restaurant rules, and vertical-specific workflows."

**Sales notes**:

- Mention supported verticals: superstore, grocery, pharmacy, cosmetics, cloth,
  garments, uniforms, shoes, mobile, electronics, bakery, cafe, fast food, and
  restaurant.
- Mention import/export for bulk product, price, contact, stock, and device
  records.

## Scene 7: Back Office Operations

**Visual**: Expense management.

**Purpose**: Show that the platform is more than POS.

**Voiceover**:
"Back-office users can manage expenses, salaries, purchases, procurement,
suppliers, and customer records. The goal is to give owners a practical
operating system where every record can feed reports, approvals, and audit
history."

**Sales notes**:

- Use this scene for owner and manager buyers.
- Connect expenses, purchase, procurement, suppliers, customers, reports, and
  audit history to daily business control.

## Scene 8: Salary And People Cost

**Visual**: Salary management.

**Purpose**: Show operating cost visibility.

**Voiceover**:
"For growing businesses, operating cost matters. Tijara includes salary
management foundations so staff-related costs can sit beside expenses, sales,
purchase, inventory, and branch performance in one operating view."

**Sales notes**:

- Keep the claim clear as a foundation for salary records and reporting.
- Do not overstate full HR/payroll compliance until implemented for a specific
  customer.

## Scene 9: Ecommerce And Delivery

**Visual**: Ecommerce storefront.

**Purpose**: Show online selling connected to store operations.

**Voiceover**:
"Tijara is not only a counter system. It includes ecommerce storefront and
customer account foundations, saved addresses, order history, return requests,
Pakistan courier profiles, in-house rider support, delivery retries, SLA
exceptions, and delivery reconciliation."

**Sales notes**:

- Mention customer portal and order history.
- Mention Pakistan courier readiness and in-house rider workflows.
- Make clear that live provider tokens and certification are separate go-live
  tasks.

## Scene 10: Customers, Loyalty, Promotions, Menus, And Deals

**Visual**: Loyalty customer records.

**Purpose**: Explain growth and customer retention features.

**Voiceover**:
"For growth, Tijara connects customer records, loyalty foundations, promotions,
deals, menus, and display screens. A business can start simple with walk-in
sales, then add loyalty, campaigns, and display upsell features as the plan
grows."

**Sales notes**:

- Use this for retail, restaurants, bakeries, cosmetics, and fashion businesses.
- Connect loyalty and promotions to repeat purchase and basket size.

## Scene 11: Analytics And Dashboards

**Visual**: Analytics dashboard.

**Purpose**: Show management value.

**Voiceover**:
"Owners need more than bills. Tijara tracks trends, history, charts, reports,
and dashboards for sales, inventory, expenses, salary liability, loyalty,
verticals, delivery, payments, FBR queues, hardware readiness, and DevOps
operations."

**Sales notes**:

- Speak in business outcomes: better stock decisions, fewer missed expiry
  issues, better branch control, clearer cash and card visibility.
- Mention Grafana for DevOps and operational monitoring when IT buyers are
  present.

## Scene 12: Enterprise Readiness

**Visual**: Payment and integration readiness.

**Purpose**: Be credible about production requirements.

**Voiceover**:
"For enterprise delivery, Tijara includes SaaS feature flags, tenant
provisioning foundations, monitoring dashboards, backups, release gates,
protected evidence, hardware bridge readiness, FBR queue readiness, and PSP
adapter readiness. For production go-live, real devices, provider credentials,
and certified compliance evidence are still required."

**Sales notes**:

- This scene protects trust. It says what exists and what still needs real
  certification.
- Use it before discussing implementation timelines, FBR, PSPs, hardware,
  couriers, and deployment responsibilities.

## Scene 13: Sales Close

**Visual**: Promotions management.

**Purpose**: Give the sales team a clear next step.

**Voiceover**:
"Tijara Suite gives the sales team a clear customer story. Start with one
vertical, demonstrate the key persona workflows, enable the right SaaS features,
and move from pilot to production only after the needed hardware, payment, FBR,
courier, security, and infrastructure evidence is complete."

**Sales notes**:

- Recommend a pilot vertical and one branch first.
- Pick two or three workflows to demonstrate live after the video.
- Agree the production certification checklist before promising go-live dates.

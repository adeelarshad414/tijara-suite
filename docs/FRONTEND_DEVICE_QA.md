# Frontend Device QA

Tijara Suite must be touch-friendly, responsive, cross-device, and
cross-browser. This standard applies to POS, kiosk, customer display, queue
display, promotion/deals display, menu display, and back-office workflows.

## Interaction Standard

- Primary actions must be usable on touch screens with a minimum 44 px target.
- Coarse-pointer devices should use 48 px targets for cashier-critical actions.
- Workflows must not depend on hover-only controls.
- Barcode scanner input must work as keyboard-wedge input without stealing focus
  from payment, search, or quantity controls.
- Numeric entry must be usable from touch keyboards and physical keyboards.
- Critical cashier flows must avoid horizontal scrolling.
- Dialogs, drawers, and popovers must fit at 360 px width.
- Text must wrap cleanly and must not overlap buttons, price fields, order
  lines, or receipt totals.
- Urdu and right-to-left surfaces must be verified wherever Urdu text is shown.

## Responsive Viewports

Validate these widths before release:

- 360 x 740: small Android phone.
- 390 x 844: common iPhone viewport.
- 768 x 1024: tablet portrait.
- 1024 x 768: tablet landscape and POS terminals.
- 1366 x 768: common laptop and counter terminal.
- 1920 x 1080: large display, customer display, and menu board.

## Browser Matrix

Pilot-ready releases must pass smoke tests on:

- Desktop Chrome current stable.
- Desktop Edge current stable.
- Desktop Firefox current stable.
- Desktop Safari current and previous major where practical.
- Android Chrome current stable.
- iOS Safari current and previous major where practical.
- Kiosk Chromium or Chrome where the business uses locked-down terminals.

## Surface-Specific Acceptance

POS:

- Product grid, search, cart, quantity, discount, customer, payment, refund, and
  exchange actions are reachable by touch.
- B2B/B2C mode and dine-in/takeaway/pickup controls are visible without layout
  collisions.
- Receipt, QR, barcode, and customer-facing totals are readable.
- Browser POS receipt screens render configured Tijara receipt profile content,
  including Urdu text and custom body tokens, without breaking checkout.
- Browser-bridge device actions can health-check the local bridge and submit a
  signed dry-run job without exposing Odoo database credentials.
- When a bridge receipt printer is assigned to POS configuration, the POS
  receipt print action submits the rendered receipt payload to the bridge and
  the order records the bridge print status and job id.

Kiosk:

- Category, menu/deal, cart, customer details, pickup code, and payment steps
  are touch-first.
- Idle and error states are visible from customer distance.
- No keyboard is required except for optional customer input.

Customer Display:

- Product lines, totals, discount, tax, QR/FBR status, and payment status remain
  legible at counter-display distance.
- Display does not expose back-office navigation or admin controls.

Queue and Promotion Displays:

- Ready/in-progress order numbers are legible at 1920 x 1080.
- Promotion, menu, and deals content can rotate without causing layout jumps.
- Screens remain usable when the browser is full-screen kiosk mode.

Back Office:

- Forms remain usable on tablet widths.
- Tables/list views have readable columns and do not hide primary actions.
- Admin workflows remain keyboard accessible.

## Automated QA Direction

Run the staging/protected browser matrix with:

```bash
make browser-e2e-matrix
```

The default matrix covers `chromium-desktop`, `firefox-desktop`,
`webkit-desktop`, `mobile-touch`, and `tablet-touch`. The matrix must be run
against seeded staging credentials and a real staging URL before production
sign-off. Use `TIJARA_BROWSER_E2E_PROJECTS="chromium-desktop mobile-touch"` only
for fast debugging, not final release approval.

Playwright or browser tests should cover:

- Login and back-office navigation.
- POS load and product search.
- POS checkout to receipt with Tijara receipt profile rendering.
- Hardware bridge health and signed dry-run job submission.
- POS receipt print-to-bridge submission and bridge print audit fields.
- B2B/B2C price mode switching.
- Dine-in/takeaway/pickup selection.
- Kiosk order creation.
- Queue display update.
- Customer display totals update.
- Refund and exchange workflow.
- Urdu receipt/display rendering.

The `tijara_pos_experience` module includes
`static/src/scss/touch_responsive.scss` as the shared touch baseline for future
screens.

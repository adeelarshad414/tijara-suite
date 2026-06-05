# Browser E2E

These Playwright tests are open-source browser regression scaffolds for staging
and production-like environments.

Install once:

```bash
npm install
npx playwright install
```

Run:

```bash
ODOO_BASE_URL=http://127.0.0.1:8069 npm run test:e2e
```

For staging evidence runs, prefer the guarded runner:

```bash
TIJARA_E2E_SCOPE=full ODOO_BASE_URL=https://staging.example.com make e2e-staging
```

The runner fails before Playwright starts if required public/authenticated
variables are missing, probes `/web/login`, runs the critical browser specs,
and writes evidence under `deploy/runtime/e2e-evidence/<run-id>/`:

- `env-summary.txt`
- `playwright-output.log`
- `playwright-results.json`
- `summary.md`

Use `TIJARA_E2E_SCOPE=public` for display/kiosk/customer-display routes only,
`TIJARA_E2E_SCOPE=authenticated` for POS/refund/offline-report routes, or
`TIJARA_E2E_SCOPE=full` for the complete staging smoke. Set
`TIJARA_E2E_PROJECT=chromium-desktop` when a single browser project is needed
for a controlled drill.

Seed local/staging public-display data before the first run:

```bash
TIJARA_E2E_PASSWORD=<staging-test-password> make seed-e2e DB=tijara_dev
export TIJARA_DISPLAY_SLUG=tijara-e2e-menu
export TIJARA_KIOSK_SLUG=tijara-e2e-kiosk
export TIJARA_CUSTOMER_DISPLAY_SLUG=tijara-e2e-customer
export TIJARA_E2E_PRODUCT_ID=<printed-by-seed>
export TIJARA_E2E_PRODUCT_NAME=<printed-by-seed>
export TIJARA_E2E_PAYMENT_METHOD_ID=<printed-by-seed>
export TIJARA_E2E_PAYMENT_METHOD_NAME=<printed-by-seed>
export TIJARA_E2E_REFUND_REASON_ID=<printed-by-seed>
export TIJARA_E2E_POS_ORDER_ID=<printed-by-seed>
export TIJARA_E2E_REFUND_BARCODE=<printed-by-seed>
export TIJARA_REFUND_ACTION_URL=<printed-by-seed>
export TIJARA_REPORT_ORDER_URL=<printed-by-seed>
export TIJARA_OFFLINE_QUEUE_ACTION_URL=<printed-by-seed>
export ODOO_USERNAME=<printed-by-seed>
export ODOO_PASSWORD=<staging-test-password>
export ODOO_DATABASE=tijara_dev
ODOO_BASE_URL=http://127.0.0.1:8069 npm run test:e2e
```

Useful environment variables:

- `ODOO_USERNAME` and `ODOO_PASSWORD` for authenticated backend/POS tests.
- `ODOO_DATABASE` for multi-database Odoo staging/dev servers.
- `TIJARA_E2E_LOGIN` and `TIJARA_E2E_PASSWORD` for optional POS-capable E2E
  user creation during seeding. The seed grants internal user, POS user/POS
  manager, Tijara user, and Tijara manager groups for staging-only browser
  coverage. Do not use production operator credentials.
- `TIJARA_RUN_POS_UI_E2E=1` to opt into the direct POS UI shell smoke with a
  properly permissioned staging POS user.
- `TIJARA_RUN_DIRECT_POS_CLICKTHROUGH=1` to opt into direct cashier POS UI
  search/add-to-cart/payment-screen selectors. This requires
  `TIJARA_E2E_PRODUCT_NAME`.
- `TIJARA_RUN_DIRECT_POS_VALIDATE_E2E=1` to let the direct POS UI test validate
  the browser sale and exercise receipt print controls on a staging register
  prepared for real browser sales.
- `TIJARA_RUN_DIRECT_REFUND_FORM_E2E=1` to opt into direct refund form barcode
  field entry and scan-button selectors.
- `TIJARA_RUN_MOBILE_OFFLINE_E2E=1` to also run the authenticated offline replay
  smoke on the mobile-touch project. Use a staging setup that can tolerate
  concurrent replay into the same POS register.
- `TIJARA_POS_CONFIG_ID` for direct POS UI smoke.
- `TIJARA_DISPLAY_SLUG` for public display route smoke.
- `TIJARA_KIOSK_SLUG` for kiosk route smoke.
- `TIJARA_CUSTOMER_DISPLAY_SLUG` for customer-display live-state smoke.
- `TIJARA_E2E_PRODUCT_ID` for authenticated offline POS replay smoke.
- `TIJARA_E2E_PRODUCT_NAME` for direct POS UI product search and add-to-cart.
- `TIJARA_E2E_PAYMENT_METHOD_ID` for authenticated offline POS replay smoke.
- `TIJARA_E2E_PAYMENT_METHOD_NAME` for direct POS UI payment-method selection.
- `TIJARA_E2E_REFUND_REASON_ID` for authenticated refund barcode scan smoke.
- `TIJARA_E2E_POS_ORDER_ID` for seeded POS receipt/report/print coverage.
- `TIJARA_E2E_REFUND_BARCODE` for authenticated refund barcode scan smoke.
- `TIJARA_REFUND_ACTION_URL` for refund/exchange backend route smoke.
- `TIJARA_REPORT_ORDER_URL` for backend report route smoke.
- `TIJARA_OFFLINE_QUEUE_ACTION_URL` for offline conflict review route smoke.

The public display, kiosk checkout, and customer-display tests can run without
credentials after the seed step. The authenticated offline POS replay smoke
runs when Odoo credentials plus seeded POS config/product/payment IDs are set.
Authenticated refund barcode scan, receipt report rendering, print-to-bridge
method coverage, offline conflict review, and POS shell tests run when the seed
prints the matching IDs/URLs and staging credentials are exported. Direct POS UI
shell coverage remains opt-in with `TIJARA_RUN_POS_UI_E2E=1`; deeper direct POS
click-through remains opt-in with `TIJARA_RUN_DIRECT_POS_CLICKTHROUGH=1` and
direct sale validation remains separately guarded by
`TIJARA_RUN_DIRECT_POS_VALIDATE_E2E=1`.

`tests/e2e/pos-enterprise-journey.spec.mjs` is the strongest authenticated
staging journey. It creates a paid browser/offline POS order, replays it into
Odoo POS, verifies receipt rendering, exercises the print-to-bridge method,
publishes and reads customer-display state when the POS register is configured,
matches the generated receipt barcode through the refund scanner workflow, and
proves duplicate replay handling plus offline status reporting.

`tests/e2e/pos-direct-ui-clickthrough.spec.mjs` is the direct cashier UI
selector drill. It searches the seeded product in the POS UI, adds it to the
cart, opens payment, optionally selects the seeded payment method, optionally
validates the sale and clicks receipt print, and can separately exercise refund
form barcode entry.

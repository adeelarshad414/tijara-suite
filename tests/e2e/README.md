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
- `status.tsv`
- `e2e-readiness.json`
- `e2e-readiness-summary.md`
- `playwright-output.log`
- `playwright-results.json`
- `summary.md`

`e2e-readiness.json` records the selected scope, required environment
variables with secret values masked, selected specs, and optional POS/refund
flags. The release sign-off pack extracts seed, profile, execution, and readiness evidence
under `e2e_seed_reviews`, `e2e_profile_reviews`, `e2e_execution_reviews`, and
`e2e_readiness_reviews`.

Use `TIJARA_E2E_SCOPE=public` for display/kiosk/customer-display routes only,
`TIJARA_E2E_SCOPE=authenticated` for POS/refund/offline-report routes, or
`TIJARA_E2E_SCOPE=full` for the complete staging smoke. Set
`TIJARA_E2E_PROJECT=chromium-desktop` when a single browser project is needed
for a controlled drill.

Seed local/staging public-display data before the first run:

```bash
TIJARA_E2E_SEED_RUN_ID=staging-pos-seed-001 \
TIJARA_E2E_PASSWORD=<staging-test-password> \
make seed-e2e DB=tijara_dev

source deploy/runtime/e2e-seed/staging-pos-seed-001/e2e-seed.env
export ODOO_PASSWORD=<staging-test-password>
ODOO_BASE_URL=http://127.0.0.1:8069 npm run test:e2e
```

The seed wrapper writes `e2e-seed.env`, `status.tsv`, `summary.md`, and
`e2e-seed-evidence.json` under `deploy/runtime/e2e-seed/<run-id>/`. The env
file is sourceable and non-secret; keep `ODOO_PASSWORD` in staging secrets.

Validate the live staging profile before running browser E2E:

```bash
TIJARA_E2E_PROFILE_RUN_ID=staging-pos-seed-001 \
TIJARA_E2E_PROFILE_STRICT=1 \
TIJARA_E2E_PROFILE_REQUIRE_SEED=1 \
TIJARA_E2E_SEED_ENV=deploy/runtime/e2e-seed/staging-pos-seed-001/e2e-seed.env \
TIJARA_E2E_SEED_EVIDENCE=deploy/runtime/e2e-seed/staging-pos-seed-001/e2e-seed-evidence.json \
TIJARA_E2E_OWNER="QA Owner" \
TIJARA_E2E_RUNBOOK_REF=docs:DEPLOY.md#display-routes \
TIJARA_E2E_CHANGE_REF=change:TIJARA-STAGE-E2E-001 \
make staging-e2e-profile
```

The profile evidence writes `staging-e2e-profile.json`, `status.tsv`,
`env-summary.txt`, and `summary.md` under
`deploy/runtime/e2e-profile/<run-id>/`. The sign-off pack extracts it under
`e2e_profile_reviews`.

After a staging browser run and sign-off package are available, correlate the
whole Browser E2E chain:

```bash
TIJARA_E2E_EXECUTION_RUN_ID=staging-pos-seed-001 \
TIJARA_E2E_EXECUTION_STRICT=1 \
TIJARA_E2E_EXECUTION_SEED_EVIDENCE=deploy/runtime/e2e-seed/staging-pos-seed-001/e2e-seed-evidence.json \
TIJARA_E2E_EXECUTION_PROFILE_EVIDENCE=deploy/runtime/e2e-profile/staging-pos-seed-001/staging-e2e-profile.json \
TIJARA_E2E_EXECUTION_E2E_DIR=deploy/runtime/e2e-evidence/staging-pos-seed-001 \
TIJARA_E2E_EXECUTION_SIGNOFF_READINESS=deploy/runtime/signoff-packages/staging-pos-seed-001/release-readiness.json \
make e2e-execution-evidence
```

Execution evidence writes `e2e-execution-evidence.json`, `status.tsv`,
`env-summary.txt`, and `summary.md` under
`deploy/runtime/e2e-execution/<run-id>/`.

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
- `TIJARA_RUN_DIRECT_POS_KEYBOARD_E2E=1` to opt into the keyboard-only cashier
  POS drill for typed/scanner product entry, `Enter`, `F4`, `F7`, and `F8`
  workflows in Chromium desktop staging.
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
- `TIJARA_ECOMMERCE_SLUG` for ecommerce storefront, catalog, checkout, delivery
  charge, queue handoff, customer tracking, provider assignment, and
  authenticated online-order review smoke.
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

The public display, kiosk checkout, customer-display, and ecommerce catalog/
checkout tests can run without credentials after the seed step. The ecommerce
authenticated order-review assertion runs when `ODOO_USERNAME`,
`ODOO_PASSWORD`, and `ODOO_DATABASE` are set, preferably with the seeded
`ecommerce-manager@demo.tijara-suite.local` account. The authenticated offline
POS replay smoke runs when Odoo credentials plus seeded POS config/product/
payment IDs are set.
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
form barcode entry. The same file also includes an opt-in keyboard-only drill
that types/scans a product into the POS, presses `Enter`, cycles service mode
and B2B/B2C selection, and opens payment from the keyboard.

`tests/e2e/ecommerce-storefront.spec.mjs` covers the ecommerce channel: catalog
payloads with PKR, Urdu names, promotions, B2C/B2B prices, stock and
fulfillment; browser pickup checkout from the storefront; API delivery checkout
with delivery charge, provider tracking, adapter state, and queue number;
pickup-code/mobile customer tracking; authenticated sale-order/queue-ticket
review by the ecommerce manager; delivery label and manifest actions; and
dry-run delivery webhook sync back into customer tracking.

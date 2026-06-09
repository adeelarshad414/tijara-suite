# Tijara Suite How-To-Use Guidelines

Version: 2026-06-09

This guide is for daily users. For credentials, use
`docs/TEST_CREDENTIALS.csv`. For screenshots, use
`docs/SCREENSHOT_USER_GUIDE.md` and `docs/VISUAL_USER_GUIDE_ALL_FUNCTIONS.md`.

## General Rules

1. Use the role account assigned to you.
2. Do not share passwords between users.
3. Use demo credentials only in local or staging.
4. Enter real customer mobile/email when loyalty, returns, delivery, or order
   history is needed.
5. Use barcode scanning whenever available; keyboard entry is supported when
   touch or mouse is not practical.
6. Confirm PKR, GST, service charge, delivery charge, and payment tax policy
   before opening a live POS session.
7. Use English, Urdu, or bilingual invoice templates according to the customer
   and branch policy.

## Cashier POS

1. Open the POS register assigned by the tenant admin.
2. Scan barcode, search product, or use keyboard product lookup.
3. Press Enter for the primary action where the POS screen supports it.
4. Choose B2C or B2B price mode.
5. Add customer details for loyalty, B2B invoice, delivery, refund, or exchange.
6. Apply line discounts or bill-level discount by amount or percentage.
7. Select cash, card, JazzCash, Easypaisa, Stripe, bank, or COD where enabled.
8. Complete payment and print or preview the receipt.
9. For refunds, scan the invoice barcode/FBR QR or search the original invoice.
10. For hardware issues, switch to browser print or record the hardware
   exception for manager review.

## Restaurant, Cafe, And Fast Food

1. Select dine-in, takeaway, pickup, or delivery.
2. Select table or customer token where required.
3. Add menu items, combos, deals, modifiers, and notes.
4. Confirm cafe/restaurant-only tax policy:
   - Card tax can be 5%.
   - Cash tax can be 16%.
   - Cafe service charge can be enabled or disabled.
5. Send order to kitchen/queue.
6. Use queue display for ready/pending tickets.
7. Use customer display for cart and total visibility.
8. Complete payment and print bilingual receipt if needed.

## Inventory Team

1. Create products with barcode, SKU, Urdu name, category, and vertical tag.
2. Maintain B2C and B2B prices.
3. Assign warehouse, store, shelf, rack, and bin.
4. Set expiry date, batch, low stock threshold, and reorder policy.
5. Review low-stock, expiry, and location/rack reports daily.
6. Use import/export for bulk product and stock updates.
7. Reconcile physical stock with system stock before major promotions.

## Ecommerce Team

1. Open Ecommerce > Storefront Channels.
2. Publish products and verify B2C/B2B prices.
3. Enable pickup, delivery, courier, and payment methods by tenant plan.
4. Review online orders, customer account orders, saved addresses, and returns.
5. Assign dry-run courier providers for demo or certified providers for
   production.
6. Review retry queue, delivery exceptions, SLA breaches, and reconciliation.
7. Share tracking links with customers when required.

## Customer Account Portal

1. Customer logs in with ecommerce customer account.
2. Customer opens `/tijara/ecommerce/<slug>/account`.
3. Customer reviews order history.
4. Customer saves delivery addresses.
5. Customer creates return/exchange request for eligible order lines.
6. Back-office team reviews and approves or rejects the request.

## Promotions, Queue, Menu, And Customer Displays

1. Promotion manager creates active promotion/menu/deal content.
2. Display operator opens the public display route.
3. Queue screen shows pending, preparing, ready, and served tickets.
4. Customer display shows current POS cart, totals, discounts, taxes, and QR.
5. Treat display routes as SaaS-enabled features and confirm plan access.

## Accountant And Finance

1. Review invoices, refunds, exchange credits, and payment status.
2. Review payment webhooks for JazzCash, Easypaisa, Stripe, and manual flows.
3. Import settlement statements and reconcile gross, fee, net, refund, and
   chargeback lines.
4. Review delivery COD reconciliation and provider fee variance.
5. Review FBR queue status and QR/invoice number before live tax reporting.
6. Do not enable live PSP/FBR unless certified credentials and sign-off evidence
   are attached.

## Manager Dashboards

1. Review daily sales, profit, product mix, low stock, expiry, expenses,
   salaries, loyalty, ecommerce, delivery, and tax/charge policy metrics.
2. Use trend/history charts to compare periods.
3. Review exception dashboards before closing the day.
4. Export reports for audit, finance, and operations meetings.

## DevOps And Support

1. Use `docs/SETUP_STEP_BY_STEP.md` for local/staging setup.
2. Use `DEPLOY.md` for deployment, monitoring, backups, rollback, and release.
3. Use `docs/PRODUCTION_READINESS_CHECKLIST.md` before production go-live.
4. Keep `.env` non-secret and `secrets/.env.secrets` secret.
5. Use dummy values only in local/demo.
6. Confirm `/tijara/monitoring/metrics` is protected by `TIJARA_METRICS_TOKEN`.
7. Run `make monitoring-evidence`, `make production-ops-readiness`, and
   `make signoff-pack` for release evidence.

# POS Demo Seed

The optional `tijara_demo_pos` module creates public-repo safe demo records for
cashier workflow testing. It is not part of the production suite install.

## What It Seeds

- `Tijara Demo POS` configuration.
- One open POS session when no session is already open for that config.
- Demo POS products with barcodes, B2C prices, B2B prices, stock quantities, and
  Urdu names.
- Demo B2C walk-in and B2B wholesale customers.
- Customer display, queue display, menu board, deals board, and kiosk screen
  records.
- Demo kiosk profile.
- Demo promotion/deal.
- Demo queue ticket.

## Run It

Create local environment files first:

```bash
cp .env.example .env
cp secrets/.env.secrets.example secrets/.env.secrets
```

Then update secret values and run:

```bash
make seed-pos-demo
```

For an already-running development stack using explicit env files, the
equivalent command is:

```bash
docker compose --env-file .env --env-file secrets/.env.secrets run --rm odoo \
  bash /usr/local/bin/tijara-start-odoo -d tijara_dev -i tijara_demo_pos \
  --without-demo --stop-after-init
```

## Cashier Smoke Path

1. Open Odoo at `http://localhost:8069/odoo`.
2. Log in as a POS manager.
3. Open `Tijara Demo POS`.
4. Add two demo products.
5. Use the POS action menu to switch B2C/B2B and confirm existing ticket lines
   reprice from the Tijara B2C/B2B product fields.
6. Switch service mode between dine-in, takeaway, and pickup.
7. Apply an overall bill discount as a manager.
8. Complete a cash sale.
9. Start a refund from the POS ticket screen.

## Notes

- Manager approval for bill discount is enabled on the seeded POS config.
- The current runtime guard blocks non-manager cashiers from opening the
  bill-discount dialog when manager approval is required.
- B2B/B2C repricing currently updates existing ticket lines. The deeper
  add-product hook for automatic new-line pricing is a future enhancement.

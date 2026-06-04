# Inventory Intelligence

Tijara Suite inventory must support the real store-floor details needed by
superstores, grocery stores, pharmacies, bakeries, cloth shops, garments,
electronics, restaurants, and wholesale businesses.

## Implemented Foundation

Module: `tijara_inventory_intelligence`

- Storage position master for warehouse, location, zone, aisle, rack, shelf, bin,
  barcode/QR, capacity, and temperature zone.
- Physical placement fields on Odoo stock locations.
- Product-level preferred storage position, critical stock quantity, expiry
  alert days, cycle-count frequency, temperature-control flag, and storage
  notes.
- Inventory alert workbench for low stock, critical stock, expiry, overstock,
  misplaced stock, and dead stock.
- Scheduled daily inventory alert scan.
- List, form, graph, and pivot views for inventory alerts.
- Storage-position search and grouping by warehouse, location, zone, and rack.

## Alert Coverage

Low stock:

- Uses product minimum stock alert quantity.
- Creates open alert records when on-hand quantity falls below the threshold.

Critical stock:

- Uses product critical stock quantity.
- Creates critical-severity alert records when on-hand quantity reaches the
  critical threshold.

Expiry:

- Depends on Odoo `product_expiry`.
- Reads lot/batch expiration dates.
- Uses product expiry-alert days, defaulting to 30 days.
- Marks lots expiring within seven days as critical.

## Placement Coverage

Storage positions capture:

- Warehouse.
- Odoo stock location.
- Zone.
- Aisle.
- Rack.
- Shelf.
- Bin.
- Barcode or QR code.
- Capacity.
- Temperature zone.
- Preferred minimum quantity.

This supports store-floor placement, back-store locations, cold-chain placement,
fast-moving shelves, expiry-sensitive shelves, and barcode/QR-driven lookup.

## Future Enhancements

- Reorder proposal generation from alert records.
- Location-aware stock counts and placement mismatch detection.
- Shelf capacity utilization.
- Dead-stock detection from sales history.
- FEFO picking for expiry-sensitive products.
- Grocery scale/PLU and price-embedded barcode integration.
- Pharmacy batch compliance dashboards.
- Mobile stock count and shelf audit screens.

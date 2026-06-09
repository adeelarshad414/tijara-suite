# Analytics and Reporting

Tijara Suite must give owners and managers clear history, trends, charts,
graphs, dashboards, records, and reports for daily decision-making.

## Implemented Foundation

Module: `tijara_analytics`

- Dashboard templates.
- Dashboard widget definitions.
- KPI snapshot history model.
- Report catalog.
- Graph and pivot views for KPI trend analysis.
- Default dashboards and report definitions seeded into Odoo.
- Manual and scheduled daily KPI snapshot collector.
- SaaS feature flag: `analytics_reporting`.

## Default Dashboards

Owner Overview:

- Revenue trend.
- Gross margin.
- Inventory risk.
- Refunds and exchanges.
- Cash variance.

Inventory Control:

- Low stock.
- Critical stock.
- Expiry alerts.
- Stock turnover.
- Dead stock.
- Shelf/rack/bin placement quality.

POS Performance:

- Orders.
- Basket size.
- Refunds and exchanges.
- Bill discount amount and percentage trends.
- Queue wait time.
- Cashier performance.

Purchase and Procurement:

- Purchase value.
- Supplier lead time.
- Reorder pressure.
- Pending purchase orders.
- Vendor performance.

Customers and Promotions:

- New customers.
- Repeat customers.
- Promotion uplift.
- Deal performance.
- Customer display and promotion display impact.

Back Office Finance:

- Expense approval pipeline.
- Paid/unpaid expense totals.
- Salary gross, deductions, bonuses, and net payable.
- Month-close audit readiness.

Restaurant and Cafe Operations:

- Dine-in, takeaway, pickup, and delivery mix.
- Queue wait and kitchen SLA.
- Cafe service charge.
- Cafe/restaurant card 5% and cash 16% food payment tax.
- Delivery charge audit.

Vertical Retail Mix:

- SKU coverage by superstore, grocery, cosmetics, cloth, garments, uniform,
  shoes, pharmacy, bakery, cafe, fast food, restaurant, mobile shop,
  electronics, and wholesale tags.
- B2B and B2C price coverage.
- Vertical margin and stock pressure.

Loyalty and Customer Retention:

- Loyalty opt-in coverage.
- Loyalty tier movement.
- Points liability.
- Walk-in conversion and repeat visit history.

## Report Catalog

Seeded report templates:

- Daily Sales Summary.
- Inventory Health.
- Purchase and Reorder Planning.
- Customer and Promotion Performance.
- Back Office Expense and Salary Audit.
- Restaurant and Cafe Charge Policy.
- Vertical Catalog Performance.
- Loyalty and Customer History.
- Display and Queue Operations.

## KPI Snapshot Coverage

Snapshots support:

- Day, week, month, quarter, and year periods.
- Sales, POS, purchase, inventory, customers, promotions, finance, operations,
  back office, payroll, loyalty, food service, vertical retail, and tax/charge
  policy.
- Revenue, gross margin, orders, basket size, refunds, stock value, stock
  turnover, low stock, expiry, purchase value, supplier lead time, new customers,
  promotion uplift, queue wait time, and cash variance.
- Actuals, targets, and variance.
- Warehouse-level grouping.

## Automated Collector

The first collector writes daily snapshots for:

- POS revenue, order count, basket size, and refunds from paid/done/invoiced POS
  orders.
- Open low-stock, critical-stock, and expiry alert counts.
- Average queue wait time from queue ticket creation to call.
- Active promotion/deal counts.

Managers can run `Collect Daily Snapshots` from the Analytics menu. The cron
`Tijara Collect Daily Analytics Snapshots` is installed disabled by default and
should be enabled after staging validation.

## Future Enhancements

- Deeper automated KPI snapshot generation from sale, purchase, stock valuation,
  customer, supplier, bill-discount, and cash-shift data.
- Role-specific dashboard rendering.
- Scheduled PDF/email reports.
- Drill-down links from dashboard cards to source records.
- Branch comparison and multi-tenant benchmarking.
- Predictive reorder suggestions.
- Slow-moving and fast-moving item trends.
- Customer segmentation and lifetime value.

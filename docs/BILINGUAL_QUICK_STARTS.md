# Tijara Suite Bilingual Quick Starts

These quick starts are written for training, pilots, and staging demos in
Pakistan-focused businesses. Each workflow is shown in English and Urdu so shop
teams can learn the same operating language before go-live.

Use these with `docs/TEST_CREDENTIALS.csv` in demo/staging only. Production
users must have real names, strong passwords, MFA where available, and
tenant-specific permissions.

## Cashier POS

| Step | English | اردو |
|---|---|---|
| 1 | Log in with the cashier account and open the assigned POS register. | کیشیئر اکاؤنٹ سے لاگ ان کریں اور اپنا POS رجسٹر کھولیں۔ |
| 2 | Select B2C for normal customers or B2B for wholesale/trade customers. | عام گاہک کے لیے B2C منتخب کریں، تھوک یا کاروباری گاہک کے لیے B2B منتخب کریں۔ |
| 3 | Scan the barcode or search the product by name/SKU. | بارکوڈ اسکین کریں یا نام/SKU سے پراڈکٹ تلاش کریں۔ |
| 4 | Check quantity, price, GST, and discount before payment. | ادائیگی سے پہلے مقدار، قیمت، GST، اور ڈسکاؤنٹ چیک کریں۔ |
| 5 | For bill discount, enter percentage or amount. The other value should update automatically. | بل ڈسکاؤنٹ کے لیے فیصد یا رقم درج کریں۔ دوسری قدر خود بخود اپڈیٹ ہونی چاہیے۔ |
| 6 | Take cash/card/mobile payment and validate the order. | کیش، کارڈ، یا موبائل ادائیگی لیں اور آرڈر ویلیڈیٹ کریں۔ |
| 7 | Print the receipt or send it to the configured receipt printer bridge. | رسید پرنٹ کریں یا کنفیگرڈ رسید پرنٹر برج کو بھیجیں۔ |
| 8 | For return/exchange, scan the invoice barcode and follow the refund approval workflow. | ریٹرن/ایکسچینج کے لیے انوائس بارکوڈ اسکین کریں اور ریفنڈ منظوری ورک فلو فالو کریں۔ |

Success signal: the receipt shows PKR, GST 18% where applicable, invoice
barcode/QR, payment, cashier, and return policy.

کامیابی کی نشانی: رسید میں PKR، ضرورت کے مطابق GST 18%، انوائس بارکوڈ/QR،
ادائیگی، کیشیئر، اور ریٹرن پالیسی واضح ہو۔

## Tenant Admin

| Step | English | اردو |
|---|---|---|
| 1 | Review company name, Pakistan country, PKR currency, branches, and warehouses. | کمپنی نام، پاکستان ملک، PKR کرنسی، برانچز، اور ویئر ہاؤسز چیک کریں۔ |
| 2 | Enable only the SaaS features paid for by the tenant, such as B2B, queue, customer display, and promotion display. | صرف وہ SaaS فیچرز فعال کریں جن کا پلان موجود ہے، جیسے B2B، قطار، کسٹمر ڈسپلے، اور پروموشن ڈسپلے۔ |
| 3 | Create users by role: cashier, inventory, accountant, manager, restaurant operator, and support. | رول کے حساب سے صارفین بنائیں: کیشیئر، انوینٹری، اکاؤنٹنٹ، مینیجر، ریسٹورنٹ آپریٹر، اور سپورٹ۔ |
| 4 | Configure POS registers, receipt templates, invoice templates, printers, scanners, and customer displays. | POS رجسٹر، رسید ٹیمپلیٹس، انوائس ٹیمپلیٹس، پرنٹرز، اسکینرز، اور کسٹمر ڈسپلے کنفیگر کریں۔ |
| 5 | Run a staging checkout, refund barcode scan, print-to-bridge test, and display screen check. | اسٹیجنگ چیک آؤٹ، ریفنڈ بارکوڈ اسکین، پرنٹ ٹو برج ٹیسٹ، اور ڈسپلے اسکرین چیک چلائیں۔ |

Success signal: every paid feature works, unpaid features are blocked, and the
tenant evidence folder is ready for sign-off.

کامیابی کی نشانی: ہر paid فیچر کام کرے، unpaid فیچرز بلاک ہوں، اور ٹیننٹ
evidence فولڈر sign-off کے لیے تیار ہو۔

## Inventory Manager

| Step | English | اردو |
|---|---|---|
| 1 | Import products with SKU, barcode, category, B2C price, B2B price, GST category, and unit. | SKU، بارکوڈ، کیٹیگری، B2C قیمت، B2B قیمت، GST کیٹیگری، اور یونٹ کے ساتھ پراڈکٹس امپورٹ کریں۔ |
| 2 | Add warehouse, store, aisle, rack, shelf, bin, batch, expiry, and reorder levels. | ویئر ہاؤس، اسٹور، آئل، ریک، شیلف، بن، بیچ، ایکسپائری، اور ری آرڈر لیول شامل کریں۔ |
| 3 | Review low stock, expiry alerts, and fast-moving item trends daily. | روزانہ low stock، expiry alerts، اور fast-moving item trends دیکھیں۔ |
| 4 | Use bulk import/export for stock corrections and new supplier price lists. | اسٹاک درستگی اور نئے supplier price lists کے لیے bulk import/export استعمال کریں۔ |
| 5 | Lock critical adjustments behind manager approval and keep audit notes. | اہم adjustments کو manager approval کے پیچھے رکھیں اور audit notes محفوظ کریں۔ |

Success signal: stock cards show correct location, available quantity, expiry
risk, reorder level, and sales trend.

کامیابی کی نشانی: stock cards میں درست جگہ، available quantity، expiry risk،
reorder level، اور sales trend نظر آئے۔

## Restaurant Operator

| Step | English | اردو |
|---|---|---|
| 1 | Confirm service mode before order: dine-in, takeaway, or pickup. | آرڈر سے پہلے service mode کنفرم کریں: dine-in، takeaway، یا pickup۔ |
| 2 | Use table/customer details for dine-in and pickup code/mobile for pickup orders. | dine-in کے لیے table/customer details، اور pickup کے لیے pickup code/mobile استعمال کریں۔ |
| 3 | Keep kiosk, menu board, deals board, queue display, and customer display open on the correct screens. | kiosk، menu board، deals board، queue display، اور customer display درست اسکرینز پر کھلے رکھیں۔ |
| 4 | Watch queue status and mark orders in progress, ready, picked up, or cancelled. | queue status دیکھیں اور orders کو in progress، ready، picked up، یا cancelled مارک کریں۔ |
| 5 | Check kitchen ticket, receipt, tax, discount, and payment before closing the order. | آرڈر بند کرنے سے پہلے kitchen ticket، receipt، tax، discount، اور payment چیک کریں۔ |

Success signal: customer display and queue display update without exposing
back-office menus.

کامیابی کی نشانی: customer display اور queue display اپڈیٹ ہوں اور back-office
menus ظاہر نہ ہوں۔

## Accountant And Owner

| Step | English | اردو |
|---|---|---|
| 1 | Review daily sales, GST, refunds, exchanges, discounts, expenses, purchases, and cash shifts. | روزانہ sales، GST، refunds، exchanges، discounts، expenses، purchases، اور cash shifts دیکھیں۔ |
| 2 | Compare B2B and B2C margins by product, category, branch, and cashier. | پراڈکٹ، کیٹیگری، برانچ، اور کیشیئر کے حساب سے B2B اور B2C margin compare کریں۔ |
| 3 | Review PSP settlement, fees, refunds, chargebacks, and unreconciled lines. | PSP settlement، fees، refunds، chargebacks، اور unreconciled lines چیک کریں۔ |
| 4 | Review FBR queue status and resolve failed invoices before closing the day. | دن بند کرنے سے پہلے FBR queue status دیکھیں اور failed invoices resolve کریں۔ |
| 5 | Use analytics dashboards for trend, history, charts, graphs, and business decisions. | trend، history، charts، graphs، اور business decisions کے لیے analytics dashboards استعمال کریں۔ |

Success signal: daily closeout has sales, tax, payment, cash, inventory, and FBR
exceptions reviewed.

کامیابی کی نشانی: daily closeout میں sales، tax، payment، cash، inventory، اور
FBR exceptions reviewed ہوں۔

## DevOps And Support

| Step | English | اردو |
|---|---|---|
| 1 | Keep `.env` and `secrets/.env.secrets` separate. Never commit real secrets. | `.env` اور `secrets/.env.secrets` الگ رکھیں۔ real secrets کبھی commit نہ کریں۔ |
| 2 | Start local services with `bash scripts/dev-start.sh` and stop with `bash scripts/dev-stop.sh`. | local services کو `bash scripts/dev-start.sh` سے start اور `bash scripts/dev-stop.sh` سے stop کریں۔ |
| 3 | For local evidence, run `make local-e2e-evidence`. | local evidence کے لیے `make local-e2e-evidence` چلائیں۔ |
| 4 | For protected/staging browser matrix, run `make browser-e2e-matrix` with seeded credentials and staging URL. | protected/staging browser matrix کے لیے seeded credentials اور staging URL کے ساتھ `make browser-e2e-matrix` چلائیں۔ |
| 5 | Attach monitoring, backup restore, load, security, tenant, PSP, FBR, courier, and hardware evidence to the sign-off pack. | monitoring، backup restore، load، security، tenant، PSP، FBR، courier، اور hardware evidence کو sign-off pack کے ساتھ attach کریں۔ |

Success signal: release evidence is repeatable, redacted, reviewed, and tied to
one run ID.

کامیابی کی نشانی: release evidence repeatable، redacted، reviewed، اور ایک run
ID کے ساتھ linked ہو۔

## Daily Go-Live Checklist

- POS opens and cashier can complete a PKR sale with GST.
- Receipt template, invoice barcode, QR, and printer bridge are verified.
- Scanner works for product entry and refund invoice lookup.
- Customer display, queue display, kiosk, menu board, and deals board are
  visible on assigned screens.
- Low stock and expiry alerts are reviewed.
- Cash shift, refunds, exchanges, discounts, and voids are reviewed.
- PSP settlement and FBR queue exceptions are checked.
- Backup, monitoring, and incident contacts are confirmed.

## روزانہ گو لائیو چیک لسٹ

- POS کھلتا ہے اور کیشیئر GST کے ساتھ PKR sale مکمل کر سکتا ہے۔
- receipt template، invoice barcode، QR، اور printer bridge verify ہیں۔
- scanner product entry اور refund invoice lookup کے لیے کام کرتا ہے۔
- customer display، queue display، kiosk، menu board، اور deals board assigned
  screens پر نظر آتے ہیں۔
- low stock اور expiry alerts reviewed ہیں۔
- cash shift، refunds، exchanges، discounts، اور voids reviewed ہیں۔
- PSP settlement اور FBR queue exceptions checked ہیں۔
- backup، monitoring، اور incident contacts confirmed ہیں۔

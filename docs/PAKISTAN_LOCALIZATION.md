# Pakistan Localization

## Required Local Fields

- Company NTN, STRN, and branch code.
- Customer CNIC, NTN, STRN, and Urdu display name.
- Product Urdu name, local SKU, barcode alias, HS code, and tax category.
- Receipt language preference.
- FBR POS enablement metadata.

## Urdu Support

The product should support English and Urdu as first-class languages:

- `.po` translations for Odoo backend labels.
- Urdu customer names and product names.
- Urdu receipt/footer templates.
- RTL-aware POS frontend in later UI phases.
- Noto Nastaliq Urdu or another readable Urdu font in receipt/report templates
  where printer support allows it.

## FBR POS

FBR integration should be treated as a fiscal adapter with a queue and retry
model. The queue should store the outgoing payload, response, FBR invoice
number, QR payload, state, timestamps, and errors.

The production adapter must be implemented from current FBR technical
documentation and tested with the official sandbox or onboarding path available
to the retailer.


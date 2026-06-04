# Open Source Policy

Tijara Suite is intended to be shared in a public repository for the community.
The project must stay open-source-first in code, tooling, deployment, assets,
and documentation.

## License Baseline

- Root project license: LGPL-3.0.
- Odoo addon manifest license: `LGPL-3`.
- Third-party dependencies must use OSI-approved open-source licenses that are
  compatible with Odoo Community and LGPL-3.0 usage.
- Any file using a different compatible open-source license must state that
  clearly with an SPDX identifier or an adjacent license note.

## Platform Rules

- Use Odoo Community as the ERP/POS base.
- Do not depend on Odoo Enterprise modules, proprietary apps, or closed-source
  services for core product behavior.
- Prefer standard Odoo Community models and extension points before adding
  custom code.
- Keep SaaS feature flags, tenant operations, analytics, POS features, and
  vertical packs open in the public codebase.

## Approved Open-Source Stack Direction

- Odoo Community for ERP/POS.
- PostgreSQL for database.
- Nginx or another open-source reverse proxy.
- Docker and Docker Compose for local/dev deployment.
- Python, JavaScript/OWL, XML, SCSS, and open-source test tools.
- Open-source browser/device testing such as Playwright where needed.

## Public Repository Hygiene

- Commit only example configuration and secret templates.
- Never commit real `.env`, real API keys, database passwords, certificates, or
  customer data.
- Keep all production secrets outside the repository and load them from env
  files or managed secret stores.
- Avoid proprietary fonts, images, icons, demo data, barcode databases, or paid
  templates unless their license explicitly allows public redistribution.
- Track attribution and license notes for any third-party assets added later.

## Dependency Intake Checklist

Before adding a new dependency, confirm:

- It is open source.
- Its license is compatible with LGPL-3.0 and public redistribution.
- It does not require a proprietary SaaS account for core functionality.
- It can be deployed by the community without vendor lock-in.
- It is documented in README, deployment docs, or module docs when it affects
  setup, operations, or licensing.

## Community Product Model

The product can support paid hosting, implementation, training, customization,
and managed support services, but the core suite should remain usable from the
public open-source repository with open-source tools.


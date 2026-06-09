# Production Infrastructure Templates

These templates are non-secret command packs for
`scripts/run_production_infra_automation.py`.

Use them to generate tenant DNS, TLS, backup, restore-drill, and rollback
wrappers from `deploy/runtime/tenants/<tenant_db>/ops-manifest.json`.

Examples:

```bash
python3 scripts/run_production_infra_automation.py \
  --tenant-artifact deploy/runtime/tenants/tijara_customer_001 \
  --provider-template cloudflare-cert-manager-postgres

python3 scripts/run_production_infra_automation.py \
  --tenant-artifact deploy/runtime/tenants/tijara_customer_001 \
  --provider-template route53-cert-manager-postgres
```

The generated scripts call runner scripts under
`deploy/production-infra/runners/`. Real provider execution requires
`CONFIRM_PROVIDER_ACTION=YES`; otherwise the generated scripts produce dry-run
evidence only.

Keep these files free of API tokens, kubeconfigs, database passwords, and
backup encryption keys. Provider credentials belong in `secrets/.env.secrets`,
Kubernetes Secrets, Vault, Doppler, SOPS, or the cloud provider secret manager.

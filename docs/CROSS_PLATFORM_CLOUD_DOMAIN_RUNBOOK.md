# Cross-Platform Configure, Install, Run, Stop, And Cloud Domain Runbook

This runbook gives operators one command path for Windows, Linux, macOS, and
cloud VM deployments. It uses only the central runtime files:

- `.env` for non-secret configuration
- `secrets/.env.secrets` for passwords, tokens, API keys, and private material

Do not create `.env.local`, `.env.production`, shell-specific secret files, or
provider-specific secret files. Keep real cloud, DNS, FBR, PSP, courier, backup,
and hardware secrets in `secrets/.env.secrets` for local/staging or in a real
secret manager for production.

## Supported Runtime Targets

Tijara Suite can run anywhere Docker and Docker Compose are available:

- Windows 11 or Windows Server with Docker Desktop or Docker Engine plus
  PowerShell
- Linux servers such as Ubuntu, Debian, RHEL, AlmaLinux, Rocky Linux, Fedora,
  Amazon Linux, and similar distributions
- macOS developer/demo machines with Docker Desktop
- Cloud VMs on AWS EC2, Azure VM, Google Compute Engine, DigitalOcean, Hetzner,
  Vultr, Linode, Oracle Cloud, or any provider that can expose ports 80/443
- Kubernetes platforms when paired with an external deployment process,
  cert-manager, ingress, and the committed DNS/TLS/backup templates

The default production path is a cloud VM or server running Docker Compose
behind a reverse proxy/TLS endpoint. Kubernetes is supported through planning
templates and should be implemented with the customer's chosen cluster/ingress
standard.

## Prerequisites

Install these tools on the machine that will run the application:

- Git
- Python 3.10 or newer where available
- Docker Engine or Docker Desktop
- Docker Compose v2
- Bash for Linux/macOS commands
- PowerShell 7 or Windows PowerShell for Windows commands

Optional but recommended:

- `make`
- `openssl`
- Provider CLIs such as `cloudflare`, `aws`, `kubectl`, or backup tooling
- A production secret manager such as Vault, SOPS, Kubernetes Secrets, Docker
  secrets, Doppler, 1Password Secrets Automation, AWS Secrets Manager, Azure Key
  Vault, or Google Secret Manager

## Configure The Project

Linux/macOS:

```bash
cp .env.example .env
mkdir -p secrets
cp secrets/.env.secrets.example secrets/.env.secrets
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
New-Item -ItemType Directory -Force secrets
Copy-Item secrets/.env.secrets.example secrets/.env.secrets
```

Generate safe local/staging placeholder secrets:

```bash
python3 scripts/tijara_host.py init-config --environment staging --generate-secrets
```

Windows:

```powershell
py -3 scripts/tijara_host.py init-config --environment staging --generate-secrets
```

For production, replace every placeholder in `secrets/.env.secrets` with real
secret-manager values. Production runs should use `--production` so missing or
placeholder secrets are blocked.

## Install And Run Locally

Linux/macOS Bash:

```bash
bash scripts/tijara-start.sh --all --install-suite --seed-demo
```

Windows PowerShell:

```powershell
powershell -File scripts/tijara-start.ps1 -AllProfiles -InstallSuite -SeedDemo
```

Python, any OS:

```bash
python3 scripts/tijara_services.py start --all-profiles --install-suite --seed-demo
```

Make, Linux/macOS or environments with Make:

```bash
make tijara-start TIJARA_SERVICE_FLAGS="--all --install-suite --seed-demo"
```

Open the local app:

```text
http://localhost:8069
```

## Stop The Project

Linux/macOS Bash:

```bash
bash scripts/tijara-stop.sh --force-kill-ports
```

Windows PowerShell:

```powershell
powershell -File scripts/tijara-stop.ps1 -ForceKillPorts
```

Python, any OS:

```bash
python3 scripts/tijara_services.py stop --force-kill-ports
```

Docker Compose fallback:

```bash
docker compose --env-file .env --env-file secrets/.env.secrets down
```

## Deploy To A Domain On Any Cloud VM

This path is provider-neutral. It works on any cloud VM where Docker Compose can
run and DNS can point to the server or load balancer.

Before running:

1. Create a VM/server.
2. Install Docker, Docker Compose, Git, and Python.
3. Clone the repo.
4. Point DNS `A`, `AAAA`, or `CNAME` records to the server or load balancer.
5. Open ports `80` and `443` to the reverse proxy.
6. Keep Odoo internal port `8069` private unless this is a controlled demo.
7. Prepare real production secrets in the secret manager or
   `secrets/.env.secrets`.

Linux/macOS cloud/domain wrapper:

```bash
bash scripts/tijara-cloud-domain-deploy.sh \
  --domain pos.example.com \
  --environment production \
  --monitoring \
  --install-suite \
  --db tijara_prod
```

Windows/PowerShell Core cloud/domain wrapper:

```powershell
pwsh -File scripts/tijara-cloud-domain-deploy.ps1 `
  -Domain pos.example.com `
  -Environment production `
  -Monitoring `
  -InstallSuite `
  -Database tijara_prod
```

Make shortcut:

```bash
make tijara-cloud-domain-deploy TIJARA_CLOUD_DOMAIN_FLAGS="--domain pos.example.com --monitoring --install-suite --db tijara_prod"
```

Low-level Python equivalent:

```bash
python3 scripts/tijara_host.py deploy \
  --production \
  --domain pos.example.com \
  --with-monitoring \
  --install-suite \
  --db tijara_prod
```

The domain deploy flow writes these non-secret runtime values to `.env`:

- `TIJARA_DOMAIN=pos.example.com`
- `TIJARA_PUBLIC_URL=https://pos.example.com`
- `ODOO_PROXY_MODE=True`
- `ODOO_DB_FILTER=^%d$|^%h$`
- production defaults such as hidden database listing when `--production` is
  used

## DNS, TLS, Backup, And Restore Planning

The cloud/domain wrapper can also generate DNS, TLS, backup, restore-drill, and
rollback evidence plans using committed provider templates.

Cloudflare plus cert-manager plus PostgreSQL backup:

```bash
bash scripts/tijara-cloud-domain-deploy.sh \
  --domain pos.example.com \
  --provider-template cloudflare-cert-manager-postgres \
  --tenant-artifact deploy/runtime/tenants/tijara_customer_001
```

AWS Route53 plus cert-manager plus PostgreSQL backup:

```bash
bash scripts/tijara-cloud-domain-deploy.sh \
  --domain pos.example.com \
  --provider-template route53-cert-manager-postgres \
  --tenant-artifact deploy/runtime/tenants/tijara_customer_001
```

Windows PowerShell:

```powershell
pwsh -File scripts/tijara-cloud-domain-deploy.ps1 `
  -Domain pos.example.com `
  -ProviderTemplate cloudflare-cert-manager-postgres `
  -TenantArtifact deploy/runtime/tenants/tijara_customer_001
```

The default infra mode is `plan`. It generates operator evidence and wrapper
commands but does not execute real provider changes. Real provider execution
requires explicit approval:

```bash
bash scripts/tijara-cloud-domain-deploy.sh \
  --domain pos.example.com \
  --provider-template cloudflare-cert-manager-postgres \
  --tenant-artifact deploy/runtime/tenants/tijara_customer_001 \
  --infra-mode apply \
  --execute-infra \
  --confirm YES
```

Production provider actions also require real secrets and provider-level
confirmation, for example `CONFIRM_PROVIDER_ACTION=YES`.

## Cloud Platform Mapping

| Cloud target | Recommended Tijara command path | DNS/TLS path |
| --- | --- | --- |
| AWS EC2 | `scripts/tijara-cloud-domain-deploy.*` on the VM | Route53 template or Cloudflare |
| Azure VM | `scripts/tijara-cloud-domain-deploy.*` on the VM | Azure DNS manually or Cloudflare |
| Google Compute Engine | `scripts/tijara-cloud-domain-deploy.*` on the VM | Cloud DNS manually or Cloudflare |
| DigitalOcean Droplet | `scripts/tijara-cloud-domain-deploy.*` on the VM | DigitalOcean DNS manually or Cloudflare |
| Hetzner, Vultr, Linode, Oracle VM | `scripts/tijara-cloud-domain-deploy.*` on the VM | Provider DNS manually or Cloudflare |
| Kubernetes | Use repo config and images with platform deployment tooling | cert-manager and ingress templates |

For "any cloud", the contract is:

- the cloud supplies compute, storage, DNS, firewall, and optional load balancer
- Tijara supplies Docker Compose runtime, central config, Odoo modules,
  monitoring profile, evidence scripts, and domain-aware config
- DNS/TLS/backup providers are plugged in through templates or customer
  platform tooling

## Reverse Proxy And Domain Notes

For a domain deployment, put Odoo behind a reverse proxy or load balancer:

- Public ports: `80` and `443`
- Odoo internal HTTP: `8069`
- Odoo longpolling/internal bus: `8072`
- Set `ODOO_PROXY_MODE=True`
- Preserve forwarded headers such as `X-Forwarded-Host`,
  `X-Forwarded-Proto`, and `X-Forwarded-For`
- Terminate TLS at nginx, cloud load balancer, ingress, or cert-manager
- Keep database and admin ports private

The committed nginx baseline is:

```text
deploy/nginx/tijara.conf
```

## Day-Two Operations

Status:

```bash
python3 scripts/tijara_services.py status
docker compose --env-file .env --env-file secrets/.env.secrets ps
```

Logs:

```bash
python3 scripts/tijara_services.py logs odoo --tail 200
docker compose --env-file .env --env-file secrets/.env.secrets logs -f odoo
```

Backup:

```bash
make backup-db DB=tijara_prod
```

Restore drill:

```bash
make restore-drill BACKUP=deploy/runtime/backups/file.dump
```

Monitoring:

```bash
make monitoring-up
make monitoring-dashboards
make monitoring-evidence
```

Release evidence:

```bash
make protected-release-chain
make protected-pos-matrix-evidence
make signoff-pack
```

## Production Go-Live Checklist

Do not mark a customer production-ready until these are complete:

- Real domain points to the server or load balancer.
- TLS certificate is valid for the domain.
- `.env` contains the correct `TIJARA_DOMAIN` and `TIJARA_PUBLIC_URL`.
- Real secrets are injected from the selected secret manager.
- Database backups and restore drills are proven.
- Monitoring, alerting, and logs are running.
- POS checkout, refund, print, and offline replay are tested on staging.
- Real printers, scanners, drawers, scales, and displays are certified.
- FBR provider credentials and compliance tests are complete.
- JazzCash, Easypaisa, Stripe, and other PSP certification is complete.
- Courier provider certification and webhook/reconciliation tests are complete.
- Security scans, dependency/container scans, and load tests have evidence.

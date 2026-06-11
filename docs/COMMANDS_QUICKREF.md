# Commands Quick Reference

## Terminal

| Action | Command |
|---|---|
| Start all core services | `bash scripts/dev-start.sh` |
| Start all services with Python manager | `python3 scripts/tijara_services.py start --all-profiles` |
| Start all services with Bash wrapper | `bash scripts/tijara-start.sh --all` |
| Start with hardware bridge | `TIJARA_DEV_START_HARDWARE=1 bash scripts/dev-start.sh` |
| Start with monitoring | `TIJARA_DEV_START_MONITORING=1 bash scripts/dev-start.sh` |
| Start, install suite, and seed POS demo | `TIJARA_DEV_INSTALL_SUITE=1 TIJARA_DEV_SEED_POS_DEMO=1 bash scripts/dev-start.sh` |
| Start, install suite, and seed through Bash wrapper | `bash scripts/tijara-start.sh --all --install-suite --seed-demo` |
| Stop all Compose services | `bash scripts/dev-stop.sh` |
| Stop all services with Python manager | `python3 scripts/tijara_services.py stop --force-kill-ports` |
| Stop all services with Bash wrapper | `bash scripts/tijara-stop.sh --force-kill-ports` |
| Stop and force free known ports | `TIJARA_FORCE_KILL_PORTS=1 bash scripts/dev-stop.sh` |
| Restart everything | `bash scripts/dev-restart.sh` |
| Restart with Python manager | `python3 scripts/tijara_services.py restart --all-profiles` |
| Python service status | `python3 scripts/tijara_services.py status` |
| Python service logs | `python3 scripts/tijara_services.py logs odoo --tail 200` |
| Python Compose config validation | `python3 scripts/tijara_services.py config` |
| Print full Python Compose config | `python3 scripts/tijara_services.py config --print` |
| Server hosting preflight | `python3 scripts/tijara_host.py preflight --all-profiles` |
| Server init central config | `python3 scripts/tijara_host.py init-config --environment staging --public-url https://staging.example.com --generate-secrets` |
| Server deploy stack | `python3 scripts/tijara_host.py deploy --with-hardware --with-monitoring --install-suite` |
| Server deploy stack with Bash wrapper | `bash scripts/tijara-deploy.sh --environment staging --generate-secrets --monitoring --install-suite` |
| Deploy to cloud VM/domain with Bash wrapper | `bash scripts/tijara-cloud-domain-deploy.sh --domain pos.example.com --environment production --monitoring --install-suite --db tijara_prod` |
| Deploy to cloud VM/domain with Make | `make tijara-cloud-domain-deploy TIJARA_CLOUD_DOMAIN_FLAGS="--domain pos.example.com --monitoring --install-suite --db tijara_prod"` |
| Validate scaffold | `make validate` |
| Start Compose manually | `make up` |
| Start via Python Make target | `make py-start` |
| Start via Bash wrapper Make target | `make tijara-start TIJARA_SERVICE_FLAGS="--all"` |
| Stop Compose manually | `make down` |
| Stop via Python Make target | `make py-stop` |
| Stop via Bash wrapper Make target | `make tijara-stop TIJARA_SERVICE_FLAGS="--force-kill-ports"` |
| Show service status | `make ps` |
| Show Python service status | `make py-status` |
| Follow Odoo logs | `make logs` |
| Install suite modules | `make install-suite` |
| Upgrade PKR/GST, POS experience, analytics, and demo modules | `make upgrade-pkr-gst` |
| Verify live PKR and GST 18% | `make verify-pkr-gst` |
| Seed POS demo | `make seed-pos-demo` |
| Seed all demo users | `make seed-demo-users` |
| Verify enterprise demo seed data | `make verify-enterprise-seed` |
| Run full local browser E2E evidence | `make local-e2e-evidence` |
| Run Odoo tests | `make test-odoo` |
| Run Playwright E2E | `make e2e` |
| Run browser/device E2E matrix | `make browser-e2e-matrix` |
| Capture screenshots | `node scripts/capture-screenshots.js` |
| Generate screenshot user guide | `make screenshot-user-guide` |
| Record demo clips | `node scripts/record-demo.js` |
| Generate customer demo with voiceover | `make customer-demo-video` |
| Assemble demo video | `bash scripts/assemble-video.sh` |
| Run security audit | `make security-audit` |
| Run JS checks | `make js-check` |
| Start hardware bridge only | `make bridge-up` |
| Start monitoring profile | `make monitoring-up` |
| Seed demo Prometheus/Pushgateway metrics | `make prometheus-demo-metrics` |
| Regenerate Grafana dashboards | `make monitoring-dashboards` |
| Validate Grafana dashboards | `make monitoring-dashboards-check` |
| Capture Grafana dashboard evidence | `make grafana-dashboard-evidence` |
| Validate Grafana dashboards without running Grafana | `node scripts/capture-grafana-evidence.js --metadata-only` |
| Generate production DNS/TLS/backup wrappers | `make production-infra TIJARA_PRODUCTION_INFRA_FLAGS="--tenant-artifact deploy/runtime/tenants/tijara_customer_001"` |
| Generate app deploy plus Cloudflare/cert-manager/Postgres plan | `bash scripts/tijara-cloud-domain-deploy.sh --domain pos.example.com --provider-template cloudflare-cert-manager-postgres --tenant-artifact deploy/runtime/tenants/tijara_customer_001` |
| Generate Cloudflare/cert-manager/Postgres wrappers | `make production-infra TIJARA_PRODUCTION_INFRA_FLAGS="--tenant-artifact deploy/runtime/tenants/tijara_customer_001 --provider-template cloudflare-cert-manager-postgres --strict"` |
| Generate Route53/cert-manager/Postgres wrappers | `make production-infra TIJARA_PRODUCTION_INFRA_FLAGS="--tenant-artifact deploy/runtime/tenants/tijara_customer_001 --provider-template route53-cert-manager-postgres --strict"` |
| Export infra provider readiness | `make infra-provider-readiness TIJARA_INFRA_PROVIDER_READINESS_FLAGS="--production-infra-evidence deploy/runtime/production-infra/20260609-provider-templates-cloudflare --allow-assumptions --assume-provider all --strict"` |
| Run full operations evidence bundle | `make operations-release-bundle` |
| Run release candidate gate | `make release-candidate` |
| Generate signoff pack | `make signoff-pack` |

## VS Code

| Action | How |
|---|---|
| Start all services | Terminal > Run Task > Start App All Services |
| Stop all services | Terminal > Run Task > Stop App Kill All |
| Restart | Terminal > Run Task > Restart App |
| Seed POS demo | Terminal > Run Task > Seed POS Demo |
| Capture screenshots | Terminal > Run Task > Capture Screenshots |
| Record demo video | Terminal > Run Task > Record Demo Video |

## Windows PowerShell

| Action | Command |
|---|---|
| Start all services | `powershell -File scripts/dev-start.ps1` |
| Start all services with PowerShell wrapper | `powershell -File scripts/tijara-start.ps1 -AllProfiles` |
| Start with hardware bridge | `powershell -File scripts/dev-start.ps1 -Hardware` |
| Start with monitoring | `powershell -File scripts/dev-start.ps1 -Monitoring` |
| Start, install suite, and seed with PowerShell wrapper | `powershell -File scripts/tijara-start.ps1 -AllProfiles -InstallSuite -SeedDemo` |
| Stop services | `powershell -File scripts/dev-stop.ps1` |
| Stop services with PowerShell wrapper | `powershell -File scripts/tijara-stop.ps1 -ForceKillPorts` |
| Stop and force known ports | `powershell -File scripts/dev-stop.ps1 -ForceKillPorts` |
| Deploy with PowerShell wrapper | `powershell -File scripts/tijara-deploy.ps1 -Environment staging -GenerateSecrets -Monitoring -InstallSuite` |
| Deploy to cloud VM/domain with PowerShell wrapper | `pwsh -File scripts/tijara-cloud-domain-deploy.ps1 -Domain pos.example.com -Environment production -Monitoring -InstallSuite -Database tijara_prod` |
| Deploy plus Cloudflare/cert-manager/Postgres plan | `pwsh -File scripts/tijara-cloud-domain-deploy.ps1 -Domain pos.example.com -ProviderTemplate cloudflare-cert-manager-postgres -TenantArtifact deploy/runtime/tenants/tijara_customer_001` |
| Generate production infra wrappers | `pwsh -File scripts/tijara-production-infra.ps1 --tenant-artifact deploy/runtime/tenants/tijara_customer_001` |
| Generate provider infra wrappers | `pwsh -File scripts/tijara-production-infra.ps1 --tenant-artifact deploy/runtime/tenants/tijara_customer_001 --provider-template cloudflare-cert-manager-postgres --strict` |

## Stop And Kill

Recommended:

```bash
bash scripts/dev-stop.sh
```

Force free known ports after Compose shutdown:

```bash
TIJARA_FORCE_KILL_PORTS=1 bash scripts/dev-stop.sh
```

Python equivalent:

```bash
python3 scripts/tijara_services.py stop --force-kill-ports
```

Kill a single stuck port on macOS or Linux:

```bash
lsof -ti:8069 | xargs kill -9
lsof -ti:8072 | xargs kill -9
lsof -ti:9109 | xargs kill -9
lsof -ti:3000 | xargs kill -9
```

Kill a single stuck port on Windows PowerShell:

```powershell
netstat -ano | findstr :8069
taskkill /PID <pid_from_above> /F
```

Stop Docker services:

```bash
docker compose --env-file .env --env-file secrets/.env.secrets down
docker compose --env-file .env --env-file secrets/.env.secrets down -v
```

## Logs

| Action | Command |
|---|---|
| Watch Odoo logs | `make logs` |
| Watch Compose logs | `docker compose --env-file .env --env-file secrets/.env.secrets logs -f` |
| Watch generated script logs | `tail -f logs/*.log` |
| Last 100 lines of Odoo logs | `docker compose --env-file .env --env-file secrets/.env.secrets logs --tail 100 odoo` |
| Search runtime logs | `grep -i "error\|exception\|failed" logs/*.log` |

## Browser And Demo Capture

| Action | Command |
|---|---|
| Capture all spec-map screens | `node scripts/capture-screenshots.js` |
| Capture against staging URL | `TIJARA_SCREENSHOT_BASE_URL=https://staging.example.com node scripts/capture-screenshots.js` |
| Generate screenshot guide DOCX | `make screenshot-user-guide` |
| Record public route clips | `node scripts/record-demo.js` |
| Record against staging URL | `TIJARA_DEMO_BASE_URL=https://staging.example.com node scripts/record-demo.js` |
| Generate customer demo with voiceover | `make customer-demo-video` |
| Assemble clips with ffmpeg | `bash scripts/assemble-video.sh` |

## Local Production Evidence

| Action | Command |
|---|---|
| Start stack, upgrade PKR/GST modules, verify PKR/GST, seed users, run full browser E2E, export evidence | `make local-e2e-evidence` |
| Skip module upgrade during local evidence run | `TIJARA_LOCAL_E2E_UPGRADE=0 make local-e2e-evidence` |
| Limit local evidence to display routes | `TIJARA_E2E_SCOPE=display make local-e2e-evidence` |
| Limit local evidence to POS flows | `TIJARA_E2E_SCOPE=pos make local-e2e-evidence` |

## Browser Matrix Evidence

| Action | Command |
|---|---|
| Run default staging/protected browser matrix | `make browser-e2e-matrix` |
| Run only desktop Chromium and mobile touch | `TIJARA_BROWSER_E2E_PROJECTS="chromium-desktop mobile-touch" make browser-e2e-matrix` |
| Use a generated seed env file | `TIJARA_BROWSER_E2E_SEED_ENV=deploy/runtime/e2e-seed/<run-id>/e2e-seed.env make browser-e2e-matrix` |
| Include matrix in protected browser lane | `TIJARA_PROTECTED_E2E_MATRIX=1 make protected-browser-e2e` |

## Protected Release Evidence

| Action | Command |
|---|---|
| Protected runner bootstrap | `make protected-runner-bootstrap` |
| Protected first-run checklist | `make protected-first-run-checklist` |
| Protected service checks | `make protected-service-checks` |
| Protected browser E2E evidence | `make protected-browser-e2e` |
| Protected browser matrix evidence | `make protected-browser-e2e-matrix` |
| Protected POS checkout/refund/print/offline matrix evidence | `make protected-pos-matrix-evidence` |
| One-command protected release chain | `make protected-release-chain` |
| Local assumption-mode chain smoke | `TIJARA_PROTECTED_CHAIN_FLAGS="--run-id local-chain --target-environment local --tenant-artifact deploy/runtime/tenants/tijara_customer_001 --allow-assumptions --assume-provider all --non-strict --signoff-required-group ops" make protected-release-chain` |
| Protected release closure | `make protected-release-closure` |
| Protected evidence bundle score | `make protected-evidence-bundle-score` |
| Protected evidence bundle drift | `make protected-evidence-bundle-drift` |

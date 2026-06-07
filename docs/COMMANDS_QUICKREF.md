# Commands Quick Reference

## Terminal

| Action | Command |
|---|---|
| Start all core services | `bash scripts/dev-start.sh` |
| Start with hardware bridge | `TIJARA_DEV_START_HARDWARE=1 bash scripts/dev-start.sh` |
| Start with monitoring | `TIJARA_DEV_START_MONITORING=1 bash scripts/dev-start.sh` |
| Start, install suite, and seed POS demo | `TIJARA_DEV_INSTALL_SUITE=1 TIJARA_DEV_SEED_POS_DEMO=1 bash scripts/dev-start.sh` |
| Stop all Compose services | `bash scripts/dev-stop.sh` |
| Stop and force free known ports | `TIJARA_FORCE_KILL_PORTS=1 bash scripts/dev-stop.sh` |
| Restart everything | `bash scripts/dev-restart.sh` |
| Validate scaffold | `make validate` |
| Start Compose manually | `make up` |
| Stop Compose manually | `make down` |
| Show service status | `make ps` |
| Follow Odoo logs | `make logs` |
| Install suite modules | `make install-suite` |
| Seed POS demo | `make seed-pos-demo` |
| Run Odoo tests | `make test-odoo` |
| Run Playwright E2E | `make e2e` |
| Capture screenshots | `node scripts/capture-screenshots.js` |
| Record demo clips | `node scripts/record-demo.js` |
| Assemble demo video | `bash scripts/assemble-video.sh` |
| Run security audit | `make security-audit` |
| Run JS checks | `make js-check` |
| Start hardware bridge only | `make bridge-up` |
| Start monitoring profile | `make monitoring-up` |
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
| Start with hardware bridge | `powershell -File scripts/dev-start.ps1 -Hardware` |
| Start with monitoring | `powershell -File scripts/dev-start.ps1 -Monitoring` |
| Stop services | `powershell -File scripts/dev-stop.ps1` |
| Stop and force known ports | `powershell -File scripts/dev-stop.ps1 -ForceKillPorts` |

## Stop And Kill

Recommended:

```bash
bash scripts/dev-stop.sh
```

Force free known ports after Compose shutdown:

```bash
TIJARA_FORCE_KILL_PORTS=1 bash scripts/dev-stop.sh
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
| Record public route clips | `node scripts/record-demo.js` |
| Record against staging URL | `TIJARA_DEMO_BASE_URL=https://staging.example.com node scripts/record-demo.js` |
| Assemble clips with ffmpeg | `bash scripts/assemble-video.sh` |

## Protected Release Evidence

| Action | Command |
|---|---|
| Protected runner bootstrap | `make protected-runner-bootstrap` |
| Protected first-run checklist | `make protected-first-run-checklist` |
| Protected service checks | `make protected-service-checks` |
| Protected browser E2E evidence | `make protected-browser-e2e` |
| Protected release closure | `make protected-release-closure` |
| Protected evidence bundle score | `make protected-evidence-bundle-score` |

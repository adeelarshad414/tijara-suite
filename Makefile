ENV_FILE_ARGS :=
ifneq ($(wildcard .env),)
ENV_FILE_ARGS += --env-file .env
endif
ifneq ($(wildcard secrets/.env.secrets),)
ENV_FILE_ARGS += --env-file secrets/.env.secrets
endif

COMPOSE ?= docker compose $(ENV_FILE_ARGS)
DB ?= tijara_dev
TIJARA_MODULES := tijara_base,tijara_retail_core,tijara_inventory_intelligence,tijara_pos_pk,tijara_saas_control,tijara_pos_experience,tijara_analytics,tijara_vertical_pharmacy,tijara_vertical_restaurant,tijara_vertical_garments,tijara_vertical_electronics,tijara_vertical_cloth,tijara_vertical_superstore,tijara_vertical_grocery,tijara_vertical_bakery
DEMO_MODULES := tijara_demo_pos

.PHONY: up down logs shell restart ps validate js-check security-audit config install-suite seed-pos-demo seed-e2e test-odoo e2e bridge-up bridge-logs bridge-ps backup-db restore-drill provision-tenant provision-tenant-ops hardware-cert-smoke load-smoke container-scan dependency-scan monitoring-up monitoring-logs

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f odoo

shell:
	$(COMPOSE) exec odoo bash

restart:
	$(COMPOSE) restart odoo

ps:
	$(COMPOSE) ps

validate:
	bash scripts/validate_scaffold.sh

js-check:
	bash scripts/js_check.sh

security-audit:
	bash scripts/security_audit.sh

config:
	$(COMPOSE) config

install-suite:
	$(COMPOSE) run --rm odoo bash /usr/local/bin/tijara-start-odoo -d $(DB) -i $(TIJARA_MODULES) --without-demo --stop-after-init

seed-pos-demo:
	$(COMPOSE) run --rm odoo bash /usr/local/bin/tijara-start-odoo -d $(DB) -i $(DEMO_MODULES) --without-demo --stop-after-init

seed-e2e:
	bash scripts/seed_e2e_odoo.sh

test-odoo:
	bash scripts/run_odoo_tests.sh

e2e:
	npx playwright test

bridge-up:
	$(COMPOSE) --profile hardware up -d hardware_bridge

bridge-logs:
	$(COMPOSE) logs -f hardware_bridge

bridge-ps:
	$(COMPOSE) --profile hardware ps hardware_bridge

backup-db:
	bash deploy/postgres/backup.sh $(DB)

restore-drill:
	test -n "$(BACKUP)" || (echo "Usage: make restore-drill BACKUP=deploy/runtime/backups/file.dump" >&2; exit 1)
	CONFIRM_RESTORE_DRILL=YES bash deploy/postgres/restore-drill.sh "$(BACKUP)"

provision-tenant:
	test -n "$(TENANT_DB)" || (echo "Usage: make provision-tenant TENANT_DB=tijara_customer_001 TENANT_NAME='Customer 001'" >&2; exit 1)
	bash scripts/provision_tenant_db.sh "$(TENANT_DB)" "$(TENANT_NAME)"

provision-tenant-ops:
	test -n "$(TENANT_DB)" || (echo "Usage: make provision-tenant-ops TENANT_DB=tijara_customer_001 TENANT_DOMAIN=customer.example.com" >&2; exit 1)
	test -n "$(TENANT_DOMAIN)" || (echo "Usage: make provision-tenant-ops TENANT_DB=tijara_customer_001 TENANT_DOMAIN=customer.example.com" >&2; exit 1)
	python3 scripts/generate_tenant_ops_manifest.py "$(TENANT_DB)" "$(TENANT_DOMAIN)" --admin-email "$(ADMIN_EMAIL)"

hardware-cert-smoke:
	python3 scripts/hardware_certification_smoke.py

load-smoke:
	k6 run scripts/load_smoke.k6.js

container-scan:
	bash scripts/container_scan.sh

dependency-scan:
	bash scripts/dependency_scan.sh

monitoring-up:
	$(COMPOSE) --profile monitoring up -d prometheus blackbox alertmanager loki grafana

monitoring-logs:
	$(COMPOSE) logs -f prometheus blackbox alertmanager loki grafana

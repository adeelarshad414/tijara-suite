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

.PHONY: up down logs shell restart ps validate js-check security-audit config install-suite seed-pos-demo seed-e2e staging-e2e-profile e2e-execution-evidence test-odoo e2e e2e-staging protected-browser-e2e ops-staging operations-release-bundle production-ops-readiness ops-tool-evidence release-candidate signoff-pack check-release-readiness staging-release-signoff production-deployment-gate production-rollback production-smoke tenant-smoke tenant-rollout protected-runner-bootstrap protected-runbook-handoff protected-first-run-checklist protected-runner-preflight protected-service-checks protected-provider-readiness protected-payment-lifecycle-evidence protected-offline-replay-evidence protected-post-run-verification github-artifact-metadata github-step-summary protected-artifact-summary certification-evidence protected-certification-evidence psp-readiness-evidence psp-fixture-smoke fbr-readiness-evidence fbr-fixture-smoke monitoring-evidence incident-runbook-evidence release-retention-evidence secret-manager-evidence secret-runtime-evidence deployment-environment-evidence tenant-ops-evidence load-evidence load-profile load-enterprise-surfaces load-profile-matrix-evidence bridge-up bridge-logs bridge-ps backup-db restore-drill provision-tenant provision-tenant-ops hardware-cert-smoke load-smoke container-scan dependency-scan monitoring-up monitoring-logs monitoring-drill

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

staging-e2e-profile:
	python3 scripts/export_staging_e2e_profile.py

e2e-execution-evidence:
	python3 scripts/export_e2e_execution_evidence.py

test-odoo:
	bash scripts/run_odoo_tests.sh

e2e:
	npx playwright test

e2e-staging:
	bash scripts/run_staging_e2e.sh

protected-browser-e2e:
	bash scripts/run_protected_browser_e2e_evidence.sh

ops-staging:
	bash scripts/run_staging_ops_checks.sh

operations-release-bundle:
	python3 scripts/run_operations_release_bundle.py

production-ops-readiness:
	python3 scripts/export_production_ops_readiness.py

ops-tool-evidence:
	python3 scripts/export_ops_tool_evidence.py

release-candidate:
	bash scripts/run_release_candidate_gate.sh

signoff-pack:
	python3 scripts/generate_signoff_pack.py

check-release-readiness:
	test -n "$(READINESS)" || (echo "Usage: make check-release-readiness READINESS=deploy/runtime/signoff-packages/<run-id>/release-readiness.json" >&2; exit 1)
	python3 scripts/check_release_readiness.py "$(READINESS)"

staging-release-signoff:
	bash scripts/run_staging_release_signoff.sh

production-deployment-gate:
	test -n "$(READINESS)" || (echo "Usage: make production-deployment-gate READINESS=deploy/runtime/signoff-packages/<run-id>/release-readiness.json" >&2; exit 1)
	python3 scripts/run_production_deployment_gate.py "$(READINESS)"

production-rollback:
	test -n "$(DEPLOYMENT_GATE)" || (echo "Usage: make production-rollback DEPLOYMENT_GATE=deploy/runtime/deployment-gates/<run-id>/deployment-decision.json" >&2; exit 1)
	python3 scripts/run_production_rollback.py "$(DEPLOYMENT_GATE)"

production-smoke:
	python3 scripts/run_production_smoke.py

tenant-smoke:
	python3 scripts/run_tenant_smoke.py

tenant-rollout:
	python3 scripts/run_tenant_rollout.py

protected-runner-bootstrap:
	bash scripts/bootstrap_protected_runner.sh

protected-runbook-handoff:
	python3 scripts/export_protected_runbook_handoff.py

protected-first-run-checklist:
	python3 scripts/export_protected_first_run_checklist.py

protected-runner-preflight:
	python3 scripts/export_protected_runner_preflight.py

protected-service-checks:
	python3 scripts/export_protected_service_checks.py

protected-provider-readiness:
	python3 scripts/export_protected_provider_readiness.py

protected-payment-lifecycle-evidence:
	python3 scripts/export_protected_payment_lifecycle_evidence.py

protected-offline-replay-evidence:
	python3 scripts/export_protected_offline_replay_evidence.py

protected-post-run-verification:
	python3 scripts/export_protected_post_run_verification.py

github-artifact-metadata:
	python3 scripts/export_github_artifact_metadata.py

github-step-summary:
	python3 scripts/export_github_step_summary.py

protected-artifact-summary:
	python3 scripts/export_protected_artifact_summary.py

certification-evidence:
	python3 scripts/collect_certification_evidence.py

protected-certification-evidence:
	bash scripts/run_protected_certification_evidence.sh

psp-readiness-evidence:
	python3 scripts/export_psp_readiness.py

psp-fixture-smoke:
	python3 scripts/psp_settlement_fixture_smoke.py

fbr-readiness-evidence:
	python3 scripts/export_fbr_readiness.py

fbr-fixture-smoke:
	python3 scripts/fbr_provider_fixture_smoke.py

monitoring-evidence:
	python3 scripts/export_monitoring_evidence.py

incident-runbook-evidence:
	python3 scripts/export_incident_runbook_evidence.py

release-retention-evidence:
	python3 scripts/export_release_retention_evidence.py

secret-manager-evidence:
	python3 scripts/export_secret_manager_evidence.py

secret-runtime-evidence:
	python3 scripts/export_secret_runtime_evidence.py

deployment-environment-evidence:
	python3 scripts/export_deployment_environment_evidence.py

tenant-ops-evidence:
	python3 scripts/export_tenant_ops_evidence.py

load-evidence:
	python3 scripts/export_load_evidence.py

load-profile:
	bash scripts/run_load_profile.sh $${TIJARA_LOAD_PROFILE:-smoke}

load-enterprise-surfaces:
	bash scripts/run_load_profile.sh enterprise-surfaces

load-profile-matrix-evidence:
	python3 scripts/export_load_profile_matrix.py

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

monitoring-drill:
	python3 scripts/staging_monitoring_drill.py

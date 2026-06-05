import json

from odoo import fields, models
from odoo.exceptions import UserError


class TijaraTenantProvisionRequest(models.Model):
    _name = "tijara.tenant.provision.request"
    _description = "Tijara Tenant Provisioning Request"
    _order = "requested_at desc, id desc"

    name = fields.Char(default="New", required=True, copy=False)
    tenant_name = fields.Char(required=True)
    database_name = fields.Char(required=True)
    subscription_id = fields.Many2one("tijara.saas.subscription", required=True)
    plan_id = fields.Many2one(related="subscription_id.plan_id", store=True)
    customer_id = fields.Many2one(related="subscription_id.customer_id", store=True)
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )
    requested_by_id = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        required=True,
    )
    requested_at = fields.Datetime(default=fields.Datetime.now)
    approved_at = fields.Datetime()
    provisioned_at = fields.Datetime()
    primary_domain = fields.Char()
    ingress_class = fields.Char(default="nginx")
    admin_login = fields.Char(default="admin")
    admin_email = fields.Char()
    backup_policy = fields.Selection(
        [
            ("daily", "Daily"),
            ("hourly", "Hourly"),
            ("custom", "Custom"),
        ],
        default="daily",
        required=True,
    )
    monitoring_enabled = fields.Boolean(default=True)
    dns_provider = fields.Char()
    operations_manifest = fields.Text()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("approved", "Approved"),
            ("provisioning", "Provisioning"),
            ("provisioned", "Provisioned"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
    )
    provisioning_runbook = fields.Text(
        default=(
            "1. Create isolated tenant database.\n"
            "2. Install Tijara suite modules.\n"
            "3. Apply subscription feature flags.\n"
            "4. Configure backup, monitoring, and admin user.\n"
            "5. Run POS, inventory, receipt, and display smoke tests."
        )
    )
    error_message = fields.Text()
    notes = fields.Text()

    def action_approve(self):
        for request in self:
            if request.state != "draft":
                raise UserError("Only draft provisioning requests can be approved.")
            if request.name == "New":
                request.name = "TPR-%05d" % request.id
            request.write({"state": "approved", "approved_at": fields.Datetime.now()})

    def action_start_provisioning(self):
        self.write({"state": "provisioning"})

    def action_mark_provisioned(self):
        for request in self:
            request.subscription_id.write(
                {
                    "tenant_name": request.tenant_name,
                    "database_name": request.database_name,
                    "state": "active",
                }
            )
        self.write({"state": "provisioned", "provisioned_at": fields.Datetime.now()})

    def _tijara_operations_manifest(self):
        self.ensure_one()
        domain = self.primary_domain or "%s.example.com" % self.database_name.replace("_", "-")
        tenant_slug = self.database_name.replace("_", "-")
        return {
            "context": {
                "generator": "addons/tijara_saas_control/models/tenant_provision_request.py",
                "artifact_schema": "tenant-ops/v1",
            },
            "tenant": {
                "name": self.tenant_name,
                "database": self.database_name,
                "domain": domain,
                "subscription": self.subscription_id.name,
                "plan": self.plan_id.name,
                "customer": self.customer_id.display_name or "",
            },
            "dns": {
                "provider": self.dns_provider or "manual",
                "hostname": domain,
                "target": "tijara-ingress",
            },
            "ingress": {
                "class": self.ingress_class or "nginx",
                "host": domain,
                "database_header": self.database_name,
                "namespace": "tijara",
                "service_name": "odoo",
                "service_port": "8069",
                "tls_issuer": "letsencrypt-prod",
                "tls_secret": "%s-tls" % tenant_slug,
            },
            "admin": {
                "login": self.admin_login or "admin",
                "email": self.admin_email or "",
                "bootstrap_secret_ref": "secret-manager:%s/admin-bootstrap" % tenant_slug,
            },
            "backup": {
                "policy": self.backup_policy,
                "database": self.database_name,
                "retention_days": 30,
                "restore_drill_required": True,
                "restore_drill_ref": "",
            },
            "monitoring": {
                "enabled": self.monitoring_enabled,
                "blackbox_url": "https://%s/web/login" % domain,
                "alert_route": "",
                "dashboard_ref": "",
                "labels": {
                    "tenant_db": self.database_name,
                    "plan": self.plan_id.name,
                },
            },
            "smoke_checks": [
                "tenant-web-login",
                "database-isolation-header",
                "admin-login-created",
                "module-install-complete",
                "subscription-feature-flags-applied",
                "pos-checkout-smoke",
                "inventory-adjustment-smoke",
                "receipt-render-smoke",
                "display-route-smoke",
                "backup-job-registered",
                "monitoring-target-healthy",
            ],
            "artifacts": {
                "nginx_location": "nginx-location.conf",
                "kubernetes_ingress": "k8s-ingress.yaml",
                "external_dns_record": "external-dns-record.json",
                "cert_manager_certificate": "cert-manager-certificate.yaml",
                "backup_policy": "backup-policy.json",
                "prometheus_blackbox_target": "prometheus-blackbox-target.json",
                "admin_bootstrap": "admin-bootstrap.md",
                "smoke_checklist": "smoke-checklist.md",
            },
        }

    def action_generate_operations_manifest(self):
        for request in self:
            request.operations_manifest = json.dumps(
                request._tijara_operations_manifest(),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )

    def action_fail(self):
        self.write({"state": "failed"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

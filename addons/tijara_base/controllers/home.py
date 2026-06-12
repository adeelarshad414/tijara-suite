from odoo import http
from odoo.http import request


class TijaraHomeController(http.Controller):
    def _has_group(self, xmlid):
        try:
            return request.env.user.has_group(xmlid)
        except Exception:
            return False

    def _action_url(self, xmlid, fallback="/odoo"):
        action = request.env.ref(xmlid, raise_if_not_found=False)
        if action:
            return f"/web#action={action.id}"
        return fallback

    def _count(self, model_name, domain=None):
        try:
            return request.env[model_name].sudo().search_count(domain or [])
        except Exception:
            return 0

    def _tenant_brand(self, company):
        primary = company.tijara_brand_primary or "#1f7a8c"
        secondary = company.tijara_brand_secondary or "#2d6a4f"
        accent = company.tijara_brand_accent or "#d18f1e"
        return {
            "mode": "tenant",
            "name": company.name or "Tijara Suite",
            "eyebrow": company.tijara_brand_tagline or "Tenant business workspace",
            "headline": company.tijara_home_headline
            or f"Welcome back to {company.name or 'your business'}",
            "subtitle": company.tijara_home_subtitle
            or "Run POS, inventory, ecommerce, staff permissions, reports, and daily operations from one clean workspace.",
            "primary": primary,
            "secondary": secondary,
            "accent": accent,
            "logo_url": f"/web/binary/company_logo?dbname={request.db}" if request.db else "/web/binary/company_logo",
            "mark": (company.name or "Tijara")[:2].upper(),
        }

    def _platform_brand(self):
        return {
            "mode": "platform",
            "name": "Tijara Platform Console",
            "eyebrow": "SaaS owner workspace",
            "headline": "Operate tenants, subscriptions, release evidence, and production controls.",
            "subtitle": "A focused command center for platform superadmins managing customer onboarding, feature plans, billing evidence, infrastructure readiness, and security operations.",
            "primary": "#246f7a",
            "secondary": "#334155",
            "accent": "#c8861f",
            "logo_url": False,
            "mark": "TP",
        }

    def _platform_cards(self):
        return [
            {
                "title": "Tenant Provisioning",
                "text": "Create and review database-per-tenant onboarding requests.",
                "url": self._action_url("tijara_saas_control.action_tijara_tenant_provision_request"),
                "metric": self._count("tijara.tenant.provision.request"),
                "metric_label": "requests",
            },
            {
                "title": "SaaS Plans",
                "text": "Control plan tiers, feature bundles, and subscription scope.",
                "url": self._action_url("tijara_saas_control.action_tijara_saas_plan"),
                "metric": self._count("tijara.saas.plan"),
                "metric_label": "plans",
            },
            {
                "title": "Subscriptions",
                "text": "Review customer subscription status, billing, dunning, and suspension.",
                "url": self._action_url("tijara_saas_control.action_tijara_saas_subscription"),
                "metric": self._count("tijara.saas.subscription"),
                "metric_label": "records",
            },
            {
                "title": "Payments And Webhooks",
                "text": "Check PSP webhook events, settlements, refunds, and chargebacks.",
                "url": self._action_url("tijara_saas_control.action_tijara_saas_payment_webhook_event"),
                "metric": self._count("tijara.payment.webhook.event"),
                "metric_label": "events",
            },
            {
                "title": "Analytics Dashboards",
                "text": "Open operational dashboards, KPIs, reports, and trend history.",
                "url": self._action_url("tijara_analytics.action_tijara_analytics_dashboard"),
                "metric": self._count("tijara.analytics.dashboard"),
                "metric_label": "dashboards",
            },
            {
                "title": "Release Evidence",
                "text": "Review readiness, certification, monitoring, and protected runner evidence.",
                "url": "/odoo",
                "metric": self._count("res.company"),
                "metric_label": "companies",
            },
        ]

    def _tenant_admin_cards(self):
        return [
            {
                "title": "User Role Assignments",
                "text": "Assign multiple business roles to users such as cashier plus inventory.",
                "url": self._action_url("tijara_base.action_tijara_user_role_assignment"),
                "metric": self._count("tijara.user.role.assignment"),
                "metric_label": "assignments",
            },
            {
                "title": "Business Branding",
                "text": "Set tenant colors, logo, Pakistan identifiers, tax, charges, and receipt language.",
                "url": "/web#model=res.company&view_type=form",
                "metric": self._count("res.users", [("share", "=", False)]),
                "metric_label": "staff users",
            },
            {
                "title": "POS And Retail Ops",
                "text": "Open refunds, exchanges, cash shifts, hardware, templates, and cashier controls.",
                "url": self._action_url("tijara_retail_core.action_tijara_cash_shift"),
                "metric": self._count("pos.config"),
                "metric_label": "POS configs",
            },
            {
                "title": "Inventory Intelligence",
                "text": "Review low stock, expiry, racks, shelves, bins, and warehouse health.",
                "url": self._action_url("tijara_inventory_intelligence.action_tijara_inventory_alert"),
                "metric": self._count("tijara.inventory.alert"),
                "metric_label": "alerts",
            },
            {
                "title": "Displays And Promotions",
                "text": "Manage kiosk, menu, deals, queue, and customer-facing display content.",
                "url": self._action_url("tijara_pos_experience.action_tijara_display_screen"),
                "metric": self._count("tijara.display.screen"),
                "metric_label": "screens",
            },
            {
                "title": "Analytics And Reports",
                "text": "Track sales, inventory, loyalty, expenses, salary, tax, and vertical KPIs.",
                "url": self._action_url("tijara_analytics.action_tijara_analytics_dashboard"),
                "metric": self._count("tijara.analytics.snapshot"),
                "metric_label": "snapshots",
            },
        ]

    def _staff_cards(self):
        return [
            {
                "title": "Start Work",
                "text": "Open the Odoo app shell for POS, inventory, sales, or assigned daily tasks.",
                "url": "/odoo",
                "metric": self._count("res.users", [("id", "=", request.env.user.id)]),
                "metric_label": "signed in",
            },
            {
                "title": "Customer Records",
                "text": "Find walk-in, B2C, B2B, loyalty, and contact history records.",
                "url": "/web#model=res.partner&view_type=list",
                "metric": self._count("res.partner"),
                "metric_label": "contacts",
            },
            {
                "title": "Inventory Alerts",
                "text": "Check stock, expiry, and placement issues if your role allows inventory access.",
                "url": self._action_url("tijara_inventory_intelligence.action_tijara_inventory_alert"),
                "metric": self._count("tijara.inventory.alert"),
                "metric_label": "alerts",
            },
            {
                "title": "Queue And Orders",
                "text": "Follow kiosk, pickup, delivery, restaurant, and ecommerce queue status.",
                "url": self._action_url("tijara_pos_experience.action_tijara_queue_ticket"),
                "metric": self._count("tijara.queue.ticket"),
                "metric_label": "tickets",
            },
        ]

    @http.route("/tijara/home", type="http", auth="user", website=True, sitemap=False)
    def home(self, **kw):
        company = request.env.company
        is_platform_admin = self._has_group("base.group_system")
        is_tenant_admin = self._has_group("tijara_base.group_tijara_manager")
        if is_platform_admin:
            brand = self._platform_brand()
            persona = "Platform Superadmin"
            cards = self._platform_cards()
            highlights = ["Tenant provisioning", "SaaS plans", "Release evidence", "Security and monitoring"]
        elif is_tenant_admin:
            brand = self._tenant_brand(company)
            persona = "Tenant Admin"
            cards = self._tenant_admin_cards()
            highlights = ["Users and RBAC", "POS and inventory", "Displays and ecommerce", "Reports and approvals"]
        else:
            brand = self._tenant_brand(company)
            persona = "Team Workspace"
            cards = self._staff_cards()
            highlights = ["Assigned apps", "Customers", "Inventory alerts", "Queue and orders"]
        values = {
            "brand": brand,
            "cards": cards,
            "persona": persona,
            "highlights": highlights,
            "company": company,
            "user": request.env.user,
        }
        return request.render("tijara_base.tijara_home_page", values)

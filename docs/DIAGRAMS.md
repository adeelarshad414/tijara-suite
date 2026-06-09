# Tijara Suite Architecture And Flow Diagrams

This document is the canonical visual design pack for Tijara Suite. Keep it
updated whenever deployment topology, module boundaries, user journeys, runtime
flows, or production operations change.

The diagrams use Mermaid so they remain source-controlled, open-source friendly,
and renderable in GitHub-compatible Markdown viewers.

## Diagram Index

| Diagram | Purpose |
|---|---|
| Deployment Architecture | Production SaaS and edge hardware topology |
| Local Development Deployment | Docker Compose developer topology |
| System Context | Users, external systems, and Tijara boundaries |
| Component Architecture | Runtime services and internal responsibilities |
| Odoo Module Map | Custom addon dependency and ownership map |
| Data Model UML | Core domain model relationships |
| POS Checkout User Flow | Cashier sales, B2B/B2C, discount, payment, print |
| Ecommerce Checkout User Flow | Storefront catalog, checkout, sale order, queue |
| Restaurant And Kiosk Activity | Dine-in, takeaway, pickup, delivery, queue |
| Offline POS Activity | Browser capture, replay, conflict review |
| Hardware Print Sequence | POS receipt print through bridge to device |
| Tenant Provisioning Activity | Tenant database, ingress, admin, backup, monitor |
| Analytics Pipeline | KPI collectors, snapshots, dashboards, reports |
| Release And Evidence Flow | CI, staging, evidence, sign-off, rollback |

## Deployment Architecture

```mermaid
flowchart TB
    UserWeb["Business users\nCashier, admin, manager"]
    PublicUser["Customers\nKiosk, ecommerce, display"]
    Browser["Browser or touch device"]
    Kiosk["Kiosk / display browser"]
    Proxy["HTTPS reverse proxy\nNginx or ingress"]
    Odoo["Odoo Community app\nTijara addons"]
    Postgres[("PostgreSQL\nDatabase per tenant")]
    Filestore[("Odoo filestore\nReports, attachments")]
    Bridge["Local hardware bridge\nShop machine"]
    Devices["Printers, scanners,\ncash drawer, scale,\ncustomer display"]
    Monitoring["Prometheus, Blackbox,\nGrafana, Alertmanager"]
    Backup["Backup and restore\nobject storage or vault"]
    PSP["Payment providers\nJazzCash, Easypaisa, Stripe"]
    FBR["FBR certified provider\nPOS invoice adapter"]
    SecretStore["Secret manager\nVault, SOPS, K8s secrets"]

    UserWeb --> Browser
    PublicUser --> Kiosk
    Browser --> Proxy
    Kiosk --> Proxy
    Proxy --> Odoo
    Odoo --> Postgres
    Odoo --> Filestore
    Odoo --> Bridge
    Bridge --> Devices
    Odoo --> PSP
    Odoo --> FBR
    Odoo --> SecretStore
    Odoo --> Monitoring
    Proxy --> Monitoring
    Postgres --> Backup
    Filestore --> Backup
```

## Local Development Deployment

```mermaid
flowchart LR
    Dev["Developer workstation"]
    Browser["Browser\nlocalhost:8069"]
    Compose["Docker Compose"]
    Odoo["odoo service\nOdoo 19 + addons mount"]
    DB[("db service\nPostgreSQL 16")]
    Bridge["hardware-bridge profile\nlocalhost:9109"]
    Monitoring["monitoring profile\nPrometheus/Grafana"]
    Env[".env\nnon-secret config"]
    Secrets["secrets/.env.secrets\nlocal secrets"]
    Docs["docs and evidence\nignored runtime folders"]

    Dev --> Browser
    Dev --> Compose
    Compose --> Odoo
    Compose --> DB
    Compose -. optional .-> Bridge
    Compose -. optional .-> Monitoring
    Env --> Compose
    Secrets --> Compose
    Odoo --> DB
    Odoo --> Bridge
    Dev --> Docs
```

## System Context

```mermaid
flowchart TB
    PlatformAdmin["Platform superadmin"]
    TenantAdmin["Tenant admin"]
    Cashier["Cashier"]
    Inventory["Inventory manager"]
    Accountant["Accountant"]
    Restaurant["Restaurant operator"]
    Ecommerce["Ecommerce manager"]
    Customer["Customer"]
    PublicDisplays["Customer display,\nqueue, menu, deals"]
    Tijara["Tijara Suite\nOdoo Community SaaS"]
    PSP["Payment providers"]
    FBR["FBR provider"]
    Hardware["Store hardware"]
    DevOps["DevOps and QA tools"]

    PlatformAdmin --> Tijara
    TenantAdmin --> Tijara
    Cashier --> Tijara
    Inventory --> Tijara
    Accountant --> Tijara
    Restaurant --> Tijara
    Ecommerce --> Tijara
    Customer --> Tijara
    Tijara --> PublicDisplays
    Tijara --> PSP
    Tijara --> FBR
    Tijara --> Hardware
    DevOps --> Tijara
```

## Component Architecture

```mermaid
flowchart TB
    subgraph Client["Client Surfaces"]
        POS["POS browser"]
        BackOffice["Odoo back office"]
        Kiosk["Kiosk"]
        Storefront["Ecommerce storefront"]
        Displays["Customer, queue,\nmenu, deals displays"]
    end

    subgraph Odoo["Odoo Community Runtime"]
        Controllers["HTTP/JSON controllers"]
        CoreModels["Odoo core models\nPOS, Sale, Stock, Account"]
        TijaraModels["Tijara custom models"]
        QWeb["QWeb reports and templates"]
        SaaS["Feature flags and subscriptions"]
        Analytics["KPI collectors and dashboards"]
    end

    subgraph Infrastructure["Infrastructure"]
        DB[("PostgreSQL")]
        Filestore[("Filestore")]
        Bridge["Hardware bridge"]
        Monitoring["Monitoring"]
        Backup["Backups"]
    end

    POS --> Controllers
    BackOffice --> Controllers
    Kiosk --> Controllers
    Storefront --> Controllers
    Displays --> Controllers
    Controllers --> TijaraModels
    Controllers --> CoreModels
    TijaraModels --> CoreModels
    TijaraModels --> SaaS
    TijaraModels --> Analytics
    TijaraModels --> QWeb
    CoreModels --> DB
    TijaraModels --> DB
    QWeb --> Filestore
    TijaraModels --> Bridge
    Odoo --> Monitoring
    DB --> Backup
    Filestore --> Backup
```

## Odoo Module Map

```mermaid
flowchart TB
    Base["tijara_base\nPakistan localization"]
    Retail["tijara_retail_core\nRetail operations"]
    Inventory["tijara_inventory_intelligence\nStock alerts and placement"]
    POSPK["tijara_pos_pk\nReceipts, FBR queue"]
    Experience["tijara_pos_experience\nKiosk, displays, queue"]
    Analytics["tijara_analytics\nDashboards and KPI history"]
    SaaS["tijara_saas_control\nPlans and feature flags"]
    Ecommerce["tijara_ecommerce\nStorefront and online checkout"]
    Demo["tijara_demo_pos\nDemo seed"]
    Verticals["Vertical modules\npharmacy, restaurant,\ngrocery, bakery, cloth,\ngarments, shoes, electronics"]

    Base --> Retail
    Base --> Inventory
    Base --> POSPK
    Base --> SaaS
    Retail --> POSPK
    Retail --> Experience
    Retail --> Analytics
    Inventory --> Analytics
    POSPK --> Experience
    SaaS --> Experience
    SaaS --> Ecommerce
    Experience --> Ecommerce
    Analytics --> Ecommerce
    Retail --> Ecommerce
    Base --> Verticals
    Retail --> Verticals
    Experience --> Demo
    Ecommerce --> Demo
    Verticals --> Demo
```

## Data Model UML

```mermaid
classDiagram
    class ResCompany {
        currency_pkr
        gst_policy
        delivery_charge_policy
        cafe_service_charge_policy
        saas_feature_checks
    }
    class SaasSubscription {
        tenant_name
        database_name
        state
    }
    class SaasPlan {
        feature_ids
        price
    }
    class ProductTemplate {
        b2c_price
        b2b_price
        urdu_name
        ecommerce_published
        vertical_tag
    }
    class EcommerceChannel {
        code
        slug
        fulfillment_methods
        payment_methods
        auto_queue
        default_delivery_provider
    }
    class DeliveryProvider {
        code
        provider_type
        service_level
        dry_run
        adapter_mode
        label_format
        webhook_signature_mode
        tracking_url_template
    }
    class DeliveryEvent {
        event_type
        direction
        status
        signature_status
        payload_hash
    }
    class SaleOrder {
        ecommerce_channel
        audience
        fulfillment_method
        payment_status
        pickup_code
        tracking_token
        delivery_status
        delivery_adapter_state
        delivery_provider_reference
    }
    class QueueTicket {
        queue_number
        source
        state
    }
    class PosOrder {
        receipt_profile
        invoice_barcode
        bridge_job
    }
    class OfflinePosQueue {
        source_order_uid
        replay_state
        conflict_reason
    }
    class ReceiptProfile {
        template_scope
        print_language
        header_footer
    }
    class AnalyticsSnapshot {
        business_area
        metric_code
        value
        snapshot_date
    }
    class HardwareDevice {
        device_type
        connection_type
        printer_language
        bridge_endpoint
    }

    ResCompany "1" --> "*" SaasSubscription
    SaasPlan "1" --> "*" SaasSubscription
    EcommerceChannel "1" --> "*" SaleOrder
    DeliveryProvider "1" --> "*" SaleOrder
    DeliveryProvider "1" --> "*" DeliveryEvent
    SaleOrder "1" --> "*" DeliveryEvent
    EcommerceChannel "*" --> "*" DeliveryProvider
    ProductTemplate "*" --> "*" EcommerceChannel
    SaleOrder "1" --> "0..1" QueueTicket
    ProductTemplate "1" --> "*" PosOrder
    PosOrder "1" --> "*" OfflinePosQueue
    ReceiptProfile "1" --> "*" PosOrder
    ReceiptProfile "1" --> "*" ProductTemplate
    ResCompany "1" --> "*" AnalyticsSnapshot
    HardwareDevice "1" --> "*" PosOrder
```

## POS Checkout User Flow

```mermaid
flowchart TD
    Start(["Cashier opens POS"])
    Session["Verify active session\nand cashier permissions"]
    Scan["Scan barcode or search product"]
    PriceMode{"B2B or B2C?"}
    Customer["Select or create customer\nwhen needed"]
    Cart["Update cart lines\nquantity, taxes, discounts"]
    Discount{"Bill discount?"}
    SyncDiscount["Sync percent and amount"]
    Pay["Select payment method"]
    Validate["Validate sale"]
    Receipt["Render bilingual receipt\nQR/barcode and policy"]
    Print{"Printer configured?"}
    Bridge["Send signed print job\nto hardware bridge"]
    Done(["Sale completed"])

    Start --> Session --> Scan --> PriceMode
    PriceMode --> Customer --> Cart
    Cart --> Discount
    Discount -- yes --> SyncDiscount --> Pay
    Discount -- no --> Pay
    Pay --> Validate --> Receipt --> Print
    Print -- yes --> Bridge --> Done
    Print -- no --> Done
```

## Ecommerce Checkout User Flow

```mermaid
flowchart TD
    Open(["Customer opens storefront"])
    Catalog["Load catalog\nPKR, Urdu, B2C/B2B, stock"]
    Audience{"Audience mode"}
    Cart["Add products to cart"]
    Fulfillment{"Fulfillment"}
    Customer["Enter customer\nmobile and address"]
    Payment["Select payment method"]
    Policy["Apply GST, delivery,\nservice, payment-tax policy"]
    CreateSO["Create Odoo sale order"]
    Queue{"Pickup or delivery queue?"}
    Ticket["Create queue ticket"]
    Provider{"Delivery or courier?"}
    Shipment["Assign dry-run/certified\nprovider tracking"]
    Track["Customer tracks order\nby token or pickup/mobile"]
    Review["Ecommerce manager reviews\norder, queue, and delivery"]
    Done(["Order ready for fulfillment"])

    Open --> Catalog --> Audience
    Audience --> Cart --> Fulfillment --> Customer --> Payment --> Policy --> CreateSO
    CreateSO --> Queue
    Queue -- yes --> Ticket --> Provider
    Queue -- no --> Provider
    Provider -- yes --> Shipment --> Track --> Review --> Done
    Provider -- no --> Track --> Review --> Done
```

## Restaurant And Kiosk Activity

```mermaid
flowchart TD
    Start(["Customer starts kiosk"])
    Type{"Order type"}
    DineIn["Assign table or area"]
    Takeaway["Takeaway counter flow"]
    Pickup["Pickup code flow"]
    Delivery["Delivery address and charge"]
    Menu["Select menu items and deals"]
    Pay["Select payment method"]
    Order["Create kiosk order"]
    Queue["Create queue ticket"]
    Kitchen["Kitchen prepares order"]
    Ready["Mark ready or called"]
    Close(["Close after pickup/payment"])

    Start --> Type
    Type -- dine in --> DineIn --> Menu
    Type -- takeaway --> Takeaway --> Menu
    Type -- pickup --> Pickup --> Menu
    Type -- delivery --> Delivery --> Menu
    Menu --> Pay --> Order --> Queue --> Kitchen --> Ready --> Close
```

## Offline POS Activity

```mermaid
stateDiagram-v2
    [*] --> Online
    Online --> OfflineCapture: network issue
    OfflineCapture --> StoredLocally: cashier keeps selling
    StoredLocally --> ReplayPending: connection returns
    ReplayPending --> Replayed: server accepts order
    ReplayPending --> Conflict: duplicate or validation issue
    Conflict --> Review: back office opens conflict screen
    Review --> Replayed: retry or merge
    Review --> Cancelled: cancel
    Review --> Duplicate: mark duplicate
    Replayed --> [*]
    Cancelled --> [*]
    Duplicate --> [*]
```

## Hardware Print Sequence

```mermaid
sequenceDiagram
    participant Cashier
    participant POS as POS Browser
    participant Odoo as Odoo Backend
    participant Bridge as Hardware Bridge
    participant Printer as Printer/Drawer/Display

    Cashier->>POS: Validate sale
    POS->>Odoo: Request receipt render
    Odoo->>Odoo: Apply receipt profile and bilingual template
    POS->>Odoo: Submit print request
    Odoo->>Bridge: Signed bridge job
    Bridge->>Bridge: Validate HMAC and adapter profile
    Bridge->>Printer: ESC/POS, CUPS, ZPL, drawer pulse, or display update
    Printer-->>Bridge: Device response
    Bridge-->>Odoo: Job id, status, result JSON
    Odoo-->>POS: Printed status
```

## Tenant Provisioning Activity

```mermaid
flowchart TD
    Request(["Tenant provision request"])
    Validate["Validate plan, owner,\ndomain, admin email"]
    Database["Create tenant database"]
    Install["Install Tijara modules"]
    Seed["Apply localization,\nfeatures, admin user"]
    DNS["Create DNS and ingress"]
    Backup["Register backup policy"]
    Monitoring["Register monitoring probes"]
    Smoke["Run tenant smoke tests"]
    Decision{"Smoke passed?"}
    Active["Mark tenant active"]
    Blocked["Block rollout and attach evidence"]

    Request --> Validate --> Database --> Install --> Seed --> DNS --> Backup --> Monitoring --> Smoke --> Decision
    Decision -- yes --> Active
    Decision -- no --> Blocked
```

## Analytics Pipeline

```mermaid
flowchart LR
    POS["POS orders"]
    Sales["Sales orders"]
    Inventory["Stock moves and alerts"]
    BackOffice["Expenses and salaries"]
    Loyalty["Customers and loyalty"]
    Ecommerce["Ecommerce orders"]
    Collectors["Automated KPI collectors"]
    Snapshots[("tijara.analytics.snapshot")]
    Dashboards["Dashboards"]
    Reports["Report catalog\npivot, graph, list"]

    POS --> Collectors
    Sales --> Collectors
    Inventory --> Collectors
    BackOffice --> Collectors
    Loyalty --> Collectors
    Ecommerce --> Collectors
    Collectors --> Snapshots
    Snapshots --> Dashboards
    Snapshots --> Reports
```

## Release And Evidence Flow

```mermaid
flowchart TD
    Code["Code and docs change"]
    Validate["Local validation\nXML, JS, Python, tests"]
    OdooTests["Odoo transaction tests"]
    Browser["Browser E2E\npublic, authenticated, matrix"]
    Ops["Ops evidence\nbackup, monitoring, load, security"]
    Cert["External certification\nhardware, PSP, FBR"]
    Bundle["Release evidence bundle"]
    Gate{"Release gate"}
    Promote["Promote to staging/production"]
    Rollback["Rollback runbook ready"]
    Block["Block release and fix gaps"]

    Code --> Validate --> OdooTests --> Browser --> Ops --> Cert --> Bundle --> Gate
    Gate -- approved --> Promote --> Rollback
    Gate -- blocked --> Block
```

## Diagram Ownership

- Product and architecture owner: keep system, module, UML, and user-flow
  diagrams current.
- DevOps owner: keep deployment, tenant provisioning, release, monitoring,
  backup, and rollback diagrams current.
- QA owner: keep E2E, activity, and evidence diagrams aligned with test
  coverage.
- Business owner: review user flows for POS, ecommerce, restaurant, inventory,
  back office, and reporting completeness.

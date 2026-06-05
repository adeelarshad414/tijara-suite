import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = (__ENV.TIJARA_BASE_URL || "http://localhost:8069").replace(/\/+$/, "");
const DISPLAY_SLUG = __ENV.TIJARA_DISPLAY_SLUG || "";
const KIOSK_SLUG = __ENV.TIJARA_KIOSK_SLUG || "";
const CUSTOMER_DISPLAY_SLUG = __ENV.TIJARA_CUSTOMER_DISPLAY_SLUG || "";
const POS_LOAD_URL = __ENV.TIJARA_POS_LOAD_URL || "/odoo";
const AUTH_COOKIE = __ENV.TIJARA_LOAD_AUTH_COOKIE || __ENV.TIJARA_LOAD_COOKIE || "";
const RUN_KIOSK_CHECKOUT = (__ENV.TIJARA_RUN_KIOSK_CHECKOUT_LOAD || "0") === "1";

export const options = {
    vus: Number(__ENV.TIJARA_LOAD_VUS || "5"),
    duration: __ENV.TIJARA_LOAD_DURATION || "30s",
    thresholds: {
        http_req_failed: [`rate<${__ENV.TIJARA_LOAD_MAX_FAIL_RATE || "0.05"}`],
        http_req_duration: [`p(95)<${__ENV.TIJARA_LOAD_MAX_P95_MS || "1000"}`],
        checks: [`rate>${__ENV.TIJARA_LOAD_MIN_CHECKS_RATE || "0.95"}`],
    },
};

function pathUrl(path) {
    if (/^https?:\/\//.test(path)) {
        return path;
    }
    return `${BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

function params(surface, extraHeaders = {}, extra = {}) {
    const headers = { ...extraHeaders };
    if (AUTH_COOKIE) {
        headers.Cookie = AUTH_COOKIE;
    }
    return {
        ...extra,
        headers,
        tags: { surface },
    };
}

function expectStatus(response, name, statuses = [200]) {
    const assertions = {};
    assertions[`${name} status`] = (res) => statuses.includes(res.status);
    return check(response, assertions);
}

function parseJson(response, name) {
    try {
        const payload = response.json();
        check(payload, {
            [`${name} json`]: (data) => typeof data === "object" && data !== null,
        });
        return payload;
    } catch (error) {
        check(null, {
            [`${name} json`]: () => false,
        });
        return null;
    }
}

function getJsonSurface(surface, path, validate) {
    const response = http.get(pathUrl(path), params(surface));
    expectStatus(response, surface);
    const payload = parseJson(response, surface);
    if (payload && validate) {
        validate(payload);
    }
    return payload;
}

function getHtmlSurface(surface, path, allowedStatuses = [200]) {
    const response = http.get(pathUrl(path), params(surface));
    expectStatus(response, surface, allowedStatuses);
}

function validateDisplayPayload(payload, surface) {
    check(payload, {
        [`${surface} screen`]: (data) => data.screen && data.screen.name,
        [`${surface} content arrays`]: (data) =>
            Array.isArray(data.content || []) && Array.isArray(data.promotions || []),
    });
}

function validateKioskPayload(payload) {
    check(payload, {
        "kiosk profile": (data) => data.kiosk && data.kiosk.profile,
        "kiosk item catalog": (data) => data.kiosk && Array.isArray(data.kiosk.items),
    });
}

function runKioskCheckout(kioskPayload) {
    if (!RUN_KIOSK_CHECKOUT || !kioskPayload || !kioskPayload.kiosk) {
        return;
    }
    const items = kioskPayload.kiosk.items || [];
    const profile = kioskPayload.kiosk.profile || {};
    const item = items.find((candidate) => candidate.id || candidate.product_id);
    if (!item) {
        check(null, {
            "kiosk checkout item available": () => false,
        });
        return;
    }
    const orderTypes = profile.allowed_order_types || [];
    const paymentMethods = profile.allowed_payment_methods || [];
    const payload = {
        order_type: profile.default_order_type || orderTypes[0] || "takeaway",
        audience: "b2c",
        payment_method: paymentMethods[0] || "cash",
        customer_name: `Load Test ${__VU}-${__ITER}`,
        customer_mobile: "03000000000",
        lines: [
            {
                content_id: item.id || false,
                product_id: item.product_id || false,
                qty: 1,
            },
        ],
    };
    const response = http.post(
        pathUrl(`/tijara/kiosk/${KIOSK_SLUG}/checkout`),
        JSON.stringify(payload),
        params("kiosk-checkout", { "Content-Type": "application/json" }),
    );
    expectStatus(response, "kiosk-checkout");
    const checkout = parseJson(response, "kiosk-checkout");
    if (checkout) {
        check(checkout, {
            "kiosk checkout ok": (data) => data.status === "ok" && Number(data.amount_total || 0) > 0,
        });
    }
}

export default function () {
    getHtmlSurface("pos-shell", POS_LOAD_URL, [200, 303]);

    if (DISPLAY_SLUG) {
        getHtmlSurface("display-shell", `/tijara/display/${DISPLAY_SLUG}`);
        getJsonSurface("display-data", `/tijara/display/${DISPLAY_SLUG}/data`, (payload) =>
            validateDisplayPayload(payload, "display-data"),
        );
    }

    let kioskPayload = null;
    if (KIOSK_SLUG) {
        getHtmlSurface("kiosk-shell", `/tijara/kiosk/${KIOSK_SLUG}`);
        kioskPayload = getJsonSurface("kiosk-data", `/tijara/kiosk/${KIOSK_SLUG}/data`, validateKioskPayload);
        runKioskCheckout(kioskPayload);
    }

    if (CUSTOMER_DISPLAY_SLUG) {
        getJsonSurface("customer-display-data", `/tijara/display/${CUSTOMER_DISPLAY_SLUG}/data`, (payload) => {
            check(payload, {
                "customer display payload": (data) => Boolean(data.customer_display),
            });
        });
    }

    sleep(1);
}

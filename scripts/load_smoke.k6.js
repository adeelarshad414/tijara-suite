import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
    vus: 5,
    duration: "30s",
    thresholds: {
        http_req_failed: ["rate<0.05"],
        http_req_duration: ["p(95)<1000"],
    },
};

const BASE_URL = __ENV.TIJARA_BASE_URL || "http://localhost:8069";

export default function () {
    const response = http.get(`${BASE_URL}/odoo`);
    check(response, {
        "Odoo responds": (res) => res.status === 200 || res.status === 303,
    });
    sleep(1);
}

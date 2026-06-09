import { expect, test } from "@playwright/test";
import { login, odooCallKw } from "./helpers.mjs";

const requiredEnv = ["ODOO_USERNAME", "ODOO_PASSWORD"];
function today() {
  return new Date().toISOString().slice(0, 10);
}

async function visitAction(page, actionUrl, expectedText) {
  await page.goto(actionUrl, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(
    ({ source, flags }) => new RegExp(source, flags).test(document.body.innerText || ""),
    { source: expectedText.source, flags: expectedText.flags },
    { timeout: 15000 }
  );
}

async function canReachModel(page, model) {
  try {
    await odooCallKw(page, model, "search_read", [[]], { fields: ["id"], limit: 1 });
    return true;
  } catch (error) {
    if (/KeyError|Not Found|not found|requested URL/i.test(error.message)) {
      return false;
    }
    throw error;
  }
}

test("authenticated back-office expense, salary, and KPI collector workflows", async ({ page }) => {
  test.setTimeout(180000);
  const missing = requiredEnv.filter((name) => !process.env[name]);
  test.skip(missing.length > 0, `Set ${requiredEnv.join(", ")} for back-office E2E.`);

  await login(page);
  test.skip(
    !(await canReachModel(page, "tijara.expense.request")),
    "Selected Odoo database does not expose Tijara back-office models."
  );

  const runStamp = Date.now();
  const snapshotDate = today();
  const partners = await odooCallKw(page, "res.partner", "search_read", [[]], {
    fields: ["id", "name"],
    limit: 1,
  });
  expect(partners.length).toBeGreaterThan(0);
  const partnerId = partners[0].id;

  await test.step("create and approve an expense request", async () => {
    const expenseId = await odooCallKw(page, "tijara.expense.request", "create", [
      {
        name: `E2E Expense ${runStamp}`,
        expense_date: snapshotDate,
        requested_by_id: 1,
        partner_id: partnerId,
        category: "delivery",
        payment_method: "cash",
        amount: 1200,
        tax_amount: 216,
        notes: "Browser E2E expense workflow",
      },
    ]);
    await odooCallKw(page, "tijara.expense.request", "action_submit", [[expenseId]]);
    await odooCallKw(page, "tijara.expense.request", "action_approve", [[expenseId]]);
    await odooCallKw(page, "tijara.expense.request", "action_mark_paid", [[expenseId]]);
    const [expense] = await odooCallKw(page, "tijara.expense.request", "read", [
      [expenseId],
      ["state", "total_amount"],
    ]);
    expect(expense.state).toBe("paid");
    expect(expense.total_amount).toBeGreaterThan(1200);
  });

  await test.step("create and approve a salary batch", async () => {
    const salaryBatchId = await odooCallKw(page, "tijara.salary.batch", "create", [
      {
        name: `E2E Salary ${runStamp}`,
        period_start: snapshotDate,
        period_end: snapshotDate,
        line_ids: [
          [
            0,
            0,
            {
              employee_id: partnerId,
              role: "Cashier",
              gross_amount: 45000,
              deduction_amount: 1500,
              bonus_amount: 2000,
              notes: "Browser E2E salary workflow",
            },
          ],
        ],
      },
    ]);
    await odooCallKw(page, "tijara.salary.batch", "action_approve", [[salaryBatchId]]);
    const [salary] = await odooCallKw(page, "tijara.salary.batch", "read", [
      [salaryBatchId],
      ["state", "gross_total", "deduction_total", "bonus_total", "net_total"],
    ]);
    expect(salary.state).toBe("approved");
    expect(salary.gross_total).toBe(45000);
    expect(salary.net_total).toBe(45500);
  });

  await test.step("collect analytics snapshots for back office and loyalty", async () => {
    await odooCallKw(page, "tijara.analytics.snapshot", "action_collect_daily_snapshots");
    const snapshots = await odooCallKw(
      page,
      "tijara.analytics.snapshot",
      "search_read",
      [[["snapshot_date", "=", snapshotDate], ["metric_type", "in", [
        "expense_state_totals",
        "salary_net_payable",
        "loyalty_points_liability",
        "vertical_catalog_coverage",
      ]]]],
      { fields: ["metric_type", "amount", "count", "notes"], limit: 20 }
    );
    const metrics = new Set(snapshots.map((snapshot) => snapshot.metric_type));
    expect(metrics.has("expense_state_totals")).toBeTruthy();
    expect(metrics.has("salary_net_payable")).toBeTruthy();
    expect(metrics.has("loyalty_points_liability")).toBeTruthy();
    expect(metrics.has("vertical_catalog_coverage")).toBeTruthy();
  });

  await test.step("load browser screens for back-office and analytics operations", async () => {
    await visitAction(page, "/odoo/action-tijara_retail_core.action_tijara_expense_request", /Expense|Expenses/i);
    await visitAction(page, "/odoo/action-tijara_retail_core.action_tijara_salary_batch", /Salary|Salaries/i);
    await visitAction(page, "/odoo/action-tijara_analytics.action_tijara_analytics_snapshot", /KPI|Snapshot|Analytics/i);
  });
});

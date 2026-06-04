export async function selectDatabase(target) {
  const database = process.env.ODOO_DATABASE;
  if (database) {
    await target.get(`/web/login?db=${encodeURIComponent(database)}`);
  }
}

export async function selectPageDatabase(page) {
  const database = process.env.ODOO_DATABASE;
  if (database) {
    await page.goto(`/web/login?db=${encodeURIComponent(database)}`);
  }
}

export async function login(page) {
  const database = process.env.ODOO_DATABASE;
  const loginUrl = database ? `/web/login?db=${encodeURIComponent(database)}` : "/web/login";
  await page.goto(loginUrl);
  await page.fill("input[name='login']", process.env.ODOO_USERNAME);
  await page.fill("input[name='password']", process.env.ODOO_PASSWORD);
  await Promise.all([
    page
      .waitForURL((url) => !url.pathname.includes("/web/login"), { timeout: 15000 })
      .catch(() => null),
    page.click("button[type='submit']")
  ]);
  await page.waitForLoadState("domcontentloaded");
}

export async function odooCallKw(page, model, method, args = [], kwargs = {}) {
  const response = await page.evaluate(
    async ({ model, method, args, kwargs }) => {
      const result = await fetch(`/web/dataset/call_kw/${model}/${method}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          jsonrpc: "2.0",
          method: "call",
          params: { model, method, args, kwargs },
          id: Date.now()
        })
      });
      return { status: result.status, body: await result.json() };
    },
    { model, method, args, kwargs }
  );
  if (response.status !== 200 || response.body.error) {
    throw new Error(JSON.stringify(response.body.error || response.body));
  }
  return response.body.result;
}

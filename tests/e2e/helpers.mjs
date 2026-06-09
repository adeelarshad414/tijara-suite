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
  if (database) {
    await page.goto(`/web/login?db=${encodeURIComponent(database)}`);
    const auth = await page.evaluate(
      async ({ database, login, password }) => {
        const result = await fetch("/web/session/authenticate", {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            jsonrpc: "2.0",
            method: "call",
            params: { db: database, login, password },
            id: Date.now()
          })
        });
        return { status: result.status, body: await result.json() };
      },
      {
        database,
        login: process.env.ODOO_USERNAME,
        password: process.env.ODOO_PASSWORD
      }
    );
    if (auth.status !== 200 || auth.body.error) {
      throw new Error(JSON.stringify(auth.body.error || auth.body));
    }
    await page.goto("/odoo", { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("domcontentloaded");
    return;
  }
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
  const database = process.env.ODOO_DATABASE;
  const databaseQuery = database ? `?db=${encodeURIComponent(database)}` : "";
  const response = await page.evaluate(
    async ({ model, method, args, kwargs, databaseQuery }) => {
      const result = await fetch(`/web/dataset/call_kw/${model}/${method}${databaseQuery}`, {
        method: "POST",
        credentials: "include",
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
    { model, method, args, kwargs, databaseQuery }
  );
  if (response.status !== 200 || response.body.error) {
    throw new Error(JSON.stringify(response.body.error || response.body));
  }
  return response.body.result;
}

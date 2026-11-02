import { expect, test } from "@playwright/test";
test.skip(
  !process.env.E2E_PRODUCTION,
  "Vyžaduje lokální HTTPS nginx + Gunicorn produkčního buildu.",
);
test("produkční nginx: fallback, JSON chyby, hlavičky, cookies a sanitizace proxy", async ({
  page,
}) => {
  const deep = await page.request.get("/auta/neexistuje");
  expect(deep.status()).toBe(200);
  expect(deep.headers()["content-type"]).toContain("text/html");
  expect(deep.headers()["cache-control"]).toContain("no-store");
  expect(deep.headers()["content-security-policy"]).toContain(
    "frame-ancestors 'none'",
  );
  expect(deep.headers()["x-content-type-options"]).toBe("nosniff");
  for (const path of ["/api", "/api/neexistuje/", "/api/health/ready/"]) {
    const response = await page.request.get(path);
    expect(response.status()).toBe(404);
    expect(response.headers()["content-type"]).toContain("application/json");
    expect(response.headers()["cache-control"]).toContain("no-store");
    expect((await response.json()).error.code).toBe("not_found");
  }
  const large = await page.request.post("/api/v1/refuelings/", {
    data: "x".repeat(1024 * 1024 + 1),
  });
  expect(large.status()).toBe(413);
  expect((await large.json()).error.code).toBe("request_too_large");
  expect(large.headers()["x-frame-options"]).toBe("DENY");
  const hugeReceipt = await page.request.post(
    "/api/v1/refuelings/00000000-0000-0000-0000-000000000000/receipt/",
    { data: "x".repeat(13 * 1024 * 1024) },
  );
  expect(hugeReceipt.status()).toBe(413);
  expect((await hugeReceipt.json()).error.code).toBe("file_too_large");
  const csrfResponse = await page.request.get("/api/v1/auth/csrf/");
  const csrf = await csrfResponse.json();
  const noCsrf = await page.request.post("/api/v1/auth/login/", {
    data: { username: "e2e-admin", password: "Synthetic-Test-Account-2026!" },
  });
  expect(noCsrf.status()).toBe(403);
  const login = await page.request.post("/api/v1/auth/login/", {
    headers: {
      "X-CSRFToken": csrf.csrf_token,
      Origin: "https://localhost:8443",
      "X-Forwarded-Proto": "http",
      "X-Forwarded-For": "203.0.113.88",
      "X-Real-IP": "203.0.113.88",
    },
    data: { username: "e2e-admin", password: "Synthetic-Test-Account-2026!" },
  });
  expect(login.status()).toBe(200);
  const cookies = await page.context().cookies();
  for (const name of ["sessionid", "csrftoken"]) {
    const cookie = cookies.find((c) => c.name === name)!;
    expect(cookie.secure).toBe(true);
    expect(cookie.httpOnly).toBe(true);
    expect(cookie.sameSite).toBe("Lax");
  }
  const sw = await page.request.get("/sw.js");
  expect(sw.headers()["content-type"]).toContain("javascript");
  expect(sw.headers()["cache-control"]).toContain("no-store");
  const manifest = await (
    await page.request.get("/manifest.webmanifest")
  ).json();
  expect(manifest.scope).toBe("/");
  for (const icon of manifest.icons) {
    expect((await page.request.get(icon.src)).status()).toBe(200);
  }
});
test("PWA: jen veřejná cache, offline bez soukromých údajů a odhlášení", async ({
  page,
  context,
}) => {
  await page.goto("/prihlaseni");
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
  await expect
    .poll(() => page.evaluate(() => !!navigator.serviceWorker.controller))
    .toBe(true);
  await page.getByLabel("Uživatelské jméno", { exact: true }).fill("e2e-admin");
  await page
    .getByLabel("Heslo", { exact: true })
    .fill("Synthetic-Test-Account-2026!");
  await page.getByRole("button", { name: "Přihlásit se", exact: true }).click();
  await expect(page.getByRole("heading", { name: /Dobrý den/ })).toBeVisible();
  await page.goto("/auta");
  await expect(
    page.getByRole("heading", { name: "Moje auta", exact: true }),
  ).toBeVisible();
  const urls = await page.evaluate(async () => {
    const result: string[] = [];
    for (const name of await caches.keys())
      for (const request of await (await caches.open(name)).keys())
        result.push(request.url);
    return result;
  });
  expect(urls.length).toBeGreaterThan(5);
  expect(
    urls.every(
      (url) =>
        /\/(assets|icons)\//.test(url) ||
        /\/(offline\.(html|css)|manifest\.webmanifest)$/.test(url),
    ),
  ).toBe(true);
  expect(urls.some((url) => url.includes("/api/"))).toBe(false);
  await context.setOffline(true);
  await page.goto("/auta");
  await expect(
    page.getByRole("heading", { name: "Chybí připojení" }),
  ).toBeVisible();
  await expect(
    page.getByText("Testovací správce", { exact: true }),
  ).toHaveCount(0);
  const apiResult = await page.evaluate(async () => {
    try {
      await fetch("/api/v1/vehicles/");
      return "unexpected";
    } catch {
      return "network_only";
    }
  });
  expect(apiResult).toBe("network_only");
  await context.setOffline(false);
  await page.getByRole("link", { name: "Zkusit připojení znovu" }).click();
  await expect(page.getByRole("heading", { name: /Dobrý den/ })).toBeVisible();
  const logout = page.getByRole("button", { name: "Odhlásit se", exact: true });
  if (await logout.isVisible()) await logout.click();
  else
    await page
      .getByRole("button", { name: "Odhlásit se na mobilu", exact: true })
      .click();
  await expect(
    page.getByRole("heading", { name: "Přihlásit se", exact: true }),
  ).toBeVisible();
  await page.goBack();
  await expect(
    page.getByRole("heading", { name: "Přihlásit se", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => localStorage.length + sessionStorage.length),
  ).toBe(0);
});

test("PWA: výpadek při formuláři zachová vstupy a retry vytvoří jediný záznam", async ({
  page,
  context,
}, info) => {
  await page.goto("/prihlaseni");
  await page.getByLabel("Uživatelské jméno", { exact: true }).fill("e2e-admin");
  await page
    .getByLabel("Heslo", { exact: true })
    .fill("Synthetic-Test-Account-2026!");
  await page.getByRole("button", { name: "Přihlásit se", exact: true }).click();
  await expect(page.getByRole("heading", { name: /Dobrý den/ })).toBeVisible();
  const csrf = await (await page.request.get("/api/v1/auth/csrf/")).json();
  const created = await page.request.post("/api/v1/vehicles/", {
    headers: {
      "X-CSRFToken": csrf.csrf_token,
      Origin: new URL(process.env.E2E_BASE_URL!).origin,
    },
    data: {
      name: `Výpadek ${info.project.name} ${Date.now()}`,
      make: "Škoda",
      model: "Fabia",
      fuel_type: "PETROL",
      initial_odometer_km: 0,
    },
  });
  expect(created.status()).toBe(201);
  const car = await created.json();
  await page.goto(`/tankovani/nove?vehicle_id=${car.id}`);
  await expect(page.getByLabel("Datum *")).not.toHaveValue("");
  await page.getByLabel("Litry *", { exact: true }).fill("10");
  await page.getByLabel("Přesná částka z účtenky (Kč)").fill("400");
  await page.getByLabel("Tachometr (km)", { exact: true }).fill("100");
  await context.setOffline(true);
  await expect(
    page.getByText(/Chybí připojení. Zápisy vyžadují server/),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Uložit tankování", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Spojení se serverem se nezdařilo",
  );
  await expect(page.getByLabel("Litry *", { exact: true })).toHaveValue("10");
  await context.setOffline(false);
  await page
    .getByRole("button", { name: "Uložit tankování", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Detail tankování", exact: true }),
  ).toBeVisible();
  expect(
    (
      await (
        await page.request.get(`/api/v1/refuelings/?vehicle_id=${car.id}`)
      ).json()
    ).count,
  ).toBe(1);
});

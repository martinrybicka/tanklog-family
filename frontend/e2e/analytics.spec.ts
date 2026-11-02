import { expect, test } from "@playwright/test";
test("dashboard: plná–plná, kotva mimo období, oprava a mobilní grafy", async ({
  page,
}, info) => {
  await page.goto("/prihlaseni");
  await page.getByLabel("Uživatelské jméno", { exact: true }).fill("e2e-admin");
  await page
    .getByLabel("Heslo", { exact: true })
    .fill("Synthetic-Test-Account-2026!");
  await page.getByRole("button", { name: "Přihlásit se", exact: true }).click();
  await expect(page.getByRole("heading", { name: /Dobrý den/ })).toBeVisible();
  const csrf = await (await page.request.get("/api/v1/auth/csrf/")).json();
  const headers = { "X-CSRFToken": csrf.csrf_token };
  const name = `Měření ${info.project.name} ${Date.now()}`;
  const response = await page.request.post("/api/v1/vehicles/", {
    headers,
    data: {
      name,
      make: "Škoda",
      model: "Octavia",
      fuel_type: "PETROL",
      initial_odometer_km: 0,
      standard_consumption_l_100km: "6",
      standard_methodology: "WLTP",
      standard_source: "Syntetická norma",
    },
  });
  expect(response.status()).toBe(201);
  const vehicle = await response.json();
  const records: string[] = [];
  for (const [date, km, liters, full] of [
    ["2026-01-31", 10000, "50", true],
    ["2026-02-01", 10300, "20", false],
    ["2026-02-05", 10600, "25", true],
  ]) {
    const created = await page.request.post("/api/v1/refuelings/", {
      headers: { ...headers, "Idempotency-Key": crypto.randomUUID() },
      data: {
        vehicle_id: vehicle.id,
        date,
        odometer_km: km,
        liters,
        total_amount: String(Number(liters) * 40),
        is_full_tank: full,
      },
    });
    expect(created.status()).toBe(201);
    records.push((await created.json()).id);
  }
  const route = `/auta/${vehicle.id}/statistiky?period=month&anchor_date=2026-02-01`;
  await page.goto(route);
  await expect(
    page.getByRole("heading", { name: `Statistiky · ${name}` }),
  ).toBeVisible();
  await expect(page.getByText("7,50", { exact: false }).first()).toBeVisible();
  await expect(
    page.getByText(/Rozdíl 1,50 l\/100 km \(25,00 %\)/),
  ).toBeVisible();
  await page
    .locator(".coverage-row > summary")
    .filter({ hasText: name })
    .click();
  await page
    .getByRole("link", { name: "Prohlédnout intervaly a podklady" })
    .click();
  await page.getByRole("link", { name: /31. 1. 2026 → 5. 2. 2026/ }).click();
  await expect(
    page.getByRole("heading", { name: "Podklady intervalu" }),
  ).toBeVisible();
  await expect(page.getByText("Pouze počáteční kotva")).toBeVisible();
  await expect(page.getByText(/Počáteční kotva je před obdobím/)).toBeVisible();
  await page.goto(route);
  await page.getByRole("button", { name: "Předchozí období" }).click();
  await expect(page.getByText(/Nedostatek dat/).first()).toBeVisible();
  await page.getByRole("button", { name: "Následující období" }).click();
  await expect(page.getByText(/Rozdíl 1,50/)).toBeVisible();
  await page
    .getByRole("combobox", { name: "Období", exact: true })
    .selectOption("custom");
  await page.getByLabel("Datum od", { exact: true }).fill("2026-02-01");
  await page.getByLabel("Datum do", { exact: true }).fill("2026-02-01");
  await page.getByRole("button", { name: "Použít období" }).click();
  await expect(page.getByText(/Nedostatek dat/).first()).toBeVisible();
  await page.goto(route);
  await page.goto(`/tankovani/${records[1]}/upravit`);
  await page.getByLabel("Litry *", { exact: true }).fill("15");
  await page.getByLabel("Přesná částka z účtenky (Kč)").fill("600");
  await page.getByRole("button", { name: "Uložit změny", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Detail tankování" }),
  ).toBeVisible();
  await page.goto(route);
  await expect(page.getByText(/Rozdíl 0,67 l\/100 km/)).toBeVisible();
  await expect(page.getByText("6,67", { exact: false }).first()).toBeVisible();
  await page
    .getByText("Zobrazit data v tabulce: realizovaná cena paliva", {
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("table", { name: "Realizovaná cena paliva (Kč/l)" }),
  ).toBeVisible();
  await page.screenshot({
    path: `../.runtime/analytics-${info.project.name}.png`,
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

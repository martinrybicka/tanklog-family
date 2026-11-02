import { expect, test, type Page } from "@playwright/test";
const password = "Synthetic-Test-Account-2026!";
const image = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAABQAAAAeCAIAAACjcKk8AAAAMUlEQVR4nO3LIQIAMAgDsa7//zPIYQ9L4/Ok0pbXU8mYefmSIdMwJUOmYUqGTIOO5wb54AE7Z4EDmQAAAABJRU5ErkJggg==",
  "base64",
);
async function signIn(page: Page) {
  await page.goto("/prihlaseni");
  await page.getByLabel("Uživatelské jméno", { exact: true }).fill("e2e-admin");
  await page.getByLabel("Heslo", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Přihlásit se", exact: true }).click();
  await expect(page.getByRole("heading", { name: /Dobrý den/ })).toBeVisible();
}
test("tankování, chyba uploadu a opakování, filtry, XLSX, oprava a smazání", async ({
  page,
}, info) => {
  test.setTimeout(60000);
  await signIn(page);
  const csrf = await (await page.request.get("/api/v1/auth/csrf/")).json();
  const name = `Tankování ${info.project.name} ${Date.now()}`;
  const car = await page.request.post("/api/v1/vehicles/", {
    headers: { "X-CSRFToken": csrf.csrf_token },
    data: {
      name,
      make: "Škoda",
      model: "Octavia",
      fuel_type: "PETROL",
      initial_odometer_km: 10000,
    },
  });
  expect(car.status()).toBe(201);
  const vehicle = (await car.json()).id;
  await page.goto(`/tankovani/nove?vehicle_id=${vehicle}`);
  await expect(page.getByLabel("Datum *")).not.toHaveValue("");
  await page.getByLabel("Datum *").fill("2026-01-10");
  await page.getByLabel("Litry *").fill("42,350");
  await page.getByLabel("Cena za litr (Kč)").fill("38,9");
  await page.getByLabel("Přesná částka z účtenky (Kč)").fill("1600,00");
  await page
    .getByRole("button", { name: "Uložit tankování", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText("Chybí tachometr");
  await page.getByRole("button", { name: "Potvrdit údaje a uložit" }).click();
  await expect(
    page.getByRole("heading", { name: "Detail tankování" }),
  ).toBeVisible();
  const path = new URL(page.url()).pathname;
  await expect(page.getByRole("heading", { name: "1 600 Kč" })).toBeVisible();
  await page.getByLabel("Přiložit účtenku", { exact: true }).setInputFiles({
    name: "bad.png",
    mimeType: "image/png",
    buffer: Buffer.from("not image"),
  });
  await page
    .getByRole("button", { name: "Nahrát účtenku", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Tankování zůstává uložené",
  );
  await page.getByLabel("Přiložit účtenku", { exact: true }).setInputFiles({
    name: "synthetic.png",
    mimeType: "image/png",
    buffer: image,
  });
  await page
    .getByRole("button", { name: "Nahrát účtenku", exact: true })
    .click();
  await expect(page.getByRole("img", { name: "Náhled účtenky" })).toBeVisible();
  expect(new URL(page.url()).pathname).toBe(path);
  await page.context().clearCookies();
  await signIn(page);
  await page.goto(path);
  await expect(page.getByRole("img", { name: "Náhled účtenky" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "1 600 Kč" })).toBeVisible();
  await page.goto(
    `/tankovani?vehicle_id=${vehicle}&date_from=2026-01-01&date_to=2026-01-31`,
  );
  await expect(
    page.getByText("Celkem 1 tankování", { exact: true }),
  ).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Exportovat vyfiltrovaná data" })
    .click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("tankovani.xlsx");
  await download.saveAs(`../.runtime/export-${info.project.name}.xlsx`);
  await page.getByRole("link", { name: new RegExp(name) }).click();
  await page
    .getByRole("link", { name: "Upravit tankování", exact: true })
    .click();
  await page.getByLabel("Přesná částka z účtenky (Kč)").fill("1590,00");
  await page.getByRole("button", { name: "Uložit změny" }).click();
  await page.getByRole("button", { name: "Potvrdit údaje a uložit" }).click();
  await expect(page.getByRole("heading", { name: "1 590 Kč" })).toBeVisible();
  await expect(page.locator("#main-content")).toBeFocused();
  await page.screenshot({
    path: `../.runtime/refueling-${info.project.name}.png`,
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page
    .getByRole("button", { name: "Smazat tankování", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Potvrdit smazání" })
    .click();
  await expect(
    page.getByText("Celkem 0 tankování", { exact: true }),
  ).toBeVisible();
});

test("sdílené tankování: přispěvatel upravuje jen vlastní, archivace a odebrání přístupu", async ({
  page,
  browser,
  playwright,
}, info) => {
  test.setTimeout(60000);
  await signIn(page);
  const suffix = `${info.project.name}-${Date.now()}`;
  const username = `fuel-contributor-${suffix}`;
  async function post(path: string, body: unknown, request = page.request) {
    const csrf = await (await request.get("/api/v1/auth/csrf/")).json();
    return request.post(`/api/v1/${path}`, {
      data: body,
      headers: {
        "X-CSRFToken": csrf.csrf_token,
        "Idempotency-Key": crypto.randomUUID(),
      },
    });
  }
  const created = await post("admin/users/", {
    username,
    display_name: username,
    system_role: "USER",
    current_password: password,
  });
  expect(created.status()).toBe(201);
  const temp = await created.json();
  const setup = await playwright.request.newContext({
    baseURL: process.env.E2E_BASE_URL || "http://localhost:8080",
  });
  await post(
    "auth/login/",
    { username, password: temp.temporary_password },
    setup,
  );
  expect(
    (
      await post("auth/password/change/", { new_password: password }, setup)
    ).status(),
  ).toBe(200);
  await setup.dispose();
  const vehicle = await (
    await post("vehicles/", {
      name: `Sdílená historie ${suffix}`,
      make: "Škoda",
      model: "Fabia",
      fuel_type: "PETROL",
      initial_odometer_km: 0,
    })
  ).json();
  const grant = await (
    await post(`admin/vehicles/${vehicle.id}/access/`, {
      user_id: temp.user_id,
      role: "CONTRIBUTOR",
    })
  ).json();
  const otherRecord = await (
    await post("refuelings/", {
      vehicle_id: vehicle.id,
      date: "2026-01-10",
      liters: "10",
      total_amount: "350",
      odometer_km: 100,
    })
  ).json();
  const context = await browser.newContext({
    baseURL: process.env.E2E_BASE_URL || "http://localhost:8080",
    viewport:
      info.project.name === "mobile"
        ? { width: 390, height: 844 }
        : { width: 1280, height: 900 },
  });
  try {
    const driver = await context.newPage();
    await driver.goto("/prihlaseni");
    await driver
      .getByLabel("Uživatelské jméno", { exact: true })
      .fill(username);
    await driver.getByLabel("Heslo", { exact: true }).fill(password);
    await driver
      .getByRole("button", { name: "Přihlásit se", exact: true })
      .click();
    await expect(
      driver.getByRole("heading", { name: /Dobrý den/ }),
    ).toBeVisible();
    await driver.goto(`/tankovani/nove?vehicle_id=${vehicle.id}`);
    await expect(driver.getByLabel("Datum *")).not.toHaveValue("");
    await driver.getByLabel("Datum *").fill("2026-01-11");
    await driver.getByLabel("Litry *").fill("20");
    await driver.getByLabel("Přesná částka z účtenky (Kč)").fill("680");
    await driver.getByLabel("Tachometr (km)").fill("300");
    await driver
      .getByRole("button", { name: "Uložit tankování", exact: true })
      .click();
    await expect(
      driver.getByRole("heading", { name: "Detail tankování" }),
    ).toBeVisible();
    const ownPath = new URL(driver.url()).pathname;
    await expect(
      driver.getByRole("link", { name: "Upravit tankování", exact: true }),
    ).toBeVisible();
    await expect(
      driver.getByRole("button", { name: "Smazat tankování", exact: true }),
    ).toHaveCount(0);
    await driver.getByLabel("Přiložit účtenku", { exact: true }).setInputFiles({
      name: "synthetic.png",
      mimeType: "image/png",
      buffer: image,
    });
    await driver
      .getByRole("button", { name: "Nahrát účtenku", exact: true })
      .click();
    await expect(
      driver.getByRole("img", { name: "Náhled účtenky" }),
    ).toBeVisible();
    await driver
      .getByRole("link", { name: "Upravit tankování", exact: true })
      .click();
    await driver.getByLabel("Přesná částka z účtenky (Kč)").fill("675");
    await driver
      .getByRole("button", { name: "Uložit změny", exact: true })
      .click();
    await expect(driver.getByRole("heading", { name: "675 Kč" })).toBeVisible();
    await driver.goto(`/tankovani/${otherRecord.id}`);
    await expect(
      driver.getByRole("link", { name: "Upravit tankování", exact: true }),
    ).toHaveCount(0);
    const current = await page.request.get(`/api/v1/vehicles/${vehicle.id}/`);
    const csrf = await (await page.request.get("/api/v1/auth/csrf/")).json();
    expect(
      (
        await page.request.post(`/api/v1/vehicles/${vehicle.id}/archive/`, {
          data: {},
          headers: {
            "X-CSRFToken": csrf.csrf_token,
            "If-Match": current.headers()["etag"],
          },
        })
      ).status(),
    ).toBe(200);
    await driver.goto(ownPath);
    await expect(driver.getByRole("heading", { name: "675 Kč" })).toBeVisible();
    await expect(
      driver.getByRole("link", { name: "Upravit tankování", exact: true }),
    ).toHaveCount(0);
    await page.goto(ownPath);
    await expect(
      page.getByRole("link", { name: "Upravit tankování", exact: true }),
    ).toBeVisible();
    const grantDetail = await page.request.get(
      `/api/v1/admin/vehicle-access/${grant.id}/`,
    );
    expect(
      (
        await page.request.delete(`/api/v1/admin/vehicle-access/${grant.id}/`, {
          headers: {
            "X-CSRFToken": csrf.csrf_token,
            "If-Match": grantDetail.headers()["etag"],
          },
        })
      ).status(),
    ).toBe(204);
    await driver.reload();
    await expect(driver.getByRole("alert")).toBeVisible();
    expect(
      (
        await driver.request.get(
          `/api/v1/refuelings/${ownPath.split("/").pop()}/receipt/`,
        )
      ).status(),
    ).toBe(404);
  } finally {
    await context.close();
  }
});

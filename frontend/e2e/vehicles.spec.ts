import {
  expect,
  test,
  type Page,
  type APIRequestContext,
} from "@playwright/test";

const password = "Synthetic-Test-Account-2026!";
async function signIn(page: Page, username = "e2e-admin") {
  await page.goto("/prihlaseni");
  await page.getByLabel("Uživatelské jméno", { exact: true }).fill(username);
  await page.getByLabel("Heslo", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Přihlásit se", exact: true }).click();
  await expect(page.getByRole("heading", { name: /Dobrý den/ })).toBeVisible();
}
async function write(request: APIRequestContext, path: string, data: unknown) {
  const csrf = await (await request.get("/api/v1/auth/csrf/")).json();
  return request.post(`/api/v1/${path}`, {
    data,
    headers: { "X-CSRFToken": csrf.csrf_token },
  });
}
async function createCar(page: Page, name: string) {
  await page.goto("/auta/nove");
  await page.getByLabel("Název auta *").fill(name);
  await page.getByLabel("Značka *").fill("Škoda");
  await page.getByLabel("Model *").fill("Octavia");
  await page.getByLabel("Počáteční tachometr (km) *").fill("120000");
  await page
    .getByRole("button", { name: "Vytvořit auto", exact: true })
    .click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  return new URL(page.url()).pathname;
}

test("vozidlo: vytvoření, úprava, archivace a trvalost bez cookies", async ({
  page,
}, info) => {
  const name = `Rodinné auto ${info.project.name} ${Date.now()}`;
  await signIn(page);
  const path = await createCar(page, name);
  await page.getByRole("link", { name: "Upravit údaje" }).click();
  await page.getByLabel("Registrační značka").fill("1AB 2345");
  await page.getByText("Technické údaje a norma (nepovinné)").click();
  await page.getByLabel("Normovaná spotřeba (l/100 km)").fill("5,125");
  await page.getByLabel("Metodika normy").selectOption("WLTP");
  await page.getByRole("button", { name: "Uložit změny" }).click();
  await expect(page.getByText("5,125 l/100 km", { exact: true })).toBeVisible();
  await page.context().clearCookies();
  await signIn(page);
  await page.goto(path);
  await expect(page.getByText("1AB 2345", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Archivovat auto", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Potvrdit", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Obnovit auto", exact: true }),
  ).toBeVisible();
  await page.goto("/auta?status=archived");
  await expect(page.getByRole("link", { name, exact: true })).toBeVisible();
  await page.getByRole("link", { name, exact: true }).click();
  await page.getByRole("button", { name: "Obnovit auto", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Potvrdit", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Archivovat auto", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: `../.runtime/vehicle-${info.project.name}.png`,
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test("sdílení VIEWER/CONTRIBUTOR, převod a odebrání přístupu", async ({
  page,
  browser,
  playwright,
}, info) => {
  test.setTimeout(90000);
  const suffix = `${info.project.name}-${Date.now()}`;
  const names = [
    `owner-${suffix}`,
    `viewer-${suffix}`,
    `contributor-${suffix}`,
  ];
  await signIn(page);
  for (const username of names) {
    const result = await write(page.request, "admin/users/", {
      username,
      display_name: username,
      system_role: "USER",
      current_password: password,
    });
    expect(result.status()).toBe(201);
    const temporary = (await result.json()).temporary_password;
    const request = await playwright.request.newContext({
      baseURL: process.env.E2E_BASE_URL || "http://localhost:8080",
    });
    try {
      expect(
        (
          await write(request, "auth/login/", { username, password: temporary })
        ).status(),
      ).toBe(200);
      expect(
        (
          await write(request, "auth/password/change/", {
            new_password: password,
          })
        ).status(),
      ).toBe(200);
    } finally {
      await request.dispose();
    }
  }
  const contexts = await Promise.all(
    names.map(() =>
      browser.newContext({
        baseURL: process.env.E2E_BASE_URL || "http://localhost:8080",
        viewport:
          info.project.name === "mobile"
            ? { width: 390, height: 844 }
            : { width: 1280, height: 900 },
      }),
    ),
  );
  try {
    const [owner, viewer, contributor] = await Promise.all(
      contexts.map((c) => c.newPage()),
    );
    await signIn(owner, names[0]);
    const name = `Sdílené auto ${suffix}`;
    const path = await createCar(owner, name);
    const id = path.split("/").pop()!;
    await page.goto(path);
    for (const [username, role] of [
      [names[1], "VIEWER"],
      [names[2], "CONTRIBUTOR"],
    ]) {
      await page
        .getByLabel("Hledat: Uživatel pro sdílení", { exact: true })
        .fill(username);
      await expect(
        page
          .getByLabel("Uživatel pro sdílení", { exact: true })
          .locator("option")
          .filter({ hasText: username }),
      ).toHaveCount(1);
      const value = await page
        .getByLabel("Uživatel pro sdílení", { exact: true })
        .locator("option")
        .filter({ hasText: username })
        .getAttribute("value");
      await page
        .getByLabel("Uživatel pro sdílení", { exact: true })
        .selectOption(value!);
      await page.getByLabel("Role sdílení", { exact: true }).selectOption(role);
      await page
        .getByRole("button", { name: "Přidat přístup", exact: true })
        .click();
      await expect(
        page
          .locator(".grant-list")
          .getByText(username, { exact: true })
          .first(),
      ).toBeVisible();
    }
    for (const [target, username, role] of [
      [viewer, names[1], "Čtenář"],
      [contributor, names[2], "Přispěvatel"],
    ] as const) {
      await signIn(target, username);
      await target.goto("/auta");
      await expect(
        target.getByText(`Sdílené auto · ${role}`, { exact: true }),
      ).toBeVisible();
      await target.getByRole("link", { name, exact: true }).click();
      await expect(
        target.getByRole("link", { name: "Upravit údaje" }),
      ).toHaveCount(0);
      expect(
        (
          await target.request.get(`/api/v1/admin/vehicles/${id}/access/`)
        ).status(),
      ).toBe(403);
    }
    await page.getByRole("button", { name: "Převést vlastnictví" }).click();
    const dialog = page.getByRole("dialog");
    await dialog
      .getByLabel("Hledat: Nový vlastník", { exact: true })
      .fill(names[2]);
    const option = dialog
      .getByLabel("Nový vlastník", { exact: true })
      .locator("option")
      .filter({ hasText: names[2] });
    await expect(option).toHaveCount(1);
    await dialog
      .getByLabel("Nový vlastník", { exact: true })
      .selectOption((await option.getAttribute("value"))!);
    await dialog
      .getByLabel("Přístup původního vlastníka")
      .selectOption("VIEWER");
    await dialog.getByLabel("Vaše aktuální heslo").fill(password);
    await dialog
      .getByRole("button", { name: "Potvrdit převod", exact: true })
      .click();
    await expect(
      page.getByText("Vlastnictví bylo převedeno.", { exact: true }),
    ).toBeVisible();
    await contributor.reload();
    await expect(
      contributor.getByRole("link", { name: "Upravit údaje" }),
    ).toBeVisible();
    await owner.reload();
    await expect(
      owner.getByRole("link", { name: "Upravit údaje" }),
    ).toHaveCount(0);
    const row = page.locator(".grant-list li").filter({ hasText: names[1] });
    await row.getByRole("button", { name: "Odebrat přístup" }).click();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Potvrdit odebrání" })
      .click();
    await expect(row).toHaveCount(0);
    await viewer.reload();
    await expect(viewer.getByRole("alert")).toBeVisible();
    expect((await viewer.request.get(`/api/v1/vehicles/${id}/`)).status()).toBe(
      404,
    );
    await viewer.goto("/auta");
    await expect(viewer.getByRole("link", { name, exact: true })).toHaveCount(
      0,
    );
    await page.screenshot({
      path: `../.runtime/sharing-${info.project.name}.png`,
      fullPage: true,
    });
  } finally {
    await Promise.all(contexts.map((c) => c.close()));
  }
});

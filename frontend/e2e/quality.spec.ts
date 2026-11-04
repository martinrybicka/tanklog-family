import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
async function signIn(page: Page) {
  await page.goto("/prihlaseni");
  await page.getByLabel("Uživatelské jméno", { exact: true }).fill("e2e-admin");
  await page
    .getByLabel("Heslo", { exact: true })
    .fill("Synthetic-Test-Account-2026!");
  await page.getByRole("button", { name: "Přihlásit se", exact: true }).click();
  await expect(page.getByRole("heading", { name: /Dobrý den/ })).toBeVisible();
}
async function audit(page: Page) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(
    result.violations.map((v) => ({
      id: v.id,
      description: v.description,
      nodes: v.nodes.map((n) => n.target),
    })),
  ).toEqual([]);
}
test("přístupnost: login, formuláře, dashboard a dialog v obou motivech", async ({
  page,
}, info) => {
  test.setTimeout(120000);
  await page.goto("/prihlaseni");
  await audit(page);
  await page.getByRole("button", { name: "Přihlásit se", exact: true }).click();
  await expect(
    page.getByLabel("Uživatelské jméno", { exact: true }),
  ).toBeFocused();
  await audit(page);
  await signIn(page);
  const profile = await page.request.get("/api/v1/profile/");
  const token = await (await page.request.get("/api/v1/auth/csrf/")).json();
  expect(
    (
      await page.request.patch("/api/v1/profile/", {
        data: { theme: "SYSTEM" },
        headers: {
          "X-CSRFToken": token.csrf_token,
          "If-Match": profile.headers()["etag"],
        },
      })
    ).status(),
  ).toBe(200);
  for (const mode of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: mode, reducedMotion: "reduce" });
    for (const path of [
      "/prehled",
      "/auta",
      "/auta/nove",
      "/tankovani",
      "/tankovani/nove",
      "/nastaveni",
      "/administrace/uzivatele",
    ]) {
      await page.goto(path);
      await expect(page.locator("main h1")).toBeVisible();
      await expect(page.getByText("Načítání…", { exact: true })).toHaveCount(0);
      await expect(page.locator("html")).toHaveClass(
        mode === "dark" ? /dark/ : /^$/,
      );
      await audit(page);
      if (path === "/nastaveni")
        await page.screenshot({
          path: `../.runtime/phase5-${mode}-${info.project.name}.png`,
          fullPage: true,
        });
    }
  }
  await page
    .getByRole("button", { name: "Přidat uživatele", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await audit(page);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Přidat uživatele", exact: true }),
  ).toBeFocused();
});
test("rozvržení: 360/390/768/1024/1440 a zvětšení 200 %", async ({ page }) => {
  test.setTimeout(90000);
  await signIn(page);
  for (const width of [360, 390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of [
      "/prehled",
      "/auta",
      "/tankovani",
      "/tankovani/nove",
      "/nastaveni",
      "/administrace/uzivatele",
    ]) {
      await page.goto(path);
      await expect(page.locator("main h1")).toBeVisible();
      if (width <= 1023)
        expect(
          Math.round((await page.locator(".app-body").boundingBox())!.width),
        ).toBe(width);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        `${path} při ${width}px`,
      ).toBe(true);
    }
  }
  // 1440px okno při skutečném zvětšení 200 % má 720 CSS px; ověřujeme reflow.
  await page.setViewportSize({ width: 720, height: 450 });
  await page.goto("/nastaveni");
  await expect(
    page.getByRole("heading", { name: "Nastavení", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  const focus = await page.evaluate(() => ({
    tag: document.activeElement?.tagName,
    outline: getComputedStyle(document.activeElement!).outlineStyle,
  }));
  expect(focus.tag).not.toBe("BODY");
  expect(focus.outline).not.toBe("none");
});

test("odhlášení ve druhém okně odstraní zobrazená soukromá data", async ({
  page,
  context,
}) => {
  await signIn(page);
  const second = await context.newPage();
  await second.goto("/auta");
  await expect(
    second.getByRole("heading", { name: "Moje auta", exact: true }),
  ).toBeVisible();
  if (await page.locator(".family-account summary").count())
    await page.locator(".family-account summary").click();
  const logout = page.getByRole("button", { name: "Odhlásit se", exact: true });
  if (await logout.isVisible()) await logout.click();
  else
    await page
      .getByRole("button", { name: "Odhlásit se na mobilu", exact: true })
      .click();
  await expect(
    second.getByRole("heading", { name: "Přihlásit se", exact: true }),
  ).toBeVisible();
  await expect(
    second.getByText("Testovací správce", { exact: true }),
  ).toHaveCount(0);
  await second.close();
});

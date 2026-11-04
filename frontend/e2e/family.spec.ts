import AxeBuilder from "@axe-core/playwright";
import { readFileSync } from "node:fs";
import { test, expect, type Page } from "@playwright/test";
const path = process.env.E2E_FAMILY_FIXTURE;
const fixtures = path
  ? (JSON.parse(readFileSync(path, "utf8")) as Record<
      string,
      { user: string; car: string; user_id: string }
    > & { image_base64: string })
  : null;
async function login(page: Page, username: string) {
  await page.goto("/prihlaseni");
  await page.getByLabel("Uživatelské jméno", { exact: true }).fill(username);
  await page
    .getByLabel("Heslo", { exact: true })
    .fill("Synthetic-Test-Account-2026!");
  await page.getByRole("button", { name: "Přihlásit se", exact: true }).click();
  await expect(page.getByRole("heading", { name: /Dobrý den/ })).toBeVisible();
}
async function audit(page: Page) {
  const report = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(
    report.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => n.target),
    })),
  ).toEqual([]);
}
test("rodina: fotka jako první, skutečné OCR, návrat k návrhu a uložení", async ({
  page,
}, info) => {
  test.skip(!fixtures, "Vyžaduje syntetickou rodinu v *_e2e DB.");
  const fixture = fixtures![info.project.name];
  await login(page, fixture.user);
  await expect(page.getByRole("link", { name: "Správa rodiny" })).toHaveCount(
    0,
  );
  await audit(page);
  await page.screenshot({
    path: `../.runtime/family-home-${info.project.name}.png`,
    fullPage: true,
  });
  await page
    .getByRole("link", { name: "Přidat účtenku", exact: true })
    .last()
    .click();
  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name: "synteticka.png",
      mimeType: "image/png",
      buffer: Buffer.from(fixtures!.image_base64, "base64"),
    });
  await page
    .getByRole("button", { name: "Přečíst účtenku", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Vypadá všechno správně?" }),
  ).toBeVisible();
  await expect(page.getByLabel("Natankováno (l)", { exact: true })).toHaveValue(
    "10.500",
  );
  await expect(page.getByLabel("Zaplaceno (Kč)", { exact: true })).toHaveValue(
    "420.00",
  );
  await audit(page);
  await page.screenshot({
    path: `../.runtime/family-review-${info.project.name}.png`,
    fullPage: true,
  });
  await page.getByRole("link", { name: /Dokončit později/ }).click();
  await expect(
    page.getByRole("heading", { name: "Ještě dokončit" }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: /Účtenka z/ })
    .first()
    .click();
  await expect(page.getByLabel("Natankováno (l)", { exact: true })).toHaveValue(
    "10.500",
  );
  await page
    .getByRole("button", { name: "Potvrdit a uložit", exact: true })
    .click();
  const warning = page.getByRole("button", { name: /Rozumím, přesto uložit/ });
  await expect(
    page.getByRole("heading", { name: "Hotovo. Šťastnou cestu!" }).or(warning),
  ).toBeVisible();
  if (await warning.isVisible()) await warning.click();
  await expect(
    page.getByRole("heading", { name: "Hotovo. Šťastnou cestu!" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Prohlédnout tankování" }).click();
  await expect(
    page.getByRole("img", { name: "Uložená účtenka tankování" }),
  ).toBeVisible();
  await audit(page);
  await page.goto("/rodina");
  await expect(page).toHaveURL(/\/$/);
});
test("rodina: ruční zadání a potvrzení varování", async ({ page }, info) => {
  test.skip(!fixtures, "Vyžaduje syntetickou rodinu.");
  await login(page, fixtures![info.project.name].user);
  await page.goto("/uctenka");
  await page
    .getByRole("button", { name: "Nemám účtenku, doplním ručně" })
    .click();
  await page.getByLabel("Natankováno (l)", { exact: true }).fill("1,250");
  await page.getByLabel("Zaplaceno (Kč)", { exact: true }).fill("0");
  await page
    .getByRole("button", { name: "Potvrdit a uložit", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Hotovo. Šťastnou cestu!" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: /Rozumím, přesto uložit/ }).click();
  await expect(
    page.getByRole("heading", { name: "Hotovo. Šťastnou cestu!" }),
  ).toBeVisible();
});
test("rodina: správce nastaví předvybrané auto", async ({ page }, info) => {
  test.skip(!fixtures, "Vyžaduje syntetickou rodinu.");
  const fixture = fixtures![info.project.name];
  await login(page, "e2e-admin");
  await page.goto("/rodina");
  await page.getByLabel("Najít člena rodiny").fill(fixture.user);
  const member = page
    .locator("section.family-member")
    .filter({ hasText: fixture.user });
  await expect(member).toHaveCount(1);
  await member.getByLabel("Výchozí auto").selectOption(fixture.car);
  await member.getByRole("button", { name: "Uložit", exact: true }).click();
  await expect(member.getByRole("status")).toContainText("Uloženo.");
  await audit(page);
});

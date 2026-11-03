import AxeBuilder from "@axe-core/playwright";
import { readFileSync } from "node:fs";
import { test, expect } from "@playwright/test";
const fixtureFile = process.env.E2E_EXTENSIONS_FIXTURE;
type Fixture = {
  car: string;
  name: string;
  vin: string;
  refueling: string;
  photo: { id: string; url: string; metadata: Record<string, string> };
};
const fixtures: Record<string, Fixture> = fixtureFile
  ? JSON.parse(readFileSync(fixtureFile, "utf8"))
  : {};
test("rozšíření: VIN návrh, foto, OCR, servis, CSV a offline synchronizace", async ({
  page,
  context,
}, info) => {
  test.setTimeout(90000);
  test.skip(
    !fixtureFile,
    "Vyžaduje syntetické fixtures připravené chráněným backendovým příkazem.",
  );
  const fixture = fixtures[info.project.name];
  await page.goto("/prihlaseni");
  await page.getByLabel("Uživatelské jméno").fill("e2e-admin");
  await page
    .getByLabel("Heslo", { exact: true })
    .fill("Synthetic-Test-Account-2026!");
  await page.getByRole("button", { name: "Přihlásit se", exact: true }).click();
  await expect(page.getByRole("heading", { name: /Dobrý den/ })).toBeVisible();
  await page.goto(`/auta/${fixture.car}/upravit`);
  await page.getByRole("button", { name: "Načíst uložený návrh VIN" }).click();
  await page.getByLabel("Značka: Testovací značka").check();
  await page.getByLabel("Model: Testovací model").check();
  await page.getByRole("button", { name: "Použít vybraná pole" }).click();
  await page.getByRole("button", { name: "Uložit změny", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: fixture.name, exact: true }),
  ).toBeVisible();
  await page.route(`**/api/v1/vehicles/${fixture.car}/photo-search/`, (route) =>
    route.fulfill({ json: { results: [fixture.photo] } }),
  );
  await page.getByRole("button", { name: "Hledat fotografie modelu" }).click();
  await page
    .getByLabel("Zkontroloval/a jsem shodu modelu/generace/karoserie")
    .check();
  await Promise.all([
    page.waitForResponse(
      (response) =>
        response.url().endsWith(`/vehicles/${fixture.car}/photo/`) &&
        response.request().method() === "POST" &&
        response.ok(),
    ),
    page.getByRole("button", { name: "Vybrat fotografii" }).click(),
  ]);
  await expect(
    page.getByRole("button", { name: "Vybrat fotografii" }),
  ).toHaveCount(0);
  await expect(
    page.getByText("Syntetický testovací autor", { exact: false }),
  ).toBeVisible();
  await page.goto(`/tankovani/${fixture.refueling}/upravit`);
  await page
    .getByRole("button", { name: "Rozpoznat účtenku", exact: true })
    .click();
  await expect(
    page.getByText("Tesseract 5.5.4 / ces+eng fast / psm6"),
  ).toBeVisible();
  await page.getByLabel("Litry: 10.500", { exact: false }).check();
  await page.getByLabel("Částka: 420.00", { exact: false }).check();
  await page.getByRole("button", { name: "Použít vybraná pole" }).click();
  await page.getByRole("button", { name: "Uložit změny", exact: true }).click();
  await expect(page).toHaveURL(
    new RegExp(`/tankovani/${fixture.refueling}(?:\\?|$)`),
  );
  await page.goto(`/auta/${fixture.car}/udalosti`);
  await page
    .getByLabel("Název *", { exact: true })
    .fill(`Kontrola termínu ${fixture.car}`);
  await page.getByLabel("Datum *", { exact: true }).fill("2026-01-01");
  await page.getByLabel("Částka (Kč)", { exact: true }).fill("100.25");
  await page
    .getByLabel("Další termín / platnost do", { exact: true })
    .fill("2026-11-01");
  await page
    .getByRole("button", { name: "Uložit událost", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: `Servis · Kontrola termínu ${fixture.car}`,
    }),
  ).toBeVisible();
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await page.screenshot({
    path: `../.runtime/phase8-events-${info.project.name}.png`,
    fullPage: true,
  });
  await page.goto("/pripominky");
  await expect(
    page.getByRole("heading", {
      name: `Kontrola termínu ${fixture.car}`,
      exact: true,
    }),
  ).toBeVisible();
  await page.goto(`/auta/${fixture.car}/import`);
  await page
    .getByLabel("Obsah CSV", { exact: true })
    .fill(
      "date;liters;total_amount;odometer_km\n2026-01-01;5.000;200.00;10000\n2026-01-02;2.000;80.00;10100",
    );
  await page.getByRole("button", { name: "Připravit náhled" }).click();
  await expect(
    page.getByRole("heading", { name: "Náhled · 2 řádků" }),
  ).toBeVisible();
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await page.screenshot({
    path: `../.runtime/phase8-import-${info.project.name}.png`,
    fullPage: true,
  });
  await page.getByLabel("Zkontroloval/a jsem řádky").check();
  await page
    .getByRole("button", { name: "Potvrdit import do databáze" })
    .click();
  await expect(
    page.getByText("Import uložen: 2 záznamů.", { exact: false }),
  ).toBeVisible();
  await page.goto(`/tankovani/nove?vehicle_id=${fixture.car}`);
  await expect(page.getByLabel("Datum *", { exact: true })).not.toHaveValue("");
  await page.getByLabel("Litry *", { exact: true }).fill("12.500");
  await page.getByLabel("Cena za litr (Kč)", { exact: true }).fill("40");
  await page
    .getByLabel("Přesná částka z účtenky (Kč)", { exact: true })
    .fill("500.00");
  await page.getByLabel("Tachometr (km)", { exact: true }).fill("20000");
  await context.setOffline(true);
  await page
    .getByRole("button", { name: "Zařadit do dočasné offline fronty" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Neuložené offline zápisy" }),
  ).toBeVisible();
  await context.setOffline(false);
  await page
    .getByRole("button", { name: "Uložit do databáze", exact: true })
    .click();
  await expect(
    page.getByText("Záznam byl uložen do databáze.", { exact: false }),
  ).toBeVisible();
  const records = await page.request.get(
    `/api/v1/refuelings/?vehicle_id=${fixture.car}`,
  );
  expect((await records.json()).count).toBe(4);
});

import { expect, test, type Page } from "@playwright/test";

const admin = process.env.E2E_USERNAME || "e2e-admin";
const password = process.env.E2E_PASSWORD || "Synthetic-Test-Account-2026!";
const newPassword = "Synthetic-New-Password-2026!";

async function signIn(page: Page, username = admin, secret = password) {
  await page.goto("/prihlaseni");
  await page.getByLabel("Uživatelské jméno", { exact: true }).fill(username);
  await page.getByLabel("Heslo", { exact: true }).fill(secret);
  await page.getByRole("button", { name: "Přihlásit se", exact: true }).click();
  await expect(page).not.toHaveURL(/\/prihlaseni$/);
}

async function signOut(page: Page) {
  await page.goto("/prehled");
  await page.getByRole("button", { name: /^Odhlásit se/ }).click();
  await expect(page).toHaveURL(/\/prihlaseni$/);
}

test("přihlášení, profil a odhlášení", async ({ page }, info) => {
  await signIn(page);
  await expect(page.getByRole("heading", { name: /Dobrý den/ })).toBeVisible();
  await page.screenshot({
    path: `../.runtime/overview-${info.project.name}.png`,
    fullPage: true,
  });
  await page.goto("/nastaveni");
  await expect(
    page.getByRole("heading", { name: "Osobní profil" }),
  ).toBeVisible();
  await page
    .getByLabel("Zobrazované jméno", { exact: true })
    .fill("Testovací správce");
  await page.getByRole("button", { name: "Uložit profil" }).click();
  await expect(page.getByRole("status")).toHaveText(/Profil byl uložen/);
  await signOut(page);
  await page.goto("/administrace/uzivatele");
  await expect(page).toHaveURL(/\/prihlaseni$/);
});

test("vytvoření účtu a povinná změna jednorázového hesla", async ({
  page,
}, info) => {
  const username = `e2e-${info.project.name}-${Date.now()}`;
  await signIn(page);
  await expect(page.getByRole("heading", { name: /Dobrý den/ })).toBeVisible();
  await page.goto("/administrace/uzivatele");
  await page.getByRole("button", { name: "Přidat uživatele" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Uživatelské jméno", { exact: true }).fill(username);
  await dialog
    .getByLabel("Zobrazované jméno", { exact: true })
    .fill("Testovací řidič");
  await dialog
    .getByLabel("Vaše aktuální heslo", { exact: true })
    .fill(password);
  await dialog.getByRole("button", { name: "Vytvořit účet" }).click();
  await expect(
    page.getByRole("heading", { name: "Jednorázové dočasné heslo" }),
  ).toBeVisible();
  const temporary = await page
    .getByLabel("Dočasné heslo", { exact: true })
    .inputValue();
  await page.getByRole("button", { name: "Hotovo", exact: true }).click();
  await signOut(page);
  await signIn(page, username, temporary);
  await expect(page).toHaveURL(/\/zmena-hesla$/);
  await page.goto("/administrace/uzivatele");
  await expect(page).toHaveURL(/\/zmena-hesla$/);
  await page.getByLabel("Nové heslo", { exact: true }).fill(newPassword);
  await page.getByLabel("Nové heslo znovu", { exact: true }).fill(newPassword);
  await page.getByRole("button", { name: "Nastavit nové heslo" }).click();
  await expect(page.getByRole("heading", { name: /Dobrý den/ })).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "Administrace", exact: true }),
  ).toHaveCount(0);
  await signOut(page);
  await signIn(page, username, newPassword);
  await expect(page.getByRole("heading", { name: /Dobrý den/ })).toBeVisible();
});

test("profil a vzhled jsou společné pro nový prohlížeč i smazané cookies", async ({
  page,
  browser,
}) => {
  await signIn(page);
  await expect(page.getByRole("heading", { name: /Dobrý den/ })).toBeVisible();
  await page.goto("/nastaveni");
  await page
    .getByLabel("Zobrazované jméno", { exact: true })
    .fill("Profil uložený v databázi");
  await page
    .getByLabel("Vzhled aplikace", { exact: true })
    .selectOption("DARK");
  await page.getByRole("button", { name: "Uložit profil" }).click();
  await expect(page.getByRole("status")).toHaveText(/Profil byl uložen/);
  await expect(page.locator("html")).toHaveClass(/dark/);

  await page.context().clearCookies();
  await page.reload();
  await expect(page).toHaveURL(/\/prihlaseni$/);
  await signIn(page);
  await page.goto("/nastaveni");
  await expect(
    page.getByLabel("Zobrazované jméno", { exact: true }),
  ).toHaveValue("Profil uložený v databázi");
  await expect(page.getByLabel("Vzhled aplikace", { exact: true })).toHaveValue(
    "DARK",
  );

  const otherContext = await browser.newContext({
    baseURL: process.env.E2E_BASE_URL || "http://localhost:8080",
  });
  const otherPage = await otherContext.newPage();
  try {
    await signIn(otherPage);
    await otherPage.goto("/nastaveni");
    await expect(
      otherPage.getByLabel("Zobrazované jméno", { exact: true }),
    ).toHaveValue("Profil uložený v databázi");
    await expect(
      otherPage.getByLabel("Vzhled aplikace", { exact: true }),
    ).toHaveValue("DARK");
    await expect(otherPage.locator("html")).toHaveClass(/dark/);
  } finally {
    await otherContext.close();
  }

  await page
    .getByLabel("Zobrazované jméno", { exact: true })
    .fill("Testovací správce");
  await page
    .getByLabel("Vzhled aplikace", { exact: true })
    .selectOption("SYSTEM");
  await page.getByRole("button", { name: "Uložit profil" }).click();
  await expect(page.getByRole("status")).toHaveText(/Profil byl uložen/);
});

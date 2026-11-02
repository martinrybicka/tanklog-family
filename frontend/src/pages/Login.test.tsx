import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi, describe, it, expect } from "vitest";
import * as apiModule from "../lib/api";
import { Login } from "./Login";

function setup() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/prihlaseni"]}>
        <Routes>
          <Route path="/prihlaseni" element={<Login />} />
          <Route path="/" element={<p>Přehled přihlášeného</p>} />
          <Route path="/zmena-hesla" element={<p>Povinná změna hesla</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return userEvent.setup();
}

describe("Přihlášení", () => {
  it("ukazuje české chyby prázdného formuláře a nevolá API", async () => {
    const spy = vi.spyOn(apiModule, "api");
    const user = setup();
    await user.click(screen.getByRole("button", { name: "Přihlásit se" }));
    expect(await screen.findByText("Zadejte uživatelské jméno.")).toBeVisible();
    expect(screen.getByText("Zadejte heslo.")).toBeVisible();
    expect(spy).not.toHaveBeenCalled();
  });
  it("zobrazí chybu serveru a zachová vyplněné jméno", async () => {
    vi.spyOn(apiModule, "api").mockRejectedValue(
      new apiModule.ApiError(
        403,
        "invalid_credentials",
        "Přihlašovací údaje nejsou správné.",
      ),
    );
    const user = setup();
    await user.type(screen.getByLabelText("Uživatelské jméno"), "driver");
    await user.type(
      screen.getByLabelText("Heslo", { exact: true }),
      "incorrect",
    );
    await user.click(screen.getByRole("button", { name: "Přihlásit se" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Přihlašovací údaje nejsou správné.",
    );
    expect(screen.getByLabelText("Uživatelské jméno")).toHaveValue("driver");
  });
  it.each([false, true])(
    "směruje podle povinné změny hesla: %s",
    async (restricted) => {
      vi.spyOn(apiModule, "api").mockResolvedValue({
        data: {
          id: "user",
          username: "driver",
          must_change_password: restricted,
        },
        etag: null,
      });
      vi.spyOn(apiModule, "refreshCsrf").mockResolvedValue();
      const user = setup();
      await user.type(screen.getByLabelText("Uživatelské jméno"), "driver");
      await user.type(
        screen.getByLabelText("Heslo", { exact: true }),
        "testpassword",
      );
      await user.click(screen.getByRole("button", { name: "Přihlásit se" }));
      expect(
        await screen.findByText(
          restricted ? "Povinná změna hesla" : "Přehled přihlášeného",
        ),
      ).toBeVisible();
    },
  );
});

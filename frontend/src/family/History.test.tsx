import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { expect, it, vi } from "vitest";
import * as apiModule from "../lib/api";
import { FamilyReceiptDetail } from "./History";

function setup(allowed: boolean, failure = false) {
  const api = vi
    .spyOn(apiModule, "api")
    .mockImplementation(async (_path, options) => {
      if (options?.method === "DELETE") {
        if (failure) throw new Error("Záznam se mezitím změnil.");
        return { data: null, etag: null };
      }
      return {
        data: {
          id: "record",
          vehicle_name: "Rodinné auto",
          date: "2026-01-10",
          total_amount: "350.00",
          liters: "10.000",
          odometer_km: 1100,
          is_full_tank: true,
          permissions: { edit: true, delete: allowed },
          receipt: { version: 1 },
        },
        etag: '"refueling:record:2"',
      };
    });
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter initialEntries={["/historie/record"]}>
        <Routes>
          <Route path="/historie/:id" element={<FamilyReceiptDetail />} />
          <Route path="/historie" element={<h1>Historie po smazání</h1>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return api;
}

it("vyžaduje potvrzení a po smazání vrátí uživatele do historie", async () => {
  const api = setup(true);
  const user = userEvent.setup();
  const action = await screen.findByRole("button", {
    name: "Smazat tankování a účtenku",
  });
  await user.click(action);
  expect(await screen.findByRole("dialog")).toHaveTextContent(
    "celé tankování i fotografie účtenky",
  );
  await user.click(screen.getByRole("button", { name: "Zrušit" }));
  expect(api.mock.calls.some((call) => call[1]?.method === "DELETE")).toBe(
    false,
  );
  await user.click(action);
  await user.click(screen.getByRole("button", { name: "Potvrdit smazání" }));
  expect(
    await screen.findByRole("heading", { name: "Historie po smazání" }),
  ).toBeVisible();
  expect(api).toHaveBeenCalledWith("refuelings/record/", {
    method: "DELETE",
    etag: '"refueling:record:2"',
  });
});

it("bez oprávnění nenabízí mazání", async () => {
  setup(false);
  await screen.findByRole("heading", { name: "Rodinné auto" });
  expect(
    screen.queryByRole("button", { name: "Smazat tankování a účtenku" }),
  ).not.toBeInTheDocument();
});

it("při konfliktu ponechá detail i dialog a nabídne aktuální záznam", async () => {
  setup(true, true);
  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("button", { name: "Smazat tankování a účtenku" }),
  );
  await user.click(screen.getByRole("button", { name: "Potvrdit smazání" }));
  expect(await screen.findByText("Záznam se mezitím změnil.")).toBeVisible();
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Načíst aktuální záznam" }),
    ).toBeEnabled(),
  );
  expect(screen.getByRole("dialog")).toBeVisible();
});

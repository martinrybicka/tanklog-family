import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import * as apiModule from "../lib/api";
import { ReceiptWizard } from "./ReceiptWizard";

function setup(startWithPhoto = false) {
  const api = vi.spyOn(apiModule, "api").mockImplementation(async (path) => {
    if (path.startsWith("vehicles/"))
      return {
        data: {
          next: null,
          results: [
            {
              id: "car",
              name: "Auto",
              fuel_type: "PETROL",
              permissions: { create_refueling: true },
            },
          ],
        },
        etag: null,
      };
    if (path === "family/settings/")
      return { data: { default_vehicle_id: "car" }, etag: null };
    if (path.endsWith("complete/"))
      return {
        data: { id: "saved", total_amount: "1563.45", liters: "42.37" },
        etag: null,
      };
    if (path === "family/receipts/")
      return {
        data: { id: "draft", vehicle_id: "car", suggestions: {} },
        etag: '"upload:1"',
      };
    return {
      data: {
        id: "draft",
        vehicle_id: "car",
        result_id: null,
        preview_url: "/preview/",
        suggestions: {
          date: { value: "2025-01-17" },
          liters: { value: "42.37" },
          total_amount: { value: "1563.45" },
          fuel_type: { value: "PETROL" },
          station_code: { value: "OTHER" },
          station_custom_name: { value: "PetrolFlex" },
        },
      },
      etag: '"draft:1"',
    };
  });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter
        initialEntries={[startWithPhoto ? "/uctenka" : "/uctenka?draft=draft"]}
      >
        <ReceiptWizard />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return api;
}

it("předvyplní z OCR palivo i název stanice a odešle je při potvrzení", async () => {
  const api = setup();
  const user = userEvent.setup();
  expect(await screen.findByLabelText("Druh paliva")).toHaveValue("PETROL");
  expect(screen.getByLabelText("Čerpací stanice", { exact: true })).toHaveValue(
    "OTHER",
  );
  expect(screen.getByLabelText("Název čerpací stanice")).toHaveValue(
    "PetrolFlex",
  );
  await user.click(screen.getByRole("button", { name: "Potvrdit a uložit" }));
  await screen.findByRole("heading", { name: "Hotovo. Šťastnou cestu!" });
  expect(api).toHaveBeenCalledWith(
    "family/receipts/draft/complete/",
    expect.objectContaining({
      method: "POST",
      body: expect.objectContaining({
        fuel_type: "PETROL",
        station_code: "OTHER",
        station_custom_name: "PetrolFlex",
      }),
    }),
  );
});

it("dovolí opravit OCR a při volbě řetězce neposílá starý vlastní název", async () => {
  const api = setup();
  const user = userEvent.setup();
  await user.selectOptions(
    await screen.findByLabelText("Druh paliva"),
    "DIESEL",
  );
  await user.selectOptions(
    screen.getByLabelText("Čerpací stanice", { exact: true }),
    "SHELL",
  );
  expect(
    screen.queryByLabelText("Název čerpací stanice"),
  ).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Potvrdit a uložit" }));
  await screen.findByRole("heading", { name: "Hotovo. Šťastnou cestu!" });
  expect(api).toHaveBeenCalledWith(
    "family/receipts/draft/complete/",
    expect.objectContaining({
      body: expect.objectContaining({
        fuel_type: "DIESEL",
        station_code: "SHELL",
        station_custom_name: "",
      }),
    }),
  );
});

it("po vyfocení automaticky nahraje fotku, spustí OCR a vyplní návrhy", async () => {
  const api = setup(true);
  await userEvent
    .setup()
    .upload(
      await screen.findByLabelText(/Vyfotit účtenku JPG/),
      new File(["fotka"], "uctenka.jpg", { type: "image/jpeg" }),
    );
  expect(await screen.findByLabelText("Natankováno (l)")).toHaveValue("42.37");
  expect(screen.getByLabelText("Zaplaceno (Kč)")).toHaveValue("1563.45");
  expect(screen.getByLabelText("Druh paliva")).toHaveValue("PETROL");
  expect(screen.getByLabelText("Název čerpací stanice")).toHaveValue(
    "PetrolFlex",
  );
  expect(
    api.mock.calls.filter(([path]) => path === "family/receipts/"),
  ).toHaveLength(1);
  expect(api).toHaveBeenCalledWith(
    "family/receipts/draft/recognize/",
    expect.objectContaining({ method: "POST", etag: '"upload:1"' }),
  );
});

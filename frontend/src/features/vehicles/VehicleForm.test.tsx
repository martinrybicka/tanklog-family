import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import * as auth from "../../lib/auth";
import { ApiError } from "../../lib/api";
import type { Vehicle } from "../../lib/types";
import { VehicleCard } from "../../pages/Vehicles";
import { VehicleForm } from "./VehicleForm";

async function requiredFields() {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Název auta *"), "Rodinné auto");
  await user.type(screen.getByLabelText("Značka *"), "Škoda");
  await user.type(screen.getByLabelText("Model *"), "Octavia");
  await user.type(
    screen.getByLabelText("Počáteční tachometr (km) *"),
    "123000",
  );
  return user;
}
describe("Formulář a karty aut", () => {
  it("neodešle prázdná povinná pole", async () => {
    const save = vi.fn();
    render(<VehicleForm onSave={save} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Vytvořit auto" }),
    );
    expect(await screen.findByText("Vyplňte název auta.")).toBeVisible();
    expect(save).not.toHaveBeenCalled();
  });
  it("zobrazí chybný VIN a neplatnou normu v technických údajích", async () => {
    const save = vi.fn();
    render(<VehicleForm onSave={save} />);
    const user = await requiredFields();
    await user.click(screen.getByText("Technické údaje a norma (nepovinné)"));
    await user.type(screen.getByLabelText("VIN"), "I123");
    await user.type(
      screen.getByLabelText("Normovaná spotřeba (l/100 km)"),
      "0",
    );
    await user.click(screen.getByRole("button", { name: "Vytvořit auto" }));
    expect(
      await screen.findByText("VIN musí mít 17 znaků bez písmen I, O a Q."),
    ).toBeVisible();
    expect(
      screen.getByLabelText("Normovaná spotřeba (l/100 km)"),
    ).toHaveAttribute("aria-invalid", "true");
    expect(save).not.toHaveBeenCalled();
  });
  it("odešle desetinnou čárku jako přesný řetězec a prázdnou normu jako null", async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    render(<VehicleForm onSave={save} />);
    const user = await requiredFields();
    await user.click(screen.getByText("Technické údaje a norma (nepovinné)"));
    await user.type(screen.getByLabelText("Výkon (kW)"), "110,25");
    await user.click(screen.getByRole("button", { name: "Vytvořit auto" }));
    expect(save).toHaveBeenCalledWith(
      expect.objectContaining({
        power_kw: "110.25",
        standard_consumption_l_100km: null,
        initial_odometer_km: 123000,
        vin: null,
      }),
    );
  });
  it("při konfliktu zachová formulář a nabídne nové načtení", async () => {
    render(
      <VehicleForm
        onReload={vi.fn()}
        onSave={vi
          .fn()
          .mockRejectedValue(
            new ApiError(412, "stale_version", "Údaje se mezitím změnily."),
          )}
      />,
    );
    const user = await requiredFields();
    await user.click(screen.getByRole("button", { name: "Vytvořit auto" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Údaje se mezitím změnily.",
    );
    expect(screen.getByLabelText("Název auta *")).toHaveValue("Rodinné auto");
    expect(
      screen.getByRole("button", { name: "Načíst aktuální údaje" }),
    ).toBeVisible();
  });
  it.each(["VIEWER", "CONTRIBUTOR"] as const)(
    "označí sdílenou kartu a roli %s",
    (role) => {
      vi.spyOn(auth, "useSession").mockReturnValue({
        data: { id: "me" },
      } as ReturnType<typeof auth.useSession>);
      const vehicle = {
        id: "car",
        owner_id: "someone",
        name: "Sdílená Octavia",
        make: "Škoda",
        model: "Octavia",
        fuel_type: "PETROL",
        status: "ACTIVE",
        effective_role: role,
      } as Vehicle;
      render(
        <QueryClientProvider client={new QueryClient()}>
          <MemoryRouter>
            <VehicleCard vehicle={vehicle} />
          </MemoryRouter>
        </QueryClientProvider>,
      );
      expect(
        screen.getByText(
          new RegExp(
            `Sdílené auto · ${role === "VIEWER" ? "Čtenář" : "Přispěvatel"}`,
          ),
        ),
      ).toBeVisible();
      expect(screen.getByRole("link", { name: "Detail auta" })).toHaveAttribute(
        "href",
        "/auta/car",
      );
      expect(screen.queryByText("Upravit údaje")).not.toBeInTheDocument();
    },
  );
});

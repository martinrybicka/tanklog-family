import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import * as apiModule from "../../lib/api";
import type { Vehicle } from "../../lib/types";
import { RefuelingForm } from "./RefuelingForm";
import { suggestedTotal } from "./money";

const vehicle = {
  id: "car",
  name: "Rodinné auto",
  fuel_type: "PETROL",
  status: "ACTIVE",
  permissions: { create_refueling: true },
} as Vehicle;
function setup(save = vi.fn().mockResolvedValue(undefined)) {
  vi.spyOn(apiModule, "api").mockImplementation(
    async (path) =>
      ({
        data: path.includes("payer-options")
          ? { today: "2026-01-10", results: [] }
          : { ordered_ids: [] },
        etag: null,
      }) as never,
  );
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter>
        <RefuelingForm vehicles={[vehicle]} onSave={save} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { user: userEvent.setup(), save };
}
describe("Tankování", () => {
  it("počítá návrh bez binárních desetinných odchylek", () => {
    expect(suggestedTotal("1,005", "1")).toBe("1.01");
    expect(suggestedTotal("42.350", "38.9000")).toBe("1647.42");
    expect(suggestedTotal("-1", "10")).toBe("");
  });
  it("odmítne neplatnou přesnost a chybějící cenu/částku", async () => {
    const { user, save } = setup();
    await screen.findByDisplayValue("2026-01-10");
    await user.type(screen.getByLabelText("Litry *"), "1.0001");
    await user.click(screen.getByRole("button", { name: "Uložit tankování" }));
    expect(
      await screen.findByText("Zadejte částku nebo cenu za litr."),
    ).toBeVisible();
    expect(save).not.toHaveBeenCalled();
  });
  it("zachová přesnou částku, nenastaví plnou nádrž a opakuje stejný klíč", async () => {
    const save = vi
      .fn()
      .mockRejectedValueOnce(
        new apiModule.ApiError(409, "confirmation_required", "Potvrďte", {}, [
          { code: "missing_odometer", message: "Chybí tachometr." },
        ]),
      )
      .mockResolvedValue(undefined);
    const { user } = setup(save);
    await screen.findByDisplayValue("2026-01-10");
    await user.type(screen.getByLabelText("Litry *"), "42,350");
    await user.type(screen.getByLabelText("Cena za litr (Kč)"), "38,9");
    await user.type(
      screen.getByLabelText("Přesná částka z účtenky (Kč)"),
      "1600,00",
    );
    await user.click(screen.getByRole("button", { name: "Uložit tankování" }));
    expect(await screen.findByRole("dialog")).toHaveTextContent(
      "Chybí tachometr.",
    );
    await user.click(
      screen.getByRole("button", { name: "Potvrdit údaje a uložit" }),
    );
    expect(save).toHaveBeenCalledTimes(2);
    expect(save.mock.calls[0][1]).toBe(save.mock.calls[1][1]);
    expect(save.mock.calls[1][0]).toEqual(
      expect.objectContaining({
        liters: "42.350",
        total_amount: "1600.00",
        odometer_km: null,
        is_full_tank: false,
        confirmed_warning_codes: ["missing_odometer"],
      }),
    );
  });
  it("po síťové chybě nechá částku i litry ve formuláři", async () => {
    const { user } = setup(
      vi
        .fn()
        .mockRejectedValue(
          new apiModule.ApiError(0, "network_error", "Spojení selhalo."),
        ),
    );
    await screen.findByDisplayValue("2026-01-10");
    await user.type(screen.getByLabelText("Litry *"), "10");
    await user.type(
      screen.getByLabelText("Přesná částka z účtenky (Kč)"),
      "320",
    );
    await user.click(screen.getByRole("button", { name: "Uložit tankování" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Spojení selhalo.",
    );
    expect(screen.getByLabelText("Litry *")).toHaveValue("10");
    expect(screen.getByLabelText("Přesná částka z účtenky (Kč)")).toHaveValue(
      "320",
    );
  });
});

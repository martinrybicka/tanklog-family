import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { PeriodPicker } from "./PeriodPicker";
import { IntervalEvidence } from "../../pages/Dashboard";
import { dateText, decimalText } from "./format";
import { shiftPeriod } from "./period";
import type { IntervalDetail, Period } from "./types";
const month: Period = {
  period: "month",
  anchor_date: "2024-01-31",
  date_from: "2024-01-01",
  date_to: "2024-01-31",
  group_by: "day",
  timezone: "Europe/Prague",
};
describe("kalendářní období a přesné hodnoty", () => {
  it("posune měsíc od jeho hranice bez přeskočení února", () => {
    expect(shiftPeriod(month, 1).get("anchor_date")).toBe("2024-02-01");
    expect(shiftPeriod(month, -1).get("anchor_date")).toBe("2023-12-01");
  });
  it("posune vlastní přestupný rozsah o stejný počet kalendářních dnů", () => {
    const p: Period = {
      ...month,
      period: "custom",
      anchor_date: null,
      date_from: "2024-02-28",
      date_to: "2024-03-01",
    };
    expect(shiftPeriod(p, 1).get("date_from")).toBe("2024-03-02");
    expect(shiftPeriod(p, 1).get("date_to")).toBe("2024-03-04");
    expect(shiftPeriod(p, -1).get("date_from")).toBe("2024-02-25");
  });
  it("nemění obchodní datum při přechodu letního času a roku", () => {
    expect(
      shiftPeriod({ ...month, period: "day", date_from: "2026-03-29" }, 1).get(
        "anchor_date",
      ),
    ).toBe("2026-03-30");
    expect(
      shiftPeriod({ ...month, period: "week", date_from: "2025-12-29" }, 1).get(
        "anchor_date",
      ),
    ).toBe("2026-01-05");
    expect(
      shiftPeriod(
        { ...month, period: "year", date_from: "2024-01-01" },
        -1,
      ).get("anchor_date"),
    ).toBe("2023-01-01");
    expect(dateText("2026-10-25")).toBe("25. 10. 2026");
  });
  it("odlišuje null a nulu a zaokrouhluje HALF_UP i bez float", () => {
    expect(decimalText(null)).toBe("Nedostatek dat");
    expect(decimalText("0.000000")).toBe("0,00");
    expect(decimalText("7.505000")).toBe("7,51");
    expect(decimalText("-1.005000")).toBe("−1,01");
    expect(decimalText("999999999999.995000")).toBe("1 000 000 000 000,00");
    expect(decimalText("5.333333")).toBe("5,33");
  });
  it("odmítne obrácený rozsah a předá platný výběr", async () => {
    const change = vi.fn();
    const user = userEvent.setup();
    render(<PeriodPicker period={month} vehicleId="auto" onChange={change} />);
    await user.selectOptions(screen.getByLabelText("Období"), "custom");
    await user.clear(screen.getByLabelText("Datum od"));
    await user.type(screen.getByLabelText("Datum od"), "2024-02-02");
    await user.click(screen.getByRole("button", { name: "Použít období" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Datum od nesmí být po datu do",
    );
    expect(change).not.toHaveBeenCalled();
    await user.clear(screen.getByLabelText("Datum do"));
    await user.type(screen.getByLabelText("Datum do"), "2024-02-05");
    await user.click(screen.getByRole("button", { name: "Použít období" }));
    expect(change.mock.calls[0][0].get("date_from")).toBe("2024-02-02");
    expect(change.mock.calls[0][0].get("anchor_date")).toBeNull();
    expect(change.mock.calls[0][0].get("vehicle_id")).toBe("auto");
  });
  it("ukáže kotvu mimo filtr a null u neplatného intervalu", () => {
    const data = {
      start_date: "2026-01-31",
      end_date: "2026-02-05",
      crosses_period_start: true,
      explanation: "Podle konce.",
      consumption_l_100km: null,
      purchase_cost_czk_100km: null,
      liters: "45",
      distance_km: 600,
      amount: "1800",
      reasons: ["HISTORY_GAP"],
      warnings: [],
      records: [
        {
          id: "a",
          date: "2026-01-31",
          day_sequence: 1,
          liters: "50",
          total_amount: "2000",
          odometer_km: null,
          fuel_type: "PETROL",
          is_full_tank: true,
          used_for_totals: false,
        },
      ],
    } as unknown as IntervalDetail;
    render(
      <MemoryRouter>
        <IntervalEvidence interval={data} />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Počáteční kotva je před obdobím/)).toBeVisible();
    expect(screen.getByText("Pouze počáteční kotva")).toBeVisible();
    expect(screen.getByText("Neuveden")).toBeVisible();
    expect(screen.getByText(/označená mezera/)).toBeVisible();
    expect(screen.getAllByText(/Nedostatek dat/).length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: /31. 1. 2026/ })).toHaveAttribute(
      "href",
      "/tankovani/a",
    );
  });
});

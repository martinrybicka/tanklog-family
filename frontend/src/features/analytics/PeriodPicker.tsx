import { useState } from "react";
import { Button, ErrorMessage } from "../../components/ui";
import { dateText } from "./format";
import { periodParams, shiftPeriod } from "./period";
import type { Period } from "./types";
export function PeriodPicker({
  period,
  vehicleId,
  onChange,
}: {
  period: Period;
  vehicleId: string;
  onChange: (params: URLSearchParams) => void;
}) {
  const [kind, setKind] = useState(period.period);
  const [anchor, setAnchor] = useState(period.anchor_date || period.date_from);
  const [from, setFrom] = useState(period.date_from);
  const [to, setTo] = useState(period.date_to);
  const [group, setGroup] = useState(period.group_by);
  const [error, setError] = useState("");
  return (
    <section className="panel period-panel" aria-label="Výběr období">
      <div className="period-navigation">
        <Button
          variant="secondary"
          aria-label="Předchozí období"
          onClick={() => onChange(shiftPeriod(period, -1, vehicleId))}
        >
          ←
        </Button>
        <strong>
          {dateText(period.date_from)} – {dateText(period.date_to)}
        </strong>
        <Button
          variant="secondary"
          aria-label="Následující období"
          onClick={() => onChange(shiftPeriod(period, 1, vehicleId))}
        >
          →
        </Button>
      </div>
      <form
        className="history-filters"
        onSubmit={(e) => {
          e.preventDefault();
          if (kind === "custom" && from > to) {
            setError("Datum od nesmí být po datu do.");
            return;
          }
          setError("");
          onChange(
            periodParams(
              {
                ...period,
                period: kind,
                anchor_date: anchor,
                date_from: from,
                date_to: to,
                group_by: group,
              },
              vehicleId,
            ),
          );
        }}
      >
        <label>
          Období
          <select
            className="input"
            value={kind}
            onChange={(e) => setKind(e.target.value as Period["period"])}
          >
            <option value="day">Den</option>
            <option value="week">Týden (pondělí–neděle)</option>
            <option value="month">Měsíc</option>
            <option value="year">Rok</option>
            <option value="custom">Vlastní rozsah</option>
          </select>
        </label>
        {kind === "custom" ? (
          <>
            <label>
              Datum od
              <input
                className="input"
                type="date"
                required
                value={from}
                min="0002-01-01"
                max="9998-12-31"
                onChange={(e) => setFrom(e.target.value)}
              />
            </label>
            <label>
              Datum do
              <input
                className="input"
                type="date"
                required
                value={to}
                min="0002-01-01"
                max="9998-12-31"
                onChange={(e) => setTo(e.target.value)}
              />
            </label>
          </>
        ) : (
          <label>
            Datum v období
            <input
              className="input"
              type="date"
              required
              value={anchor}
              min="0002-01-01"
              max="9998-12-31"
              onChange={(e) => setAnchor(e.target.value)}
            />
          </label>
        )}
        <label>
          Seskupení nákupních grafů
          <select
            className="input"
            value={group}
            onChange={(e) => setGroup(e.target.value as Period["group_by"])}
          >
            <option value="day">Dny</option>
            <option value="week">Týdny od pondělí</option>
            <option value="month">Měsíce</option>
          </select>
        </label>
        <Button type="submit">Použít období</Button>
      </form>
      <ErrorMessage>{error}</ErrorMessage>
      <p className="muted">
        Kalendářní data podle Prahy. Vlastní rozsah posouváme o stejný počet
        dnů.
      </p>
    </section>
  );
}

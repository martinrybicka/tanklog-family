import { useState } from "react";
import { Button } from "../../components/ui";
export type Suggestion = {
  value: string | number;
  confidence?: string;
  source?: string;
};
const labels: Record<string, string> = {
  make: "Značka",
  model: "Model",
  engine_displacement_cc: "Objem motoru (cm³)",
  power_kw: "Výkon (kW)",
  fuel_type: "Palivo",
  date: "Datum",
  liters: "Litry",
  unit_price_entered: "Cena za litr",
  total_amount: "Částka",
  odometer_km: "Tachometr",
  station_code: "Stanice",
};
export function Suggestions({
  values,
  onApply,
}: {
  values: Record<string, Suggestion>;
  onApply: (values: Record<string, string | number>) => void;
}) {
  const [selected, setSelected] = useState<string[]>([]);
  return (
    <fieldset className="extension-suggestions">
      <legend>Vyberte jednotlivé návrhy ke kontrole</legend>
      {Object.entries(values).map(([name, item]) => (
        <label key={name}>
          <input
            type="checkbox"
            checked={selected.includes(name)}
            onChange={(e) =>
              setSelected(
                e.target.checked
                  ? [...selected, name]
                  : selected.filter((v) => v !== name),
              )
            }
          />
          {labels[name] || name}: <strong>{item.value}</strong>
          {item.confidence !== undefined && (
            <span> · jistota {item.confidence} %</span>
          )}
          {item.source && <small>{item.source}</small>}
        </label>
      ))}
      <Button
        type="button"
        disabled={!selected.length}
        onClick={() =>
          onApply(
            Object.fromEntries(
              selected.map((name) => [name, values[name].value]),
            ),
          )
        }
      >
        Použít vybraná pole
      </Button>
    </fieldset>
  );
}

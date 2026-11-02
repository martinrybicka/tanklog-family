import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";
import { Button, ErrorMessage, Field, Input, Modal } from "../../components/ui";
import { api, ApiError, errorText } from "../../lib/api";
import type { Refueling, Vehicle } from "../../lib/types";
import { fuels } from "../vehicles/VehicleForm";
import { stations, suggestedTotal } from "./money";

const decimal = (places: number, optional = false) =>
  z
    .string()
    .refine(
      (value) =>
        (optional && value === "") ||
        new RegExp(`^\\d+([.,]\\d{1,${places}})?$`).test(value),
      `Zadejte nezáporné číslo, nejvýše ${places} desetinná místa.`,
    );
const schema = z
  .object({
    vehicle_id: z.string().min(1, "Vyberte auto."),
    date: z.string().min(1, "Vyberte datum."),
    liters: decimal(3).refine(
      (v) => Number(v.replace(",", ".")) > 0,
      "Litry musí být kladné.",
    ),
    unit_price_entered: decimal(4, true),
    total_amount: decimal(2, true),
    odometer_km: z
      .string()
      .refine(
        (v) => v === "" || (/^\d+$/.test(v) && Number(v) <= 99999999),
        "Zadejte celé km od 0 do 99 999 999.",
      ),
    day_sequence: z
      .string()
      .refine(
        (v) => v === "" || (/^\d+$/.test(v) && Number(v) > 0),
        "Zadejte kladnou celou pozici.",
      ),
    is_full_tank: z.boolean(),
    break_before: z.boolean(),
    fuel_type: z.string(),
    station_code: z.string(),
    station_custom_name: z.string().max(120),
    note: z.string().max(2000),
    paid_by_user_id: z.string(),
    paid_by_label: z.string().max(150),
  })
  .refine((v) => v.total_amount !== "" || v.unit_price_entered !== "", {
    path: ["total_amount"],
    message: "Zadejte částku nebo cenu za litr.",
  });
type Values = z.infer<typeof schema>;
export function RefuelingForm({
  item,
  vehicles,
  initialVehicleId,
  onSave,
  onReload,
}: {
  item?: Refueling;
  vehicles: Vehicle[];
  initialVehicleId?: string;
  onSave: (body: Record<string, unknown>, key: string) => Promise<void>;
  onReload?: () => void;
}) {
  const key = useRef(crypto.randomUUID());
  const [error, setError] = useState("");
  const [warnings, setWarnings] = useState<{ code: string; message: string }[]>(
    [],
  );
  const [pending, setPending] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [extraOpen, setExtraOpen] = useState(false);
  const defaults = {
    vehicle_id:
      item?.vehicle_id ||
      initialVehicleId ||
      (vehicles.length === 1 ? vehicles[0].id : ""),
    date: item?.date || "",
    liters: item?.liters || "",
    unit_price_entered: item?.unit_price_entered || "",
    total_amount: item?.amount_source === "ENTERED" ? item.total_amount : "",
    odometer_km: item?.odometer_km?.toString() || "",
    day_sequence: item?.day_sequence.toString() || "",
    is_full_tank: item?.is_full_tank || false,
    break_before: item?.break_before || false,
    fuel_type:
      item?.fuel_type ||
      vehicles.find((v) => v.id === initialVehicleId)?.fuel_type ||
      vehicles[0]?.fuel_type ||
      "PETROL",
    station_code: item?.station_code || "",
    station_custom_name: item?.station_custom_name || "",
    note: item?.note || "",
    paid_by_user_id: item?.paid_by_user_id || "",
    paid_by_label: item?.paid_by_label || "",
  };
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    getValues,
    formState: { errors, isSubmitting },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: defaults,
  });
  const selected = watch("vehicle_id");
  const payer = useQuery({
    queryKey: ["payer-options", selected],
    queryFn: async () => {
      const response = await api<{
        today: string;
        results: { id: string; display_name: string }[];
      }>(`vehicles/${selected}/payer-options/`);
      if (!getValues("date")) setValue("date", response.data.today);
      return response.data;
    },
    enabled: !!selected,
  });
  const order = useQuery({
    queryKey: ["refueling-order", selected, watch("date")],
    queryFn: () =>
      api<{ ordered_ids: string[] }>(
        `vehicles/${selected}/refueling-order/?date=${watch("date")}`,
      ),
    enabled: !!selected && !!watch("date"),
  });
  async function send(body: Record<string, unknown>) {
    setError("");
    setBusy(true);
    try {
      await onSave(body, key.current);
      setWarnings([]);
    } catch (e) {
      if (e instanceof ApiError && e.code === "confirmation_required") {
        setPending(body);
        setWarnings(e.warnings);
      } else {
        setError(errorText(e));
        setWarnings([]);
      }
    } finally {
      setBusy(false);
    }
  }
  const field = (
    id: keyof Values,
    label: string,
    numeric = false,
    hint?: string,
  ) => (
    <Field
      key={id}
      id={id}
      label={label}
      error={errors[id]?.message}
      hint={hint}
    >
      <Input
        id={id}
        inputMode={numeric ? "decimal" : undefined}
        aria-invalid={!!errors[id]}
        aria-describedby={errors[id] ? `${id}-error` : undefined}
        {...register(id)}
      />
    </Field>
  );
  return (
    <form
      noValidate
      onSubmit={handleSubmit(
        async (values) => {
          const body: Record<string, unknown> = {
            ...values,
            liters: values.liters.replace(",", "."),
            unit_price_entered: values.unit_price_entered
              ? values.unit_price_entered.replace(",", ".")
              : null,
            odometer_km:
              values.odometer_km !== "" ? Number(values.odometer_km) : null,
            paid_by_user_id: values.paid_by_user_id || null,
          };
          if (item) delete body.vehicle_id;
          if (values.total_amount !== "")
            body.total_amount = values.total_amount.replace(",", ".");
          else delete body.total_amount;
          if (values.day_sequence)
            body.day_sequence = Number(values.day_sequence);
          else delete body.day_sequence;
          await send(body);
        },
        () => setExtraOpen(true),
      )}
    >
      <div className="vehicle-form-grid">
        <Field
          id="vehicle_id"
          label="Auto *"
          error={errors.vehicle_id?.message}
        >
          <select
            id="vehicle_id"
            className="input"
            disabled={!!item}
            {...register("vehicle_id", {
              onChange: (e) => {
                const vehicle = vehicles.find((v) => v.id === e.target.value);
                if (vehicle) setValue("fuel_type", vehicle.fuel_type);
                setValue("paid_by_user_id", "");
                setValue("day_sequence", "");
              },
            })}
          >
            <option value="">Vyberte auto</option>
            {vehicles.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
                {v.status === "ARCHIVED" ? " · Archivované" : ""}
              </option>
            ))}
          </select>
        </Field>
        <Field id="date" label="Datum *" error={errors.date?.message}>
          <Input
            type="date"
            id="date"
            max={payer.data?.today}
            {...register("date")}
          />
        </Field>
        {field("liters", "Litry *", true)}
        {field("unit_price_entered", "Cena za litr (Kč)", true)}
        {field(
          "total_amount",
          "Přesná částka z účtenky (Kč)",
          true,
          "Zadaná částka má přednost. Prázdná se vypočte z litrů a ceny.",
        )}
        {field(
          "odometer_km",
          "Tachometr (km)",
          true,
          "Nepovinné. Chybějící údaj bude zřetelně označen.",
        )}
      </div>
      {suggestedTotal(watch("liters"), watch("unit_price_entered")) && (
        <p className="muted">
          Návrh podle litrů a ceny:{" "}
          {suggestedTotal(watch("liters"), watch("unit_price_entered")).replace(
            ".",
            ",",
          )}{" "}
          Kč. Přesná částka z účtenky má přednost.
        </p>
      )}
      {order.data && (
        <p className="muted" aria-live="polite">
          Pozice v rámci dne:{" "}
          {watch("day_sequence") ||
            (item && watch("date") === item.date
              ? item.day_sequence
              : order.data.data.ordered_ids.length + 1)}
          . V tomto dni je zatím {order.data.data.ordered_ids.length} záznamů.
          Pozici můžete změnit v dalších údajích.
        </p>
      )}
      <label className="check-label">
        <input type="checkbox" {...register("is_full_tank")} /> Plná nádrž
      </label>
      <details
        className="vehicle-optional"
        open={extraOpen || undefined}
        onToggle={(e) => setExtraOpen(e.currentTarget.open)}
      >
        <summary>Další údaje a pořadí dne</summary>
        <div className="vehicle-form-grid">
          <Field id="fuel_type" label="Skutečné palivo">
            <select id="fuel_type" className="input" {...register("fuel_type")}>
              {Object.entries(fuels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
          <Field id="station_code" label="Čerpací stanice">
            <select
              id="station_code"
              className="input"
              {...register("station_code", {
                onChange: () => setValue("station_custom_name", ""),
              })}
            >
              {Object.entries(stations).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
          {watch("station_code") === "OTHER" &&
            field("station_custom_name", "Vlastní název stanice")}
          {field(
            "day_sequence",
            "Pozice v rámci dne",
            true,
            `V tomto dni je ${order.data?.data.ordered_ids.length ?? "…"} záznamů. Prázdné pořadí přidá nový záznam na konec.`,
          )}
          <Field id="paid_by_user_id" label="Plátce – uživatel">
            <select
              className="input"
              id="paid_by_user_id"
              {...register("paid_by_user_id", {
                onChange: () => setValue("paid_by_label", ""),
              })}
            >
              <option value="">Bez výběru / vlastní název</option>
              {payer.data?.results.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.display_name}
                </option>
              ))}
            </select>
          </Field>
          {!watch("paid_by_user_id") &&
            field("paid_by_label", "Plátce – vlastní název")}
        </div>
        <Field id="note" label="Poznámka" error={errors.note?.message}>
          <textarea
            id="note"
            className="input"
            rows={3}
            {...register("note")}
          />
        </Field>
        <label className="check-label">
          <input type="checkbox" {...register("break_before")} /> Před tímto
          tankováním je mezera v evidenci / odčerpání paliva
        </label>
      </details>
      <ErrorMessage>{error}</ErrorMessage>
      <ErrorMessage>{payer.error && errorText(payer.error)}</ErrorMessage>
      <div className="vehicle-actions">
        <Button type="submit" disabled={busy || isSubmitting}>
          {busy ? "Ukládání…" : item ? "Uložit změny" : "Uložit tankování"}
        </Button>
        {error && onReload && (
          <Button type="button" variant="secondary" onClick={onReload}>
            Načíst aktuální záznam
          </Button>
        )}
        {error && <Link to="/tankovani">Ověřit výsledek v historii</Link>}
      </div>
      <Modal
        open={warnings.length > 0}
        onClose={() => {
          if (!busy) setWarnings([]);
        }}
        title="Zkontrolujte tankování"
        description="Uvedená upozornění nebrání uložení. Potvrďte, že zadané údaje a pořadí odpovídají skutečnosti."
      >
        <ul className="warning-list">
          {warnings.map((w) => (
            <li key={w.code}>{w.message}</li>
          ))}
        </ul>
        <Button
          type="button"
          disabled={busy}
          onClick={() => {
            if (pending)
              void send({
                ...pending,
                confirmed_warning_codes: warnings.map((w) => w.code),
              });
          }}
        >
          Potvrdit údaje a uložit
        </Button>
      </Modal>
    </form>
  );
}

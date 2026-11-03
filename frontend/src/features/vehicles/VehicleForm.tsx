import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button, ErrorMessage, Field, Input } from "../../components/ui";
import { errorText } from "../../lib/api";
import { VinLookup } from "../extensions/VehicleIntegrations";
import type { Vehicle } from "../../lib/types";

export const fuels: Record<string, string> = {
  CNG: "CNG (kg)",
  ELECTRIC: "Elektřina (kWh)",
  PETROL: "Benzín",
  DIESEL: "Nafta",
  LPG: "LPG",
  ETHANOL: "Ethanol",
  OTHER_LIQUID: "Jiné kapalné palivo",
};
export const roles: Record<string, string> = {
  OWNER: "Vlastník",
  ADMIN: "Administrátor",
  VIEWER: "Čtenář",
  CONTRIBUTOR: "Přispěvatel",
};
export const methodologies: Record<string, string> = {
  UNKNOWN: "Neznámá",
  WLTP: "WLTP",
  NEDC: "NEDC",
  MANUFACTURER: "Výrobce",
  USER_ESTIMATE: "Vlastní odhad",
};
const integer = (min: number, max: number, optional = false) =>
  z
    .string()
    .refine(
      (value) =>
        (optional && value === "") ||
        (/^\d+$/.test(value) && Number(value) >= min && Number(value) <= max),
      `Zadejte celé číslo od ${min} do ${max}.`,
    );
const decimal = (places: number, max: number) =>
  z
    .string()
    .refine(
      (value) =>
        value === "" ||
        (new RegExp(`^\\d+([.,]\\d{1,${places}})?$`).test(value) &&
          Number(value.replace(",", ".")) > 0 &&
          Number(value.replace(",", ".")) < max),
      `Zadejte kladné číslo menší než ${max}, nejvýše ${places} desetinná místa.`,
    );
const schema = z.object({
  name: z.string().trim().min(1, "Vyplňte název auta.").max(100),
  make: z.string().trim().min(1, "Vyplňte značku.").max(100),
  model: z.string().trim().min(1, "Vyplňte model.").max(100),
  fuel_type: z.enum([
    "PETROL",
    "DIESEL",
    "LPG",
    "ETHANOL",
    "OTHER_LIQUID",
    "CNG",
    "ELECTRIC",
  ]),
  initial_odometer_km: integer(0, 99999999),
  manufacture_year: integer(
    1886,
    Number(
      new Intl.DateTimeFormat("en", {
        year: "numeric",
        timeZone: "Europe/Prague",
      }).format(new Date()),
    ) + 1,
    true,
  ),
  registration_plate: z.string().max(20),
  vin: z
    .string()
    .trim()
    .refine(
      (value) => !value || /^[A-HJ-NPR-Z0-9]{17}$/i.test(value),
      "VIN musí mít 17 znaků bez písmen I, O a Q.",
    ),
  consumption_mode: z.enum([
    "SINGLE_TANK",
    "UNSUPPORTED_MULTI_TANK",
    "UNSUPPORTED_UNIT",
  ]),
  engine_displacement_cc: integer(1, 2147483647, true),
  power_kw: decimal(2, 1000000),
  tank_capacity_l: decimal(3, 100000),
  standard_consumption_l_100km: decimal(3, 10000),
  standard_methodology: z.enum([
    "UNKNOWN",
    "WLTP",
    "NEDC",
    "MANUFACTURER",
    "USER_ESTIMATE",
  ]),
  standard_source: z.string().max(500),
  standard_source_note: z.string().max(2000),
});
type Values = z.infer<typeof schema>;
export function VehicleForm({
  vehicle,
  onSave,
  onReload,
}: {
  vehicle?: Vehicle;
  onSave: (data: Record<string, unknown>) => Promise<void>;
  onReload?: () => void;
}) {
  const [error, setError] = useState("");
  const [lookup, setLookup] = useState<{
    id: string;
    vin: string;
    fields: string[];
  } | null>(null);
  const defaults = {
    name: "",
    make: "",
    model: "",
    fuel_type: "PETROL",
    initial_odometer_km: "",
    manufacture_year: "",
    registration_plate: "",
    vin: "",
    consumption_mode: "SINGLE_TANK",
    engine_displacement_cc: "",
    power_kw: "",
    tank_capacity_l: "",
    standard_consumption_l_100km: "",
    standard_methodology: "UNKNOWN",
    standard_source: "",
    standard_source_note: "",
  };
  if (vehicle)
    for (const key of Object.keys(defaults) as (keyof Values)[])
      defaults[key] = String(vehicle[key] ?? "");
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: defaults as Values,
  });
  const field = (
    key: keyof Values,
    label: string,
    numeric = false,
    hint?: string,
  ) => (
    <Field
      key={key}
      id={key}
      label={label}
      error={errors[key]?.message}
      hint={hint}
    >
      <Input
        id={key}
        inputMode={numeric ? "decimal" : undefined}
        aria-invalid={!!errors[key]}
        aria-describedby={errors[key] ? `${key}-error` : undefined}
        {...register(key)}
      />
    </Field>
  );
  return (
    <form
      noValidate
      onSubmit={handleSubmit(async (values) => {
        setError("");
        const data: Record<string, unknown> = {
          ...values,
          vin: values.vin.trim().toUpperCase() || null,
          initial_odometer_km: Number(values.initial_odometer_km),
        };
        for (const key of [
          "manufacture_year",
          "engine_displacement_cc",
        ] as const)
          data[key] = values[key] ? Number(values[key]) : null;
        for (const key of [
          "power_kw",
          "tank_capacity_l",
          "standard_consumption_l_100km",
        ] as const)
          data[key] = values[key] ? values[key].replace(",", ".") : null;
        try {
          if (lookup && data.vin === lookup.vin) {
            data.lookup_id = lookup.id;
            data.lookup_fields = lookup.fields;
          }
          await onSave(data);
        } catch (e) {
          setError(errorText(e));
        }
      })}
    >
      <div className="vehicle-form-grid">
        {field("name", "Název auta *")}
        {field("make", "Značka *")}
        {field("model", "Model *")}
        <Field id="fuel_type" label="Primární palivo *">
          <select className="input" id="fuel_type" {...register("fuel_type")}>
            {Object.entries(fuels).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </Field>
        {field(
          "initial_odometer_km",
          "Počáteční tachometr (km) *",
          true,
          "Výchozí stav evidence, nikoli plná nádrž.",
        )}
        {field("registration_plate", "Registrační značka")}
      </div>
      <details
        className="vehicle-optional"
        open={
          Object.keys(errors).some(
            (key) =>
              !["name", "make", "model", "initial_odometer_km"].includes(key),
          ) || undefined
        }
      >
        <summary>Technické údaje a norma (nepovinné)</summary>
        <div className="vehicle-form-grid">
          {field("manufacture_year", "Rok výroby", true)}
          {field(
            "vin",
            "VIN",
            false,
            "VIN můžete zadat ručně nebo dohledat. Historický nestandardní identifikátor uveďte do poznámky ke zdroji.",
          )}
          {field("engine_displacement_cc", "Objem motoru (cm³)", true)}
          {field("power_kw", "Výkon (kW)", true)}
          {field("tank_capacity_l", "Objem nádrže (l)", true)}
          <Field id="consumption_mode" label="Uspořádání nádrží">
            <select
              className="input"
              id="consumption_mode"
              {...register("consumption_mode")}
            >
              <option value="SINGLE_TANK">Jedna nádrž</option>
              <option value="UNSUPPORTED_UNIT">Jiné jednotky (kg/kWh)</option>
              <option value="UNSUPPORTED_MULTI_TANK">
                Více nádrží / souběžná paliva
              </option>
            </select>
          </Field>
          {field(
            "standard_consumption_l_100km",
            "Normovaná spotřeba (l/100 km)",
            true,
            "Ponechte prázdné, pokud normu neznáte. Nula není platná norma.",
          )}
          <Field id="standard_methodology" label="Metodika normy">
            <select
              className="input"
              id="standard_methodology"
              {...register("standard_methodology")}
            >
              {Object.entries(methodologies).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </Field>
          {field(
            "standard_source",
            "Zdroj normy",
            false,
            "Název nebo URL; aplikace zdroj automaticky nenačítá.",
          )}
          {field("standard_source_note", "Poznámka ke zdroji")}
        </div>
      </details>
      <VinLookup
        vin={watch("vin")}
        vehicleId={vehicle?.id}
        onApply={(values, id, vin) => {
          for (const [key, value] of Object.entries(values)) {
            if (key in defaults)
              setValue(key as keyof Values, String(value) as never, {
                shouldValidate: true,
              });
          }
          setLookup({ id, vin, fields: Object.keys(values) });
        }}
      />
      {["CNG", "ELECTRIC"].includes(watch("fuel_type")) && (
        <p className="alert">
          Nákupy v kg/kWh zadávejte do událostí auta. Norma l/100 km a plná–plná
          se pro tento pohon nepoužívají.
        </p>
      )}
      {watch("consumption_mode") === "UNSUPPORTED_MULTI_TANK" && (
        <p className="alert">
          U více nádrží bude možné evidovat výdaje; výpočet spotřeby nebude
          dostupný.
        </p>
      )}
      <ErrorMessage>{error}</ErrorMessage>
      <div className="vehicle-actions">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting
            ? "Ukládání…"
            : vehicle
              ? "Uložit změny"
              : "Vytvořit auto"}
        </Button>
        {error && onReload && (
          <Button type="button" variant="secondary" onClick={onReload}>
            Načíst aktuální údaje
          </Button>
        )}
      </div>
    </form>
  );
}

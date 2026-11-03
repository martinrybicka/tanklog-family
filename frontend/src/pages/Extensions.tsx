/* oxlint-disable jsx-a11y/no-noninteractive-tabindex -- Posuvný náhled tabulky musí být dostupný klávesnicí. */
import { decimalText, dateText } from "../features/analytics/format";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Button, ErrorMessage, Loading } from "../components/ui";
import { api, errorText, ApiError } from "../lib/api";
import { useSession } from "../lib/auth";
import type { Vehicle, Page } from "../lib/types";
type EventItem = {
  id: string;
  author_id: string;
  etag: string;
  version: number;
  kind: string;
  title: string;
  date: string;
  note: string;
  amount: string;
  odometer_km: number | null;
  due_date: string | null;
  due_odometer_km: number | null;
  notice_days: number;
  notice_km: number;
  closed: boolean;
  quantity: string | null;
  unit: string;
};
type Reminder = {
  id: string;
  vehicle_id: string;
  vehicle_name: string;
  title: string;
  due_date: string | null;
  due_odometer_km: number | null;
  reading_km: number | null;
  state: string;
};
const kinds: Record<string, string> = {
  SERVICE: "Servis",
  INSPECTION: "STK",
  INSURANCE: "Pojištění",
  REMINDER: "Připomínka",
  ENERGY: "Nákup energie",
};
const state: Record<string, string> = {
  OVERDUE: "Po termínu",
  SOON: "Blíží se",
  UNKNOWN: "Chybí odečet km",
  LATER: "Později",
};
const today = () =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Prague",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
function fresh() {
  return {
    kind: "SERVICE",
    title: "",
    date: today(),
    note: "",
    amount: "0.00",
    odometer_km: "",
    due_date: "",
    due_odometer_km: "",
    notice_days: "30",
    notice_km: "1000",
    closed: false,
    quantity: "",
    unit: "",
  };
}
export function Reminders() {
  const [page, setPage] = useState(1);
  const query = useQuery({
    queryKey: ["reminders", page],
    queryFn: () => api<Page<Reminder>>(`reminders/?page=${page}`),
    refetchInterval: 30000,
  });
  return (
    <>
      <h1>Připomínky</h1>
      <p>
        Termíny a známé km z dostupných aut. Upozornění zůstávají uvnitř
        aplikace; neposíláme e-mail ani push.
      </p>
      {query.isPending ? (
        <Loading />
      ) : query.error ? (
        <ErrorMessage>{errorText(query.error)}</ErrorMessage>
      ) : (
        <>
          <p>Celkem {query.data.data.count}</p>
          {query.data.data.results.map((item) => (
            <section className="panel" key={item.id}>
              <h2>{item.title}</h2>
              <p>
                {item.vehicle_name} · {state[item.state]}
              </p>
              <p>
                Datum: {item.due_date || "neuvedeno"} · Termín km:{" "}
                {item.due_odometer_km ?? "neuveden"} · Poslední známý odečet:{" "}
                {item.reading_km ?? "chybí"}
              </p>
              <Link to={`/auta/${item.vehicle_id}/udalosti`}>
                Otevřít události auta
              </Link>
            </section>
          ))}
          <Pagination
            page={page}
            setPage={setPage}
            previous={!!query.data.data.previous}
            next={!!query.data.data.next}
          />
        </>
      )}
    </>
  );
}
function Pagination({
  page,
  setPage,
  previous,
  next,
}: {
  page: number;
  setPage: (page: number) => void;
  previous: boolean;
  next: boolean;
}) {
  return (
    <div className="vehicle-actions">
      <Button
        variant="secondary"
        disabled={!previous}
        onClick={() => setPage(page - 1)}
      >
        Předchozí
      </Button>
      <span>Strana {page}</span>
      <Button
        variant="secondary"
        disabled={!next}
        onClick={() => setPage(page + 1)}
      >
        Další
      </Button>
    </div>
  );
}
export function Events() {
  const { id } = useParams();
  const session = useSession();
  const client = useQueryClient();
  const [page, setPage] = useState(1);
  const car = useQuery({
    queryKey: ["vehicle", id],
    queryFn: () => api<Vehicle>(`vehicles/${id}/`),
  });
  const events = useQuery({
    queryKey: ["events", id, page],
    queryFn: () => api<Page<EventItem>>(`vehicles/${id}/events/?page=${page}`),
  });
  const totals = useQuery({
    queryKey: ["energy", id],
    queryFn: () =>
      api<Record<string, { quantity: string; amount: string }>>(
        `vehicles/${id}/energy-totals/`,
      ),
  });
  const [form, setForm] = useState(fresh);
  const [editing, setEditing] = useState<EventItem | null>(null);
  const [key, setKey] = useState(() => crypto.randomUUID());
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function refresh() {
    await client.invalidateQueries({ queryKey: ["events"] });
    await client.invalidateQueries({ queryKey: ["reminders"] });
    await client.invalidateQueries({ queryKey: ["energy"] });
  }
  if (car.isPending || events.isPending) return <Loading />;
  if (car.error || events.error)
    return <ErrorMessage>{errorText(car.error || events.error)}</ErrorMessage>;
  const vehicle = car.data.data;
  const manage = vehicle.permissions.edit;
  const create =
    vehicle.status === "ACTIVE" &&
    (manage || vehicle.effective_role === "CONTRIBUTOR");
  const field = (
    name: Exclude<keyof typeof form, "closed">,
    label: string,
    type = "text",
  ) => (
    <label className="field" key={name}>
      {label}
      <input
        className="input"
        type={type}
        value={form[name]}
        onChange={(e) => setForm({ ...form, [name]: e.target.value })}
      />
    </label>
  );
  return (
    <>
      <Link to={`/auta/${id}`}>Zpět na auto</Link>
      <h1>Události · {vehicle.name}</h1>
      <ErrorMessage>{error}</ErrorMessage>
      <p>
        Servis, STK, pojištění, termíny a energie. Záznamy nemění litrovou
        spotřebu. <Link to={`/auta/${id}/import`}>Import historie</Link>
      </p>
      <section className="panel">
        <h2>Výdaje a množství energie</h2>
        {totals.error ? (
          <ErrorMessage>{errorText(totals.error)}</ErrorMessage>
        ) : (
          Object.entries(totals.data?.data || {}).map(([unit, total]) => (
            <p key={unit}>
              {decimalText(total.quantity, 3)} {unit} ·{" "}
              {decimalText(total.amount)} Kč
            </p>
          ))
        )}
        {!totals.isPending && !Object.keys(totals.data?.data || {}).length && (
          <p>Zatím žádné nákupy energie.</p>
        )}
      </section>
      {(create || editing) && (
        <section className="panel">
          <h2>{editing ? "Upravit událost" : "Nová událost"}</h2>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError("");
              const body = {
                ...form,
                amount: form.amount.replace(",", "."),
                quantity:
                  form.kind === "ENERGY"
                    ? form.quantity.replace(",", ".") || null
                    : null,
                unit: form.kind === "ENERGY" ? form.unit : "",
                odometer_km: form.odometer_km || null,
                due_date: form.due_date || null,
                due_odometer_km: form.due_odometer_km || null,
                notice_days: form.notice_days,
                notice_km: form.notice_km,
              };
              try {
                await api(
                  `vehicles/${id}/events/${editing ? editing.id + "/" : ""}`,
                  {
                    method: editing ? "PUT" : "POST",
                    body,
                    etag: editing?.etag,
                    headers: editing ? undefined : { "Idempotency-Key": key },
                  },
                );
                setEditing(null);
                setForm(fresh());
                setKey(crypto.randomUUID());
                await refresh();
              } catch (error) {
                setError(errorText(error));
              } finally {
                setBusy(false);
              }
            }}
          >
            <div className="vehicle-form-grid">
              <label className="field">
                Druh
                <select
                  className="input"
                  value={form.kind}
                  onChange={(e) => setForm({ ...form, kind: e.target.value })}
                >
                  {Object.entries(kinds).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              {field("title", "Název *")}
              {field("date", "Datum *", "date")}
              {field("amount", "Částka (Kč)")}
              {field("odometer_km", "Tachometr (km)")}
              {field("due_date", "Další termín / platnost do", "date")}
              {field("due_odometer_km", "Další termín km")}
              {field("notice_days", "Předstih (dny)")}
              {field("notice_km", "Předstih (km)")}
              {form.kind === "ENERGY" && (
                <>
                  {field("quantity", "Množství *")}
                  <label className="field">
                    Jednotka *
                    <select
                      className="input"
                      value={form.unit}
                      onChange={(e) =>
                        setForm({ ...form, unit: e.target.value })
                      }
                    >
                      <option value="">Vyberte</option>
                      <option value="kg">kg (CNG)</option>
                      <option value="kWh">kWh (elektřina)</option>
                    </select>
                  </label>
                </>
              )}
              {field("note", "Poznámka / dodavatel / číslo smlouvy")}
            </div>
            <label>
              <input
                type="checkbox"
                checked={form.closed}
                onChange={(e) => setForm({ ...form, closed: e.target.checked })}
              />
              Uzavřeno – nepřipomínat
            </label>
            <ErrorMessage>{error}</ErrorMessage>
            <Button disabled={busy}>
              {busy ? "Ukládání…" : "Uložit událost"}
            </Button>
            {editing && (
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setEditing(null);
                  setForm(fresh());
                  setKey(crypto.randomUUID());
                }}
              >
                Zrušit úpravy
              </Button>
            )}
          </form>
        </section>
      )}
      {events.data.data.results.map((item) => (
        <section className="panel" key={item.id}>
          <h2>
            {kinds[item.kind]} · {item.title}
          </h2>
          <p>
            {dateText(item.date)} · {decimalText(item.amount)} Kč{" "}
            {item.quantity &&
              ` · ${decimalText(item.quantity, 3)} ${item.unit}`}{" "}
            {item.closed && " · uzavřeno"}
          </p>
          <p>{item.note}</p>
          <p>
            Další termín: {item.due_date || "–"} / {item.due_odometer_km ?? "–"}{" "}
            km
          </p>
          {(manage || (create && item.author_id === session.data?.id)) && (
            <Button
              variant="secondary"
              onClick={() => {
                const values = fresh();
                for (const name of Object.keys(
                  values,
                ) as (keyof typeof values)[]) {
                  if (name === "closed") values.closed = item.closed;
                  else values[name] = String(item[name] ?? "");
                }
                setForm(values);
                setEditing(item);
                setError("");
              }}
            >
              Upravit
            </Button>
          )}
          {manage && (
            <Button
              variant="secondary"
              disabled={busy}
              onClick={async () => {
                if (!window.confirm(`Smazat událost „${item.title}“?`)) return;
                setBusy(true);
                try {
                  await api(`vehicles/${id}/events/${item.id}/`, {
                    method: "DELETE",
                    etag: item.etag,
                  });
                  await refresh();
                } catch (error) {
                  setError(errorText(error));
                } finally {
                  setBusy(false);
                }
              }}
            >
              Smazat
            </Button>
          )}
        </section>
      ))}
      <Pagination
        page={page}
        setPage={setPage}
        previous={!!events.data.data.previous}
        next={!!events.data.data.next}
      />
    </>
  );
}
type Batch = {
  csv_text: string;
  id: string;
  kind: string;
  rows: Record<string, unknown>[];
  errors: {
    row: number;
    fields?: Record<string, string[]>;
    message?: string;
  }[];
  warnings: { row: number; code: string; message: string }[];
  completed: boolean;
  results: string[];
};
export function ImportHistory() {
  const { id } = useParams();
  const [historyPage, setHistoryPage] = useState(1);
  const history = useQuery({
    queryKey: ["import-history", id, historyPage],
    queryFn: () =>
      api<
        Page<{
          id: string;
          created_at: string;
          kind: string;
          completed: boolean;
        }>
      >(`vehicles/${id}/imports/?page=${historyPage}`),
  });
  const client = useQueryClient();
  const [kind, setKind] = useState("FUEL");
  const [text, setText] = useState("");
  const [batch, setBatch] = useState<Batch | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [accepted, setAccepted] = useState(false);
  return (
    <>
      <Link to={`/auta/${id}/udalosti`}>Zpět na události</Link>
      <h1>Import historie</h1>
      <details>
        <summary>Uložené návrhy a předchozí importy</summary>
        {history.error && (
          <ErrorMessage>{errorText(history.error)}</ErrorMessage>
        )}
        {history.data?.data.results.map((item) => (
          <p key={item.id}>
            <Button
              variant="secondary"
              onClick={async () => {
                setError("");
                try {
                  const value = (await api<Batch>(`imports/${item.id}/`)).data;
                  setBatch(value);
                  setKind(value.kind);
                  setText(value.csv_text);
                  setAccepted(false);
                } catch (e) {
                  setError(errorText(e));
                }
              }}
            >
              {item.created_at.slice(0, 10)} ·{" "}
              {item.kind === "FUEL" ? "Tankování" : "Události"} ·{" "}
              {item.completed ? "Uloženo" : "Návrh"}
            </Button>
          </p>
        ))}
        {history.data && (
          <Pagination
            page={historyPage}
            setPage={setHistoryPage}
            previous={!!history.data.data.previous}
            next={!!history.data.data.next}
          />
        )}
      </details>
      <p>
        CSV UTF-8; nejvýše 128 KiB a 200 řádků. Náhled nic nezapíše do historie.
        Potvrzení uloží celou dávku nebo nic.
      </p>
      <section className="panel">
        <label className="field">
          Druh importu
          <select
            className="input"
            value={kind}
            onChange={(e) => {
              setKind(e.target.value);
              setBatch(null);
            }}
          >
            <option value="FUEL">Tankování v litrech</option>
            <option value="EVENT">Události / energie</option>
          </select>
        </label>
        <details>
          <summary>Šablona a podporované sloupce</summary>
          <pre className="ocr-text">
            {kind === "FUEL"
              ? "date;liters;total_amount;odometer_km;is_full_tank;fuel_type;note\n2026-01-02;10.500;420.00;10000;false;PETROL;Syntetický příklad"
              : "kind;title;date;amount;due_date;quantity;unit;note\nENERGY;Nabíjení;2026-01-02;120.00;;20.000;kWh;Syntetický příklad"}
          </pre>
          <p>
            Datum ISO RRRR-MM-DD, desetinná čárka nebo tečka, boolean
            true/false. Další sloupce:{" "}
            {kind === "FUEL"
              ? "unit_price_entered, day_sequence, break_before, station_code, station_custom_name, paid_by_label"
              : "odometer_km, due_odometer_km, notice_days, notice_km, closed"}
            . Nepovolené sloupce se odmítají.
          </p>
        </details>
        <label className="field">
          Soubor CSV
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              if (file.size > 128 * 1024) {
                setError("Soubor přesahuje 128 KiB.");
                return;
              }
              try {
                setText(
                  new TextDecoder("utf-8", { fatal: true }).decode(
                    await file.arrayBuffer(),
                  ),
                );
                setBatch(null);
              } catch {
                setError("CSV není platné UTF-8. Převeďte kódování souboru.");
              }
            }}
          />
        </label>
        <label className="field">
          Obsah CSV
          <textarea
            aria-label="Obsah CSV"
            className="input ocr-text"
            rows={10}
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setBatch(null);
            }}
          />
        </label>
        <Button
          disabled={busy || !text}
          onClick={async () => {
            setBusy(true);
            setError("");
            setAccepted(false);
            try {
              setBatch(
                (
                  await api<Batch>(`vehicles/${id}/imports/`, {
                    method: "POST",
                    body: { kind, csv_text: text },
                  })
                ).data,
              );
            } catch (e) {
              setError(errorText(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          Připravit náhled
        </Button>
        <ErrorMessage>{error}</ErrorMessage>
      </section>
      {batch && (
        <section className="panel">
          <h2>Náhled · {batch.rows.length} řádků</h2>
          <details open>
            <summary>Řádky a chyby ({batch.errors.length})</summary>
            <div
              className="table-wrap"
              role="region"
              aria-label="Náhled importu"
              tabIndex={0}
            >
              <table>
                <caption>Kontrola importovaných řádků</caption>
                <thead>
                  <tr>
                    {[
                      "Řádek",
                      "Datum",
                      "Druh / název",
                      "Množství",
                      "Částka Kč",
                      "Km",
                      "Poznámka",
                    ].map((label) => (
                      <th key={label} scope="col">
                        {label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {batch.rows.map((row, index) => (
                    <tr key={index}>
                      <th scope="row">{index + 1}</th>
                      <td>{String(row.date || "–")}</td>
                      <td>
                        {String(row.title || row.fuel_type || "Tankování")}
                      </td>
                      <td>
                        {String(row.liters || row.quantity || "–")}{" "}
                        {String(row.unit || "l")}
                      </td>
                      <td>{String(row.total_amount || row.amount || "–")}</td>
                      <td>{String(row.odometer_km ?? "–")}</td>
                      <td>{String(row.note || "")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {batch.errors.map((item, index) => (
              <p role="alert" key={index}>
                Řádek {item.row}:{" "}
                {item.message ||
                  Object.values(item.fields || {})
                    .flat()
                    .join(" ")}
              </p>
            ))}
          </details>
          {batch.warnings.map((warning, index) => (
            <p key={index}>
              {warning.row ? `Řádek ${warning.row}` : "Dávka"}:{" "}
              {warning.message}
            </p>
          ))}
          {batch.completed ? (
            <p role="status">
              Import uložen: {batch.results.length} záznamů. Opakované potvrzení
              neduplikuje data.
            </p>
          ) : (
            <>
              <label>
                <input
                  type="checkbox"
                  checked={accepted}
                  onChange={(e) => setAccepted(e.target.checked)}
                />
                Zkontroloval/a jsem řádky a potvrzuji uvedená upozornění.
              </label>
              <Button
                disabled={busy || !accepted || !!batch.errors.length}
                onClick={async () => {
                  setBusy(true);
                  setError("");
                  try {
                    setBatch(
                      (
                        await api<Batch>(`imports/${batch.id}/`, {
                          method: "POST",
                          body: {
                            confirmed: true,
                            confirmed_warning_codes: [
                              ...new Set(batch.warnings.map((w) => w.code)),
                            ],
                          },
                        })
                      ).data,
                    );
                    await client.invalidateQueries({ queryKey: ["events"] });
                    await client.invalidateQueries({ queryKey: ["energy"] });
                    await client.invalidateQueries({ queryKey: ["reminders"] });
                    await client.invalidateQueries({
                      queryKey: ["refuelings"],
                    });
                    await client.invalidateQueries({ queryKey: ["analytics"] });
                    await client.invalidateQueries({
                      queryKey: ["import-history"],
                    });
                  } catch (e) {
                    setError(errorText(e));
                    if (e instanceof ApiError && e.warnings.length) {
                      const warnings = e.warnings.map((w) => ({
                        ...w,
                        row: w.row ?? 0,
                      }));
                      setBatch({
                        ...batch,
                        warnings: [...batch.warnings, ...warnings].filter(
                          (warning, index, all) =>
                            all.findIndex(
                              (item) =>
                                item.code === warning.code &&
                                item.row === warning.row,
                            ) === index,
                        ),
                      });
                      setAccepted(false);
                    }
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Potvrdit import do databáze
              </Button>
            </>
          )}
        </section>
      )}
    </>
  );
}

import { useQuery } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { Button, ErrorMessage, Loading } from "../components/ui";
import { api, errorText } from "../lib/api";
import { useSession } from "../lib/auth";
import type { Page } from "../lib/types";
import { fuels, methodologies } from "../features/vehicles/VehicleForm";
import { PeriodPicker } from "../features/analytics/PeriodPicker";
import {
  ConsumptionChart,
  IntervalTable,
  PurchaseChart,
} from "../features/analytics/Charts";
import {
  dateText,
  decimalText,
  reasonText,
} from "../features/analytics/format";
import { analyticsParams, periodParams } from "../features/analytics/period";
import type {
  Interval,
  IntervalDetail,
  Statistics,
} from "../features/analytics/types";

function Metric({
  label,
  value,
  unit,
  note,
}: {
  label: string;
  value: string | null;
  unit?: string;
  note: string;
}) {
  return (
    <article className="panel metric">
      <span>{label}</span>
      <strong>
        {decimalText(value)}
        {value !== null && unit && <small> {unit}</small>}
      </strong>
      <p className="muted">{note}</p>
    </article>
  );
}
export function Dashboard() {
  const { id } = useParams();
  const { data: user } = useSession();
  const [params, setParams] = useSearchParams();
  const filters = analyticsParams(params);
  if (id) filters.set("vehicle_id", id);
  const query = useQuery({
    queryKey: ["analytics", "dashboard", filters.toString()],
    queryFn: () => api<Statistics>(`dashboard/?${filters}`),
    refetchInterval: 30000,
  });
  const data = query.data?.data;
  const selected = id || params.get("vehicle_id") || "";
  const names = new Map(
    data?.coverage.vehicles.map((v) => [v.vehicle_id, v.name]),
  );
  const chartGroups = new Map<string, Interval[]>();
  for (const item of data?.charts.consumption || []) {
    const key = `${item.vehicle_id}:${item.fuel_type}`;
    chartGroups.set(key, [...(chartGroups.get(key) || []), item]);
  }
  return (
    <div className="analytics-page">
      {id && <Link to={`/auta/${id}`}>← Zpět na auto</Link>}
      <div className="page-heading">
        <div>
          <span className="eyebrow">PŘEHLED NÁKUPŮ A MĚŘENÍ</span>
          <h1>
            {id
              ? `Statistiky · ${names.get(id) || "vozidlo"}`
              : `Dobrý den${user?.display_name ? `, ${user.display_name}` : ""}.`}
          </h1>
          <p className="muted">
            Každý nákup v součtech. Spotřeba pouze z doložených intervalů.
          </p>
        </div>
        <Link className="button button-secondary" to="/tankovani">
          Historie tankování
        </Link>
      </div>
      {query.isPending ? (
        <Loading />
      ) : query.error ? (
        <section className="panel">
          <ErrorMessage>{errorText(query.error)}</ErrorMessage>
          <Button onClick={() => query.refetch()}>Zkusit znovu</Button>
          <Button variant="secondary" onClick={() => setParams({})}>
            Obnovit výchozí měsíc
          </Button>
        </section>
      ) : (
        data && (
          <>
            {!id && (
              <label className="analytics-vehicle">
                Vozidlo
                <select
                  className="input"
                  value={selected}
                  onChange={(e) => {
                    const next = new URLSearchParams(filters);
                    if (e.target.value) next.set("vehicle_id", e.target.value);
                    else next.delete("vehicle_id");
                    setParams(next);
                  }}
                >
                  <option value="">
                    Všechna přístupná auta včetně archivovaných
                  </option>
                  {data.available_vehicles.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name}
                      {v.status === "ARCHIVED" ? " (archivované)" : ""}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <PeriodPicker
              key={JSON.stringify(data.period)}
              period={data.period}
              vehicleId={selected}
              onChange={setParams}
            />
            {selected && !id && (
              <p>
                <Link to="/">Zrušit výběr auta a vrátit výchozí měsíc</Link>
              </p>
            )}
            <div className="metric-grid">
              <Metric
                label="Výdaje v období"
                value={data.purchases.amount}
                unit="Kč"
                note={`${data.purchases.count} nákupů podle data tankování`}
              />
              <Metric
                label="Nakoupené palivo"
                value={data.purchases.liters}
                unit="l"
                note="Včetně částečných a neuzavřených tankování"
              />
              <Metric
                label="Realizovaná cena"
                value={data.purchases.realized_unit_price}
                unit="Kč/l"
                note="Součet částek / součet litrů"
              />
            </div>
            <section className="panel measurement">
              <div className="section-title">
                <h2>Naměřená spotřeba</h2>
                <span className="date-chip">PLNÁ → PLNÁ</span>
              </div>
              <p>{data.explanation}</p>
              {!data.consumption_by_fuel.length && (
                <p>Nedostatek dat pro spotřebu v tomto období.</p>
              )}
              <div className="metric-grid">
                {data.consumption_by_fuel.map((g) => (
                  <div key={g.fuel_type}>
                    <h3>{fuels[g.fuel_type] || g.fuel_type}</h3>
                    <p className="measurement-value">
                      {decimalText(g.consumption_l_100km)}
                      {g.consumption_l_100km !== null && (
                        <small> l/100 km</small>
                      )}
                    </p>
                    <p>
                      Nákupní náklad: {decimalText(g.purchase_cost_czk_100km)}
                      {g.purchase_cost_czk_100km !== null ? " Kč/100 km" : ""}
                    </p>
                    <p className="muted">
                      {g.valid_intervals} platných intervalů ·{" "}
                      {g.distance_km.toLocaleString("cs-CZ")} km
                    </p>
                  </div>
                ))}
              </div>
              <p className="muted">
                Váženě ze součtu litrů a kilometrů. Různá paliva neslučujeme.
                Nákupní Kč/100 km vycházejí z částek v intervalech, nejde o
                přesné ocenění spálené zásoby.
              </p>
            </section>
            {data.comparison && (
              <section className="panel">
                <h2>Srovnání s normou</h2>
                <p>
                  Norma {decimalText(data.comparison.standard)} l/100 km ·{" "}
                  {methodologies[data.comparison.methodology] ||
                    data.comparison.methodology}
                </p>
                <p>
                  Rozdíl {decimalText(data.comparison.difference_l_100km)} l/100
                  km ({decimalText(data.comparison.difference_percent)} %)
                </p>
                <p>Zdroj: {data.comparison.source || "Neuveden"}</p>
                {data.comparison.source_note && (
                  <p>{data.comparison.source_note}</p>
                )}
              </section>
            )}
            <section className="panel">
              <h2>Pokrytí měření</h2>
              <p>
                {data.coverage.valid_intervals} platných ·{" "}
                {data.coverage.excluded_intervals} vyřazených intervalů ·{" "}
                {data.coverage.distance_km.toLocaleString("cs-CZ")} km
              </p>
              <p>
                Platné hranice: {dateText(data.coverage.start_date)} →{" "}
                {dateText(data.coverage.end_date)}
              </p>
              {data.coverage.vehicles.length === 0 && (
                <p>
                  Zatím nemáte přístupné auto.{" "}
                  <Link to="/auta/nove">Přidat první auto</Link>
                </p>
              )}
              {data.coverage.vehicles.map((v) => (
                <details className="coverage-row" key={v.vehicle_id}>
                  <summary>
                    {v.name} ·{" "}
                    {v.status === "VALID"
                      ? "Platné měření"
                      : v.status === "UNSUPPORTED"
                        ? "Nepodporované měření"
                        : v.status === "INVALID_DATA"
                          ? "Neplatné podklady"
                          : "Nedostatek dat"}{" "}
                    · {v.valid_intervals} platných / {v.excluded_intervals}{" "}
                    vyřazených
                  </summary>
                  <ul>
                    {v.reasons.map((r) => (
                      <li key={r}>{reasonText(r)}</li>
                    ))}
                  </ul>
                  {v.missing_odometer_ids.length > 0 && (
                    <p>
                      {reasonText("MISSING_ODOMETER")} Záznamů v historii:{" "}
                      {v.missing_odometer_ids.length}.
                    </p>
                  )}
                  <div className="vehicle-actions">
                    <Link
                      to={`/auta/${v.vehicle_id}/intervaly?${periodParams(data.period)}`}
                    >
                      Prohlédnout intervaly a podklady
                    </Link>
                    <Link to={`/tankovani?vehicle_id=${v.vehicle_id}`}>
                      Opravit historii
                    </Link>
                  </div>
                </details>
              ))}
            </section>
            <div className="analytics-charts">
              <PurchaseChart points={data.charts.purchases} />
              <PurchaseChart points={data.charts.purchases} price />
            </div>
            {Array.from(chartGroups, ([key, items]) => (
              <ConsumptionChart
                key={key}
                intervals={items}
                title={`${names.get(items[0].vehicle_id)} · ${fuels[items[0].fuel_type] || items[0].fuel_type}`}
                params={periodParams(data.period)}
              />
            ))}
            <section className="panel">
              <h2>Poslední tankování ve vybraném období</h2>
              {!data.recent_refuelings.length && (
                <p>Žádné nákupy v tomto období.</p>
              )}
              <div className="recent-refuelings">
                {data.recent_refuelings.map((r) => (
                  <Link key={r.id} to={`/tankovani/${r.id}`}>
                    <span>
                      {r.vehicle_name}
                      <small>
                        {dateText(r.date)} · pořadí {r.day_sequence}
                      </small>
                    </span>
                    <span>
                      {decimalText(r.liters, 3)} l ·{" "}
                      {decimalText(r.total_amount)} Kč
                    </span>
                  </Link>
                ))}
              </div>
            </section>
          </>
        )
      )}
    </div>
  );
}

export function Intervals() {
  const { id } = useParams();
  const [params, setParams] = useSearchParams();
  const filters = analyticsParams(params);
  filters.delete("vehicle_id");
  const page = Math.max(1, Number(params.get("page")) || 1);
  const query = useQuery({
    queryKey: ["analytics", "intervals", id, filters.toString(), page],
    queryFn: () =>
      api<Page<Interval>>(
        `vehicles/${id}/consumption-intervals/?${filters}&page=${page}`,
      ),
    refetchInterval: 30000,
  });
  return (
    <>
      <Link to={`/auta/${id}/statistiky?${filters}`}>
        ← Zpět na statistiky auta
      </Link>
      <div className="page-heading">
        <h1>Intervaly spotřeby</h1>
      </div>
      <section className="panel">
        <p>
          Každý interval je přiřazen dnem koncové plné nádrže. Kliknutím na
          hranice zobrazíte všechny podklady včetně počáteční kotvy.
        </p>
        {query.isPending ? (
          <Loading />
        ) : query.error ? (
          <ErrorMessage>{errorText(query.error)}</ErrorMessage>
        ) : (
          <>
            <IntervalTable
              intervals={query.data.data.results}
              params={filters}
            />
            <div className="vehicle-actions">
              <Button
                variant="secondary"
                disabled={!query.data.data.previous}
                onClick={() => {
                  const next = new URLSearchParams(params);
                  next.set("page", String(page - 1));
                  setParams(next);
                }}
              >
                Předchozí
              </Button>
              <span>
                Strana {page} · celkem {query.data.data.count}
              </span>
              <Button
                variant="secondary"
                disabled={!query.data.data.next}
                onClick={() => {
                  const next = new URLSearchParams(params);
                  next.set("page", String(page + 1));
                  setParams(next);
                }}
              >
                Další
              </Button>
            </div>
          </>
        )}
      </section>
    </>
  );
}
export function IntervalEvidence({ interval }: { interval: IntervalDetail }) {
  return (
    <section className="panel">
      <h2>
        {dateText(interval.start_date)} → {dateText(interval.end_date)}
      </h2>
      <p>{interval.explanation}</p>
      {interval.crosses_period_start && (
        <p className="alert">
          Počáteční kotva je před obdobím a je zde uvedena kvůli ověřitelnosti
          výpočtu.
        </p>
      )}
      <p>
        Spotřeba:{" "}
        <strong>
          {decimalText(interval.consumption_l_100km)}
          {interval.consumption_l_100km !== null ? " l/100 km" : ""}
        </strong>
      </p>
      <p>
        {decimalText(interval.liters, 3)} l po kotvě / {interval.distance_km} km
        × 100. Částka po kotvě: {decimalText(interval.amount)} Kč.
      </p>
      <p>
        Nákupní náklad: {decimalText(interval.purchase_cost_czk_100km)}
        {interval.purchase_cost_czk_100km !== null ? " Kč/100 km" : ""}
      </p>
      {[...interval.reasons, ...interval.warnings].map((r) => (
        <p className="alert" key={r}>
          {reasonText(r)}
        </p>
      ))}
      <div className="table-wrap">
        <table>
          <caption>
            Podklady výpočtu: počáteční nákup se do intervalu nesčítá
          </caption>
          <thead>
            <tr>
              <th>Tankování</th>
              <th>Tachometr</th>
              <th>Litry</th>
              <th>Kč</th>
              <th>Palivo / plná</th>
              <th>Použití</th>
            </tr>
          </thead>
          <tbody>
            {interval.records.map((r) => (
              <tr key={r.id}>
                <td>
                  <Link to={`/tankovani/${r.id}`}>
                    {dateText(r.date)} · {r.day_sequence}
                  </Link>
                </td>
                <td>
                  {r.odometer_km === null ? "Neuveden" : `${r.odometer_km} km`}
                </td>
                <td>{decimalText(r.liters, 3)}</td>
                <td>{decimalText(r.total_amount)}</td>
                <td>
                  {fuels[r.fuel_type] || r.fuel_type} ·{" "}
                  {r.is_full_tank ? "Plná" : "Částečná"}
                  {r.break_before && <small>Mezera před záznamem</small>}
                </td>
                <td>
                  {r.used_for_totals
                    ? "Započtený nákup"
                    : "Pouze počáteční kotva"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted">
        Podklady se přepočítávají z aktuální historie. Změnou plných hranic může
        interval zaniknout.
      </p>
    </section>
  );
}
export function IntervalDetails() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const filters = analyticsParams(params);
  filters.delete("vehicle_id");
  const detail = new URLSearchParams(filters);
  detail.set("start_id", params.get("start_id") || "");
  detail.set("end_id", params.get("end_id") || "");
  const query = useQuery({
    queryKey: ["analytics", "detail", id, detail.toString()],
    queryFn: () =>
      api<IntervalDetail>(
        `vehicles/${id}/consumption-intervals/detail/?${detail}`,
      ),
    refetchInterval: 30000,
  });
  return (
    <>
      <Link to={`/auta/${id}/intervaly?${filters}`}>← Zpět na intervaly</Link>
      <div className="page-heading">
        <h1>Podklady intervalu</h1>
      </div>
      {query.isPending ? (
        <Loading />
      ) : query.error ? (
        <>
          <ErrorMessage>{errorText(query.error)}</ErrorMessage>
          <Button onClick={() => query.refetch()}>
            Načíst aktuální podklady
          </Button>
        </>
      ) : (
        <IntervalEvidence interval={query.data.data} />
      )}
    </>
  );
}

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Link } from "react-router-dom";
import { dateText, decimalText, reasonText } from "./format";
import type { Interval, PurchasePoint } from "./types";
export function intervalLink(interval: Interval, params: URLSearchParams) {
  const next = new URLSearchParams(params);
  next.delete("vehicle_id");
  next.set("start_id", interval.start_id);
  next.set("end_id", interval.end_id);
  return `/auta/${interval.vehicle_id}/intervaly/detail?${next}`;
}
export function PurchaseChart({
  points,
  price = false,
}: {
  points: PurchasePoint[];
  price?: boolean;
}) {
  const title = price ? "Realizovaná cena paliva" : "Výdaje za palivo";
  const unit = price ? "Kč/l" : "Kč";
  // Number slouží pouze souřadnicím grafu; účetní hodnoty a tabulky zůstávají řetězci z API.
  const data = points.map((p) => ({
    date: p.date,
    value: price
      ? p.unit_price === null
        ? null
        : Number(p.unit_price)
      : Number(p.amount),
  }));
  return (
    <section className="panel chart-panel">
      <h2>{title}</h2>
      <p className="muted">
        {price
          ? "Součet skutečných částek / součet litrů. Bez nákupů zůstává mezera."
          : "Skutečné částky nákupů v období."}{" "}
        Jednotka: {unit}.
      </p>
      <div
        className="analytics-chart"
        role="img"
        aria-label={`${title}, ${unit}. Data jsou dostupná také v tabulce pod grafem.`}
      >
        <ResponsiveContainer width="100%" height="100%" minWidth={0}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tickFormatter={dateText} minTickGap={35} />
            <YAxis width={62} unit={` ${unit}`} />
            <Tooltip
              labelFormatter={(v) => dateText(String(v))}
              formatter={(v) => [
                typeof v === "number"
                  ? decimalText(String(v)) + ` ${unit}`
                  : "Nedostatek dat",
                title,
              ]}
            />
            <Line
              type="linear"
              dataKey="value"
              name={title}
              stroke="#3979ba"
              strokeWidth={2}
              dot={price ? { r: 3 } : false}
              connectNulls={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <details>
        <summary>Zobrazit data v tabulce: {title.toLowerCase()}</summary>
        <div className="table-wrap">
          <table>
            <caption>
              {title} ({unit})
            </caption>
            <thead>
              <tr>
                <th>Začátek skupiny</th>
                <th>{unit}</th>
                <th>Litry</th>
                <th>Nákupy</th>
              </tr>
            </thead>
            <tbody>
              {points.map((p) => (
                <tr key={p.date}>
                  <td>{dateText(p.date)}</td>
                  <td>{decimalText(price ? p.unit_price : p.amount)}</td>
                  <td>{decimalText(p.liters, 3)}</td>
                  <td>{p.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}
export function ConsumptionChart({
  intervals,
  title,
  params,
}: {
  intervals: Interval[];
  title: string;
  params: URLSearchParams;
}) {
  const data = intervals.map((i) => ({
    date: i.end_date,
    value:
      i.consumption_l_100km === null ? null : Number(i.consumption_l_100km),
  }));
  return (
    <section className="panel chart-panel">
      <h2>Spotřeba · {title}</h2>
      <p className="muted">
        l/100 km podle koncového tankování. Neplatné intervaly přerušují čáru.
      </p>
      <div
        className="analytics-chart"
        role="img"
        aria-label={`Spotřeba ${title}, l/100 km. Tabulkové podklady jsou pod grafem.`}
      >
        <ResponsiveContainer width="100%" height="100%" minWidth={0}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tickFormatter={dateText} minTickGap={35} />
            <YAxis
              width={64}
              label={{ value: "l/100 km", angle: -90, position: "insideLeft" }}
            />
            <Tooltip
              labelFormatter={(v) => dateText(String(v))}
              formatter={(v) => [
                typeof v === "number"
                  ? decimalText(String(v)) + " l/100 km"
                  : "Nedostatek dat",
                "Spotřeba",
              ]}
            />
            <Line
              type="linear"
              dataKey="value"
              stroke="#3979ba"
              strokeWidth={2}
              dot={{ r: 4 }}
              connectNulls={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <details>
        <summary>Zobrazit podklady spotřeby: {title}</summary>
        <IntervalTable intervals={intervals} params={params} />
      </details>
    </section>
  );
}
export function IntervalTable({
  intervals,
  params,
}: {
  intervals: Interval[];
  params: URLSearchParams;
}) {
  if (!intervals.length)
    return <p>V období nekončí žádný uzavřený interval.</p>;
  return (
    <div className="table-wrap">
      <table>
        <caption>Intervaly plná–plná · spotřeba v l/100 km</caption>
        <thead>
          <tr>
            <th>Hranice a podklady</th>
            <th>Litry po kotvě</th>
            <th>km</th>
            <th>l/100 km</th>
            <th>Stav</th>
          </tr>
        </thead>
        <tbody>
          {intervals.map((i) => (
            <tr key={`${i.start_id}-${i.end_id}`}>
              <td>
                <Link to={intervalLink(i, params)}>
                  {dateText(i.start_date)} → {dateText(i.end_date)}
                </Link>
                {i.crosses_period_start && (
                  <small className="muted">Kotva je před obdobím</small>
                )}
              </td>
              <td>{decimalText(i.liters, 3)}</td>
              <td>{i.distance_km}</td>
              <td>{decimalText(i.consumption_l_100km)}</td>
              <td>
                {i.status === "VALID" ? "Platný" : "Vyřazený"}
                {[...i.reasons, ...i.warnings].map((r) => (
                  <small key={r}>{reasonText(r)}</small>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

import type { Period } from "./types";
const dayMs = 86400000;
const timestamp = (value: string) => Date.parse(`${value}T12:00:00Z`);
const iso = (value: number) => new Date(value).toISOString().slice(0, 10);
export function periodParams(period: Period, vehicleId = "") {
  const params = new URLSearchParams({
    period: period.period,
    group_by: period.group_by,
  });
  if (period.period === "custom") {
    params.set("date_from", period.date_from);
    params.set("date_to", period.date_to);
  } else if (period.anchor_date) params.set("anchor_date", period.anchor_date);
  if (vehicleId) params.set("vehicle_id", vehicleId);
  return params;
}
export function shiftPeriod(period: Period, direction: number, vehicleId = "") {
  const next = { ...period };
  const anchor = timestamp(period.date_from);
  if (period.period === "custom") {
    const length = Math.round((timestamp(period.date_to) - anchor) / dayMs) + 1;
    next.date_from = iso(anchor + direction * length * dayMs);
    next.date_to = iso(timestamp(period.date_to) + direction * length * dayMs);
  } else if (period.period === "month" || period.period === "year") {
    const date = new Date(anchor);
    if (period.period === "month")
      date.setUTCMonth(date.getUTCMonth() + direction);
    else date.setUTCFullYear(date.getUTCFullYear() + direction);
    next.anchor_date = iso(date.getTime());
  } else
    next.anchor_date = iso(
      anchor + direction * (period.period === "week" ? 7 : 1) * dayMs,
    );
  return periodParams(next, vehicleId);
}
export function analyticsParams(params: URLSearchParams) {
  const result = new URLSearchParams();
  for (const key of [
    "period",
    "anchor_date",
    "date_from",
    "date_to",
    "group_by",
    "vehicle_id",
  ]) {
    const value = params.get(key);
    if (value) result.set(key, value);
  }
  return result;
}

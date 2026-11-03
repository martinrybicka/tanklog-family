// Desetinné řetězce z API zaokrouhlujeme HALF_UP bez převodu na binární float.
export function decimalText(value: string | null, places = 2): string {
  if (value === null) return "Nedostatek dat";
  const negative = value.startsWith("-");
  const [whole, fraction = ""] = value.replace(/^[+-]/, "").split(".");
  const padded = fraction.padEnd(places + 1, "0");
  let scaled = BigInt(whole + padded.slice(0, places));
  if (padded[places] >= "5") scaled += 1n;
  const digits = scaled.toString().padStart(places + 1, "0");
  const integer = places ? digits.slice(0, -places) : digits;
  return `${negative && scaled !== 0n ? "−" : ""}${integer.replace(/\B(?=(\d{3})+(?!\d))/g, " ")}${places ? "," + digits.slice(-places) : ""}`;
}
export const dateText = (value: string | null) =>
  value
    ? new Date(`${value}T12:00:00Z`).toLocaleDateString("cs-CZ", {
        timeZone: "UTC",
      })
    : "—";
export const reasons: Record<string, string> = {
  ZERO_DISTANCE: "Nulová nebo záporná vzdálenost mezi plnými nádržemi.",
  ODOMETER_DECREASE:
    "Tachometr klesá. Opravte odečty nebo pořadí; následující měření je do opravy vyřazené.",
  BELOW_INITIAL_ODOMETER: "Odečet je nižší než počáteční tachometr vozidla.",
  HISTORY_GAP: "V intervalu je označená mezera v evidenci.",
  MIXED_FUEL: "V intervalu se mísí různá paliva.",
  UNSUPPORTED_UNIT:
    "Pro kg/kWh se litrová spotřeba nepočítá. Výdaje jsou v událostech vozidla.",
  UNSUPPORTED_MULTI_TANK:
    "Více nádrží nebo souběžná paliva: spotřebu nelze spolehlivě určit.",
  INVALID_ORDER: "Pořadí tankování není jednoznačné.",
  MISSING_ANCHOR:
    "Chybí dvě použitelné plné hranice pro uzavřené měření v období.",
  NO_CLOSED_INTERVAL: "V období nekončí žádný uzavřený interval.",
  OPEN_INTERVAL:
    "Po poslední plné nádrži zbývá neuzavřený úsek. Jeho nákupy se započítávají.",
  MISSING_ODOMETER:
    "Některé tankování nemá tachometr. Jeho litry se v ohraničeném intervalu započítávají.",
};
export const reasonText = (code: string) => reasons[code] || code;

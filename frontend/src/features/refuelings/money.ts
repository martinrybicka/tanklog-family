// Návrh částky počítáme v celých jednotkách BigInt, autoritativní výpočet provede server.
export function suggestedTotal(liters: string, price: string) {
  const scaled = (value: string, places: number) => {
    const normalized = value.replace(",", ".");
    if (!new RegExp(`^\\d+(\\.\\d{1,${places}})?$`).test(normalized))
      return null;
    const [whole, fraction = ""] = normalized.split(".");
    return BigInt(whole + fraction.padEnd(places, "0"));
  };
  const l = scaled(liters, 3),
    p = scaled(price, 4);
  if (l === null || p === null) return "";
  const cents = (l * p + 50000n) / 100000n;
  return `${cents / 100n}.${(cents % 100n).toString().padStart(2, "0")}`;
}
export const stations: Record<string, string> = {
  "": "Neuvedena",
  ORLEN: "ORLEN",
  SHELL: "Shell",
  MOL: "MOL",
  OMV: "OMV",
  EUROOIL: "EuroOil",
  TANK_ONO: "Tank ONO",
  OTHER: "Ostatní",
};
export const numberText = (value: string | number | null, digits = 2) =>
  value === null
    ? "Neuvedeno"
    : Number(value).toLocaleString("cs-CZ", { maximumFractionDigits: digits });
export function saveBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

import { api } from "../lib/api";
import type { Page, Vehicle } from "../lib/types";
export async function familyCars() {
  const cars: Vehicle[] = [];
  let path: string | null = "vehicles/?status=active";
  while (path) {
    const response: { data: Page<Vehicle> } = await api<Page<Vehicle>>(path);
    cars.push(...response.data.results);
    path = response.data.next?.replace(/^.*\/api\/v1\//, "") ?? null;
  }
  return cars;
}
export type Draft = {
  id: string;
  vehicle_id: string;
  suggestions: Record<string, { value: string; confidence: string }>;
  preview_url: string;
  result_id: string | null;
  created_at: string;
};
export const today = () =>
  new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Prague" }).format(
    new Date(),
  );

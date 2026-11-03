import { useSyncExternalStore } from "react";
export type PendingFuel = {
  key: string;
  userId: string;
  body: Record<string, unknown>;
  error: string;
  warnings: { code: string; message: string }[];
};
let entries: PendingFuel[] = [];
const listeners = new Set<() => void>();
function notify() {
  listeners.forEach((listener) => listener());
}
export function queueFuel(
  userId: string,
  body: Record<string, unknown>,
  key: string,
) {
  if (entries.some((item) => item.key === key)) return;
  if (entries.length >= 20)
    throw new Error("Dočasná fronta je plná (20 záznamů).");
  entries = [
    ...entries,
    { key, userId, body: structuredClone(body), error: "", warnings: [] },
  ];
  notify();
}
export function updatePending(key: string, values: Partial<PendingFuel>) {
  entries = entries.map((item) =>
    item.key === key ? { ...item, ...values } : item,
  );
  notify();
}
export function discardPending(key: string) {
  entries = entries.filter((item) => item.key !== key);
  notify();
}
export function clearOutbox() {
  entries = [];
  notify();
}
export function pendingSnapshot() {
  return entries;
}
export function useOutbox() {
  return useSyncExternalStore((listener) => {
    listeners.add(listener);
    return () => listeners.delete(listener);
  }, pendingSnapshot);
}

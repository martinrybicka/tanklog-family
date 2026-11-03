import { beforeEach, expect, it, vi } from "vitest";
import {
  clearOutbox,
  queueFuel,
  pendingSnapshot,
  updatePending,
  discardPending,
} from "./outbox";
beforeEach(clearOutbox);
it("udrží kopii původního klíče, nic nezapisuje do trvalého úložiště a logout vyprázdní frontu", () => {
  const local = vi.spyOn(Storage.prototype, "setItem");
  const body = { liters: "12.345", total_amount: "400.10" };
  queueFuel("user", body, "same-key");
  body.liters = "99";
  queueFuel("user", body, "same-key");
  expect(pendingSnapshot()).toHaveLength(1);
  expect(pendingSnapshot()[0].body.liters).toBe("12.345");
  expect(local).not.toHaveBeenCalled();
  clearOutbox();
  expect(pendingSnapshot()).toHaveLength(0);
  local.mockRestore();
});
it("umožní opravu a zahození bez změny idempotency key a omezuje frontu", () => {
  queueFuel("user", { note: "Původní" }, "key");
  updatePending("key", { body: { note: "Opraveno" } });
  expect(pendingSnapshot()[0].key).toBe("key");
  discardPending("key");
  for (let n = 0; n < 20; n++) queueFuel("user", { liters: "1" }, String(n));
  expect(() => queueFuel("user", {}, "overflow")).toThrow();
});

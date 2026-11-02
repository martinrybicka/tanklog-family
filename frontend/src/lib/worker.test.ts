import { readFileSync } from "node:fs";
import { createContext, runInContext } from "node:vm";
import { describe, expect, it, vi } from "vitest";
const source = readFileSync("scripts/worker.js", "utf8");
function worker() {
  const handlers: Record<string, (event: unknown) => void> = {};
  const cache = { put: vi.fn(), match: vi.fn(async () => ({ offline: true })) };
  const caches = {
    open: vi.fn(async () => cache),
    keys: vi.fn(async () => [
      "tanklog-public-old",
      "tanklog-public-test",
      "other-app",
    ]),
    delete: vi.fn(),
  };
  const fetch = vi.fn(async (_input: unknown, _options?: RequestInit) => ({
    ok: true,
    redirected: false,
  }));
  const self = {
    location: { origin: "https://tanklog.test" },
    addEventListener: (name: string, callback: (event: unknown) => void) => {
      handlers[name] = callback;
    },
    clients: { claim: vi.fn() },
    skipWaiting: vi.fn(),
  };
  runInContext(
    source
      .replace("__VERSION__", "test")
      .replace(
        "__PUBLIC_FILES__",
        JSON.stringify(["/assets/app-hash.js", "/offline.html"]),
      ),
    createContext({ self, caches, fetch, URL, Set, Error }),
  );
  return { handlers, cache, caches, fetch, self };
}
describe("hranice veřejné service worker cache", () => {
  it("API, exporty, účtenky, mutace a cizí origin nikdy neobsluhuje z cache", () => {
    const { handlers, caches } = worker();
    for (const [path, method] of [
      ["/api/v1/vehicles/", "GET"],
      ["/api/v1/refuelings/export/", "GET"],
      ["/api/v1/refuelings/id/receipt/", "GET"],
      ["/api/v1/auth/logout/", "POST"],
      ["/media/private.png", "GET"],
      ["/private_media/private.png", "GET"],
      ["https://other.test/assets/app-hash.js", "GET"],
      ["/assets/app-hash.js?private=1", "GET"],
    ]) {
      const respondWith = vi.fn();
      handlers.fetch({
        request: { url: new URL(path, "https://tanklog.test").href, method },
        respondWith,
      });
      expect(respondWith).not.toHaveBeenCalled();
    }
    expect(caches.open).not.toHaveBeenCalled();
  });
  it("instalace stáhne jen pevný veřejný seznam bez cookies", async () => {
    const { handlers, fetch, cache } = worker();
    let promise: Promise<unknown>;
    handlers.install({
      waitUntil: (value: Promise<unknown>) => {
        promise = value;
      },
    });
    await promise!;
    expect(fetch.mock.calls.map((args) => args[0])).toEqual([
      "/assets/app-hash.js",
      "/offline.html",
    ]);
    expect(fetch).toHaveBeenCalledWith("/offline.html", {
      credentials: "omit",
      cache: "reload",
    });
    expect(cache.put).toHaveBeenCalledTimes(2);
  });
  it("při offline navigaci vrátí jen obecnou offline stránku a nic neukládá", async () => {
    const { handlers, fetch, cache } = worker();
    fetch.mockRejectedValue(new Error("offline"));
    let promise: Promise<unknown>;
    handlers.fetch({
      request: {
        url: "https://tanklog.test/auta/private-id",
        method: "GET",
        mode: "navigate",
      },
      respondWith: (value: Promise<unknown>) => {
        promise = value;
      },
    });
    await expect(promise!).resolves.toEqual({ offline: true });
    expect(cache.match).toHaveBeenCalledWith("/offline.html");
    expect(cache.put).not.toHaveBeenCalled();
  });
  it("aktivace uklidí jen starý veřejný shell a update nevnucuje bez pokynu", async () => {
    const { handlers, caches, self } = worker();
    let promise: Promise<unknown>;
    handlers.activate({
      waitUntil: (value: Promise<unknown>) => {
        promise = value;
      },
    });
    await promise!;
    expect(caches.delete).toHaveBeenCalledExactlyOnceWith("tanklog-public-old");
    expect(self.skipWaiting).not.toHaveBeenCalled();
    handlers.message({ data: "unknown" });
    expect(self.skipWaiting).not.toHaveBeenCalled();
    handlers.message({ data: "ACTIVATE_UPDATE" });
    expect(self.skipWaiting).toHaveBeenCalledOnce();
  });
});

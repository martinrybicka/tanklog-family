import { expect, it, vi } from "vitest";
import { api, ApiError, refreshCsrf } from "./api";

it("před mutací předá CSRF token a podmíněnou verzi, nikoliv auth token do úložiště", async () => {
  const fetch = vi.spyOn(globalThis, "fetch");
  fetch.mockResolvedValueOnce(
    new Response(JSON.stringify({ csrf_token: "masked-test-token" }), {
      status: 200,
    }),
  );
  await refreshCsrf();
  fetch.mockResolvedValueOnce(
    new Response(JSON.stringify({ id: "user" }), {
      headers: { ETag: '"user:1:2"' },
    }),
  );
  await api("profile/", {
    method: "PATCH",
    body: { display_name: "Řidič" },
    etag: '"user:1:1"',
  });
  expect(fetch).toHaveBeenLastCalledWith(
    "/api/v1/profile/",
    expect.objectContaining({
      credentials: "same-origin",
      cache: "no-store",
      headers: expect.objectContaining({
        "X-CSRFToken": "masked-test-token",
        "If-Match": '"user:1:1"',
      }),
    }),
  );
  expect(localStorage.length).toBe(0);
});

it("propaguje strojový kód odmítnuté session", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        error: { code: "authentication_required", message: "Přihlaste se." },
      }),
      { status: 403 },
    ),
  );
  const listener = vi.fn();
  window.addEventListener("tanklog:session", listener);
  await expect(api("profile/")).rejects.toBeInstanceOf(ApiError);
  expect(listener).toHaveBeenCalledOnce();
  window.removeEventListener("tanklog:session", listener);
});

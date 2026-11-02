let csrfToken: string | null = null;
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public fields: Record<string, string[]> = {},
    public warnings: { code: string; message: string }[] = [],
  ) {
    super(message);
  }
}

export async function refreshCsrf() {
  const response = await fetch("/api/v1/auth/csrf/", {
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!response.ok)
    throw new ApiError(
      response.status,
      "csrf_failed",
      "Nepodařilo se připravit zabezpečený formulář.",
    );
  csrfToken = (await response.json()).csrf_token;
}

export async function api<T>(
  path: string,
  options: {
    method?: string;
    body?: unknown;
    etag?: string;
    headers?: Record<string, string>;
    binary?: boolean;
  } = {},
) {
  const method = options.method || "GET";
  if (method !== "GET" && !csrfToken) await refreshCsrf();
  const headers: Record<string, string> = {
    Accept: options.binary ? "*/*" : "application/json",
    ...options.headers,
  };
  if (options.body !== undefined && !(options.body instanceof FormData))
    headers["Content-Type"] = "application/json";
  if (method !== "GET") headers["X-CSRFToken"] = csrfToken!;
  if (options.etag) headers["If-Match"] = options.etag;
  let response: Response;
  try {
    response = await fetch(`/api/v1/${path}`, {
      method,
      headers,
      credentials: "same-origin",
      cache: "no-store",
      body:
        options.body instanceof FormData
          ? options.body
          : options.body !== undefined
            ? JSON.stringify(options.body)
            : undefined,
    });
  } catch {
    throw new ApiError(
      0,
      "network_error",
      "Spojení se serverem se nezdařilo. Zkontrolujte připojení a zkuste to znovu.",
    );
  }
  const body =
    response.status === 204
      ? null
      : options.binary && response.ok
        ? await response.blob()
        : await response.json().catch(() => null);
  if (!response.ok) {
    if (body?.error?.code === "csrf_failed") csrfToken = null;
    if (
      path !== "auth/me/" &&
      ["authentication_required", "password_change_required"].includes(
        body?.error?.code,
      )
    ) {
      window.dispatchEvent(
        new CustomEvent("tanklog:session", { detail: body.error.code }),
      );
    }
    throw new ApiError(
      response.status,
      body?.error?.code || "server_error",
      body?.error?.message || "Požadavek se nepodařilo dokončit.",
      body?.error?.fields,
      body?.error?.warnings,
    );
  }
  return { data: body as T, etag: response.headers.get("ETag") };
}

export function errorText(error: unknown) {
  if (error instanceof ApiError && Object.keys(error.fields).length) {
    return Object.values(error.fields).flat().join(" ");
  }
  return error instanceof Error ? error.message : "Nastala neočekávaná chyba.";
}
export const userETag = (user: { id: string; version: number }) =>
  `"user:${user.id}:${user.version}"`;

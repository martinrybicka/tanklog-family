import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import * as apiModule from "../lib/api";
import { IntegrationSettings } from "./IntegrationSettings";

it("uloží klíč, vyprázdní citlivé pole a otestuje až uložené nastavení", async () => {
  const api = vi
    .spyOn(apiModule, "api")
    .mockImplementation(async (_path) => {
      if (_path.endsWith("test/"))
        return { data: { message: "Spojení funguje." }, etag: null };
      return {
        data: { configured: true, source: "database" },
        etag: '"rsv-setting:1"',
      };
    });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <IntegrationSettings />
    </QueryClientProvider>,
  );
  const user = userEvent.setup();
  const probe = await screen.findByRole("button", {
    name: "Otestovat spojení",
  });
  await waitFor(() => expect(probe).toBeEnabled());
  const key = screen.getByLabelText("Nový API klíč RSV");
  await user.type(key, "synthetic-test-key");
  expect(probe).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "Uložit API klíč" }));
  await waitFor(() => expect(key).toHaveValue(""));
  expect(api).toHaveBeenCalledWith("admin/integrations/rsv/", {
    method: "PUT",
    body: { api_key: "synthetic-test-key" },
    etag: '"rsv-setting:1"',
  });
  await user.click(probe);
  expect(await screen.findByText("Spojení funguje.")).toBeVisible();
});

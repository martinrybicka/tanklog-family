import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import * as apiModule from "../lib/api";
import { PasswordForm } from "./Password";

it("odmítne krátké nebo neshodné nové heslo bez požadavku na server", async () => {
  const spy = vi.spyOn(apiModule, "api");
  const client = new QueryClient();
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <PasswordForm restricted />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  const user = userEvent.setup();
  await user.type(
    screen.getByLabelText("Nové heslo", { exact: true }),
    "short",
  );
  await user.type(screen.getByLabelText("Nové heslo znovu"), "other");
  await user.click(screen.getByRole("button", { name: "Nastavit nové heslo" }));
  expect(
    await screen.findByText("Nové heslo musí mít alespoň 12 znaků."),
  ).toBeVisible();
  expect(screen.getByText("Hesla se neshodují.")).toBeVisible();
  expect(screen.queryByLabelText("Aktuální heslo")).not.toBeInTheDocument();
  expect(spy).not.toHaveBeenCalled();
});

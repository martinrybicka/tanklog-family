import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { PwaInstallButton, PwaNotice } from "./Pwa";

it("nabídne návod, pokud prohlížeč neposkytuje instalační výzvu", async () => {
  vi.spyOn(navigator, "userAgent", "get").mockReturnValue("iPhone Safari");
  render(<PwaInstallButton />);
  const user = userEvent.setup();
  await user.click(
    screen.getByRole("button", { name: "Nainstalovat aplikaci" }),
  );
  expect(screen.getByRole("dialog")).toHaveTextContent("Přidat na plochu");
  await user.click(screen.getByRole("button", { name: "Rozumím" }));
  await waitFor(() =>
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
  );
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Nainstalovat aplikaci" }),
    ).toHaveFocus(),
  );
});

it("použije nativní výzvu jednou a po instalaci skryje všechny nabídky", async () => {
  render(
    <>
      <PwaNotice />
      <PwaInstallButton />
      <PwaInstallButton />
    </>,
  );
  const prompt = vi.fn().mockResolvedValue(undefined);
  const event = Object.assign(
    new Event("beforeinstallprompt", { cancelable: true }),
    {
      prompt,
      userChoice: Promise.resolve({ outcome: "accepted" }),
    },
  );
  window.dispatchEvent(event);
  const user = userEvent.setup();
  await user.click(
    screen.getAllByRole("button", { name: "Nainstalovat aplikaci" })[0],
  );
  expect(event.defaultPrevented).toBe(true);
  expect(prompt).toHaveBeenCalledOnce();
  await waitFor(() =>
    expect(
      screen.queryByRole("button", { name: "Nainstalovat aplikaci" }),
    ).not.toBeInTheDocument(),
  );
});

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import * as apiModule from "../../lib/api";
import { Illustration, PhotoPicker } from "./VehicleIntegrations";

it("odešle vlastní fotografii s verzí auta a obnoví kartu", async () => {
  const api = vi
    .spyOn(apiModule, "api")
    .mockResolvedValue({ data: {}, etag: null });
  const refresh = vi.fn().mockResolvedValue(undefined);
  render(
    <PhotoPicker vehicleId="car-id" etag='"vehicle:1"' onChange={refresh} />,
  );
  const file = new File(["synthetic-image"], "car.jpg", { type: "image/jpeg" });
  const user = userEvent.setup();
  await user.upload(
    screen.getByLabelText("Vybrat vlastní fotografii auta"),
    file,
  );
  await user.click(screen.getByRole("button", { name: "Nahrát fotografii" }));
  await waitFor(() => expect(refresh).toHaveBeenCalledOnce());
  expect(api).toHaveBeenCalledWith(
    "vehicles/car-id/photo-upload/",
    expect.objectContaining({ method: "POST", etag: '"vehicle:1"' }),
  );
  const payload = api.mock.calls[0][1]!.body as FormData;
  expect(payload.get("file")).toBe(file);
  expect(
    await screen.findByText("Vlastní fotografie byla uložena."),
  ).toBeVisible();
});

it("vlastní snímek nevydává za fotografii z veřejného zdroje", () => {
  render(
    <Illustration
      photo={{
        id: "photo",
        url: "/api/v1/vehicle-images/photo/",
        metadata: {
          kind: "upload",
          author: "Vlastní fotografie",
          license: "Soukromá fotografie",
          license_url: "",
          source: "",
          title: "Auto",
          modified: "Náhled",
        },
      }}
    />,
  );
  expect(screen.getByAltText("Vlastní fotografie auta")).toBeVisible();
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
});

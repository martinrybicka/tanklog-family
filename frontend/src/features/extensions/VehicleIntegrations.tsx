import { useState } from "react";
import { Button, ErrorMessage } from "../../components/ui";
import { api, errorText } from "../../lib/api";
import { Suggestions } from "./Suggestions";
export type Photo = {
  id: string;
  url: string;
  metadata: {
    author: string;
    credit?: string;
    attribution?: string;
    license: string;
    license_url: string;
    source: string;
    title: string;
    modified: string;
  };
};
type Lookup = {
  expired: boolean;
  id: string;
  vin: string;
  suggestions: Record<string, string | number>;
  notes: { consumption: string; power: string; methodology: string };
};
export function VinLookup({
  vin,
  vehicleId,
  onApply,
}: {
  vin: string;
  vehicleId?: string;
  onApply: (
    values: Record<string, string | number>,
    id: string,
    vin: string,
  ) => void;
}) {
  const [result, setResult] = useState<Lookup | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <section className="extension-block">
      <h2>Dohledat technické údaje podle VIN</h2>
      <p>
        VIN odešlete pouze do oficiálního RSV. Návrhy se uloží až po vašem
        výběru a uložení auta. První registrace není rok výroby.
      </p>
      <Button
        type="button"
        variant="secondary"
        disabled={busy || !vin}
        onClick={async () => {
          setBusy(true);
          setError("");
          setResult(null);
          try {
            setResult(
              (
                await api<Lookup>("vehicle-lookups/", {
                  method: "POST",
                  body: {
                    vin,
                    ...(vehicleId ? { vehicle_id: vehicleId } : {}),
                  },
                })
              ).data,
            );
          } catch (e) {
            setError(errorText(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? "Dohledávání…" : "Dohledat VIN"}
      </Button>
      <Button
        type="button"
        variant="secondary"
        onClick={async () => {
          setError("");
          try {
            const response = await api<{ results: Lookup[] }>(
              `vehicle-lookups/${vehicleId ? `?vehicle_id=${vehicleId}` : ""}`,
            );
            const match = response.data.results.find(
              (item) => item.vin === vin.trim().toUpperCase(),
            );
            if (match) {
              setResult(match);
              if (match.expired)
                setError("Uložený návrh vypršel. Dohledejte VIN znovu.");
            } else setError("Pro tento VIN není uložený návrh.");
          } catch (e) {
            setError(errorText(e));
          }
        }}
      >
        Načíst uložený návrh VIN
      </Button>
      <ErrorMessage>{error}</ErrorMessage>
      {result && (
        <>
          <Suggestions
            values={Object.fromEntries(
              Object.entries(result.expired ? {} : result.suggestions).map(
                ([key, value]) => [key, { value }],
              ),
            )}
            onApply={(values) => onApply(values, result.id, result.vin)}
          />
          <p className="muted">
            Původní údaj výkonu: {result.notes.power || "neuveden"}; spotřeba:{" "}
            {result.notes.consumption || "neuvedena"} (
            {result.notes.methodology || "neznámá metodika"}). Nejednoznačné
            hodnoty doplňte ručně.
          </p>
        </>
      )}
    </section>
  );
}
export function Illustration({
  photo,
  caption = true,
}: {
  photo: Photo;
  caption?: boolean;
}) {
  return (
    <figure className="vehicle-photo">
      <img
        src={photo.url}
        alt="Ilustrační fotografie modelu vozidla"
        loading="lazy"
      />
      {caption && (
        <figcaption>
          Ilustrační fotografie · {photo.metadata.author} ·{" "}
          <a href={photo.metadata.license_url} target="_blank" rel="noreferrer">
            {photo.metadata.license}
          </a>{" "}
          ·{" "}
          <a href={photo.metadata.source} target="_blank" rel="noreferrer">
            Zdroj
          </a>
          {photo.metadata.credit && <small>{photo.metadata.credit}</small>}
          {photo.metadata.attribution && (
            <small>{photo.metadata.attribution}</small>
          )}
          <small>{photo.metadata.modified}</small>
        </figcaption>
      )}
    </figure>
  );
}
export function PhotoPicker({
  vehicleId,
  etag,
  onChange,
}: {
  vehicleId: string;
  etag: string;
  onChange: () => Promise<unknown>;
}) {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [error, setError] = useState("");
  const [searched, setSearched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  return (
    <section className="panel">
      <h2>Ilustrační fotografie</h2>
      <p>
        Po potvrzeném dohledání VIN lze nabídnout model z Wikimedia Commons.
        Ověřte model, generaci i karoserii; fotografie nemusí odpovídat
        barvě/výbavě vašeho auta.
      </p>
      <Button
        variant="secondary"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          setError("");
          try {
            setPhotos(
              (
                await api<{ results: Photo[] }>(
                  `vehicles/${vehicleId}/photo-search/`,
                  { method: "POST", body: {} },
                )
              ).data.results,
            );
            setSearched(true);
          } catch (e) {
            setError(errorText(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        Hledat fotografie modelu
      </Button>
      <ErrorMessage>{error}</ErrorMessage>
      {searched && !photos.length && (
        <p>
          Zdroj nemá spolehlivě použitelný návrh s úplnou licencí. Zůstává
          obecná ikona.
        </p>
      )}
      {photos.length > 0 && (
        <>
          <label>
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
            />
            Zkontroloval/a jsem shodu modelu/generace/karoserie a licenční údaje
            vybrané fotografie.
          </label>
          <div className="vehicle-grid">
            {photos.map((photo) => (
              <div key={photo.id}>
                <Illustration photo={photo} />
                <Button
                  disabled={!confirmed || busy}
                  onClick={async () => {
                    setBusy(true);
                    setError("");
                    try {
                      await api(`vehicles/${vehicleId}/photo/`, {
                        method: "POST",
                        body: { image_id: photo.id, confirmed: true },
                        etag,
                      });
                      setPhotos([]);
                      await onChange();
                    } catch (e) {
                      setError(errorText(e));
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  Vybrat fotografii
                </Button>
              </div>
            ))}
          </div>
        </>
      )}
      <Button
        variant="secondary"
        disabled={busy}
        onClick={async () => {
          setError("");
          try {
            await api(`vehicles/${vehicleId}/photo/`, {
              method: "DELETE",
              etag,
            });
            setPhotos([]);
            await onChange();
          } catch (e) {
            setError(errorText(e));
          }
        }}
      >
        Odebrat fotografii a návrhy
      </Button>
    </section>
  );
}

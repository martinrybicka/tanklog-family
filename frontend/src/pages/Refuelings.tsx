import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { Button, ErrorMessage, Loading, Modal } from "../components/ui";
import { api, errorText } from "../lib/api";
import type { Page, Refueling, Vehicle } from "../lib/types";
import { fuels } from "../features/vehicles/VehicleForm";
import { RefuelingForm } from "../features/refuelings/RefuelingForm";
import { numberText, saveBlob, stations } from "../features/refuelings/money";

async function allVehicles() {
  const results: Vehicle[] = [];
  for (let page = 1; ; page++) {
    const response = await api<Page<Vehicle>>(
      `vehicles/?status=all&page=${page}`,
    );
    results.push(...response.data.results);
    if (!response.data.next) return results;
  }
}
export function Refuelings() {
  const [params, setParams] = useSearchParams();
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState(false);
  const vehicles = useQuery({
    queryKey: ["vehicles", "options"],
    queryFn: allVehicles,
  });
  const query = useQuery({
    queryKey: ["refuelings", params.toString()],
    queryFn: () => api<Page<Refueling>>(`refuelings/?${params}`),
  });
  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    next.delete("page");
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">VAŠE HISTORIE</span>
          <h1>Tankování</h1>
          <p className="muted">
            Přesné částky, účtenky a přehled společných cest.
          </p>
        </div>
        <div className="vehicle-actions">
          <Link
            className="button button-primary"
            to={`/tankovani/nove${params.get("vehicle_id") ? `?vehicle_id=${params.get("vehicle_id")}` : ""}`}
          >
            Zadat tankování
          </Link>
          <Button
            variant="secondary"
            disabled={exporting}
            onClick={async () => {
              setError("");
              setExporting(true);
              try {
                const filters = new URLSearchParams(params);
                filters.delete("page");
                saveBlob(
                  (
                    await api<Blob>(`refuelings/export/?${filters}`, {
                      binary: true,
                    })
                  ).data,
                  "tankovani.xlsx",
                );
              } catch (e) {
                setError(errorText(e));
              } finally {
                setExporting(false);
              }
            }}
          >
            Exportovat vyfiltrovaná data
          </Button>
        </div>
      </div>
      <section className="panel history-filters" aria-label="Filtry historie">
        <label>
          Auto
          <select
            className="input"
            value={params.get("vehicle_id") || ""}
            onChange={(e) => set("vehicle_id", e.target.value)}
          >
            <option value="">Všechna přístupná auta</option>
            {vehicles.data?.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
                {v.status === "ARCHIVED" ? " · Archivované" : ""}
              </option>
            ))}
          </select>
        </label>
        <label>
          Od
          <input
            className="input"
            type="date"
            value={params.get("date_from") || ""}
            onChange={(e) => set("date_from", e.target.value)}
          />
        </label>
        <label>
          Do
          <input
            className="input"
            type="date"
            value={params.get("date_to") || ""}
            onChange={(e) => set("date_to", e.target.value)}
          />
        </label>
        <label>
          Palivo
          <select
            className="input"
            value={params.get("fuel_type") || ""}
            onChange={(e) => set("fuel_type", e.target.value)}
          >
            <option value="">Všechna paliva</option>
            {Object.entries(fuels).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </label>
        <label>
          Stanice
          <select
            className="input"
            value={params.get("station_code") || ""}
            onChange={(e) => set("station_code", e.target.value)}
          >
            <option value="">Všechny stanice</option>
            {Object.entries(stations)
              .filter(([v]) => v)
              .map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
          </select>
        </label>
        <label>
          Hledat v autě, stanici a poznámce
          <input
            className="input"
            type="search"
            maxLength={200}
            value={params.get("search") || ""}
            onChange={(e) => set("search", e.target.value)}
          />
        </label>
        <label>
          Řazení
          <select
            className="input"
            value={params.get("ordering") || "-date"}
            onChange={(e) => set("ordering", e.target.value)}
          >
            {[
              ["date", "Data"],
              ["total_amount", "Částky"],
              ["liters", "Litrů"],
              ["odometer_km", "Tachometru"],
            ].flatMap(([key, label]) => [
              <option key={"-" + key} value={"-" + key}>
                {label} sestupně
              </option>,
              <option key={key} value={key}>
                {label} vzestupně
              </option>,
            ])}
          </select>
        </label>
        <Button variant="ghost" onClick={() => setParams({})}>
          Vymazat filtry
        </Button>
      </section>
      <ErrorMessage>{error}</ErrorMessage>
      <ErrorMessage>{vehicles.error && errorText(vehicles.error)}</ErrorMessage>
      {query.isPending ? (
        <Loading />
      ) : query.error ? (
        <>
          <ErrorMessage>{errorText(query.error)}</ErrorMessage>
          <Button onClick={() => query.refetch()}>Zkusit znovu</Button>
        </>
      ) : (
        <>
          <p className="muted">Celkem {query.data.data.count} tankování</p>
          {query.data.data.count === 0 ? (
            <section className="panel">
              <h2>Žádné tankování v tomto výběru</h2>
              <p>Změňte filtry nebo zadejte první tankování.</p>
            </section>
          ) : (
            <div className="history-results">
              <div className="table-scroll desktop-history">
                <table>
                  <caption className="sr-only">
                    Vyfiltrovaná historie tankování
                  </caption>
                  <thead>
                    <tr>
                      <th>Datum a auto</th>
                      <th>Stanice / palivo</th>
                      <th>Litry</th>
                      <th>Celkem</th>
                      <th>Tachometr</th>
                      <th>Stav</th>
                    </tr>
                  </thead>
                  <tbody>
                    {query.data.data.results.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <Link to={`/tankovani/${item.id}?${params}`}>
                            {new Date(
                              item.date + "T12:00:00",
                            ).toLocaleDateString("cs-CZ")}{" "}
                            · {item.vehicle_name}
                          </Link>
                          <small className="muted">
                            {" "}
                            · pořadí {item.day_sequence}
                          </small>
                        </td>
                        <td>
                          {item.station_custom_name ||
                            stations[item.station_code]}
                          <br />
                          {fuels[item.fuel_type]}
                        </td>
                        <td>{numberText(item.liters, 3)} l</td>
                        <td>{numberText(item.total_amount)} Kč</td>
                        <td>
                          {item.odometer_km === null
                            ? "Chybí"
                            : numberText(item.odometer_km, 0) + " km"}
                        </td>
                        <td>
                          {[
                            item.is_full_tank ? "Plná nádrž" : "Částečná",
                            item.break_before ? "Mezera" : "",
                            item.receipt ? "Účtenka" : "",
                            item.quality_warnings.length
                              ? `Upozornění: ${item.quality_warnings.length}`
                              : "",
                          ]
                            .filter(Boolean)
                            .join(" · ")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="refueling-history mobile-history">
                {query.data.data.results.map((item) => (
                  <article className="panel refueling-row" key={item.id}>
                    <div>
                      <Link to={`/tankovani/${item.id}?${params}`}>
                        {new Date(item.date + "T12:00:00").toLocaleDateString(
                          "cs-CZ",
                        )}{" "}
                        · {item.vehicle_name}
                      </Link>
                      <p className="muted">
                        {item.station_custom_name ||
                          stations[item.station_code]}{" "}
                        · {fuels[item.fuel_type]} · pořadí {item.day_sequence}
                      </p>
                    </div>
                    <div>
                      <strong>{numberText(item.total_amount)} Kč</strong>
                      <p>
                        {numberText(item.liters, 3)} l ·{" "}
                        {numberText(item.odometer_km, 0)}
                        {item.odometer_km !== null ? " km" : " – tachometr"}
                      </p>
                    </div>
                    <div className="refueling-tags">
                      {item.is_full_tank && (
                        <span className="date-chip">Plná nádrž</span>
                      )}
                      {item.break_before && (
                        <span className="date-chip">Mezera v evidenci</span>
                      )}
                      {item.receipt && (
                        <span className="date-chip">Účtenka</span>
                      )}
                      {item.quality_warnings.length > 0 && (
                        <span className="date-chip">
                          Upozornění: {item.quality_warnings.length}
                        </span>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            </div>
          )}
          <div className="vehicle-actions">
            <Button
              variant="secondary"
              disabled={!query.data.data.previous}
              onClick={() => {
                const next = new URLSearchParams(params);
                next.set("page", String(Number(params.get("page") || 1) - 1));
                setParams(next);
              }}
            >
              Předchozí
            </Button>
            <span>Strana {params.get("page") || 1}</span>
            <Button
              variant="secondary"
              disabled={!query.data.data.next}
              onClick={() => {
                const next = new URLSearchParams(params);
                next.set("page", String(Number(params.get("page") || 1) + 1));
                setParams(next);
              }}
            >
              Další
            </Button>
          </div>
        </>
      )}
    </>
  );
}
export function RefuelingEditor() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const client = useQueryClient();
  const vehicles = useQuery({
    queryKey: ["vehicles", "options"],
    queryFn: allVehicles,
  });
  const query = useQuery({
    queryKey: ["refueling", id],
    queryFn: () => api<Refueling>(`refuelings/${id}/`),
    enabled: !!id,
  });
  if (vehicles.isPending || (id && query.isPending)) return <Loading />;
  if (vehicles.error || query.error)
    return (
      <ErrorMessage>{errorText(vehicles.error || query.error)}</ErrorMessage>
    );
  if (id && !query.data?.data.permissions.edit)
    return (
      <ErrorMessage>K úpravě tohoto tankování nemáte oprávnění.</ErrorMessage>
    );
  const available = vehicles.data.filter((v) =>
    id ? v.id === query.data?.data.vehicle_id : v.permissions.create_refueling,
  );
  return (
    <>
      <Link to={id ? `/tankovani/${id}?${params}` : `/tankovani?${params}`}>
        ← Zpět
      </Link>
      <div className="page-heading">
        <h1>{id ? "Upravit tankování" : "Nové tankování"}</h1>
      </div>
      <section className="panel">
        {!available.length ? (
          <p>
            Nemáte aktivní auto s právem zadat tankování.{" "}
            <Link to="/auta">Otevřít auta</Link>
          </p>
        ) : (
          <RefuelingForm
            key={query.data?.etag || "new"}
            item={query.data?.data}
            vehicles={available}
            initialVehicleId={params.get("vehicle_id") || undefined}
            onReload={() => query.refetch()}
            onSave={async (body, key) => {
              const response = await api<Refueling>(
                id ? `refuelings/${id}/` : "refuelings/",
                {
                  method: id ? "PATCH" : "POST",
                  body,
                  etag: query.data?.etag || undefined,
                  headers: id ? undefined : { "Idempotency-Key": key },
                },
              );
              await client.invalidateQueries({ queryKey: ["refuelings"] });
              await client.invalidateQueries({ queryKey: ["analytics"] });
              await client.invalidateQueries({ queryKey: ["vehicle"] });
              client.setQueryData(["refueling", response.data.id], response);
              navigate(`/tankovani/${response.data.id}?${params}`);
            }}
          />
        )}
      </section>
    </>
  );
}
export function RefuelingDetail() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const client = useQueryClient();
  const navigate = useNavigate();
  const query = useQuery({
    queryKey: ["refueling", id],
    queryFn: () => api<Refueling>(`refuelings/${id}/`),
    refetchInterval: 30000,
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState<"record" | "receipt" | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const uploadRef = useRef<HTMLInputElement>(null);
  async function reload() {
    await query.refetch();
    await client.invalidateQueries({ queryKey: ["refuelings"] });
    await client.invalidateQueries({ queryKey: ["analytics"] });
    await client.invalidateQueries({ queryKey: ["vehicle"] });
  }
  if (query.isPending) return <Loading />;
  if (query.error)
    return (
      <>
        <ErrorMessage>{errorText(query.error)}</ErrorMessage>
        <Link to="/tankovani">Zpět na historii</Link>
      </>
    );
  const item = query.data.data;
  return (
    <>
      <Link to={`/tankovani?${params}`}>← Zpět na historii</Link>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{item.vehicle_name}</span>
          <h1>Detail tankování</h1>
          <p>
            {new Date(item.date + "T12:00:00").toLocaleDateString("cs-CZ")} ·
            pořadí dne {item.day_sequence}
          </p>
        </div>
        <div className="vehicle-actions">
          {item.permissions.edit && (
            <Link
              className="button button-secondary"
              to={`/tankovani/${id}/upravit?${params}`}
            >
              Upravit tankování
            </Link>
          )}
          {item.permissions.delete && (
            <Button variant="danger" onClick={() => setConfirm("record")}>
              Smazat tankování
            </Button>
          )}
        </div>
      </div>
      <section className="panel">
        <h2>{numberText(item.total_amount)} Kč</h2>
        <p className="muted">
          {item.amount_source === "ENTERED"
            ? "Přesná zadaná částka"
            : "Částka vypočtená z litrů a ceny"}
        </p>
        <dl className="vehicle-facts">
          {Object.entries({
            Litry: numberText(item.liters, 3) + " l",
            "Zadaná cena za litr":
              item.unit_price_entered !== null
                ? numberText(item.unit_price_entered, 4) + " Kč"
                : "Neuvedena",
            "Efektivní cena":
              numberText(item.effective_unit_price, 4) + " Kč/l",
            Tachometr:
              item.odometer_km === null
                ? "Chybí"
                : numberText(item.odometer_km, 0) + " km",
            Palivo: fuels[item.fuel_type],
            "Plná nádrž": item.is_full_tank ? "Ano" : "Ne",
            "Mezera před záznamem": item.break_before ? "Ano" : "Ne",
            Stanice: item.station_custom_name || stations[item.station_code],
            Autor: item.created_by_name,
            "Poslední úprava": item.updated_by_name,
            Plátce: item.paid_by_name || "Neuveden",
            Poznámka: item.note || "Bez poznámky",
          }).map(([key, value]) => (
            <div key={key}>
              <dt>{key}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
        {item.quality_warnings.length > 0 && (
          <>
            <h3>Upozornění k údajům</h3>
            <ul>
              {item.quality_warnings.map((w) => (
                <li key={w.code}>{w.message}</li>
              ))}
            </ul>
          </>
        )}
      </section>
      <section className="panel receipt-panel">
        <h2>Účtenka</h2>
        <p className="muted">
          Soukromý JPEG/PNG do 10 MiB a 24 megapixelů. Originál může obsahovat
          metadata polohy; přístup mají uživatelé sdíleného auta.
        </p>
        {item.receipt ? (
          <>
            <img
              className="receipt-preview"
              src={`/api/v1/refuelings/${id}/receipt/?variant=preview&version=${item.receipt.version}`}
              alt="Náhled účtenky"
            />
            <div className="vehicle-actions">
              <Button
                variant="secondary"
                disabled={busy}
                onClick={async () => {
                  try {
                    saveBlob(
                      (
                        await api<Blob>(`refuelings/${id}/receipt/`, {
                          binary: true,
                        })
                      ).data,
                      item.receipt!.original_filename,
                    );
                  } catch (e) {
                    setError(errorText(e));
                  }
                }}
              >
                Stáhnout originál
              </Button>
              {item.permissions.edit && (
                <Button
                  variant="secondary"
                  onClick={() => setConfirm("receipt")}
                >
                  Smazat účtenku
                </Button>
              )}
            </div>
          </>
        ) : (
          <p>Účtenka zatím není přiložena. Tankování je už uložené.</p>
        )}
        {item.permissions.edit && (
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (!file) return;
              setBusy(true);
              setError("");
              const body = new FormData();
              body.append("file", file);
              try {
                await api(`refuelings/${id}/receipt/`, {
                  method: item.receipt ? "PUT" : "POST",
                  body,
                  etag: query.data.etag!,
                });
                setFile(null);
                if (uploadRef.current) uploadRef.current.value = "";
                await reload();
              } catch (e) {
                setError(
                  errorText(e) +
                    " Tankování zůstává uložené. Nahrání lze zopakovat u tohoto záznamu.",
                );
              } finally {
                setBusy(false);
              }
            }}
          >
            <label htmlFor="receipt-file">
              {item.receipt ? "Nahradit účtenku" : "Přiložit účtenku"}
            </label>
            <input
              ref={uploadRef}
              className="input"
              type="file"
              id="receipt-file"
              accept="image/jpeg,image/png"
              onChange={(e) => {
                const next = e.target.files?.[0] || null;
                setFile(next);
                if (next && next.size > 10 * 1024 * 1024)
                  setError("Soubor přesahuje 10 MiB.");
                else setError("");
              }}
            />
            <Button
              disabled={!file || busy || file.size > 10 * 1024 * 1024}
              type="submit"
            >
              {busy
                ? "Nahrávání…"
                : item.receipt
                  ? "Nahradit obrázek"
                  : "Nahrát účtenku"}
            </Button>
          </form>
        )}
      </section>
      <ErrorMessage>{error}</ErrorMessage>
      {error && (
        <Button
          variant="secondary"
          onClick={() => {
            void reload();
            setError("");
          }}
        >
          Načíst aktuální záznam
        </Button>
      )}
      {item.permissions.reorder && (
        <DayOrder
          vehicleId={item.vehicle_id}
          date={item.date}
          onChange={reload}
        />
      )}
      <Modal
        open={!!confirm}
        onClose={() => {
          if (!busy) {
            setConfirm(null);
            setError("");
          }
        }}
        title={confirm === "record" ? "Smazat tankování?" : "Smazat účtenku?"}
        description={`${item.date} · ${item.vehicle_name} · ${numberText(item.total_amount)} Kč. ${confirm === "record" ? "Odstraní se záznam i účtenka; změní se podklady budoucích statistik." : "Tankování zůstane zachované."}`}
      >
        <ErrorMessage>{error}</ErrorMessage>
        <Button
          variant="danger"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setError("");
            try {
              await api(
                `refuelings/${id}/${confirm === "receipt" ? "receipt/" : ""}`,
                { method: "DELETE", etag: query.data.etag! },
              );
              await client.invalidateQueries({ queryKey: ["refuelings"] });
              await client.invalidateQueries({ queryKey: ["analytics"] });
              if (confirm === "record") {
                client.removeQueries({ queryKey: ["refueling", id] });
                navigate(`/tankovani?${params}`);
              } else await reload();
              setConfirm(null);
            } catch (e) {
              setError(errorText(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          Potvrdit smazání
        </Button>
      </Modal>
    </>
  );
}
function DayOrder({
  vehicleId,
  date,
  onChange,
}: {
  vehicleId: string;
  date: string;
  onChange: () => Promise<void>;
}) {
  const query = useQuery({
    queryKey: ["day-order", vehicleId, date],
    queryFn: () =>
      api<{ ordered_ids: string[] }>(
        `vehicles/${vehicleId}/refueling-order/?date=${date}`,
      ),
  });
  const [order, setOrder] = useState<string[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const ids = order || query.data?.data.ordered_ids || [];
  if (!query.data || ids.length < 2) return null;
  return (
    <section className="panel">
      <h2>Pořadí tankování dne {date}</h2>
      <p className="muted">
        Změna celého dne je vyhrazená vlastníkovi a správci. Čísla odpovídají
        původnímu pořadí; detaily otevřete odkazem.
      </p>
      <ol className="day-order">
        {ids.map((id, index) => (
          <li key={id}>
            <Link to={`/tankovani/${id}`}>
              Tankování {query.data.data.ordered_ids.indexOf(id) + 1}
            </Link>
            <Button
              variant="ghost"
              disabled={index === 0 || busy}
              onClick={() => {
                const next = [...ids];
                [next[index - 1], next[index]] = [next[index], next[index - 1]];
                setOrder(next);
              }}
            >
              Výše
            </Button>
            <Button
              variant="ghost"
              disabled={index === ids.length - 1 || busy}
              onClick={() => {
                const next = [...ids];
                [next[index + 1], next[index]] = [next[index], next[index + 1]];
                setOrder(next);
              }}
            >
              Níže
            </Button>
          </li>
        ))}
      </ol>
      <ErrorMessage>{error}</ErrorMessage>
      <Button
        disabled={!order || busy}
        onClick={async () => {
          setBusy(true);
          setError("");
          try {
            await api(`vehicles/${vehicleId}/refueling-order/`, {
              method: "PUT",
              etag: query.data.etag!,
              body: { date, ordered_ids: ids },
            });
            setOrder(null);
            await query.refetch();
            await onChange();
          } catch (e) {
            setError(errorText(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        Uložit pořadí dne
      </Button>
      {error && (
        <Button
          variant="secondary"
          onClick={() => {
            setOrder(null);
            void query.refetch();
          }}
        >
          Načíst aktuální pořadí
        </Button>
      )}
    </section>
  );
}

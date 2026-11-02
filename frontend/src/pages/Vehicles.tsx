import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CarFront, Plus, ArrowLeft } from "lucide-react";
import { useState } from "react";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { Button, ErrorMessage, Loading, Modal } from "../components/ui";
import { api, errorText } from "../lib/api";
import { useSession } from "../lib/auth";
import type { Page, Vehicle } from "../lib/types";
import {
  fuels,
  roles,
  methodologies,
  VehicleForm,
} from "../features/vehicles/VehicleForm";
import { VehicleSharing } from "../features/vehicles/VehicleSharing";

export function VehicleCard({ vehicle }: { vehicle: Vehicle }) {
  const { data: user } = useSession();
  return (
    <article className="panel vehicle-card">
      <div className="vehicle-card-top">
        <span className="icon-tile">
          <CarFront size={28} />
        </span>
        <span className="date-chip">
          {vehicle.status === "ARCHIVED" ? "Archivované" : "Aktivní"}
        </span>
      </div>
      <h2>
        <Link to={`/auta/${vehicle.id}`}>{vehicle.name}</Link>
      </h2>
      <p>
        {vehicle.make} {vehicle.model}
        {vehicle.manufacture_year ? ` · ${vehicle.manufacture_year}` : ""}
      </p>
      <p className="muted">
        {vehicle.registration_plate || "Bez registrační značky"} ·{" "}
        {fuels[vehicle.fuel_type]}
      </p>
      <p className="vehicle-role">
        {vehicle.owner_id === user?.id
          ? "Vlastní auto"
          : vehicle.effective_role === "ADMIN"
            ? "Správa vozidla"
            : "Sdílené auto"}{" "}
        · {roles[vehicle.effective_role]}
      </p>
      <Link className="button button-secondary" to={`/auta/${vehicle.id}`}>
        Detail auta
      </Link>
    </article>
  );
}
export function Vehicles({ admin = false }: { admin?: boolean }) {
  const [params, setParams] = useSearchParams();
  const status = params.get("status") || (admin ? "all" : "active");
  const page = Number(params.get("page") || 1);
  const query = useQuery({
    queryKey: ["vehicles", admin, status, page],
    queryFn: () =>
      api<Page<Vehicle>>(
        `${admin ? "admin/" : ""}vehicles/?status=${encodeURIComponent(status)}&page=${page}`,
      ),
  });
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">VAŠE GARÁŽ</span>
          <h1>{admin ? "Všechna vozidla a sdílení" : "Moje auta"}</h1>
          <p className="muted">Vlastní i sdílená vozidla na jednom místě.</p>
        </div>
        <Link className="button button-primary" to="/auta/nove">
          <Plus size={18} /> Přidat auto
        </Link>
      </div>
      <div className="vehicle-filters">
        <label htmlFor="vehicle-status">Stav vozidel</label>
        <select
          className="input"
          id="vehicle-status"
          value={status}
          onChange={(e) => setParams({ status: e.target.value })}
        >
          <option value="active">Aktivní</option>
          <option value="archived">Archivovaná</option>
          <option value="all">Všechna</option>
        </select>
        {query.data && (
          <span className="muted">Celkem {query.data.data.count}</span>
        )}
      </div>
      {query.isPending ? (
        <Loading />
      ) : query.error ? (
        <>
          <ErrorMessage>{errorText(query.error)}</ErrorMessage>
          <Button onClick={() => query.refetch()}>Zkusit znovu</Button>
        </>
      ) : (
        <>
          {query.data.data.count === 0 ? (
            <section className="panel">
              <h2>Žádná vozidla v tomto výběru</h2>
              <p>
                Přidejte své první auto nebo změňte filtr. Sdílení přiděluje
                správce.
              </p>
            </section>
          ) : (
            <div className="vehicle-grid">
              {query.data.data.results.map((vehicle) => (
                <VehicleCard key={vehicle.id} vehicle={vehicle} />
              ))}
            </div>
          )}
          <div className="vehicle-actions">
            <Button
              variant="secondary"
              disabled={!query.data.data.previous}
              onClick={() => setParams({ status, page: String(page - 1) })}
            >
              Předchozí
            </Button>
            <span>Strana {page}</span>
            <Button
              variant="secondary"
              disabled={!query.data.data.next}
              onClick={() => setParams({ status, page: String(page + 1) })}
            >
              Další
            </Button>
          </div>
        </>
      )}
    </>
  );
}
export function VehicleEditor() {
  const { id } = useParams();
  const navigate = useNavigate();
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["vehicle", id],
    queryFn: () => api<Vehicle>(`vehicles/${id}/`),
    enabled: !!id,
  });
  if (id && query.isPending) return <Loading />;
  if (id && query.error)
    return <ErrorMessage>{errorText(query.error)}</ErrorMessage>;
  if (id && !query.data?.data.permissions.edit)
    return (
      <ErrorMessage>
        Údaje vozidla mění pouze vlastník nebo administrátor.
      </ErrorMessage>
    );
  return (
    <>
      <Link to={id ? `/auta/${id}` : "/auta"}>
        <ArrowLeft size={16} /> Zpět na auta
      </Link>
      <div className="page-heading">
        <h1>{id ? "Upravit auto" : "Nové auto"}</h1>
      </div>
      <section className="panel">
        <VehicleForm
          key={query.data?.etag || "new"}
          vehicle={query.data?.data}
          onReload={() => query.refetch()}
          onSave={async (data) => {
            const saved = await api<Vehicle>(
              id ? `vehicles/${id}/` : "vehicles/",
              {
                method: id ? "PATCH" : "POST",
                body: data,
                etag: query.data?.etag || undefined,
              },
            );
            await client.invalidateQueries({ queryKey: ["vehicles"] });
            client.setQueryData(["vehicle", saved.data.id], saved);
            navigate(`/auta/${saved.data.id}`);
          }}
        />
      </section>
    </>
  );
}
export function VehicleDetail() {
  const { id } = useParams();
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["vehicle", id],
    queryFn: () => api<Vehicle>(`vehicles/${id}/`),
    refetchInterval: 30000,
  });
  const [confirm, setConfirm] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (query.isPending) return <Loading />;
  if (query.error)
    return (
      <>
        <ErrorMessage>{errorText(query.error)}</ErrorMessage>
        <Link to="/auta">Zpět na auta</Link>
      </>
    );
  const vehicle = query.data.data;
  const number = (v: number | string | null, unit = "") =>
    v === null
      ? "Neuvedeno"
      : `${Number(v).toLocaleString("cs-CZ", { maximumFractionDigits: 3 })}${unit}`;
  return (
    <>
      <Link to="/auta">
        <ArrowLeft size={16} /> Zpět na auta
      </Link>
      <div className="page-heading">
        <div>
          <span className="eyebrow">
            {roles[vehicle.effective_role]} ·{" "}
            {vehicle.status === "ACTIVE" ? "AKTIVNÍ" : "ARCHIVOVANÉ"}
          </span>
          <h1>{vehicle.name}</h1>
          <p className="muted">
            {vehicle.make} {vehicle.model}
          </p>
        </div>
        <div className="vehicle-actions">
          {vehicle.permissions.edit && (
            <Link
              className="button button-secondary"
              to={`/auta/${id}/upravit`}
            >
              Upravit údaje
            </Link>
          )}
          {(vehicle.permissions.archive || vehicle.permissions.restore) && (
            <Button variant="secondary" onClick={() => setConfirm(true)}>
              {vehicle.status === "ACTIVE" ? "Archivovat auto" : "Obnovit auto"}
            </Button>
          )}
        </div>
      </div>
      <section className="panel">
        <h2>Údaje vozidla</h2>
        <dl className="vehicle-facts">
          {Object.entries({
            "Registrační značka": vehicle.registration_plate || "Neuvedena",
            VIN: vehicle.vin || "Neuveden",
            Palivo: fuels[vehicle.fuel_type],
            "Rok výroby": number(vehicle.manufacture_year),
            "Počáteční tachometr": number(vehicle.initial_odometer_km, " km"),
            "Objem motoru": number(vehicle.engine_displacement_cc, " cm³"),
            Výkon: number(vehicle.power_kw, " kW"),
            "Objem nádrže": number(vehicle.tank_capacity_l, " l"),
            "Normovaná spotřeba": number(
              vehicle.standard_consumption_l_100km,
              " l/100 km",
            ),
            "Metodika normy": methodologies[vehicle.standard_methodology],
            "Zdroj normy": vehicle.standard_source || "Neuveden",
            "Poznámka ke zdroji": vehicle.standard_source_note || "Neuvedena",
          }).map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
        {vehicle.consumption_mode === "UNSUPPORTED_MULTI_TANK" && (
          <p className="alert">
            Více nádrží / souběžná paliva: budoucí měření spotřeby nebude
            dostupné.
          </p>
        )}
      </section>
      <section className="panel">
        <h2>Historie a spotřeba</h2>
        <p className="muted">
          Evidence tankování bude dostupná ve fázi 3, výpočty ve fázi 4.
        </p>
        {vehicle.status === "ARCHIVED" && (
          <p>
            Archivace zachovává historii. Nové tankování bude možné po obnovení
            auta.
          </p>
        )}
      </section>
      {vehicle.permissions.manage_access && (
        <VehicleSharing
          vehicle={vehicle}
          etag={query.data.etag!}
          onChange={async () => {
            await client.invalidateQueries({ queryKey: ["vehicle", id] });
            await client.invalidateQueries({ queryKey: ["vehicles"] });
          }}
        />
      )}
      <Modal
        open={confirm}
        onClose={() => {
          if (!busy) {
            setConfirm(false);
            setError("");
          }
        }}
        title={
          vehicle.status === "ACTIVE"
            ? `Archivovat ${vehicle.name}?`
            : `Obnovit ${vehicle.name}?`
        }
        description="Archivace zachovává vozidlo i celou historii. Nové tankování do archivovaného auta nebude možné."
      >
        <ErrorMessage>{error}</ErrorMessage>
        <Button
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setError("");
            try {
              await api(
                `vehicles/${id}/${vehicle.status === "ACTIVE" ? "archive" : "restore"}/`,
                { method: "POST", body: {}, etag: query.data.etag! },
              );
              await client.invalidateQueries({ queryKey: ["vehicles"] });
              await query.refetch();
              setConfirm(false);
            } catch (e) {
              setError(errorText(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          Potvrdit
        </Button>
        {error && (
          <Button
            variant="secondary"
            onClick={() => {
              void query.refetch();
              setConfirm(false);
            }}
          >
            Načíst aktuální údaje
          </Button>
        )}
      </Modal>
    </>
  );
}

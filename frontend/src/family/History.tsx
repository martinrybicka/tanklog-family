import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Camera,
  CarFront,
  Check,
  Droplets,
  ReceiptText,
  Wallet,
} from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ErrorMessage, Loading } from "../components/ui";
import { api, errorText } from "../lib/api";
import type { Page, Refueling } from "../lib/types";
import { dateText, decimalText } from "../features/analytics/format";
import { familyCars } from "./api";
import { ReceiptRows } from "./Home";
export function FamilyHistory() {
  const [params, setParams] = useSearchParams();
  const page = Number(params.get("page") || 1);
  const vehicle = params.get("vehicle_id") || "";
  const cars = useQuery({
    queryKey: ["vehicles", "family"],
    queryFn: familyCars,
  });
  const records = useQuery({
    queryKey: ["refuelings", "family-history", page, vehicle],
    queryFn: () =>
      api<Page<Refueling>>(
        `refuelings/?page=${page}&page_size=12${vehicle ? `&vehicle_id=${vehicle}` : ""}`,
      ),
  });
  return (
    <>
      <div className="family-greeting">
        <div>
          <span className="family-eyebrow">VŠECHNY CESTY POHROMADĚ</span>
          <h1>Vaše tankování</h1>
          <p>Účtenky už nemusíte hledat po kapsách.</p>
        </div>
        <Link className="family-primary" to="/uctenka">
          <Camera size={19} />
          Přidat účtenku
        </Link>
      </div>
      <section className="family-card family-history">
        <div className="family-section-heading">
          <h2>Uložená historie</h2>
          <label className="family-history-filter">
            <CarFront size={18} />
            <span className="sr-only">Filtrovat podle auta</span>
            <select
              value={vehicle}
              onChange={(e) =>
                setParams(e.target.value ? { vehicle_id: e.target.value } : {})
              }
            >
              <option value="">Všechna auta</option>
              {cars.data?.map((car) => (
                <option value={car.id} key={car.id}>
                  {car.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <ErrorMessage>{records.error && errorText(records.error)}</ErrorMessage>
        {records.isPending ? (
          <Loading />
        ) : records.data?.data.results.length ? (
          <ReceiptRows items={records.data.data.results} />
        ) : (
          <div className="family-empty">
            <ReceiptText size={35} />
            <h2>Zatím žádné tankování</h2>
            <p>První účtenka tu bude hned po uložení.</p>
          </div>
        )}
        <div className="family-pagination">
          <button
            disabled={page <= 1 || records.isFetching}
            onClick={() =>
              setParams({
                ...Object.fromEntries(params),
                page: String(page - 1),
              })
            }
          >
            <ArrowLeft size={16} />
            Zpět
          </button>
          <span>Strana {page}</span>
          <button
            disabled={!records.data?.data.next || records.isFetching}
            onClick={() =>
              setParams({
                ...Object.fromEntries(params),
                page: String(page + 1),
              })
            }
          >
            Další
            <ArrowRight size={16} />
          </button>
        </div>
      </section>
    </>
  );
}
export function FamilyReceiptDetail() {
  const { id } = useParams();
  const query = useQuery({
    queryKey: ["refuelings", id],
    queryFn: () => api<Refueling>(`refuelings/${id}/`),
  });
  const item = query.data?.data;
  return (
    <div className="family-wizard">
      <Link className="family-back" to="/historie">
        <ArrowLeft size={17} />
        Zpět na historii
      </Link>
      <ErrorMessage>{query.error && errorText(query.error)}</ErrorMessage>
      {query.isPending ? (
        <Loading />
      ) : (
        item && (
          <section className="family-card family-detail">
            <span className="family-large-icon">
              <ReceiptText size={28} />
            </span>
            <h1>{item.vehicle_name}</h1>
            <p>
              {dateText(item.date)} ·{" "}
              {item.station_custom_name || item.station_code || "Tankování"}
            </p>
            <div className="family-detail-numbers">
              <span>
                <Wallet size={20} />
                <strong>{decimalText(item.total_amount)} Kč</strong>Zaplaceno
              </span>
              <span>
                <Droplets size={20} />
                <strong>{decimalText(item.liters, 2)} l</strong>Natankováno
              </span>
            </div>
            <dl>
              <div>
                <dt>Tachometr</dt>
                <dd>
                  {item.odometer_km === null
                    ? "Neuveden"
                    : `${item.odometer_km.toLocaleString("cs-CZ")} km`}
                </dd>
              </div>
              <div>
                <dt>Nádrž</dt>
                <dd>
                  {item.is_full_tank ? (
                    <>
                      <Check size={15} />
                      Do plné
                    </>
                  ) : (
                    "Částečné tankování"
                  )}
                </dd>
              </div>
              {item.note && (
                <div>
                  <dt>Poznámka</dt>
                  <dd>{item.note}</dd>
                </div>
              )}
            </dl>
            {item.receipt && (
              <div className="family-detail-photo">
                <h2>Uložená účtenka</h2>
                <img
                  alt="Uložená účtenka tankování"
                  src={`/api/v1/refuelings/${item.id}/receipt/?variant=preview&version=${item.receipt.version}`}
                />
              </div>
            )}
            {item.permissions.edit && (
              <Link
                className="family-text-button"
                to={`/tankovani/${item.id}/upravit`}
              >
                Opravit údaje
                <ArrowRight size={16} />
              </Link>
            )}
          </section>
        )
      )}
    </div>
  );
}

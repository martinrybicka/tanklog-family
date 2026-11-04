import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Camera,
  CarFront,
  Check,
  Droplets,
  Plus,
  ReceiptText,
  ShieldCheck,
  Sparkles,
  Wallet,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useSession } from "../lib/auth";
import { api, errorText } from "../lib/api";
import type { Page, Refueling } from "../lib/types";
import { ErrorMessage, Loading } from "../components/ui";
import { dateText, decimalText } from "../features/analytics/format";
import { familyCars, type Draft } from "./api";

export function RoadIllustration() {
  return (
    <svg
      className="family-road"
      viewBox="0 0 400 270"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="224" cy="120" r="100" fill="white" fillOpacity=".06" />
      <circle cx="224" cy="120" r="73" stroke="white" strokeOpacity=".1" />
      <path
        d="M32 262C32 205 352 249 352 166S81 204 81 120C81 85 121 70 158 71"
        stroke="white"
        strokeOpacity=".12"
        strokeWidth="44"
      />
      <path
        d="M32 262C32 205 352 249 352 166S81 204 81 120C81 85 121 70 158 71"
        stroke="white"
        strokeOpacity=".5"
        strokeDasharray="8 12"
        strokeWidth="2"
      />
      <g transform="translate(140 76) rotate(-8 90 50)">
        <ellipse
          cx="90"
          cy="104"
          rx="89"
          ry="10"
          fill="#262965"
          fillOpacity=".2"
        />
        <path
          d="M13 57 39 49 59 17C62 12 67 10 76 10H127C136 10 144 16 150 25L169 51 179 59V87H8V66C8 62 9 60 13 57Z"
          fill="#F8FAFF"
        />
        <path
          d="M52 47 68 22H94V47H52ZM103 22H123C129 22 133 24 137 30L149 47H103V22Z"
          fill="#9CAAF5"
        />
        <path d="M10 67H32M155 64H178" stroke="#FFC88D" strokeWidth="8" />
        <path
          d="M104 59H115"
          stroke="#B9C3E4"
          strokeWidth="4"
          strokeLinecap="round"
        />
        <circle cx="44" cy="87" r="18" fill="#293453" />
        <circle cx="44" cy="87" r="9" fill="#D4DCF6" />
        <circle cx="146" cy="87" r="18" fill="#293453" />
        <circle cx="146" cy="87" r="9" fill="#D4DCF6" />
      </g>
      <g transform="translate(287 34)">
        <rect width="51" height="51" rx="16" fill="white" />
        <path
          d="m16 26 7 7 14-15"
          stroke="#5575CB"
          strokeWidth="4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </g>
      <path d="m83 43 3 8 8 3-8 3-3 8-3-8-8-3 8-3 3-8Z" fill="#D9D7FF" />
      <circle cx="350" cy="116" r="5" fill="#DDDFFF" />
    </svg>
  );
}
function ReceiptRows({ items }: { items: Refueling[] }) {
  return (
    <div className="family-receipt-list">
      {items.map((item) => (
        <Link
          key={item.id}
          className="family-receipt-row"
          to={`/historie/${item.id}`}
        >
          <span className="family-icon-soft">
            <ReceiptText size={21} />
          </span>
          <span>
            <strong>
              {item.station_custom_name ||
                (item.station_code && item.station_code !== "OTHER"
                  ? item.station_code
                  : "Tankování")}
            </strong>
            <small>
              {item.vehicle_name} · {dateText(item.date)}
            </small>
          </span>
          <span className="family-receipt-value">
            <strong>{decimalText(item.total_amount)} Kč</strong>
            <small>
              {decimalText(item.liters, 2)} l <ArrowRight size={13} />
            </small>
          </span>
        </Link>
      ))}
    </div>
  );
}
export { ReceiptRows };
export function FamilyHome() {
  const { data: user } = useSession();
  const cars = useQuery({
    queryKey: ["vehicles", "family"],
    queryFn: familyCars,
  });
  const recent = useQuery({
    queryKey: ["refuelings", "family-recent"],
    queryFn: () => api<Page<Refueling>>("refuelings/?page_size=4"),
  });
  const summary = useQuery({
    queryKey: ["analytics", "family-month"],
    queryFn: () =>
      api<{ purchases: { amount: string; count: number; liters: string } }>(
        "dashboard/",
      ),
  });
  const drafts = useQuery({
    queryKey: ["family-drafts"],
    queryFn: () => api<{ results: Draft[] }>("family/receipts/"),
  });
  const eligible = cars.data?.some((car) => car.permissions.create_refueling);
  const [month] = useState(() =>
    new Intl.DateTimeFormat("cs-CZ", {
      month: "long",
      year: "numeric",
      timeZone: "Europe/Prague",
    }).format(new Date()),
  );
  return (
    <>
      <div className="family-greeting">
        <div>
          <span className="family-eyebrow">VŠECHNO NA SVÉM MÍSTĚ</span>
          <h1>
            Dobrý den{user?.display_name ? `, ${user.display_name}` : ""}
            <span className="family-wave" aria-hidden="true">
              ☀
            </span>
          </h1>
          <p>O něco méně papírování. O něco více pohody.</p>
        </div>
        {user?.system_role === "ADMIN" && (
          <Link className="family-admin-link" to="/rodina">
            <ShieldCheck size={18} />
            Správa rodiny
            <ArrowRight size={16} />
          </Link>
        )}
      </div>
      <section className="family-hero">
        <div>
          <span className="family-hero-label">
            <Sparkles size={16} /> VÁŠ MALÝ POMOCNÍK
          </span>
          <h2>
            Natankováno?
            <br />
            Účtenku sem.
          </h2>
          <p>
            Vyfoťte nebo nahrajte účtenku.
            <br />
            Údaje pak už jen zkontrolujete a uložíte.
          </p>
          <Link className="family-hero-button" to="/uctenka">
            <Camera size={21} />
            Přidat účtenku
            <ArrowRight size={18} />
          </Link>
          <small>
            <Check size={15} />
            Bez přepisování všeho od začátku
          </small>
        </div>
        <RoadIllustration />
      </section>
      <div className="family-section-heading">
        <h2>Tenhle měsíc v kostce</h2>
        <span>{month}</span>
      </div>
      <ErrorMessage>{summary.error && errorText(summary.error)}</ErrorMessage>
      <div className="family-stats">
        {[
          {
            icon: Wallet,
            label: "Zaplaceno za palivo",
            value: summary.data
              ? `${decimalText(summary.data.data.purchases.amount, 0)} Kč`
              : "—",
            tone: "violet",
          },
          {
            icon: ReceiptText,
            label: "Uložená tankování",
            value: summary.data
              ? String(summary.data.data.purchases.count)
              : "—",
            tone: "blue",
          },
          {
            icon: Droplets,
            label: "Natankováno",
            value: summary.data
              ? `${decimalText(summary.data.data.purchases.liters, 1)} l`
              : "—",
            tone: "mint",
          },
        ].map(({ icon: Icon, label, value, tone }) => (
          <section className="family-stat" key={label}>
            <span className={`family-stat-icon ${tone}`}>
              <Icon size={24} />
            </span>
            <div>
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
          </section>
        ))}
      </div>
      {!!drafts.data?.data.results.length && (
        <section className="family-drafts">
          <div>
            <ReceiptText size={22} />
            <div>
              <h2>Ještě dokončit</h2>
              <p>Rozpracované účtenky už bezpečně čekají v databázi.</p>
            </div>
          </div>
          {drafts.data.data.results.map((draft) => (
            <Link key={draft.id} to={`/uctenka?draft=${draft.id}`}>
              Účtenka z {dateText(draft.created_at.slice(0, 10))}
              <ArrowRight size={16} />
            </Link>
          ))}
        </section>
      )}
      <div className="family-home-grid">
        <section className="family-card">
          <div className="family-section-heading">
            <h2>Poslední tankování</h2>
            <Link to="/historie">
              Celá historie
              <ArrowRight size={15} />
            </Link>
          </div>
          <ErrorMessage>{recent.error && errorText(recent.error)}</ErrorMessage>
          {recent.isPending ? (
            <Loading />
          ) : recent.data?.data.results.length ? (
            <ReceiptRows items={recent.data.data.results} />
          ) : (
            <div className="family-empty">
              <ReceiptText size={34} />
              <h3>Tady budou vaše účtenky</h3>
              <p>První tankování přidáte během chvilky.</p>
              <Link to="/uctenka">
                Přidat první účtenku
                <ArrowRight size={16} />
              </Link>
            </div>
          )}
        </section>
        <aside className="family-garage">
          <section className="family-card">
            <div className="family-section-heading">
              <h2>Naše garáž</h2>
              <CarFront size={20} />
            </div>
            <ErrorMessage>{cars.error && errorText(cars.error)}</ErrorMessage>
            {cars.isPending ? (
              <Loading />
            ) : cars.data?.length ? (
              cars.data.slice(0, 3).map((car) => (
                <div key={car.id} className="family-car">
                  <span className="family-car-icon">
                    <CarFront size={32} strokeWidth={1.5} />
                  </span>
                  <div>
                    <strong>{car.name}</strong>
                    <small>
                      {car.make} {car.model}
                    </small>
                    <span className="family-car-plate">
                      {car.registration_plate || "Rodinné auto"}
                    </span>
                  </div>
                  <span className="family-car-status" aria-hidden="true" />
                </div>
              ))
            ) : (
              <p className="family-note">
                Správce vám nejprve připraví a zpřístupní auto.
              </p>
            )}
          </section>
          <div className="family-tip">
            <span className="family-tip-icon">
              <Sparkles size={21} />
            </span>
            <div>
              <strong>
                {eligible
                  ? "Malý tip, velká úspora času"
                  : "Nastavení nechte na správci"}
              </strong>
              <p>
                {eligible
                  ? "Účtenku vyfoťte rovně a na světle. Údaje se pak čtou lépe."
                  : "Auta a přístupy připraví správce. Vy se můžete soustředit na cesty."}
              </p>
            </div>
          </div>
          {user?.system_role === "ADMIN" && (
            <Link className="family-setup-link" to="/administrace/vozidla">
              <Plus size={17} />
              Připravit auta a přístupy
            </Link>
          )}
        </aside>
      </div>
    </>
  );
}

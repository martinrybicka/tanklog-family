import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  CarFront,
  Check,
  LayoutDashboard,
  Settings2,
  ShieldCheck,
  UsersRound,
} from "lucide-react";
import { Link, Navigate } from "react-router-dom";
import { useSession } from "../lib/auth";
import { api, errorText } from "../lib/api";
import type { Page, User } from "../lib/types";
import { ErrorMessage, Loading } from "../components/ui";
import { familyCars } from "./api";
function MemberSetting({ user }: { user: User }) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["family-preference", user.id],
    queryFn: () =>
      api<{ default_vehicle_id: string | null }>(
        `family/admin/settings/${user.id}/`,
      ),
  });
  const cars = useQuery({
    queryKey: ["vehicles", "family"],
    queryFn: familyCars,
  });
  const [selection, setSelection] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  return (
    <section className="family-member">
      <span className="family-avatar">
        {(user.display_name || user.username).slice(0, 1).toUpperCase()}
      </span>
      <div>
        <h3>{user.display_name || user.username}</h3>
        <small>
          {user.username} ·{" "}
          {user.system_role === "ADMIN" ? "Správce" : "Člen rodiny"}
        </small>
        <label className="family-field">
          Výchozí auto
          <select
            disabled={busy || query.isPending}
            value={selection ?? query.data?.data.default_vehicle_id ?? ""}
            onChange={(e) => {
              setSelection(e.target.value);
              setMessage("");
            }}
          >
            <option value="">Automaticky při jednom dostupném autě</option>
            {cars.data
              ?.filter((car) => car.permissions.create_refueling)
              .map((car) => (
                <option key={car.id} value={car.id}>
                  {car.name}
                </option>
              ))}
          </select>
        </label>
        <ErrorMessage>
          {error || (query.error && errorText(query.error))}
        </ErrorMessage>
        <small role="status">{message}</small>
      </div>
      <button
        className="family-secondary"
        disabled={busy || !query.data}
        onClick={async () => {
          setBusy(true);
          setError("");
          try {
            await api(`family/admin/settings/${user.id}/`, {
              method: "PUT",
              body: {
                default_vehicle_id:
                  (selection ?? query.data?.data.default_vehicle_id) || null,
              },
              etag: query.data?.etag ?? undefined,
            });
            await client.invalidateQueries({ queryKey: ["family-preference"] });
            setSelection(null);
            setMessage("Uloženo. Auto bude předvybrané i na jiném zařízení.");
          } catch (e) {
            setError(errorText(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        <Check size={17} />
        {busy ? "Ukládání…" : "Uložit"}
      </button>
    </section>
  );
}
export function FamilyAdmin() {
  const session = useSession();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const users = useQuery({
    queryKey: ["users", "family", page, search],
    enabled: session.data?.system_role === "ADMIN",
    queryFn: () =>
      api<Page<User>>(
        `admin/users/?is_active=true&page_size=12&page=${page}&search=${encodeURIComponent(search)}`,
      ),
  });
  if (session.data?.system_role !== "ADMIN") return <Navigate to="/" replace />;
  return (
    <>
      <div className="family-greeting">
        <div>
          <span className="family-eyebrow">
            PŘIPRAVÍTE JEDNOU. POUŽÍVAJÍ VŠICHNI.
          </span>
          <h1>Správa rodiny</h1>
          <p>Vy nastavíte auta a přístupy. Ostatní už jen přidávají účtenky.</p>
        </div>
        <span className="family-admin-pill">
          <ShieldCheck size={17} />
          Administrátor
        </span>
      </div>
      <div className="family-admin-cards">
        {[
          {
            icon: UsersRound,
            title: "1. Členové rodiny",
            text: "Vytvořte účty a předejte přihlašovací údaje.",
            to: "/administrace/uzivatele",
          },
          {
            icon: CarFront,
            title: "2. Auta a přístupy",
            text: "Připravte auta a přidělte členům právo přispívat.",
            to: "/administrace/vozidla",
          },
          {
            icon: LayoutDashboard,
            title: "Podrobné přehledy",
            text: "Statistiky, servis a další nástroje jsou stále po ruce.",
            to: "/prehled",
          },
        ].map(({ icon: Icon, title, text, to }) => (
          <Link className="family-card family-admin-card" key={title} to={to}>
            <span className="family-icon-soft">
              <Icon size={24} />
            </span>
            <h2>{title}</h2>
            <p>{text}</p>
            <ArrowRight size={20} />
          </Link>
        ))}
      </div>
      <section className="family-card family-admin-settings">
        <div className="family-section-heading">
          <h2>
            <Settings2 size={20} />
            3. Předvybraná auta
          </h2>
        </div>
        <p className="family-note">
          Nejprve zpřístupněte auto konkrétnímu členovi jako přispěvateli nebo
          vlastníkovi. Výběr níže přístup sám nepřidává.
        </p>
        <ErrorMessage>{users.error && errorText(users.error)}</ErrorMessage>
        <label className="family-field family-member-search">
          Najít člena rodiny
          <input
            type="search"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            placeholder="Jméno nebo uživatelský účet"
          />
        </label>
        {users.isPending ? (
          <Loading />
        ) : (
          users.data?.data.results.map((user) => (
            <MemberSetting key={user.id} user={user} />
          ))
        )}
        <div className="family-pagination">
          <button disabled={page === 1} onClick={() => setPage(page - 1)}>
            Předchozí
          </button>
          <span>Strana {page}</span>
          <button
            disabled={!users.data?.data.next}
            onClick={() => setPage(page + 1)}
          >
            Další
          </button>
        </div>
      </section>
    </>
  );
}

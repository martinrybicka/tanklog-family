import { Offline } from "./pages/Offline";
import { useQueryClient } from "@tanstack/react-query";
import {
  CarFront,
  Fuel,
  LayoutDashboard,
  LogOut,
  Settings2,
  ShieldCheck,
  UsersRound,
  ScrollText,
  Server,
  Plus,
} from "lucide-react";
import { lazy, Suspense, useEffect, useState } from "react";
import {
  Link,
  Navigate,
  NavLink,
  Outlet,
  Route,
  Routes,
  useNavigate,
  useLocation,
} from "react-router-dom";
import { Button, ErrorMessage, Loading, Logo } from "./components/ui";
import { api, errorText, forgetCsrf } from "./lib/api";
import { clearOutbox, pendingSnapshot } from "./lib/outbox";
import { announceLogout } from "./lib/sessionEvents";
import { useSession } from "./lib/auth";
import { PwaNotice } from "./components/Pwa";
import { RouteFocus } from "./components/RouteFocus";
import type { Session } from "./lib/types";
const Audit = lazy(() =>
  import("./pages/AdminInfo").then((module) => ({ default: module.Audit })),
);
const System = lazy(() =>
  import("./pages/AdminInfo").then((module) => ({ default: module.System })),
);
const Login = lazy(() =>
  import("./pages/Login").then((module) => ({ default: module.Login })),
);
const ForcedPassword = lazy(() =>
  import("./pages/Password").then((module) => ({
    default: module.ForcedPassword,
  })),
);
const Profile = lazy(() =>
  import("./pages/Profile").then((module) => ({ default: module.Profile })),
);
const Users = lazy(() =>
  import("./pages/Users").then((module) => ({ default: module.Users })),
);

const Vehicles = lazy(() =>
  import("./pages/Vehicles").then((m) => ({ default: m.Vehicles })),
);
const VehicleEditor = lazy(() =>
  import("./pages/Vehicles").then((m) => ({ default: m.VehicleEditor })),
);
const VehicleDetail = lazy(() =>
  import("./pages/Vehicles").then((m) => ({ default: m.VehicleDetail })),
);

const Refuelings = lazy(() =>
  import("./pages/Refuelings").then((m) => ({ default: m.Refuelings })),
);
const RefuelingEditor = lazy(() =>
  import("./pages/Refuelings").then((m) => ({ default: m.RefuelingEditor })),
);
const RefuelingDetail = lazy(() =>
  import("./pages/Refuelings").then((m) => ({ default: m.RefuelingDetail })),
);

const Overview = lazy(() =>
  import("./pages/Dashboard").then((m) => ({ default: m.Dashboard })),
);
const Intervals = lazy(() =>
  import("./pages/Dashboard").then((m) => ({ default: m.Intervals })),
);
const IntervalDetails = lazy(() =>
  import("./pages/Dashboard").then((m) => ({ default: m.IntervalDetails })),
);

const Events = lazy(() =>
  import("./pages/Extensions").then((m) => ({ default: m.Events })),
);
const Reminders = lazy(() =>
  import("./pages/Extensions").then((m) => ({ default: m.Reminders })),
);
const ImportHistory = lazy(() =>
  import("./pages/Extensions").then((m) => ({ default: m.ImportHistory })),
);

function Theme({ value }: { value?: string }) {
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const update = () =>
      document.documentElement.classList.toggle(
        "dark",
        value === "DARK" || ((!value || value === "SYSTEM") && media.matches),
      );
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [value]);
  return null;
}

function Protected() {
  const session = useSession();
  if (session.isPending) return <Loading />;
  if (session.error && !session.data)
    return (
      <main className="standalone">
        <ErrorMessage>{errorText(session.error)}</ErrorMessage>
        <Button onClick={() => session.refetch()}>Zkusit znovu</Button>
      </main>
    );
  if (!session.data) return <Navigate to="/prihlaseni" replace />;
  if (session.data.must_change_password)
    return <Navigate to="/zmena-hesla" replace />;
  return <Shell user={session.data} />;
}

function Shell({ user }: { user: Session }) {
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (pendingSnapshot().length) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => {
      window.removeEventListener("beforeunload", warn);
      clearOutbox();
    };
  }, [user.id]);
  const client = useQueryClient();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const admin = user.system_role === "ADMIN";
  const location = useLocation();
  const vehicleId =
    /^\/auta\/([0-9a-f-]{36})(?:\/|$)/.exec(location.pathname)?.[1] ||
    new URLSearchParams(location.search).get("vehicle_id");
  return (
    <div className="app-shell">
      <a href="#main-content" className="skip-link">
        Přejít k obsahu
      </a>
      <aside className="sidebar">
        <Link to="/" className="logo-link">
          <Logo />
          <span className="sr-only"> – přehled</span>
        </Link>
        <span className="nav-caption">VÁŠ DENÍK</span>
        <nav aria-label="Hlavní navigace">
          <NavLink end to="/">
            <LayoutDashboard size={20} />
            Přehled
          </NavLink>
          <NavLink to="/auta">
            <CarFront size={20} />
            Moje auta
          </NavLink>
          <NavLink to="/tankovani">
            <Fuel size={20} />
            Tankování
          </NavLink>
          <NavLink to="/pripominky">
            <ScrollText size={20} />
            Připomínky
          </NavLink>
          <NavLink to="/offline">
            <Fuel size={20} />
            Neuložené zápisy
          </NavLink>
          <NavLink to="/nastaveni">
            <Settings2 size={20} />
            Nastavení
          </NavLink>
        </nav>
        {admin && (
          <>
            <span className="nav-caption">SPRÁVA APLIKACE</span>
            <nav aria-label="Administrace">
              <NavLink to="/administrace/uzivatele">
                <UsersRound size={20} />
                Uživatelé
              </NavLink>
              <NavLink to="/administrace/vozidla">
                <CarFront size={20} />
                Vozidla a sdílení
              </NavLink>
              <NavLink to="/administrace/audit">
                <ScrollText size={20} />
                Auditní historie
              </NavLink>
              <NavLink to="/administrace/system">
                <Server size={20} />
                Stav systému
              </NavLink>
            </nav>
          </>
        )}
        <div className="sidebar-bottom">
          <div className="private-note">
            <ShieldCheck size={18} />
            <div>
              <strong>Soukromý prostor</strong>
              <small>Data pod vaší kontrolou</small>
            </div>
          </div>
          <div className="current-user">
            <span className="avatar">
              {(user.display_name || user.username).slice(0, 2).toUpperCase()}
            </span>
            <div>
              <strong>{user.display_name || user.username}</strong>
              <small>{admin ? "Administrátor" : "Uživatel"}</small>
            </div>
            <Button
              variant="ghost"
              aria-label="Odhlásit se"
              onClick={async () => {
                try {
                  clearOutbox();
                  await api("auth/logout/", { method: "POST" });
                  announceLogout();
                  client.clear();
                  forgetCsrf();
                  client.setQueryData(["session"], null);
                  navigate("/prihlaseni", { replace: true });
                } catch (e) {
                  setError(errorText(e));
                }
              }}
            >
              <LogOut size={17} />
            </Button>
          </div>
        </div>
      </aside>
      <div className="app-body">
        <header className="topbar">
          <div>
            <span className="desktop-only">Váš automobilový deník</span>
            <span className="mobile-only">
              <Logo />
            </span>
          </div>
          <div className="topbar-actions">
            <span className="local-badge">
              <span />
              Lokální aplikace
            </span>
            <Link
              className="button button-primary"
              to={`/tankovani/nove${vehicleId ? `?vehicle_id=${vehicleId}` : ""}`}
            >
              <Plus size={17} />
              Zadat tankování
            </Link>
          </div>
        </header>
        <main id="main-content" className="main-content" tabIndex={-1}>
          <nav className="vehicle-actions" aria-label="Nástroje evidence">
            <Link to="/pripominky">Připomínky</Link>
            <Link to="/offline">Neuložené zápisy</Link>
          </nav>
          <ErrorMessage>{error}</ErrorMessage>
          <Outlet />
        </main>
        <footer className="app-footer">
          <span>
            TankLog <span className="muted">/</span> Osobní automobilový deník
          </span>
          <span>Osobní automobilový deník</span>
        </footer>
      </div>
      <nav className="mobile-nav" aria-label="Mobilní navigace">
        <NavLink end to="/">
          <LayoutDashboard size={19} />
          Přehled
        </NavLink>
        <NavLink to="/auta">
          <CarFront size={19} />
          Auta
        </NavLink>
        <NavLink to="/tankovani">
          <Fuel size={19} />
          Tankování
        </NavLink>
        <NavLink to="/nastaveni">
          <Settings2 size={19} />
          Nastavení
        </NavLink>
        {admin && (
          <NavLink to="/administrace/uzivatele">
            <UsersRound size={19} />
            Správa
          </NavLink>
        )}
      </nav>
      <div className="mobile-logout">
        <Button
          variant="ghost"
          aria-label="Odhlásit se na mobilu"
          onClick={async () => {
            try {
              await api("auth/logout/", { method: "POST" });
              announceLogout();
              client.clear();
              forgetCsrf();
              client.setQueryData(["session"], null);
              navigate("/prihlaseni");
            } catch (e) {
              setError(errorText(e));
            }
          }}
        >
          <LogOut size={18} />
        </Button>
      </div>
    </div>
  );
}

function AdminOnly() {
  const { data } = useSession();
  return data?.system_role === "ADMIN" ? (
    <>
      <nav className="admin-mobile-tabs" aria-label="Administrace na mobilu">
        <NavLink to="/administrace/uzivatele">Uživatelé</NavLink>
        <NavLink to="/administrace/vozidla">Vozidla a sdílení</NavLink>
        <NavLink to="/administrace/audit">Audit</NavLink>
        <NavLink to="/administrace/system">Systém</NavLink>
      </nav>
      <Outlet />
    </>
  ) : (
    <Navigate to="/" replace />
  );
}

function LoginRoute() {
  const session = useSession();
  if (session.isPending) return <Loading />;
  return session.data ? (
    <Navigate
      to={session.data.must_change_password ? "/zmena-hesla" : "/"}
      replace
    />
  ) : (
    <Login />
  );
}

function PasswordRoute() {
  const session = useSession();
  if (session.isPending) return <Loading />;
  if (!session.data) return <Navigate to="/prihlaseni" replace />;
  return session.data.must_change_password ? (
    <ForcedPassword />
  ) : (
    <Navigate to="/" replace />
  );
}

function AuthEvents() {
  const client = useQueryClient();
  const navigate = useNavigate();
  const session = useSession();
  useEffect(() => {
    if (session.data === null)
      client.removeQueries({
        predicate: (query) => query.queryKey[0] !== "session",
      });
  }, [session.data, client]);
  useEffect(() => {
    if (!("BroadcastChannel" in window)) return;
    const channel = new BroadcastChannel("tanklog-session");
    channel.onmessage = (event) => {
      if (event.data === "logout") {
        client.clear();
        client.setQueryData(["session"], null);
        forgetCsrf();
        navigate("/prihlaseni", { replace: true });
      }
    };
    return () => channel.close();
  }, [client, navigate]);
  useEffect(() => {
    const restored = (event: PageTransitionEvent) => {
      if (event.persisted) {
        client.clear();
        window.location.reload();
      }
    };
    window.addEventListener("pageshow", restored);
    return () => window.removeEventListener("pageshow", restored);
  }, [client]);
  useEffect(() => {
    const expired = (event: Event) => {
      if ((event as CustomEvent).detail === "password_change_required") {
        void client.invalidateQueries({ queryKey: ["session"] });
        navigate("/zmena-hesla", { replace: true });
      } else {
        client.clear();
        client.setQueryData(["session"], null);
        navigate("/prihlaseni", { replace: true });
      }
    };
    window.addEventListener("tanklog:session", expired);
    return () => window.removeEventListener("tanklog:session", expired);
  }, [client, navigate]);
  return null;
}

export function App() {
  const session = useSession();
  return (
    <>
      <Theme
        value={
          session.data?.must_change_password ? undefined : session.data?.theme
        }
      />
      <AuthEvents />
      <PwaNotice />
      <RouteFocus />
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/prihlaseni" element={<LoginRoute />} />
          <Route path="/zmena-hesla" element={<PasswordRoute />} />
          <Route element={<Protected />}>
            <Route index element={<Overview />} />
            <Route path="nastaveni" element={<Profile />} />
            <Route path="tankovani" element={<Refuelings />} />
            <Route path="tankovani/nove" element={<RefuelingEditor />} />
            <Route path="tankovani/:id" element={<RefuelingDetail />} />
            <Route path="tankovani/:id/upravit" element={<RefuelingEditor />} />
            <Route path="auta" element={<Vehicles />} />
            <Route path="auta/:id/udalosti" element={<Events />} />
            <Route path="auta/:id/import" element={<ImportHistory />} />
            <Route path="pripominky" element={<Reminders />} />
            <Route path="offline" element={<Offline />} />
            <Route path="auta/nove" element={<VehicleEditor />} />
            <Route path="auta/:id" element={<VehicleDetail />} />
            <Route path="auta/:id/statistiky" element={<Overview />} />
            <Route path="auta/:id/intervaly" element={<Intervals />} />
            <Route
              path="auta/:id/intervaly/detail"
              element={<IntervalDetails />}
            />
            <Route path="auta/:id/upravit" element={<VehicleEditor />} />
            <Route element={<AdminOnly />}>
              <Route path="administrace/uzivatele" element={<Users />} />
              <Route path="administrace/vozidla" element={<Vehicles admin />} />
              <Route path="administrace/audit" element={<Audit />} />
              <Route path="administrace/system" element={<System />} />
            </Route>
            <Route
              path="*"
              element={
                <section className="panel">
                  <h1>Stránka nebyla nalezena</h1>
                  <Link to="/">Zpět na přehled</Link>
                </section>
              }
            />
          </Route>
        </Routes>
      </Suspense>
    </>
  );
}

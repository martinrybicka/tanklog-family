import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  Camera,
  ChevronDown,
  Home,
  LogOut,
  ReceiptText,
  Settings2,
  ShieldCheck,
} from "lucide-react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { api, errorText, forgetCsrf } from "../lib/api";
import { announceLogout } from "../lib/sessionEvents";
import { clearOutbox } from "../lib/outbox";
import { ErrorMessage } from "../components/ui";
import type { Session } from "../lib/types";
import "./family.css";

export function FamilyShell({ user }: { user: Session }) {
  const client = useQueryClient();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const name = user.display_name || user.username;
  return (
    <div className="family-app">
      <a href="#main-content" className="skip-link">
        Přejít k obsahu
      </a>
      <header className="family-header">
        <Link to="/" className="family-brand">
          <span>
            <ReceiptText size={23} strokeWidth={1.8} />
          </span>
          <strong>
            tanklog<span className="brand-dot">.</span>
          </strong>
          <small>méně starostí, více cest</small>
        </Link>
        <nav aria-label="Rodinná navigace" className="family-nav">
          <NavLink end to="/">
            <Home size={19} />
            Domů
          </NavLink>
          <NavLink to="/uctenka">
            <Camera size={19} />
            Přidat účtenku
          </NavLink>
          <NavLink to="/historie">
            <ReceiptText size={19} />
            Historie
          </NavLink>
        </nav>
        <details className="family-account">
          <summary>
            <span className="family-avatar">
              {name.slice(0, 1).toUpperCase()}
            </span>
            <span className="family-account-name">{name}</span>
            <ChevronDown size={15} />
          </summary>
          <div>
            <Link to="/profil">
              <Settings2 size={17} />
              Můj účet
            </Link>
            {user.system_role === "ADMIN" && (
              <Link to="/rodina">
                <ShieldCheck size={17} />
                Správa rodiny
              </Link>
            )}
            <button
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                setError("");
                try {
                  await api("auth/logout/", { method: "POST" });
                  clearOutbox();
                  announceLogout();
                  client.clear();
                  forgetCsrf();
                  client.setQueryData(["session"], null);
                  navigate("/prihlaseni", { replace: true });
                } catch (e) {
                  setError(errorText(e));
                } finally {
                  setBusy(false);
                }
              }}
            >
              <LogOut size={17} />
              Odhlásit se
            </button>
          </div>
        </details>
      </header>
      <main id="main-content" className="family-main" tabIndex={-1}>
        <ErrorMessage>{error}</ErrorMessage>
        <Outlet />
      </main>
      <footer className="family-footer">
        <span>TankLog · malý pomocník pro velké cesty</span>
        <span>
          <ShieldCheck size={14} />
          Vaše účtenky zůstávají u vás.
        </span>
      </footer>
    </div>
  );
}

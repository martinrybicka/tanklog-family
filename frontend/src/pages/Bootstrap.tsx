import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, ShieldCheck } from "lucide-react";
import { Navigate, useNavigate } from "react-router-dom";
import {
  Button,
  ErrorMessage,
  Field,
  Input,
  Loading,
  Logo,
} from "../components/ui";
import { api, errorText, refreshCsrf } from "../lib/api";
import type { Session } from "../lib/types";

export const setupStatus = () => api<{ available: boolean }>("auth/setup/");
export function Bootstrap() {
  const status = useQuery({ queryKey: ["installation"], queryFn: setupStatus });
  const client = useQueryClient();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (status.isPending) return <Loading />;
  if (status.error)
    return (
      <main className="standalone">
        <ErrorMessage>{errorText(status.error)}</ErrorMessage>
        <Button onClick={() => status.refetch()}>Zkusit znovu</Button>
      </main>
    );
  if (!status.data?.data.available)
    return <Navigate to="/prihlaseni" replace />;
  return (
    <div className="auth-layout">
      <section className="auth-story">
        <Logo />
        <div>
          <span className="eyebrow">VÍTEJTE DOMA</span>
          <h2>
            Vaše rodina.
            <br />
            Vaše auta.
            <br />
            <em>Začínáme.</em>
          </h2>
          <p>
            Vytvořte si vlastní účet správce. Potom připravíte auta a přístupy
            ostatním členům rodiny.
          </p>
        </div>
        <div className="auth-trust">
          <ShieldCheck size={20} />
          Čistá instalace bez ukázkových dat.
        </div>
      </section>
      <main className="auth-main">
        <div className="auth-form">
          <span className="icon-tile">
            <KeyRound size={24} />
          </span>
          <h1>První spuštění</h1>
          <p className="muted">
            Zvolte si přihlašovací údaje prvního administrátora. Tento krok lze
            provést pouze jednou.
          </p>
          <form
            onSubmit={async (event) => {
              event.preventDefault();
              setBusy(true);
              setError("");
              const values = new FormData(event.currentTarget);
              try {
                const result = await api<Session>("auth/setup/", {
                  method: "POST",
                  body: Object.fromEntries(values),
                });
                await refreshCsrf();
                client.clear();
                client.setQueryData(["session"], result.data);
                navigate("/", { replace: true });
              } catch (e) {
                setError(errorText(e));
              } finally {
                setBusy(false);
              }
            }}
          >
            <Field id="setup_token" label="Jednorázový instalační kód">
              <Input
                id="setup_token"
                name="setup_token"
                type="password"
                autoComplete="off"
                required
                maxLength={256}
              />
            </Field>
            <p className="muted">
              Kód najdete v Portaineru v prostředí stacku jako
              TANKLOG_SETUP_TOKEN. Nikdy není předvyplněný v aplikaci.
            </p>
            <Field id="setup_username" label="Uživatelské jméno správce">
              <Input
                id="setup_username"
                name="username"
                autoComplete="username"
                autoCapitalize="none"
                required
                maxLength={150}
              />
            </Field>
            <Field id="setup_name" label="Vaše jméno">
              <Input
                id="setup_name"
                name="display_name"
                autoComplete="name"
                maxLength={150}
              />
            </Field>
            <Field id="setup_password" label="Heslo správce">
              <Input
                id="setup_password"
                name="password"
                type="password"
                autoComplete="new-password"
                minLength={12}
                required
                maxLength={256}
              />
            </Field>
            <Field id="setup_confirm" label="Heslo znovu">
              <Input
                id="setup_confirm"
                name="password_confirmation"
                type="password"
                autoComplete="new-password"
                minLength={12}
                required
                maxLength={256}
              />
            </Field>
            <ErrorMessage>{error}</ErrorMessage>
            <Button className="w-full" disabled={busy}>
              {busy
                ? "Připravuji váš účet…"
                : "Vytvořit správce a přihlásit se"}
            </Button>
          </form>
        </div>
      </main>
    </div>
  );
}

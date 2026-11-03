import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Button, ErrorMessage } from "../components/ui";
import { clearOutbox } from "../lib/outbox";
import type { Session } from "../lib/types";
import { api, ApiError, errorText } from "../lib/api";
import { useSession } from "../lib/auth";
import { useOutbox, updatePending, discardPending } from "../lib/outbox";
export function Offline() {
  const entries = useOutbox();
  const session = useSession();
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  async function sync(key: string, confirm = false) {
    const item = entries.find((row) => row.key === key);
    if (!item || item.userId !== session.data?.id) return;
    setBusy(true);
    setMessage("");
    try {
      const current = (await api<Session>("auth/me/")).data;
      if (current.id !== item.userId) {
        clearOutbox();
        client.setQueryData(["session"], current);
        setMessage("Účet se změnil. Dočasná fronta byla zrušena.");
        return;
      }
      const body = {
        ...item.body,
        ...(confirm
          ? { confirmed_warning_codes: item.warnings.map((w) => w.code) }
          : {}),
      };
      await api("refuelings/", {
        method: "POST",
        body,
        headers: { "Idempotency-Key": key },
      });
      discardPending(key);
      await client.invalidateQueries({ queryKey: ["refuelings"] });
      await client.invalidateQueries({ queryKey: ["analytics"] });
      setMessage("Záznam byl uložen do databáze.");
    } catch (error) {
      if (
        error instanceof ApiError &&
        ["authentication_required", "password_change_required"].includes(
          error.code,
        )
      ) {
        clearOutbox();
        client.clear();
        client.setQueryData(["session"], null);
        return;
      }
      updatePending(key, {
        error: errorText(error),
        warnings: error instanceof ApiError ? error.warnings : [],
      });
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <h1>Neuložené offline zápisy</h1>
      <p>
        Fronta existuje jen v paměti tohoto okna. Reload, zavření nebo odhlášení
        ji zruší. Účtenky se do fronty neukládají. Synchronizaci spouštíte ručně
        po připojení.
      </p>
      <p role="status">
        {online ? "Připojení je dostupné." : "Jste offline."} {message}
      </p>
      {!entries.length && (
        <p>
          Žádné čekající zápisy.{" "}
          <Link to="/tankovani/nove">Nové tankování</Link>
        </p>
      )}
      {entries
        .filter((item) => item.userId === session.data?.id)
        .map((item) => (
          <section className="panel" key={item.key}>
            <h2>Neuložené tankování · {String(item.body.date)}</h2>
            {(
              ["date", "liters", "total_amount", "odometer_km", "note"] as const
            ).map((name) => (
              <label className="field" key={name}>
                {
                  {
                    date: "Datum",
                    liters: "Litry",
                    total_amount: "Částka",
                    odometer_km: "Tachometr",
                    note: "Poznámka",
                  }[name]
                }
                <input
                  className="input"
                  type={name === "date" ? "date" : "text"}
                  value={String(item.body[name] ?? "")}
                  onChange={(e) =>
                    updatePending(item.key, {
                      body: {
                        ...item.body,
                        [name]:
                          name === "odometer_km"
                            ? e.target.value
                              ? e.target.value
                              : null
                            : name === "date" || name === "note"
                              ? e.target.value
                              : e.target.value.replace(",", "."),
                      },
                      warnings: [],
                      error: "",
                    })
                  }
                />
              </label>
            ))}
            <ErrorMessage>{item.error}</ErrorMessage>
            {item.warnings.map((w) => (
              <p key={w.code}>{w.message}</p>
            ))}
            <div className="vehicle-actions">
              <Button disabled={busy || !online} onClick={() => sync(item.key)}>
                {busy ? "Synchronizace…" : "Uložit do databáze"}
              </Button>
              {item.warnings.length > 0 && (
                <Button
                  disabled={busy || !online}
                  onClick={() => sync(item.key, true)}
                >
                  Potvrdit uvedená upozornění a uložit
                </Button>
              )}
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() => discardPending(item.key)}
              >
                Zahodit neuložený zápis
              </Button>
            </div>
          </section>
        ))}
    </>
  );
}

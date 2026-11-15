import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound } from "lucide-react";
import { api, errorText } from "../lib/api";
import { ErrorMessage } from "../components/ui";

type Configuration = {
  configured: boolean;
  source: "database" | "environment" | "none";
};
export function IntegrationSettings() {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["rsv-settings"],
    queryFn: () => api<Configuration>("admin/integrations/rsv/"),
  });
  const [key, setKey] = useState("");
  const [vin, setVin] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  async function run(save: boolean) {
    setBusy(true);
    setMessage("");
    setError("");
    try {
      if (save) {
        await api("admin/integrations/rsv/", {
          method: "PUT",
          body: { api_key: key },
          etag: query.data?.etag ?? undefined,
        });
        setKey("");
        await client.invalidateQueries({ queryKey: ["rsv-settings"] });
        setMessage("Klíč byl bezpečně uložen. Nyní můžete otestovat spojení.");
      } else {
        const result = await api<{ message: string }>(
          "admin/integrations/rsv/test/",
          { method: "POST", body: { vin } },
        );
        setMessage(result.data.message);
      }
    } catch (e) {
      setError(errorText(e));
      await client.invalidateQueries({ queryKey: ["rsv-settings"] });
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="family-card family-admin-settings">
      <h2>
        <KeyRound size={20} /> Registr vozidel – dohledání VIN
      </h2>
      <p className="family-note">
        {query.data?.data.configured
          ? "API klíč je nastavený. Z bezpečnostních důvodů se nezobrazuje."
          : "Vložte API klíč z Registru silničních vozidel."}{" "}
        Nastavení platí pro celou rodinu a je dostupné pouze správci.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void run(true);
        }}
      >
        <label className="family-field">
          Nový API klíč RSV
          <input
            type="password"
            autoComplete="new-password"
            value={key}
            maxLength={256}
            disabled={busy}
            onChange={(e) => {
              setKey(e.target.value);
              setMessage("");
              setError("");
            }}
          />
        </label>
        <button
          className="family-primary"
          disabled={busy || !key.trim() || !query.data}
        >
          {busy ? "Pracuji…" : "Uložit API klíč"}
        </button>
      </form>
      <label className="family-field">
        VIN pro test spojení (nepovinné)
        <input
          value={vin}
          maxLength={17}
          disabled={busy}
          onChange={(e) => {
            setVin(e.target.value.toUpperCase());
            setMessage("");
            setError("");
          }}
        />
      </label>
      <p className="family-note">
        Bez vyplnění se použije veřejný vzorový VIN. Test odešle VIN pouze
        registru a nevytvoří ani nezmění žádné auto. Nový klíč nejprve uložte.
      </p>
      <button
        type="button"
        className="family-secondary"
        disabled={busy || !!key || !query.data?.data.configured}
        onClick={() => void run(false)}
      >
        {busy ? "Pracuji…" : "Otestovat spojení"}
      </button>
      <ErrorMessage>
        {error || (query.error && errorText(query.error))}
      </ErrorMessage>
      <p role="status">{message}</p>
    </section>
  );
}

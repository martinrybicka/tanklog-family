import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Camera,
  CarFront,
  Check,
  CheckCheck,
  ChevronDown,
  ImagePlus,
  LoaderCircle,
  PencilLine,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { api, ApiError, errorText } from "../lib/api";
import { ErrorMessage, Loading } from "../components/ui";
import type { Refueling } from "../lib/types";
import { decimalText } from "../features/analytics/format";
import { familyCars, today, type Draft } from "./api";

type Form = {
  date: string;
  liters: string;
  total_amount: string;
  odometer_km: string;
  station_code: string;
  note: string;
  is_full_tank: boolean;
};
const emptyForm = (): Form => ({
  date: today(),
  liters: "",
  total_amount: "",
  odometer_km: "",
  station_code: "",
  note: "",
  is_full_tank: false,
});
export function ReceiptWizard() {
  const [params] = useSearchParams();
  const id = params.get("draft");
  const cars = useQuery({
    queryKey: ["vehicles", "family"],
    queryFn: familyCars,
  });
  const preference = useQuery({
    queryKey: ["family-preference"],
    queryFn: () =>
      api<{ default_vehicle_id: string | null }>("family/settings/"),
  });
  const pending = useQuery({
    queryKey: ["family-draft", id],
    enabled: !!id,
    queryFn: () => api<Draft>(`family/receipts/${id}/`),
  });
  const [selectedVehicle, setVehicle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [draft, setDraft] = useState<Awaited<
    ReturnType<typeof api<Draft>>
  > | null>(null);
  const [form, setForm] = useState<Form>(emptyForm);
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [warnings, setWarnings] = useState<{ code: string; message: string }[]>(
    [],
  );
  const [saved, setSaved] = useState<Refueling | null>(null);
  const [uploadKey, setUploadKey] = useState(() => crypto.randomUUID());
  const [manualKey] = useState(() => crypto.randomUUID());
  const loaded = useRef<string | null>(null);
  const client = useQueryClient();
  const eligible =
    cars.data?.filter((car) => car.permissions.create_refueling) ?? [];
  const preferred = eligible.find(
    (car) => car.id === preference.data?.data.default_vehicle_id,
  )?.id;
  const vehicle =
    selectedVehicle ||
    preferred ||
    (eligible.length === 1 ? eligible[0].id : "");
  const car = cars.data?.find((car) => car.id === vehicle);

  function apply(result: Awaited<ReturnType<typeof api<Draft>>>) {
    setDraft(result);
    setVehicle(result.data.vehicle_id);
    const next = emptyForm();
    for (const key of [
      "date",
      "liters",
      "total_amount",
      "odometer_km",
      "station_code",
    ] as const) {
      if (result.data.suggestions[key])
        next[key] = String(result.data.suggestions[key].value);
    }
    setForm(next);
    setWarnings([]);
    setStep(result.data.result_id ? 3 : 2);
  }
  useEffect(() => {
    if (pending.data && loaded.current !== pending.data.data.id) {
      loaded.current = pending.data.data.id;
      apply(pending.data);
    }
  }, [pending.data]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (step === 2 && (form.liters || form.total_amount)) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [step, form.liters, form.total_amount]);
  function chooseFile(selected: File | null) {
    setError("");
    if (selected && selected.size > 10 * 1024 ** 2) {
      setError("Účtenka smí mít nejvýše 10 MiB.");
      setFile(null);
      return;
    }
    setFile(selected);
    setUploadKey(crypto.randomUUID());
  }
  function change<K extends keyof Form>(name: K, value: Form[K]) {
    setForm((current) => ({ ...current, [name]: value }));
    setWarnings([]);
    setError("");
  }
  async function read() {
    if (!file || !vehicle) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const data = new FormData();
      data.set("file", file);
      data.set("vehicle_id", vehicle);
      const uploaded = await api<Draft>("family/receipts/", {
        method: "POST",
        body: data,
        headers: { "Idempotency-Key": uploadKey },
      });
      setDraft(uploaded);
      await client.invalidateQueries({ queryKey: ["family-drafts"] });
      try {
        apply(
          await api<Draft>(`family/receipts/${uploaded.data.id}/recognize/`, {
            method: "POST",
            body: {},
            etag: uploaded.etag!,
          }),
        );
      } catch (e) {
        apply(uploaded);
        setNotice(
          `Fotka je uložená. Automatické čtení se nepodařilo: ${errorText(e)} Údaje můžete doplnit ručně.`,
        );
      }
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  async function save(confirm = false) {
    if (!vehicle) return;
    setBusy(true);
    setError("");
    try {
      const body = {
        vehicle_id: vehicle,
        date: form.date,
        liters: form.liters.replace(",", "."),
        total_amount: form.total_amount.replace(",", "."),
        odometer_km: form.odometer_km || null,
        is_full_tank: form.is_full_tank,
        station_code: form.station_code,
        note: form.note,
        ...(confirm
          ? { confirmed_warning_codes: warnings.map((w) => w.code) }
          : {}),
      };
      const result = draft
        ? await api<Refueling>(`family/receipts/${draft.data.id}/complete/`, {
            method: "POST",
            body,
            etag: draft.etag!,
          })
        : await api<Refueling>("refuelings/", {
            method: "POST",
            body,
            headers: { "Idempotency-Key": manualKey },
          });
      setSaved(result.data);
      setStep(3);
      setWarnings([]);
      await Promise.all(
        ["refuelings", "analytics", "family-drafts"].map((key) =>
          client.invalidateQueries({ queryKey: [key] }),
        ),
      );
    } catch (e) {
      setError(errorText(e));
      if (e instanceof ApiError) setWarnings(e.warnings);
    } finally {
      setBusy(false);
    }
  }
  if (cars.isPending || (id && pending.isPending)) return <Loading />;
  const canCreate = !!eligible.length;
  return (
    <div className="family-wizard">
      <Link className="family-back" to="/">
        <ArrowLeft size={17} />
        Zpět domů
      </Link>
      <ol className="family-steps" aria-label="Postup přidání účtenky">
        {["Účtenka", "Kontrola", "Hotovo"].map((label, index) => (
          <li
            key={label}
            className={step >= index + 1 ? "is-current" : ""}
            aria-current={step === index + 1 ? "step" : undefined}
          >
            <span>{step > index + 1 ? <Check size={15} /> : index + 1}</span>
            {label}
          </li>
        ))}
      </ol>
      <ErrorMessage>{cars.error && errorText(cars.error)}</ErrorMessage>
      <ErrorMessage>{pending.error && errorText(pending.error)}</ErrorMessage>
      <ErrorMessage>
        {preference.error && errorText(preference.error)}
      </ErrorMessage>
      {step === 1 && (
        <section className="family-card family-upload">
          <span className="family-large-icon">
            <Camera size={31} />
          </span>
          <h1>Jedna fotka. A máte přehled.</h1>
          <p>
            Vyberte účtenku a nechte nás přečíst údaje.
            <br />
            Před uložením je společně zkontrolujeme.
          </p>
          {!canCreate ? (
            <div className="family-empty">
              <CarFront size={34} />
              <h2>Nejdřív vám připravíme auto</h2>
              <p>
                Požádejte správce o auto s právem přidávat tankování. Pro
                elektřinu a CNG použijte evidenci energie.
              </p>
            </div>
          ) : (
            <>
              {eligible.length > 1 ? (
                <label className="family-field family-vehicle-select">
                  Pro které auto?
                  <select
                    disabled={busy}
                    value={vehicle}
                    onChange={(e) => setVehicle(e.target.value)}
                    required
                  >
                    <option value="">Vyberte auto</option>
                    {eligible.map((car) => (
                      <option value={car.id} key={car.id}>
                        {car.name}
                      </option>
                    ))}
                  </select>
                </label>
              ) : (
                <div className="family-selected-car">
                  <CarFront size={21} />
                  <span>{eligible[0].name}</span>
                  <Check size={16} />
                </div>
              )}
              <label className={`family-dropzone ${file ? "has-file" : ""}`}>
                <input
                  type="file"
                  accept="image/jpeg,image/png"
                  capture="environment"
                  disabled={busy}
                  aria-label="Vyfotit účtenku JPG nebo PNG nejvýše 10 MB"
                  onChange={(e) => chooseFile(e.target.files?.[0] ?? null)}
                />
                <span>
                  <ImagePlus size={32} />
                </span>
                <strong>{file ? file.name : "Vyfotit účtenku"}</strong>
                <small>JPG nebo PNG · nejvýše 10 MB</small>
              </label>
              <label className="family-file-library">
                <ImagePlus size={16} />
                <span>Nebo vybrat fotku ze zařízení</span>
                <input
                  type="file"
                  accept="image/jpeg,image/png"
                  aria-label="Vybrat fotku ze zařízení"
                  disabled={busy}
                  onChange={(e) => chooseFile(e.target.files?.[0] ?? null)}
                />
              </label>
              <ErrorMessage>{error}</ErrorMessage>
              <button
                className="family-primary"
                disabled={busy || !file || !vehicle}
                onClick={read}
              >
                {busy ? (
                  <LoaderCircle className="spin" size={20} />
                ) : (
                  <Sparkles size={20} />
                )}{" "}
                {busy ? "Čtu vaši účtenku…" : "Přečíst účtenku"}
                {!busy && <ArrowRight size={18} />}
              </button>
              <button
                className="family-text-button"
                disabled={busy || !vehicle}
                onClick={() => {
                  setStep(2);
                  setNotice("");
                }}
              >
                <PencilLine size={17} />
                Nemám účtenku, doplním ručně
              </button>
            </>
          )}
          <div className="family-private-note">
            <ShieldCheck size={15} />
            Fotografie zůstává soukromá. Čtení probíhá lokálně.
          </div>
        </section>
      )}
      {step === 2 && (
        <>
          <div className="family-review-heading">
            <span className="family-eyebrow">POSLEDNÍ DROBNOST</span>
            <h1>Vypadá všechno správně?</h1>
            <p>
              {draft
                ? "Přečtené údaje jsou návrh. Zkontrolujte je podle účtenky."
                : "Stačí datum, litry a zaplacená částka."}
            </p>
          </div>
          <div
            className={`family-review-grid ${!draft ? "without-photo" : ""}`}
          >
            {draft && (
              <aside className="family-card family-receipt-preview">
                <div>
                  <ReceiptTextIcon />
                  Vaše účtenka
                </div>
                <img
                  src={draft.data.preview_url}
                  alt="Náhled vaší nahrané účtenky"
                />
                <small>Originál zůstane uložený spolu s tankováním.</small>
                <button
                  className="family-text-button"
                  disabled={busy}
                  onClick={async () => {
                    setBusy(true);
                    setError("");
                    try {
                      apply(
                        await api<Draft>(
                          `family/receipts/${draft.data.id}/recognize/`,
                          { method: "POST", body: {}, etag: draft.etag! },
                        ),
                      );
                      setNotice("");
                    } catch (e) {
                      setError(errorText(e));
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  <RotateCcw size={16} />
                  Přečíst znovu
                </button>
              </aside>
            )}
            <form
              className="family-card family-check-form"
              onSubmit={(e) => {
                e.preventDefault();
                void save();
              }}
            >
              <div className="family-selected-car">
                <CarFront size={21} />
                <span>{car?.name ?? "Vybrané auto"}</span>
                <Check size={16} />
              </div>
              {notice && (
                <p className="family-notice" role="status">
                  {notice}
                </p>
              )}
              {draft && Object.keys(draft.data.suggestions).length > 0 && (
                <p className="family-scan-status">
                  <Sparkles size={16} />
                  Údaje načteny. Vy máte poslední slovo.
                </p>
              )}
              <label className="family-field">
                Datum tankování
                <input
                  required
                  type="date"
                  max={today()}
                  value={form.date}
                  disabled={busy}
                  onChange={(e) => change("date", e.target.value)}
                />
              </label>
              <div className="family-form-pair">
                <label className="family-field">
                  Natankováno (l)
                  <input
                    required
                    inputMode="decimal"
                    placeholder="např. 42,5"
                    value={form.liters}
                    disabled={busy}
                    onChange={(e) => change("liters", e.target.value)}
                  />
                </label>
                <label className="family-field">
                  Zaplaceno (Kč)
                  <input
                    required
                    inputMode="decimal"
                    placeholder="např. 1 650"
                    value={form.total_amount}
                    disabled={busy}
                    onChange={(e) =>
                      change("total_amount", e.target.value.replace(/\s/g, ""))
                    }
                  />
                </label>
              </div>
              <label className="family-field">
                Tachometr (km)
                <input
                  inputMode="numeric"
                  placeholder="Nepovinné, pomůže se spotřebou"
                  value={form.odometer_km}
                  disabled={busy}
                  onChange={(e) => change("odometer_km", e.target.value)}
                />
              </label>
              <label className="family-checkbox">
                <input
                  type="checkbox"
                  checked={form.is_full_tank}
                  disabled={busy}
                  onChange={(e) => change("is_full_tank", e.target.checked)}
                />
                <span>
                  Natankováno do plné
                  <small>Zaškrtněte jen při skutečně plné nádrži.</small>
                </span>
              </label>
              <details className="family-extra">
                <summary>
                  Stanice a poznámka
                  <ChevronDown size={15} />
                </summary>
                <label className="family-field">
                  Čerpací stanice
                  <select
                    value={form.station_code}
                    disabled={busy}
                    onChange={(e) => change("station_code", e.target.value)}
                  >
                    {[
                      "",
                      "ORLEN",
                      "SHELL",
                      "MOL",
                      "OMV",
                      "EUROOIL",
                      "TANK_ONO",
                      "OTHER",
                    ].map((code) => (
                      <option value={code} key={code}>
                        {code || "Nevybráno"}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="family-field">
                  Poznámka
                  <textarea
                    aria-label="Poznámka"
                    maxLength={2000}
                    disabled={busy}
                    value={form.note}
                    onChange={(e) => change("note", e.target.value)}
                  />
                </label>
              </details>
              <ErrorMessage>{error}</ErrorMessage>
              {warnings.length > 0 && (
                <div className="family-warning">
                  <strong>Ještě prosím zkontrolujte</strong>
                  {warnings.map((w) => (
                    <p key={w.code}>{w.message}</p>
                  ))}
                  <button
                    type="button"
                    className="family-primary"
                    disabled={busy}
                    onClick={() => save(true)}
                  >
                    Rozumím, přesto uložit
                    <Check size={18} />
                  </button>
                </div>
              )}
              <button
                className="family-primary"
                type="submit"
                disabled={busy || !vehicle}
              >
                {busy ? (
                  <LoaderCircle className="spin" size={19} />
                ) : (
                  <CheckCheck size={20} />
                )}{" "}
                {busy ? "Ukládání…" : "Potvrdit a uložit"}
              </button>
              <p className="family-form-hint">
                Částku z účtenky zachováme přesně tak, jak ji zadáte.
              </p>
            </form>
          </div>
        </>
      )}
      {step === 3 && (
        <section className="family-card family-success">
          <span>
            <CheckCheck size={42} />
          </span>
          <span className="family-eyebrow">O JEDNU STAROST MÉNĚ</span>
          <h1>Hotovo. Šťastnou cestu!</h1>
          <p>
            Tankování{draft ? " i účtenka jsou uložené" : " je uložené"} a
            najdete je v historii.
          </p>
          {saved && (
            <div className="family-success-amount">
              {decimalText(saved.total_amount)} <small>Kč</small>
            </div>
          )}
          <Link className="family-primary" to="/">
            Zpět domů
            <ArrowRight size={18} />
          </Link>
          <Link
            className="family-text-button"
            to={`/historie/${saved?.id || draft?.data.result_id || ""}`}
          >
            Prohlédnout tankování
          </Link>
        </section>
      )}
      {step !== 3 && (
        <Link to="/" className="family-wizard-close">
          <X size={15} />
          Dokončit později{draft ? " — fotka už je uložená" : ""}
        </Link>
      )}
    </div>
  );
}
function ReceiptTextIcon() {
  return <Camera size={17} />;
}

import { useEffect, useState } from "react";
import { Button, Modal } from "./ui";
interface InstallPrompt extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: string }>;
}
let installer: InstallPrompt | null = null;
let waiting: ServiceWorker | null = null;
export function PwaNotice() {
  const [online, setOnline] = useState(navigator.onLine);
  const [update, setUpdate] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const changed = () => setOnline(navigator.onLine);
    const install = (event: Event) => {
      event.preventDefault();
      installer = event as InstallPrompt;
      window.dispatchEvent(new Event("tanklog:install"));
    };
    const installed = () => {
      installer = null;
      window.dispatchEvent(new Event("tanklog:install"));
    };
    window.addEventListener("online", changed);
    window.addEventListener("offline", changed);
    window.addEventListener("beforeinstallprompt", install);
    window.addEventListener("appinstalled", installed);
    if (import.meta.env.PROD && "serviceWorker" in navigator) {
      navigator.serviceWorker
        .register("/sw.js", { scope: "/", updateViaCache: "none" })
        .then((registration) => {
          const inspect = () => {
            if (registration.waiting && navigator.serviceWorker.controller) {
              waiting = registration.waiting;
              setUpdate(true);
            }
          };
          inspect();
          registration.addEventListener("updatefound", () =>
            registration.installing?.addEventListener("statechange", inspect),
          );
        })
        .catch(() => setFailed(true));
    }
    return () => {
      window.removeEventListener("online", changed);
      window.removeEventListener("offline", changed);
      window.removeEventListener("beforeinstallprompt", install);
      window.removeEventListener("appinstalled", installed);
    };
  }, []);
  return (
    <>
      {!online && (
        <div role="status" className="connection-notice">
          Chybí připojení. Zápisy vyžadují server; rozepsaný formulář zůstává
          jen v tomto okně. Před opakováním ověřte výsledek v historii.
        </div>
      )}
      {failed && (
        <div role="status" className="connection-notice">
          Instalovatelný režim se nepodařilo připravit. Aplikaci můžete dál
          používat online.
        </div>
      )}
      {update && (
        <div className="connection-notice" role="status">
          Je připravená nová verze rozhraní.{" "}
          <Button variant="secondary" onClick={() => setConfirm(true)}>
            Načíst novou verzi
          </Button>
        </div>
      )}
      <Modal
        open={confirm}
        onClose={() => setConfirm(false)}
        title="Načíst novou verzi?"
        description="Nejprve uložte nebo zkontrolujte rozpracované údaje. Obnovení stránky odstraní neuložený formulář."
      >
        <Button
          onClick={() => {
            navigator.serviceWorker.addEventListener(
              "controllerchange",
              () => window.location.reload(),
              { once: true },
            );
            waiting?.postMessage("ACTIVATE_UPDATE");
          }}
        >
          Obnovit aplikaci
        </Button>
      </Modal>
    </>
  );
}
export function PwaSettings() {
  const [available, setAvailable] = useState(!!installer);
  const [error, setError] = useState("");
  useEffect(() => {
    const update = () => setAvailable(!!installer);
    window.addEventListener("tanklog:install", update);
    return () => window.removeEventListener("tanklog:install", update);
  }, []);
  return (
    <section className="panel pwa-settings">
      <h2>Aplikace v zařízení</h2>
      <p>
        TankLog lze přidat na plochu přes nabídku prohlížeče, pokud to zařízení
        podporuje. Přihlášení, údaje i tankování vyžadují připojení k serveru.
      </p>
      {available && (
        <Button
          onClick={async () => {
            try {
              await installer?.prompt();
              await installer?.userChoice;
              installer = null;
              setAvailable(false);
            } catch {
              setError(
                "Instalace se nezdařila. Použijte nabídku prohlížeče nebo pokračujte online.",
              );
            }
          }}
        >
          Nainstalovat TankLog
        </Button>
      )}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}

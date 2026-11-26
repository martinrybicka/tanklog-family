import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { Button, Modal } from "./ui";
interface InstallPrompt extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: string }>;
}
let installer: InstallPrompt | null = null;
let installedInPage = false;
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
      installedInPage = true;
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
function installHelp() {
  const agent = navigator.userAgent;
  if (
    /iPhone|iPad|iPod/i.test(agent) ||
    (/Macintosh/i.test(agent) && navigator.maxTouchPoints > 1)
  ) {
    return "V Safari otevřete Sdílet → Přidat na plochu. Pokud se zobrazí volba Otevřít jako webovou aplikaci, zapněte ji a klepněte na Přidat.";
  }
  if (/Macintosh.*Safari/i.test(agent) && !/Chrome|Chromium|Edg/i.test(agent)) {
    return "V Safari otevřete Sdílet → Přidat do Docku a potvrďte tlačítkem Přidat.";
  }
  return "V nabídce prohlížeče vyhledejte volbu Nainstalovat aplikaci nebo Přidat na plochu. Pokud ji prohlížeč nenabízí, otevřete TankLog v Chrome, Edge nebo Safari.";
}

function runningAsApp() {
  return (
    installedInPage ||
    window.matchMedia("(display-mode: standalone)").matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}

export function PwaInstallButton({ className }: { className?: string }) {
  const [hidden, setHidden] = useState(runningAsApp);
  const [showHelp, setShowHelp] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const mode = window.matchMedia("(display-mode: standalone)");
    const update = () => {
      const standalone = runningAsApp();
      setHidden(standalone);
      if (standalone) setShowHelp(false);
    };
    window.addEventListener("tanklog:install", update);
    mode.addEventListener("change", update);
    update();
    return () => {
      window.removeEventListener("tanklog:install", update);
      mode.removeEventListener("change", update);
    };
  }, []);

  if (hidden) return null;
  return (
    <>
      <Button
        type="button"
        variant="secondary"
        className={className}
        disabled={busy}
        onClick={async () => {
          const request = installer;
          if (!request) {
            setShowHelp(true);
            return;
          }
          // Prohlížeč dovoluje použít jednu instalační výzvu jen jednou.
          installer = null;
          setBusy(true);
          try {
            await request.prompt();
            if ((await request.userChoice).outcome === "accepted") {
              installedInPage = true;
              window.dispatchEvent(new Event("tanklog:install"));
            }
          } catch {
            setShowHelp(true);
          } finally {
            setBusy(false);
          }
        }}
      >
        <Download size={17} aria-hidden="true" />
        Nainstalovat aplikaci
      </Button>
      <Modal
        open={showHelp}
        onClose={() => setShowHelp(false)}
        title="Nainstalovat TankLog"
        description={installHelp()}
      >
        <Button type="button" onClick={() => setShowHelp(false)}>
          Rozumím
        </Button>
      </Modal>
    </>
  );
}

export function PwaSettings() {
  return (
    <section className="panel pwa-settings">
      <h2>Aplikace v zařízení</h2>
      <p>Přihlášení, údaje i tankování vyžadují připojení k serveru.</p>
      <PwaInstallButton />
    </section>
  );
}

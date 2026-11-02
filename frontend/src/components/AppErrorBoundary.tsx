import { Component, type ReactNode } from "react";
import { Button } from "./ui";
export class AppErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <main className="standalone">
        <section className="panel">
          <h1>Rozhraní se nepodařilo načíst</h1>
          <p>
            Uložená data zůstávají na serveru. Zkontrolujte připojení a obnovte
            stránku. Neuložený formulář se obnovením ztratí.
          </p>
          <Button onClick={() => window.location.reload()}>
            Obnovit stránku
          </Button>
        </section>
      </main>
    ) : (
      this.props.children
    );
  }
}

import { useState } from "react";
import { Button, ErrorMessage } from "../../components/ui";
import { api, errorText } from "../../lib/api";
import { Suggestions, type Suggestion } from "./Suggestions";
type Extraction = {
  id: string;
  stale: boolean;
  engine: string;
  raw_text: string;
  suggestions: Record<string, Suggestion>;
};
export function OcrPanel({
  itemId,
  onApply,
}: {
  itemId: string;
  onApply: (values: Record<string, string | number>, id: string) => void;
}) {
  const [result, setResult] = useState<Extraction | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <section className="extension-block">
      <h2>Rozpoznat uloženou účtenku</h2>
      <p>
        OCR běží lokálně. Nejisté návrhy zkontrolujte; změny se zapíší až běžným
        uložením formuláře.
      </p>
      <Button
        type="button"
        variant="secondary"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          setError("");
          setResult(null);
          try {
            const item = await api(`refuelings/${itemId}/`);
            setResult(
              (
                await api<Extraction>(`refuelings/${itemId}/recognize/`, {
                  method: "POST",
                  body: {},
                  etag: item.etag!,
                })
              ).data,
            );
          } catch (e) {
            setError(errorText(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? "Rozpoznávání…" : "Rozpoznat účtenku"}
      </Button>
      <Button
        type="button"
        variant="secondary"
        onClick={async () => {
          setError("");
          try {
            const value = (
              await api<Extraction>(`refuelings/${itemId}/recognize/`)
            ).data;
            setResult(value);
            if (value.stale)
              setError(
                "Uložený výsledek patří starší verzi účtenky. Spusťte OCR znovu.",
              );
          } catch (e) {
            setError(errorText(e));
          }
        }}
      >
        Načíst uložený výsledek OCR
      </Button>
      <ErrorMessage>{error}</ErrorMessage>
      {result && (
        <>
          <p>{result.engine}</p>
          {!Object.keys(result.suggestions).length && (
            <p>
              Rozpoznání neposkytlo jednoznačné hodnoty. Vyplňte údaje ručně.
            </p>
          )}
          <Suggestions
            values={result.stale ? {} : result.suggestions}
            onApply={async (values) => {
              try {
                const current = (
                  await api<Extraction>(
                    `refuelings/${itemId}/extractions/${result.id}/`,
                  )
                ).data;
                if (current.stale) {
                  setError("Účtenka se změnila. Spusťte rozpoznání znovu.");
                  return;
                }
                onApply(values, result.id);
              } catch (e) {
                setError(errorText(e));
              }
            }}
          />
          <details>
            <summary>Rozpoznaný text</summary>
            <pre className="ocr-text">{result.raw_text}</pre>
          </details>
        </>
      )}
    </section>
  );
}

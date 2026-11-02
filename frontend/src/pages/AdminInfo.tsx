import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Button, ErrorMessage, Input, Loading } from "../components/ui";
import { api, errorText } from "../lib/api";
import type { AuditEvent, Page } from "../lib/types";

export function System() {
  const result = useQuery({
    queryKey: ["system"],
    queryFn: () =>
      api<{
        application: string;
        version: string;
        phase: number;
        django_version: string;
        database: string;
      }>("admin/system/"),
  });
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">ADMINISTRACE</span>
          <h1>Stav systému</h1>
          <p className="muted">
            Základní provozní informace bez citlivé konfigurace.
          </p>
        </div>
      </div>
      <section className="panel">
        {result.isPending ? (
          <Loading />
        ) : result.error ? (
          <ErrorMessage>{errorText(result.error)}</ErrorMessage>
        ) : (
          <dl className="system-list">
            <dt>Aplikace</dt>
            <dd>{result.data.data.application}</dd>
            <dt>Verze</dt>
            <dd>{result.data.data.version}</dd>
            <dt>Aktuální etapa</dt>
            <dd>Fáze {result.data.data.phase}</dd>
            <dt>Django</dt>
            <dd>{result.data.data.django_version}</dd>
            <dt>Databáze</dt>
            <dd>
              <span className="status-dot">
                {result.data.data.database === "ok" ? "Dostupná" : "Nedostupná"}
              </span>
            </dd>
          </dl>
        )}
      </section>
    </>
  );
}

export function Audit() {
  const [page, setPage] = useState(1);
  const [action, setAction] = useState("");
  const params = new URLSearchParams({
    page: String(page),
    ...(action ? { action } : {}),
  });
  const result = useQuery({
    queryKey: ["audit", page, action],
    queryFn: () => api<Page<AuditEvent>>(`admin/audit/?${params}`),
  });
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">ADMINISTRACE</span>
          <h1>Auditní historie</h1>
          <p className="muted">
            Dohledatelné změny účtů a události zabezpečení.
          </p>
        </div>
      </div>
      <section className="panel">
        <Input
          className="audit-filter"
          aria-label="Filtr akce auditu"
          placeholder="Kód akce, např. user.created"
          value={action}
          onChange={(e) => {
            setAction(e.target.value);
            setPage(1);
          }}
        />
        {result.isPending ? (
          <Loading />
        ) : result.error ? (
          <ErrorMessage>{errorText(result.error)}</ErrorMessage>
        ) : (
          <>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Čas</th>
                    <th>Uživatel</th>
                    <th>Akce</th>
                    <th>Změny</th>
                  </tr>
                </thead>
                <tbody>
                  {result.data.data.results.map((event) => (
                    <tr key={event.id}>
                      <td>
                        {new Date(event.occurred_at).toLocaleString("cs-CZ", {
                          timeZone: "Europe/Prague",
                        })}
                      </td>
                      <td>{event.actor_name || "Nepřihlášený / systém"}</td>
                      <td>
                        <code>{event.action}</code>
                      </td>
                      <td>
                        <code className="audit-change">
                          {Object.keys(event.changes).length
                            ? JSON.stringify(event.changes)
                            : "—"}
                        </code>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!result.data.data.count && (
                <p className="empty-state">
                  Žádné události neodpovídají filtru.
                </p>
              )}
            </div>
            <div className="pagination">
              <span>{result.data.data.count} událostí</span>
              <div>
                <Button
                  variant="ghost"
                  disabled={page === 1}
                  onClick={() => setPage(page - 1)}
                >
                  Předchozí
                </Button>
                <span>{page}</span>
                <Button
                  variant="ghost"
                  disabled={!result.data.data.next}
                  onClick={() => setPage(page + 1)}
                >
                  Další
                </Button>
              </div>
            </div>
          </>
        )}
      </section>
    </>
  );
}

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Copy,
  KeyRound,
  Pencil,
  Plus,
  Search,
  ShieldCheck,
  UserRound,
  UsersRound,
} from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import {
  Button,
  ErrorMessage,
  Field,
  Input,
  Loading,
  Modal,
} from "../components/ui";
import { api, errorText, userETag } from "../lib/api";
import type { Page, TemporaryPassword, User } from "../lib/types";

const schema = z.object({
  username: z
    .string()
    .min(1, "Vyplňte uživatelské jméno.")
    .max(150)
    .regex(
      /^[a-zA-Z0-9_.@+-]+$/,
      "Použijte písmena bez diakritiky, číslice nebo . @ + - _.",
    ),
  display_name: z.string().max(150),
  email: z.union([z.email("Zadejte platný e-mail."), z.literal("")]),
  system_role: z.enum(["USER", "ADMIN"]),
  current_password: z
    .string()
    .min(1, "Potvrďte akci svým aktuálním heslem.")
    .max(256),
});
type Action = "edit" | "password-reset" | "activate" | "deactivate";

function UserEditor({
  user,
  onClose,
  onTemporary,
}: {
  user?: User;
  onClose: () => void;
  onTemporary: (value: TemporaryPassword) => void;
}) {
  const client = useQueryClient();
  const [error, setError] = useState("");
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: {
      username: user?.username || "",
      display_name: user?.display_name || "",
      email: user?.email || "",
      system_role: user?.system_role || "USER",
      current_password: "",
    },
  });
  return (
    <form
      className="modal-form"
      onSubmit={handleSubmit(async (data) => {
        setError("");
        try {
          if (user) {
            const { username: _username, ...body } = data;
            await api(`admin/users/${user.id}/`, {
              method: "PATCH",
              body,
              etag: userETag(user),
            });
          } else {
            const result = await api<TemporaryPassword>("admin/users/", {
              method: "POST",
              body: data,
            });
            onTemporary(result.data);
          }
          await client.invalidateQueries({ queryKey: ["users"] });
          onClose();
        } catch (e) {
          setError(errorText(e));
        }
      })}
      noValidate
    >
      <Field
        id="edit-username"
        label="Uživatelské jméno"
        error={errors.username?.message}
      >
        <Input
          id="edit-username"
          readOnly={!!user}
          autoCapitalize="none"
          autoComplete="off"
          {...register("username")}
        />
      </Field>
      <Field id="edit-name" label="Zobrazované jméno">
        <Input id="edit-name" {...register("display_name")} />
      </Field>
      <Field
        id="edit-email"
        label="Kontaktní e-mail"
        error={errors.email?.message}
      >
        <Input id="edit-email" type="email" {...register("email")} />
      </Field>
      <Field id="edit-role" label="Systémová role">
        <select id="edit-role" className="input" {...register("system_role")}>
          <option value="USER">Uživatel</option>
          <option value="ADMIN">Administrátor</option>
        </select>
      </Field>
      <Field
        id="admin-password"
        label="Vaše aktuální heslo"
        hint="Potvrzení citlivé administrační operace."
        error={errors.current_password?.message}
      >
        <Input
          id="admin-password"
          type="password"
          autoComplete="current-password"
          {...register("current_password")}
        />
      </Field>
      <ErrorMessage>{error}</ErrorMessage>
      <div className="form-actions">
        <Button variant="secondary" type="button" onClick={onClose}>
          Zrušit
        </Button>
        <Button disabled={isSubmitting} type="submit">
          {isSubmitting ? "Ukládání…" : user ? "Uložit změny" : "Vytvořit účet"}
        </Button>
      </div>
    </form>
  );
}

function ActionForm({
  user,
  action,
  onClose,
  onTemporary,
}: {
  user: User;
  action: Exclude<Action, "edit">;
  onClose: () => void;
  onTemporary: (value: TemporaryPassword) => void;
}) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const client = useQueryClient();
  return (
    <form
      className="modal-form"
      onSubmit={async (event) => {
        event.preventDefault();
        setError("");
        setBusy(true);
        try {
          const result = await api<TemporaryPassword>(
            `admin/users/${user.id}/${action}/`,
            {
              method: "POST",
              body: { current_password: password },
              etag: userETag(user),
            },
          );
          if (action === "password-reset") onTemporary(result.data);
          await client.invalidateQueries({ queryKey: ["users"] });
          onClose();
        } catch (e) {
          setError(errorText(e));
        } finally {
          setBusy(false);
        }
      }}
    >
      <p>
        Účet: <strong>{user.username}</strong>
      </p>
      <Field id="confirm-admin-password" label="Vaše aktuální heslo">
        <Input
          id="confirm-admin-password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </Field>
      <ErrorMessage>{error}</ErrorMessage>
      <div className="form-actions">
        <Button variant="secondary" type="button" onClick={onClose}>
          Zrušit
        </Button>
        <Button
          disabled={busy}
          variant={action === "deactivate" ? "danger" : "default"}
          type="submit"
        >
          {busy
            ? "Zpracování…"
            : action === "password-reset"
              ? "Vydat dočasné heslo"
              : action === "activate"
                ? "Aktivovat účet"
                : "Deaktivovat účet"}
        </Button>
      </div>
    </form>
  );
}

const actionLabels = {
  edit: "Upravit uživatele",
  "password-reset": "Resetovat heslo",
  activate: "Aktivovat účet",
  deactivate: "Deaktivovat účet",
};

export function Users() {
  const [search, setSearch] = useState("");
  const [active, setActive] = useState("");
  const [role, setRole] = useState("");
  const [page, setPage] = useState(1);
  const [editor, setEditor] = useState<{ user?: User; action: Action } | null>(
    null,
  );
  const [temporary, setTemporary] = useState<TemporaryPassword | null>(null);
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState("");
  const params = new URLSearchParams({ search, page: String(page) });
  if (active) params.set("is_active", active);
  if (role) params.set("system_role", role);
  const users = useQuery({
    queryKey: ["users", search, active, role, page],
    queryFn: () => api<Page<User>>(`admin/users/?${params}`),
  });
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">ADMINISTRACE</span>
          <h1>
            Uživatelé{" "}
            <span className="count-badge">{users.data?.data.count ?? "…"}</span>
          </h1>
          <p className="muted">
            Spravujte účty a bezpečný přístup do TankLogu.
          </p>
        </div>
        <Button onClick={() => setEditor({ action: "edit" })}>
          <Plus size={18} /> Přidat uživatele
        </Button>
      </div>
      <div className="info-strip">
        <ShieldCheck size={19} />
        <span>
          Registrace není veřejná. Nové účty získají jednorázové heslo a nastaví
          si vlastní.
        </span>
      </div>
      <section className="panel users-panel">
        <div className="filter-bar">
          <div className="search-field">
            <Search size={18} />
            <Input
              aria-label="Hledat uživatele"
              placeholder="Hledat jméno nebo uživatelské jméno…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
          </div>
          <select
            className="input"
            aria-label="Filtr stavu"
            value={active}
            onChange={(e) => {
              setActive(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Všechny stavy</option>
            <option value="true">Aktivní</option>
            <option value="false">Neaktivní</option>
          </select>
          <select
            className="input"
            aria-label="Filtr role"
            value={role}
            onChange={(e) => {
              setRole(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Všechny role</option>
            <option value="USER">Uživatelé</option>
            <option value="ADMIN">Administrátoři</option>
          </select>
        </div>
        {users.isPending ? (
          <Loading />
        ) : users.error ? (
          <ErrorMessage>{errorText(users.error)}</ErrorMessage>
        ) : !users.data.data.results.length ? (
          <div className="empty-state">
            <UsersRound size={32} />
            <h2>Žádní uživatelé neodpovídají filtru</h2>
            <p className="muted">Upravte hledání nebo vytvořte nový účet.</p>
          </div>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Uživatel</th>
                  <th>Role</th>
                  <th>Stav účtu</th>
                  <th className="text-right">Akce</th>
                </tr>
              </thead>
              <tbody>
                {users.data.data.results.map((user) => (
                  <tr key={user.id}>
                    <td>
                      <div className="person-cell">
                        <span className="avatar">
                          <UserRound size={20} />
                        </span>
                        <div>
                          <strong>{user.display_name || user.username}</strong>
                          <small>
                            {user.username}
                            {user.email ? ` · ${user.email}` : ""}
                          </small>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span
                        className={`role-badge ${user.system_role === "ADMIN" ? "role-admin" : ""}`}
                      >
                        {user.system_role === "ADMIN" && (
                          <ShieldCheck size={13} />
                        )}
                        {user.system_role === "ADMIN"
                          ? "Administrátor"
                          : "Uživatel"}
                      </span>
                    </td>
                    <td>
                      <span
                        className={`status-dot ${user.is_active ? "" : "inactive"}`}
                      >
                        {user.is_active ? "Aktivní" : "Neaktivní"}
                      </span>
                      {user.must_change_password && (
                        <small className="muted block">
                          Čeká na změnu hesla
                        </small>
                      )}
                    </td>
                    <td>
                      <div className="row-actions">
                        <Button
                          variant="ghost"
                          aria-label={`Upravit ${user.username}`}
                          onClick={() => setEditor({ user, action: "edit" })}
                        >
                          <Pencil size={16} />
                        </Button>
                        <Button
                          variant="ghost"
                          disabled={!user.is_active}
                          aria-label={`Resetovat heslo ${user.username}`}
                          onClick={() =>
                            setEditor({ user, action: "password-reset" })
                          }
                        >
                          <KeyRound size={16} />
                        </Button>
                        <Button
                          variant="ghost"
                          onClick={() =>
                            setEditor({
                              user,
                              action: user.is_active
                                ? "deactivate"
                                : "activate",
                            })
                          }
                        >
                          {user.is_active ? "Deaktivovat" : "Aktivovat"}
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="pagination">
          <span className="muted">
            {users.data?.data.count ?? 0} účtů celkem
          </span>
          <div>
            <Button
              variant="ghost"
              aria-label="Předchozí strana"
              disabled={page === 1}
              onClick={() => setPage(page - 1)}
            >
              <ChevronLeft size={17} />
            </Button>
            <span>Strana {page}</span>
            <Button
              variant="ghost"
              aria-label="Další strana"
              disabled={!users.data?.data.next}
              onClick={() => setPage(page + 1)}
            >
              <ChevronRight size={17} />
            </Button>
          </div>
        </div>
      </section>
      <Modal
        open={!!editor}
        onClose={() => setEditor(null)}
        title={
          editor?.user ? actionLabels[editor.action] : "Nový uživatelský účet"
        }
        description={
          editor?.action === "deactivate"
            ? "Deaktivace odhlásí všechna zařízení. Historie uživatele zůstane zachována."
            : "Citlivou změnu potvrďte svým aktuálním heslem."
        }
      >
        {editor &&
          (editor.action === "edit" ? (
            <UserEditor
              user={editor.user}
              onClose={() => setEditor(null)}
              onTemporary={setTemporary}
            />
          ) : (
            <ActionForm
              user={editor.user!}
              action={editor.action}
              onClose={() => setEditor(null)}
              onTemporary={setTemporary}
            />
          ))}
      </Modal>
      <Modal
        open={!!temporary}
        onClose={() => {
          setTemporary(null);
          setCopied(false);
          setCopyError("");
        }}
        title="Jednorázové dočasné heslo"
        description="Heslo uvidíte pouze nyní. Předejte ho uživateli soukromým kanálem. Platí 24 hodin a lze ho použít jen jednou."
      >
        {temporary && (
          <div className="modal-form">
            <Field id="temporary-password" label="Dočasné heslo">
              <Input
                id="temporary-password"
                readOnly
                value={temporary.temporary_password}
                className="mono"
              />
            </Field>
            <p className="muted">
              Platnost do{" "}
              {new Date(temporary.expires_at).toLocaleString("cs-CZ", {
                timeZone: "Europe/Prague",
              })}
              .
            </p>
            <ErrorMessage>{copyError}</ErrorMessage>
            <div className="form-actions">
              <Button
                variant="secondary"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(
                      temporary.temporary_password,
                    );
                    setCopied(true);
                  } catch {
                    setCopyError(
                      "Kopírování není dostupné. Heslo označte a zkopírujte ručně.",
                    );
                  }
                }}
              >
                {copied ? <Check size={16} /> : <Copy size={16} />}
                {copied ? "Zkopírováno" : "Kopírovat heslo"}
              </Button>
              <Button
                onClick={() => {
                  setTemporary(null);
                  setCopied(false);
                  setCopyError("");
                }}
              >
                Hotovo
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </>
  );
}

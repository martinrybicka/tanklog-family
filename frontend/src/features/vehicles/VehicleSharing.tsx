import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  Button,
  ErrorMessage,
  Field,
  Input,
  Loading,
  Modal,
} from "../../components/ui";
import { api, errorText } from "../../lib/api";
import type { Page, User, Vehicle, VehicleAccess } from "../../lib/types";
import { roles } from "./VehicleForm";

function UserPicker({
  id,
  label,
  value,
  onChange,
  exclude = "",
}: {
  id: string;
  label: string;
  value: string;
  onChange: (id: string) => void;
  exclude?: string;
}) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const users = useQuery({
    queryKey: ["vehicle-user-options", search, page],
    queryFn: () =>
      api<Page<User>>(
        `admin/users/?is_active=true&search=${encodeURIComponent(search)}&page=${page}`,
      ),
  });
  return (
    <div className="user-picker">
      <Field id={`${id}-search`} label={`Hledat: ${label}`}>
        <Input
          id={`${id}-search`}
          type="search"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
            onChange("");
          }}
        />
      </Field>
      <Field id={id} label={label}>
        <select
          id={id}
          className="input"
          required
          value={value}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">Vyberte aktivní účet</option>
          {users.data?.data.results
            .filter((u) => u.id !== exclude)
            .map((u) => (
              <option key={u.id} value={u.id}>
                {u.display_name || u.username} ({u.username})
              </option>
            ))}
        </select>
      </Field>
      {users.isPending && <Loading />}
      <ErrorMessage>{users.error && errorText(users.error)}</ErrorMessage>
      {users.data && users.data.data.count > 25 && (
        <div className="vehicle-actions">
          <Button
            type="button"
            variant="ghost"
            disabled={!users.data.data.previous}
            onClick={() => {
              setPage(page - 1);
              onChange("");
            }}
          >
            Předchozí účty
          </Button>
          <span>{page}</span>
          <Button
            type="button"
            variant="ghost"
            disabled={!users.data.data.next}
            onClick={() => {
              setPage(page + 1);
              onChange("");
            }}
          >
            Další účty
          </Button>
        </div>
      )}
    </div>
  );
}
export function VehicleSharing({
  vehicle,
  etag,
  onChange,
}: {
  vehicle: Vehicle;
  etag: string;
  onChange: () => Promise<void>;
}) {
  const client = useQueryClient();
  const [userId, setUserId] = useState("");
  const [role, setRole] = useState("VIEWER");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);
  const [remove, setRemove] = useState<VehicleAccess | null>(null);
  const [transfer, setTransfer] = useState(false);
  const [newOwner, setNewOwner] = useState("");
  const [previousRole, setPreviousRole] = useState("");
  const [password, setPassword] = useState("");
  const [dialogError, setDialogError] = useState("");
  const grants = useQuery({
    queryKey: ["vehicle-access", vehicle.id],
    queryFn: () =>
      api<{
        owner_id: string;
        owner: { username: string; display_name: string };
        results: VehicleAccess[];
      }>(`admin/vehicles/${vehicle.id}/access/`),
  });
  const tag = (grant: VehicleAccess) =>
    `"vehicle-access:${grant.id}:${grant.version}"`;
  const reload = async () => {
    await client.invalidateQueries({
      queryKey: ["vehicle-access", vehicle.id],
    });
    await onChange();
  };
  const mutate = async (action: () => Promise<unknown>, done: string) => {
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await action();
      await reload();
      setSuccess(done);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="panel" id="sdileni">
      <div className="section-title">
        <h2>Sdílení a vlastnictví</h2>
        <Button
          variant="secondary"
          onClick={() => {
            setTransfer(true);
            setDialogError("");
          }}
        >
          Převést vlastnictví
        </Button>
      </div>
      <p>
        Vlastník:{" "}
        <strong>
          {grants.data?.data.owner?.display_name ||
            grants.data?.data.owner?.username ||
            vehicle.owner_id}
        </strong>
      </p>
      <p className="muted">
        Čtenář (VIEWER) pouze prohlíží. Přispěvatel (CONTRIBUTOR) bude moci od
        fáze 3 přidávat a upravovat vlastní tankování. Sdílení zpřístupní celou
        historii včetně budoucích účtenek.
      </p>
      <ErrorMessage>{error}</ErrorMessage>
      {success && (
        <p role="status" className="success-text">
          {success}
        </p>
      )}
      {error && (
        <Button
          variant="secondary"
          onClick={() => {
            void reload();
            setError("");
          }}
        >
          Načíst aktuální údaje
        </Button>
      )}
      {grants.isPending ? (
        <Loading />
      ) : grants.error ? (
        <ErrorMessage>{errorText(grants.error)}</ErrorMessage>
      ) : grants.data.data.results.length ? (
        <ul className="grant-list">
          {grants.data.data.results.map((grant) => (
            <li key={grant.id}>
              <div>
                <strong>{grant.display_name || grant.username}</strong>
                <p className="muted">
                  {grant.username}
                  {!grant.is_active ? " · Neaktivní účet" : ""}
                </p>
              </div>
              <label className="sr-only" htmlFor={`grant-${grant.id}`}>
                Role pro {grant.username}
              </label>
              <select
                id={`grant-${grant.id}`}
                className="input"
                value={grant.role}
                disabled={busy || !grant.is_active}
                onChange={(e) => {
                  void mutate(
                    () =>
                      api(`admin/vehicle-access/${grant.id}/`, {
                        method: "PATCH",
                        body: { role: e.target.value },
                        etag: tag(grant),
                      }),
                    "Role byla změněna.",
                  );
                }}
              >
                {["VIEWER", "CONTRIBUTOR"].map((r) => (
                  <option value={r} key={r}>
                    {roles[r]}
                  </option>
                ))}
              </select>
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() => {
                  setRemove(grant);
                  setDialogError("");
                }}
              >
                Odebrat přístup
              </Button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">Vozidlo zatím není sdílené.</p>
      )}
      <form
        className="sharing-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (!userId) return;
          void mutate(async () => {
            await api(`admin/vehicles/${vehicle.id}/access/`, {
              method: "POST",
              body: { user_id: userId, role },
            });
            setUserId("");
          }, "Přístup byl přidán.");
        }}
      >
        <h3>Přidat sdílení</h3>
        <UserPicker
          id="grant-user"
          label="Uživatel pro sdílení"
          value={userId}
          onChange={setUserId}
          exclude={vehicle.owner_id}
        />
        <Field id="grant-role" label="Role sdílení">
          <select
            id="grant-role"
            className="input"
            value={role}
            onChange={(e) => setRole(e.target.value)}
          >
            <option value="VIEWER">Čtenář</option>
            <option value="CONTRIBUTOR">Přispěvatel</option>
          </select>
        </Field>
        <Button type="submit" disabled={busy || !userId}>
          Přidat přístup
        </Button>
      </form>
      <Modal
        open={!!remove}
        onClose={() => {
          if (!busy) setRemove(null);
        }}
        title="Odebrat přístup?"
        description={`${remove?.display_name || remove?.username || "Uživatel"} ztratí přístup k tomuto vozidlu i celé jeho historii. Systémový ADMIN si ponechá globální oprávnění.`}
      >
        <ErrorMessage>{dialogError}</ErrorMessage>
        <Button
          variant="danger"
          disabled={busy}
          onClick={async () => {
            if (!remove) return;
            setBusy(true);
            try {
              await api(`admin/vehicle-access/${remove.id}/`, {
                method: "DELETE",
                etag: tag(remove),
              });
              await reload();
              setRemove(null);
              setSuccess("Přístup byl odebrán.");
            } catch (e) {
              setDialogError(errorText(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          Potvrdit odebrání
        </Button>
        {dialogError && (
          <Button
            variant="secondary"
            onClick={() => {
              void reload();
              setRemove(null);
            }}
          >
            Načíst aktuální údaje
          </Button>
        )}
      </Modal>
      <Modal
        open={transfer}
        onClose={() => {
          if (!busy) {
            setTransfer(false);
            setPassword("");
          }
        }}
        title="Převod vlastnictví"
        description={`Převádíte vozidlo ${vehicle.name}. Nový vlastník získá plnou správu. Jeho dosavadní grant se odstraní. Systémový ADMIN si vždy ponechá globální oprávnění.`}
      >
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            if (!newOwner) return;
            setBusy(true);
            setDialogError("");
            try {
              await api(`admin/vehicles/${vehicle.id}/transfer-owner/`, {
                method: "POST",
                etag,
                body: {
                  new_owner_id: newOwner,
                  current_password: password,
                  ...(previousRole
                    ? { previous_owner_role: previousRole }
                    : {}),
                },
              });
              await reload();
              setTransfer(false);
              setNewOwner("");
              setSuccess("Vlastnictví bylo převedeno.");
            } catch (e) {
              setDialogError(errorText(e));
            } finally {
              setBusy(false);
              setPassword("");
            }
          }}
        >
          <UserPicker
            id="new-owner"
            label="Nový vlastník"
            value={newOwner}
            onChange={setNewOwner}
            exclude={vehicle.owner_id}
          />
          <Field id="previous-owner-role" label="Přístup původního vlastníka">
            <select
              id="previous-owner-role"
              className="input"
              value={previousRole}
              onChange={(e) => setPreviousRole(e.target.value)}
            >
              <option value="">Odebrat přístup</option>
              <option value="VIEWER">Ponechat jako čtenáře</option>
              <option value="CONTRIBUTOR">Ponechat jako přispěvatele</option>
            </select>
          </Field>
          <p className="alert">
            {previousRole
              ? `Původní vlastník dostane grant: ${roles[previousRole]}.`
              : "Původní vlastník ztratí přístup, pokud nemá systémovou roli ADMIN."}
          </p>
          <Field id="transfer-password" label="Vaše aktuální heslo">
            <Input
              id="transfer-password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>
          <ErrorMessage>{dialogError}</ErrorMessage>
          <Button type="submit" disabled={busy || !newOwner || !password}>
            Potvrdit převod
          </Button>
          {dialogError && (
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                void reload();
                setTransfer(false);
                setPassword("");
              }}
            >
              Načíst aktuální údaje
            </Button>
          )}
        </form>
      </Modal>
    </section>
  );
}

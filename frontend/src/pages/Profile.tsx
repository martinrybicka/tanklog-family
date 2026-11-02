import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, LockKeyhole, UserRound } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button, ErrorMessage, Field, Input, Loading } from "../components/ui";
import { api, errorText } from "../lib/api";
import type { User } from "../lib/types";
import { PwaSettings } from "../components/Pwa";
import { PasswordForm } from "./Password";

const schema = z.object({
  display_name: z.string().max(150),
  email: z.union([z.email("Zadejte platný e-mail."), z.literal("")]),
  theme: z.enum(["SYSTEM", "LIGHT", "DARK"]),
});

function ProfileForm({ user, etag }: { user: User; etag: string }) {
  const client = useQueryClient();
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: user,
  });
  return (
    <form
      onSubmit={handleSubmit(async (data) => {
        setError("");
        setSaved(false);
        try {
          await api("profile/", {
            method: "PATCH",
            body: {
              display_name: data.display_name,
              email: data.email,
              theme: data.theme,
            },
            etag,
          });
          await client.invalidateQueries({ queryKey: ["profile"] });
          await client.invalidateQueries({ queryKey: ["session"] });
          setSaved(true);
        } catch (e) {
          setError(errorText(e));
        }
      })}
      noValidate
    >
      <Field
        label="Uživatelské jméno"
        id="profile-username"
        hint="Uživatelské jméno nelze změnit."
      >
        <Input id="profile-username" value={user.username} disabled />
      </Field>
      <Field
        label="Zobrazované jméno"
        id="display_name"
        error={errors.display_name?.message}
      >
        <Input
          id="display_name"
          autoComplete="name"
          {...register("display_name")}
        />
      </Field>
      <Field label="Kontaktní e-mail" id="email" error={errors.email?.message}>
        <Input
          id="email"
          type="email"
          autoComplete="email"
          aria-invalid={!!errors.email}
          aria-describedby="email-error"
          {...register("email")}
        />
      </Field>
      <Field label="Vzhled aplikace" id="theme">
        <select id="theme" className="input" {...register("theme")}>
          <option value="SYSTEM">Podle nastavení zařízení</option>
          <option value="LIGHT">Světlý</option>
          <option value="DARK">Tmavý</option>
        </select>
      </Field>
      <ErrorMessage>{error}</ErrorMessage>
      {saved && (
        <p role="status" className="success-text">
          <Check size={16} /> Profil byl uložen.
        </p>
      )}
      <Button disabled={isSubmitting} type="submit">
        {isSubmitting ? "Ukládání…" : "Uložit profil"}
      </Button>
    </form>
  );
}

export function Profile() {
  const profile = useQuery({
    queryKey: ["profile"],
    queryFn: () => api<User>("profile/"),
  });
  if (profile.isPending) return <Loading />;
  if (profile.error)
    return <ErrorMessage>{errorText(profile.error)}</ErrorMessage>;
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">VÁŠ ÚČET</span>
          <h1>Nastavení</h1>
          <p className="muted">
            Osobní údaje, vzhled a zabezpečení na jednom místě.
          </p>
        </div>
      </div>
      <div className="settings-grid">
        <section className="panel">
          <div className="section-heading">
            <span className="icon-tile">
              <UserRound size={21} />
            </span>
            <div>
              <h2>Osobní profil</h2>
              <p className="muted">Údaje, pod kterými vás ostatní uvidí.</p>
            </div>
          </div>
          <ProfileForm user={profile.data.data} etag={profile.data.etag!} />
        </section>
        <section className="panel">
          <div className="section-heading">
            <span className="icon-tile">
              <LockKeyhole size={21} />
            </span>
            <div>
              <h2>Změna hesla</h2>
              <p className="muted">Po změně odhlásíme ostatní zařízení.</p>
            </div>
          </div>
          <PasswordForm />
        </section>
      </div>
      <PwaSettings />
    </>
  );
}

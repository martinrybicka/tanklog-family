import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, ShieldCheck, LockKeyhole } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";
import { Button, ErrorMessage, Field, Input, Logo } from "../components/ui";
import { api, errorText, refreshCsrf } from "../lib/api";
import type { Session } from "../lib/types";

const loginSchema = z.object({
  username: z.string().trim().min(1, "Zadejte uživatelské jméno.").max(150),
  password: z.string().min(1, "Zadejte heslo.").max(256),
});
export function Login() {
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<z.infer<typeof loginSchema>>({
    resolver: zodResolver(loginSchema),
  });
  return (
    <div className="auth-layout">
      <section className="auth-story">
        <Logo />
        <div>
          <span className="eyebrow">MÉNĚ STAROSTÍ. VÍCE PŘEHLEDU.</span>
          <h1>
            Vaše auta.
            <br />
            Vaše cesty.
            <br />
            <em>Na jednom místě.</em>
          </h1>
          <p>
            Soukromý prostor pro váš automobilový deník. Přehledně, jednoduše a
            pod vaší kontrolou.
          </p>
        </div>
        <div className="auth-trust">
          <ShieldCheck size={20} /> Vaše data zůstávají u vás.
        </div>
        <div className="road-lines" aria-hidden="true" />
      </section>
      <main className="auth-main">
        <div className="auth-mobile-brand">
          <Logo />
        </div>
        <div className="auth-form">
          <span className="icon-tile">
            <LockKeyhole size={24} />
          </span>
          <span className="eyebrow">VÍTEJTE V TANKLOGU</span>
          <h2>Přihlásit se</h2>
          <p className="muted">Pokračujte do svého automobilového deníku.</p>
          <form
            onSubmit={handleSubmit(async (data) => {
              setError("");
              try {
                const result = await api<Session>("auth/login/", {
                  method: "POST",
                  body: data,
                });
                await refreshCsrf();
                queryClient.clear();
                queryClient.setQueryData(["session"], result.data);
                navigate(
                  result.data.must_change_password ? "/zmena-hesla" : "/",
                  { replace: true },
                );
              } catch (e) {
                setError(errorText(e));
              }
            })}
            noValidate
          >
            <Field
              id="username"
              label="Uživatelské jméno"
              error={errors.username?.message}
            >
              <Input
                id="username"
                autoComplete="username"
                autoCapitalize="none"
                aria-invalid={!!errors.username}
                aria-describedby={
                  errors.username ? "username-error" : undefined
                }
                {...register("username")}
              />
            </Field>
            <Field id="password" label="Heslo" error={errors.password?.message}>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                aria-invalid={!!errors.password}
                aria-describedby={
                  errors.password ? "password-error" : undefined
                }
                {...register("password")}
              />
            </Field>
            <ErrorMessage>{error}</ErrorMessage>
            <Button disabled={isSubmitting} className="w-full" type="submit">
              {isSubmitting ? "Přihlašování…" : "Přihlásit se"}
              <ArrowRight size={18} />
            </Button>
          </form>
          <div className="login-help">
            <ShieldCheck size={17} />
            <p>
              Účet vám vytvoří správce aplikace.
              <br />
              Pokud heslo neznáte, požádejte ho o reset.
            </p>
          </div>
        </div>
        <small className="auth-footer">
          TankLog · Váš soukromý automobilový deník
        </small>
      </main>
    </div>
  );
}

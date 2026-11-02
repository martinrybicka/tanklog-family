import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { KeyRound } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";
import { Button, ErrorMessage, Field, Input, Logo } from "../components/ui";
import { api, errorText, refreshCsrf } from "../lib/api";
import type { Session } from "../lib/types";

const schema = z
  .object({
    current_password: z.string(),
    new_password: z
      .string()
      .min(12, "Nové heslo musí mít alespoň 12 znaků.")
      .max(256),
    confirm_password: z.string(),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "Hesla se neshodují.",
    path: ["confirm_password"],
  });

export function PasswordForm({ restricted = false }: { restricted?: boolean }) {
  const client = useQueryClient();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: {
      current_password: "",
      new_password: "",
      confirm_password: "",
    },
  });
  return (
    <form
      onSubmit={handleSubmit(async (data) => {
        setError("");
        setSuccess(false);
        try {
          await api("auth/password/change/", {
            method: "POST",
            body: {
              new_password: data.new_password,
              ...(restricted
                ? {}
                : { current_password: data.current_password }),
            },
          });
          await refreshCsrf();
          const session = await api<Session>("auth/me/");
          client.removeQueries({
            predicate: (query) => query.queryKey[0] !== "session",
          });
          client.setQueryData(["session"], session.data);
          reset();
          setSuccess(true);
          if (restricted) navigate("/", { replace: true });
        } catch (e) {
          setError(errorText(e));
        }
      })}
      noValidate
    >
      {!restricted && (
        <Field label="Aktuální heslo" id="current_password">
          <Input
            id="current_password"
            type="password"
            autoComplete="current-password"
            required
            {...register("current_password")}
          />
        </Field>
      )}
      <Field
        label="Nové heslo"
        id="new_password"
        hint="Nejméně 12 znaků. Nepoužívejte běžné heslo ani své uživatelské jméno."
        error={errors.new_password?.message}
      >
        <Input
          id="new_password"
          type="password"
          autoComplete="new-password"
          aria-invalid={!!errors.new_password}
          aria-describedby="new_password-error"
          {...register("new_password")}
        />
      </Field>
      <Field
        label="Nové heslo znovu"
        id="confirm_password"
        error={errors.confirm_password?.message}
      >
        <Input
          id="confirm_password"
          type="password"
          autoComplete="new-password"
          aria-invalid={!!errors.confirm_password}
          aria-describedby="confirm_password-error"
          {...register("confirm_password")}
        />
      </Field>
      <ErrorMessage>{error}</ErrorMessage>
      {success && (
        <p role="status" className="success-text">
          Heslo bylo změněno. Ostatní přihlášení byla zneplatněna.
        </p>
      )}
      <Button disabled={isSubmitting} type="submit">
        <KeyRound size={17} />
        {isSubmitting ? "Ukládání…" : "Nastavit nové heslo"}
      </Button>
    </form>
  );
}

export function ForcedPassword() {
  const navigate = useNavigate();
  const client = useQueryClient();
  const [error, setError] = useState("");
  return (
    <main className="forced-password">
      <Logo />
      <section className="panel">
        <span className="icon-tile">
          <KeyRound size={24} />
        </span>
        <span className="eyebrow">ZABEZPEČENÍ ÚČTU</span>
        <h1>Nastavte si vlastní heslo</h1>
        <p className="muted">
          Dočasné heslo již bylo použito. Pro přístup do aplikace si během 15
          minut nastavte nové.
        </p>
        <PasswordForm restricted />
        <ErrorMessage>{error}</ErrorMessage>
        <Button
          variant="ghost"
          onClick={async () => {
            try {
              await api("auth/logout/", { method: "POST" });
              await refreshCsrf();
              client.clear();
              client.setQueryData(["session"], null);
              navigate("/prihlaseni");
            } catch (e) {
              setError(errorText(e));
            }
          }}
        >
          Odhlásit se
        </Button>
      </section>
    </main>
  );
}

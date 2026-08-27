import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import type {
  FieldError,
  InvitationAcceptanceResponse,
  InvitationValidationResponse,
} from "../api/contracts";
import { useSession } from "../session/SessionContext";
import { ErrorSummary } from "../ui/ErrorSummary";
import { ErrorState, LoadingState } from "../ui/States";
import { fieldError, formErrors } from "../ui/formErrors";

export function InvitationAcceptPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const navigate = useNavigate();
  const { client, setSession } = useSession();
  const [validation, setValidation] = useState<InvitationValidationResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [errors, setErrors] = useState<FieldError[]>([]);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!token) return;
    let active = true;
    client
      .request<InvitationValidationResponse>("/invitations/validate", {
        method: "POST",
        body: { token },
      })
      .then((response) => {
        if (active) setValidation(response);
      })
      .catch((error: unknown) => {
        if (active) setLoadError(formErrors(error, "token")[0]?.message ?? "Запрошення недійсне.");
      });
    return () => {
      active = false;
    };
  }, [client, token]);

  if (!token)
    return (
      <ErrorState
        title="Не вдалося відкрити запрошення"
        description="Посилання не містить токена запрошення."
      />
    );
  if (loadError)
    return <ErrorState title="Не вдалося відкрити запрошення" description={loadError} />;
  if (!validation) return <LoadingState label="Перевіряємо запрошення…" />;

  const isNewAccount = validation.acceptance_mode === "activate_access";
  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextErrors: FieldError[] = [];
    if (password.length < (isNewAccount ? 8 : 1))
      nextErrors.push({
        field: "password",
        code: "PASSWORD_TOO_SHORT",
        message: isNewAccount ? "Пароль має містити щонайменше 8 символів." : "Введіть пароль.",
      });
    if (isNewAccount && confirmation !== password)
      nextErrors.push({
        field: "password_confirmation",
        code: "PASSWORD_MISMATCH",
        message: "Паролі не збігаються.",
      });
    if (nextErrors.length > 0) {
      setErrors(nextErrors);
      return;
    }
    setErrors([]);
    setSubmitting(true);
    try {
      const response = await client.request<InvitationAcceptanceResponse>("/invitations/accept", {
        method: "POST",
        body: { token, acceptance_mode: validation.acceptance_mode, password },
      });
      setSession(response);
      void navigate("/", { replace: true });
    } catch (error) {
      setErrors(formErrors(error, "password"));
    } finally {
      setSubmitting(false);
    }
  };

  const passwordError = fieldError(errors, "password");
  const confirmationError = fieldError(errors, "password_confirmation");
  return (
    <main aria-label="Bacara Academy" className="auth-page">
      <section className="auth-panel" aria-labelledby="invitation-title">
        <p className="eyebrow">Запрошення до команди</p>
        <h1 id="invitation-title">{validation.organization_name}</h1>
        <p className="form-intro">
          Запрошення надіслано для {validation.email_masked}.{" "}
          {isNewAccount ? "Створіть пароль для доступу." : "Підтвердьте доступ чинним паролем."}
        </p>
        <form className="form-stack" onSubmit={(event) => void handleSubmit(event)} noValidate>
          <ErrorSummary errors={errors} />
          <div className="field-group">
            <label htmlFor="password">{isNewAccount ? "Створіть пароль" : "Пароль"}</label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete={isNewAccount ? "new-password" : "current-password"}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              aria-invalid={Boolean(passwordError)}
              aria-describedby={passwordError ? "password-error" : undefined}
            />
            {passwordError ? (
              <p id="password-error" className="field-error">
                {passwordError}
              </p>
            ) : null}
          </div>
          {isNewAccount ? (
            <div className="field-group">
              <label htmlFor="password_confirmation">Повторіть пароль</label>
              <input
                id="password_confirmation"
                name="password_confirmation"
                type="password"
                autoComplete="new-password"
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
                aria-invalid={Boolean(confirmationError)}
                aria-describedby={confirmationError ? "password-confirmation-error" : undefined}
              />
              {confirmationError ? (
                <p id="password-confirmation-error" className="field-error">
                  {confirmationError}
                </p>
              ) : null}
            </div>
          ) : null}
          <button className="button button-primary button-full" type="submit" disabled={submitting}>
            {submitting ? "Приймаємо…" : "Прийняти запрошення"}
          </button>
        </form>
      </section>
    </main>
  );
}

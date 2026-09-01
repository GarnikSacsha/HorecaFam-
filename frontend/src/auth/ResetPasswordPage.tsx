import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ApiError } from "../api/client";
import type { FieldError } from "../api/contracts";
import { useSession } from "../session/SessionContext";
import { ErrorSummary } from "../ui/ErrorSummary";
import { fieldError, formErrors } from "../ui/formErrors";

export function ResetPasswordPage() {
  const { client } = useSession();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [errors, setErrors] = useState<FieldError[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [complete, setComplete] = useState(false);
  const [invalidLink, setInvalidLink] = useState(!token);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const localErrors: FieldError[] = [];
    if (newPassword.length < 8) {
      localErrors.push({
        field: "new_password",
        code: "PASSWORD_TOO_SHORT",
        message: "Пароль має містити щонайменше 8 символів.",
      });
    }
    if (newPassword !== confirmation) {
      localErrors.push({
        field: "password_confirmation",
        code: "PASSWORD_CONFIRMATION_MISMATCH",
        message: "Паролі не збігаються.",
      });
    }
    setErrors(localErrors);
    if (localErrors.length > 0) return;

    setSubmitting(true);
    try {
      await client.request<void>("/auth/password/reset", {
        method: "POST",
        body: { token, new_password: newPassword },
      });
      setNewPassword("");
      setConfirmation("");
      setComplete(true);
    } catch (error) {
      if (error instanceof ApiError && error.code === "PASSWORD_RESET_TOKEN_INVALID") {
        setNewPassword("");
        setConfirmation("");
        setInvalidLink(true);
      } else {
        setErrors(formErrors(error, "new_password"));
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (invalidLink) {
    return (
      <main aria-label="Bacara Academy" className="auth-page">
        <section className="auth-panel" aria-labelledby="reset-invalid-title">
          <p className="eyebrow">Посилання недійсне</p>
          <h1 id="reset-invalid-title">Запросіть нове посилання</h1>
          <p className="form-intro">
            Посилання відсутнє, прострочене або вже використане. Старе посилання відновити не можна.
          </p>
          <Link className="button button-primary button-full" to="/forgot-password">
            Запросити нове посилання
          </Link>
        </section>
      </main>
    );
  }

  const passwordError = fieldError(errors, "new_password");
  const confirmationError = fieldError(errors, "password_confirmation");
  return (
    <main aria-label="Bacara Academy" className="auth-page">
      <section className="auth-panel" aria-labelledby="reset-password-title">
        <p className="brand-mark">Bacara Academy</p>
        <p className="eyebrow">Відновлення доступу</p>
        <h1 id="reset-password-title">Створіть новий пароль</h1>
        {complete ? (
          <div className="auth-success" role="status">
            <h2>Пароль змінено</h2>
            <p>Посилання використано. Усі попередні сесії завершено.</p>
            <Link className="button button-primary button-full" to="/login">
              Увійти з новим паролем
            </Link>
          </div>
        ) : (
          <form className="form-stack" onSubmit={(event) => void handleSubmit(event)} noValidate>
            <ErrorSummary errors={errors} />
            <div className="field-group">
              <label htmlFor="new_password">Новий пароль</label>
              <input
                id="new_password"
                name="new_password"
                type="password"
                autoComplete="new-password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                aria-invalid={Boolean(passwordError)}
                aria-describedby={passwordError ? "new-password-error" : "new-password-hint"}
                required
              />
              <p id="new-password-hint" className="field-hint">
                Щонайменше 8 символів. Можна вставити пароль із менеджера паролів.
              </p>
              {passwordError ? (
                <p id="new-password-error" className="field-error">
                  {passwordError}
                </p>
              ) : null}
            </div>
            <div className="field-group">
              <label htmlFor="password_confirmation">Повторіть новий пароль</label>
              <input
                id="password_confirmation"
                name="password_confirmation"
                type="password"
                autoComplete="new-password"
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
                aria-invalid={Boolean(confirmationError)}
                aria-describedby={confirmationError ? "confirmation-error" : undefined}
                required
              />
              {confirmationError ? (
                <p id="confirmation-error" className="field-error">
                  {confirmationError}
                </p>
              ) : null}
            </div>
            <button
              className="button button-primary button-full"
              type="submit"
              disabled={submitting}
            >
              {submitting ? "Змінюємо…" : "Змінити пароль"}
            </button>
          </form>
        )}
      </section>
    </main>
  );
}

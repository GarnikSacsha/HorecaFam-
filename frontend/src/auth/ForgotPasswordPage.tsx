import { useState } from "react";
import { Link } from "react-router-dom";

import type { FieldError, PasswordForgotResponse } from "../api/contracts";
import { useSession } from "../session/SessionContext";
import { ErrorSummary } from "../ui/ErrorSummary";
import { fieldError, formErrors } from "../ui/formErrors";

export function ForgotPasswordPage() {
  const { client } = useSession();
  const [email, setEmail] = useState("");
  const [errors, setErrors] = useState<FieldError[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [accepted, setAccepted] = useState(false);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrors([]);
    setSubmitting(true);
    try {
      await client.request<PasswordForgotResponse>("/auth/password/forgot", {
        method: "POST",
        body: { email },
      });
      setAccepted(true);
    } catch (error) {
      setErrors(formErrors(error, "email"));
    } finally {
      setSubmitting(false);
    }
  };

  const emailError = fieldError(errors, "email");
  return (
    <main aria-label="Bacara Academy" className="auth-page">
      <section className="auth-panel" aria-labelledby="forgot-password-title">
        <p className="brand-mark">Bacara Academy</p>
        <p className="eyebrow">Відновлення доступу</p>
        <h1 id="forgot-password-title">Відновіть пароль</h1>
        {accepted ? (
          <div className="auth-success" role="status">
            <h2>Перевірте пошту</h2>
            <p>
              Якщо адреса зареєстрована, ми надіслали інструкцію для зміни пароля. Посилання діє 30
              хвилин і може бути використане лише один раз.
            </p>
            <Link className="button button-primary button-full" to="/login">
              Повернутися до входу
            </Link>
          </div>
        ) : (
          <>
            <p className="form-intro">
              Введіть робочу адресу. Відповідь не повідомлятиме, чи існує обліковий запис.
            </p>
            <form className="form-stack" onSubmit={(event) => void handleSubmit(event)} noValidate>
              <ErrorSummary errors={errors} />
              <div className="field-group">
                <label htmlFor="email">Робоча електронна пошта</label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  aria-invalid={Boolean(emailError)}
                  aria-describedby={emailError ? "email-error" : undefined}
                  required
                />
                {emailError ? (
                  <p id="email-error" className="field-error">
                    {emailError}
                  </p>
                ) : null}
              </div>
              <button
                className="button button-primary button-full"
                type="submit"
                disabled={submitting}
              >
                {submitting ? "Надсилаємо…" : "Надіслати інструкцію"}
              </button>
              <Link className="auth-link" to="/login">
                Повернутися до входу
              </Link>
            </form>
          </>
        )}
      </section>
    </main>
  );
}

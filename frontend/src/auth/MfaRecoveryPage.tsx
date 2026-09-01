import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import type { FieldError, SessionResponse } from "../api/contracts";
import { useSession } from "../session/SessionContext";
import { ErrorSummary } from "../ui/ErrorSummary";
import { fieldError, formErrors } from "../ui/formErrors";

export function MfaRecoveryPage() {
  const navigate = useNavigate();
  const { client, setSession } = useSession();
  const [code, setCode] = useState("");
  const [errors, setErrors] = useState<FieldError[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrors([]);
    const normalizedCode = code.replace(/\s/g, "").toUpperCase();
    if (normalizedCode.length < 16) {
      setErrors([
        {
          field: "code",
          code: "INVALID_RECOVERY_CODE",
          message: "Введіть повний резервний код.",
        },
      ]);
      return;
    }
    setSubmitting(true);
    try {
      const session = await client.request<SessionResponse>("/auth/mfa/recovery/verify", {
        method: "POST",
        body: { code: normalizedCode },
      });
      setCode("");
      setSession(session);
      void navigate("/", { replace: true });
    } catch (error) {
      setErrors(formErrors(error, "code"));
    } finally {
      setSubmitting(false);
    }
  };

  const codeError = fieldError(errors, "code");
  return (
    <main aria-label="Bacara Academy" className="auth-page">
      <section className="auth-panel" aria-labelledby="mfa-recovery-title">
        <p className="eyebrow">Резервний вхід</p>
        <h1 id="mfa-recovery-title">Використайте резервний код</h1>
        <p className="form-intro">
          Код спрацює лише один раз. Після входу використаний код стане недійсним.
        </p>
        <form className="form-stack" onSubmit={(event) => void handleSubmit(event)} noValidate>
          <ErrorSummary errors={errors} />
          <div className="field-group">
            <label htmlFor="code">Резервний код</label>
            <input
              id="code"
              name="code"
              type="text"
              autoComplete="one-time-code"
              spellCheck={false}
              value={code}
              onChange={(event) => setCode(event.target.value)}
              aria-invalid={Boolean(codeError)}
              aria-describedby={codeError ? "code-error" : undefined}
              required
            />
            {codeError ? (
              <p id="code-error" className="field-error">
                {codeError}
              </p>
            ) : null}
          </div>
          <button className="button button-primary button-full" type="submit" disabled={submitting}>
            {submitting ? "Перевіряємо…" : "Увійти з резервним кодом"}
          </button>
          <Link className="auth-link" to="/mfa">
            Повернутися до коду з застосунку
          </Link>
        </form>
      </section>
    </main>
  );
}

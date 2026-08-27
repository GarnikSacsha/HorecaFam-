import { useState } from "react";
import { useNavigate } from "react-router-dom";

import type { FieldError, SessionResponse } from "../api/contracts";
import { useSession } from "../session/SessionContext";
import { ErrorSummary } from "../ui/ErrorSummary";
import { fieldError, formErrors } from "../ui/formErrors";

export function MfaPage() {
  const navigate = useNavigate();
  const { client, setSession } = useSession();
  const [code, setCode] = useState("");
  const [errors, setErrors] = useState<FieldError[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrors([]);
    if (!/^\d{6}$/.test(code)) {
      setErrors([{ field: "code", code: "INVALID_MFA_CODE", message: "Введіть шість цифр." }]);
      return;
    }
    setSubmitting(true);
    try {
      const response = await client.request<SessionResponse>("/auth/mfa/verify", {
        method: "POST",
        body: { code },
      });
      setSession(response);
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
      <section className="auth-panel" aria-labelledby="mfa-title">
        <p className="eyebrow">Безпечний вхід</p>
        <h1 id="mfa-title">Підтвердження входу</h1>
        <p className="form-intro">Введіть шестизначний код із застосунку автентифікації.</p>
        <form className="form-stack" onSubmit={(event) => void handleSubmit(event)} noValidate>
          <ErrorSummary errors={errors} />
          <div className="field-group">
            <label htmlFor="code">Код підтвердження</label>
            <input
              id="code"
              name="code"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9]{6}"
              maxLength={6}
              value={code}
              onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))}
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
            {submitting ? "Перевіряємо…" : "Підтвердити"}
          </button>
        </form>
      </section>
    </main>
  );
}

import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import type {
  FieldError,
  MfaEnrollmentConfirmResponse,
  MfaEnrollmentStartResponse,
} from "../api/contracts";
import { useSession } from "../session/SessionContext";
import { ErrorSummary } from "../ui/ErrorSummary";
import { fieldError, formErrors } from "../ui/formErrors";

type EnrollmentState =
  | { kind: "loading" }
  | { kind: "ready"; setup: MfaEnrollmentStartResponse }
  | { kind: "codes"; result: MfaEnrollmentConfirmResponse }
  | { kind: "error" };

export function MfaEnrollmentPage() {
  const navigate = useNavigate();
  const { client, setSession } = useSession();
  const [state, setState] = useState<EnrollmentState>({ kind: "loading" });
  const [code, setCode] = useState("");
  const [errors, setErrors] = useState<FieldError[]>([]);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let active = true;
    client
      .request<MfaEnrollmentStartResponse>("/auth/mfa/enrollment/start", { method: "POST" })
      .then((setup) => {
        if (active) setState({ kind: "ready", setup });
      })
      .catch(() => {
        if (active) setState({ kind: "error" });
      });
    return () => {
      active = false;
    };
  }, [client]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrors([]);
    if (!/^\d{6}$/.test(code)) {
      setErrors([{ field: "code", code: "INVALID_MFA_CODE", message: "Введіть шість цифр." }]);
      return;
    }
    setSubmitting(true);
    try {
      const result = await client.request<MfaEnrollmentConfirmResponse>(
        "/auth/mfa/enrollment/confirm",
        { method: "POST", body: { code } },
      );
      setCode("");
      setState({ kind: "codes", result });
    } catch (error) {
      setErrors(formErrors(error, "code"));
    } finally {
      setSubmitting(false);
    }
  };

  if (state.kind === "loading") {
    return (
      <main aria-label="Bacara Academy" className="auth-page" aria-busy="true">
        <section className="auth-panel">
          <p role="status">Готуємо захищене налаштування…</p>
        </section>
      </main>
    );
  }

  if (state.kind === "error") {
    return (
      <main aria-label="Bacara Academy" className="auth-page">
        <section className="auth-panel" aria-labelledby="enrollment-expired-title">
          <p className="eyebrow">Спроба входу завершилась</p>
          <h1 id="enrollment-expired-title">Почніть вхід ще раз</h1>
          <p className="form-intro">
            Захищений виклик прострочено або вже використано. Нове налаштування доступне після
            повторного входу.
          </p>
          <Link className="button button-primary button-full" to="/login">
            Повернутися до входу
          </Link>
        </section>
      </main>
    );
  }

  if (state.kind === "codes") {
    return (
      <main aria-label="Bacara Academy" className="auth-page">
        <section className="auth-panel auth-panel-wide" aria-labelledby="recovery-codes-title">
          <p className="eyebrow">Одноразове відображення</p>
          <h1 id="recovery-codes-title">Збережіть резервні коди</h1>
          <p className="form-intro">
            Кожен код працює один раз. Після переходу далі цей список більше не буде показано.
          </p>
          <ul className="recovery-code-list" aria-label="Резервні коди">
            {state.result.recovery_codes.map((recoveryCode) => (
              <li key={recoveryCode}>
                <code>{recoveryCode}</code>
              </li>
            ))}
          </ul>
          <button
            className="button button-primary button-full"
            type="button"
            onClick={() => {
              setSession(state.result.session);
              void navigate("/", { replace: true });
            }}
          >
            Я зберіг коди
          </button>
        </section>
      </main>
    );
  }

  const codeError = fieldError(errors, "code");
  return (
    <main aria-label="Bacara Academy" className="auth-page">
      <section className="auth-panel" aria-labelledby="mfa-enrollment-title">
        <p className="eyebrow">Обов’язковий захист</p>
        <h1 id="mfa-enrollment-title">Налаштуйте двофакторний вхід</h1>
        <ol className="auth-steps">
          <li>Відкрийте застосунок-автентифікатор.</li>
          <li>
            Додайте ключ <code className="setup-secret">{state.setup.secret}</code> або відкрийте
            {` `}
            <a href={state.setup.otpauth_uri}>налаштування в застосунку</a>.
          </li>
          <li>Введіть згенерований шестизначний код.</li>
        </ol>
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
            {submitting ? "Перевіряємо…" : "Підтвердити й отримати резервні коди"}
          </button>
        </form>
      </section>
    </main>
  );
}

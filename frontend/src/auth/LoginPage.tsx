import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";

import type {
  FieldError,
  MfaEnrollmentRequiredResponse,
  MfaRequiredResponse,
  SessionResponse,
} from "../api/contracts";
import { useSession } from "../session/SessionContext";
import { ErrorSummary } from "../ui/ErrorSummary";
import { fieldError, formErrors } from "../ui/formErrors";

function isMfaRequired(
  response: SessionResponse | MfaRequiredResponse | MfaEnrollmentRequiredResponse,
): response is MfaRequiredResponse {
  return "status" in response && response.status === "mfa_required";
}

function isMfaEnrollmentRequired(
  response: SessionResponse | MfaRequiredResponse | MfaEnrollmentRequiredResponse,
): response is MfaEnrollmentRequiredResponse {
  return "status" in response && response.status === "mfa_enrollment_required";
}

export function LoginPage() {
  const navigate = useNavigate();
  const { client, session, setSession, status } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<FieldError[]>([]);
  const [submitting, setSubmitting] = useState(false);

  if (status === "authenticated" && session) return <Navigate to="/" replace />;

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrors([]);
    setSubmitting(true);
    try {
      const response = await client.request<
        SessionResponse | MfaRequiredResponse | MfaEnrollmentRequiredResponse
      >("/auth/login", {
        method: "POST",
        body: { email, password },
      });
      if (isMfaRequired(response)) {
        void navigate("/mfa", { replace: true });
      } else if (isMfaEnrollmentRequired(response)) {
        void navigate("/mfa/enroll", { replace: true });
      } else {
        setSession(response);
        void navigate("/", { replace: true });
      }
    } catch (error) {
      setErrors(formErrors(error, "email"));
    } finally {
      setSubmitting(false);
    }
  };

  const emailError = fieldError(errors, "email");
  const passwordError = fieldError(errors, "password");

  return (
    <main aria-label="Bacara Academy" className="auth-page">
      <section className="auth-panel" aria-labelledby="login-title">
        <p className="brand-mark">Bacara Academy</p>
        <p className="eyebrow">Доступ до навчання</p>
        <h1 id="login-title">Увійдіть до свого простору</h1>
        <p className="form-intro">Використайте робочу адресу, на яку вас запросив адміністратор.</p>
        <form className="form-stack" onSubmit={(event) => void handleSubmit(event)} noValidate>
          <ErrorSummary errors={errors} />
          <div className="field-group">
            <label htmlFor="email">Робоча електронна пошта</label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="username"
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
          <div className="field-group">
            <label htmlFor="password">Пароль</label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              aria-invalid={Boolean(passwordError)}
              aria-describedby={passwordError ? "password-error" : undefined}
              required
            />
            {passwordError ? (
              <p id="password-error" className="field-error">
                {passwordError}
              </p>
            ) : null}
          </div>
          <button className="button button-primary button-full" type="submit" disabled={submitting}>
            {submitting ? "Входимо…" : "Увійти"}
          </button>
          <Link className="auth-link" to="/forgot-password">
            Забули пароль?
          </Link>
        </form>
      </section>
    </main>
  );
}

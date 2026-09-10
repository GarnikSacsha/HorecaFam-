import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useSession } from "../session/SessionContext";

export function LogoutButton() {
  const navigate = useNavigate();
  const { clearSession, client, session } = useSession();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [endingOthers, setEndingOthers] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const logout = async () => {
    if (!session) return;
    setError(null);
    setNotice(null);
    setSubmitting(true);
    try {
      await client.request<void>("/auth/logout", { method: "POST", csrfToken: session.csrf_token });
      clearSession();
      void navigate("/login", { replace: true });
    } catch {
      setError("Не вдалося вийти. Повторіть спробу.");
    } finally {
      setSubmitting(false);
    }
  };

  const logoutOthers = async () => {
    if (!session) return;
    setError(null);
    setNotice(null);
    setEndingOthers(true);
    try {
      await client.request<void>("/auth/logout-all", {
        method: "POST",
        csrfToken: session.csrf_token,
      });
      setNotice("На інших пристроях виконано вихід. Поточний сеанс збережено.");
    } catch {
      setError("Не вдалося завершити інші сеанси. Повторіть спробу.");
    } finally {
      setEndingOthers(false);
    }
  };

  return (
    <div className="session-action">
      <button
        className="button button-quiet"
        type="button"
        onClick={() => void logout()}
        disabled={submitting || endingOthers}
      >
        {submitting ? "Виходимо…" : "Вийти"}
      </button>
      <button
        className="button button-quiet"
        type="button"
        onClick={() => void logoutOthers()}
        disabled={submitting || endingOthers}
      >
        {endingOthers ? "Завершуємо сеанси…" : "Вийти з інших пристроїв"}
      </button>
      {notice ? <p role="status">{notice}</p> : null}
      {error ? (
        <p className="field-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

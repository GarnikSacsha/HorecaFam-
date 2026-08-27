import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useSession } from "../session/SessionContext";

export function LogoutButton() {
  const navigate = useNavigate();
  const { clearSession, client, session } = useSession();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const logout = async () => {
    if (!session) return;
    setError(null);
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

  return (
    <div className="session-action">
      <button
        className="button button-quiet"
        type="button"
        onClick={() => void logout()}
        disabled={submitting}
      >
        {submitting ? "Виходимо…" : "Вийти"}
      </button>
      {error ? (
        <p className="field-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

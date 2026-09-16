import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, createIdempotencyKey, type ApiClient } from "../api/client";
import type { InvitationListResponse, InvitationResponse } from "../api/contracts";

const labels = {
  pending: "Очікує прийняття",
  expired: "Термін минув",
  accepted: "Прийнято",
  revoked: "Відкликано",
};

export function AdminInvitationsPanel({
  client,
  organizationId,
  csrfToken,
  revision,
}: {
  client: ApiClient;
  organizationId: string;
  csrfToken: string;
  revision: number;
}) {
  const [items, setItems] = useState<InvitationResponse[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [readError, setReadError] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const writeLock = useRef(false);
  const readVersion = useRef(0);
  const keys = useRef(new Map<string, string>());
  const base = `/organizations/${organizationId}/invitations`;

  const load = useCallback(
    async (next: string | null = null) => {
      const version = ++readVersion.current;
      setLoading(true);
      setReadError(false);
      try {
        const response = await client.request<InvitationListResponse>(
          `${base}?limit=50${next ? `&cursor=${encodeURIComponent(next)}` : ""}`,
        );
        if (version !== readVersion.current) return;
        if (!Array.isArray(response.items)) throw new Error("Invalid invitation list");
        setItems((previous) =>
          next
            ? [
                ...previous,
                ...response.items.filter((item) => !previous.some((row) => row.id === item.id)),
              ]
            : response.items,
        );
        setCursor(response.next_cursor);
      } catch {
        if (version === readVersion.current) setReadError(true);
      } finally {
        if (version === readVersion.current) setLoading(false);
      }
    },
    [base, client],
  );

  useEffect(() => {
    const versions = readVersion;
    // Окреме читання не блокує список працівників, якщо запрошення недоступні.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
    return () => {
      versions.current++;
    };
  }, [load, revision]);

  const resend = async (item: InvitationResponse) => {
    if (writeLock.current) return;
    writeLock.current = true;
    setBusy(item.id);
    setError(null);
    setSuccess(null);
    const key = keys.current.get(item.id) ?? createIdempotencyKey();
    keys.current.set(item.id, key);
    try {
      const result = await client.request<InvitationResponse>(`${base}/${item.id}/resend`, {
        method: "POST",
        csrfToken,
        idempotencyKey: key,
      });
      keys.current.delete(item.id);
      setItems((previous) => previous.map((row) => (row.id === result.id ? result : row)));
      setSuccess(`Лист поставлено в чергу для ${result.email}. Попереднє посилання більше не діє.`);
    } catch (failure) {
      // Після невідомого результату повтор використовує той самий ключ без другого листа.
      if (
        failure instanceof ApiError &&
        failure.status >= 400 &&
        failure.status < 500 &&
        failure.status !== 408
      )
        keys.current.delete(item.id);
      setError(
        failure instanceof ApiError && failure.status === 429
          ? "Забагато спроб. Спробуйте пізніше."
          : "Не вдалося перевипустити запрошення. Повторіть спробу або оновіть список.",
      );
    } finally {
      writeLock.current = false;
      setBusy(null);
    }
  };

  return (
    <section className="dataset-section" aria-labelledby="invitations-title">
      <div className="dataset-header">
        <div>
          <h2 id="invitations-title">Запрошення</h2>
          <p>Повторне надсилання створює посилання на три дні та скасовує попереднє.</p>
        </div>
        <button
          type="button"
          className="button button-quiet"
          disabled={loading || busy !== null}
          onClick={() => void load()}
        >
          Оновити запрошення
        </button>
      </div>
      {readError && <p role="alert">Не вдалося завантажити запрошення.</p>}
      {error && <p role="alert">{error}</p>}
      {success && (
        <p className="success-message" role="status">
          {success}
        </p>
      )}
      {loading && <p role="status">Завантажуємо запрошення…</p>}
      {!loading && !readError && items.length === 0 && <p>Запрошень ще немає.</p>}
      <ul className="invitation-list">
        {items.map((item) => (
          <li key={item.id}>
            <p style={{ overflowWrap: "anywhere" }}>
              <strong>{item.email}</strong> — {labels[item.status]}
            </p>
            <p>
              Діє до:{" "}
              <time dateTime={item.expires_at}>
                {new Date(item.expires_at).toLocaleString("uk-UA")}
              </time>
            </p>
            {(item.status === "pending" || item.status === "expired") && (
              <button
                type="button"
                className="button button-quiet"
                aria-label={`Надіслати повторно ${item.email}`}
                disabled={loading || busy !== null}
                onClick={() => void resend(item)}
              >
                {busy === item.id ? "Надсилаємо…" : "Надіслати повторно"}
              </button>
            )}
          </li>
        ))}
      </ul>
      {cursor && (
        <button
          type="button"
          className="button button-quiet"
          disabled={loading || busy !== null}
          onClick={() => void load(cursor)}
        >
          Ще запрошення
        </button>
      )}
    </section>
  );
}

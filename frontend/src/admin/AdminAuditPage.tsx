import { FormEvent, useCallback, useEffect, useState } from "react";

import type { AuditEventListResponse, AuditEventResponse } from "../api/contracts";
import { LogoutButton } from "../auth/LogoutButton";
import { useSession } from "../session/SessionContext";
import { AuditEventList } from "../ui/AuditEventList";

export function AdminAuditPage() {
  const { client, session, status } = useSession();
  const organizationId = session?.organization_access.find(
    (access) => access.is_organization_admin,
  )?.organization_id;
  const [items, setItems] = useState<AuditEventResponse[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [action, setAction] = useState("");
  const [actorType, setActorType] = useState("");
  const [appliedAction, setAppliedAction] = useState("");
  const [appliedActorType, setAppliedActorType] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const requestPage = useCallback(
    (cursor?: string) => {
      const query = new URLSearchParams({ limit: "50" });
      if (appliedAction) query.set("action", appliedAction);
      if (appliedActorType) query.set("actor_type", appliedActorType);
      if (cursor) query.set("cursor", cursor);
      return client.request<AuditEventListResponse>(
        `/organizations/${organizationId}/audit-events?${query}`,
      );
    },
    [appliedAction, appliedActorType, client, organizationId],
  );

  useEffect(() => {
    if (status !== "authenticated" || !organizationId) return;
    let active = true;
    void requestPage()
      .then((response) => {
        if (!active) return;
        setItems(response.items);
        setNextCursor(response.next_cursor);
      })
      .catch(() => {
        if (active) setError("Не вдалося завантажити події аудиту. Повторіть спробу.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [organizationId, requestPage, status]);

  const loadMore = async () => {
    if (!nextCursor) return;
    setLoading(true);
    setError(null);
    try {
      const response = await requestPage(nextCursor);
      setItems((current) => [...current, ...response.items]);
      setNextCursor(response.next_cursor);
    } catch {
      setError("Не вдалося завантажити наступну сторінку аудиту.");
    } finally {
      setLoading(false);
    }
  };

  const applyFilters = (event: FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setAppliedAction(action.trim());
    setAppliedActorType(actorType);
  };

  return (
    <section className="admin-page operations-page" aria-labelledby="admin-audit-title">
      <div className="page-heading-row">
        <div>
          <p className="eyebrow">Контроль змін</p>
          <h1 id="admin-audit-title">Аудит організації</h1>
          <p className="page-description">
            Безпечна незмінна історія дій лише в поточній організації.
          </p>
        </div>
        <LogoutButton />
      </div>
      <form className="operations-filters" onSubmit={applyFilters}>
        <label className="field-group">
          <span>Дія</span>
          <input
            value={action}
            onChange={(event) => setAction(event.target.value)}
            maxLength={120}
            placeholder="employee.paused"
          />
        </label>
        <label className="field-group">
          <span>Тип актора</span>
          <select value={actorType} onChange={(event) => setActorType(event.target.value)}>
            <option value="">Усі</option>
            <option value="user">Користувач</option>
            <option value="system">Система</option>
            <option value="worker">Worker</option>
            <option value="cron">Cron</option>
          </select>
        </label>
        <button className="button button-secondary" type="submit">
          Застосувати фільтри
        </button>
      </form>
      {error ? (
        <p className="inline-error" role="alert">
          {error}
        </p>
      ) : null}
      {loading && !items.length ? <p aria-live="polite">Завантажуємо події аудиту…</p> : null}
      {!loading && !items.length && !error ? (
        <div className="empty-state">
          <h2>Подій за цими фільтрами немає</h2>
          <p>Змініть фільтри або поверніться пізніше.</p>
        </div>
      ) : null}
      {items.length ? (
        <AuditEventList
          items={items}
          tableLabel="Події аудиту організації"
          mobileLabel="Мобільний список подій аудиту"
        />
      ) : null}
      {nextCursor ? (
        <button
          className="button button-secondary operations-load-more"
          type="button"
          disabled={loading}
          onClick={() => void loadMore()}
        >
          {loading ? "Завантажуємо…" : "Показати більше"}
        </button>
      ) : null}
    </section>
  );
}

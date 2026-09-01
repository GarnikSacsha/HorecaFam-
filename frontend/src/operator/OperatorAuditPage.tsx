import { useEffect, useState } from "react";

import type { AuditEventListResponse, AuditEventResponse } from "../api/contracts";
import { useSession } from "../session/SessionContext";
import { AuditEventList } from "../ui/AuditEventList";

export function OperatorAuditPage() {
  const { client, status } = useSession();
  const [items, setItems] = useState<AuditEventResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status !== "authenticated") return;
    let active = true;
    void client
      .request<AuditEventListResponse>("/operator/audit-events")
      .then((response) => {
        if (active) setItems(response.items);
      })
      .catch(() => {
        if (active) setError("Не вдалося завантажити системний аудит.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [client, status]);

  return (
    <section className="operations-page" aria-labelledby="operator-audit-title">
      <div className="page-heading-row">
        <div>
          <p className="eyebrow">Platform Operations</p>
          <h1 id="operator-audit-title">Системний аудит</h1>
          <p className="page-description">
            Системні, worker, cron та операторські події. Бізнес-аудит організацій тут не
            змішується.
          </p>
        </div>
      </div>
      {error ? (
        <p className="inline-error" role="alert">
          {error}
        </p>
      ) : null}
      {loading ? <p aria-live="polite">Завантажуємо системний аудит…</p> : null}
      {!loading && !items.length && !error ? (
        <div className="empty-state">
          <h2>Системних подій ще немає</h2>
          <p>Події з’являться після виконання контрольованих операцій.</p>
        </div>
      ) : null}
      {items.length ? (
        <AuditEventList
          items={items}
          tableLabel="Системні та операторські події"
          mobileLabel="Системний аудит — мобільний список"
        />
      ) : null}
    </section>
  );
}

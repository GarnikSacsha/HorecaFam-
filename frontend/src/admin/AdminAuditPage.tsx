import { useCallback, useEffect, useState } from "react";

import type {
  MenuBusinessValues,
  MenuChangeEvent,
  MenuChangeHistoryResponse,
} from "../api/contracts";
import { LogoutButton } from "../auth/LogoutButton";
import { useSession } from "../session/SessionContext";

const fields: Array<[keyof MenuBusinessValues, string]> = [
  ["name", "Назва"],
  ["description", "Опис"],
  ["price_minor", "Ціна"],
  ["currency", "Валюта"],
  ["availability", "Доступність"],
  ["component_data_status", "Відомості про склад"],
  ["components", "Склад"],
  ["allergen_data_status", "Відомості про алергени"],
  ["allergen_codes", "Алергени"],
];
const labels: Record<string, string> = {
  available: "Доступно",
  temporarily_unavailable: "Тимчасово недоступно",
  seasonal: "Сезонна позиція",
  discontinued: "Знято з меню",
  unknown: "Не підтверджено",
  confirmed_none: "Підтверджено відсутність",
  confirmed_present: "Підтверджено наявність",
};
function displayValue(values: MenuBusinessValues | null, field: keyof MenuBusinessValues) {
  const value = values?.[field];
  if (value === null || value === undefined) return "Не вказано";
  if (field === "price_minor")
    return `${(Number(value) / 100).toLocaleString("uk-UA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${values?.currency ?? ""}`;
  if (field === "components")
    return (
      values?.components
        .map(
          (item) =>
            `${item.name}${item.optional === true ? " (за бажанням)" : item.optional === null ? " (обов’язковість не вказана)" : ""}`,
        )
        .join(", ") || "Немає"
    );
  if (Array.isArray(value))
    return value.filter((item) => typeof item === "string").join(", ") || "Немає";
  return labels[String(value)] ?? String(value);
}
function ChangeCard({ item }: { item: MenuChangeEvent }) {
  const changed = fields.filter(
    ([field]) =>
      JSON.stringify(item.old_values?.[field]) !== JSON.stringify(item.new_values?.[field]),
  );
  return (
    <article className="menu-change-card">
      <header>
        <div>
          <p className="eyebrow">
            {item.action === "created"
              ? "Додано позицію"
              : item.action === "removed"
                ? "Видалено з чернетки"
                : "Змінено позицію"}
          </p>
          <h2>{item.item_name}</h2>
        </div>
        <div className="menu-change-author">
          <strong>{item.actor_email}</strong>
          <time dateTime={item.created_at}>
            {new Date(item.created_at).toLocaleString("uk-UA")}
          </time>
        </div>
      </header>
      <p className="page-description">Зміни в чернетці меню</p>
      <dl className="menu-change-fields">
        {changed.map(([field, label]) => (
          <div key={field}>
            <dt>{label}</dt>
            <dd>
              <span>
                <small>Було</small>
                {item.old_values ? displayValue(item.old_values, field) : "Позиції не було"}
              </span>
              <span aria-hidden="true">→</span>
              <span>
                <small>Стало</small>
                {item.new_values ? displayValue(item.new_values, field) : "Позицію видалено"}
              </span>
            </dd>
          </div>
        ))}
      </dl>
    </article>
  );
}

export function AdminAuditPage() {
  const { client, session, status } = useSession();
  const organizationId = session?.organization_access.find(
    (access) => access.is_organization_admin,
  )?.organization_id;
  const [items, setItems] = useState<MenuChangeEvent[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const requestPage = useCallback(
    (cursor?: string) => {
      const query = new URLSearchParams({ limit: "50" });
      if (cursor) query.set("cursor", cursor);
      return client.request<MenuChangeHistoryResponse>(
        `/organizations/${organizationId}/menu-change-history?${query}`,
      );
    },
    [client, organizationId],
  );
  useEffect(() => {
    if (status !== "authenticated" || !organizationId) return;
    let active = true;
    void requestPage()
      .then((response) => {
        if (!active) return;
        setItems(response.items);
        setNextCursor(response.next_cursor);
        setError(null);
      })
      .catch(() => {
        if (active) setError("Не вдалося завантажити історію змін меню.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [organizationId, requestPage, status, reload]);
  const loadMore = async () => {
    if (!nextCursor || loading) return;
    setLoading(true);
    setError(null);
    try {
      const response = await requestPage(nextCursor);
      setItems((current) => [
        ...current,
        ...response.items.filter((item) => !current.some((existing) => existing.id === item.id)),
      ]);
      setNextCursor(response.next_cursor);
    } catch {
      setError("Не вдалося завантажити наступну сторінку історії.");
    } finally {
      setLoading(false);
    }
  };
  return (
    <section className="admin-page operations-page" aria-labelledby="admin-audit-title">
      <div className="page-heading-row">
        <div>
          <p className="eyebrow">Контроль змін</p>
          <h1 id="admin-audit-title">Історія змін меню</h1>
          <p className="page-description">
            Хто та коли змінив ціни, склад, алергени й інші відомості про позиції.
          </p>
        </div>
        <LogoutButton />
      </div>
      {error ? (
        <div role="alert">
          <p className="inline-error">{error}</p>
          {!items.length ? (
            <button
              className="button button-secondary"
              onClick={() => {
                setLoading(true);
                setReload((value) => value + 1);
              }}
            >
              Повторити
            </button>
          ) : null}
        </div>
      ) : null}
      {loading && !items.length ? <p aria-live="polite">Завантажуємо історію…</p> : null}
      {!loading && !items.length && !error ? (
        <div className="empty-state">
          <h2>Змін ще немає</h2>
          <p>
            Тут з’являться нові зміни позицій меню з автором та значеннями до і після редагування.
            Давні зміни не відновлюються.
          </p>
        </div>
      ) : null}
      <div className="menu-change-list">
        {items.map((item) => (
          <ChangeCard key={item.id} item={item} />
        ))}
      </div>
      {nextCursor ? (
        <button
          className="button button-secondary operations-load-more"
          disabled={loading}
          onClick={() => void loadMore()}
        >
          {loading ? "Завантажуємо…" : "Показати більше"}
        </button>
      ) : null}
    </section>
  );
}

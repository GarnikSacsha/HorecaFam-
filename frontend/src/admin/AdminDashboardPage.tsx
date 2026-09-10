import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import type { DashboardResponse, LocationSummary } from "../api/contracts";
import { LogoutButton } from "../auth/LogoutButton";
import { useSession } from "../session/SessionContext";
import "./admin-dashboard.css";

function Counts({ values }: { values: [string, number][] }) {
  return (
    <dl className="dashboard-counts">
      {values.map(([label, count]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{count}</dd>
        </div>
      ))}
    </dl>
  );
}

export function AdminDashboardPage() {
  const { client, session } = useSession();
  const organizationId = session?.organization_access.find(
    (access) => access.is_organization_admin,
  )?.organization_id;
  const [locationId, setLocationId] = useState("");
  const [locationResult, setLocationResult] = useState<{
    organizationId: string;
    items: LocationSummary[];
  } | null>(null);
  const [result, setResult] = useState<{
    key: string;
    data: DashboardResponse | null;
    failed: boolean;
  } | null>(null);
  const [retry, setRetry] = useState(0);
  const requestKey = `${organizationId}:${locationId}:${retry}`;
  const loading = result?.key !== requestKey;
  const error = !loading && result?.failed;
  const summary = !loading ? result?.data : null;
  const locations =
    locationResult && locationResult.organizationId === organizationId ? locationResult.items : [];

  useEffect(() => {
    if (!organizationId) return;
    let active = true;
    const query = locationId ? `?location_id=${encodeURIComponent(locationId)}` : "";
    void Promise.all([
      client.request<DashboardResponse>(`/organizations/${organizationId}/dashboard${query}`),
      client.request<LocationSummary[]>(`/organizations/${organizationId}/locations`),
    ])
      .then(([data, availableLocations]) => {
        if (!active) return;
        setResult({ key: requestKey, data, failed: false });
        setLocationResult({ organizationId, items: availableLocations });
      })
      .catch(() => {
        if (active) setResult({ key: requestKey, data: null, failed: true });
      });
    return () => {
      active = false;
    };
  }, [client, organizationId, locationId, requestKey]);

  return (
    <section className="admin-page dashboard-page" aria-labelledby="dashboard-title">
      <div className="page-heading-row">
        <div>
          <p className="eyebrow">Навчання команди</p>
          <h1 id="dashboard-title">Огляд команди</h1>
          <p className="page-description">Поточні завдання й результати вашого закладу.</p>
        </div>
        <LogoutButton />
      </div>
      <div className="dashboard-filter">
        <label htmlFor="dashboard-location">Локація</label>
        <select
          id="dashboard-location"
          value={locationId}
          onChange={(event) => setLocationId(event.target.value)}
          disabled={loading}
        >
          <option value="">Усі локації</option>
          {locations.map((location) => (
            <option key={location.id} value={location.id}>
              {location.name}
              {location.status === "archived" ? " (архів)" : ""}
            </option>
          ))}
        </select>
      </div>
      {loading ? <p role="status">Завантажуємо огляд…</p> : null}
      {error ? (
        <div className="inline-error">
          <p role="alert">Не вдалося завантажити огляд.</p>
          <button className="button button-quiet" onClick={() => setRetry((value) => value + 1)}>
            Повторити
          </button>
        </div>
      ) : null}
      {summary ? (
        <>
          {summary.employees.total === 0 ? (
            <div className="empty-state">
              <h2>Працівників ще немає</h2>
              <p>Відкрийте розділ працівників, щоб запросити команду й налаштувати доступ.</p>
            </div>
          ) : null}
          <div className="dashboard-grid">
            <section className="dashboard-card" aria-labelledby="dashboard-employees">
              <p className="eyebrow">Команда</p>
              <h2 id="dashboard-employees">Працівники</h2>
              <Counts
                values={[
                  ["Усього", summary.employees.total],
                  ["Активні", summary.employees.active],
                  ["Очікують активації", summary.employees.pending],
                  ["На паузі серед активних", summary.employees.paused],
                  ["Доступ вимкнено", summary.employees.disabled],
                ]}
              />
              <Link className="text-link" to="/admin/employees">
                Відкрити працівників
              </Link>
            </section>
            <section className="dashboard-card" aria-labelledby="dashboard-training">
              <p className="eyebrow">Поточні призначення</p>
              <h2 id="dashboard-training">Навчання</h2>
              <Counts
                values={[
                  ["Ще не розпочато", summary.training.assigned],
                  ["У процесі", summary.training.in_progress],
                  ["Завершено", summary.training.completed],
                ]}
              />
              <p className="dashboard-note">
                Кількість призначень активним працівникам, зокрема тим, хто на паузі.
              </p>
              <Link className="text-link" to="/admin/results">
                Відкрити результати
              </Link>
            </section>
            <section className="dashboard-card" aria-labelledby="dashboard-final">
              <p className="eyebrow">Знання команди</p>
              <h2 id="dashboard-final">Екзамени</h2>
              <Counts
                values={[
                  ["Сертифіковані", summary.final_exam.certified],
                  ["Навчання завершено, іспит попереду", summary.final_exam.needs_exam],
                  ["Мають повторну перевірку", summary.final_exam.retake],
                  ["Прострочили повторну перевірку", summary.final_exam.overdue_retake],
                ]}
              />
              <p className="dashboard-note">
                Кількість працівників. Категорії можуть перетинатися; допуск до іспиту залежить від
                готовності питань і Practice.
              </p>
              <Link className="text-link" to="/admin/results">
                Переглянути екзамени
              </Link>
            </section>
            <section className="dashboard-card" aria-labelledby="dashboard-attention">
              <p className="eyebrow">Потребує уваги</p>
              <h2 id="dashboard-attention">Attention</h2>
              <Counts
                values={[
                  ["Невирішені випадки", summary.attention.unresolved],
                  ["З них — критичні алергени", summary.attention.critical],
                ]}
              />
              <p className="dashboard-note">Відкриті й підтверджені випадки, які ще не закрито.</p>
              <Link className="text-link" to="/admin/attention">
                Відкрити Attention
              </Link>
            </section>
          </div>
        </>
      ) : null}
    </section>
  );
}

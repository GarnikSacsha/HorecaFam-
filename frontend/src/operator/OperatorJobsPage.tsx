import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import type {
  BackgroundJobStatus,
  BackgroundJobType,
  OperatorJobListResponse,
  OperatorJobSummary,
} from "../api/contracts";
import { useSession } from "../session/SessionContext";
import { StatusPill } from "../ui/States";

function formatDate(value: string) {
  return new Intl.DateTimeFormat("uk-UA", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function JobStatus({ status }: { status: BackgroundJobStatus }) {
  const tone =
    status === "completed"
      ? "success"
      : status === "failed"
        ? "danger"
        : status === "processing"
          ? "info"
          : "neutral";
  return <StatusPill tone={tone}>{status}</StatusPill>;
}

export function OperatorJobsPage() {
  const { client, status } = useSession();
  const [items, setItems] = useState<OperatorJobSummary[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [appliedStatus, setAppliedStatus] = useState("");
  const [appliedType, setAppliedType] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const requestPage = useCallback(
    (cursor?: string) => {
      const query = new URLSearchParams();
      if (appliedStatus) query.set("status", appliedStatus);
      if (appliedType) query.set("job_type", appliedType);
      if (cursor) query.set("cursor", cursor);
      const suffix = query.size ? `?${query}` : "";
      return client.request<OperatorJobListResponse>(`/operator/jobs${suffix}`);
    },
    [appliedStatus, appliedType, client],
  );

  useEffect(() => {
    if (status !== "authenticated") return;
    let active = true;
    void requestPage()
      .then((response) => {
        if (!active) return;
        setItems(response.items);
        setNextCursor(response.next_cursor);
      })
      .catch(() => {
        if (active) setError("Не вдалося завантажити Jobs. Повторіть спробу.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [requestPage, status]);

  const loadMore = async () => {
    if (!nextCursor) return;
    setLoading(true);
    setError(null);
    try {
      const response = await requestPage(nextCursor);
      setItems((current) => [...current, ...response.items]);
      setNextCursor(response.next_cursor);
    } catch {
      setError("Не вдалося завантажити наступну сторінку Jobs.");
    } finally {
      setLoading(false);
    }
  };

  const applyFilters = (event: FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setAppliedStatus(statusFilter);
    setAppliedType(typeFilter);
  };

  return (
    <section className="operations-page" aria-labelledby="operator-jobs-title">
      <div className="page-heading-row">
        <div>
          <p className="eyebrow">Platform Operations</p>
          <h1 id="operator-jobs-title">Jobs</h1>
          <p className="page-description">
            Стан виконання, безпечні помилки та історія спроб без payload і секретів.
          </p>
        </div>
      </div>
      <form className="operations-filters" onSubmit={applyFilters}>
        <label className="field-group">
          <span>Статус</span>
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="">Усі</option>
            {(["pending", "processing", "completed", "failed"] as BackgroundJobStatus[]).map(
              (value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ),
            )}
          </select>
        </label>
        <label className="field-group">
          <span>Тип Job</span>
          <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}>
            <option value="">Усі</option>
            {(
              [
                "invitation_email",
                "password_reset_email",
                "training_assignment_notification",
                "training_rollout_notification",
                "attempt_expiry",
                "retake_deadline_projection",
                "security_record_cleanup",
                "audit_retention",
              ] as BackgroundJobType[]
            ).map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
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
      {loading && !items.length ? <p aria-live="polite">Завантажуємо Jobs…</p> : null}
      {!loading && !items.length && !error ? (
        <div className="empty-state">
          <h2>Jobs за цими фільтрами немає</h2>
          <p>Черга не потребує уваги або фільтр надто вузький.</p>
        </div>
      ) : null}
      {items.length ? (
        <>
          <div className="desktop-table-wrap operations-table-wrap">
            <table className="data-table" aria-label="Операторські Jobs">
              <thead>
                <tr>
                  <th>Тип</th>
                  <th>Статус</th>
                  <th>Спроби</th>
                  <th>Оновлено</th>
                  <th>
                    <span className="sr-only">Дія</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <strong>{item.job_type}</strong>
                    </td>
                    <td>
                      <JobStatus status={item.status} />
                    </td>
                    <td>
                      {item.attempt_count}/{item.max_attempts}
                    </td>
                    <td>
                      <time dateTime={item.updated_at}>{formatDate(item.updated_at)}</time>
                    </td>
                    <td>
                      <Link className="text-link" to={`/operator/jobs/${item.id}`}>
                        Відкрити Job
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="operations-mobile-list" aria-label="Jobs — мобільний список">
            {items.map((item) => (
              <article className="operations-card" key={item.id}>
                <div className="operations-card-heading">
                  <strong>{item.job_type}</strong>
                  <JobStatus status={item.status} />
                </div>
                <p>
                  Спроби: {item.attempt_count}/{item.max_attempts}
                </p>
                <Link className="text-link" to={`/operator/jobs/${item.id}`}>
                  Відкрити Job
                </Link>
              </article>
            ))}
          </div>
        </>
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

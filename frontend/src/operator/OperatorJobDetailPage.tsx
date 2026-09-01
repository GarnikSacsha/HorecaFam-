import { FormEvent, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError, createIdempotencyKey } from "../api/client";
import type {
  OperatorJobDetail,
  OperatorJobRetryResponse,
  OperatorJobSummary,
} from "../api/contracts";
import { useSession } from "../session/SessionContext";
import { StatusPill } from "../ui/States";

function formatDate(value: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("uk-UA", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function JobSummary({ job }: { job: OperatorJobSummary }) {
  return (
    <dl className="operations-facts">
      <div>
        <dt>Статус</dt>
        <dd>
          <StatusPill tone={job.status === "failed" ? "danger" : "neutral"}>
            {job.status}
          </StatusPill>
        </dd>
      </div>
      <div>
        <dt>Тип</dt>
        <dd>{job.job_type}</dd>
      </div>
      <div>
        <dt>Спроби</dt>
        <dd>
          {job.attempt_count}/{job.max_attempts}
        </dd>
      </div>
      <div>
        <dt>Організація</dt>
        <dd>{job.organization_id ?? "Системний Job"}</dd>
      </div>
      <div>
        <dt>Наступний запуск</dt>
        <dd>{formatDate(job.next_run_at)}</dd>
      </div>
      <div>
        <dt>Помилка</dt>
        <dd>{job.last_error_code ?? "—"}</dd>
      </div>
    </dl>
  );
}

export function OperatorJobDetailPage() {
  const { jobId } = useParams();
  const { client, session, status } = useSession();
  const [job, setJob] = useState<OperatorJobDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryOpen, setRetryOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [retrying, setRetrying] = useState(false);
  const [retryResult, setRetryResult] = useState<OperatorJobRetryResponse | null>(null);
  const retryKeyRef = useRef<string | null>(null);
  const reasonRef = useRef<HTMLTextAreaElement>(null);
  const retryTriggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (status !== "authenticated" || !jobId) return;
    let active = true;
    void client
      .request<OperatorJobDetail>(`/operator/jobs/${jobId}`)
      .then((response) => {
        if (active) setJob(response);
      })
      .catch(() => {
        if (active) setError("Не вдалося завантажити Job.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [client, jobId, status]);

  useEffect(() => {
    if (retryOpen) reasonRef.current?.focus();
  }, [retryOpen]);

  const closeRetry = () => {
    setRetryOpen(false);
    setReason("");
    retryKeyRef.current = null;
    retryTriggerRef.current?.focus();
  };

  const submitRetry = async (event: FormEvent) => {
    event.preventDefault();
    if (!job || !session || !reason.trim()) return;
    setRetrying(true);
    setError(null);
    retryKeyRef.current ??= createIdempotencyKey();
    try {
      const response = await client.request<OperatorJobRetryResponse>(
        `/operator/jobs/${job.id}/retry`,
        {
          method: "POST",
          body: { reason: reason.trim() },
          csrfToken: session.csrf_token,
          idempotencyKey: retryKeyRef.current,
        },
      );
      setRetryResult(response);
      setRetryOpen(false);
      setReason("");
      retryKeyRef.current = null;
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === "JOB_NOT_RETRYABLE") {
        setError("Job уже не має Failed-статусу. Оновіть сторінку.");
      } else {
        setError("Повтор не створено. Причину збережено — спробуйте ще раз.");
      }
    } finally {
      setRetrying(false);
    }
  };

  if (loading) return <p aria-live="polite">Завантажуємо деталі Job…</p>;
  if (!job) {
    return (
      <section className="operations-page">
        <h1>Job недоступний</h1>
        <p className="inline-error" role="alert">
          {error ?? "Ресурс не знайдено."}
        </p>
      </section>
    );
  }

  return (
    <section className="operations-page" aria-labelledby="operator-job-title">
      <Link className="text-link" to="/operator/jobs">
        ← До списку Jobs
      </Link>
      <div className="page-heading-row">
        <div>
          <p className="eyebrow">Platform Operations</p>
          <h1 id="operator-job-title">Job detail</h1>
          <p className="operations-id">{job.id}</p>
        </div>
        {job.status === "failed" && !retryResult ? (
          <button
            className="button button-primary"
            type="button"
            onClick={() => setRetryOpen(true)}
            ref={retryTriggerRef}
          >
            Повторити Failed Job
          </button>
        ) : null}
      </div>
      <JobSummary job={job} />
      {job.last_error_message ? (
        <div className="operations-error-detail">
          <strong>{job.last_error_code}</strong>
          <p>{job.last_error_message}</p>
        </div>
      ) : null}
      {error ? (
        <p className="inline-error" role="alert">
          {error}
        </p>
      ) : null}
      {retryResult ? (
        <div className="operations-success" role="status">
          <strong>Створено контрольований повтор Job.</strong>
          <Link className="text-link" to={`/operator/jobs/${retryResult.job.id}`}>
            Відкрити новий Job
          </Link>
        </div>
      ) : null}
      {retryOpen ? (
        <form className="operations-retry-form" onSubmit={(event) => void submitRetry(event)}>
          <div>
            <h2>Підтвердьте контрольований повтор</h2>
            <p>Початковий Failed Job і його спроби залишаться незмінною історією.</p>
          </div>
          <label className="field-group">
            <span>Причина повтору</span>
            <textarea
              ref={reasonRef}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              minLength={1}
              maxLength={500}
              required
            />
          </label>
          <div className="operations-actions">
            <button className="button button-primary" type="submit" disabled={retrying}>
              {retrying ? "Створюємо…" : "Підтвердити повтор"}
            </button>
            <button className="button button-secondary" type="button" onClick={closeRetry}>
              Скасувати
            </button>
          </div>
        </form>
      ) : null}
      <section className="operations-section" aria-labelledby="attempts-title">
        <h2 id="attempts-title">Історія спроб</h2>
        {job.attempts.length ? (
          <ol className="operations-attempts">
            {job.attempts.map((attempt) => (
              <li key={attempt.id}>
                <div className="operations-card-heading">
                  <strong>Спроба {attempt.attempt_number}</strong>
                  <StatusPill tone={attempt.outcome === "failed" ? "danger" : "neutral"}>
                    {attempt.outcome}
                  </StatusPill>
                </div>
                <p>{formatDate(attempt.started_at)}</p>
                {attempt.error_code ? <p>{attempt.error_code}</p> : null}
              </li>
            ))}
          </ol>
        ) : (
          <p>Спроб ще немає.</p>
        )}
      </section>
      {job.delivery ? (
        <section className="operations-section" aria-labelledby="delivery-title">
          <h2 id="delivery-title">Delivery state</h2>
          <p>
            {job.delivery.provider}: {job.delivery.status}
          </p>
        </section>
      ) : null}
    </section>
  );
}

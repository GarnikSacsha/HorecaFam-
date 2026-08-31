import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import type { AdminEmployeeResultsDetailResponse } from "../api/contracts";
import { useSession } from "../session/SessionContext";
import { StatusPill } from "../ui/States";

export function AdminResultDetailPage() {
  const { employeeId } = useParams();
  const { client, session, status } = useSession();
  const organizationId = session?.organization_access.find(
    (item) => item.is_organization_admin,
  )?.organization_id;
  const [detail, setDetail] = useState<AdminEmployeeResultsDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status !== "authenticated" || !organizationId || !employeeId) return;
    client
      .request<AdminEmployeeResultsDetailResponse>(
        `/organizations/${organizationId}/results/employees/${employeeId}`,
      )
      .then(setDetail)
      .catch(() => setError("Не вдалося завантажити історію результатів."));
  }, [client, employeeId, organizationId, status]);

  if (error)
    return (
      <section className="admin-page">
        <p className="inline-error" role="alert">
          {error}
        </p>
      </section>
    );
  if (!detail) return <p aria-live="polite">Завантажуємо історію…</p>;
  const name =
    [detail.employee.first_name, detail.employee.last_name].filter(Boolean).join(" ") ||
    "Працівник";
  return (
    <section className="admin-page results-page" aria-labelledby="result-detail-title">
      <Link className="text-link" to="/admin/results">
        ← Усі результати
      </Link>
      <div>
        <p className="eyebrow">Історія працівника</p>
        <h1 id="result-detail-title">{name}</h1>
      </div>
      <section className="bounded-section" aria-labelledby="certification-title">
        <h2 id="certification-title">Сертифікація</h2>
        {detail.final_exam.certification ? (
          <StatusPill tone="success">Сертифіковано</StatusPill>
        ) : (
          <StatusPill tone="neutral">Не сертифіковано</StatusPill>
        )}
        {detail.final_exam.best ? (
          <p>
            Найкращий результат: <strong>{detail.final_exam.best.correct_count}/20</strong>
          </p>
        ) : (
          <p>Final Exam ще не завершувався.</p>
        )}
      </section>
      {detail.final_exam.history.length ? (
        <ol className="results-history-list">
          {detail.final_exam.history.map((result) => (
            <li key={result.result_id}>
              <strong>{result.correct_count}/20</strong>
              <span>{result.pass_status === "passed" ? "Passed" : "Failed"}</span>
              <time dateTime={result.completed_at}>
                {new Date(result.completed_at).toLocaleDateString("uk-UA")}
              </time>
              {result.critical_error_count ? (
                <span>Критичні помилки: {result.critical_error_count}</span>
              ) : null}
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}

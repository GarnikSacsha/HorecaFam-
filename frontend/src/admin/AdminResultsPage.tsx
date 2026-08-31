import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import type { AdminEmployeeResultRow, AdminResultsOverviewResponse } from "../api/contracts";
import { LogoutButton } from "../auth/LogoutButton";
import { useSession } from "../session/SessionContext";
import { StatusPill } from "../ui/States";

function employeeName(employee: AdminEmployeeResultRow) {
  return [employee.first_name, employee.last_name].filter(Boolean).join(" ") || "Працівник";
}

function ResultState({ employee }: { employee: AdminEmployeeResultRow }) {
  if (employee.certification) return <StatusPill tone="success">Сертифіковано</StatusPill>;
  if (employee.latest_final_exam?.pass_status === "failed") {
    return <StatusPill tone="warning">Потрібне повторення</StatusPill>;
  }
  return <StatusPill tone="neutral">Ще немає результату</StatusPill>;
}

export function AdminResultsPage() {
  const { client, session, status } = useSession();
  const organizationId = session?.organization_access.find(
    (access) => access.is_organization_admin,
  )?.organization_id;
  const [results, setResults] = useState<AdminEmployeeResultRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status !== "authenticated" || !organizationId) return;
    let active = true;
    void client
      .request<AdminResultsOverviewResponse>(`/organizations/${organizationId}/results`)
      .then((response) => {
        if (active) setResults(response.items);
      })
      .catch(() => {
        if (active) setError("Не вдалося завантажити результати.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [client, organizationId, status]);

  return (
    <section className="admin-page results-page" aria-labelledby="results-title">
      <div className="page-heading-row">
        <div>
          <p className="eyebrow">Навчання команди</p>
          <h1 id="results-title">Результати</h1>
          <p className="page-description">
            Поточний прогрес і незмінна історія сертифікації без рейтингу працівників.
          </p>
        </div>
        <LogoutButton />
      </div>
      {error ? (
        <p className="inline-error" role="alert">
          {error}
        </p>
      ) : null}
      {loading ? <p aria-live="polite">Завантажуємо результати…</p> : null}
      {!loading && !results.length ? (
        <div className="empty-state">
          <h2>Результатів ще немає</h2>
          <p>Вони з’являться після проходження навчання.</p>
        </div>
      ) : null}
      {results.length ? (
        <>
          <div className="desktop-table-wrap">
            <table className="data-table" aria-label="Результати працівників">
              <thead>
                <tr>
                  <th>Працівник</th>
                  <th>Навчання</th>
                  <th>Practice</th>
                  <th>Final Exam</th>
                  <th>
                    <span className="sr-only">Дія</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {results.map((employee) => (
                  <tr key={employee.employee_id}>
                    <td>
                      <strong>{employeeName(employee)}</strong>
                    </td>
                    <td>{employee.current_training_status ?? "Не призначено"}</td>
                    <td>
                      {employee.latest_practice_score_basis_points == null
                        ? "—"
                        : `${employee.latest_practice_score_basis_points / 100}%`}
                    </td>
                    <td>
                      <ResultState employee={employee} />
                    </td>
                    <td>
                      <Link className="text-link" to={`/admin/results/${employee.employee_id}`}>
                        Відкрити
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mobile-employee-list" aria-label="Результати — мобільний список">
            {results.map((employee) => (
              <article className="mobile-employee-row" key={employee.employee_id}>
                <strong>{employeeName(employee)}</strong>
                <ResultState employee={employee} />
                <p>
                  Practice:{" "}
                  {employee.latest_practice_score_basis_points == null
                    ? "—"
                    : `${employee.latest_practice_score_basis_points / 100}%`}
                </p>
                <Link className="text-link" to={`/admin/results/${employee.employee_id}`}>
                  Деталі результатів
                </Link>
              </article>
            ))}
          </div>
        </>
      ) : null}
    </section>
  );
}

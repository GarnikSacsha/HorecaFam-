import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { createIdempotencyKey } from "../api/client";
import type { EmployeeListResponse, EmployeeSummary, OrganizationSummary } from "../api/contracts";
import { LogoutButton } from "../auth/LogoutButton";
import { useSession } from "../session/SessionContext";
import { ErrorSummary } from "../ui/ErrorSummary";
import { StatusPill } from "../ui/States";
import { formErrors } from "../ui/formErrors";

const statusCopy = { pending: "Очікує", active: "Активний", disabled: "Вимкнено" } as const;

function EmployeeRows({ employees }: { employees: EmployeeSummary[] }) {
  return (
    <>
      <div className="desktop-table-wrap">
        <table className="data-table" aria-label="Працівники">
          <thead>
            <tr>
              <th>Працівник</th>
              <th>Роль</th>
              <th>Локація</th>
              <th>Статус</th>
              <th>
                <span className="sr-only">Дія</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {employees.map((employee) => (
              <tr key={employee.id}>
                <td>
                  <strong>
                    {[employee.first_name, employee.last_name].filter(Boolean).join(" ") ||
                      employee.email}
                  </strong>
                  <span>{employee.email}</span>
                </td>
                <td>{employee.operational_role?.name_uk ?? "Не призначено"}</td>
                <td>{employee.location?.name ?? "Не призначено"}</td>
                <td>
                  <StatusPill
                    tone={
                      employee.membership_status === "pending"
                        ? "warning"
                        : employee.membership_status === "active"
                          ? "success"
                          : "neutral"
                    }
                  >
                    {statusCopy[employee.membership_status]}
                  </StatusPill>
                </td>
                <td>
                  <Link className="text-link" to={`/admin/employees/${employee.id}`}>
                    Відкрити
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mobile-employee-list" aria-label="Працівники — мобільний список">
        {employees.map((employee) => (
          <article className="mobile-employee-row" key={employee.id}>
            <div>
              <strong>
                {[employee.first_name, employee.last_name].filter(Boolean).join(" ") ||
                  employee.email}
              </strong>
              <span>{employee.email}</span>
            </div>
            <StatusPill
              tone={
                employee.membership_status === "pending"
                  ? "warning"
                  : employee.membership_status === "active"
                    ? "success"
                    : "neutral"
              }
            >
              {statusCopy[employee.membership_status]}
            </StatusPill>
            <dl>
              <div>
                <dt>Роль</dt>
                <dd>{employee.operational_role?.name_uk ?? "Не призначено"}</dd>
              </div>
              <div>
                <dt>Локація</dt>
                <dd>{employee.location?.name ?? "Не призначено"}</dd>
              </div>
            </dl>
            <Link className="text-link" to={`/admin/employees/${employee.id}`}>
              Відкрити профіль
            </Link>
          </article>
        ))}
      </div>
    </>
  );
}

export function AdminEmployeesPage() {
  const { client, session, status } = useSession();
  const organizationId = session?.organization_access.find(
    (access) => access.is_organization_admin,
  )?.organization_id;
  const [organization, setOrganization] = useState<OrganizationSummary | null>(null);
  const [employees, setEmployees] = useState<EmployeeSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteErrors, setInviteErrors] = useState<ReturnType<typeof formErrors>>([]);
  const [inviteSuccess, setInviteSuccess] = useState<string | null>(null);
  const [inviting, setInviting] = useState(false);

  const loadEmployees = useCallback(
    async (search = "") => {
      if (!organizationId) return;
      const suffix = search.trim() ? `?query=${encodeURIComponent(search.trim())}` : "";
      try {
        const [organizationResponse, employeeResponse] = await Promise.all([
          client.request<OrganizationSummary>(`/organizations/${organizationId}`),
          client.request<EmployeeListResponse>(
            `/organizations/${organizationId}/employees${suffix}`,
          ),
        ]);
        setOrganization(organizationResponse);
        setEmployees(employeeResponse.items);
      } catch {
        setLoadError("Не вдалося завантажити працівників.");
      } finally {
        setLoading(false);
      }
    },
    [client, organizationId],
  );

  useEffect(() => {
    if (status === "authenticated") {
      // Початковий запит змінює UI-стан лише після асинхронної відповіді API.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      void loadEmployees();
    }
  }, [loadEmployees, status]);

  const invite = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!organizationId || !session) return;
    setInviteErrors([]);
    setInviteSuccess(null);
    setInviting(true);
    try {
      await client.request(`/organizations/${organizationId}/invitations`, {
        method: "POST",
        body: { email: inviteEmail },
        csrfToken: session.csrf_token,
        idempotencyKey: createIdempotencyKey(),
      });
      setInviteSuccess(`Запрошення створено для ${inviteEmail}`);
      setInviteEmail("");
    } catch (error) {
      setInviteErrors(formErrors(error, "email"));
    } finally {
      setInviting(false);
    }
  };

  return (
    <section className="admin-page" aria-labelledby="employees-title">
      <div className="page-heading-row">
        <div>
          <p className="eyebrow">{organization?.name ?? "Команда"}</p>
          <h1 id="employees-title">Працівники</h1>
          <p className="page-description">
            Запрошуйте людей і завершуйте їхнє налаштування перед окремою активацією.
          </p>
        </div>
        <LogoutButton />
      </div>
      <section className="bounded-section" aria-labelledby="invite-title">
        <div>
          <p className="eyebrow">Новий доступ</p>
          <h2 id="invite-title">Запросити працівника</h2>
        </div>
        <form className="inline-form" onSubmit={(event) => void invite(event)} noValidate>
          <ErrorSummary errors={inviteErrors} />
          <div className="field-group">
            <label htmlFor="email">Електронна пошта нового працівника</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              value={inviteEmail}
              onChange={(event) => setInviteEmail(event.target.value)}
              required
            />
          </div>
          <button className="button button-primary" type="submit" disabled={inviting}>
            {inviting ? "Створюємо…" : "Надіслати запрошення"}
          </button>
        </form>
        {inviteSuccess ? (
          <p className="success-message" role="status">
            {inviteSuccess}
          </p>
        ) : null}
      </section>
      <section className="dataset-section" aria-labelledby="team-list-title">
        <div className="dataset-header">
          <div>
            <p className="eyebrow">Поточний склад</p>
            <h2 id="team-list-title">Команда</h2>
          </div>
          <form
            className="search-form"
            onSubmit={(event) => {
              event.preventDefault();
              setLoading(true);
              setLoadError(null);
              void loadEmployees(query);
            }}
          >
            <label htmlFor="employee-search">Пошук</label>
            <input
              id="employee-search"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Ім’я або email"
            />
            <button className="button button-quiet" type="submit">
              Знайти
            </button>
          </form>
        </div>
        {loadError ? (
          <p className="inline-error" role="alert">
            {loadError}
          </p>
        ) : null}
        {loading ? (
          <p aria-live="polite">Завантажуємо працівників…</p>
        ) : employees.length > 0 ? (
          <EmployeeRows employees={employees} />
        ) : (
          <div className="empty-state">
            <h3>Працівників ще немає</h3>
            <p>Створіть перше запрошення, щоб розпочати налаштування команди.</p>
          </div>
        )}
      </section>
    </section>
  );
}

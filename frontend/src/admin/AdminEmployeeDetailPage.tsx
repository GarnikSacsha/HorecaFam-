import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { createIdempotencyKey } from "../api/client";
import type {
  EmployeeDetail,
  EmployeeLifecycleActionResponse,
  FieldError,
  LocationSummary,
  OperationalRoleSummary,
} from "../api/contracts";
import { LogoutButton } from "../auth/LogoutButton";
import { useSession } from "../session/SessionContext";
import { ConfirmDialog } from "../ui/ConfirmDialog";
import { ErrorSummary } from "../ui/ErrorSummary";
import { StatusPill } from "../ui/States";
import { fieldError, formErrors } from "../ui/formErrors";
import { AdminEmployeeTrainingPanel } from "./AdminEmployeeTrainingPanel";

export function AdminEmployeeDetailPage() {
  const { employeeId = "" } = useParams();
  const { client, session, status } = useSession();
  const organizationId = session?.organization_access.find(
    (access) => access.is_organization_admin,
  )?.organization_id;
  const [employee, setEmployee] = useState<EmployeeDetail | null>(null);
  const [roles, setRoles] = useState<OperationalRoleSummary[]>([]);
  const [locations, setLocations] = useState<LocationSummary[]>([]);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [roleId, setRoleId] = useState("");
  const [locationId, setLocationId] = useState("");
  const [errors, setErrors] = useState<FieldError[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [activating, setActivating] = useState(false);

  useEffect(() => {
    if (status !== "authenticated" || !organizationId || !employeeId) return;
    let active = true;
    Promise.all([
      client.request<EmployeeDetail>(`/organizations/${organizationId}/employees/${employeeId}`),
      client.request<LocationSummary[]>(`/organizations/${organizationId}/locations`),
      client.request<OperationalRoleSummary[]>(
        `/organizations/${organizationId}/operational-roles`,
      ),
    ])
      .then(([employeeResponse, locationResponse, roleResponse]) => {
        if (!active) return;
        setEmployee(employeeResponse);
        setLocations(locationResponse);
        setRoles(roleResponse);
        setFirstName(employeeResponse.first_name ?? "");
        setLastName(employeeResponse.last_name ?? "");
        setRoleId(employeeResponse.operational_role?.id ?? "");
        setLocationId(employeeResponse.location?.id ?? "");
        setLoading(false);
      })
      .catch(() => {
        if (active) {
          setErrors([
            { field: "profile", code: "LOAD_ERROR", message: "Не вдалося завантажити профіль." },
          ]);
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [client, employeeId, organizationId, status]);

  const save = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!organizationId || !employeeId || !session) return;
    setErrors([]);
    setMessage(null);
    setSaving(true);
    try {
      const updated = await client.request<EmployeeDetail>(
        `/organizations/${organizationId}/employees/${employeeId}`,
        {
          method: "PATCH",
          body: {
            first_name: firstName,
            last_name: lastName,
            operational_role_id: roleId || null,
            location_id: locationId || null,
          },
          csrfToken: session.csrf_token,
        },
      );
      setEmployee(updated);
      setMessage("Профіль збережено. Працівник ще очікує активації.");
    } catch (error) {
      setErrors(formErrors(error, "profile"));
    } finally {
      setSaving(false);
    }
  };

  const activate = async () => {
    if (!organizationId || !employeeId || !session) return;
    setErrors([]);
    setMessage(null);
    setActivating(true);
    try {
      const result = await client.request<EmployeeLifecycleActionResponse>(
        `/organizations/${organizationId}/employees/${employeeId}/activate`,
        { method: "POST", csrfToken: session.csrf_token, idempotencyKey: createIdempotencyKey() },
      );
      setEmployee((current) =>
        current
          ? {
              ...current,
              membership_status: result.membership_status,
              activated_at: result.activated_at,
            }
          : current,
      );
      setMessage("Працівника активовано");
      setConfirmOpen(false);
    } catch (error) {
      setErrors(formErrors(error, "profile"));
      setConfirmOpen(false);
    } finally {
      setActivating(false);
    }
  };

  if (loading) return <p aria-live="polite">Завантажуємо профіль…</p>;
  if (!employee)
    return (
      <div>
        <ErrorSummary errors={errors} />
        <Link className="text-link" to="/admin/employees">
          Повернутися до працівників
        </Link>
      </div>
    );
  const pending = employee.membership_status === "pending";
  return (
    <section className="admin-page employee-detail-page" aria-labelledby="employee-title">
      <Link className="back-link" to="/admin/employees">
        ← Працівники
      </Link>
      <div className="page-heading-row">
        <div>
          <p className="eyebrow">Профіль працівника</p>
          <h1 id="employee-title">
            {[employee.first_name, employee.last_name].filter(Boolean).join(" ") || employee.email}
          </h1>
          <p className="page-description">{employee.email}</p>
        </div>
        <div className="heading-actions">
          <StatusPill tone={pending ? "warning" : "success"}>
            {pending ? "Очікує" : "Активний"}
          </StatusPill>
          <LogoutButton />
        </div>
      </div>
      {message ? (
        <p className="success-message" role="status">
          {message}
        </p>
      ) : null}
      <ErrorSummary errors={errors} />
      <form className="profile-form" onSubmit={(event) => void save(event)} noValidate>
        <div className="field-grid">
          <div className="field-group">
            <label htmlFor="first_name">Ім’я</label>
            <input
              id="first_name"
              value={firstName}
              onChange={(event) => setFirstName(event.target.value)}
              disabled={!pending}
              aria-invalid={Boolean(fieldError(errors, "first_name"))}
            />
          </div>
          <div className="field-group">
            <label htmlFor="last_name">Прізвище</label>
            <input
              id="last_name"
              value={lastName}
              onChange={(event) => setLastName(event.target.value)}
              disabled={!pending}
              aria-invalid={Boolean(fieldError(errors, "last_name"))}
            />
          </div>
          <div className="field-group">
            <label htmlFor="operational_role_id">Роль</label>
            <select
              id="operational_role_id"
              value={roleId}
              onChange={(event) => setRoleId(event.target.value)}
              disabled={!pending}
            >
              <option value="">Оберіть роль</option>
              {roles
                .filter((role) => role.status === "active")
                .map((role) => (
                  <option key={role.id} value={role.id}>
                    {role.name_uk}
                  </option>
                ))}
            </select>
          </div>
          <div className="field-group">
            <label htmlFor="location_id">Локація</label>
            <select
              id="location_id"
              value={locationId}
              onChange={(event) => setLocationId(event.target.value)}
              disabled={!pending}
            >
              <option value="">Оберіть локацію</option>
              {locations
                .filter((location) => location.status === "active")
                .map((location) => (
                  <option key={location.id} value={location.id}>
                    {location.name}
                  </option>
                ))}
            </select>
          </div>
        </div>
        {pending ? (
          <div className="separate-actions">
            <button className="button button-quiet" type="submit" disabled={saving}>
              {saving ? "Зберігаємо…" : "Зберегти профіль"}
            </button>
            <div>
              <p>Активація — окрема дія. Вона відкриє працівнику активний доступ.</p>
              <button
                className="button button-primary"
                type="button"
                onClick={() => setConfirmOpen(true)}
                disabled={!employee.profile_complete}
              >
                Активувати працівника
              </button>
              {!employee.profile_complete ? (
                <span className="action-note">
                  Спочатку заповніть ім’я, прізвище, роль і локацію.
                </span>
              ) : null}
            </div>
          </div>
        ) : (
          <p className="success-message">
            Профіль активний. Історія активації зберігається на сервері.
          </p>
        )}
      </form>
      {!pending && session && organizationId ? (
        <AdminEmployeeTrainingPanel
          client={client}
          csrfToken={session.csrf_token}
          employeeId={employeeId}
          organizationId={organizationId}
        />
      ) : null}
      <ConfirmDialog
        open={confirmOpen}
        title="Активувати працівника?"
        description="Профіль уже збережено. Після підтвердження сервер окремо змінить Membership з Pending на Active."
        confirmLabel="Підтвердити активацію"
        busy={activating}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => void activate()}
      />
    </section>
  );
}

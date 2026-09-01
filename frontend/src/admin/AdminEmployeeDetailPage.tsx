import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { createIdempotencyKey } from "../api/client";
import type {
  EmployeeDetail,
  EmployeeLifecycleActionResponse,
  EmployeeLifecycleStateResponse,
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

type LifecycleAction = "disable" | "reactivate" | "pause" | "resume";

const lifecycleCopy: Record<
  LifecycleAction,
  { title: string; description: string; confirmLabel: string; success: string }
> = {
  disable: {
    title: "Вимкнути доступ працівника?",
    description:
      "Активні сесії буде відкликано, а навчання і повторні спроби заморожено. Історія працівника збережеться.",
    confirmLabel: "Підтвердити вимкнення",
    success: "Доступ працівника вимкнено",
  },
  reactivate: {
    title: "Відновити доступ працівника?",
    description:
      "Сервер повторно перевірить профіль, роль і локацію. Нова сесія автоматично не створюється.",
    confirmLabel: "Підтвердити відновлення",
    success: "Доступ працівника відновлено",
  },
  pause: {
    title: "Призупинити навчання?",
    description:
      "Поточне навчання та строки повторних спроб буде заморожено до окремого відновлення.",
    confirmLabel: "Підтвердити паузу",
    success: "Навчання працівника призупинено",
  },
  resume: {
    title: "Відновити навчання?",
    description:
      "Сервер відновить навчання і зсуне строки повторних спроб на точну тривалість паузи.",
    confirmLabel: "Підтвердити відновлення",
    success: "Навчання працівника відновлено",
  },
};

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
  const [lifecycleAction, setLifecycleAction] = useState<LifecycleAction | null>(null);
  const [lifecycleBusy, setLifecycleBusy] = useState(false);
  const [reasonCode, setReasonCode] = useState("");
  const [lifecycleNote, setLifecycleNote] = useState("");
  const [plannedResumeAt, setPlannedResumeAt] = useState("");

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

  const executeLifecycleAction = async () => {
    if (!organizationId || !employeeId || !session || !lifecycleAction) return;
    const action = lifecycleAction;
    const includesReason = action === "disable" || action === "pause";
    const body = includesReason
      ? {
          reason_code: reasonCode || null,
          note: lifecycleNote.trim() || null,
          ...(action === "pause"
            ? {
                planned_resume_at: plannedResumeAt ? new Date(plannedResumeAt).toISOString() : null,
              }
            : {}),
        }
      : undefined;
    setErrors([]);
    setMessage(null);
    setLifecycleBusy(true);
    try {
      const result = await client.request<EmployeeLifecycleStateResponse>(
        `/organizations/${organizationId}/employees/${employeeId}/${action}`,
        {
          method: "POST",
          body,
          csrfToken: session.csrf_token,
          idempotencyKey: createIdempotencyKey(),
        },
      );
      setEmployee((current) =>
        current
          ? {
              ...current,
              membership_status: result.membership_status,
              training_participation_status: result.training_participation_status,
              activated_at: result.activated_at,
              disabled_at: result.disabled_at,
              training_paused_at: result.training_paused_at,
              training_pause_reason_code: result.training_pause_reason_code,
              training_pause_note: result.training_pause_note,
              planned_resume_at: result.planned_resume_at,
              disabled_reason_code: result.disabled_reason_code,
              disabled_note: result.disabled_note,
            }
          : current,
      );
      setMessage(lifecycleCopy[action].success);
      setReasonCode("");
      setLifecycleNote("");
      setPlannedResumeAt("");
      setLifecycleAction(null);
    } catch (error) {
      setErrors(formErrors(error, "lifecycle"));
      setLifecycleAction(null);
    } finally {
      setLifecycleBusy(false);
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
  const disabled = employee.membership_status === "disabled";
  const paused = employee.training_participation_status === "paused";
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
          <StatusPill tone={pending ? "warning" : disabled ? "danger" : "success"}>
            {pending ? "Очікує" : disabled ? "Доступ вимкнено" : "Активний"}
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
        ) : disabled ? (
          <p className="action-note">Профіль і вся історія збережені, але доступ вимкнено.</p>
        ) : (
          <p className="success-message">
            Профіль активний. Історія активації зберігається на сервері.
          </p>
        )}
      </form>
      <section className="lifecycle-panel" aria-labelledby="employee-lifecycle-title">
        <div className="lifecycle-heading">
          <div>
            <p className="eyebrow">Керування станом</p>
            <h2 id="employee-lifecycle-title">Доступ і навчання</h2>
          </div>
          <StatusPill tone={paused ? "warning" : "success"}>
            {paused ? "Навчання призупинено" : "Навчання активне"}
          </StatusPill>
        </div>

        {paused ? (
          <dl className="lifecycle-facts">
            <div>
              <dt>Причина паузи</dt>
              <dd>{employee.training_pause_reason_code ?? "Не вказано"}</dd>
            </div>
            <div>
              <dt>Примітка</dt>
              <dd>{employee.training_pause_note ?? "Не вказано"}</dd>
            </div>
            <div>
              <dt>Заплановане відновлення</dt>
              <dd>
                {employee.planned_resume_at
                  ? new Date(employee.planned_resume_at).toLocaleString("uk-UA")
                  : "Не заплановано"}
              </dd>
            </div>
          </dl>
        ) : null}

        {disabled ? (
          <dl className="lifecycle-facts">
            <div>
              <dt>Причина вимкнення</dt>
              <dd>{employee.disabled_reason_code ?? "Не вказано"}</dd>
            </div>
            <div>
              <dt>Примітка</dt>
              <dd>{employee.disabled_note ?? "Не вказано"}</dd>
            </div>
          </dl>
        ) : null}

        {!disabled ? (
          <div className="lifecycle-fields">
            <div className="field-group">
              <label htmlFor="lifecycle-reason">Причина</label>
              <select
                id="lifecycle-reason"
                value={reasonCode}
                onChange={(event) => setReasonCode(event.target.value)}
              >
                <option value="">Не вказувати</option>
                <option value="scheduled_leave">Запланована відсутність</option>
                <option value="leave">Тимчасова відсутність</option>
                <option value="access_review">Перевірка доступу</option>
                <option value="other">Інша</option>
              </select>
            </div>
            <div className="field-group lifecycle-note-field">
              <label htmlFor="lifecycle-note">Примітка</label>
              <textarea
                id="lifecycle-note"
                value={lifecycleNote}
                onChange={(event) => setLifecycleNote(event.target.value)}
                maxLength={500}
              />
            </div>
            {!paused && !pending ? (
              <div className="field-group">
                <label htmlFor="planned-resume-at">Заплановане відновлення</label>
                <input
                  id="planned-resume-at"
                  type="datetime-local"
                  value={plannedResumeAt}
                  onChange={(event) => setPlannedResumeAt(event.target.value)}
                />
              </div>
            ) : null}
          </div>
        ) : null}

        <div className="lifecycle-actions">
          {disabled ? (
            <button
              className="button button-primary"
              type="button"
              onClick={() => setLifecycleAction("reactivate")}
            >
              Відновити доступ
            </button>
          ) : (
            <>
              {!pending ? (
                <button
                  className="button button-quiet"
                  type="button"
                  onClick={() => setLifecycleAction(paused ? "resume" : "pause")}
                >
                  {paused ? "Відновити навчання" : "Призупинити навчання"}
                </button>
              ) : null}
              <button
                className="button button-danger"
                type="button"
                onClick={() => setLifecycleAction("disable")}
              >
                Вимкнути доступ
              </button>
            </>
          )}
        </div>
      </section>
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
      <ConfirmDialog
        open={lifecycleAction !== null}
        title={lifecycleAction ? lifecycleCopy[lifecycleAction].title : "Підтвердити дію?"}
        description={
          lifecycleAction
            ? lifecycleCopy[lifecycleAction].description
            : "Підтвердіть зміну стану працівника."
        }
        confirmLabel={lifecycleAction ? lifecycleCopy[lifecycleAction].confirmLabel : "Підтвердити"}
        busy={lifecycleBusy}
        onCancel={() => setLifecycleAction(null)}
        onConfirm={() => void executeLifecycleAction()}
      />
    </section>
  );
}

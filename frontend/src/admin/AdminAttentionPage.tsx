import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { createIdempotencyKey } from "../api/client";
import type {
  AdminAttentionCase,
  AdminAttentionCollection,
  AdminRetakeRequirement,
  AdminRetakeRequirementCollection,
} from "../api/contracts";
import { LogoutButton } from "../auth/LogoutButton";
import { useSession } from "../session/SessionContext";
import { StatusPill } from "../ui/States";

const timingCopy = {
  scheduled: "Заплановано",
  approaching: "До 48 годин",
  overdue: "Прострочено",
  frozen: "Час призупинено",
} as const;

function formatDate(value: string) {
  return new Intl.DateTimeFormat("uk-UA", { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(value),
  );
}

function defaultDueAt() {
  const value = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);
  return new Date(value.getTime() - value.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

export function AdminAttentionPage() {
  const { client, session, status } = useSession();
  const organizationId = session?.organization_access.find(
    (access) => access.is_organization_admin,
  )?.organization_id;
  const [cases, setCases] = useState<AdminAttentionCase[]>([]);
  const [requirements, setRequirements] = useState<AdminRetakeRequirement[]>([]);
  const [stateFilter, setStateFilter] = useState("current");
  const [typeFilter, setTypeFilter] = useState("all");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [caseLocationFilter, setCaseLocationFilter] = useState("all");
  const [requirementStateFilter, setRequirementStateFilter] = useState("current");
  const [reasonFilter, setReasonFilter] = useState("all");
  const [timingFilter, setTimingFilter] = useState("all");
  const [requirementLocationFilter, setRequirementLocationFilter] = useState("all");
  const [selectedCase, setSelectedCase] = useState<AdminAttentionCase | null>(null);
  const [selectedRequirement, setSelectedRequirement] = useState<AdminRetakeRequirement | null>(
    null,
  );
  const [comment, setComment] = useState("");
  const [dueAt, setDueAt] = useState("");
  const [createReason, setCreateReason] = useState<"critical_error" | "management_follow_up">(
    "critical_error",
  );
  const [sourceCaseId, setSourceCaseId] = useState("");
  const [createEmployeeId, setCreateEmployeeId] = useState("");
  const [managementSourceKey, setManagementSourceKey] = useState("");
  const [proposalDueAt, setProposalDueAt] = useState(defaultDueAt);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status !== "authenticated" || !organizationId) return;
    let active = true;
    Promise.all([
      client.request<AdminAttentionCollection>(`/organizations/${organizationId}/attention`),
      client.request<AdminRetakeRequirementCollection>(
        `/organizations/${organizationId}/retake-requirements`,
      ),
    ])
      .then(([attention, retakes]) => {
        if (!active) return;
        setCases(attention.items);
        setRequirements(retakes.items);
      })
      .catch(() => {
        if (active) setError("Не вдалося завантажити чергу. Повторіть спробу.");
      });
    return () => {
      active = false;
    };
  }, [client, organizationId, status]);

  const visibleCases = useMemo(
    () =>
      cases.filter((item) => {
        const stateMatches =
          stateFilter === "current" ? item.state !== "resolved" : item.state === stateFilter;
        return (
          stateMatches &&
          (typeFilter === "all" || item.case_type === typeFilter) &&
          (severityFilter === "all" || item.severity === severityFilter) &&
          (caseLocationFilter === "all" || item.location_id === caseLocationFilter)
        );
      }),
    [caseLocationFilter, cases, severityFilter, stateFilter, typeFilter],
  );

  const visibleRequirements = useMemo(
    () =>
      requirements.filter((item) => {
        const stateMatches =
          requirementStateFilter === "current"
            ? item.state === "proposed" || item.state === "active"
            : item.state === requirementStateFilter;
        return (
          stateMatches &&
          (reasonFilter === "all" || item.reason === reasonFilter) &&
          (timingFilter === "all" || item.timing_state === timingFilter) &&
          (requirementLocationFilter === "all" || item.location_id === requirementLocationFilter)
        );
      }),
    [reasonFilter, requirementLocationFilter, requirementStateFilter, requirements, timingFilter],
  );

  const criticalSources = useMemo(
    () =>
      cases.filter((item) => item.case_type === "critical_allergen" && item.state !== "resolved"),
    [cases],
  );

  const caseLocations = useMemo(
    () => Array.from(new Set(cases.map((item) => item.location_id))),
    [cases],
  );
  const requirementLocations = useMemo(
    () => Array.from(new Set(requirements.map((item) => item.location_id))),
    [requirements],
  );

  const mutateCase = async (item: AdminAttentionCase, action: "acknowledge" | "resolve") => {
    if (!session || !organizationId) return;
    setBusy(true);
    setError(null);
    try {
      const payload =
        action === "acknowledge"
          ? { expected_revision: item.revision }
          : {
              expected_revision: item.revision,
              resolution_type: "admin_follow_up",
              comment,
              evidence_attempt_id: null,
            };
      const updated = await client.request<AdminAttentionCase>(
        `/organizations/${organizationId}/attention/${item.id}/${action}`,
        {
          method: "POST",
          body: payload,
          csrfToken: session.csrf_token,
          idempotencyKey: createIdempotencyKey(),
        },
      );
      setCases((current) => current.map((entry) => (entry.id === updated.id ? updated : entry)));
      setSelectedCase(updated);
      setComment("");
      setMessage(action === "acknowledge" ? "Кейс взято в роботу." : "Кейс завершено.");
    } catch {
      setError("Дію не виконано. Дані в черзі не змінено.");
    } finally {
      setBusy(false);
    }
  };

  const mutateRequirement = async (
    item: AdminRetakeRequirement,
    action: "edit" | "confirm" | "cancel",
  ) => {
    if (!session || !organizationId) return;
    setBusy(true);
    setError(null);
    const path = `/organizations/${organizationId}/retake-requirements/${item.id}${
      action === "edit" ? "" : `/${action}`
    }`;
    const body =
      action === "edit"
        ? { expected_revision: item.revision, due_at: new Date(dueAt).toISOString() }
        : action === "cancel"
          ? { expected_revision: item.revision, comment }
          : { expected_revision: item.revision };
    try {
      const updated = await client.request<AdminRetakeRequirement>(path, {
        method: action === "edit" ? "PATCH" : "POST",
        body,
        csrfToken: session.csrf_token,
        idempotencyKey: createIdempotencyKey(),
      });
      setRequirements((current) =>
        current.map((entry) => (entry.id === updated.id ? updated : entry)),
      );
      setSelectedRequirement(updated);
      setComment("");
      setMessage("Вимогу оновлено.");
    } catch {
      setError("Вимогу не змінено. Перевірте дедлайн або актуальність даних.");
    } finally {
      setBusy(false);
    }
  };

  const createRequirement = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!session || !organizationId) return;
    const sourceCase = criticalSources.find((item) => item.id === sourceCaseId) ?? null;
    const employeeId =
      createReason === "critical_error" ? sourceCase?.employee_profile_id : createEmployeeId.trim();
    if (!employeeId) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const created = await client.request<AdminRetakeRequirement>(
        `/organizations/${organizationId}/employees/${employeeId}/retake-requirements`,
        {
          method: "POST",
          body: {
            reason: createReason,
            source_attention_case_id:
              createReason === "critical_error" ? (sourceCase?.id ?? null) : null,
            management_source_key:
              createReason === "management_follow_up" ? managementSourceKey.trim() : null,
            target_policy: {
              assessment_type: "menu_final_exam",
              minimum_result: "passed",
              required_subject_keys:
                createReason === "critical_error" && sourceCase?.subject_key
                  ? [sourceCase.subject_key]
                  : [],
            },
            due_at: new Date(proposalDueAt).toISOString(),
          },
          csrfToken: session.csrf_token,
          idempotencyKey: createIdempotencyKey(),
        },
      );
      setRequirements((current) => [created, ...current]);
      setSelectedRequirement(created);
      setDueAt(created.due_at.slice(0, 16));
      setManagementSourceKey("");
      setMessage("Проєкт вимоги створено. Перевірте дедлайн і підтвердьте окремою дією.");
    } catch {
      setError("Проєкт вимоги не створено. Перевірте джерело та поточне призначення навчання.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="admin-page attention-page" aria-labelledby="attention-title">
      <div className="page-heading-row">
        <div>
          <p className="eyebrow">Безпечний follow-up</p>
          <h1 id="attention-title">Attention і перескладання</h1>
          <p className="page-description">
            Окрема робоча черга без рейтингу, покарань і зміни збережених результатів.
          </p>
        </div>
        <LogoutButton />
      </div>
      {message ? (
        <p className="success-message" role="status" aria-atomic="true">
          {message}
        </p>
      ) : null}
      {error ? (
        <p className="inline-error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="queue-filter-grid">
        <div className="field-group">
          <label htmlFor="attention-state">Стан кейсів</label>
          <select
            id="attention-state"
            value={stateFilter}
            onChange={(event) => setStateFilter(event.target.value)}
          >
            <option value="current">Відкриті та в роботі</option>
            <option value="open">Відкриті</option>
            <option value="acknowledged">В роботі</option>
            <option value="resolved">Завершені</option>
          </select>
        </div>
        <div className="field-group">
          <label htmlFor="attention-type">Тип</label>
          <select
            id="attention-type"
            value={typeFilter}
            onChange={(event) => setTypeFilter(event.target.value)}
          >
            <option value="all">Усі типи</option>
            <option value="critical_allergen">Критичний алерген</option>
            <option value="retake_overdue">Прострочене перескладання</option>
          </select>
        </div>
        <div className="field-group">
          <label htmlFor="attention-severity">Пріоритет</label>
          <select
            id="attention-severity"
            value={severityFilter}
            onChange={(event) => setSeverityFilter(event.target.value)}
          >
            <option value="all">Усі</option>
            <option value="critical">Критичні</option>
            <option value="overdue">Прострочені</option>
          </select>
        </div>
        <div className="field-group">
          <label htmlFor="attention-location">Локація</label>
          <select
            id="attention-location"
            value={caseLocationFilter}
            onChange={(event) => setCaseLocationFilter(event.target.value)}
          >
            <option value="all">Усі локації</option>
            {caseLocations.map((locationId) => (
              <option key={locationId} value={locationId}>
                {locationId.slice(0, 8)}
              </option>
            ))}
          </select>
        </div>
      </div>

      <section className="queue-section" aria-labelledby="attention-queue-title">
        <h2 id="attention-queue-title">Черга Attention</h2>
        {!visibleCases.length ? <p className="quiet-note">За цим фільтром кейсів немає.</p> : null}
        <div className="desktop-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Тип</th>
                <th>Стан</th>
                <th>Працівник</th>
                <th>Створено</th>
                <th>
                  <span className="sr-only">Дія</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {visibleCases.map((item) => (
                <tr key={item.id}>
                  <td>
                    {item.case_type === "critical_allergen"
                      ? "Критичний алерген"
                      : "Дедлайн перескладання"}
                  </td>
                  <td>
                    <StatusPill tone={item.severity === "critical" ? "warning" : "neutral"}>
                      {item.state}
                    </StatusPill>
                  </td>
                  <td>
                    <code>{item.employee_profile_id.slice(0, 8)}</code>
                  </td>
                  <td>{formatDate(item.created_at)}</td>
                  <td>
                    <button
                      className="text-link button-link"
                      type="button"
                      onClick={() => setSelectedCase(item)}
                    >
                      Відкрити
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mobile-employee-list">
          {visibleCases.map((item) => (
            <article className="mobile-employee-row" key={item.id}>
              <strong>
                {item.case_type === "critical_allergen"
                  ? "Критичний алерген"
                  : "Прострочене перескладання"}
              </strong>
              <StatusPill tone={item.severity === "critical" ? "warning" : "neutral"}>
                {item.state}
              </StatusPill>
              <button
                className="button button-quiet"
                type="button"
                onClick={() => setSelectedCase(item)}
              >
                Відкрити кейс
              </button>
            </article>
          ))}
        </div>
      </section>

      {selectedCase ? (
        <section className="follow-up-detail" aria-labelledby="case-detail-title">
          <div>
            <p className="eyebrow">Обраний кейс</p>
            <h2 id="case-detail-title">
              {selectedCase.case_type === "critical_allergen"
                ? "Перевірка безпеки"
                : "Прострочене перескладання"}
            </h2>
            <p>
              Джерел: {selectedCase.critical_error_ids.length || 1}. Перегляд не завершує кейс
              автоматично.
            </p>
            <Link className="text-link" to={`/admin/results/${selectedCase.employee_profile_id}`}>
              Переглянути незмінну історію результатів
            </Link>
          </div>
          {selectedCase.state === "open" ? (
            <button
              className="button button-secondary"
              disabled={busy}
              type="button"
              onClick={() => void mutateCase(selectedCase, "acknowledge")}
            >
              Взяти в роботу
            </button>
          ) : null}
          {selectedCase.state !== "resolved" && selectedCase.case_type === "critical_allergen" ? (
            <div className="field-group">
              <label htmlFor="resolution-comment">Підсумок follow-up</label>
              <textarea
                id="resolution-comment"
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                rows={3}
              />
              <button
                className="button button-primary"
                disabled={busy || !comment.trim()}
                type="button"
                onClick={() => void mutateCase(selectedCase, "resolve")}
              >
                Завершити після розмови
              </button>
            </div>
          ) : null}
        </section>
      ) : null}

      <section className="bounded-section" aria-labelledby="create-requirement-title">
        <div>
          <p className="eyebrow">Окреме рішення адміністратора</p>
          <h2 id="create-requirement-title">Створити проєкт вимоги</h2>
          <p>Проєкт ще не видимий працівнику. Дедлайн і активація підтверджуються окремо.</p>
        </div>
        <form className="follow-up-form" onSubmit={(event) => void createRequirement(event)}>
          <div className="field-group">
            <label htmlFor="requirement-reason">Причина</label>
            <select
              id="requirement-reason"
              value={createReason}
              onChange={(event) => setCreateReason(event.target.value as typeof createReason)}
            >
              <option value="critical_error">Критична помилка</option>
              <option value="management_follow_up">Управлінський follow-up</option>
            </select>
          </div>
          {createReason === "critical_error" ? (
            <div className="field-group">
              <label htmlFor="requirement-source">Джерело Attention</label>
              <select
                id="requirement-source"
                value={sourceCaseId}
                onChange={(event) => setSourceCaseId(event.target.value)}
                required
              >
                <option value="">Оберіть відкритий критичний кейс</option>
                {criticalSources.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.employee_profile_id.slice(0, 8)} · {item.subject_key ?? "алерген"}
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <>
              <div className="field-group">
                <label htmlFor="requirement-employee">ID працівника</label>
                <input
                  id="requirement-employee"
                  value={createEmployeeId}
                  onChange={(event) => setCreateEmployeeId(event.target.value)}
                  required
                />
              </div>
              <div className="field-group">
                <label htmlFor="management-source">Ключ рішення</label>
                <input
                  id="management-source"
                  value={managementSourceKey}
                  onChange={(event) => setManagementSourceKey(event.target.value)}
                  maxLength={200}
                  required
                />
              </div>
            </>
          )}
          <div className="field-group">
            <label htmlFor="proposal-due">Запропонований дедлайн</label>
            <input
              id="proposal-due"
              type="datetime-local"
              value={proposalDueAt}
              onChange={(event) => setProposalDueAt(event.target.value)}
              required
            />
          </div>
          <button
            className="button button-primary"
            type="submit"
            disabled={
              busy ||
              !proposalDueAt ||
              (createReason === "critical_error"
                ? !sourceCaseId
                : !createEmployeeId.trim() || !managementSourceKey.trim())
            }
          >
            Створити проєкт
          </button>
        </form>
      </section>

      <section className="queue-section" aria-labelledby="retake-queue-title">
        <h2 id="retake-queue-title">Вимоги перескладання</h2>
        <div className="queue-filter-grid">
          <div className="field-group">
            <label htmlFor="retake-state-filter">Стан</label>
            <select
              id="retake-state-filter"
              value={requirementStateFilter}
              onChange={(event) => setRequirementStateFilter(event.target.value)}
            >
              <option value="current">Поточні</option>
              <option value="proposed">Проєкти</option>
              <option value="active">Активні</option>
              <option value="completed">Завершені</option>
              <option value="cancelled">Скасовані</option>
            </select>
          </div>
          <div className="field-group">
            <label htmlFor="retake-reason-filter">Причина</label>
            <select
              id="retake-reason-filter"
              value={reasonFilter}
              onChange={(event) => setReasonFilter(event.target.value)}
            >
              <option value="all">Усі</option>
              <option value="failed_exam">Невдалий іспит</option>
              <option value="critical_error">Критична помилка</option>
              <option value="management_follow_up">Управлінський follow-up</option>
            </select>
          </div>
          <div className="field-group">
            <label htmlFor="retake-timing-filter">Час</label>
            <select
              id="retake-timing-filter"
              value={timingFilter}
              onChange={(event) => setTimingFilter(event.target.value)}
            >
              <option value="all">Будь-який</option>
              <option value="scheduled">Заплановано</option>
              <option value="approaching">До 48 годин</option>
              <option value="overdue">Прострочено</option>
              <option value="frozen">Призупинено</option>
            </select>
          </div>
          <div className="field-group">
            <label htmlFor="retake-location-filter">Локація</label>
            <select
              id="retake-location-filter"
              value={requirementLocationFilter}
              onChange={(event) => setRequirementLocationFilter(event.target.value)}
            >
              <option value="all">Усі локації</option>
              {requirementLocations.map((locationId) => (
                <option key={locationId} value={locationId}>
                  {locationId.slice(0, 8)}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="queue-card-grid">
          {visibleRequirements.map((item) => (
            <button
              className="queue-card"
              type="button"
              key={item.id}
              onClick={() => {
                setSelectedRequirement(item);
                setDueAt(item.due_at.slice(0, 16));
              }}
            >
              <span>
                <strong>{item.reason}</strong>
                <StatusPill tone={item.timing_state === "overdue" ? "warning" : "neutral"}>
                  {item.state}
                </StatusPill>
              </span>
              <span>
                {item.timing_state ? timingCopy[item.timing_state] : "Історія"} ·{" "}
                {formatDate(item.due_at)}
              </span>
            </button>
          ))}
        </div>
      </section>

      {selectedRequirement ? (
        <section className="follow-up-detail" aria-labelledby="requirement-detail-title">
          <h2 id="requirement-detail-title">Керування вимогою</h2>
          <Link
            className="text-link"
            to={`/admin/results/${selectedRequirement.employee_profile_id}`}
          >
            Переглянути незмінну історію результатів
          </Link>
          {selectedRequirement.state === "proposed" ? (
            <>
              <div className="field-group">
                <label htmlFor="retake-due">Дедлайн</label>
                <input
                  id="retake-due"
                  type="datetime-local"
                  value={dueAt}
                  onChange={(event) => setDueAt(event.target.value)}
                />
              </div>
              <div className="compact-actions">
                <button
                  className="button button-secondary"
                  disabled={busy || !dueAt}
                  type="button"
                  onClick={() => void mutateRequirement(selectedRequirement, "edit")}
                >
                  Зберегти дедлайн
                </button>
                <button
                  className="button button-primary"
                  disabled={busy}
                  type="button"
                  onClick={() => void mutateRequirement(selectedRequirement, "confirm")}
                >
                  Підтвердити вимогу
                </button>
              </div>
            </>
          ) : null}
          {selectedRequirement.state === "active" ? (
            <div className="field-group">
              <label htmlFor="cancel-comment">Причина скасування</label>
              <textarea
                id="cancel-comment"
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                rows={3}
              />
              <button
                className="button button-quiet"
                disabled={busy || !comment.trim()}
                type="button"
                onClick={() => void mutateRequirement(selectedRequirement, "cancel")}
              >
                Скасувати вимогу
              </button>
            </div>
          ) : null}
        </section>
      ) : null}
    </section>
  );
}

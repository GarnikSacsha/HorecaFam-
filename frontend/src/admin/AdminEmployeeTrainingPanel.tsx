import { useCallback, useEffect, useState } from "react";

import { createIdempotencyKey } from "../api/client";
import type { ApiClient } from "../api/client";
import type { TrainingAssignmentListResponse, TrainingAssignmentResponse } from "../api/contracts";
import { ConfirmDialog } from "../ui/ConfirmDialog";
import { StatusPill } from "../ui/States";

const assignmentStatusLabel = {
  assigned: "Призначено",
  in_progress: "У процесі",
  completed: "Завершено",
  revoked: "Відкликано",
};

interface AdminEmployeeTrainingPanelProps {
  client: ApiClient;
  csrfToken: string;
  employeeId: string;
  organizationId: string;
}

export function AdminEmployeeTrainingPanel({
  client,
  csrfToken,
  employeeId,
  organizationId,
}: AdminEmployeeTrainingPanelProps) {
  const [assignments, setAssignments] = useState<TrainingAssignmentListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [revokeReason, setRevokeReason] = useState("");
  const [revokeOpen, setRevokeOpen] = useState(false);
  const base = `/organizations/${organizationId}/employees/${employeeId}/training-assignments`;

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setAssignments(await client.request<TrainingAssignmentListResponse>(base));
      setError(null);
    } catch {
      setError("Не вдалося завантажити призначення навчання.");
    } finally {
      setLoading(false);
    }
  }, [base, client]);

  useEffect(() => {
    // Історія призначень належить серверу, тому локально не відтворюємо її припущеннями.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  const mutate = async (path: string, body: Record<string, unknown>, successMessage: string) => {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await client.request<TrainingAssignmentResponse>(path, {
        method: "POST",
        body,
        csrfToken,
        idempotencyKey: createIdempotencyKey(),
      });
      await refresh();
      setMessage(successMessage);
    } catch {
      setError("Дію з призначенням не виконано. Оновіть дані та спробуйте ще раз.");
    } finally {
      setBusy(false);
    }
  };

  const current = assignments?.current ?? null;
  const latestRevoked = assignments?.history.find((item) => item.status === "revoked") ?? null;

  return (
    <section className="employee-training-panel" aria-labelledby="employee-training-title">
      <div className="training-panel-heading">
        <div>
          <p className="eyebrow">Поточне зобов’язання</p>
          <h2 id="employee-training-title">Призначення навчання</h2>
        </div>
        {current ? (
          <StatusPill tone={current.status === "completed" ? "success" : "warning"}>
            {assignmentStatusLabel[current.status]}
          </StatusPill>
        ) : (
          <StatusPill>Не призначено</StatusPill>
        )}
      </div>

      {loading ? <p aria-live="polite">Завантажуємо призначення…</p> : null}
      {error ? (
        <p className="inline-error" role="alert">
          {error}
        </p>
      ) : null}
      {message ? (
        <p className="success-message" role="status">
          {message}
        </p>
      ) : null}

      {!loading && assignments ? (
        current ? (
          <div className="assignment-current">
            <p>
              Версія <code>{current.training_version_id}</code>
            </p>
            {assignments.progress ? (
              <p>
                {assignments.progress.completed_required_lesson_count} із{" "}
                {assignments.progress.required_lesson_count} обов’язкових уроків ·{" "}
                {assignments.progress.percentage}%
              </p>
            ) : null}
            <div className="field-group">
              <label htmlFor="assignment-revoke-reason">Причина відкликання</label>
              <textarea
                id="assignment-revoke-reason"
                value={revokeReason}
                onChange={(event) => setRevokeReason(event.target.value)}
                maxLength={500}
                required
              />
            </div>
            <button
              className="button button-danger"
              type="button"
              disabled={!revokeReason.trim() || busy}
              onClick={() => setRevokeOpen(true)}
            >
              Відкликати призначення
            </button>
          </div>
        ) : (
          <div className="assignment-empty">
            <p>У працівника немає поточного призначення.</p>
            <button
              className="button button-primary"
              type="button"
              disabled={busy}
              onClick={() =>
                void mutate(
                  base,
                  { training_version_id: null, reason: null },
                  "Навчання призначено",
                )
              }
            >
              Призначити поточну версію
            </button>
          </div>
        )
      ) : null}

      {assignments?.history.length ? (
        <div className="assignment-history">
          <h3>Історія</h3>
          <ul>
            {assignments.history.map((item) => (
              <li key={item.id}>
                <span>{assignmentStatusLabel[item.status]}</span>
                <code>{item.training_version_id}</code>
                {item.revoke_note ? <span>{item.revoke_note}</span> : null}
              </li>
            ))}
          </ul>
          {!current && latestRevoked ? (
            <button
              className="button button-secondary"
              type="button"
              disabled={busy}
              onClick={() =>
                void mutate(
                  `${base}/${latestRevoked.id}/reassign`,
                  { training_version_id: null, reason: null },
                  "Навчання призначено повторно",
                )
              }
            >
              Призначити повторно
            </button>
          ) : null}
        </div>
      ) : null}

      <ConfirmDialog
        open={revokeOpen}
        title="Відкликати призначення?"
        description="Поточний доступ буде відкликано, але історія та завершення залишаться на сервері."
        confirmLabel="Підтвердити відкликання"
        busy={busy}
        onCancel={() => setRevokeOpen(false)}
        onConfirm={() => {
          if (!current) return;
          setRevokeOpen(false);
          void mutate(
            `${base}/${current.id}/revoke`,
            { reason: revokeReason.trim() },
            "Призначення відкликано",
          );
        }}
      />
    </section>
  );
}

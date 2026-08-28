import { useCallback, useEffect, useState } from "react";

import { ApiError, createIdempotencyKey } from "../api/client";
import type { ApiClient } from "../api/client";
import type { RolloutLessonRule, TrainingRolloutResponse } from "../api/contracts";
import { ConfirmDialog } from "../ui/ConfirmDialog";
import { StatusPill } from "../ui/States";

interface AdminTrainingRolloutPanelProps {
  client: ApiClient;
  csrfToken: string;
  locationId: string;
  organizationId: string;
  rolloutId: string;
}

function employeeCountLabel(count: number): string {
  return count === 1 ? "1 працівник" : `${count} працівників`;
}

function unresolvedCountLabel(count: number): string {
  return count === 1 ? "1 рішення для змінених уроків" : `${count} рішень для змінених уроків`;
}

function rolloutStatusLabel(rollout: TrainingRolloutResponse): string {
  if (rollout.status === "completed") return "Перенесення завершено";
  if (rollout.is_stale || rollout.status === "draft") return "Потрібен новий перегляд";
  if (rollout.status === "preview_ready") return "Перегляд готовий";
  if (rollout.status === "failed") return "Перенесення не виконано";
  return "Перенесення виконується";
}

export function AdminTrainingRolloutPanel({
  client,
  csrfToken,
  locationId,
  organizationId,
  rolloutId,
}: AdminTrainingRolloutPanelProps) {
  const [rollout, setRollout] = useState<TrainingRolloutResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const base = `/organizations/${organizationId}/locations/${locationId}/training-rollouts/${rolloutId}`;

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setRollout(await client.request<TrainingRolloutResponse>(base));
      setError(null);
    } catch {
      setError("Не вдалося завантажити перенесення прогресу.");
    } finally {
      setLoading(false);
    }
  }, [base, client]);

  useEffect(() => {
    // Rollout є серверним знімком; локальний стан оновлюємо лише отриманою відповіддю.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  const handleError = (caught: unknown) => {
    if (caught instanceof ApiError && caught.code === "TRAINING_ROLLOUT_STALE") {
      setError("Попередній перегляд застарів. Оновіть його перед підтвердженням.");
    } else if (caught instanceof ApiError && caught.code === "REVISION_CONFLICT") {
      setError("Перенесення вже змінили в іншій сесії. Оновіть дані.");
    } else if (caught instanceof ApiError && caught.code === "ROLLOUT_RULE_REQUIRED") {
      setError("Оберіть дію для кожного зміненого уроку.");
    } else {
      setError("Дію з перенесенням не виконано. Оновіть дані та спробуйте ще раз.");
    }
  };

  const updateRule = async (lessonId: string, rule: RolloutLessonRule) => {
    if (!rollout) return;
    setBusy(true);
    setError(null);
    try {
      setRollout(
        await client.request<TrainingRolloutResponse>(`${base}/lesson-rules/${lessonId}`, {
          method: "PATCH",
          body: { expected_revision: rollout.revision, rule },
          csrfToken,
        }),
      );
    } catch (caught) {
      handleError(caught);
    } finally {
      setBusy(false);
    }
  };

  const preview = async () => {
    if (!rollout) return;
    setBusy(true);
    setError(null);
    try {
      setRollout(
        await client.request<TrainingRolloutResponse>(`${base}/preview`, {
          method: "POST",
          body: { expected_revision: rollout.revision },
          csrfToken,
          idempotencyKey: createIdempotencyKey(),
        }),
      );
    } catch (caught) {
      handleError(caught);
    } finally {
      setBusy(false);
    }
  };

  const confirm = async () => {
    if (!rollout) return;
    setBusy(true);
    setError(null);
    try {
      setRollout(
        await client.request<TrainingRolloutResponse>(`${base}/confirm`, {
          method: "POST",
          body: { expected_revision: rollout.revision },
          csrfToken,
          idempotencyKey: createIdempotencyKey(),
        }),
      );
      setConfirmOpen(false);
    } catch (caught) {
      setConfirmOpen(false);
      handleError(caught);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="training-rollout-panel" aria-labelledby="training-rollout-title">
      <div className="training-panel-heading">
        <div>
          <p className="eyebrow">Заміна версії</p>
          <h2 id="training-rollout-title">Перенесення прогресу</h2>
        </div>
        {rollout ? (
          <StatusPill tone={rollout.status === "completed" ? "success" : "warning"}>
            {rolloutStatusLabel(rollout)}
          </StatusPill>
        ) : null}
      </div>

      {loading ? <p aria-live="polite">Завантажуємо попередній перегляд…</p> : null}
      {error ? (
        <div className="inline-error rollout-error" role="alert">
          <p>{error}</p>
          <button className="button button-quiet" type="button" onClick={() => void refresh()}>
            Оновити дані
          </button>
        </div>
      ) : null}

      {rollout ? (
        <>
          <p className="rollout-version-path">
            Версія {rollout.from_version.version_number} → версія{" "}
            {rollout.to_version.version_number}
          </p>
          <div className="rollout-summary" aria-label="Вплив перенесення">
            <strong>{employeeCountLabel(rollout.impact_counts.employee_count)}</strong>
            <span>{unresolvedCountLabel(rollout.impact_counts.unresolved_rule_count)}</span>
          </div>

          {rollout.rules.some((rule) => rule.requires_admin_decision) ? (
            <div className="rollout-rule-list">
              <h3>Змінені уроки</h3>
              {rollout.rules
                .filter((rule) => rule.requires_admin_decision)
                .map((rule, index) => (
                  <section key={rule.lesson_id} className="rollout-rule">
                    <p>
                      <strong>Змінений урок {index + 1}</strong>
                    </p>
                    <p>Оберіть, чи зберігати попереднє завершення для цієї нової версії.</p>
                    <div className="rollout-rule-actions">
                      <button
                        className="button button-secondary"
                        type="button"
                        disabled={busy}
                        onClick={() => void updateRule(rule.lesson_id, "preserve_completion")}
                      >
                        Зберегти завершення
                      </button>
                      <button
                        className="button button-quiet"
                        type="button"
                        disabled={busy}
                        onClick={() => void updateRule(rule.lesson_id, "needs_repeat")}
                      >
                        Повторити урок
                      </button>
                    </div>
                  </section>
                ))}
            </div>
          ) : null}

          {rollout.employee_impacts.length ? (
            <div className="rollout-impact-list">
              <h3>Прогноз для працівників</h3>
              {rollout.employee_impacts.map((impact) => (
                <div key={impact.employee_profile_id} className="rollout-impact-row">
                  <code>{impact.employee_profile_id}</code>
                  <span>
                    Зараз: {impact.current_completed_count} із {impact.current_required_count} ·{" "}
                    {impact.current_progress_percentage}%
                  </span>
                  <strong>
                    Прогноз: {impact.projected_completed_count} із {impact.projected_required_count}{" "}
                    · {impact.projected_progress_percentage}%
                  </strong>
                </div>
              ))}
            </div>
          ) : null}

          {rollout.status !== "completed" &&
          (rollout.is_stale || rollout.status === "draft" || !rollout.previewed_at) ? (
            <button
              className="button button-secondary"
              type="button"
              disabled={busy || rollout.impact_counts.unresolved_rule_count > 0}
              onClick={() => void preview()}
            >
              Оновити попередній перегляд
            </button>
          ) : null}
          {rollout.status === "preview_ready" &&
          !rollout.is_stale &&
          rollout.impact_counts.unresolved_rule_count === 0 ? (
            <button
              className="button button-primary"
              type="button"
              disabled={busy}
              onClick={() => setConfirmOpen(true)}
            >
              Підтвердити перенесення
            </button>
          ) : null}
        </>
      ) : null}

      <ConfirmDialog
        open={confirmOpen}
        title="Перенести прогрес на нову версію?"
        description="Сервер ще раз перевірить версії, правила та вплив. Історія попередніх призначень залишиться незмінною."
        confirmLabel="Перенести прогрес"
        busy={busy}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => void confirm()}
      />
    </section>
  );
}

import { useRef, useState } from "react";

import { ApiError, createIdempotencyKey } from "../api/client";
import type { CourseAttempt, CourseModuleSummary } from "../api/contracts";
import { useSession } from "../session/SessionContext";

function text(payload: Record<string, unknown>): string {
  for (const key of ["stem", "text", "label", "title"]) {
    if (typeof payload[key] === "string") return payload[key];
  }
  return "";
}

export function EmployeeCourseAssessment({ course }: { course: CourseModuleSummary }) {
  const { client, session } = useSession();
  const [attempt, setAttempt] = useState<CourseAttempt | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef(false);
  const retry = useRef<{ signature: string; key: string } | null>(null);
  const question = attempt?.questions.find((item) => !item.answer_payload);

  async function request(path: string, body?: unknown, read = false) {
    if (!session || pending.current) return;
    pending.current = true;
    setBusy(true);
    setError(null);
    const signature = JSON.stringify([path, body]);
    if (!read && retry.current?.signature !== signature) {
      retry.current = { signature, key: createIdempotencyKey() };
    }
    try {
      const response = await client.request<CourseAttempt>(
        path,
        read
          ? undefined
          : {
              method: "POST",
              body,
              csrfToken: session.csrf_token,
              idempotencyKey: retry.current?.key,
            },
      );
      setAttempt(response);
      setSelected(null);
      retry.current = null;
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Не вдалося виконати запит. Спробуйте ще раз.",
      );
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }

  const start = () => request(`/me/training/modules/${course.module_version_id}/course/attempts`);
  const attemptPath = attempt ? `/me/training/course/attempts/${attempt.id}` : "";
  return (
    <section className="interactive-training" aria-label="Перевірка модуля" aria-busy={busy}>
      <h2>Перевірка модуля</h2>
      <p>
        {course.question_count} запитань. Пояснення та результат з’являться після завершення
        перевірки.
      </p>
      {error ? (
        <p role="alert" className="inline-error">
          {error}
        </p>
      ) : null}
      {!attempt ? (
        <>
          {!course.can_start ? (
            <p>
              {course.ready
                ? "Спочатку завершіть обов’язкові уроки. Якщо навчання призупинено, зверніться до адміністратора."
                : "Перевірка ще готується."}
            </p>
          ) : null}
          {course.active_attempt_id ? (
            <button
              type="button"
              className="button button-primary"
              disabled={busy}
              onClick={() =>
                void request(
                  `/me/training/course/attempts/${course.active_attempt_id}`,
                  undefined,
                  true,
                )
              }
            >
              Продовжити перевірку
            </button>
          ) : (
            <button
              type="button"
              className="button button-primary"
              disabled={busy || !course.can_start}
              onClick={() => void start()}
            >
              Розпочати перевірку
            </button>
          )}
        </>
      ) : null}
      {attempt?.status === "in_progress" ? (
        <>
          <p aria-live="polite">
            Збережено {attempt.questions.filter((item) => item.answer_payload).length} із{" "}
            {attempt.questions.length} відповідей
          </p>
          {!attempt.writable ? (
            <button
              type="button"
              className="button button-secondary"
              disabled={busy}
              onClick={() => void request(`${attemptPath}/takeover`)}
            >
              Продовжити в цій сесії
            </button>
          ) : null}
          {question ? (
            <fieldset className="interactive-options" disabled={busy || !attempt.writable}>
              <legend>
                {question.position + 1}. {text(question.prompt_payload)}
              </legend>
              {question.options.map((option) => (
                <label key={option.id} className="interactive-option">
                  <input
                    type="radio"
                    name={`course-${question.id}`}
                    value={option.id}
                    checked={selected === option.id}
                    onChange={() => setSelected(option.id)}
                  />
                  {text(option.payload)}
                </label>
              ))}
              <button
                type="button"
                className="button button-primary"
                disabled={!selected}
                onClick={() =>
                  void request(`${attemptPath}/answer`, {
                    attempt_question_id: question.id,
                    lease_generation: attempt.lease_generation,
                    answer_payload: { mechanic: "single_choice", option_id: selected },
                  })
                }
              >
                Зберегти відповідь
              </button>
            </fieldset>
          ) : (
            <button
              type="button"
              className="button button-primary"
              disabled={busy || !attempt.writable}
              onClick={() =>
                void request(`${attemptPath}/finish`, {
                  lease_generation: attempt.lease_generation,
                })
              }
            >
              Завершити перевірку
            </button>
          )}
          <button
            type="button"
            className="button button-quiet"
            disabled={busy}
            onClick={() => void request(attemptPath, undefined, true)}
          >
            Оновити стан
          </button>
        </>
      ) : null}
      {attempt?.result ? (
        <>
          <div className="interactive-result-card" aria-live="polite">
            <h3>Результат перевірки</h3>
            <strong>
              {attempt.result.correct_count} із {attempt.result.total_count}
            </strong>
            <p>
              {new Intl.NumberFormat("uk-UA", { maximumFractionDigits: 2 }).format(
                attempt.result.score_basis_points / 100,
              )}
              %
            </p>
          </div>
          {attempt.questions.map((item) =>
            item.review ? (
              <article className="practice-review-card" key={item.id}>
                <h4>
                  {item.position + 1}. {text(item.prompt_payload)}
                </h4>
                <p>{item.review.is_correct ? "Правильно" : "Потрібно повторити"}</p>
                <ul>
                  {item.options.map((option) => (
                    <li key={option.id}>
                      {text(option.payload)}
                      {item.review?.correct_option_ids.includes(option.id)
                        ? " · правильна відповідь"
                        : ""}
                    </li>
                  ))}
                </ul>
                <p>{text(item.review.explanation_payload)}</p>
              </article>
            ) : null,
          )}
        </>
      ) : null}
      {attempt && attempt.status !== "in_progress" ? (
        <button
          type="button"
          className="button button-primary"
          disabled={busy || !course.can_start}
          onClick={() => void start()}
        >
          Нова спроба
        </button>
      ) : null}
      {course.history.length ? (
        <details>
          <summary>Історія перевірок</summary>
          <ul>
            {course.history.map((item) => (
              <li key={item.attempt_id}>
                <button
                  type="button"
                  className="button button-quiet"
                  disabled={busy}
                  onClick={() =>
                    void request(`/me/training/course/attempts/${item.attempt_id}`, undefined, true)
                  }
                >
                  {item.result.correct_count}/{item.result.total_count} ·{" "}
                  {new Date(item.result.completed_at).toLocaleDateString("uk-UA")}
                </button>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  );
}

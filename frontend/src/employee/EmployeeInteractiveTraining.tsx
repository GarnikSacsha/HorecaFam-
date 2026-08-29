import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import type { ApiClient } from "../api/client";
import { ApiError, createIdempotencyKey } from "../api/client";
import type {
  InteractiveAnswerPayload,
  InteractiveAnswerResponse,
  InteractiveAttempt,
  InteractiveAttemptQuestion,
  InteractiveAttemptStartResponse,
  InteractiveAttemptTakeoverResponse,
  InteractiveKnowledgeLevel,
  InteractiveResult,
  InteractiveResultSummary,
  LessonInteractiveTrainingSummary,
} from "../api/contracts";

interface EmployeeInteractiveTrainingProps {
  client: ApiClient;
  csrfToken: string;
  lessonCompleted: boolean;
  lessonId: string;
  preferredLocale: "uk" | "en";
}

type BusyAction = "start" | "answer" | "takeover" | null;

const knowledgeLabels: Record<InteractiveKnowledgeLevel, string> = {
  very_weak: "Потрібно повторити",
  weak: "Базове розуміння",
  good: "Добре знання",
  strong: "Сильне знання",
};

function payloadText(payload: Record<string, unknown>, ...keys: string[]): string | null {
  for (const key of keys) {
    const value = payload[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  return null;
}

function optionText(option: InteractiveAttemptQuestion["options"][number]): string {
  return payloadText(option.payload, "text", "label", "title") ?? `Варіант ${option.position + 1}`;
}

function scoreLabel(result: Pick<InteractiveResultSummary, "correct_count" | "total_count">) {
  return `${result.correct_count} з ${result.total_count}`;
}

function knowledgeLabel(level: InteractiveKnowledgeLevel) {
  return knowledgeLabels[level];
}

function ResultCard({ result, title }: { result: InteractiveResultSummary; title: string }) {
  return (
    <article className="interactive-result-card">
      <h3>{title}</h3>
      <strong>{scoreLabel(result)}</strong>
      <span>{knowledgeLabel(result.knowledge_level)}</span>
      <time dateTime={result.completed_at}>
        {new Intl.DateTimeFormat("uk-UA", { dateStyle: "medium", timeStyle: "short" }).format(
          new Date(result.completed_at),
        )}
      </time>
      {!result.is_current ? <small>Попередня версія уроку</small> : null}
    </article>
  );
}

function AttemptHistory({ summary }: { summary: LessonInteractiveTrainingSummary }) {
  if (!summary.latest && !summary.best && summary.history.length === 0) return null;
  return (
    <section className="interactive-history" aria-labelledby="interactive-history-title">
      <div className="interactive-history-heading">
        <p className="eyebrow">Знання теми</p>
        <h2 id="interactive-history-title">Ваші результати</h2>
      </div>
      <div className="interactive-result-grid">
        {summary.latest ? <ResultCard result={summary.latest} title="Останній результат" /> : null}
        {summary.best ? <ResultCard result={summary.best} title="Найкращий результат" /> : null}
      </div>
      {summary.history.length > 0 ? (
        <details className="interactive-history-list">
          <summary>Історія спроб</summary>
          <ol>
            {summary.history.map((item) => (
              <li key={item.result_id}>
                <span>
                  Результат: {item.correct_count}/{item.total_count} ·{" "}
                  {knowledgeLabel(item.knowledge_level)}
                </span>
                <time dateTime={item.completed_at}>
                  {new Intl.DateTimeFormat("uk-UA", { dateStyle: "medium" }).format(
                    new Date(item.completed_at),
                  )}
                </time>
                {!item.is_current ? <small>Попередня версія</small> : null}
              </li>
            ))}
          </ol>
        </details>
      ) : null}
    </section>
  );
}

function AvailabilityMessage({ summary }: { summary: LessonInteractiveTrainingSummary }) {
  if (summary.availability === "paused") {
    return (
      <div className="interactive-availability is-paused" role="status">
        <strong>Навчання призупинено</strong>
        <span>Результати доступні для перегляду. Нові відповіді тимчасово недоступні.</span>
      </div>
    );
  }
  if (summary.availability === "preparing") {
    return (
      <div className="interactive-availability" role="status">
        <strong>Тренування готується</strong>
        <span>Поверніться трохи пізніше — матеріал уроку залишається доступним.</span>
      </div>
    );
  }
  if (summary.availability === "unavailable") {
    return (
      <div className="interactive-availability" role="status">
        <strong>Тренування поки недоступне</strong>
        <span>Це не впливає на завершення уроку або прогрес навчання.</span>
      </div>
    );
  }
  if (summary.readiness_status === "warning") {
    return (
      <p className="interactive-warning" role="status">
        Тренування готове, але наступна спроба може містити знайомі питання.
      </p>
    );
  }
  return null;
}

function FeedbackPanel({ question }: { question: InteractiveAttemptQuestion }) {
  if (!question.feedback) return null;
  const correctAnswers = question.options
    .filter((option) => question.feedback?.correct_option_ids.includes(option.id))
    .map(optionText);
  return (
    <div
      className={`interactive-feedback ${question.feedback.is_correct ? "is-correct" : "is-incorrect"}`}
      role="status"
    >
      <strong>{question.feedback.is_correct ? "Правильна відповідь" : "Варто повторити"}</strong>
      {!question.feedback.is_correct && correctAnswers.length > 0 ? (
        <p>
          <b>Правильна відповідь:</b> {correctAnswers.join(", ")}
        </p>
      ) : null}
      <p>
        {payloadText(question.feedback.explanation_payload, "text", "explanation") ??
          "Відповідь перевірено за матеріалами уроку."}
      </p>
    </div>
  );
}

function QuestionOptions({
  question,
  selected,
  matching,
  disabled,
  onSelected,
  onMatching,
}: {
  question: InteractiveAttemptQuestion;
  selected: string[];
  matching: Record<string, string>;
  disabled: boolean;
  onSelected: (ids: string[]) => void;
  onMatching: (leftId: string, rightId: string) => void;
}) {
  const options = [...question.options].sort((left, right) => left.position - right.position);

  if (question.mechanic === "single_choice") {
    return (
      <fieldset className="interactive-options" disabled={disabled}>
        <legend>Оберіть одну відповідь</legend>
        {options.map((option) => (
          <label className="interactive-option" key={option.id}>
            <input
              checked={selected[0] === option.id}
              name={`answer-${question.id}`}
              onChange={() => onSelected([option.id])}
              type="radio"
              value={option.id}
            />
            <span>{optionText(option)}</span>
          </label>
        ))}
      </fieldset>
    );
  }

  if (question.mechanic === "multiple_choice" || question.mechanic === "recognition") {
    return (
      <fieldset className="interactive-options" disabled={disabled}>
        <legend>Оберіть усі правильні відповіді</legend>
        {options.map((option) => (
          <label className="interactive-option" key={option.id}>
            <input
              checked={selected.includes(option.id)}
              onChange={() =>
                onSelected(
                  selected.includes(option.id)
                    ? selected.filter((id) => id !== option.id)
                    : [...selected, option.id],
                )
              }
              type="checkbox"
              value={option.id}
            />
            <span>{optionText(option)}</span>
          </label>
        ))}
      </fieldset>
    );
  }

  if (question.mechanic === "ordering" || question.mechanic === "assembly") {
    const orderedIds = selected.length === options.length ? selected : options.map(({ id }) => id);
    const move = (index: number, offset: number) => {
      const target = index + offset;
      if (target < 0 || target >= orderedIds.length) return;
      const next = [...orderedIds];
      [next[index], next[target]] = [next[target], next[index]];
      onSelected(next);
    };
    return (
      <fieldset className="interactive-options interactive-ordering" disabled={disabled}>
        <legend>Розташуйте у правильному порядку</legend>
        {orderedIds.map((id, index) => {
          const option = options.find((item) => item.id === id);
          if (!option) return null;
          return (
            <div className="interactive-order-row" key={id}>
              <span>
                {index + 1}. {optionText(option)}
              </span>
              <span className="interactive-order-actions">
                <button
                  aria-label={`Перемістити ${optionText(option)} вище`}
                  className="button button-quiet"
                  disabled={disabled || index === 0}
                  onClick={() => move(index, -1)}
                  type="button"
                >
                  ↑
                </button>
                <button
                  aria-label={`Перемістити ${optionText(option)} нижче`}
                  className="button button-quiet"
                  disabled={disabled || index === orderedIds.length - 1}
                  onClick={() => move(index, 1)}
                  type="button"
                >
                  ↓
                </button>
              </span>
            </div>
          );
        })}
      </fieldset>
    );
  }

  if (question.mechanic === "matching") {
    const left = options.filter((item) => item.payload.side === "left");
    const right = options.filter((item) => item.payload.side === "right");
    return (
      <fieldset className="interactive-options" disabled={disabled}>
        <legend>Зіставте пари</legend>
        {left.map((leftOption) => (
          <label className="interactive-match-row" key={leftOption.id}>
            <span>{optionText(leftOption)}</span>
            <select
              aria-label={`Пара для ${optionText(leftOption)}`}
              onChange={(event) => onMatching(leftOption.id, event.target.value)}
              value={matching[leftOption.id] ?? ""}
            >
              <option value="">Оберіть відповідність</option>
              {right.map((rightOption) => (
                <option key={rightOption.id} value={rightOption.id}>
                  {optionText(rightOption)}
                </option>
              ))}
            </select>
          </label>
        ))}
      </fieldset>
    );
  }

  return <p className="inline-error">Цей тип питання ще не підтримується інтерфейсом.</p>;
}

export function EmployeeInteractiveTraining({
  client,
  csrfToken,
  lessonCompleted,
  lessonId,
  preferredLocale,
}: EmployeeInteractiveTrainingProps) {
  const [summary, setSummary] = useState<LessonInteractiveTrainingSummary | null>(null);
  const [attempt, setAttempt] = useState<InteractiveAttempt | null>(null);
  const [activeQuestionId, setActiveQuestionId] = useState<string | null>(null);
  const [selected, setSelected] = useState<Record<string, string[]>>({});
  const [matching, setMatching] = useState<Record<string, Record<string, string>>>({});
  const [reviewQuestionId, setReviewQuestionId] = useState<string | null>(null);
  const [result, setResult] = useState<InteractiveResult | null>(null);
  const [loading, setLoading] = useState(lessonCompleted);
  const [busy, setBusy] = useState<BusyAction>(null);
  const [error, setError] = useState<string | null>(null);
  const [deviceConflict, setDeviceConflict] = useState(false);
  const startKey = useRef(createIdempotencyKey());
  const takeoverKey = useRef(createIdempotencyKey());
  const answerKeys = useRef<Record<string, string>>({});
  const errorRef = useRef<HTMLDivElement>(null);
  const questionHeadingRef = useRef<HTMLHeadingElement>(null);

  const openAttempt = useCallback((nextAttempt: InteractiveAttempt) => {
    setAttempt(nextAttempt);
    const nextQuestion = nextAttempt.questions.find((item) => !item.answered);
    setActiveQuestionId(nextQuestion?.id ?? nextAttempt.questions.at(-1)?.id ?? null);
    setReviewQuestionId(null);
    setDeviceConflict(!nextAttempt.writable);
  }, []);

  const loadSummary = useCallback(async () => {
    if (!lessonCompleted) return;
    setLoading(true);
    setError(null);
    try {
      const response = await client.request<LessonInteractiveTrainingSummary>(
        `/me/training/lessons/${lessonId}/interactive-training`,
      );
      setSummary(response);
      if (response.active_attempt) openAttempt(response.active_attempt);
    } catch {
      setError("Не вдалося завантажити тренування. Спробуйте ще раз.");
    } finally {
      setLoading(false);
    }
  }, [client, lessonCompleted, lessonId, openAttempt]);

  useEffect(() => {
    // Стан тренування є серверним знімком; локально не вгадуємо доступність.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadSummary();
  }, [loadSummary]);

  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);

  const activeQuestion = useMemo(
    () => attempt?.questions.find((item) => item.id === activeQuestionId) ?? null,
    [activeQuestionId, attempt],
  );
  const activePosition = activeQuestion ? activeQuestion.position + 1 : 0;
  const isPaused = summary?.availability === "paused";
  const feedback =
    activeQuestion && reviewQuestionId === activeQuestion.id ? activeQuestion.feedback : null;
  const finalFeedbackQuestion =
    result && reviewQuestionId
      ? (attempt?.questions.find((item) => item.id === reviewQuestionId) ?? null)
      : null;

  const startAttempt = async () => {
    if (busy || !summary?.can_start || isPaused) return;
    setBusy("start");
    setError(null);
    setResult(null);
    try {
      const response = await client.request<InteractiveAttemptStartResponse>(
        `/me/training/lessons/${lessonId}/interactive-training/attempts?locale=${preferredLocale}`,
        { method: "POST", idempotencyKey: startKey.current },
      );
      openAttempt(response.attempt);
      setSelected({});
      setMatching({});
      startKey.current = createIdempotencyKey();
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === "ASSESSMENT_NOT_READY") {
        setError("Тренування ще готується. Матеріал уроку залишається доступним.");
      } else {
        setError("Не вдалося почати тренування. Спробуйте ще раз.");
      }
    } finally {
      setBusy(null);
    }
  };

  const answerPayload = (question: InteractiveAttemptQuestion): InteractiveAnswerPayload | null => {
    const ids = selected[question.id] ?? [];
    if (question.mechanic === "single_choice") {
      return ids[0] ? { mechanic: "single_choice", option_id: ids[0] } : null;
    }
    if (question.mechanic === "multiple_choice" || question.mechanic === "recognition") {
      return ids.length > 0 ? { mechanic: question.mechanic, option_ids: ids } : null;
    }
    if (question.mechanic === "ordering" || question.mechanic === "assembly") {
      const ordered =
        ids.length === question.options.length ? ids : question.options.map(({ id }) => id);
      return ordered.length >= 2 ? { mechanic: question.mechanic, option_ids: ordered } : null;
    }
    if (question.mechanic === "matching") {
      const pairs = Object.entries(matching[question.id] ?? {})
        .filter(([, rightId]) => Boolean(rightId))
        .map(([left_option_id, right_option_id]) => ({ left_option_id, right_option_id }));
      const leftCount = question.options.filter((item) => item.payload.side === "left").length;
      return pairs.length === leftCount && leftCount > 0 ? { mechanic: "matching", pairs } : null;
    }
    return null;
  };

  const submitAnswer = async () => {
    if (!attempt || !activeQuestion || busy || isPaused || !attempt.writable) return;
    const payload = answerPayload(activeQuestion);
    if (!payload) return;
    const key = answerKeys.current[activeQuestion.id] ?? createIdempotencyKey();
    answerKeys.current[activeQuestion.id] = key;
    setBusy("answer");
    setError(null);
    try {
      const response = await client.request<InteractiveAnswerResponse>(
        `/me/training/interactive-training/attempts/${attempt.id}/answer`,
        {
          method: "POST",
          body: {
            attempt_question_id: activeQuestion.id,
            answer_payload: payload,
            lease_generation: attempt.lease_generation,
          },
          csrfToken,
          idempotencyKey: key,
        },
      );
      delete answerKeys.current[activeQuestion.id];
      setAttempt((current) =>
        current
          ? {
              ...current,
              status: response.attempt_status,
              questions: current.questions.map((item) =>
                item.id === activeQuestion.id
                  ? {
                      ...item,
                      answered: true,
                      confirmed_answer: response.answer,
                      feedback: response.feedback,
                    }
                  : item,
              ),
            }
          : current,
      );
      setReviewQuestionId(activeQuestion.id);
      setResult(response.result);
    } catch (caught) {
      if (
        caught instanceof ApiError &&
        (caught.code === "ATTEMPT_DEVICE_CONFLICT" || caught.code === "ATTEMPT_NOT_WRITABLE")
      ) {
        setDeviceConflict(true);
        setAttempt((current) => (current ? { ...current, writable: false } : current));
        setError("Спроба відкрита на іншому пристрої. Відповідь не збережено.");
      } else if (caught instanceof ApiError && caught.code === "ATTEMPT_EXPIRED") {
        setError("Термін цієї спроби минув. Почніть нове тренування.");
      } else {
        setError("Відповідь не збережено. Ваш вибір залишився — спробуйте ще раз.");
      }
    } finally {
      setBusy(null);
    }
  };

  const takeover = async () => {
    if (!attempt || busy || isPaused) return;
    setBusy("takeover");
    setError(null);
    try {
      const response = await client.request<InteractiveAttemptTakeoverResponse>(
        `/me/training/interactive-training/attempts/${attempt.id}/takeover`,
        {
          method: "POST",
          csrfToken,
          idempotencyKey: takeoverKey.current,
        },
      );
      setAttempt((current) =>
        current
          ? { ...current, writable: true, lease_generation: response.lease_generation }
          : current,
      );
      setDeviceConflict(false);
      takeoverKey.current = createIdempotencyKey();
    } catch {
      setError("Не вдалося перенести спробу на цей пристрій. Спробуйте ще раз.");
    } finally {
      setBusy(null);
    }
  };

  const continueAttempt = () => {
    if (!attempt || !activeQuestion) return;
    const next = attempt.questions.find(
      (item) => item.position > activeQuestion.position && !item.answered,
    );
    if (next) {
      setActiveQuestionId(next.id);
      setReviewQuestionId(null);
      requestAnimationFrame(() => questionHeadingRef.current?.focus());
    }
  };

  const retryAttempt = async () => {
    setAttempt(null);
    setActiveQuestionId(null);
    setReviewQuestionId(null);
    setResult(null);
    await startAttempt();
  };

  const canSubmit = activeQuestion ? Boolean(answerPayload(activeQuestion)) : false;

  return (
    <section className="interactive-training" aria-labelledby="interactive-training-title">
      <div className="interactive-training-heading">
        <p className="eyebrow">Практика після уроку</p>
        <h2 id="interactive-training-title">Інтерактивне тренування</h2>
        <p>П’ять коротких питань із поясненням після кожної підтвердженої відповіді.</p>
      </div>

      {!lessonCompleted ? (
        <div className="interactive-availability">
          <strong>Спочатку завершіть урок</strong>
          <span>Після підтвердження ознайомлення тут з’явиться тренування.</span>
        </div>
      ) : null}
      {loading ? <p aria-live="polite">Перевіряємо готовність тренування…</p> : null}
      {error ? (
        <div className="inline-error" ref={errorRef} role="alert" tabIndex={-1}>
          <p>{error}</p>
          {!attempt ? (
            <button
              className="button button-quiet"
              onClick={() => void loadSummary()}
              type="button"
            >
              Оновити
            </button>
          ) : null}
        </div>
      ) : null}

      {summary ? <AvailabilityMessage summary={summary} /> : null}

      {deviceConflict && attempt && !isPaused ? (
        <div className="interactive-device-card">
          <strong>Відкрито на іншому пристрої</strong>
          <p>Збережені відповіді не втратяться. Продовження тут вимкне запис на іншому пристрої.</p>
          <button
            className="button button-secondary"
            disabled={busy === "takeover"}
            onClick={() => void takeover()}
            type="button"
          >
            {busy === "takeover" ? "Переносимо…" : "Продовжити на цьому пристрої"}
          </button>
        </div>
      ) : null}

      {attempt && activeQuestion && !result ? (
        <article className="interactive-attempt" aria-labelledby={`question-${activeQuestion.id}`}>
          <div className="interactive-progress" aria-label={`Питання ${activePosition} з 5`}>
            <span>{activePosition} з 5</span>
            <progress max={5} value={activePosition} />
          </div>
          {attempt.presentation_locale !== preferredLocale ? (
            <p className="interactive-locale-note" role="status">
              Ця спроба продовжується мовою, обраною під час її початку.
            </p>
          ) : null}
          <h3 id={`question-${activeQuestion.id}`} ref={questionHeadingRef} tabIndex={-1}>
            {payloadText(activeQuestion.prompt_payload, "stem", "text", "title") ??
              `Питання ${activePosition}`}
          </h3>
          <QuestionOptions
            disabled={Boolean(feedback) || busy === "answer" || isPaused || !attempt.writable}
            matching={matching[activeQuestion.id] ?? {}}
            onMatching={(leftId, rightId) =>
              setMatching((current) => ({
                ...current,
                [activeQuestion.id]: {
                  ...(current[activeQuestion.id] ?? {}),
                  [leftId]: rightId,
                },
              }))
            }
            onSelected={(ids) =>
              setSelected((current) => ({ ...current, [activeQuestion.id]: ids }))
            }
            question={activeQuestion}
            selected={selected[activeQuestion.id] ?? []}
          />

          {feedback ? <FeedbackPanel question={activeQuestion} /> : null}

          <div className="interactive-attempt-actions">
            {!feedback ? (
              <button
                className="button button-primary"
                disabled={!canSubmit || busy === "answer" || isPaused || !attempt.writable}
                onClick={() => void submitAnswer()}
                type="button"
              >
                {busy === "answer"
                  ? "Зберігаємо відповідь…"
                  : error
                    ? "Спробувати ще раз"
                    : "Підтвердити відповідь"}
              </button>
            ) : null}
            {feedback && attempt.status !== "completed" ? (
              <button className="button button-primary" onClick={continueAttempt} type="button">
                Наступне питання
              </button>
            ) : null}
          </div>
        </article>
      ) : null}

      {result && attempt ? (
        <section className="interactive-final" aria-labelledby="interactive-final-title">
          <p className="eyebrow">Спробу завершено</p>
          <h3 id="interactive-final-title">
            {result.correct_count} з {result.total_count} правильних відповідей
          </h3>
          <strong className="interactive-knowledge-level">
            {knowledgeLabel(result.knowledge_level)} · {result.score_basis_points / 100}%
          </strong>
          {finalFeedbackQuestion?.feedback ? (
            <FeedbackPanel question={finalFeedbackQuestion} />
          ) : null}
          {attempt.questions.some((item) => item.feedback?.is_correct === false) ? (
            <div className="interactive-weak-items">
              <h4>Що варто повторити</h4>
              <ul>
                {attempt.questions
                  .filter((item) => item.feedback?.is_correct === false)
                  .map((item) => (
                    <li key={item.id}>
                      {payloadText(item.prompt_payload, "stem", "text", "title") ??
                        `Питання ${item.position + 1}`}
                    </li>
                  ))}
              </ul>
            </div>
          ) : (
            <p>Усі відповіді правильні. Можете повторити тренування для закріплення.</p>
          )}
          <div className="interactive-final-actions">
            <button
              className="button button-primary"
              disabled={!summary?.can_start || isPaused || busy === "start"}
              onClick={() => void retryAttempt()}
              type="button"
            >
              {busy === "start" ? "Готуємо спробу…" : "Повторити тренування"}
            </button>
            <Link className="button button-secondary" to="/employee/learning">
              Продовжити навчання
            </Link>
          </div>
        </section>
      ) : null}

      {summary?.can_start && !attempt && !isPaused ? (
        <button
          className="button button-primary interactive-start-button"
          disabled={busy === "start"}
          onClick={() => void startAttempt()}
          type="button"
        >
          {busy === "start"
            ? "Готуємо спробу…"
            : summary.latest
              ? "Повторити тренування"
              : "Почати тренування"}
        </button>
      ) : null}

      {summary ? <AttemptHistory summary={summary} /> : null}
    </section>
  );
}

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, createIdempotencyKey } from "../api/client";
import type {
  InteractiveAnswerPayload,
  PracticeAnswerResponse,
  PracticeAttempt,
  PracticeAttemptQuestion,
  PracticeAttemptStartResponse,
  PracticeAttemptTakeoverResponse,
  PracticeFinishResponse,
  PracticeHistoryResponse,
  PracticeKnowledgeLevel,
  PracticeQuestionReview,
  PracticeResultSummary,
  PracticeSummaryResponse,
} from "../api/contracts";
import { LogoutButton } from "../auth/LogoutButton";
import { useSession } from "../session/SessionContext";
import { StatusPill } from "../ui/States";

type BusyAction = "load" | "start" | "answer" | "takeover" | "finish" | null;

const knowledgeLabels: Record<PracticeKnowledgeLevel, string> = {
  very_weak: "Дуже слабке знання",
  weak: "Слабке знання",
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

function optionText(option: PracticeAttemptQuestion["options"][number]) {
  return payloadText(option.payload, "text", "label", "title") ?? `Варіант ${option.position + 1}`;
}

function answerOptionIds(payload: Record<string, unknown>): string[] {
  if (typeof payload.option_id === "string") return [payload.option_id];
  return Array.isArray(payload.option_ids)
    ? payload.option_ids.filter((item): item is string => typeof item === "string")
    : [];
}

function savedOptionIds(question: PracticeAttemptQuestion): string[] {
  return question.saved_answer ? answerOptionIds(question.saved_answer.answer_payload) : [];
}

function ResultCard({ result, title }: { result: PracticeResultSummary; title: string }) {
  return (
    <article className="interactive-result-card">
      <h3>{title}</h3>
      <strong>
        {result.correct_count} з {result.total_count}
      </strong>
      <span>{knowledgeLabels[result.knowledge_level]}</span>
      <time dateTime={result.completed_at}>
        {new Intl.DateTimeFormat("uk-UA", { dateStyle: "medium", timeStyle: "short" }).format(
          new Date(result.completed_at),
        )}
      </time>
    </article>
  );
}

function PracticeHistory({ history }: { history: PracticeHistoryResponse }) {
  if (!history.latest && !history.best && history.history.length === 0) return null;
  return (
    <section className="interactive-history" aria-labelledby="practice-history-title">
      <div className="interactive-history-heading">
        <p className="eyebrow">Ваш прогрес</p>
        <h2 id="practice-history-title">Результати Практики</h2>
      </div>
      <div className="interactive-result-grid">
        {history.latest ? <ResultCard result={history.latest} title="Останній результат" /> : null}
        {history.best ? <ResultCard result={history.best} title="Найкращий результат" /> : null}
      </div>
      {history.history.length ? (
        <details className="interactive-history-list">
          <summary>Історія спроб</summary>
          <ol>
            {history.history.map((item) => (
              <li key={item.result_id}>
                <span>
                  {item.correct_count}/{item.total_count} · {knowledgeLabels[item.knowledge_level]}
                </span>
                <time dateTime={item.completed_at}>
                  {new Intl.DateTimeFormat("uk-UA", { dateStyle: "medium" }).format(
                    new Date(item.completed_at),
                  )}
                </time>
              </li>
            ))}
          </ol>
        </details>
      ) : null}
    </section>
  );
}

function ReviewCard({ item }: { item: PracticeQuestionReview }) {
  const selectedIds = answerOptionIds(item.answer.answer_payload);
  return (
    <article className={`practice-review-card ${item.is_correct ? "is-correct" : "is-incorrect"}`}>
      <div className="readiness-card-heading">
        <h4>
          {item.position + 1}. {payloadText(item.prompt_payload, "stem", "text", "title")}
        </h4>
        <StatusPill tone={item.is_correct ? "success" : "warning"}>
          {item.is_correct ? "Правильно" : "Потрібно повторити"}
        </StatusPill>
      </div>
      <ul>
        {item.options.map((option) => (
          <li key={option.id}>
            {optionText(option)}
            {selectedIds.includes(option.id) ? " · ваша відповідь" : ""}
            {item.correct_option_ids.includes(option.id) ? " · правильна відповідь" : ""}
          </li>
        ))}
      </ul>
      {item.is_critical_error ? (
        <p className="practice-critical-note">Критична помилка щодо алергенів.</p>
      ) : null}
      <p>{payloadText(item.explanation_payload, "text", "explanation")}</p>
    </article>
  );
}

export function EmployeePracticePage() {
  const { client, session } = useSession();
  const [summary, setSummary] = useState<PracticeSummaryResponse | null>(null);
  const [history, setHistory] = useState<PracticeHistoryResponse>({
    qualified: false,
    latest: null,
    best: null,
    history: [],
  });
  const [attempt, setAttempt] = useState<PracticeAttempt | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [selected, setSelected] = useState<Record<string, string[]>>({});
  const [finish, setFinish] = useState<PracticeFinishResponse | null>(null);
  const [busy, setBusy] = useState<BusyAction>("load");
  const [error, setError] = useState<string | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const startKey = useRef<string | null>(null);
  const takeoverKey = useRef<string | null>(null);
  const finishKey = useRef<string | null>(null);
  const answerKeys = useRef(new Map<string, string>());
  const locale = session?.user.preferred_locale === "en" ? "en" : "uk";

  const applyAttempt = useCallback((next: PracticeAttempt) => {
    setAttempt(next);
    setSelected(
      Object.fromEntries(next.questions.map((question) => [question.id, savedOptionIds(question)])),
    );
    const unanswered = next.questions.findIndex((question) => !question.saved_answer);
    setActiveIndex(unanswered >= 0 ? unanswered : next.questions.length - 1);
  }, []);

  const load = useCallback(async () => {
    if (!session) return;
    setBusy("load");
    setError(null);
    try {
      const [nextSummary, nextHistory] = await Promise.all([
        client.request<PracticeSummaryResponse>("/me/training/practice"),
        client.request<PracticeHistoryResponse>("/me/training/practice/attempts"),
      ]);
      setSummary(nextSummary);
      setHistory(nextHistory);
      if (nextSummary.active_attempt) applyAttempt(nextSummary.active_attempt);
      else setAttempt(null);
    } catch {
      setError("Не вдалося завантажити Практику. Перевірте мережу та спробуйте ще раз.");
    } finally {
      setBusy(null);
    }
  }, [applyAttempt, client, session]);

  useEffect(() => {
    // Практика є серверним знімком; локальний стан оновлюється лише з API-відповіді.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  const activeQuestion = attempt?.questions[activeIndex] ?? null;
  const activeSelection = activeQuestion ? (selected[activeQuestion.id] ?? []) : [];
  const allAnswered = attempt?.answered_count === 10;
  const canSave = Boolean(
    activeQuestion &&
    !activeQuestion.saved_answer &&
    activeSelection.length &&
    attempt?.writable &&
    busy !== "answer",
  );

  useEffect(() => {
    if (attempt && !finish) headingRef.current?.focus();
  }, [activeIndex, attempt, finish]);

  const startAttempt = async () => {
    if (!session || busy) return;
    setBusy("start");
    setError(null);
    startKey.current ??= createIdempotencyKey();
    try {
      const response = await client.request<PracticeAttemptStartResponse>(
        `/me/training/practice/attempts?locale=${locale}`,
        {
          method: "POST",
          csrfToken: session.csrf_token,
          idempotencyKey: startKey.current,
        },
      );
      startKey.current = null;
      setFinish(null);
      applyAttempt(response.attempt);
    } catch {
      setError("Спробу не відкрито. Дані не втрачено — повторіть дію.");
    } finally {
      setBusy(null);
    }
  };

  const takeover = async () => {
    if (!session || !attempt || busy) return;
    setBusy("takeover");
    setError(null);
    takeoverKey.current ??= createIdempotencyKey();
    try {
      const response = await client.request<PracticeAttemptTakeoverResponse>(
        `/me/training/practice/attempts/${attempt.id}/takeover`,
        {
          method: "POST",
          csrfToken: session.csrf_token,
          idempotencyKey: takeoverKey.current,
        },
      );
      takeoverKey.current = null;
      setAttempt((current) =>
        current
          ? { ...current, writable: true, lease_generation: response.lease_generation }
          : current,
      );
    } catch {
      setError("Не вдалося продовжити на цьому пристрої. Оновіть дані.");
    } finally {
      setBusy(null);
    }
  };

  const answerPayload = (question: PracticeAttemptQuestion): InteractiveAnswerPayload =>
    question.mechanic === "single_choice"
      ? { mechanic: "single_choice", option_id: activeSelection[0] }
      : {
          mechanic: question.mechanic === "recognition" ? "recognition" : "multiple_choice",
          option_ids: activeSelection,
        };

  const saveAnswer = async () => {
    if (!session || !attempt || !activeQuestion || !canSave) return;
    setBusy("answer");
    setError(null);
    const key = answerKeys.current.get(activeQuestion.id) ?? createIdempotencyKey();
    answerKeys.current.set(activeQuestion.id, key);
    try {
      const response = await client.request<PracticeAnswerResponse>(
        `/me/training/practice/attempts/${attempt.id}/answer`,
        {
          method: "POST",
          body: {
            attempt_question_id: activeQuestion.id,
            answer_payload: answerPayload(activeQuestion),
            lease_generation: attempt.lease_generation,
          },
          csrfToken: session.csrf_token,
          idempotencyKey: key,
        },
      );
      answerKeys.current.delete(activeQuestion.id);
      setAttempt((current) =>
        current
          ? {
              ...current,
              answered_count: response.answered_count,
              questions: current.questions.map((question) =>
                question.id === activeQuestion.id
                  ? { ...question, saved_answer: response.answer }
                  : question,
              ),
            }
          : current,
      );
      if (response.next_question_id) {
        const nextIndex = attempt.questions.findIndex(
          (question) => question.id === response.next_question_id,
        );
        if (nextIndex >= 0) setActiveIndex(nextIndex);
      }
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === "ATTEMPT_DEVICE_CONFLICT") {
        setAttempt((current) => (current ? { ...current, writable: false } : current));
        setError("Спробу відкрито на іншому пристрої. Підтвердьте продовження тут.");
      } else if (caught instanceof ApiError && caught.code === "ATTEMPT_EXPIRED") {
        setAttempt(null);
        setError("Час активності спроби минув. Почніть нову спробу.");
      } else {
        setError("Відповідь не збережено. Вибір залишився на екрані — повторіть дію.");
      }
    } finally {
      setBusy(null);
    }
  };

  const finishAttempt = async () => {
    if (!session || !attempt || !allAnswered || busy) return;
    setBusy("finish");
    setError(null);
    finishKey.current ??= createIdempotencyKey();
    try {
      const response = await client.request<PracticeFinishResponse>(
        `/me/training/practice/attempts/${attempt.id}/finish`,
        {
          method: "POST",
          body: { lease_generation: attempt.lease_generation },
          csrfToken: session.csrf_token,
          idempotencyKey: finishKey.current,
        },
      );
      finishKey.current = null;
      setFinish(response);
      setAttempt((current) => (current ? { ...current, status: "completed" } : current));
      setHistory(await client.request<PracticeHistoryResponse>("/me/training/practice/attempts"));
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === "ATTEMPT_DEVICE_CONFLICT") {
        setAttempt((current) => (current ? { ...current, writable: false } : current));
      }
      setError("Практику не завершено. Збережені відповіді залишилися на сервері.");
    } finally {
      setBusy(null);
    }
  };

  const retry = async () => {
    setAttempt(null);
    setFinish(null);
    finishKey.current = null;
    await startAttempt();
  };

  const availability = useMemo(() => {
    if (!summary || attempt || finish) return null;
    if (summary.availability === "paused")
      return ["Навчання призупинено", "Історія доступна, нові відповіді тимчасово недоступні."];
    if (summary.availability === "preparing")
      return ["Практика готується", "Банк питань ще не готовий. Поверніться пізніше."];
    if (summary.availability === "unavailable")
      return [
        "Спочатку завершіть навчання",
        "Практика відкриється після всіх обов’язкових уроків.",
      ];
    return null;
  }, [attempt, finish, summary]);

  return (
    <section className="employee-learning-page practice-page" aria-labelledby="practice-title">
      <div className="employee-learning-heading">
        <div>
          <p className="eyebrow">Усе меню</p>
          <h1 id="practice-title">Практика</h1>
          <p className="page-description">
            10 різних позицій меню. Правильні відповіді та пояснення з’являться тільки після фінішу.
          </p>
        </div>
        <LogoutButton />
      </div>

      {busy === "load" ? <p aria-live="polite">Завантажуємо Практику…</p> : null}
      {error ? (
        <div className="inline-error" role="alert">
          <p>{error}</p>
          {!attempt ? (
            <button className="button button-quiet" onClick={() => void load()} type="button">
              Оновити дані
            </button>
          ) : null}
        </div>
      ) : null}
      {summary?.qualified ? (
        <p className="practice-qualified-note" role="status">
          Доступ до підсумкового іспиту вже відкрито. Практику можна повторювати без обмежень.
        </p>
      ) : null}
      {availability ? (
        <div className="interactive-availability" role="status">
          <strong>{availability[0]}</strong>
          <span>{availability[1]}</span>
        </div>
      ) : null}

      {attempt && !finish && !attempt.writable ? (
        <div className="interactive-device-card">
          <strong>Відкрито на іншому пристрої</strong>
          <p>Перегляд безпечний. Для відповідей підтвердьте право запису на цьому пристрої.</p>
          <button
            className="button button-secondary"
            disabled={busy === "takeover"}
            onClick={() => void takeover()}
            type="button"
          >
            {busy === "takeover" ? "Підтверджуємо…" : "Продовжити на цьому пристрої"}
          </button>
        </div>
      ) : null}

      {attempt && activeQuestion && !finish ? (
        <article className="interactive-attempt">
          <div className="interactive-progress">
            <span>{attempt.answered_count} з 10 відповідей збережено</span>
            <progress max={10} value={attempt.answered_count}>
              {attempt.answered_count} з 10
            </progress>
          </div>
          <h2 ref={headingRef} tabIndex={-1}>
            Питання {activeQuestion.position + 1}
          </h2>
          <p className="practice-question-copy">
            {payloadText(activeQuestion.prompt_payload, "stem", "text", "title")}
          </p>
          <fieldset
            className="interactive-options"
            disabled={!attempt.writable || Boolean(activeQuestion.saved_answer)}
          >
            <legend>
              {activeQuestion.mechanic === "single_choice"
                ? "Оберіть один варіант"
                : "Оберіть усі правильні варіанти"}
            </legend>
            {activeQuestion.options.map((option) => {
              const checked = activeSelection.includes(option.id);
              const single = activeQuestion.mechanic === "single_choice";
              return (
                <label className="interactive-option" key={option.id}>
                  <input
                    checked={checked}
                    name={`practice-${activeQuestion.id}`}
                    onChange={() =>
                      setSelected((current) => ({
                        ...current,
                        [activeQuestion.id]: single
                          ? [option.id]
                          : checked
                            ? activeSelection.filter((id) => id !== option.id)
                            : [...activeSelection, option.id],
                      }))
                    }
                    type={single ? "radio" : "checkbox"}
                  />
                  <span>{optionText(option)}</span>
                </label>
              );
            })}
          </fieldset>
          {activeQuestion.saved_answer ? (
            <p className="practice-saved-note" role="status">
              Відповідь збережено. Правильність буде показано після фінішу.
            </p>
          ) : null}
          <div className="interactive-attempt-actions">
            <button
              className="button button-primary"
              disabled={!canSave}
              onClick={() => void saveAnswer()}
              type="button"
            >
              {busy === "answer"
                ? "Зберігаємо…"
                : error
                  ? "Спробувати ще раз"
                  : "Зберегти відповідь"}
            </button>
            {activeIndex > 0 ? (
              <button
                className="button button-quiet"
                onClick={() => setActiveIndex(activeIndex - 1)}
                type="button"
              >
                Попереднє
              </button>
            ) : null}
            {activeQuestion.saved_answer && activeIndex < 9 ? (
              <button
                className="button button-secondary"
                onClick={() => setActiveIndex(activeIndex + 1)}
                type="button"
              >
                Наступне
              </button>
            ) : null}
          </div>
          {allAnswered ? (
            <section className="practice-finish-panel" aria-labelledby="practice-finish-title">
              <h3 id="practice-finish-title">Усі 10 відповідей збережено</h3>
              <p>До натискання кнопки результат і правильні відповіді залишаються прихованими.</p>
              <button
                className="button button-primary"
                disabled={busy === "finish" || !attempt.writable}
                onClick={() => void finishAttempt()}
                type="button"
              >
                {busy === "finish" ? "Завершуємо…" : "Завершити Практику"}
              </button>
            </section>
          ) : null}
        </article>
      ) : null}

      {finish ? (
        <section
          className="interactive-final practice-final"
          aria-labelledby="practice-result-title"
        >
          <p className="eyebrow">Спробу завершено</p>
          <h2 id="practice-result-title">
            {finish.result.correct_count} з {finish.result.total_count} правильних відповідей
          </h2>
          <strong className="interactive-knowledge-level">
            {knowledgeLabels[finish.result.knowledge_level]} ·{" "}
            {finish.result.score_basis_points / 100}%
          </strong>
          <p>Критичних помилок щодо алергенів: {finish.result.critical_error_count}</p>
          {finish.qualified ? (
            <p className="practice-qualified-note">
              Доступ до підсумкового іспиту відкрито та збережено.
            </p>
          ) : (
            <p>Для відкриття підсумкового іспиту потрібно щонайменше 4 правильні відповіді.</p>
          )}
          <div className="practice-review-list" aria-label="Перевірка відповідей">
            {finish.review.map((item) => (
              <ReviewCard item={item} key={item.attempt_question_id} />
            ))}
          </div>
          <div className="interactive-final-actions">
            <button className="button button-primary" onClick={() => void retry()} type="button">
              Повторити Практику
            </button>
            <Link className="button button-secondary" to="/employee/learning">
              Переглянути навчання
            </Link>
          </div>
        </section>
      ) : null}

      {summary?.can_start && !attempt && !finish && summary.availability === "ready" ? (
        <button
          className="button button-primary interactive-start-button"
          disabled={busy === "start"}
          onClick={() => void startAttempt()}
          type="button"
        >
          {busy === "start"
            ? "Готуємо спробу…"
            : history.latest
              ? "Повторити Практику"
              : "Почати Практику"}
        </button>
      ) : null}
      <PracticeHistory history={history} />
    </section>
  );
}

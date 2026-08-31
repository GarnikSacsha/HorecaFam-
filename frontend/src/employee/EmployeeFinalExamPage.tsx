import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, createIdempotencyKey } from "../api/client";
import type {
  FinalExamAnswerResponse,
  FinalExamAttempt,
  FinalExamAttemptQuestion,
  FinalExamAttemptStartResponse,
  FinalExamAttemptTakeoverResponse,
  FinalExamFinishResponse,
  FinalExamHistoryResponse,
  FinalExamQuestionReview,
  FinalExamSummaryResponse,
  InteractiveAnswerPayload,
} from "../api/contracts";
import { LogoutButton } from "../auth/LogoutButton";
import { useSession } from "../session/SessionContext";
import { StatusPill } from "../ui/States";

type BusyAction = "load" | "start" | "answer" | "takeover" | "finish" | null;

function payloadText(payload: Record<string, unknown>, ...keys: string[]): string | null {
  for (const key of keys) {
    const value = payload[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  return null;
}

function optionText(option: FinalExamAttemptQuestion["options"][number]) {
  return payloadText(option.payload, "text", "label", "title") ?? `Варіант ${option.position + 1}`;
}

function answerOptionIds(payload: Record<string, unknown>): string[] {
  if (typeof payload.option_id === "string") return [payload.option_id];
  return Array.isArray(payload.option_ids)
    ? payload.option_ids.filter((item): item is string => typeof item === "string")
    : [];
}

function savedOptionIds(question: FinalExamAttemptQuestion): string[] {
  return question.saved_answer ? answerOptionIds(question.saved_answer.answer_payload) : [];
}

function ReviewCard({ item }: { item: FinalExamQuestionReview }) {
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

export function EmployeeFinalExamPage() {
  const { client, session } = useSession();
  const [summary, setSummary] = useState<FinalExamSummaryResponse | null>(null);
  const [history, setHistory] = useState<FinalExamHistoryResponse>({
    certification: null,
    latest: null,
    best: null,
    history: [],
  });
  const [attempt, setAttempt] = useState<FinalExamAttempt | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [selected, setSelected] = useState<Record<string, string[]>>({});
  const [finish, setFinish] = useState<FinalExamFinishResponse | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState<BusyAction>("load");
  const [error, setError] = useState<string | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const startKey = useRef<string | null>(null);
  const takeoverKey = useRef<string | null>(null);
  const finishKey = useRef<string | null>(null);
  const answerKeys = useRef(new Map<string, string>());
  const locale = session?.user.preferred_locale === "en" ? "en" : "uk";

  const applyAttempt = useCallback((next: FinalExamAttempt) => {
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
        client.request<FinalExamSummaryResponse>("/me/training/final-exam"),
        client.request<FinalExamHistoryResponse>("/me/training/final-exam/attempts"),
      ]);
      setSummary(nextSummary);
      setHistory(nextHistory);
      if (nextSummary.active_attempt) applyAttempt(nextSummary.active_attempt);
      else setAttempt(null);
    } catch {
      setError("Не вдалося завантажити Final Exam. Перевірте мережу та спробуйте ще раз.");
    } finally {
      setBusy(null);
    }
  }, [applyAttempt, client, session]);

  useEffect(() => {
    // Сервер є джерелом стану іспиту; локальна копія оновлюється лише через API.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  const activeQuestion = attempt?.questions[activeIndex] ?? null;
  const activeSelection = activeQuestion ? (selected[activeQuestion.id] ?? []) : [];
  const allAnswered = attempt?.answered_count === 20;
  const answerPayload: InteractiveAnswerPayload | null = (() => {
    if (!activeQuestion || !activeSelection.length) return null;
    return activeQuestion.mechanic === "single_choice"
      ? { mechanic: "single_choice", option_id: activeSelection[0] }
      : {
          mechanic: activeQuestion.mechanic === "recognition" ? "recognition" : "multiple_choice",
          option_ids: activeSelection,
        };
  })();
  const canSave = Boolean(
    activeQuestion &&
    !activeQuestion.saved_answer &&
    answerPayload &&
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
      const response = await client.request<FinalExamAttemptStartResponse>(
        `/me/training/final-exam/attempts?locale=${locale}`,
        {
          method: "POST",
          csrfToken: session.csrf_token,
          idempotencyKey: startKey.current,
        },
      );
      startKey.current = null;
      setFinish(null);
      setConfirming(false);
      applyAttempt(response.attempt);
    } catch {
      setError("Спробу Final Exam не відкрито. Дані не втрачено — повторіть дію.");
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
      const response = await client.request<FinalExamAttemptTakeoverResponse>(
        `/me/training/final-exam/attempts/${attempt.id}/takeover`,
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
      setError("Не вдалося продовжити іспит на цьому пристрої. Оновіть дані.");
    } finally {
      setBusy(null);
    }
  };

  const saveAnswer = async () => {
    if (!session || !attempt || !activeQuestion || !answerPayload || !canSave) return;
    setBusy("answer");
    setError(null);
    const key = answerKeys.current.get(activeQuestion.id) ?? createIdempotencyKey();
    answerKeys.current.set(activeQuestion.id, key);
    try {
      const response = await client.request<FinalExamAnswerResponse>(
        `/me/training/final-exam/attempts/${attempt.id}/answer`,
        {
          method: "POST",
          body: {
            attempt_question_id: activeQuestion.id,
            answer_payload: answerPayload,
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
        setError("Семиденний строк спроби минув. Почніть новий Final Exam.");
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
      const response = await client.request<FinalExamFinishResponse>(
        `/me/training/final-exam/attempts/${attempt.id}/finish`,
        {
          method: "POST",
          body: { lease_generation: attempt.lease_generation },
          csrfToken: session.csrf_token,
          idempotencyKey: finishKey.current,
        },
      );
      finishKey.current = null;
      setFinish(response);
      setConfirming(false);
      setAttempt((current) => (current ? { ...current, status: "completed" } : current));
      setHistory(
        await client.request<FinalExamHistoryResponse>("/me/training/final-exam/attempts"),
      );
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === "ATTEMPT_DEVICE_CONFLICT") {
        setAttempt((current) => (current ? { ...current, writable: false } : current));
      }
      setError("Final Exam не завершено. Збережені відповіді залишилися на сервері.");
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
    const copy: Partial<Record<FinalExamSummaryResponse["availability"], [string, string]>> = {
      no_assignment: ["Навчання ще не призначено", "Final Exam з’явиться після призначення."],
      training_incomplete: ["Спочатку завершіть навчання", "Потім відкриється Практика."],
      practice_required: [
        "Спочатку пройдіть Практику",
        "Потрібно щонайменше 4 з 10 правильних відповідей.",
      ],
      preparing: ["Final Exam готується", "Перевірений банк питань ще не готовий."],
      paused: ["Навчання призупинено", "Історія доступна, нова спроба тимчасово недоступна."],
    };
    return copy[summary.availability] ?? null;
  }, [attempt, finish, summary]);

  return (
    <section className="employee-learning-page practice-page" aria-labelledby="final-exam-title">
      <div className="employee-learning-heading">
        <div>
          <p className="eyebrow">Сертифікація</p>
          <h1 id="final-exam-title">Final Exam</h1>
          <p className="page-description">
            20 запитань. Відповіді зберігаються без підказок; результат і пояснення відкриваються
            тільки після фінального підтвердження.
          </p>
        </div>
        <LogoutButton />
      </div>

      {busy === "load" ? <p aria-live="polite">Завантажуємо Final Exam…</p> : null}
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
      {summary?.certification ? (
        <p className="practice-qualified-note" role="status">
          Сертифікацію отримано. Результат та незмінна історія спроб залишаються доступними.
        </p>
      ) : null}
      {availability ? (
        <div className="interactive-availability" role="status">
          <strong>{availability[0]}</strong>
          <span>{availability[1]}</span>
          {summary?.availability === "practice_required" ? (
            <Link className="button button-secondary" to="/employee/practice">
              Перейти до Практики
            </Link>
          ) : null}
        </div>
      ) : null}

      {attempt && !finish && !attempt.writable ? (
        <div className="interactive-device-card">
          <strong>Відкрито на іншому пристрої</strong>
          <p>Для збереження відповідей підтвердьте продовження на цьому пристрої.</p>
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
            <span>{attempt.answered_count} з 20 відповідей збережено</span>
            <progress max={20} value={attempt.answered_count}>
              {attempt.answered_count} з 20
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
                    name={`final-exam-${activeQuestion.id}`}
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
              Відповідь збережено. Правильність буде показано після фінальної відправки.
            </p>
          ) : null}
          <div className="interactive-attempt-actions">
            <button
              className="button button-primary"
              disabled={!canSave}
              onClick={() => void saveAnswer()}
              type="button"
            >
              {busy === "answer" ? "Зберігаємо…" : "Зберегти відповідь"}
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
            {activeQuestion.saved_answer && activeIndex < 19 ? (
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
            <section className="practice-finish-panel" aria-labelledby="final-exam-finish-title">
              <h3 id="final-exam-finish-title">Усі 20 відповідей збережено</h3>
              <p>Після підтвердження відповіді змінити не можна.</p>
              <button
                className="button button-primary"
                disabled={busy === "finish" || !attempt.writable}
                onClick={() => setConfirming(true)}
                type="button"
              >
                Завершити Final Exam
              </button>
            </section>
          ) : null}
        </article>
      ) : null}

      {confirming ? (
        <div className="confirmation-layer">
          <div
            className="confirmation-dialog"
            role="dialog"
            aria-modal="true"
            aria-label="Підтвердити завершення"
          >
            <h2>Надіслати всі відповіді?</h2>
            <p>Після цього одразу з’являться результат, правильні відповіді та пояснення.</p>
            <div className="compact-actions">
              <button
                className="button button-primary"
                onClick={() => void finishAttempt()}
                type="button"
              >
                {busy === "finish" ? "Завершуємо…" : "Підтвердити та завершити"}
              </button>
              <button
                className="button button-quiet"
                disabled={busy === "finish"}
                onClick={() => setConfirming(false)}
                type="button"
              >
                Повернутися до відповідей
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {finish ? (
        <section
          className="interactive-final practice-final"
          aria-labelledby="final-exam-result-title"
        >
          <p className="eyebrow">Final Exam завершено</p>
          <h2 id="final-exam-result-title">
            {finish.result.correct_count} з {finish.result.total_count} правильних відповідей
          </h2>
          <StatusPill tone={finish.result.pass_status === "passed" ? "success" : "warning"}>
            {finish.result.pass_status === "passed" ? "Пройдено" : "Не пройдено"}
          </StatusPill>
          <p>
            Результат: {finish.result.score_basis_points / 100}% · критичних помилок:{" "}
            {finish.result.critical_error_count}
          </p>
          {finish.certification ? (
            <p className="practice-qualified-note">Сертифікацію збережено.</p>
          ) : null}
          <div className="practice-review-list" aria-label="Перевірка відповідей Final Exam">
            {finish.review.map((item) => (
              <ReviewCard item={item} key={item.attempt_question_id} />
            ))}
          </div>
          {finish.retake_available ? (
            <button className="button button-primary" onClick={() => void retry()} type="button">
              Повторити Final Exam
            </button>
          ) : null}
        </section>
      ) : null}

      {summary?.can_start && !attempt && !finish ? (
        <button
          className="button button-primary interactive-start-button"
          disabled={busy === "start"}
          onClick={() => void startAttempt()}
          type="button"
        >
          {busy === "start"
            ? "Готуємо спробу…"
            : history.latest
              ? "Повторити Final Exam"
              : "Почати Final Exam"}
        </button>
      ) : null}

      {history.history.length ? (
        <section className="interactive-history" aria-labelledby="final-exam-history-title">
          <h2 id="final-exam-history-title">Історія Final Exam</h2>
          <ol className="results-history-list">
            {history.history.map((result) => (
              <li key={result.result_id}>
                <strong>{result.correct_count}/20</strong>
                <span>{result.pass_status === "passed" ? "Пройдено" : "Не пройдено"}</span>
                <time dateTime={result.completed_at}>
                  {new Intl.DateTimeFormat("uk-UA", { dateStyle: "medium" }).format(
                    new Date(result.completed_at),
                  )}
                </time>
              </li>
            ))}
          </ol>
        </section>
      ) : null}
    </section>
  );
}

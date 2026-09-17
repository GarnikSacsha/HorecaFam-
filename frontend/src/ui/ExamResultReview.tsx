import { useState } from "react";
import type {
  FinalExamQuestionReview,
  FinalExamResult,
  FinalExamResultSummary,
} from "../api/contracts";
import { StatusPill } from "./States";

export function ExamResultSummary({
  result,
}: {
  result: FinalExamResult | FinalExamResultSummary;
}) {
  return (
    <div className="exam-result-summary">
      <strong className="exam-result-score">{result.score_basis_points / 100}%</strong>
      <div>
        <StatusPill tone={result.pass_status === "passed" ? "success" : "warning"}>
          {result.pass_status === "passed" ? "Пройдено" : "Не пройдено"}
        </StatusPill>
        <p>
          {result.correct_count} з {result.total_count} правильних відповідей
        </p>
        <p>Помилок: {result.total_count - result.correct_count}</p>
        <p>Критичних помилок: {result.critical_error_count}</p>
        <time dateTime={result.completed_at}>
          {new Intl.DateTimeFormat("uk-UA", { dateStyle: "medium", timeStyle: "short" }).format(
            new Date(result.completed_at),
          )}
        </time>
      </div>
    </div>
  );
}

function text(payload: Record<string, unknown>) {
  const value = payload.stem ?? payload.text ?? payload.label ?? payload.title;
  return typeof value === "string" ? value : "";
}

export function ExamResultReview({ items }: { items: FinalExamQuestionReview[] }) {
  const [showAll, setShowAll] = useState(false);
  const mistakes = items.filter((item) => !item.is_correct);
  const visible = showAll ? items : mistakes;
  return (
    <section className="exam-review" aria-label="Розбір відповідей">
      <h3>{showAll ? "Усі відповіді" : "Що повторити"}</h3>
      {!mistakes.length && !showAll ? <p>У цій спробі всі відповіді правильні.</p> : null}
      <button
        className="button button-secondary"
        type="button"
        aria-pressed={showAll}
        onClick={() => setShowAll((value) => !value)}
      >
        {showAll ? "Лише помилки" : `Усі відповіді (${items.length})`}
      </button>
      <div className="practice-review-list">
        {visible.map((item) => {
          const answer = item.answer.answer_payload;
          const selected =
            typeof answer.option_id === "string"
              ? [answer.option_id]
              : Array.isArray(answer.option_ids)
                ? answer.option_ids
                : [];
          const names = (ids: unknown[]) =>
            item.options
              .filter((option) => ids.includes(option.id))
              .map((option) => text(option.payload))
              .join(", ");
          return (
            <article
              className={`practice-review-card ${item.is_correct ? "is-correct" : "is-incorrect"}`}
              key={item.attempt_question_id}
            >
              <h4>
                {item.position + 1}. {text(item.prompt_payload)}
              </h4>
              <p>
                <strong>Ваша відповідь:</strong> {names(selected)}
              </p>
              {!item.is_correct ? (
                <p>
                  <strong>Правильна відповідь:</strong> {names(item.correct_option_ids)}
                </p>
              ) : null}
              {item.is_critical_error ? (
                <p className="practice-critical-note">Критична помилка щодо алергенів.</p>
              ) : null}
              <p>{text(item.explanation_payload)}</p>
            </article>
          );
        })}
      </div>
    </section>
  );
}

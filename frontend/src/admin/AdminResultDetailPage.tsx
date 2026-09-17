import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import type {
  AdminAttentionCollection,
  AdminEmployeeResultsDetailResponse,
  AdminRetakeRequirementCollection,
  FinalExamFinishResponse,
} from "../api/contracts";
import { useSession } from "../session/SessionContext";
import { StatusPill } from "../ui/States";
import { ExamResultReview, ExamResultSummary } from "../ui/ExamResultReview";

export function AdminResultDetailPage() {
  const { employeeId } = useParams();
  const { client, session, status } = useSession();
  const organizationId = session?.organization_access.find(
    (item) => item.is_organization_admin,
  )?.organization_id;
  const [detail, setDetail] = useState<AdminEmployeeResultsDetailResponse | null>(null);
  const [attentionCount, setAttentionCount] = useState(0);
  const [currentRetakeCount, setCurrentRetakeCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [review, setReview] = useState<FinalExamFinishResponse | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [reviewLoading, setReviewLoading] = useState(false);

  const openReview = async (attemptId: string) => {
    setReviewLoading(true);
    setReviewError(null);
    setReview(null);
    try {
      setReview(
        await client.request<FinalExamFinishResponse>(
          `/organizations/${organizationId}/results/final-exams/${attemptId}`,
        ),
      );
    } catch {
      setReviewError("Не вдалося завантажити розбір. Повторіть дію.");
    } finally {
      setReviewLoading(false);
    }
  };

  useEffect(() => {
    if (status !== "authenticated" || !organizationId || !employeeId) return;
    client
      .request<AdminEmployeeResultsDetailResponse>(
        `/organizations/${organizationId}/results/employees/${employeeId}`,
      )
      .then((response) => {
        setDetail(response);
        void Promise.all([
          client.request<AdminAttentionCollection>(
            `/organizations/${organizationId}/employees/${employeeId}/attention`,
          ),
          client.request<AdminRetakeRequirementCollection>(
            `/organizations/${organizationId}/retake-requirements?q=${encodeURIComponent(employeeId)}`,
          ),
        ])
          .then(([attention, retakes]) => {
            setAttentionCount(attention.items.filter((item) => item.state !== "resolved").length);
            setCurrentRetakeCount(
              retakes.items.filter((item) => item.state === "proposed" || item.state === "active")
                .length,
            );
          })
          .catch(() => {
            // Follow-up є додатковим контекстом: незмінна історія Results доступна незалежно.
          });
      })
      .catch(() => setError("Не вдалося завантажити історію результатів."));
  }, [client, employeeId, organizationId, status]);

  if (error)
    return (
      <section className="admin-page">
        <p className="inline-error" role="alert">
          {error}
        </p>
      </section>
    );
  if (!detail) return <p aria-live="polite">Завантажуємо історію…</p>;
  const name =
    [detail.employee.first_name, detail.employee.last_name].filter(Boolean).join(" ") ||
    "Працівник";
  return (
    <section className="admin-page results-page" aria-labelledby="result-detail-title">
      <Link className="text-link" to="/admin/results">
        ← Усі результати
      </Link>
      <div>
        <p className="eyebrow">Історія працівника</p>
        <h1 id="result-detail-title">{name}</h1>
      </div>
      <section className="bounded-section" aria-labelledby="certification-title">
        <h2 id="certification-title">Сертифікація</h2>
        {detail.final_exam.certification ? (
          <StatusPill tone="success">Сертифіковано</StatusPill>
        ) : (
          <StatusPill tone="neutral">Не сертифіковано</StatusPill>
        )}
        {detail.final_exam.best ? (
          <p>
            Найкращий результат: <strong>{detail.final_exam.best.correct_count}/20</strong>
          </p>
        ) : (
          <p>Final Exam ще не завершувався.</p>
        )}
      </section>
      <section className="bounded-section" aria-labelledby="follow-up-title">
        <div>
          <p className="eyebrow">Attention і перескладання</p>
          <h2 id="follow-up-title">Поточний follow-up</h2>
        </div>
        <p>
          Відкриті кейси: <strong>{attentionCount}</strong> · поточні вимоги:{" "}
          <strong>{currentRetakeCount}</strong>
        </p>
        <Link className="button button-secondary" to="/admin/attention">
          Відкрити робочу чергу
        </Link>
      </section>
      <section className="bounded-section">
        <h2>Підсумок навчання</h2>
        <p>
          Практика:{" "}
          {detail.employee.latest_practice_score_basis_points == null
            ? "Ще немає результату"
            : `${detail.employee.latest_practice_score_basis_points / 100}%`}
        </p>
        <p>Завершених спроб іспиту: {detail.final_exam.history.length}</p>
        {detail.final_exam.latest ? (
          <>
            <h3>Останній іспит</h3>
            <ExamResultSummary result={detail.final_exam.latest} />
          </>
        ) : null}
      </section>
      {reviewLoading ? <p role="status">Завантажуємо розбір…</p> : null}
      {reviewError ? <p role="alert">{reviewError}</p> : null}
      {review ? (
        <section className="bounded-section">
          <h2>Обрана спроба</h2>
          <ExamResultSummary result={review.result} />
          <ExamResultReview key={review.result.id} items={review.review} />
        </section>
      ) : null}
      {detail.final_exam.history.length ? (
        <ol className="results-history-list">
          {detail.final_exam.history.map((result) => (
            <li key={result.result_id}>
              <strong>{result.correct_count}/20</strong>
              <span>{result.pass_status === "passed" ? "Пройдено" : "Не пройдено"}</span>
              <button
                className="button button-secondary"
                disabled={reviewLoading}
                type="button"
                onClick={() => void openReview(result.attempt_id)}
              >
                Розбір спроби
              </button>
              <time dateTime={result.completed_at}>
                {new Date(result.completed_at).toLocaleDateString("uk-UA")}
              </time>
              {result.critical_error_count ? (
                <span>Критичні помилки: {result.critical_error_count}</span>
              ) : null}
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}

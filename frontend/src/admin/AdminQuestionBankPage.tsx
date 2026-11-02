import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, createIdempotencyKey } from "../api/client";
import type {
  FinalExamReadinessResponse,
  InteractiveTrainingReadinessResponse,
  LocationSummary,
  MenuVersionCollection,
  PracticeReadinessResponse,
  QuestionCandidateCollection,
  QuestionCandidateEditedPayload,
  QuestionCandidateGenerateResponse,
  QuestionCandidateResponse,
  QuestionCandidateStatus,
  TrainingVersionCollection,
  TrainingVersionDetail,
  TrainingVersionSummary,
} from "../api/contracts";
import { LogoutButton } from "../auth/LogoutButton";
import { readinessCodeLabel, readinessStatusLabel } from "./readinessLabels";
import { useSession } from "../session/SessionContext";
import { LoadingState, StatusPill } from "../ui/States";
import { AdminAuthoredQuestions } from "./AdminAuthoredQuestions";

type CandidateFilter = QuestionCandidateStatus | "all";

const mechanicLabels: Record<string, string> = {
  single_choice: "Один варіант",
  multiple_choice: "Кілька варіантів",
  recognition: "Розпізнавання",
  matching: "Відповідність",
  ordering: "Порядок",
  assembly: "Збірка",
};

const statusLabels: Record<QuestionCandidateStatus, string> = {
  needs_review: "Потребує перевірки",
  approved: "Схвалено",
  rejected: "Відхилено",
  stale: "Застаріло",
};

function candidateTone(status: QuestionCandidateStatus) {
  if (status === "approved") return "success" as const;
  if (status === "rejected" || status === "stale") return "danger" as const;
  return "warning" as const;
}

function readinessTone(status: string) {
  if (status === "ready") return "success" as const;
  if (status === "warning" || status === "processing") return "warning" as const;
  return "danger" as const;
}

function sourceIdentity(source: QuestionCandidateResponse["sources"][number]): string {
  return (
    source.menu_item_version_component_id ??
    source.menu_item_version_allergen_id ??
    source.menu_item_version_id ??
    source.standard_rule_version_id ??
    "Джерело без ідентифікатора"
  );
}

function CandidateCard({
  candidate,
  lessonTitle,
  selected,
  busy,
  onSelect,
  onApprove,
  onReject,
}: {
  candidate: QuestionCandidateResponse;
  lessonTitle?: string;
  selected: boolean;
  busy: boolean;
  onSelect: (candidateId: string, selected: boolean) => void;
  onApprove: (
    candidate: QuestionCandidateResponse,
    editedPayload?: QuestionCandidateEditedPayload,
  ) => Promise<boolean>;
  onReject: (candidate: QuestionCandidateResponse) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [stem, setStem] = useState(candidate.prompt_payload.stem);
  const [options, setOptions] = useState(() =>
    candidate.prompt_payload.options.map((option) => ({ ...option })),
  );
  const [correctKey, setCorrectKey] = useState(
    candidate.answer_payload.correct_option_keys[0] ?? "",
  );
  const [explanation, setExplanation] = useState(candidate.explanation_payload.text);
  const reviewable = candidate.status === "needs_review";

  const submitEdited = async () => {
    const approved = await onApprove(candidate, {
      prompt_payload: { ...candidate.prompt_payload, locale: "uk", stem, options },
      answer_payload: { correct_option_keys: [correctKey] },
      explanation_payload: { locale: "uk", text: explanation },
    });
    if (approved) setEditing(false);
  };

  return (
    <article className="question-candidate-card" aria-labelledby={`candidate-${candidate.id}`}>
      <div className="question-candidate-heading">
        <div>
          <div className="question-candidate-badges">
            <StatusPill tone={candidateTone(candidate.status)}>
              {statusLabels[candidate.status]}
            </StatusPill>
            <StatusPill tone="info">
              {mechanicLabels[candidate.mechanic] ?? candidate.mechanic}
            </StatusPill>
            <span className="candidate-revision">Ревізія {candidate.revision}</span>
          </div>
          <h3 id={`candidate-${candidate.id}`}>{candidate.prompt_payload.stem}</h3>
        </div>
        {reviewable ? (
          <label className="candidate-select">
            <input
              type="checkbox"
              checked={selected}
              onChange={(event) => onSelect(candidate.id, event.target.checked)}
              aria-label={`Вибрати ${candidate.prompt_payload.stem}`}
            />
            До пакета
          </label>
        ) : null}
      </div>

      {editing ? (
        <form
          className="candidate-editor"
          aria-label={`Редагування ${candidate.prompt_payload.stem}`}
          onSubmit={(event) => {
            event.preventDefault();
            void submitEdited();
          }}
        >
          <div className="field-group">
            <label htmlFor={`candidate-stem-${candidate.id}`}>Текст питання</label>
            <textarea
              id={`candidate-stem-${candidate.id}`}
              value={stem}
              onChange={(event) => setStem(event.target.value)}
              required
            />
          </div>
          <fieldset className="candidate-options-editor">
            <legend>Варіанти й правильна відповідь</legend>
            {options.map((option, index) => (
              <div className="candidate-option-editor" key={option.stable_key}>
                <input
                  type="radio"
                  name={`correct-${candidate.id}`}
                  checked={correctKey === option.stable_key}
                  onChange={() => setCorrectKey(option.stable_key)}
                  aria-label={`Позначити варіант ${index + 1} правильним`}
                />
                <label className="sr-only" htmlFor={`candidate-option-${candidate.id}-${index}`}>
                  Варіант {index + 1}
                </label>
                <input
                  id={`candidate-option-${candidate.id}-${index}`}
                  value={option.text}
                  onChange={(event) =>
                    setOptions((current) =>
                      current.map((item, itemIndex) =>
                        itemIndex === index ? { ...item, text: event.target.value } : item,
                      ),
                    )
                  }
                  required
                />
              </div>
            ))}
          </fieldset>
          <div className="field-group">
            <label htmlFor={`candidate-explanation-${candidate.id}`}>Пояснення</label>
            <textarea
              id={`candidate-explanation-${candidate.id}`}
              value={explanation}
              onChange={(event) => setExplanation(event.target.value)}
              required
            />
          </div>
          <div className="compact-actions">
            <button className="button button-primary" type="submit" disabled={busy}>
              Зберегти та схвалити
            </button>
            <button
              className="button button-quiet"
              type="button"
              onClick={() => setEditing(false)}
              disabled={busy}
            >
              Скасувати
            </button>
          </div>
        </form>
      ) : (
        <>
          <ol className="candidate-options">
            {candidate.prompt_payload.options.map((option) => (
              <li key={option.stable_key}>
                <span>{option.text}</span>
                {candidate.answer_payload.correct_option_keys.includes(option.stable_key) ? (
                  <span className="correct-answer-note">Правильна відповідь</span>
                ) : null}
              </li>
            ))}
          </ol>
          <p className="candidate-explanation">
            <strong>Пояснення:</strong> {candidate.explanation_payload.text}
          </p>
          {candidate.explanation_payload.authoring && (
            <div className="candidate-provenance">
              <h4>Підстави авторського питання</h4>
              <blockquote>{candidate.explanation_payload.authoring.source_quote}</blockquote>
              <ul>
                {candidate.prompt_payload.options.map((option) => (
                  <li key={option.stable_key}>
                    <strong>{option.text}:</strong>{" "}
                    {candidate.explanation_payload.authoring?.option_rationales[option.stable_key]}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}

      <details className="candidate-provenance">
        <summary>Звідки взято питання</summary>
        <dl>
          <div>
            <dt>Урок</dt>
            <dd>{lessonTitle ?? "Урок поточного навчання"}</dd>
          </div>
          <div>
            <dt>Правило / механіка</dt>
            <dd>{mechanicLabels[candidate.mechanic] ?? candidate.mechanic}</dd>
          </div>
          <div>
            <dt>Технічний відбиток джерела</dt>
            <dd className="candidate-fingerprint">{candidate.source_fingerprint}</dd>
          </div>
        </dl>
        <ul className="candidate-source-list">
          {candidate.sources.map((source, index) => (
            <li key={`${source.source_role}-${sourceIdentity(source)}-${index}`}>
              <span>{source.source_role}</span>
              <code>{sourceIdentity(source)}</code>
            </li>
          ))}
        </ul>
      </details>

      {reviewable && !editing ? (
        <div className="compact-actions candidate-actions">
          <button
            className="button button-primary"
            type="button"
            onClick={() => void onApprove(candidate)}
            disabled={busy}
          >
            Схвалити
          </button>
          <button
            className="button button-quiet"
            type="button"
            onClick={() => setEditing(true)}
            disabled={busy || !!candidate.explanation_payload.authoring}
          >
            Редагувати
          </button>
          <button
            className="button button-quiet button-danger"
            type="button"
            onClick={() => void onReject(candidate)}
            disabled={busy}
          >
            Відхилити
          </button>
        </div>
      ) : null}
    </article>
  );
}

export function AdminQuestionBankPage() {
  const { client, session, status } = useSession();
  const organizationId = session?.organization_access.find(
    (access) => access.is_organization_admin,
  )?.organization_id;
  const errorRef = useRef<HTMLDivElement>(null);
  const [locations, setLocations] = useState<LocationSummary[]>([]);
  const [locationId, setLocationId] = useState("");
  const [menuVersionId, setMenuVersionId] = useState<string | null>(null);
  const [menuVersionNumber, setMenuVersionNumber] = useState<number | null>(null);
  const [lessonTitles, setLessonTitles] = useState<Map<string, string>>(() => new Map());
  const [trainingVersion, setTrainingVersion] = useState<TrainingVersionSummary | null>(null);
  const [candidates, setCandidates] = useState<QuestionCandidateResponse[]>([]);
  const [candidateTotal, setCandidateTotal] = useState(0);
  const [candidateFilter, setCandidateFilter] = useState<CandidateFilter>("needs_review");
  const [readiness, setReadiness] = useState<InteractiveTrainingReadinessResponse | null>(null);
  const [practiceReadiness, setPracticeReadiness] = useState<PracticeReadinessResponse | null>(
    null,
  );
  const [finalExamReadiness, setFinalExamReadiness] = useState<FinalExamReadinessResponse | null>(
    null,
  );
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);

  const loadWorkspace = useCallback(
    async (selectedLocationId: string, filter: CandidateFilter) => {
      if (!organizationId || !selectedLocationId) return;
      setLoading(true);
      setError(null);
      try {
        const base = `/organizations/${organizationId}/locations/${selectedLocationId}`;
        const candidatePath =
          filter === "all"
            ? `${base}/question-candidates`
            : `${base}/question-candidates?status=${filter}`;
        const [menus, trainings, queue] = await Promise.all([
          client.request<MenuVersionCollection>(`${base}/menu-versions`),
          client.request<TrainingVersionCollection>(`${base}/training-versions`),
          client.request<QuestionCandidateCollection>(candidatePath),
        ]);
        const publishedTraining = trainings.published;
        setMenuVersionId(menus.current_published?.id ?? null);
        setMenuVersionNumber(menus.current_published?.version_number ?? null);
        setTrainingVersion(publishedTraining);
        setCandidates(queue.items);
        setCandidateTotal(queue.total);
        setSelectedIds(new Set());
        if (publishedTraining) {
          const [lessonReadiness, wholeMenuReadiness, examReadiness, trainingDetail] =
            await Promise.all([
              client.request<InteractiveTrainingReadinessResponse>(
                `${base}/training-versions/${publishedTraining.id}/interactive-training/readiness`,
              ),
              client.request<PracticeReadinessResponse>(
                `${base}/training-versions/${publishedTraining.id}/practice/readiness`,
              ),
              client.request<FinalExamReadinessResponse>(
                `${base}/training-versions/${publishedTraining.id}/final-exam/readiness`,
              ),
              client
                .request<TrainingVersionDetail>(`${base}/training-versions/${publishedTraining.id}`)
                .catch(() => null),
            ]);
          const titles = new Map<string, string>();
          for (const trainingModule of trainingDetail?.modules ?? []) {
            for (const lesson of trainingModule.lessons ?? []) {
              titles.set(lesson.id, lesson.title_uk);
              if (lesson.lesson_version_id) titles.set(lesson.lesson_version_id, lesson.title_uk);
            }
          }
          setLessonTitles(titles);
          setReadiness(lessonReadiness);
          setPracticeReadiness(wholeMenuReadiness);
          setFinalExamReadiness(examReadiness);
        } else {
          setReadiness(null);
          setPracticeReadiness(null);
          setFinalExamReadiness(null);
        }
      } catch {
        setError("Не вдалося завантажити Банк питань. Перевірте з’єднання та повторіть.");
      } finally {
        setLoading(false);
      }
    },
    [client, organizationId],
  );

  useEffect(() => {
    if (status !== "authenticated" || !organizationId) return;
    let active = true;
    client
      .request<LocationSummary[]>(`/organizations/${organizationId}/locations`)
      .then((response) => {
        if (!active) return;
        const available = response.filter((location) => location.status === "active");
        setLocations(available);
        const first = available[0]?.id ?? "";
        setLocationId(first);
        if (first) void loadWorkspace(first, "needs_review");
        else setLoading(false);
      })
      .catch(() => {
        if (active) {
          setError("Не вдалося завантажити локації.");
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [client, loadWorkspace, organizationId, status]);

  const mutationError = (caught: unknown, atomic = false) => {
    if (atomic) {
      setError("Пакет не схвалено. Жоден кандидат не змінений; перевірте склад пакета.");
    } else if (caught instanceof ApiError && caught.code === "QUESTION_CANDIDATE_STALE") {
      setError("Кандидат застарів. Оновіть дані та перевірте нову версію джерела.");
    } else if (caught instanceof ApiError && caught.code === "REVISION_CONFLICT") {
      setError("Кандидата вже змінили. Локальні правки збережено — оновіть дані перед повтором.");
    } else {
      setError("Дію не виконано. Дані кандидата залишилися без змін.");
    }
  };

  const generate = async (source: "menu" | "standards" = "menu") => {
    if (!organizationId || !locationId || !trainingVersion || !session) return;
    if (source === "menu" && !menuVersionId) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await client.request<QuestionCandidateGenerateResponse>(
        source === "standards"
          ? `/organizations/${organizationId}/locations/${locationId}/training-versions/${trainingVersion.id}/standard-question-candidates/generate`
          : `/organizations/${organizationId}/locations/${locationId}/question-candidates/generate`,
        {
          method: "POST",
          body:
            source === "menu"
              ? { menu_version_id: menuVersionId, training_version_id: trainingVersion.id }
              : undefined,
          csrfToken: session.csrf_token,
          idempotencyKey: createIdempotencyKey(),
        },
      );
      setNotice(
        `Створено ${result.created_count}; вже існувало ${result.existing_count}; застаріло ${result.stale_candidate_count}.`,
      );
      await loadWorkspace(locationId, candidateFilter);
    } catch (caught) {
      mutationError(caught);
    } finally {
      setBusy(false);
    }
  };

  const approve = async (
    candidate: QuestionCandidateResponse,
    editedPayload?: QuestionCandidateEditedPayload,
  ): Promise<boolean> => {
    if (!organizationId || !locationId || !session) return false;
    setBusy(true);
    setError(null);
    try {
      await client.request(
        `/organizations/${organizationId}/locations/${locationId}/question-candidates/${candidate.id}/approve`,
        {
          method: "POST",
          body: { expected_revision: candidate.revision, edited_payload: editedPayload ?? null },
          csrfToken: session.csrf_token,
        },
      );
      setNotice("Кандидата схвалено та опубліковано в Банку питань.");
      await loadWorkspace(locationId, candidateFilter);
      return true;
    } catch (caught) {
      mutationError(caught);
      return false;
    } finally {
      setBusy(false);
    }
  };

  const reject = async (candidate: QuestionCandidateResponse) => {
    if (!organizationId || !locationId || !session) return;
    setBusy(true);
    setError(null);
    try {
      await client.request(
        `/organizations/${organizationId}/locations/${locationId}/question-candidates/${candidate.id}/reject`,
        {
          method: "POST",
          body: { expected_revision: candidate.revision, reason_code: "ADMIN_REJECTED" },
          csrfToken: session.csrf_token,
        },
      );
      setNotice("Кандидата відхилено.");
      await loadWorkspace(locationId, candidateFilter);
    } catch (caught) {
      mutationError(caught);
    } finally {
      setBusy(false);
    }
  };

  const batchApprove = async () => {
    if (!organizationId || !locationId || !session || !selectedIds.size) return;
    const items = candidates
      .filter((candidate) => selectedIds.has(candidate.id))
      .map((candidate) => ({ candidate_id: candidate.id, expected_revision: candidate.revision }));
    setBusy(true);
    setError(null);
    try {
      await client.request(
        `/organizations/${organizationId}/locations/${locationId}/question-candidates/batch-approve`,
        { method: "POST", body: { items }, csrfToken: session.csrf_token },
      );
      setNotice(`Схвалено кандидатів: ${items.length}.`);
      await loadWorkspace(locationId, candidateFilter);
    } catch (caught) {
      mutationError(caught, true);
    } finally {
      setBusy(false);
    }
  };

  if (loading && !locations.length) return <LoadingState label="Завантажуємо Банк питань…" />;

  return (
    <section className="admin-page question-bank-page" aria-labelledby="question-bank-title">
      <div className="page-heading-row">
        <div>
          <p className="eyebrow">Контроль джерел</p>
          <h1 id="question-bank-title">Банк питань</h1>
          <p className="page-description">
            Перевіряйте автоматично створені кандидати, їхні джерела та готовність кожного уроку.
          </p>
        </div>
        <LogoutButton />
      </div>

      <div className="question-bank-toolbar">
        <div className="field-group">
          <label htmlFor="question-location">Локація</label>
          <select
            id="question-location"
            disabled={busy || loading}
            value={locationId}
            onChange={(event) => {
              setLocationId(event.target.value);
              void loadWorkspace(event.target.value, candidateFilter);
            }}
          >
            {locations.map((location) => (
              <option key={location.id} value={location.id}>
                {location.name}
              </option>
            ))}
          </select>
        </div>
        <div className="question-version-context" aria-label="Версії джерел">
          <span>
            Меню:{" "}
            {menuVersionNumber !== null
              ? `опублікована версія ${menuVersionNumber}`
              : "немає опублікованої версії"}
          </span>
          <span>
            Навчання:{" "}
            {trainingVersion
              ? `опублікована версія ${trainingVersion.version_number}`
              : "немає опублікованої версії"}
          </span>
        </div>
        <button
          className="button button-primary"
          type="button"
          onClick={() => void generate()}
          disabled={busy || !menuVersionId || !trainingVersion}
        >
          Згенерувати кандидатів
        </button>
        <button
          className="button button-secondary"
          type="button"
          onClick={() => void generate("standards")}
          disabled={busy || !trainingVersion}
        >
          Кандидати зі стандартів
        </button>
      </div>

      {error ? (
        <div className="error-summary" role="alert" tabIndex={-1} ref={errorRef}>
          <h2>Потрібна увага</h2>
          <p>{error}</p>
          <button
            className="button button-quiet"
            type="button"
            onClick={() => void loadWorkspace(locationId, candidateFilter)}
          >
            Оновити дані
          </button>
        </div>
      ) : null}
      {notice ? (
        <p className="success-message" aria-live="polite">
          {notice}
        </p>
      ) : null}

      {organizationId && locationId && menuVersionId && trainingVersion && session ? (
        <AdminAuthoredQuestions
          key={`${organizationId}/${locationId}/${trainingVersion.id}/${menuVersionId}`}
          client={client}
          base={`/organizations/${organizationId}/locations/${locationId}`}
          csrfToken={session.csrf_token}
          menuId={menuVersionId}
          trainingId={trainingVersion.id}
          disabled={busy || loading}
          onBusy={setBusy}
          onRefresh={() => loadWorkspace(locationId, candidateFilter)}
        />
      ) : null}

      <section className="question-readiness" aria-labelledby="readiness-title">
        <div className="dataset-header">
          <div>
            <p className="eyebrow">Опубліковане навчання</p>
            <h2 id="readiness-title">Готовність уроків</h2>
          </div>
          {readiness ? (
            <span className="readiness-summary">
              {readiness.lessons.filter((lesson) => lesson.can_start).length} із{" "}
              {readiness.lessons.length} уроків готові
            </span>
          ) : null}
        </div>
        {practiceReadiness ? (
          <article
            className="readiness-card practice-readiness-card"
            aria-labelledby="practice-readiness-title"
          >
            <div className="readiness-card-heading">
              <div>
                <p className="eyebrow">Усе опубліковане меню</p>
                <h3 id="practice-readiness-title">Готовність Практики</h3>
              </div>
              <StatusPill tone={readinessTone(practiceReadiness.status)}>
                {readinessStatusLabel(practiceReadiness.status)}
              </StatusPill>
            </div>
            <p className="practice-readiness-count" role="status" aria-atomic="true">
              <strong>
                {practiceReadiness.eligible_count} / {practiceReadiness.required_count}
              </strong>{" "}
              різних позицій меню
            </p>
            <p>
              Повна ротація від {practiceReadiness.rotation_target_count}:{" "}
              {practiceReadiness.rotation_supported ? "підтримується" : "ще обмежена"}
            </p>
            {[...practiceReadiness.blocking_codes, ...practiceReadiness.warning_codes].map(
              (code) => (
                <p className="readiness-note" key={code} title={code}>
                  {readinessCodeLabel(code)}
                </p>
              ),
            )}
          </article>
        ) : null}
        {finalExamReadiness ? (
          <article
            className="readiness-card practice-readiness-card"
            aria-labelledby="final-exam-readiness-title"
          >
            <div className="readiness-card-heading">
              <div>
                <p className="eyebrow">Сертифікація</p>
                <h3 id="final-exam-readiness-title">Готовність підсумкового іспиту</h3>
              </div>
              <StatusPill tone={readinessTone(finalExamReadiness.status)}>
                {readinessStatusLabel(finalExamReadiness.status)}
              </StatusPill>
            </div>
            <p className="practice-readiness-count" role="status">
              <strong>
                {finalExamReadiness.eligible_count} / {finalExamReadiness.required_count}
              </strong>{" "}
              перевірених питань
            </p>
            <p>
              Повна ротація від {finalExamReadiness.rotation_target_count}:{" "}
              {finalExamReadiness.rotation_supported ? "підтримується" : "ще обмежена"}
            </p>
            {[...finalExamReadiness.blocking_codes, ...finalExamReadiness.warning_codes].map(
              (code) => (
                <p className="readiness-note" key={code} title={code}>
                  {readinessCodeLabel(code)}
                </p>
              ),
            )}
          </article>
        ) : null}
        {readiness?.lessons.length ? (
          <div className="readiness-grid">
            {readiness.lessons.map((lesson, index) => (
              <article className="readiness-card" key={lesson.lesson_version_id}>
                <div className="readiness-card-heading">
                  <h3 className="readiness-lesson-title">
                    {lessonTitles.get(lesson.lesson_id) ?? `Урок ${index + 1}`}
                  </h3>
                  <StatusPill tone={readinessTone(lesson.status)}>
                    {readinessStatusLabel(lesson.status)}
                  </StatusPill>
                </div>
                <p>
                  Питань: {lesson.eligible_count} з потрібних {lesson.required_count} · Різні
                  варіанти при повторі: {lesson.rotation_supported ? "так" : "обмежено"}
                </p>
                {[...lesson.blocking_codes, ...lesson.warning_codes].map((code) => (
                  <p className="readiness-note" key={code} title={code}>
                    {readinessCodeLabel(code)}
                  </p>
                ))}
              </article>
            ))}
          </div>
        ) : (
          <p className="empty-state">
            Для опублікованого навчання перевірку знань ще не налаштовано.
          </p>
        )}
      </section>

      <section className="question-queue" aria-labelledby="candidate-queue-title">
        <div className="dataset-header question-queue-heading">
          <div>
            <p className="eyebrow">Черга перевірки</p>
            <h2 id="candidate-queue-title">{candidateTotal} кандидати</h2>
          </div>
          <div className="question-queue-controls">
            <div className="field-group">
              <label htmlFor="candidate-status">Статус</label>
              <select
                id="candidate-status"
                value={candidateFilter}
                onChange={(event) => {
                  const nextFilter = event.target.value as CandidateFilter;
                  setCandidateFilter(nextFilter);
                  void loadWorkspace(locationId, nextFilter);
                }}
              >
                <option value="needs_review">Потребує перевірки</option>
                <option value="approved">Схвалено</option>
                <option value="rejected">Відхилено</option>
                <option value="stale">Застаріло</option>
                <option value="all">Усі</option>
              </select>
            </div>
            <button
              className="button button-primary"
              type="button"
              onClick={() => void batchApprove()}
              disabled={busy || selectedIds.size === 0}
            >
              Схвалити вибрані ({selectedIds.size})
            </button>
          </div>
        </div>
        {loading ? <p aria-live="polite">Оновлюємо чергу…</p> : null}
        {!loading && candidates.length === 0 ? (
          <div className="empty-state">
            <h3>У цій черзі немає кандидатів</h3>
            <p>Змініть фільтр або запустіть генерацію для поточних опублікованих версій.</p>
          </div>
        ) : (
          <div className="question-candidate-list">
            {candidates.map((candidate) => (
              <CandidateCard
                key={candidate.id}
                candidate={candidate}
                lessonTitle={lessonTitles.get(candidate.lesson_version_id)}
                selected={selectedIds.has(candidate.id)}
                busy={busy}
                onSelect={(candidateId, selected) =>
                  setSelectedIds((current) => {
                    const next = new Set(current);
                    if (selected) next.add(candidateId);
                    else next.delete(candidateId);
                    return next;
                  })
                }
                onApprove={approve}
                onReject={reject}
              />
            ))}
          </div>
        )}
      </section>
    </section>
  );
}

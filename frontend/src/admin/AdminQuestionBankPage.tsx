import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, createIdempotencyKey } from "../api/client";
import type {
  InteractiveTrainingReadinessResponse,
  LocationSummary,
  MenuVersionCollection,
  QuestionCandidateCollection,
  QuestionCandidateEditedPayload,
  QuestionCandidateGenerateResponse,
  QuestionCandidateResponse,
  QuestionCandidateStatus,
  TrainingVersionCollection,
  TrainingVersionSummary,
} from "../api/contracts";
import { LogoutButton } from "../auth/LogoutButton";
import { useSession } from "../session/SessionContext";
import { LoadingState, StatusPill } from "../ui/States";

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
    "Джерело без ідентифікатора"
  );
}

function CandidateCard({
  candidate,
  selected,
  busy,
  onSelect,
  onApprove,
  onReject,
}: {
  candidate: QuestionCandidateResponse;
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
      prompt_payload: { locale: "uk", stem, options },
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
        </>
      )}

      <details className="candidate-provenance">
        <summary>Джерела та provenance</summary>
        <dl>
          <div>
            <dt>Урок</dt>
            <dd>{candidate.lesson_version_id}</dd>
          </div>
          <div>
            <dt>Навчання</dt>
            <dd>{candidate.training_version_id}</dd>
          </div>
          <div>
            <dt>Правило / механіка</dt>
            <dd>{mechanicLabels[candidate.mechanic] ?? candidate.mechanic}</dd>
          </div>
          <div>
            <dt>Fingerprint</dt>
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
            disabled={busy}
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
  const [trainingVersion, setTrainingVersion] = useState<TrainingVersionSummary | null>(null);
  const [candidates, setCandidates] = useState<QuestionCandidateResponse[]>([]);
  const [candidateTotal, setCandidateTotal] = useState(0);
  const [candidateFilter, setCandidateFilter] = useState<CandidateFilter>("needs_review");
  const [readiness, setReadiness] = useState<InteractiveTrainingReadinessResponse | null>(null);
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
        setTrainingVersion(publishedTraining);
        setCandidates(queue.items);
        setCandidateTotal(queue.total);
        setSelectedIds(new Set());
        setReadiness(
          publishedTraining
            ? await client.request<InteractiveTrainingReadinessResponse>(
                `${base}/training-versions/${publishedTraining.id}/interactive-training/readiness`,
              )
            : null,
        );
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

  const generate = async () => {
    if (!organizationId || !locationId || !menuVersionId || !trainingVersion || !session) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await client.request<QuestionCandidateGenerateResponse>(
        `/organizations/${organizationId}/locations/${locationId}/question-candidates/generate`,
        {
          method: "POST",
          body: { menu_version_id: menuVersionId, training_version_id: trainingVersion.id },
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
          <span>Меню: {menuVersionId ?? "немає Published версії"}</span>
          <span>
            Навчання:{" "}
            {trainingVersion ? `v${trainingVersion.version_number}` : "немає Published версії"}
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

      <section className="question-readiness" aria-labelledby="readiness-title">
        <div className="dataset-header">
          <div>
            <p className="eyebrow">Published навчання</p>
            <h2 id="readiness-title">Готовність уроків</h2>
          </div>
          {readiness ? (
            <span className="readiness-summary">
              {readiness.lessons.filter((lesson) => lesson.can_start).length} із{" "}
              {readiness.lessons.length} уроків готові
            </span>
          ) : null}
        </div>
        {readiness?.lessons.length ? (
          <div className="readiness-grid">
            {readiness.lessons.map((lesson) => (
              <article className="readiness-card" key={lesson.lesson_version_id}>
                <div className="readiness-card-heading">
                  <strong>Урок {lesson.lesson_version_id}</strong>
                  <StatusPill tone={readinessTone(lesson.status)}>{lesson.status}</StatusPill>
                </div>
                <p>
                  Пул: {lesson.eligible_count} / {lesson.required_count} · Ротація:{" "}
                  {lesson.rotation_supported ? "так" : "обмежена"}
                </p>
                {[...lesson.blocking_codes, ...lesson.warning_codes].map((code) => (
                  <code key={code}>{code}</code>
                ))}
              </article>
            ))}
          </div>
        ) : (
          <p className="empty-state">Для Published навчання ще немає конфігурації оцінювання.</p>
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
            <p>Змініть фільтр або запустіть генерацію для поточних Published версій.</p>
          </div>
        ) : (
          <div className="question-candidate-list">
            {candidates.map((candidate) => (
              <CandidateCard
                key={candidate.id}
                candidate={candidate}
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

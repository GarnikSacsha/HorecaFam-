import { useEffect, useRef, useState } from "react";
import { ApiError, type ApiClient } from "../api/client";
import type {
  FinalExamReadinessResponse,
  QuestionCandidateResponse,
  MenuVersionCollection,
  TrainingVersionCollection,
} from "../api/contracts";
import {
  bindQuestions,
  loadCatalogue,
  parseImport,
  parsePolicy,
  payloadKey,
  quotas,
  type PreparedQuestion,
  type QuotaPolicy,
} from "./authoredImport";

interface CreatedQuestion {
  question: PreparedQuestion;
  candidate: QuestionCandidateResponse;
  questionVersionId?: string;
}
interface FinalRequest {
  expected_assessment_version_id: string;
  policy: QuotaPolicy;
}
const groupLabels = { food: "Їжа", drinks: "Напої", desserts: "Десерти", other: "Інше" };

export function AdminAuthoredQuestions({
  client,
  base,
  csrfToken,
  menuId,
  trainingId,
  disabled,
  onBusy,
  onRefresh,
}: {
  client: ApiClient;
  base: string;
  csrfToken: string;
  menuId: string;
  trainingId: string;
  disabled: boolean;
  onBusy: (busy: boolean) => void;
  onRefresh: () => Promise<void>;
}) {
  const [mode, setMode] = useState<"import" | "final" | null>(null);
  const [input, setInput] = useState("");
  const [policyInput, setPolicyInput] = useState("");
  const [prepared, setPrepared] = useState<PreparedQuestion[]>([]);
  const [created, setCreated] = useState<CreatedQuestion[]>([]);
  const [finalRequest, setFinalRequest] = useState<FinalRequest | null>(null);
  const [published, setPublished] = useState<FinalExamReadinessResponse | null>(null);
  const [reviewed, setReviewed] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const running = useRef(false);
  const errorRef = useRef<HTMLDivElement>(null);
  const [approvalUncertain, setApprovalUncertain] = useState(false);
  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);

  const run = async (action: () => Promise<void>) => {
    if (running.current) return;
    running.current = true;
    setBusy(true);
    onBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action();
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? "Сервер не підтвердив операцію. Перевірте стан нижче. Для імпорту та Final повтор надсилає той самий запит; при конфлікті версій підготуйте новий перегляд."
          : caught instanceof Error
            ? caught.message
            : "Не вдалося виконати операцію.",
      );
    } finally {
      running.current = false;
      setBusy(false);
      onBusy(false);
    }
  };
  const currentVersions = async () => {
    const [menus, trainings] = await Promise.all([
      client.request<MenuVersionCollection>(`${base}/menu-versions`),
      client.request<TrainingVersionCollection>(`${base}/training-versions`),
    ]);
    if (menus.current_published?.id !== menuId || trainings.published?.id !== trainingId)
      throw new Error(
        "Опубліковані джерела змінилися. Оновіть Банк питань і перевірте пакет знову.",
      );
  };
  const prepare = () =>
    run(async () => {
      setPrepared([]);
      setReviewed(false);
      const rows = parseImport(input);
      await currentVersions();
      const catalogue = await loadCatalogue(client, base, menuId, trainingId);
      setPrepared(bindQuestions(rows, catalogue));
      setNotice("Джерела й уроки зіставлено. Перегляньте питання перед створенням кандидатів.");
    });
  const create = () =>
    run(async () => {
      await currentVersions();
      const next = [...created];
      for (const question of prepared.slice(next.length)) {
        const candidate = await client.request<QuestionCandidateResponse>(
          `${base}/question-candidates/authored`,
          {
            method: "POST",
            body: question.body,
            csrfToken,
            idempotencyKey: await payloadKey(base, question.body),
          },
        );
        if (
          candidate.training_version_id !== trainingId ||
          candidate.lesson_version_id !== question.body.lesson_version_id
        )
          throw new Error("Сервер повернув іншу прив’язку кандидата. Імпорт зупинено.");
        next.push({ question, candidate });
        setCreated([...next]);
      }
      setNotice(`Створено кандидатів: ${next.length}. Перевірте їх і окремо схваліть пакет.`);
      await onRefresh();
    });
  const approve = () =>
    run(async () => {
      await currentVersions();
      const fresh = await Promise.all(
        created.map((row) =>
          client.request<QuestionCandidateResponse>(
            `${base}/question-candidates/${row.candidate.id}`,
          ),
        ),
      );
      if (
        fresh.some(
          (candidate, index) =>
            candidate.status !== "needs_review" ||
            candidate.revision !== created[index].candidate.revision,
        )
      )
        throw new Error(
          "Статус або ревізія кандидата змінилися. Перевірте чергу; повторне схвалення не надіслано.",
        );
      // API review не має replay-контракту: після невизначеної відповіді не повторюємо запис.
      setApprovalUncertain(true);
      const result = await client.request<{
        items: Array<{ candidate: QuestionCandidateResponse; question_version_id: string }>;
      }>(`${base}/question-candidates/batch-approve`, {
        method: "POST",
        csrfToken,
        body: {
          items: fresh.map((candidate) => ({
            candidate_id: candidate.id,
            expected_revision: candidate.revision,
          })),
        },
      });
      const next = created.map((row) => {
        const approved = result.items.find((item) => item.candidate.id === row.candidate.id);
        if (!approved || approved.candidate.status !== "approved" || !approved.question_version_id)
          throw new Error("Схвалення потребує звірки з історією змін; неповна відповідь сервера.");
        return {
          ...row,
          candidate: approved.candidate,
          questionVersionId: approved.question_version_id,
        };
      });
      setCreated(next);
      setApprovalUncertain(false);
      const policy: QuotaPolicy = {
        strategy: "curated_category_quotas_v1",
        question_version_ids: next.map((row) => row.questionVersionId),
        buckets: (Object.keys(quotas) as Array<keyof typeof quotas>).map((key) => ({
          key,
          count: quotas[key],
          category_ids: [
            ...new Set(
              next
                .filter((row) => row.question.bucket === key)
                .map((row) => row.question.categoryId),
            ),
          ],
        })),
      };
      setPolicyInput(JSON.stringify(policy, null, 2));
      setNotice(
        `Схвалено ${next.length} питань. Конфігурацію Final підготовлено; іспит ще не змінено.`,
      );
      await onRefresh();
    });
  const prepareFinal = () =>
    run(async () => {
      setFinalRequest(null);
      setConfirmed(false);
      setPublished(null);
      const policy = parsePolicy(policyInput);
      await currentVersions();
      const readiness = await client.request<FinalExamReadinessResponse>(
        `${base}/training-versions/${trainingId}/final-exam/readiness`,
      );
      if (!readiness.assessment_version_id)
        throw new Error("Поточна версія Final ще не готова до налаштування.");
      setFinalRequest({ expected_assessment_version_id: readiness.assessment_version_id, policy });
    });
  const publish = () =>
    run(async () => {
      if (!finalRequest || !confirmed) return;
      const result = await client.request<FinalExamReadinessResponse>(
        `${base}/training-versions/${trainingId}/final-exam/versions`,
        {
          method: "POST",
          body: finalRequest,
          csrfToken,
          idempotencyKey: await payloadKey(`${base}/${trainingId}/final`, finalRequest),
        },
      );
      setPublished(result);
      setNotice("Нову версію Final опубліковано. Попередні результати й активні спроби збережено.");
      await onRefresh();
    });
  const locked = busy || disabled;
  return (
    <section
      className="question-candidate-card"
      aria-label="Авторські питання та версії іспиту"
      aria-busy={busy}
    >
      <div className="compact-actions">
        <button
          type="button"
          className="button button-quiet"
          disabled={locked}
          aria-expanded={mode === "import"}
          onClick={() => setMode("import")}
        >
          Імпорт авторських питань
        </button>
        <button
          type="button"
          className="button button-quiet"
          disabled={locked}
          aria-expanded={mode === "final"}
          onClick={() => setMode("final")}
        >
          Нова версія Final Exam
        </button>
      </div>
      {error && (
        <div className="error-summary" role="alert" tabIndex={-1} ref={errorRef}>
          <p>{error}</p>
          <a href={mode === "import" ? "#authored-json" : "#final-json"}>Перевірити пакет</a>
        </div>
      )}
      {notice && <p role="status">{notice}</p>}
      {mode === "import" && (
        <div className="candidate-editor">
          <h2>Імпорт авторських питань</h2>
          <p>
            Пакет перевіряється за поточними опублікованими меню та уроками. Імпорт створює чергу
            кандидатів; схвалення — окрема дія.
          </p>
          <details>
            <summary>Формат пакета</summary>
            <p>
              JSON з масивом questions (1–100). Кожне питання: source_name, category, bucket
              (food/drinks/desserts/other), prompt_payload, answer_payload, explanation_payload,
              source_quote, option_rationales. Для кількох уроків із тим самим джерелом додайте
              lesson_title. Назви мають точно відповідати меню й урокам.
            </p>
          </details>
          <div className="field-group">
            <label htmlFor="authored-file">Завантажити пакет JSON</label>
            <input
              id="authored-file"
              type="file"
              accept=".json,application/json"
              disabled={locked || created.length > 0}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (!file) return;
                void run(async () => {
                  if (file.size > 1_000_000) throw new Error("Пакет завеликий: максимум 1 МБ.");
                  const text = await file.text();
                  parseImport(text);
                  setInput(text);
                  setPrepared([]);
                  setReviewed(false);
                });
              }}
            />
          </div>
          <div className="field-group">
            <label htmlFor="authored-json">Пакет питань (JSON)</label>
            <textarea
              id="authored-json"
              rows={8}
              value={input}
              disabled={locked || created.length > 0}
              aria-describedby={error ? "authored-input-help" : undefined}
              onChange={(event) => {
                setInput(event.target.value);
                setPrepared([]);
                setReviewed(false);
              }}
            />
            <p id="authored-input-help">
              Чотири варіанти, одна правильна відповідь і обґрунтування кожного варіанта.
            </p>
          </div>
          <button
            className="button button-quiet"
            type="button"
            disabled={locked || !input || created.length > 0}
            onClick={() => void prepare()}
          >
            Перевірити джерела та показати питання
          </button>
          {prepared.length > 0 && (
            <>
              <p>
                Питань у пакеті: {prepared.length}. Створено: {created.length}. Схвалено:{" "}
                {created.filter((row) => row.questionVersionId).length}.
              </p>
              {prepared.map((row, index) => (
                <details key={index} className="candidate-provenance">
                  <summary>
                    {index + 1}. {row.body.prompt_payload.stem}
                  </summary>
                  <p>
                    {row.source} · {row.lesson} · {groupLabels[row.bucket]}
                  </p>
                  <blockquote>{row.body.explanation_payload.authoring.source_quote}</blockquote>
                  <ol>
                    {row.body.prompt_payload.options.map((option) => (
                      <li key={option.stable_key}>
                        {option.text}
                        {row.body.answer_payload.correct_option_keys.includes(option.stable_key)
                          ? " — правильна відповідь"
                          : ""}
                        <p>
                          {
                            row.body.explanation_payload.authoring.option_rationales[
                              option.stable_key
                            ]
                          }
                        </p>
                      </li>
                    ))}
                  </ol>
                  <p>{row.body.explanation_payload.text}</p>
                </details>
              ))}
              <button
                className="button button-primary"
                type="button"
                disabled={locked || created.length === prepared.length}
                onClick={() => void create()}
              >
                {created.length ? "Продовжити імпорт" : "Створити кандидатів"}
              </button>
              <label>
                <input
                  type="checkbox"
                  checked={reviewed}
                  disabled={locked}
                  onChange={(event) => setReviewed(event.target.checked)}
                />{" "}
                Перевірено зміст, цитати, правильні відповіді й усі відволікаючі варіанти
              </label>
              <button
                className="button button-primary"
                type="button"
                disabled={
                  locked ||
                  !reviewed ||
                  created.length !== prepared.length ||
                  created.some((row) => row.questionVersionId) ||
                  approvalUncertain
                }
                onClick={() => void approve()}
              >
                Схвалити перевірений пакет
              </button>
              {approvalUncertain && (
                <p role="alert">
                  Результат схвалення потребує звірки з Банком питань та історією змін. Повторне
                  схвалення заблоковано.
                </p>
              )}
            </>
          )}
        </div>
      )}
      {mode === "final" && (
        <div className="candidate-editor">
          <h2>Нова версія Final Exam</h2>
          <p>
            20 питань: їжа 10, напої 4, десерти 3, інше 3. Прохідний бал — 70%. Нова версія
            застосовується до нових дозволених спроб; сертифікація та історія зберігаються.
          </p>
          <div className="field-group">
            <label htmlFor="final-json">Конфігурація Final (JSON)</label>
            <textarea
              id="final-json"
              rows={8}
              value={policyInput}
              disabled={locked || !!published}
              onChange={(event) => {
                setPolicyInput(event.target.value);
                setFinalRequest(null);
                setConfirmed(false);
              }}
            />
          </div>
          <p>
            Вставте policy з переліком опублікованих question_version_ids і чотирма buckets. Після
            схвалення імпортованого пакета ці дані заповнюються автоматично.
          </p>
          <button
            type="button"
            className="button button-quiet"
            disabled={locked || !policyInput || !!published}
            onClick={() => void prepareFinal()}
          >
            Переглянути нову версію
          </button>
          {finalRequest && (
            <>
              <p>Банк: {finalRequest.policy.question_version_ids.length} питань.</p>
              <ul>
                {finalRequest.policy.buckets.map((bucket) => (
                  <li key={bucket.key}>
                    {groupLabels[bucket.key]}: {bucket.count} питань, категорій:{" "}
                    {bucket.category_ids.length}
                  </li>
                ))}
              </ul>
              <label>
                <input
                  type="checkbox"
                  checked={confirmed}
                  disabled={locked || !!published}
                  onChange={(event) => setConfirmed(event.target.checked)}
                />{" "}
                Підтверджую публікацію цієї версії іспиту
              </label>
              <button
                type="button"
                className="button button-primary"
                disabled={locked || !confirmed || !!published}
                onClick={() => void publish()}
              >
                Опублікувати нову версію Final
              </button>
            </>
          )}
          {published && (
            <p role="status">
              Версія опублікована. Готовність: {published.status}; питань:{" "}
              {published.eligible_count}. {published.blocking_codes.join(", ")}
            </p>
          )}
        </div>
      )}
      {(created.length > 0 || published) && (
        <details>
          <summary>Зберегти звіт операції</summary>
          <p>
            Збережіть цей звіт перед виходом зі сторінки для звірки та продовження налаштування.
          </p>
          <textarea
            aria-label="Звіт операції"
            rows={6}
            readOnly
            value={JSON.stringify(
              {
                training_version_id: trainingId,
                candidates: created.map((row) => ({
                  candidate_id: row.candidate.id,
                  revision: row.candidate.revision,
                  question_version_id: row.questionVersionId ?? null,
                  source: row.question.source,
                  category_id: row.question.categoryId,
                  bucket: row.question.bucket,
                })),
                final: published,
              },
              null,
              2,
            )}
          />
        </details>
      )}
    </section>
  );
}

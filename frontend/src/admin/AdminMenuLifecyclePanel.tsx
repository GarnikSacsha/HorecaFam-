import { useCallback, useEffect, useState } from "react";

import { createIdempotencyKey } from "../api/client";
import type {
  MenuFindingResolutionAction,
  MenuImportConfirmResponse,
  MenuImportDetail,
  MenuPublishResponse,
  MenuReadinessResponse,
  MenuVersionDetail,
} from "../api/contracts";
import { useSession } from "../session/SessionContext";
import { ConfirmDialog } from "../ui/ConfirmDialog";
import { StatusPill } from "../ui/States";

const actionCopy: Record<MenuFindingResolutionAction, string> = {
  confirm_legitimate: "Підтвердити",
  map_existing: "Зіставити з наявною",
  confirm_removal: "Підтвердити видалення",
  confirm_critical_change: "Підтвердити критичну зміну",
  exclude_source_record: "Виключити запис",
};

export function AdminMenuLifecyclePanel({
  organizationId,
  locationId,
  draft,
  onDraftConfirmed,
  onPublished,
}: {
  organizationId: string;
  locationId: string;
  draft: MenuVersionDetail;
  onDraftConfirmed: (draft: MenuVersionDetail) => void;
  onPublished: (result: MenuPublishResponse) => void;
}) {
  const { client, session } = useSession();
  const [file, setFile] = useState<File | null>(null);
  const [menuImport, setMenuImport] = useState<MenuImportDetail | null>(null);
  const [readiness, setReadiness] = useState<MenuReadinessResponse | null>(null);
  const [acknowledgeWarnings, setAcknowledgeWarnings] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [publishOpen, setPublishOpen] = useState(false);
  const base = `/organizations/${organizationId}/locations/${locationId}`;

  const loadReadiness = useCallback(async () => {
    try {
      const response = await client.request<MenuReadinessResponse>(
        `${base}/menu-versions/${draft.id}/readiness`,
      );
      setReadiness(response);
    } catch {
      setError("Не вдалося перевірити готовність чернетки.");
    }
  }, [base, client, draft.id]);

  useEffect(() => {
    // Readiness is an external server snapshot and updates state only after its response.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadReadiness();
  }, [draft.revision, loadReadiness]);

  const preview = async () => {
    if (!file || !session) return;
    setBusy(true);
    setError(null);
    try {
      const parsed: unknown = JSON.parse(await file.text());
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("invalid-json-root");
      }
      const response = await client.request<MenuImportDetail>(`${base}/menu-imports`, {
        method: "POST",
        body: { ...parsed, source_filename: file.name },
        csrfToken: session.csrf_token,
        idempotencyKey: createIdempotencyKey(),
      });
      setMenuImport(response);
      setAcknowledgeWarnings(false);
    } catch {
      setError("Файл не пройшов перевірку. Перевірте JSON і спробуйте ще раз.");
    } finally {
      setBusy(false);
    }
  };

  const resolveFinding = async (findingId: string, action: MenuFindingResolutionAction) => {
    if (!menuImport || !session) return;
    setBusy(true);
    setError(null);
    try {
      const response = await client.request<{
        finding: MenuImportDetail["findings"][number];
        review_revision: number;
      }>(`${base}/menu-imports/${menuImport.id}/findings/${findingId}/resolve`, {
        method: "POST",
        body: {
          action,
          target_entity_id: null,
          comment: null,
          expected_revision: menuImport.review_revision,
        },
        csrfToken: session.csrf_token,
        idempotencyKey: createIdempotencyKey(),
      });
      setMenuImport((current) =>
        current
          ? {
              ...current,
              review_revision: response.review_revision,
              findings: current.findings.map((finding) =>
                finding.id === response.finding.id ? response.finding : finding,
              ),
            }
          : current,
      );
    } catch {
      setError("Не вдалося зберегти рішення щодо знахідки.");
    } finally {
      setBusy(false);
    }
  };

  const confirmImport = async () => {
    if (!menuImport || !session) return;
    setBusy(true);
    setError(null);
    try {
      const response = await client.request<MenuImportConfirmResponse>(
        `${base}/menu-imports/${menuImport.id}/confirm`,
        {
          method: "POST",
          body: {
            expected_revision: menuImport.review_revision,
            acknowledge_warnings: acknowledgeWarnings,
          },
          csrfToken: session.csrf_token,
          idempotencyKey: createIdempotencyKey(),
        },
      );
      setMenuImport(response.import);
      onDraftConfirmed(response.draft);
    } catch {
      setError("Імпорт не підтверджено. Оновіть review і повторіть дію.");
    } finally {
      setBusy(false);
    }
  };

  const publish = async () => {
    if (!session || !readiness) return;
    setBusy(true);
    setError(null);
    try {
      const response = await client.request<MenuPublishResponse>(
        `${base}/menu-versions/${draft.id}/publish`,
        {
          method: "POST",
          body: { expected_revision: readiness.revision },
          csrfToken: session.csrf_token,
          idempotencyKey: createIdempotencyKey(),
        },
      );
      setPublishOpen(false);
      onPublished(response);
    } catch {
      setPublishOpen(false);
      setError("Меню не опубліковано. Перевірте готовність і повторіть дію.");
      await loadReadiness();
    } finally {
      setBusy(false);
    }
  };

  const unresolvedReview = menuImport?.findings.some(
    (finding) =>
      finding.severity === "requires_review" && finding.resolution_status === "unresolved",
  );
  const importBlocked = Boolean(menuImport?.blocker_count) || unresolvedReview;
  return (
    <section className="menu-lifecycle" aria-labelledby="menu-lifecycle-title">
      <div>
        <p className="eyebrow">Review та публікація</p>
        <h2 id="menu-lifecycle-title">Перевірити перед зміною поточного меню</h2>
      </div>
      {error ? (
        <p className="inline-error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="menu-lifecycle-grid">
        <section className="menu-lifecycle-card" aria-labelledby="json-import-title">
          <div className="menu-card-heading">
            <div>
              <span className="menu-step">1</span>
              <h3 id="json-import-title">JSON-імпорт</h3>
            </div>
            {menuImport ? <StatusPill tone="info">{menuImport.status}</StatusPill> : null}
          </div>
          <p>Файл спочатку створює preview. Працівники не побачать жодних змін.</p>
          <div className="field-group">
            <label htmlFor="menu-json-file">JSON-файл меню</label>
            <input
              id="menu-json-file"
              type="file"
              accept="application/json,.json"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </div>
          <button
            className="button button-quiet"
            type="button"
            disabled={!file || busy}
            onClick={() => void preview()}
          >
            Перевірити JSON
          </button>
          {menuImport ? (
            <div className="import-review" aria-live="polite">
              <dl className="import-counts">
                <div>
                  <dt>Додано</dt>
                  <dd>{menuImport.added_count}</dd>
                </div>
                <div>
                  <dt>Змінено</dt>
                  <dd>{menuImport.changed_count}</dd>
                </div>
                <div>
                  <dt>Видалено</dt>
                  <dd>{menuImport.removed_count}</dd>
                </div>
                <div>
                  <dt>Без змін</dt>
                  <dd>{menuImport.unchanged_count}</dd>
                </div>
              </dl>
              {menuImport.findings.length ? (
                <ul className="finding-list" aria-label="Знахідки імпорту">
                  {menuImport.findings.map((finding) => {
                    const action = finding.allowed_actions.find(
                      (value) => value !== "map_existing",
                    );
                    return (
                      <li key={finding.id} className={`finding finding-${finding.severity}`}>
                        <div>
                          <strong>{finding.code}</strong>
                          <p>{finding.message}</p>
                        </div>
                        {finding.resolution_status === "resolved" ? (
                          <StatusPill tone="success">Вирішено</StatusPill>
                        ) : action ? (
                          <button
                            className="button button-quiet"
                            type="button"
                            disabled={busy}
                            onClick={() => void resolveFinding(finding.id, action)}
                          >
                            {actionCopy[action]}
                          </button>
                        ) : finding.severity === "blocker" ? (
                          <StatusPill tone="danger">Виправте файл</StatusPill>
                        ) : (
                          <span className="action-note">Потрібне ручне зіставлення</span>
                        )}
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="success-message">Знахідок немає.</p>
              )}
              {menuImport.warning_count ? (
                <label className="check-row">
                  <input
                    type="checkbox"
                    checked={acknowledgeWarnings}
                    onChange={(event) => setAcknowledgeWarnings(event.target.checked)}
                  />
                  Я переглянув попередження імпорту
                </label>
              ) : null}
              <button
                className="button button-primary"
                type="button"
                disabled={
                  busy ||
                  importBlocked ||
                  (menuImport.warning_count > 0 && !acknowledgeWarnings) ||
                  menuImport.status !== "ready_for_review"
                }
                onClick={() => void confirmImport()}
              >
                Підтвердити в чернетку
              </button>
            </div>
          ) : null}
        </section>
        <section className="menu-lifecycle-card" aria-labelledby="readiness-title">
          <div className="menu-card-heading">
            <div>
              <span className="menu-step">2</span>
              <h3 id="readiness-title">Готовність</h3>
            </div>
            {readiness ? (
              <StatusPill tone={readiness.can_publish ? "success" : "warning"}>
                {readiness.can_publish ? "Готово" : "Потрібні виправлення"}
              </StatusPill>
            ) : null}
          </div>
          <p>Сервер повторно перевіряє український текст, факти, base version і ревізію.</p>
          {readiness?.blocking_errors?.length ? (
            <ul className="readiness-list">
              {readiness.blocking_errors.map((issue, index) => (
                <li key={`${issue.code}-${issue.entity_id ?? index}`}>
                  <strong>{issue.code}</strong>
                  <span>{issue.message}</span>
                </li>
              ))}
            </ul>
          ) : null}
          {readiness?.warnings?.length ? (
            <details>
              <summary>Попередження: {readiness.warnings.length}</summary>
              <ul className="readiness-list">
                {readiness.warnings.map((issue, index) => (
                  <li key={`${issue.code}-${issue.entity_id ?? index}`}>{issue.message}</li>
                ))}
              </ul>
            </details>
          ) : null}
          <dl className="zero-applicability">
            <div>
              <dt>Training content</dt>
              <dd>{readiness?.applicable_training_content_count ?? 0}</dd>
            </div>
            <div>
              <dt>Assignments</dt>
              <dd>0</dd>
            </div>
            <div>
              <dt>Notifications</dt>
              <dd>0</dd>
            </div>
          </dl>
          <button
            className="button button-primary"
            type="button"
            disabled={!readiness?.can_publish || busy}
            onClick={() => setPublishOpen(true)}
          >
            Опублікувати меню
          </button>
        </section>
      </div>
      <ConfirmDialog
        open={publishOpen}
        title="Опублікувати цю версію меню?"
        description="Після підтвердження працівники цієї локації одразу бачитимуть нову версію. Попередня залишиться в історії."
        confirmLabel="Опублікувати"
        busy={busy}
        onCancel={() => setPublishOpen(false)}
        onConfirm={() => void publish()}
      />
    </section>
  );
}

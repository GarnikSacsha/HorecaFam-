import { useCallback, useEffect, useState } from "react";

import { createIdempotencyKey } from "../api/client";
import type {
  MenuFindingResolutionAction,
  MenuImportConfirmResponse,
  MenuImportDetail,
  MenuPublishResponse,
  MenuReadinessResponse,
  MenuReadinessIssue,
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

function ReadinessGroups({
  issues,
  onInspectItem,
  itemNames,
}: {
  issues: MenuReadinessIssue[];
  onInspectItem?: (id: string) => void;
  itemNames: Record<string, string>;
}) {
  const groups = new Map<string, MenuReadinessIssue[]>();
  for (const issue of issues) {
    const key = JSON.stringify([issue.code, issue.message, issue.entity_type]);
    groups.set(key, [...(groups.get(key) ?? []), issue]);
  }
  return (
    <ul className="readiness-list">
      {Array.from(groups, ([key, rows]) => (
        <li key={key}>
          <strong>{rows[0].code}</strong>
          <span>{rows[0].message}</span>
          <details>
            <summary>Показати позиції: {rows.length}</summary>
            <ul className="readiness-entities">
              {rows.map((issue, index) => (
                <li key={`${issue.entity_id}-${index}`}>
                  {issue.entity_type === "menu_item" && issue.entity_id && onInspectItem ? (
                    <button
                      type="button"
                      className="button button-quiet"
                      onClick={() => onInspectItem(issue.entity_id!)}
                    >
                      Відкрити позицію {itemNames[issue.entity_id] ?? issue.entity_id}
                    </button>
                  ) : (
                    <span>
                      {issue.entity_type} {issue.entity_id ?? ""}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </details>
        </li>
      ))}
    </ul>
  );
}

export function AdminMenuLifecyclePanel({
  organizationId,
  locationId,
  draft,
  onDraftConfirmed,
  onPublished,
  onInspectItem,
  itemNames = {},
}: {
  organizationId: string;
  locationId: string;
  draft: MenuVersionDetail;
  onDraftConfirmed: (draft: MenuVersionDetail) => void;
  onPublished: (result: MenuPublishResponse) => void;
  onInspectItem?: (id: string) => void;
  itemNames?: Record<string, string>;
}) {
  const { client, session } = useSession();
  const [file, setFile] = useState<File | null>(null);
  const [menuImport, setMenuImport] = useState<MenuImportDetail | null>(null);
  const [readiness, setReadiness] = useState<MenuReadinessResponse | null>(null);
  const [acknowledgeWarnings, setAcknowledgeWarnings] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [publishOpen, setPublishOpen] = useState(false);
  const [demoAcknowledgement, setDemoAcknowledgement] = useState<string | null>(null);
  const snapshotKey = `${draft.id}:${draft.revision}`;
  const readinessCurrent =
    readiness?.menu_version_id === draft.id && readiness?.revision === draft.revision;
  const demoSelected =
    readinessCurrent &&
    readiness?.demo_publication_allowed === true &&
    demoAcknowledgement === snapshotKey;
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
    if (!session || !readiness || (!readiness.can_publish && !demoSelected)) return;
    setBusy(true);
    setError(null);
    try {
      const response = await client.request<MenuPublishResponse>(
        `${base}/menu-versions/${draft.id}/publish`,
        {
          method: "POST",
          body: {
            expected_revision: readiness.revision,
            ...(demoSelected ? { demo_with_unknown_facts: true } : {}),
          },
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
            <ReadinessGroups
              issues={readiness.blocking_errors}
              onInspectItem={onInspectItem}
              itemNames={itemNames}
            />
          ) : null}
          {readiness?.warnings?.length ? (
            <details>
              <summary>Попередження: {readiness.warnings.length}</summary>
              <ReadinessGroups
                issues={readiness.warnings}
                onInspectItem={onInspectItem}
                itemNames={itemNames}
              />
            </details>
          ) : null}
          {readiness?.demo_publication_allowed ? (
            <div className="demo-publication-notice">
              <p>
                Демо доступне лише поза робочим середовищем. Невідомі факти не стають підтвердженими
                й не використовуються для питань про безпечність.
              </p>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={demoSelected}
                  onChange={(event) =>
                    setDemoAcknowledgement(event.target.checked ? snapshotKey : null)
                  }
                />
                Демо: склад і алергени залишаються непідтвердженими
              </label>
            </div>
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
            disabled={!readinessCurrent || (!readiness?.can_publish && !demoSelected) || busy}
            onClick={() => setPublishOpen(true)}
          >
            {readiness?.demo_publication_allowed ? "Опублікувати демо" : "Опублікувати меню"}
          </button>
        </section>
      </div>
      <ConfirmDialog
        open={publishOpen}
        title={
          demoSelected
            ? "Опублікувати демо з непідтвердженими фактами?"
            : "Опублікувати цю версію меню?"
        }
        description={
          demoSelected
            ? "Працівники бачитимуть меню з непідтвердженими складом та алергенами. Воно не підтверджує безпечність страв. Перед робочим використанням факти потрібно перевірити за джерелом."
            : "Після підтвердження працівники цієї локації одразу бачитимуть нову версію. Попередня залишиться в історії."
        }
        confirmLabel="Опублікувати"
        busy={busy}
        onCancel={() => setPublishOpen(false)}
        onConfirm={() => void publish()}
      />
    </section>
  );
}

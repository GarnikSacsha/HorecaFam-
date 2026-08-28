import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, createIdempotencyKey } from "../api/client";
import type {
  AssetUploadIntentResponse,
  LocationSummary,
  TrainingAssetResponse,
  TrainingContentBlockType,
  TrainingLessonResponse,
  TrainingPublishResponse,
  TrainingReadinessResponse,
  TrainingVersionCollection,
  TrainingVersionDetail,
} from "../api/contracts";
import { LogoutButton } from "../auth/LogoutButton";
import { useSession } from "../session/SessionContext";
import { ConfirmDialog } from "../ui/ConfirmDialog";
import { StatusPill } from "../ui/States";

type SaveState = "saved" | "saving" | "error" | "conflict";

const blockLabels: Record<TrainingContentBlockType, string> = {
  heading: "Заголовок",
  text: "Текст",
  list: "Список",
  callout: "Акцент",
  menu_item_card: "Картка позиції меню",
  image: "Зображення",
  external_video: "YouTube-відео",
};

function saveStateLabel(state: SaveState): string {
  if (state === "saving") return "Збереження…";
  if (state === "conflict") return "Конфлікт версій";
  if (state === "error") return "Не збережено";
  return "Збережено";
}

async function sha256(file: File): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function move<T>(items: T[], from: number, to: number): T[] {
  if (to < 0 || to >= items.length) return items;
  const copy = [...items];
  const [item] = copy.splice(from, 1);
  copy.splice(to, 0, item);
  return copy;
}

function lessonLabel(lesson: TrainingLessonResponse): string {
  return `${lesson.title_uk}${lesson.required ? " · обов’язковий" : ""}`;
}

function LessonSettingsForm({
  lesson,
  busy,
  onSave,
}: {
  lesson: TrainingLessonResponse;
  busy: boolean;
  onSave: (values: {
    title: string;
    description: string;
    required: boolean;
    minutes: string;
  }) => void;
}) {
  const [title, setTitle] = useState(lesson.title_uk);
  const [description, setDescription] = useState(lesson.description_uk ?? "");
  const [minutes, setMinutes] = useState(
    lesson.estimated_minutes === null ? "" : String(lesson.estimated_minutes),
  );
  const [required, setRequired] = useState(lesson.required);
  return (
    <form
      className="training-lesson-form"
      aria-label="Налаштування уроку"
      onSubmit={(event) => {
        event.preventDefault();
        onSave({ title, description, required, minutes });
      }}
    >
      <div className="field-group">
        <label htmlFor={`lesson-title-${lesson.id}`}>Назва уроку</label>
        <input
          id={`lesson-title-${lesson.id}`}
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          required
        />
      </div>
      <div className="field-group training-grow">
        <label htmlFor={`lesson-description-${lesson.id}`}>Опис уроку</label>
        <input
          id={`lesson-description-${lesson.id}`}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
      </div>
      <div className="field-group">
        <label htmlFor={`lesson-minutes-${lesson.id}`}>Хвилини</label>
        <input
          id={`lesson-minutes-${lesson.id}`}
          type="number"
          min="1"
          max="240"
          value={minutes}
          onChange={(event) => setMinutes(event.target.value)}
        />
      </div>
      <label className="check-row">
        <input
          type="checkbox"
          checked={required}
          onChange={(event) => setRequired(event.target.checked)}
        />
        Обов’язковий урок
      </label>
      <button className="button button-secondary" type="submit" disabled={busy}>
        Зберегти урок
      </button>
    </form>
  );
}

export function AdminTrainingPage() {
  const { client, session, status } = useSession();
  const organizationId = session?.organization_access.find(
    (access) => access.is_organization_admin,
  )?.organization_id;
  const [locations, setLocations] = useState<LocationSummary[]>([]);
  const [locationId, setLocationId] = useState("");
  const [collection, setCollection] = useState<TrainingVersionCollection | null>(null);
  const [draft, setDraft] = useState<TrainingVersionDetail | null>(null);
  const [readiness, setReadiness] = useState<TrainingReadinessResponse | null>(null);
  const [selectedLessonId, setSelectedLessonId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<SaveState>("saved");
  const [publishOpen, setPublishOpen] = useState(false);
  const [moduleTitle, setModuleTitle] = useState("");
  const [moduleDescription, setModuleDescription] = useState("");
  const [moduleRequired, setModuleRequired] = useState(true);
  const [lessonTitle, setLessonTitle] = useState("");
  const [lessonMinutes, setLessonMinutes] = useState("");
  const [blockType, setBlockType] = useState<TrainingContentBlockType>("text");
  const [blockText, setBlockText] = useState("");
  const [blockSecondaryText, setBlockSecondaryText] = useState("");
  const [assetFile, setAssetFile] = useState<File | null>(null);
  const [uploadedAsset, setUploadedAsset] = useState<TrainingAssetResponse | null>(null);
  const [uploadState, setUploadState] = useState<
    "idle" | "uploading" | "verifying" | "ready" | "failed"
  >("idle");

  const module = draft?.modules[0] ?? null;
  const lessons = useMemo(
    () => [...(module?.lessons ?? [])].sort((left, right) => left.position - right.position),
    [module],
  );
  const selectedLesson =
    lessons.find((lesson) => lesson.id === selectedLessonId) ?? lessons[0] ?? null;

  const applyDetail = useCallback((detail: TrainingVersionDetail) => {
    setDraft(detail);
    const nextModule = detail.modules[0];
    setModuleTitle(nextModule?.title_uk ?? "");
    setModuleDescription(nextModule?.description_uk ?? "");
    setModuleRequired(nextModule?.required ?? true);
    setSelectedLessonId((current) => {
      const available = nextModule?.lessons ?? [];
      return available.some((lesson) => lesson.id === current)
        ? current
        : (available[0]?.id ?? null);
    });
  }, []);

  const refreshDraft = useCallback(
    async (selectedLocationId: string, versionId: string) => {
      if (!organizationId) return;
      const base = `/organizations/${organizationId}/locations/${selectedLocationId}/training-versions/${versionId}`;
      const [detail, nextReadiness] = await Promise.all([
        client.request<TrainingVersionDetail>(base),
        client.request<TrainingReadinessResponse>(`${base}/readiness`),
      ]);
      applyDetail(detail);
      setReadiness(nextReadiness);
    },
    [applyDetail, client, organizationId],
  );

  const loadWorkspace = useCallback(
    async (selectedLocationId: string) => {
      if (!organizationId || !selectedLocationId) return;
      setLoading(true);
      setError(null);
      try {
        const nextCollection = await client.request<TrainingVersionCollection>(
          `/organizations/${organizationId}/locations/${selectedLocationId}/training-versions`,
        );
        setCollection(nextCollection);
        if (nextCollection.draft) {
          await refreshDraft(selectedLocationId, nextCollection.draft.id);
        } else {
          setDraft(null);
          setReadiness(null);
        }
      } catch {
        setError("Не вдалося завантажити навчальні матеріали локації.");
      } finally {
        setLoading(false);
      }
    },
    [client, organizationId, refreshDraft],
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
        if (first) void loadWorkspace(first);
        else setLoading(false);
      })
      .catch(() => {
        if (!active) return;
        setError("Не вдалося завантажити локації.");
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [client, loadWorkspace, organizationId, status]);

  const draftBase =
    organizationId && locationId && draft
      ? `/organizations/${organizationId}/locations/${locationId}/training-versions/${draft.id}`
      : "";

  const mutate = async (action: () => Promise<unknown>) => {
    if (!draft || !locationId) return;
    setBusy(true);
    setError(null);
    setSaveState("saving");
    try {
      await action();
      await refreshDraft(locationId, draft.id);
      setSaveState("saved");
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === "REVISION_CONFLICT") {
        setSaveState("conflict");
        setError("Чернетку вже змінили в іншій сесії. Локальний текст збережено на екрані.");
      } else {
        setSaveState("error");
        setError("Зміни не збережено. Перевірте дані та повторіть дію.");
      }
    } finally {
      setBusy(false);
    }
  };

  const createDraft = async () => {
    if (!organizationId || !locationId || !session) return;
    setBusy(true);
    setError(null);
    try {
      const created = await client.request<TrainingVersionDetail>(
        `/organizations/${organizationId}/locations/${locationId}/training-versions`,
        {
          method: "POST",
          body: { base_version_id: collection?.published?.id ?? null },
          csrfToken: session.csrf_token,
          idempotencyKey: createIdempotencyKey(),
        },
      );
      applyDetail(created);
      await loadWorkspace(locationId);
    } catch {
      setError("Не вдалося створити чернетку навчання.");
    } finally {
      setBusy(false);
    }
  };

  const saveModule = () => {
    if (!module || !draft || !session) return;
    void mutate(() =>
      client.request(`${draftBase}/modules/${module.id}`, {
        method: "PATCH",
        body: {
          expected_revision: draft.revision,
          title_uk: moduleTitle,
          description_uk: moduleDescription || null,
          required: moduleRequired,
        },
        csrfToken: session.csrf_token,
      }),
    );
  };

  const addLesson = () => {
    if (!module || !draft || !session || !lessonTitle.trim()) return;
    void mutate(async () => {
      await client.request(`${draftBase}/modules/${module.id}/lessons`, {
        method: "POST",
        body: {
          expected_revision: draft.revision,
          title_uk: lessonTitle,
          description_uk: null,
          required: true,
          estimated_minutes: lessonMinutes ? Number(lessonMinutes) : null,
        },
        csrfToken: session.csrf_token,
      });
      setLessonTitle("");
      setLessonMinutes("");
    });
  };

  const reorderLessons = (index: number, direction: -1 | 1) => {
    if (!module || !draft || !session) return;
    const ordered = move(lessons, index, index + direction).map((lesson) => lesson.id);
    if (ordered.join() === lessons.map((lesson) => lesson.id).join()) return;
    void mutate(() =>
      client.request(`${draftBase}/modules/${module.id}/lessons/reorder`, {
        method: "POST",
        body: { expected_revision: draft.revision, ordered_ids: ordered },
        csrfToken: session.csrf_token,
      }),
    );
  };

  const deleteLesson = (lesson: TrainingLessonResponse) => {
    if (!draft || !session) return;
    void mutate(() =>
      client.request(`${draftBase}/lessons/${lesson.id}?expected_revision=${draft.revision}`, {
        method: "DELETE",
        csrfToken: session.csrf_token,
      }),
    );
  };

  const saveLesson = (values: {
    title: string;
    description: string;
    required: boolean;
    minutes: string;
  }) => {
    if (!selectedLesson || !draft || !session) return;
    void mutate(() =>
      client.request(`${draftBase}/lessons/${selectedLesson.id}`, {
        method: "PATCH",
        body: {
          expected_revision: draft.revision,
          title_uk: values.title,
          description_uk: values.description || null,
          required: values.required,
          estimated_minutes: values.minutes ? Number(values.minutes) : null,
        },
        csrfToken: session.csrf_token,
      }),
    );
  };

  const blockPayload = (): Record<string, unknown> | null => {
    if (blockType === "heading") return { level: 2, text_uk: blockText };
    if (blockType === "text") return { text_uk: blockText };
    if (blockType === "list")
      return {
        style: "unordered",
        items_uk: blockText
          .split("\n")
          .map((item) => item.trim())
          .filter(Boolean),
      };
    if (blockType === "callout")
      return { tone: "info", title_uk: blockSecondaryText || null, text_uk: blockText };
    if (blockType === "menu_item_card")
      return { menu_item_id: blockText.trim(), note_uk: blockSecondaryText || null };
    if (blockType === "image")
      return uploadedAsset
        ? { asset_id: uploadedAsset.id, alt_uk: blockText, caption_uk: blockSecondaryText || null }
        : null;
    return { url: blockText, title_uk: blockSecondaryText, summary_uk: blockSecondaryText };
  };

  const addBlock = () => {
    if (!selectedLesson || !draft || !session) return;
    const payload = blockPayload();
    if (!payload) {
      setError("Спочатку завантажте й перевірте зображення.");
      return;
    }
    void mutate(async () => {
      await client.request(`${draftBase}/lessons/${selectedLesson.id}/content-blocks`, {
        method: "POST",
        body: { expected_revision: draft.revision, type: blockType, payload },
        csrfToken: session.csrf_token,
      });
      setBlockText("");
      setBlockSecondaryText("");
    });
  };

  const reorderBlocks = (index: number, direction: -1 | 1) => {
    if (!selectedLesson || !draft || !session) return;
    const blocks = [...selectedLesson.content_blocks].sort(
      (left, right) => left.position - right.position,
    );
    const ordered = move(blocks, index, index + direction).map((block) => block.id);
    if (ordered.join() === blocks.map((block) => block.id).join()) return;
    void mutate(() =>
      client.request(`${draftBase}/lessons/${selectedLesson.id}/content-blocks/reorder`, {
        method: "POST",
        body: { expected_revision: draft.revision, ordered_ids: ordered },
        csrfToken: session.csrf_token,
      }),
    );
  };

  const deleteBlock = (blockId: string) => {
    if (!draft || !session) return;
    void mutate(() =>
      client.request(`${draftBase}/content-blocks/${blockId}?expected_revision=${draft.revision}`, {
        method: "DELETE",
        csrfToken: session.csrf_token,
      }),
    );
  };

  const uploadAsset = async () => {
    if (!assetFile || !organizationId || !locationId || !session) return;
    setUploadState("uploading");
    setError(null);
    try {
      const checksum = await sha256(assetFile);
      const intent = await client.request<AssetUploadIntentResponse>(
        `/organizations/${organizationId}/locations/${locationId}/assets/upload-intents`,
        {
          method: "POST",
          body: {
            file_name: assetFile.name,
            mime_type: assetFile.type,
            size_bytes: assetFile.size,
            sha256: checksum,
          },
          csrfToken: session.csrf_token,
          idempotencyKey: createIdempotencyKey(),
        },
      );
      const form = new FormData();
      Object.entries(intent.upload_fields).forEach(([key, value]) => form.append(key, value));
      form.append("file", assetFile);
      const upload = await fetch(intent.upload_url, { method: "POST", body: form });
      if (!upload.ok) throw new Error("upload failed");
      setUploadState("verifying");
      const ready = await client.request<TrainingAssetResponse>(
        `/organizations/${organizationId}/locations/${locationId}/assets/${intent.asset_id}/complete`,
        {
          method: "POST",
          body: { sha256: checksum },
          csrfToken: session.csrf_token,
          idempotencyKey: createIdempotencyKey(),
        },
      );
      setUploadedAsset(ready);
      setUploadState("ready");
    } catch {
      setUploadState("failed");
      setError("Зображення не завантажено або не пройшло перевірку.");
    }
  };

  const publish = async () => {
    if (!draft || !readiness || !session) return;
    setBusy(true);
    setError(null);
    try {
      await client.request<TrainingPublishResponse>(`${draftBase}/publish`, {
        method: "POST",
        body: { expected_revision: readiness.revision },
        csrfToken: session.csrf_token,
        idempotencyKey: createIdempotencyKey(),
      });
      setPublishOpen(false);
      await loadWorkspace(locationId);
    } catch (caught) {
      setPublishOpen(false);
      if (caught instanceof ApiError && caught.code === "REVISION_CONFLICT") {
        setSaveState("conflict");
        setError("Чернетку змінили після перевірки готовності. Оновіть дані.");
      } else {
        setError("Навчання не опубліковано. Перевірте готовність і повторіть дію.");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="admin-page training-workspace" aria-labelledby="training-title">
      <div className="page-heading-row">
        <div>
          <p className="eyebrow">Навчання команди</p>
          <h1 id="training-title">Навчальні матеріали</h1>
          <p className="page-description">
            Створюйте уроки про меню, перевіряйте готовність і публікуйте одну стабільну версію.
          </p>
        </div>
        <LogoutButton />
      </div>

      <div className="training-toolbar">
        <div className="field-group">
          <label htmlFor="training-location">Локація</label>
          <select
            id="training-location"
            value={locationId}
            onChange={(event) => {
              setLocationId(event.target.value);
              void loadWorkspace(event.target.value);
            }}
          >
            {locations.map((location) => (
              <option key={location.id} value={location.id}>
                {location.name}
              </option>
            ))}
          </select>
        </div>
        {collection?.published ? (
          <StatusPill tone="success">
            Опубліковано v{collection.published.version_number}
          </StatusPill>
        ) : (
          <StatusPill>Ще не опубліковано</StatusPill>
        )}
        {draft ? <StatusPill tone="warning">Чернетка v{draft.version_number}</StatusPill> : null}
        <span className={`save-state save-${saveState}`} aria-live="polite">
          {saveStateLabel(saveState)}
        </span>
      </div>

      {error ? (
        <div className="inline-error training-conflict" role="alert">
          <p>{error}</p>
          {saveState === "conflict" ? (
            <button
              className="button button-quiet"
              type="button"
              onClick={() => void loadWorkspace(locationId)}
            >
              Оновити дані
            </button>
          ) : null}
        </div>
      ) : null}

      {loading ? (
        <p aria-live="polite">Завантажуємо навчальні матеріали…</p>
      ) : !draft ? (
        <div className="empty-state">
          <h2>Чернетки немає</h2>
          <p>Почніть першу версію або скопіюйте поточне опубліковане навчання.</p>
          <button
            className="button button-primary"
            type="button"
            onClick={() => void createDraft()}
            disabled={busy}
          >
            Створити чернетку
          </button>
        </div>
      ) : module ? (
        <div className="training-layout">
          <aside className="training-outline" aria-label="Структура навчання">
            <div className="training-panel-heading">
              <div>
                <p className="eyebrow">Фіксований модуль</p>
                <h2>{module.title_uk}</h2>
              </div>
              <span>{lessons.length} уроків</span>
            </div>
            <ol className="training-lesson-list">
              {lessons.map((lesson, index) => (
                <li
                  key={lesson.id}
                  className={lesson.id === selectedLesson?.id ? "is-selected" : ""}
                >
                  <button
                    className="training-lesson-select"
                    type="button"
                    onClick={() => setSelectedLessonId(lesson.id)}
                  >
                    <span>{lessonLabel(lesson)}</span>
                    <small>{lesson.content_blocks.length} блоків</small>
                  </button>
                  <div className="icon-actions">
                    <button
                      type="button"
                      className="button button-quiet"
                      onClick={() => reorderLessons(index, -1)}
                      disabled={index === 0 || busy}
                      aria-label={`Перемістити ${lesson.title_uk} вище`}
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      className="button button-quiet"
                      onClick={() => reorderLessons(index, 1)}
                      disabled={index === lessons.length - 1 || busy}
                      aria-label={`Перемістити ${lesson.title_uk} нижче`}
                    >
                      ↓
                    </button>
                    <button
                      type="button"
                      className="button button-quiet"
                      onClick={() => deleteLesson(lesson)}
                      disabled={lesson.content_blocks.length > 0 || busy}
                      aria-label={`Видалити ${lesson.title_uk}`}
                    >
                      ×
                    </button>
                  </div>
                </li>
              ))}
            </ol>
            <form
              className="training-add-form"
              aria-label="Новий урок"
              onSubmit={(event) => {
                event.preventDefault();
                addLesson();
              }}
            >
              <div className="field-group">
                <label htmlFor="lesson-title">Назва нового уроку</label>
                <input
                  id="lesson-title"
                  value={lessonTitle}
                  onChange={(event) => setLessonTitle(event.target.value)}
                  required
                />
              </div>
              <div className="field-group">
                <label htmlFor="lesson-minutes">Орієнтовні хвилини</label>
                <input
                  id="lesson-minutes"
                  type="number"
                  min="1"
                  max="240"
                  value={lessonMinutes}
                  onChange={(event) => setLessonMinutes(event.target.value)}
                />
              </div>
              <button className="button button-secondary" type="submit" disabled={busy}>
                Додати урок
              </button>
            </form>
          </aside>

          <section className="training-editor" aria-label="Редактор уроку">
            <form
              className="training-module-form"
              aria-label="Налаштування модуля"
              onSubmit={(event) => {
                event.preventDefault();
                saveModule();
              }}
            >
              <div className="field-group">
                <label htmlFor="module-title">Назва модуля</label>
                <input
                  id="module-title"
                  value={moduleTitle}
                  onChange={(event) => setModuleTitle(event.target.value)}
                  required
                />
              </div>
              <div className="field-group training-grow">
                <label htmlFor="module-description">Опис модуля</label>
                <input
                  id="module-description"
                  value={moduleDescription}
                  onChange={(event) => setModuleDescription(event.target.value)}
                />
              </div>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={moduleRequired}
                  onChange={(event) => setModuleRequired(event.target.checked)}
                />
                Обов’язковий модуль
              </label>
              <button className="button button-secondary" type="submit" disabled={busy}>
                Зберегти модуль
              </button>
            </form>

            {selectedLesson ? (
              <section className="lesson-editor" aria-labelledby="selected-lesson-title">
                <div className="training-panel-heading">
                  <div>
                    <p className="eyebrow">Урок</p>
                    <h2 id="selected-lesson-title">{selectedLesson.title_uk}</h2>
                  </div>
                  {selectedLesson.translation_status_en === "ready" ? (
                    <StatusPill tone="success">EN готово</StatusPill>
                  ) : (
                    <StatusPill tone="warning">EN: український fallback</StatusPill>
                  )}
                </div>
                <LessonSettingsForm
                  key={selectedLesson.id}
                  lesson={selectedLesson}
                  busy={busy}
                  onSave={saveLesson}
                />
                {selectedLesson.content_blocks.length ? (
                  <ol className="training-block-list">
                    {[...selectedLesson.content_blocks]
                      .sort((left, right) => left.position - right.position)
                      .map((block, index, blocks) => (
                        <li key={block.id} className="training-block-card">
                          <div>
                            <strong>{blockLabels[block.type]}</strong>
                            <pre>{JSON.stringify(block.payload, null, 2)}</pre>
                          </div>
                          <div className="icon-actions">
                            <button
                              className="button button-quiet"
                              type="button"
                              onClick={() => reorderBlocks(index, -1)}
                              disabled={index === 0 || busy}
                              aria-label={`Перемістити блок ${index + 1} вище`}
                            >
                              ↑
                            </button>
                            <button
                              className="button button-quiet"
                              type="button"
                              onClick={() => reorderBlocks(index, 1)}
                              disabled={index === blocks.length - 1 || busy}
                              aria-label={`Перемістити блок ${index + 1} нижче`}
                            >
                              ↓
                            </button>
                            <button
                              className="button button-quiet"
                              type="button"
                              onClick={() => deleteBlock(block.id)}
                              disabled={busy}
                              aria-label={`Видалити блок ${index + 1}`}
                            >
                              ×
                            </button>
                          </div>
                        </li>
                      ))}
                  </ol>
                ) : (
                  <div className="empty-state compact-empty">
                    <h3>Урок ще порожній</h3>
                    <p>Додайте хоча б один змістовний блок перед публікацією.</p>
                  </div>
                )}

                <form
                  className="training-block-form"
                  aria-label="Новий блок уроку"
                  onSubmit={(event) => {
                    event.preventDefault();
                    addBlock();
                  }}
                >
                  <div className="field-group">
                    <label htmlFor="block-type">Тип блока</label>
                    <select
                      id="block-type"
                      value={blockType}
                      onChange={(event) =>
                        setBlockType(event.target.value as TrainingContentBlockType)
                      }
                    >
                      {Object.entries(blockLabels).map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field-group training-grow">
                    <label htmlFor="block-text">
                      {blockType === "external_video"
                        ? "YouTube URL"
                        : blockType === "menu_item_card"
                          ? "ID позиції меню"
                          : blockType === "list"
                            ? "Пункти, кожен з нового рядка"
                            : "Основний текст українською"}
                    </label>
                    <textarea
                      id="block-text"
                      value={blockText}
                      onChange={(event) => setBlockText(event.target.value)}
                      required
                    />
                  </div>
                  {(blockType === "callout" ||
                    blockType === "menu_item_card" ||
                    blockType === "image" ||
                    blockType === "external_video") && (
                    <div className="field-group training-grow">
                      <label htmlFor="block-secondary">
                        {blockType === "image"
                          ? "Підпис"
                          : blockType === "external_video"
                            ? "Назва й короткий опис"
                            : "Додаткова примітка"}
                      </label>
                      <input
                        id="block-secondary"
                        value={blockSecondaryText}
                        onChange={(event) => setBlockSecondaryText(event.target.value)}
                        required={blockType === "external_video"}
                      />
                    </div>
                  )}
                  {blockType === "image" ? (
                    <fieldset className="asset-upload-fieldset">
                      <legend>Приватне зображення</legend>
                      <input
                        aria-label="Зображення уроку"
                        type="file"
                        accept="image/jpeg,image/png,image/webp"
                        onChange={(event) => {
                          setAssetFile(event.target.files?.[0] ?? null);
                          setUploadState("idle");
                          setUploadedAsset(null);
                        }}
                      />
                      <button
                        className="button button-secondary"
                        type="button"
                        onClick={() => void uploadAsset()}
                        disabled={
                          !assetFile || uploadState === "uploading" || uploadState === "verifying"
                        }
                      >
                        Завантажити зображення
                      </button>
                      <span aria-live="polite">
                        {uploadState === "uploading"
                          ? "Завантаження…"
                          : uploadState === "verifying"
                            ? "Перевірка файла…"
                            : uploadState === "ready"
                              ? "Зображення готове"
                              : uploadState === "failed"
                                ? "Зображення не готове"
                                : "Файл не вибрано"}
                      </span>
                    </fieldset>
                  ) : null}
                  <button className="button button-primary" type="submit" disabled={busy}>
                    Додати блок
                  </button>
                </form>
              </section>
            ) : null}
          </section>

          <aside className="training-readiness" aria-label="Готовність до публікації">
            <div className="training-panel-heading">
              <div>
                <p className="eyebrow">Перевірка</p>
                <h2>Готовність</h2>
              </div>
              <StatusPill tone={readiness?.can_publish ? "success" : "danger"}>
                {readiness?.can_publish ? "Готово" : "Є блокери"}
              </StatusPill>
            </div>
            {readiness?.blocking_errors.length ? (
              <ul className="readiness-list readiness-errors">
                {readiness.blocking_errors.map((issue) => (
                  <li key={`${issue.code}-${issue.entity_id}`}>{issue.message}</li>
                ))}
              </ul>
            ) : null}
            {readiness?.warnings.length ? (
              <div className="readiness-warning">
                <h3>Попередження</h3>
                <ul className="readiness-list">
                  {readiness.warnings.map((issue) => (
                    <li key={`${issue.code}-${issue.entity_id}`}>{issue.message}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            <button
              className="button button-primary"
              type="button"
              onClick={() => setPublishOpen(true)}
              disabled={!readiness?.can_publish || busy}
            >
              Опублікувати навчання
            </button>
          </aside>
        </div>
      ) : null}

      <ConfirmDialog
        open={publishOpen}
        title="Опублікувати цю версію навчання?"
        description="Команда одразу бачитиме нову версію. Попередня залишиться в незмінній історії."
        confirmLabel="Опублікувати"
        busy={busy}
        onCancel={() => setPublishOpen(false)}
        onConfirm={() => void publish()}
      />
    </section>
  );
}

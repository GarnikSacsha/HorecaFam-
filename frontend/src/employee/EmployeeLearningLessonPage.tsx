import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import type {
  EmployeeTrainingAssetAccessResponse,
  EmployeeTrainingContentBlock,
  EmployeeTrainingLessonDetail,
} from "../api/contracts";
import type { ApiClient } from "../api/client";
import { useSession } from "../session/SessionContext";

function textValue(payload: Record<string, unknown>, key: string): string | null {
  const value = payload[key];
  return typeof value === "string" && value.trim() ? value : null;
}

function stringList(payload: Record<string, unknown>, key: string): string[] {
  const value = payload[key];
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function FallbackNote({ visible }: { visible: boolean }) {
  return visible ? <span className="learning-fallback-note">Показано українською</span> : null;
}

function TrainingImageBlock({
  block,
  client,
}: {
  block: EmployeeTrainingContentBlock;
  client: ApiClient;
}) {
  const assetId = textValue(block.payload, "asset_id");
  const alt = textValue(block.payload, "alt_uk") ?? "Навчальне зображення";
  const caption = textValue(block.payload, "caption_uk");
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    if (!assetId) {
      return () => {
        active = false;
      };
    }
    client
      .request<EmployeeTrainingAssetAccessResponse>(`/me/training/assets/${assetId}/access`)
      .then((response) => {
        if (active) setUrl(response.url);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, [assetId, client]);

  return (
    <figure className="learning-media">
      {url ? <img src={url} alt={alt} loading="lazy" /> : null}
      {assetId && !url && !failed ? <p aria-live="polite">Завантажуємо зображення…</p> : null}
      {failed || !assetId ? (
        <p role="img" aria-label={alt}>
          Зображення тимчасово недоступне: {alt}
        </p>
      ) : null}
      {caption ? <figcaption>{caption}</figcaption> : null}
      <FallbackNote visible={block.translation_fallback} />
    </figure>
  );
}

function TrainingBlock({
  block,
  client,
}: {
  block: EmployeeTrainingContentBlock;
  client: ApiClient;
}) {
  const payload = block.payload;
  const fallback = <FallbackNote visible={block.translation_fallback} />;

  if (block.type === "heading") {
    const text = textValue(payload, "text_uk");
    if (!text) return null;
    return payload.level === 3 ? (
      <section>
        <h3>{text}</h3>
        {fallback}
      </section>
    ) : (
      <section>
        <h2>{text}</h2>
        {fallback}
      </section>
    );
  }
  if (block.type === "text") {
    const text = textValue(payload, "text_uk");
    return text ? (
      <section>
        <p className="learning-prose">{text}</p>
        {fallback}
      </section>
    ) : null;
  }
  if (block.type === "list") {
    const items = stringList(payload, "items_uk");
    if (!items.length) return null;
    const content = items.map((item, index) => <li key={`${block.id}-${index}`}>{item}</li>);
    return (
      <section>
        {payload.style === "ordered" ? <ol>{content}</ol> : <ul>{content}</ul>}
        {fallback}
      </section>
    );
  }
  if (block.type === "callout") {
    const title = textValue(payload, "title_uk");
    const text = textValue(payload, "text_uk");
    if (!text) return null;
    const tone = textValue(payload, "tone") ?? "info";
    return (
      <aside className={`learning-callout is-${tone}`} role="note">
        {title ? <h3>{title}</h3> : null}
        <p>{text}</p>
        {fallback}
      </aside>
    );
  }
  if (block.type === "menu_item_card") {
    const itemId = textValue(payload, "menu_item_id");
    const note = textValue(payload, "note_uk");
    if (!itemId) return null;
    return (
      <aside className="learning-menu-card">
        <p className="eyebrow">Пов’язана позиція меню</p>
        {note ? <p>{note}</p> : null}
        <Link to={`/employee/menu?item=${encodeURIComponent(itemId)}`}>
          Відкрити позицію в меню
        </Link>
        {fallback}
      </aside>
    );
  }
  if (block.type === "image") return <TrainingImageBlock block={block} client={client} />;
  if (block.type === "external_video") {
    const provider = textValue(payload, "provider");
    const videoId = textValue(payload, "video_id");
    const title = textValue(payload, "title_uk");
    const summary = textValue(payload, "summary_uk");
    if (provider !== "youtube" || !videoId || !/^[A-Za-z0-9_-]{11}$/.test(videoId) || !title)
      return null;
    return (
      <section className="learning-video">
        <h2>{title}</h2>
        {summary ? <p>{summary}</p> : null}
        <div className="learning-video-frame">
          <iframe
            src={`https://www.youtube-nocookie.com/embed/${videoId}`}
            title={title}
            loading="lazy"
            referrerPolicy="strict-origin-when-cross-origin"
            allow="accelerometer; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
          />
        </div>
        {fallback}
      </section>
    );
  }
  return null;
}

export function EmployeeLearningLessonPage() {
  const { client, session } = useSession();
  const { lessonId } = useParams<{ lessonId: string }>();
  const [lesson, setLesson] = useState<EmployeeTrainingLessonDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const locale = session?.user.preferred_locale === "en" ? "en" : "uk";

  const loadLesson = useCallback(async () => {
    if (!session || !lessonId) return;
    setLoading(true);
    setError(null);
    try {
      setLesson(
        await client.request<EmployeeTrainingLessonDetail>(
          `/me/training/lessons/${lessonId}?locale=${locale}`,
        ),
      );
    } catch {
      setError("Не вдалося завантажити урок. Перевірте посилання або спробуйте ще раз.");
    } finally {
      setLoading(false);
    }
  }, [client, lessonId, locale, session]);

  useEffect(() => {
    // Урок є серверним знімком і змінюється лише після відповіді API.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadLesson();
  }, [loadLesson]);

  return (
    <article className="employee-learning-page learning-reader lesson-reader">
      <Link className="learning-back-link" to="/employee/learning">
        ← До навчальних модулів
      </Link>
      {error ? (
        <div className="inline-error" role="alert">
          <p>{error}</p>
          <button className="button button-quiet" type="button" onClick={() => void loadLesson()}>
            Повторити
          </button>
        </div>
      ) : null}
      {loading ? <p aria-live="polite">Завантажуємо урок…</p> : null}
      {lesson ? (
        <>
          <header className="learning-reader-heading">
            <p className="eyebrow">Навчальний матеріал</p>
            <h1>{lesson.title}</h1>
            {lesson.description ? <p>{lesson.description}</p> : null}
            {lesson.estimated_minutes ? (
              <p className="learning-time-note">Читання: близько {lesson.estimated_minutes} хв</p>
            ) : null}
            <FallbackNote visible={lesson.translation_fallback} />
          </header>
          <div className="lesson-content">
            {lesson.content_blocks.map((block) => (
              <TrainingBlock key={block.id} block={block} client={client} />
            ))}
          </div>
        </>
      ) : null}
    </article>
  );
}

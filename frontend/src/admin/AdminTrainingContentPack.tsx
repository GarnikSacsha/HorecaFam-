import { useRef, useState } from "react";

import { createIdempotencyKey } from "../api/client";
import { useSession } from "../session/SessionContext";

interface ContentPack {
  notice: string;
  courses: Array<{
    code: string;
    title: string;
    positions: string[];
    lessons: Array<{ title: string; text: string }>;
    scenarios: Array<{
      scenario: string;
      action: string;
      alternatives: string[];
      explanation: string;
    }>;
  }>;
}

export function AdminTrainingContentPack({
  organizationId,
  draftBase,
  revision,
  busy,
  mutate,
}: {
  organizationId: string;
  draftBase: string;
  revision: number;
  busy: boolean;
  mutate: (action: () => Promise<unknown>) => Promise<boolean>;
}) {
  const { client, session } = useSession();
  const [preview, setPreview] = useState<ContentPack | null>(null);
  const [roles, setRoles] = useState<Array<{ id: string; name_uk: string; status: string }>>([]);
  const [waiterRole, setWaiterRole] = useState("");
  const [reviewed, setReviewed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [installed, setInstalled] = useState(false);
  const retry = useRef<{ signature: string; key: string } | null>(null);
  const load = async () => {
    if (loading || busy) return;
    setLoading(true);
    setError("");
    try {
      const [pack, available] = await Promise.all([
        client.request<ContentPack>(`/organizations/${organizationId}/training-content-pack`),
        client.request<Array<{ id: string; name_uk: string; status: string }>>(
          `/organizations/${organizationId}/operational-roles`,
        ),
      ]);
      setPreview(pack);
      setRoles(available.filter((role) => role.status === "active"));
    } catch {
      setError("Не вдалося завантажити пакет. Спробуйте ще раз.");
    } finally {
      setLoading(false);
    }
  };
  const install = async () => {
    if (!reviewed || !preview || !session || busy) return;
    const body = {
      expected_revision: revision,
      acknowledge_generic_content: true,
      waiter_role_id: waiterRole || null,
    };
    const signature = JSON.stringify(body);
    if (retry.current?.signature !== signature)
      retry.current = { signature, key: createIdempotencyKey() };
    const saved = await mutate(() =>
      client.request(`${draftBase}/content-pack`, {
        method: "POST",
        body,
        csrfToken: session.csrf_token,
        idempotencyKey: retry.current?.key,
      }),
    );
    if (saved) {
      setInstalled(true);
      retry.current = null;
    }
  };
  return (
    <section className="training-panel" aria-label="Початковий навчальний пакет">
      <h2>Runner, Bartender і Service Standards</h2>
      <p>
        23 навчальні розділи та 45 сценарних запитань. Пакет додається до чернетки; публікація
        навчання й одобрення запитань виконуються окремо.
      </p>
      <button
        className="button button-secondary"
        type="button"
        disabled={busy || loading}
        onClick={() => void load()}
      >
        Переглянути навчальний пакет
      </button>
      {error ? <p role="alert">{error}</p> : null}
      {preview ? (
        <>
          <p>{preview.notice}</p>
          {preview.courses.map((course) => (
            <details key={course.code}>
              <summary>
                {course.title} · {course.lessons.length} розділів · {course.scenarios.length}{" "}
                запитань
              </summary>
              {course.lessons.map((lesson) => (
                <article key={lesson.title}>
                  <h3>{lesson.title}</h3>
                  <p>{lesson.text}</p>
                </article>
              ))}
              <details>
                <summary>Сценарії та обґрунтування</summary>
                {course.scenarios.map((fact) => (
                  <article key={fact.scenario}>
                    <h4>{fact.scenario}</h4>
                    <p>{fact.action}</p>
                    <p>{fact.explanation}</p>
                    <p>Неприпустимі альтернативи: {fact.alternatives.join(" ")}</p>
                  </article>
                ))}
              </details>
            </details>
          ))}
          <div className="field-group">
            <label htmlFor="pack-waiter-role">Наявна посада офіціанта</label>
            <select
              id="pack-waiter-role"
              value={waiterRole}
              disabled={busy || installed}
              onChange={(event) => setWaiterRole(event.target.value)}
            >
              <option value="">Посада з кодом waiter (створити, якщо відсутня)</option>
              {roles.map((role) => (
                <option key={role.id} value={role.id}>
                  {role.name_uk}
                </option>
              ))}
            </select>
          </div>
          <label>
            <input
              type="checkbox"
              checked={reviewed}
              disabled={busy || installed}
              onChange={(event) => setReviewed(event.target.checked)}
            />{" "}
            Переглянуто загальний матеріал; локальні правила й рецептури перевірятимемо окремо.
          </label>
          <button
            className="button button-primary"
            type="button"
            disabled={!reviewed || busy || installed}
            onClick={() => void install()}
          >
            Додати пакет до чернетки
          </button>
        </>
      ) : null}
      {installed ? (
        <p role="status">
          Пакет додано. Перевірте аудиторії та опублікуйте навчання, потім перегляньте кандидатів у
          банку запитань.
        </p>
      ) : null}
    </section>
  );
}

import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import type { EmployeeTrainingModuleDetail } from "../api/contracts";
import { useSession } from "../session/SessionContext";

export function EmployeeLearningModulePage() {
  const { client, session } = useSession();
  const { moduleId } = useParams<{ moduleId: string }>();
  const [module, setModule] = useState<EmployeeTrainingModuleDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const locale = session?.user.preferred_locale === "en" ? "en" : "uk";

  const loadModule = useCallback(async () => {
    if (!session || !moduleId) return;
    setLoading(true);
    setError(null);
    try {
      setModule(
        await client.request<EmployeeTrainingModuleDetail>(
          `/me/training/modules/${moduleId}?locale=${locale}`,
        ),
      );
    } catch {
      setError("Не вдалося завантажити модуль. Перевірте посилання або спробуйте ще раз.");
    } finally {
      setLoading(false);
    }
  }, [client, locale, moduleId, session]);

  useEffect(() => {
    // Модуль є серверним знімком і змінюється лише після відповіді API.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadModule();
  }, [loadModule]);

  return (
    <article className="employee-learning-page learning-reader">
      <Link aria-label="До всіх модулів" className="learning-back-link" to="/employee/learning">
        ← До всіх модулів
      </Link>
      {error ? (
        <div className="inline-error" role="alert">
          <p>{error}</p>
          <button className="button button-quiet" type="button" onClick={() => void loadModule()}>
            Повторити
          </button>
        </div>
      ) : null}
      {loading ? <p aria-live="polite">Завантажуємо модуль…</p> : null}
      {module ? (
        <>
          <header className="learning-reader-heading">
            <p className="eyebrow">Навчальний модуль</p>
            <h1>{module.title}</h1>
            {module.description ? <p>{module.description}</p> : null}
            {module.translation_fallback ? (
              <span className="learning-fallback-note">Показано українською</span>
            ) : null}
          </header>
          {module.lessons.length ? (
            <ol className="learning-card-list learning-lesson-list" aria-label="Уроки модуля">
              {module.lessons.map((lesson) => (
                <li key={lesson.id}>
                  <Link className="learning-card" to={`/employee/learning/lessons/${lesson.id}`}>
                    <span className="learning-card-copy">
                      <strong>{lesson.title}</strong>
                      {lesson.description ? <span>{lesson.description}</span> : null}
                      {lesson.estimated_minutes ? (
                        <small>Близько {lesson.estimated_minutes} хв</small>
                      ) : null}
                      {lesson.translation_fallback ? (
                        <span className="learning-fallback-note">Показано українською</span>
                      ) : null}
                    </span>
                    <span aria-hidden="true">→</span>
                  </Link>
                </li>
              ))}
            </ol>
          ) : (
            <div className="empty-state">
              <h2>У цьому модулі немає уроків</h2>
            </div>
          )}
        </>
      ) : null}
    </article>
  );
}

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import type { EmployeeTrainingReferenceResponse } from "../api/contracts";
import { LogoutButton } from "../auth/LogoutButton";
import { useSession } from "../session/SessionContext";

export function EmployeeLearningPage() {
  const { client, session } = useSession();
  const [response, setResponse] = useState<EmployeeTrainingReferenceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const locale = session?.user.preferred_locale === "en" ? "en" : "uk";

  const loadTraining = useCallback(async () => {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      setResponse(
        await client.request<EmployeeTrainingReferenceResponse>(`/me/training?locale=${locale}`),
      );
    } catch {
      setError("Не вдалося завантажити навчальні матеріали. Спробуйте ще раз.");
    } finally {
      setLoading(false);
    }
  }, [client, locale, session]);

  useEffect(() => {
    // Довідник є серверним знімком і змінюється лише після відповіді API.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadTraining();
  }, [loadTraining]);

  return (
    <section className="employee-learning-page" aria-labelledby="employee-learning-title">
      <div className="employee-learning-heading">
        <div>
          <p className="eyebrow">Робочий довідник</p>
          <h1 id="employee-learning-title">Навчання</h1>
          {response?.training ? (
            <p className="learning-version-note">
              Опублікована версія {response.training.version_number}
            </p>
          ) : null}
        </div>
        <LogoutButton />
      </div>

      {error ? (
        <div className="inline-error" role="alert">
          <p>{error}</p>
          <button className="button button-quiet" type="button" onClick={() => void loadTraining()}>
            Повторити
          </button>
        </div>
      ) : null}
      {loading ? <p aria-live="polite">Завантажуємо навчальні матеріали…</p> : null}
      {!loading && response && !response.training ? (
        <div className="empty-state">
          <h2>Навчальні матеріали ще не опубліковано</h2>
          <p>Коли адміністратор опублікує матеріали вашої локації, вони з’являться тут.</p>
        </div>
      ) : null}
      {response?.training && response.modules.length === 0 ? (
        <div className="empty-state">
          <h2>У цій версії немає модулів</h2>
          <p>Поверніться пізніше після оновлення матеріалів.</p>
        </div>
      ) : null}
      {response?.modules.length ? (
        <div className="learning-card-list" aria-label="Навчальні модулі">
          {response.modules.map((module) => (
            <Link
              className="learning-card"
              key={module.id}
              to={`/employee/learning/modules/${module.id}`}
            >
              <span className="learning-card-copy">
                <strong>{module.title}</strong>
                {module.description ? <span>{module.description}</span> : null}
                <small>
                  {module.lesson_count} {module.lesson_count === 1 ? "урок" : "уроків"}
                </small>
                {module.translation_fallback ? (
                  <span className="learning-fallback-note">Показано українською</span>
                ) : null}
              </span>
              <span aria-hidden="true">→</span>
            </Link>
          ))}
        </div>
      ) : null}
    </section>
  );
}

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import type { OwnEmployeeProfile, OwnEmployeeProfilesResponse } from "../api/contracts";
import { LogoutButton } from "../auth/LogoutButton";
import { useSession } from "../session/SessionContext";
import { StatusPill } from "../ui/States";

export function PendingPage() {
  const navigate = useNavigate();
  const { client, refreshSession, session, status } = useSession();
  const [profile, setProfile] = useState<OwnEmployeeProfile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    if (status !== "authenticated" || !session) return;
    const organizationId = session.organization_access.find(
      (access) => access.is_employee,
    )?.organization_id;
    let active = true;
    client
      .request<OwnEmployeeProfilesResponse>("/me/profile")
      .then((response) => {
        if (!active) return;
        const current =
          response.profiles.find((item) => item.organization.id === organizationId) ?? null;
        setProfile(current);
        if (!current) setError("Профіль працівника не знайдено.");
      })
      .catch(() => {
        if (active) setError("Не вдалося завантажити профіль.");
      });
    return () => {
      active = false;
    };
  }, [client, session, status]);

  const checkStatus = async () => {
    setRefreshing(true);
    await refreshSession();
    setRefreshing(false);
    void navigate("/", { replace: true });
  };

  return (
    <section className="pending-page" aria-labelledby="pending-title">
      <div className="page-heading-row">
        <div>
          <p className="eyebrow">Профіль працівника</p>
          <h1 id="pending-title">Майже готово</h1>
        </div>
        <LogoutButton />
      </div>
      {error ? (
        <p className="inline-error" role="alert">
          {error}
        </p>
      ) : null}
      {profile ? (
        <div className="pending-summary">
          <StatusPill tone="warning">Очікує налаштування адміністратором</StatusPill>
          <h2>{profile.organization.name}</h2>
          <p>
            Адміністратор має призначити вашу роль і локацію, а потім окремо активувати доступ. Ваші
            дані та прогрес не буде створено наперед.
          </p>
          <dl className="detail-list">
            <div>
              <dt>Роль</dt>
              <dd>{profile.operational_role?.name_uk ?? "Ще не призначено"}</dd>
            </div>
            <div>
              <dt>Локація</dt>
              <dd>{profile.location?.name ?? "Ще не призначено"}</dd>
            </div>
          </dl>
          <button
            className="button button-primary"
            type="button"
            onClick={() => void checkStatus()}
            disabled={refreshing}
          >
            {refreshing ? "Перевіряємо…" : "Перевірити статус"}
          </button>
        </div>
      ) : !error ? (
        <p aria-live="polite">Завантажуємо профіль…</p>
      ) : null}
    </section>
  );
}

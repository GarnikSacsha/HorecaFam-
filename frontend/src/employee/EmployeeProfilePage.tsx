import { useEffect, useState } from "react";

import type { OwnEmployeeProfile, OwnEmployeeProfilesResponse } from "../api/contracts";
import { LogoutButton } from "../auth/LogoutButton";
import { useSession } from "../session/SessionContext";
import "./employee-profile.css";

export function EmployeeProfilePage() {
  const { client, session } = useSession();
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<{
    profile: OwnEmployeeProfile | null;
    error: string | null;
  } | null>(null);
  const organizationId = session?.organization_access.find(
    (access) => access.is_employee && access.membership_status === "active",
  )?.organization_id;

  useEffect(() => {
    let active = true;
    client.request<OwnEmployeeProfilesResponse>("/me/profile").then(
      (response) => {
        if (!active) return;
        // Організацію визначає сесія; порядок профілів у відповіді не надає доступу.
        const profile =
          response.profiles.find(
            (item) =>
              item.organization.id === organizationId && item.membership_status === "active",
          ) ?? null;
        setResult({ profile, error: profile ? null : "Активний профіль працівника не знайдено." });
      },
      () => {
        if (active) setResult({ profile: null, error: "Не вдалося завантажити профіль." });
      },
    );
    return () => {
      active = false;
    };
  }, [client, organizationId, attempt]);

  const profile = result?.profile;
  const name = profile ? [profile.first_name, profile.last_name].filter(Boolean).join(" ") : "";
  return (
    <section className="employee-profile-page" aria-labelledby="profile-title">
      <div className="page-heading-row">
        <div>
          <p className="eyebrow">Bacara · Команда</p>
          <h1 id="profile-title">Мій профіль</h1>
        </div>
        <LogoutButton />
      </div>
      {!result ? <p role="status">Завантажуємо профіль…</p> : null}
      {result?.error ? (
        <div className="employee-profile-message">
          <p role="alert">{result.error}</p>
          <button
            className="button button-primary"
            type="button"
            onClick={() => {
              setResult(null);
              setAttempt((value) => value + 1);
            }}
          >
            Повторити
          </button>
        </div>
      ) : null}
      {profile ? (
        <>
          <div className="employee-profile-identity">
            <p className="eyebrow">Працівник</p>
            <h2>{name || "Ім’я не вказано"}</h2>
            <p>{profile.organization.name}</p>
          </div>
          <dl className="employee-profile-details">
            <div>
              <dt>Заклад</dt>
              <dd>{profile.location?.name ?? "Не вказано"}</dd>
            </div>
            <div>
              <dt>Робоча роль</dt>
              <dd>{profile.operational_role?.name_uk ?? "Не вказано"}</dd>
            </div>
            <div>
              <dt>Статус доступу</dt>
              <dd>Активний</dd>
            </div>
          </dl>
          <p className="employee-profile-note">
            Ці дані налаштовує адміністратор. Якщо потрібне уточнення, зверніться до нього.
          </p>
        </>
      ) : null}
    </section>
  );
}

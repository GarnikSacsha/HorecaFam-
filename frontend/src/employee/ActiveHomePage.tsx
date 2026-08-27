import { useEffect, useState } from "react";

import type { OwnEmployeeProfile, OwnEmployeeProfilesResponse } from "../api/contracts";
import { LogoutButton } from "../auth/LogoutButton";
import { useSession } from "../session/SessionContext";
import { StatusPill } from "../ui/States";

export function ActiveHomePage() {
  const { client, session, status } = useSession();
  const [profile, setProfile] = useState<OwnEmployeeProfile | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status !== "authenticated" || !session) return;
    const organizationId = session.organization_access.find(
      (access) => access.is_employee && access.membership_status === "active",
    )?.organization_id;
    let active = true;
    client
      .request<OwnEmployeeProfilesResponse>("/me/profile")
      .then((response) => {
        if (!active) return;
        const current =
          response.profiles.find(
            (item) =>
              item.organization.id === organizationId && item.membership_status === "active",
          ) ?? null;
        setProfile(current);
        if (!current) setError("Активний профіль працівника не знайдено.");
      })
      .catch(() => {
        if (active) setError("Не вдалося завантажити профіль.");
      });
    return () => {
      active = false;
    };
  }, [client, session, status]);

  if (error)
    return (
      <p className="inline-error" role="alert">
        {error}
      </p>
    );
  if (!profile) return <p aria-live="polite">Завантажуємо вашу головну сторінку…</p>;

  return (
    <section className="active-home" aria-labelledby="active-home-title">
      <div className="page-heading-row">
        <div>
          <p className="eyebrow">Головна</p>
          <h1 id="active-home-title">Вітаємо, {profile.first_name ?? "колего"}</h1>
          <p className="page-description">{profile.organization.name}</p>
        </div>
        <LogoutButton />
      </div>

      <div className="employee-context-row" aria-label="Робочий контекст">
        <StatusPill tone="success">Активний профіль</StatusPill>
        <span>{profile.operational_role?.name_uk ?? "Роль не вказана"}</span>
        <span>{profile.location?.name ?? "Локація не вказана"}</span>
      </div>

      <section className="next-action-empty" aria-labelledby="assignment-title">
        <p className="eyebrow">Наступний крок</p>
        <h2 id="assignment-title">Навчання ще не призначено</h2>
        <p>
          Ваш профіль активний. Коли адміністратор опублікує відповідні матеріали, тут з’явиться
          перша доступна дія.
        </p>
        <p className="quiet-note">Нічого додатково робити зараз не потрібно.</p>
      </section>
    </section>
  );
}

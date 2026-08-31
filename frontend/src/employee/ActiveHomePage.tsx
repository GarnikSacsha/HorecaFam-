import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import type {
  EmployeeTrainingHomeResponse,
  OwnEmployeeProfile,
  OwnEmployeeProfilesResponse,
} from "../api/contracts";
import { LogoutButton } from "../auth/LogoutButton";
import { useSession } from "../session/SessionContext";
import { StatusPill } from "../ui/States";

function assignmentCopy(response: EmployeeTrainingHomeResponse) {
  if (response.next_action === "open_final_exam") {
    return {
      heading: "Час пройти Final Exam",
      action: "Відкрити Final Exam",
      note: "20 запитань без підказок. Результат і правильні відповіді з’являться лише після фінального підтвердження.",
      to: "/employee/final-exam",
    };
  }
  if (response.next_action === "open_practice") {
    return {
      heading: "Час перевірити знання меню",
      action: "Відкрити Практику",
      note: "Дайте відповіді на 10 запитань. Результат з’явиться лише після явного завершення.",
      to: "/employee/practice",
    };
  }
  if (response.assignment?.status === "completed") {
    return {
      heading: "Навчання завершено",
      action: "Переглянути матеріали",
      note: "Призначені матеріали залишаються доступними для повторення.",
      to: "/employee/learning",
    };
  }
  if (response.assignment?.status === "in_progress") {
    return {
      heading: "Продовжуйте навчання",
      action: "Продовжити навчання",
      note: "Поверніться до призначеної версії з того місця, де зупинилися.",
      to: "/employee/learning",
    };
  }
  return {
    heading: "Розпочніть навчання",
    action: "Розпочати навчання",
    note: "Для вас уже підготовлено перший навчальний крок.",
    to: "/employee/learning",
  };
}

export function ActiveHomePage() {
  const { client, session, status } = useSession();
  const [profile, setProfile] = useState<OwnEmployeeProfile | null>(null);
  const [training, setTraining] = useState<EmployeeTrainingHomeResponse | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status !== "authenticated" || !session) return;
    const organizationId = session.organization_access.find(
      (access) => access.is_employee && access.membership_status === "active",
    )?.organization_id;
    const locale = session.user.preferred_locale === "en" ? "en" : "uk";
    let active = true;

    Promise.all([
      client.request<OwnEmployeeProfilesResponse>("/me/profile"),
      client.request<EmployeeTrainingHomeResponse>(`/me/training?locale=${locale}`),
    ])
      .then(([profileResponse, trainingResponse]) => {
        if (!active) return;
        const current =
          profileResponse.profiles.find(
            (item) =>
              item.organization.id === organizationId && item.membership_status === "active",
          ) ?? null;
        setProfile(current);
        setTraining(trainingResponse);
        if (!current) setError("Активний профіль працівника не знайдено.");
      })
      .catch(() => {
        if (active) setError("Не вдалося завантажити вашу головну сторінку.");
      })
      .finally(() => {
        if (active) setLoaded(true);
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
  if (!loaded || !profile) return <p aria-live="polite">Завантажуємо вашу головну сторінку…</p>;

  const assignedTraining =
    training?.assignment && training.training && training.progress
      ? {
          training: training.training,
          progress: training.progress,
          copy: assignmentCopy(training),
        }
      : null;

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

      {assignedTraining ? (
        <section className="next-action-panel" aria-labelledby="assignment-title">
          <p className="eyebrow">Наступний крок</p>
          <h2 id="assignment-title">{assignedTraining.copy.heading}</h2>
          <p className="assignment-version">
            Призначена версія {assignedTraining.training.version_number}
          </p>
          <p>
            {assignedTraining.progress.completed_required_lesson_count} із{" "}
            {assignedTraining.progress.required_lesson_count} обов’язкових уроків завершено
          </p>
          <div
            className="training-progress"
            role="progressbar"
            aria-label="Поточний прогрес"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={assignedTraining.progress.percentage}
          >
            <span style={{ width: `${assignedTraining.progress.percentage}%` }} />
          </div>
          <p className="quiet-note">{assignedTraining.copy.note}</p>
          <Link className="button button-primary next-action-link" to={assignedTraining.copy.to}>
            {assignedTraining.copy.action}
          </Link>
        </section>
      ) : (
        <section className="next-action-empty" aria-labelledby="assignment-title">
          <p className="eyebrow">Наступний крок</p>
          <h2 id="assignment-title">Навчання ще не призначено</h2>
          <p>
            Ваш профіль активний. Коли адміністратор призначить відповідні матеріали, тут з’явиться
            перша доступна дія.
          </p>
          <p className="quiet-note">Нічого додатково робити зараз не потрібно.</p>
        </section>
      )}
    </section>
  );
}

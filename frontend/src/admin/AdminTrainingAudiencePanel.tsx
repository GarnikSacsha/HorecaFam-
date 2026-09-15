import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../api/client";
import type { OperationalRoleSummary, TrainingAudienceResponse } from "../api/contracts";
import { useSession } from "../session/SessionContext";

export function AdminTrainingAudiencePanel({
  organizationId,
  locationId,
  versionId,
  busy,
  onBusyChange,
  onSaved,
}: {
  organizationId: string;
  locationId: string;
  versionId: string;
  busy: boolean;
  onBusyChange: (busy: boolean) => void;
  onSaved: (revision: number) => Promise<void>;
}) {
  const { client, session } = useSession();
  const [roles, setRoles] = useState<OperationalRoleSummary[]>([]);
  const [snapshot, setSnapshot] = useState<TrainingAudienceResponse | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const generation = useRef(0);
  const pending = useRef(false);
  const base = `/organizations/${organizationId}/locations/${locationId}/training-versions/${versionId}/audiences`;

  const load = useCallback(async () => {
    const current = ++generation.current;
    setLoading(true);
    setError(null);
    setSaved(false);
    setSnapshot(null);
    try {
      const [nextRoles, nextAudience] = await Promise.all([
        client.request<OperationalRoleSummary[]>(
          `/organizations/${organizationId}/operational-roles`,
        ),
        client.request<TrainingAudienceResponse>(base),
      ]);
      if (current !== generation.current) return;
      if (nextAudience.training_version_id !== versionId)
        throw new Error("Audience version mismatch");
      setRoles(nextRoles);
      setSnapshot(nextAudience);
      setSelected(nextAudience.operational_role_ids);
      setConflict(false);
    } catch {
      if (current === generation.current)
        setError("Не вдалося завантажити аудиторію. Збереження недоступне.");
    } finally {
      if (current === generation.current) setLoading(false);
    }
  }, [base, client, organizationId, versionId]);

  useEffect(() => {
    // Повний серверний набір потрібен до будь-якої заміни аудиторії.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
    return () => {
      generation.current += 1;
    };
  }, [load]);

  const valid =
    selected.length > 0 &&
    selected.every((id) => roles.some((role) => role.id === id && role.status === "active"));
  const changed =
    snapshot !== null &&
    [...selected].sort().join() !== [...snapshot.operational_role_ids].sort().join();
  const save = async () => {
    if (!snapshot || !session || !valid || !changed || busy || pending.current || conflict) return;
    const current = generation.current;
    pending.current = true;
    setSaving(true);
    onBusyChange(true);
    setError(null);
    setSaved(false);
    let persisted = false;
    try {
      const result = await client.request<TrainingAudienceResponse>(base, {
        method: "PUT",
        body: { expected_revision: snapshot.revision, operational_role_ids: selected },
        csrfToken: session.csrf_token,
      });
      if (current !== generation.current) return;
      persisted = true;
      setSnapshot(result);
      setSelected(result.operational_role_ids);
      setSaved(true);
      await onSaved(result.revision);
    } catch (caught) {
      if (current !== generation.current) return;
      if (persisted) {
        setError("Аудиторію збережено, але готовність навчання не оновлено. Оновіть сторінку.");
      } else if (
        caught instanceof ApiError &&
        ["REVISION_CONFLICT", "VERSION_IMMUTABLE"].includes(caught.code)
      ) {
        setConflict(true);
        setError(
          "Чернетку вже змінено. Ваш вибір залишився на екрані. Завантаження знову замінить його серверним.",
        );
      } else {
        setError(
          "Аудиторію не збережено. Ваш вибір залишився на екрані. Перевірте ролі та повторіть дію.",
        );
      }
    } finally {
      pending.current = false;
      if (current === generation.current) {
        setSaving(false);
        onBusyChange(false);
      }
    }
  };
  const options = [
    ...roles
      .filter(
        (role) => role.status === "active" || snapshot?.operational_role_ids.includes(role.id),
      )
      .map((role) => ({
        id: role.id,
        active: role.status === "active",
        label: role.name_uk + (role.status === "active" ? "" : " · неактивна роль"),
      })),
    ...(snapshot?.operational_role_ids ?? [])
      .filter((id) => !roles.some((role) => role.id === id))
      .map((id) => ({ id, active: false, label: `Недоступна роль · ${id}` })),
  ];

  return (
    <section className="training-readiness form-stack" aria-label="Аудиторія навчання">
      <h2>Для кого це навчання</h2>
      <p>
        Оберіть операційні ролі команди цієї локації. Зміни стосуються чернетки та набудуть чинності
        після публікації.
      </p>
      {loading ? <p aria-live="polite">Завантажуємо аудиторію…</p> : null}
      {error ? (
        <p role="alert" className="inline-error">
          {error}
        </p>
      ) : null}
      {!loading && snapshot ? (
        <form
          className="form-stack"
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
        >
          <fieldset className="field-group" disabled={busy || saving}>
            <legend>Операційні ролі</legend>
            {options.map((role) => (
              <label className="check-row" key={role.id}>
                <input
                  type="checkbox"
                  checked={selected.includes(role.id)}
                  disabled={!role.active && !selected.includes(role.id)}
                  onChange={(event) => {
                    setSaved(false);
                    setSelected((current) =>
                      event.target.checked
                        ? [...current, role.id]
                        : current.filter((id) => id !== role.id),
                    );
                  }}
                />
                {role.label}
              </label>
            ))}
          </fieldset>
          {!roles.some((role) => role.status === "active") ? (
            <p>Активних операційних ролей немає.</p>
          ) : null}
          {!valid ? (
            <p>
              Оберіть щонайменше одну активну роль. Неактивні або недоступні ролі потрібно прибрати
              явно.
            </p>
          ) : null}
          <button
            className="button button-secondary"
            type="submit"
            disabled={busy || saving || conflict || !valid || !changed}
          >
            {saving ? "Збереження аудиторії…" : "Зберегти аудиторію"}
          </button>
        </form>
      ) : null}
      {saved ? <p aria-live="polite">Аудиторію збережено.</p> : null}
      {!loading && (error || conflict) ? (
        <button
          className="button button-quiet"
          type="button"
          disabled={busy || saving}
          onClick={() => void load()}
        >
          Завантажити аудиторію знову
        </button>
      ) : null}
    </section>
  );
}

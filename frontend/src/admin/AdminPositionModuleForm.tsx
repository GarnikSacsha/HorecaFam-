import { useEffect, useId, useState } from "react";
import type { OperationalRoleSummary, TrainingModuleResponse } from "../api/contracts";
import { useSession } from "../session/SessionContext";

export interface PositionModuleValues {
  title_uk: string;
  domain_type: "service" | "sales" | "venue_standards";
  all_positions: boolean;
  operational_role_ids: string[];
}

export function AdminPositionModuleForm({
  organizationId,
  module,
  busy,
  onSave,
}: {
  organizationId: string;
  module?: TrainingModuleResponse;
  busy: boolean;
  onSave: (values: PositionModuleValues) => Promise<boolean>;
}) {
  const { client } = useSession();
  const id = useId();
  const [title, setTitle] = useState("");
  const [domain, setDomain] = useState<PositionModuleValues["domain_type"]>("service");
  const [allPositions, setAllPositions] = useState(module?.all_positions ?? Boolean(module));
  const [selected, setSelected] = useState(module?.operational_role_ids ?? []);
  const [roles, setRoles] = useState<OperationalRoleSummary[] | null>(null);
  const [error, setError] = useState(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let active = true;
    client
      .request<OperationalRoleSummary[]>(`/organizations/${organizationId}/operational-roles`)
      .then((items) => {
        if (active) {
          setRoles(items);
          setError(false);
        }
      })
      .catch(() => {
        if (active) setError(true);
      });
    return () => {
      active = false;
    };
  }, [client, organizationId, reload]);
  const valid =
    roles !== null &&
    !error &&
    (allPositions ||
      (selected.length > 0 &&
        selected.every((value) =>
          roles.some((role) => role.id === value && role.status === "active"),
        )));
  const changed =
    !module ||
    allPositions !== module.all_positions ||
    [...selected].sort().join() !== [...(module.operational_role_ids ?? [])].sort().join();
  return (
    <form
      className="form-stack training-add-form"
      aria-label={module ? "Аудиторія модуля" : "Новий модуль"}
      onSubmit={(event) => {
        event.preventDefault();
        if (!valid || busy || !changed || (!module && !title.trim())) return;
        void onSave({
          title_uk: title.trim(),
          domain_type: domain,
          all_positions: allPositions,
          operational_role_ids: allPositions ? [] : selected,
        }).then((saved) => {
          if (saved && !module) {
            setTitle("");
            setSelected([]);
            setAllPositions(false);
          }
        });
      }}
    >
      <h3>{module ? "Позиції цього модуля" : "Додати модуль"}</h3>
      {!module ? (
        <>
          <div className="field-group">
            <label htmlFor={`${id}-title`}>Назва нового модуля</label>
            <input
              id={`${id}-title`}
              value={title}
              maxLength={200}
              required
              disabled={busy}
              onChange={(event) => setTitle(event.target.value)}
            />
          </div>
          <div className="field-group">
            <label htmlFor={`${id}-domain`}>Напрям модуля</label>
            <select
              id={`${id}-domain`}
              value={domain}
              disabled={busy}
              onChange={(event) =>
                setDomain(event.target.value as PositionModuleValues["domain_type"])
              }
            >
              <option value="service">Сервіс</option>
              <option value="sales">Продажі</option>
              <option value="venue_standards">Стандарти закладу</option>
            </select>
          </div>
        </>
      ) : null}
      <p>Модуль доступний обраним позиціям у межах аудиторії всього навчання.</p>
      {error ? (
        <p role="alert">
          Не вдалося завантажити позиції.{" "}
          <button
            type="button"
            className="button button-quiet"
            onClick={() => setReload((value) => value + 1)}
          >
            Повторити
          </button>
        </p>
      ) : null}
      {!roles && !error ? <p aria-live="polite">Завантажуємо позиції…</p> : null}
      <fieldset className="field-group" disabled={busy || roles === null || error}>
        <legend>Аудиторія модуля</legend>
        <label className="check-row">
          <input
            type="checkbox"
            checked={allPositions}
            onChange={(event) => setAllPositions(event.target.checked)}
          />
          Усі позиції навчання
        </label>
        {(roles ?? [])
          .filter((role) => role.status === "active" || selected.includes(role.id))
          .map((role) => (
            <label className="check-row" key={role.id}>
              <input
                type="checkbox"
                checked={selected.includes(role.id)}
                disabled={allPositions}
                onChange={(event) =>
                  setSelected((current) =>
                    event.target.checked
                      ? [...current, role.id]
                      : current.filter((value) => value !== role.id),
                  )
                }
              />
              {role.name_uk}
              {role.status === "active" ? "" : " · неактивна позиція"}
            </label>
          ))}
        {selected
          .filter((value) => roles && !roles.some((role) => role.id === value))
          .map((value) => (
            <label className="check-row" key={value}>
              <input
                type="checkbox"
                checked
                disabled={allPositions}
                onChange={() => setSelected((current) => current.filter((item) => item !== value))}
              />
              Недоступна позиція · {value}
            </label>
          ))}
      </fieldset>
      {!valid && roles && !error ? <p>Оберіть активні позиції або всі позиції навчання.</p> : null}
      <button
        type="submit"
        className="button button-secondary"
        disabled={busy || !valid || !changed || (!module && !title.trim())}
      >
        {module ? "Зберегти аудиторію модуля" : "Додати модуль"}
      </button>
    </form>
  );
}

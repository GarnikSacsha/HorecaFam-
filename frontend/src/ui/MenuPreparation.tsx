import { useId } from "react";
import type { MenuPreparation } from "../api/contracts";

const textFields = [
  ["technique_uk", "Техніка приготування", 200],
  ["glassware_uk", "Посуд", 200],
  ["garnish_uk", "Гарнір", 500],
  ["serving_standard_uk", "Стандарт подачі", 2000],
] as const;
const empty: MenuPreparation = {
  volume_ml: null,
  technique_uk: null,
  glassware_uk: null,
  garnish_uk: null,
  serving_standard_uk: null,
  preparation_seconds: null,
};

export function MenuPreparationEditor({
  value,
  onChange,
  disabled,
}: {
  value: MenuPreparation | null;
  onChange: (value: MenuPreparation | null) => void;
  disabled: boolean;
}) {
  const id = useId();
  const change = (field: keyof MenuPreparation, next: string | number | null) => {
    const updated = { ...(value ?? empty), [field]: next };
    onChange(Object.values(updated).every((item) => item === null || item === "") ? null : updated);
  };
  return (
    <details>
      <summary>Приготування й подача (необов’язково)</summary>
      <p>
        Заповнюйте лише підтверджені дані технологічної картки. Порожнє поле означає, що дані не
        вказані.
      </p>
      {(
        [
          ["volume_ml", "Об’єм, мл", 10000],
          ["preparation_seconds", "Час приготування, с", 86400],
        ] as const
      ).map(([field, label, max]) => (
        <div className="field-group" key={field}>
          <label htmlFor={`${id}-${field}`}>{label}</label>
          <input
            id={`${id}-${field}`}
            type="number"
            min="1"
            max={max}
            step="1"
            disabled={disabled}
            value={value?.[field] ?? ""}
            onChange={(event) =>
              change(field, event.target.value === "" ? null : Number(event.target.value))
            }
          />
        </div>
      ))}
      {textFields.map(([field, label, max]) => (
        <div className="field-group" key={field}>
          <label htmlFor={`${id}-${field}`}>{label}</label>
          <textarea
            id={`${id}-${field}`}
            rows={2}
            maxLength={max}
            disabled={disabled}
            value={value?.[field] ?? ""}
            onChange={(event) => change(field, event.target.value || null)}
          />
        </div>
      ))}
    </details>
  );
}

export function MenuPreparationDetails({ value }: { value: MenuPreparation | null | undefined }) {
  if (!value || !Object.values(value).some((item) => item !== null && item !== "")) return null;
  return (
    <section>
      <h3>Приготування й подача</h3>
      <dl>
        {value.volume_ml !== null ? (
          <>
            <dt>Об’єм</dt>
            <dd>{value.volume_ml} мл</dd>
          </>
        ) : null}
        {textFields.map(([field, label]) =>
          value[field] ? (
            <div key={field}>
              <dt>{label}</dt>
              <dd>{value[field]}</dd>
            </div>
          ) : null,
        )}
        {value.preparation_seconds !== null ? (
          <>
            <dt>Час приготування</dt>
            <dd>{value.preparation_seconds} с</dd>
          </>
        ) : null}
      </dl>
    </section>
  );
}

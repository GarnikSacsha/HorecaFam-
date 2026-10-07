import { useEffect, useRef, useState } from "react";
import { ApiError, createIdempotencyKey } from "../api/client";
import { uploadPrivateImage } from "../api/assets";
import type {
  AcademyArticle,
  AcademyCollection,
  AcademyWrite,
  LocationSummary,
} from "../api/contracts";
import { useSession } from "../session/SessionContext";

type Role = { id: string; name_uk: string; status: string };
const empty: AcademyWrite = {
  slug: "",
  title_uk: "",
  summary_uk: "",
  body_uk: "",
  category: "service",
  status: "draft",
  position: 0,
  all_positions: true,
  operational_role_ids: [],
  cover_asset_id: null,
};

function AcademyWorkspace({ org, loc, roles }: { org: string; loc: string; roles: Role[] }) {
  const { client, session } = useSession();
  const base = `/organizations/${org}/locations/${loc}/academy`;
  const [items, setItems] = useState<AcademyArticle[]>([]);
  const [offset, setOffset] = useState(0);
  const [next, setNext] = useState<number | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [selected, setSelected] = useState<AcademyArticle | null>(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<AcademyWrite>(empty);
  const [seedRoles, setSeedRoles] = useState({
    waiter_role_id: "",
    runner_role_id: "",
    bartender_role_id: "",
  });
  const retry = useRef<{ signature: string; key: string } | null>(null);
  useEffect(() => {
    let active = true;
    // Серверний знімок приховуємо до завершення нового запиту.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError("");
    client
      .request<AcademyCollection>(`${base}?offset=${offset}&limit=20`)
      .then((data) => {
        if (active) {
          setItems(data.items);
          setNext(data.next_offset);
        }
      })
      .catch(() => {
        if (active) setError("Не вдалося завантажити статті.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [client, base, offset, refresh]);
  const validAudience =
    form.all_positions ||
    (form.operational_role_ids.length > 0 &&
      form.operational_role_ids.every((id) =>
        roles.some((role) => role.id === id && role.status === "active"),
      ));
  const save = async () => {
    if (!session || busy || !validAudience) return;
    setBusy(true);
    setError("");
    setNotice("");
    const body = selected ? { ...form, expected_revision: selected.revision } : form;
    const signature = JSON.stringify(body);
    if (retry.current?.signature !== signature)
      retry.current = { signature, key: createIdempotencyKey() };
    try {
      await client.request(`${base}${selected ? `/${selected.id}` : ""}`, {
        method: selected ? "PATCH" : "POST",
        body,
        csrfToken: session.csrf_token,
        idempotencyKey: selected ? undefined : retry.current.key,
      });
      retry.current = null;
      setEditing(false);
      setSelected(null);
      setRefresh((value) => value + 1);
      setNotice("Статтю збережено.");
    } catch (caught) {
      setError(
        caught instanceof ApiError && caught.code === "REVISION_CONFLICT"
          ? "Статтю вже змінено. Оновіть список і відкрийте її знову; ваш текст залишено у формі."
          : "Не вдалося зберегти. Перевірте адресу, аудиторію та поля статті.",
      );
    } finally {
      setBusy(false);
    }
  };
  const seed = async () => {
    if (!session || busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await client.request<{ created_count: number }>(`${base}/seed`, {
        method: "POST",
        body: seedRoles,
        csrfToken: session.csrf_token,
      });
      setRefresh((value) => value + 1);
      setNotice(`Додано чернеток: ${result.created_count}. Перегляньте їх перед публікацією.`);
    } catch {
      setError("Не вдалося додати статті. Оберіть три різні активні посади.");
    } finally {
      setBusy(false);
    }
  };
  const upload = async (file: File) => {
    if (!session || busy) return;
    setBusy(true);
    setError("");
    try {
      const asset = await uploadPrivateImage(
        client,
        `/organizations/${org}/locations/${loc}/assets`,
        session.csrf_token,
        file,
      );
      setForm((value) => ({ ...value, cover_asset_id: asset.id }));
    } catch {
      setError("Обкладинка не завантажена або не пройшла перевірку.");
    } finally {
      setBusy(false);
    }
  };
  const edit = (article: AcademyArticle | null) => {
    setSelected(article);
    setEditing(true);
    setError("");
    setNotice("");
    retry.current = null;
    setForm(
      article
        ? (Object.fromEntries(
            Object.keys(empty).map((key) => [key, article[key as keyof AcademyWrite]]),
          ) as unknown as AcademyWrite)
        : { ...empty },
    );
  };
  return (
    <>
      <div className="compact-actions">
        <button className="button button-primary" disabled={busy} onClick={() => edit(null)}>
          Нова стаття
        </button>
        <button
          className="button button-secondary"
          disabled={busy}
          onClick={() => setRefresh((value) => value + 1)}
        >
          Оновити список
        </button>
      </div>
      {error ? <p role="alert">{error}</p> : null}
      {notice ? <p role="status">{notice}</p> : null}
      {editing ? (
        <form
          className="training-panel"
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
        >
          <h2>{selected ? "Редагування статті" : "Нова стаття"}</h2>
          <fieldset disabled={busy}>
            {(
              [
                ["title_uk", "Назва", 200],
                ["slug", "Адреса статті (slug)", 120],
                ["category", "Категорія", 64],
              ] as const
            ).map(([field, label, max]) => (
              <div className="field-group" key={field}>
                <label htmlFor={`academy-${field}`}>{label}</label>
                <input
                  id={`academy-${field}`}
                  value={form[field]}
                  maxLength={max}
                  required
                  pattern={
                    field === "slug"
                      ? "[a-z0-9]+(-[a-z0-9]+)*"
                      : field === "category"
                        ? "[a-z0-9_]+"
                        : undefined
                  }
                  onChange={(event) => setForm({ ...form, [field]: event.target.value })}
                />
              </div>
            ))}
            {(
              [
                ["summary_uk", "Короткий опис", 500, 3],
                ["body_uk", "Текст статті", 50000, 12],
              ] as const
            ).map(([field, label, max, rows]) => (
              <div className="field-group" key={field}>
                <label htmlFor={`academy-${field}`}>{label}</label>
                <textarea
                  id={`academy-${field}`}
                  value={form[field]}
                  maxLength={max}
                  rows={rows}
                  required
                  onChange={(event) => setForm({ ...form, [field]: event.target.value })}
                />
              </div>
            ))}
            <div className="field-group">
              <label htmlFor="academy-position">Порядок</label>
              <input
                id="academy-position"
                type="number"
                min="0"
                max="100000"
                required
                value={form.position}
                onChange={(event) => setForm({ ...form, position: Number(event.target.value) })}
              />
            </div>
            <label>
              <input
                type="checkbox"
                checked={form.all_positions}
                onChange={(event) =>
                  setForm({
                    ...form,
                    all_positions: event.target.checked,
                    operational_role_ids: [],
                  })
                }
              />{" "}
              Усі посади, включно з майбутніми
            </label>
            {!form.all_positions ? (
              <fieldset>
                <legend>Посади читачів</legend>
                {roles
                  .filter(
                    (role) =>
                      role.status === "active" || form.operational_role_ids.includes(role.id),
                  )
                  .map((role) => (
                    <label key={role.id} className="field-group">
                      <span>
                        <input
                          type="checkbox"
                          checked={form.operational_role_ids.includes(role.id)}
                          onChange={(event) =>
                            setForm({
                              ...form,
                              operational_role_ids: event.target.checked
                                ? [...form.operational_role_ids, role.id]
                                : form.operational_role_ids.filter((id) => id !== role.id),
                            })
                          }
                        />{" "}
                        {role.name_uk}
                        {role.status === "active" ? "" : " · неактивна посада"}
                      </span>
                    </label>
                  ))}
                {form.operational_role_ids
                  .filter((id) => !roles.some((role) => role.id === id))
                  .map((id) => (
                    <label key={id} className="field-group">
                      <span>
                        <input
                          type="checkbox"
                          checked
                          onChange={() =>
                            setForm({
                              ...form,
                              operational_role_ids: form.operational_role_ids.filter(
                                (value) => value !== id,
                              ),
                            })
                          }
                        />{" "}
                        Недоступна посада
                      </span>
                    </label>
                  ))}
              </fieldset>
            ) : null}
            <div className="field-group">
              <label htmlFor="academy-cover">Обкладинка (JPEG, PNG, WebP до 5 МБ)</label>
              <input
                id="academy-cover"
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void upload(file);
                }}
              />
            </div>
            {form.cover_asset_id ? (
              <p>
                Обкладинка додана.{" "}
                <button type="button" onClick={() => setForm({ ...form, cover_asset_id: null })}>
                  Прибрати обкладинку
                </button>
              </p>
            ) : null}
            <div className="field-group">
              <label htmlFor="academy-status">Публікація</label>
              <select
                id="academy-status"
                value={form.status}
                onChange={(event) =>
                  setForm({ ...form, status: event.target.value as AcademyWrite["status"] })
                }
              >
                <option value="draft">Чернетка</option>
                <option value="published">Опубліковано</option>
              </select>
            </div>
            <p>
              Перевірте текст та аудиторію перед публікацією. Статті не є обов’язковим навчанням.
            </p>
            <div className="compact-actions">
              <button className="button button-primary" disabled={!validAudience}>
                Зберегти статтю
              </button>
              <button
                className="button button-secondary"
                type="button"
                onClick={() => setEditing(false)}
              >
                Закрити форму
              </button>
            </div>
          </fieldset>
        </form>
      ) : null}
      <details className="training-panel">
        <summary>13 стартових статей</summary>
        <p>
          Загальні поради: 4 для всіх і по 3 для офіціанта, Runner та Bartender. Додаються як
          чернетки. Наявні статті не перезаписуються.
        </p>
        {(Object.keys(seedRoles) as Array<keyof typeof seedRoles>).map((field, index) => (
          <div className="field-group" key={field}>
            <label htmlFor={field}>{["Офіціант", "Runner", "Bartender"][index]}</label>
            <select
              id={field}
              value={seedRoles[field]}
              disabled={busy}
              onChange={(event) => setSeedRoles({ ...seedRoles, [field]: event.target.value })}
            >
              <option value="">Оберіть посаду</option>
              {roles
                .filter((role) => role.status === "active")
                .map((role) => (
                  <option value={role.id} key={role.id}>
                    {role.name_uk}
                  </option>
                ))}
            </select>
          </div>
        ))}
        <button
          className="button button-secondary"
          disabled={
            busy ||
            Object.values(seedRoles).some((value) => !value) ||
            new Set(Object.values(seedRoles)).size !== 3
          }
          onClick={() => void seed()}
        >
          Додати 13 чернеток
        </button>
      </details>
      {loading ? (
        <p role="status">Завантаження…</p>
      ) : items.length ? (
        items.map((item) => (
          <article className="training-panel" key={item.id}>
            <h2>{item.title_uk}</h2>
            <p>{item.summary_uk}</p>
            <p>
              {item.status === "published" ? "Опубліковано" : "Чернетка"} ·{" "}
              {item.all_positions ? "Усі посади" : "Вибрані посади"}
            </p>
            <button className="button button-secondary" disabled={busy} onClick={() => edit(item)}>
              Редагувати {item.title_uk}
            </button>
          </article>
        ))
      ) : (
        <p>Статей ще немає.</p>
      )}
      <div className="compact-actions">
        {offset > 0 ? (
          <button disabled={busy || loading} onClick={() => setOffset(Math.max(0, offset - 20))}>
            Попередні статті
          </button>
        ) : null}
        {next !== null ? (
          <button disabled={busy || loading} onClick={() => setOffset(next)}>
            Наступні статті
          </button>
        ) : null}
      </div>
    </>
  );
}

export function AdminAcademyPage() {
  const { client, session } = useSession();
  const org = session?.organization_access.find(
    (access) => access.is_organization_admin,
  )?.organization_id;
  const [locations, setLocations] = useState<LocationSummary[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loc, setLoc] = useState("");
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!org) return;
    let active = true;
    // Зміна організації не повинна залишати попередню локацію у формі.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLocations([]);
    setLoc("");
    setError(false);
    Promise.all([
      client.request<LocationSummary[]>(`/organizations/${org}/locations`),
      client.request<Role[]>(`/organizations/${org}/operational-roles`),
    ])
      .then(([places, positions]) => {
        if (!active) return;
        setLocations(places);
        setLoc(places[0]?.id ?? "");
        setRoles(positions);
      })
      .catch(() => {
        if (active) setError(true);
      });
    return () => {
      active = false;
    };
  }, [client, org, retry]);
  return (
    <section className="content-section academy-page">
      <h1>Академія</h1>
      <p>Додаткові статті для працівників за посадами.</p>
      {error ? (
        <div role="alert">
          <p>Не вдалося завантажити локації та посади.</p>
          <button onClick={() => setRetry((value) => value + 1)}>Спробувати ще раз</button>
        </div>
      ) : null}
      <div className="field-group">
        <label htmlFor="academy-location">Локація</label>
        <select id="academy-location" value={loc} onChange={(event) => setLoc(event.target.value)}>
          {locations.map((place) => (
            <option key={place.id} value={place.id}>
              {place.name}
            </option>
          ))}
        </select>
      </div>
      {org && loc ? (
        <AcademyWorkspace key={`${org}-${loc}`} org={org} loc={loc} roles={roles} />
      ) : null}
    </section>
  );
}

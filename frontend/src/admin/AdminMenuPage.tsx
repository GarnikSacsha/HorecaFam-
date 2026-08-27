import { useCallback, useEffect, useState } from "react";

import { createIdempotencyKey } from "../api/client";
import type {
  LocationSummary,
  MenuItemListResponse,
  MenuItemResponse,
  MenuVersionCollection,
  MenuVersionDetail,
} from "../api/contracts";
import { LogoutButton } from "../auth/LogoutButton";
import { useSession } from "../session/SessionContext";
import { StatusPill } from "../ui/States";

function formatPrice(value: number | null): string {
  return value === null ? "—" : `${(value / 100).toFixed(2)} ₴`;
}

function MenuItemEditor({
  item,
  busy,
  onSave,
}: {
  item: MenuItemResponse;
  busy: boolean;
  onSave: (item: MenuItemResponse, name: string, priceMinor: number | null) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(item.name_uk);
  const [price, setPrice] = useState(
    item.price_minor === null ? "" : String(item.price_minor / 100),
  );
  return (
    <article className="menu-item-card">
      {editing ? (
        <form
          className="menu-inline-editor"
          onSubmit={(event) => {
            event.preventDefault();
            const normalized = price.trim() ? Math.round(Number(price) * 100) : null;
            void onSave(item, name, Number.isFinite(normalized) ? normalized : null).then(() =>
              setEditing(false),
            );
          }}
        >
          <div className="field-group">
            <label htmlFor={`item-name-${item.item_id}`}>Назва</label>
            <input
              id={`item-name-${item.item_id}`}
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
            />
          </div>
          <div className="field-group">
            <label htmlFor={`item-price-${item.item_id}`}>Ціна, ₴</label>
            <input
              id={`item-price-${item.item_id}`}
              type="number"
              min="0"
              step="0.01"
              value={price}
              onChange={(event) => setPrice(event.target.value)}
            />
          </div>
          <div className="compact-actions">
            <button className="button button-primary" type="submit" disabled={busy}>
              Зберегти
            </button>
            <button className="button button-quiet" type="button" onClick={() => setEditing(false)}>
              Скасувати
            </button>
          </div>
        </form>
      ) : (
        <>
          <div>
            <strong>{item.name_uk}</strong>
            <p>{item.description_uk || "Опис ще не додано"}</p>
          </div>
          <div className="menu-item-meta">
            <span>{formatPrice(item.price_minor)}</span>
            <StatusPill tone={item.training_impact === "required" ? "warning" : "neutral"}>
              {item.delta_kind === "added"
                ? "Нова"
                : item.delta_kind === "changed"
                  ? "Змінена"
                  : "Без змін"}
            </StatusPill>
            <button className="button button-quiet" type="button" onClick={() => setEditing(true)}>
              Редагувати
            </button>
          </div>
        </>
      )}
    </article>
  );
}

export function AdminMenuPage() {
  const { client, session, status } = useSession();
  const organizationId = session?.organization_access.find(
    (access) => access.is_organization_admin,
  )?.organization_id;
  const [locations, setLocations] = useState<LocationSummary[]>([]);
  const [locationId, setLocationId] = useState("");
  const [versions, setVersions] = useState<MenuVersionCollection | null>(null);
  const [draft, setDraft] = useState<MenuVersionDetail | null>(null);
  const [items, setItems] = useState<MenuItemResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sectionName, setSectionName] = useState("");
  const [categoryName, setCategoryName] = useState("");
  const [categorySectionId, setCategorySectionId] = useState("");
  const [itemName, setItemName] = useState("");
  const [itemCategoryId, setItemCategoryId] = useState("");
  const [itemPrice, setItemPrice] = useState("");

  const refreshDraft = useCallback(
    async (selectedLocationId: string, versionId: string) => {
      if (!organizationId) return;
      const base = `/organizations/${organizationId}/locations/${selectedLocationId}/menu-versions/${versionId}`;
      const [detail, itemList] = await Promise.all([
        client.request<MenuVersionDetail>(base),
        client.request<MenuItemListResponse>(`${base}/items?limit=100`),
      ]);
      setDraft(detail);
      setItems(itemList.items);
    },
    [client, organizationId],
  );

  const loadWorkspace = useCallback(
    async (selectedLocationId: string) => {
      if (!organizationId || !selectedLocationId) return;
      setLoading(true);
      setError(null);
      try {
        const collection = await client.request<MenuVersionCollection>(
          `/organizations/${organizationId}/locations/${selectedLocationId}/menu-versions`,
        );
        setVersions(collection);
        if (collection.draft) await refreshDraft(selectedLocationId, collection.draft.id);
        else {
          setDraft(null);
          setItems([]);
        }
      } catch {
        setError("Не вдалося завантажити меню локації.");
      } finally {
        setLoading(false);
      }
    },
    [client, organizationId, refreshDraft],
  );

  useEffect(() => {
    if (status !== "authenticated" || !organizationId) return;
    let active = true;
    client
      .request<LocationSummary[]>(`/organizations/${organizationId}/locations`)
      .then((response) => {
        if (!active) return;
        const available = response.filter((location) => location.status === "active");
        setLocations(available);
        const first = available[0]?.id ?? "";
        setLocationId(first);
        if (first) void loadWorkspace(first);
        else setLoading(false);
      })
      .catch(() => {
        if (active) {
          setError("Не вдалося завантажити локації.");
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [client, loadWorkspace, organizationId, status]);

  const mutate = async (action: () => Promise<unknown>) => {
    if (!draft || !locationId) return;
    setBusy(true);
    setError(null);
    try {
      await action();
      await refreshDraft(locationId, draft.id);
    } catch {
      setError("Зміни не збережено. Оновіть сторінку та повторіть дію.");
    } finally {
      setBusy(false);
    }
  };

  const createDraft = async () => {
    if (!organizationId || !locationId || !session) return;
    setBusy(true);
    try {
      const created = await client.request<MenuVersionDetail>(
        `/organizations/${organizationId}/locations/${locationId}/menu-versions`,
        {
          method: "POST",
          body: { copy_from_version_id: null },
          csrfToken: session.csrf_token,
          idempotencyKey: createIdempotencyKey(),
        },
      );
      setDraft(created);
      setItems([]);
      await loadWorkspace(locationId);
    } catch {
      setError("Не вдалося створити чернетку меню.");
    } finally {
      setBusy(false);
    }
  };

  const basePath =
    organizationId && locationId && draft
      ? `/organizations/${organizationId}/locations/${locationId}/menu-versions/${draft.id}`
      : "";
  const itemByCategory = (categoryId: string) =>
    items.filter((item) => item.category_id === categoryId).sort((a, b) => a.position - b.position);

  return (
    <section className="admin-page menu-workspace" aria-labelledby="menu-title">
      <div className="page-heading-row">
        <div>
          <p className="eyebrow">Джерело правди</p>
          <h1 id="menu-title">Меню</h1>
          <p className="page-description">
            Редагуйте чернетку окремо від меню, яке зараз бачить команда.
          </p>
        </div>
        <LogoutButton />
      </div>
      <div className="menu-toolbar">
        <div className="field-group">
          <label htmlFor="menu-location">Локація</label>
          <select
            id="menu-location"
            value={locationId}
            onChange={(event) => {
              setLocationId(event.target.value);
              void loadWorkspace(event.target.value);
            }}
          >
            {locations.map((location) => (
              <option key={location.id} value={location.id}>
                {location.name}
              </option>
            ))}
          </select>
        </div>
        {versions?.current_published ? (
          <StatusPill tone="success">
            Опубліковано v{versions.current_published.version_number}
          </StatusPill>
        ) : (
          <StatusPill>Ще не опубліковано</StatusPill>
        )}
        {draft ? <StatusPill tone="warning">Чернетка v{draft.version_number}</StatusPill> : null}
      </div>
      {error ? (
        <p className="inline-error" role="alert">
          {error}
        </p>
      ) : null}
      {loading ? (
        <p aria-live="polite">Завантажуємо меню…</p>
      ) : !draft ? (
        <div className="empty-state">
          <h2>Чернетки немає</h2>
          <p>Створіть її з поточної опублікованої версії або почніть перше меню.</p>
          <button
            className="button button-primary"
            type="button"
            onClick={() => void createDraft()}
          >
            Створити чернетку
          </button>
        </div>
      ) : (
        <div className="menu-editor-grid">
          <aside className="menu-outline" aria-label="Структура меню">
            <p className="eyebrow">Структура</p>
            <ol>
              {draft.sections.map((section) => (
                <li key={section.id}>
                  <a href={`#section-${section.id}`}>{section.name_uk}</a>
                  <span>{section.category_count}</span>
                </li>
              ))}
            </ol>
          </aside>
          <div className="menu-editor">
            <div className="menu-editor-heading">
              <div>
                <p className="eyebrow">Чернетка · ревізія {draft.revision}</p>
                <h2>Розділи та позиції</h2>
              </div>
              <details className="menu-add-panel">
                <summary className="button button-primary">Додати</summary>
                <div className="menu-add-forms">
                  <form
                    onSubmit={(event) => {
                      event.preventDefault();
                      if (!session) return;
                      void mutate(() =>
                        client.request(`${basePath}/sections`, {
                          method: "POST",
                          csrfToken: session.csrf_token,
                          body: {
                            name_uk: sectionName,
                            stable_code: null,
                            position: draft.sections.length,
                            expected_revision: draft.revision,
                          },
                        }),
                      ).then(() => setSectionName(""));
                    }}
                  >
                    <div className="field-group">
                      <label htmlFor="new-section">Новий розділ</label>
                      <input
                        id="new-section"
                        value={sectionName}
                        onChange={(event) => setSectionName(event.target.value)}
                        required
                      />
                    </div>
                    <button className="button button-quiet" type="submit" disabled={busy}>
                      Додати розділ
                    </button>
                  </form>
                  <form
                    onSubmit={(event) => {
                      event.preventDefault();
                      if (!session) return;
                      const section = draft.sections.find(({ id }) => id === categorySectionId);
                      if (!section) return;
                      void mutate(() =>
                        client.request(`${basePath}/categories`, {
                          method: "POST",
                          csrfToken: session.csrf_token,
                          body: {
                            section_id: section.id,
                            name_uk: categoryName,
                            stable_code: null,
                            position: section.categories.length,
                            expected_revision: draft.revision,
                          },
                        }),
                      ).then(() => setCategoryName(""));
                    }}
                  >
                    <div className="field-group">
                      <label htmlFor="category-section">Розділ категорії</label>
                      <select
                        id="category-section"
                        value={categorySectionId}
                        onChange={(event) => setCategorySectionId(event.target.value)}
                        required
                      >
                        <option value="">Оберіть розділ</option>
                        {draft.sections.map((section) => (
                          <option key={section.id} value={section.id}>
                            {section.name_uk}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="field-group">
                      <label htmlFor="new-category">Нова категорія</label>
                      <input
                        id="new-category"
                        value={categoryName}
                        onChange={(event) => setCategoryName(event.target.value)}
                        required
                      />
                    </div>
                    <button className="button button-quiet" type="submit" disabled={busy}>
                      Додати категорію
                    </button>
                  </form>
                  <form
                    onSubmit={(event) => {
                      event.preventDefault();
                      if (!session) return;
                      const count = itemByCategory(itemCategoryId).length;
                      void mutate(() =>
                        client.request(`${basePath}/items`, {
                          method: "POST",
                          csrfToken: session.csrf_token,
                          body: {
                            expected_revision: draft.revision,
                            category_id: itemCategoryId,
                            stable_code: null,
                            name_uk: itemName,
                            description_uk: null,
                            price_minor: itemPrice ? Math.round(Number(itemPrice) * 100) : null,
                            currency: "UAH",
                            availability: "available",
                            position: count,
                            component_data_status: "confirmed_none",
                            components: [],
                            allergen_data_status: "confirmed_none",
                            allergen_codes: [],
                            source_kind: "manual",
                            source_reference: null,
                            source_item_key: null,
                          },
                        }),
                      ).then(() => {
                        setItemName("");
                        setItemPrice("");
                      });
                    }}
                  >
                    <div className="field-group">
                      <label htmlFor="item-category">Категорія позиції</label>
                      <select
                        id="item-category"
                        value={itemCategoryId}
                        onChange={(event) => setItemCategoryId(event.target.value)}
                        required
                      >
                        <option value="">Оберіть категорію</option>
                        {draft.sections.flatMap((section) =>
                          section.categories.map((category) => (
                            <option key={category.id} value={category.id}>
                              {section.name_uk} · {category.name_uk}
                            </option>
                          )),
                        )}
                      </select>
                    </div>
                    <div className="field-group">
                      <label htmlFor="new-item">Нова позиція</label>
                      <input
                        id="new-item"
                        value={itemName}
                        onChange={(event) => setItemName(event.target.value)}
                        required
                      />
                    </div>
                    <div className="field-group">
                      <label htmlFor="new-item-price">Ціна, ₴</label>
                      <input
                        id="new-item-price"
                        type="number"
                        min="0"
                        step="0.01"
                        value={itemPrice}
                        onChange={(event) => setItemPrice(event.target.value)}
                      />
                    </div>
                    <button className="button button-quiet" type="submit" disabled={busy}>
                      Додати позицію
                    </button>
                  </form>
                </div>
              </details>
            </div>
            {draft.sections.length === 0 ? (
              <div className="empty-state">
                <h3>Додайте перший розділ</h3>
                <p>Після нього можна створити категорію та позиції меню.</p>
              </div>
            ) : (
              draft.sections.map((section, sectionIndex) => (
                <section
                  className="menu-section-block"
                  id={`section-${section.id}`}
                  key={section.id}
                  aria-labelledby={`section-title-${section.id}`}
                >
                  <div className="menu-entity-heading">
                    <h3 id={`section-title-${section.id}`}>{section.name_uk}</h3>
                    <div
                      className="compact-actions"
                      aria-label={`Порядок розділу ${section.name_uk}`}
                    >
                      <button
                        className="button button-quiet"
                        type="button"
                        disabled={busy || sectionIndex === 0}
                        aria-label={`Перемістити ${section.name_uk} вище`}
                        onClick={() => {
                          if (!session) return;
                          const ordered = draft.sections.map(({ id }) => id);
                          [ordered[sectionIndex - 1], ordered[sectionIndex]] = [
                            ordered[sectionIndex],
                            ordered[sectionIndex - 1],
                          ];
                          void mutate(() =>
                            client.request(`${basePath}/sections/reorder`, {
                              method: "POST",
                              csrfToken: session.csrf_token,
                              body: { ordered_ids: ordered, expected_revision: draft.revision },
                            }),
                          );
                        }}
                      >
                        Вище
                      </button>
                      <button
                        className="button button-quiet"
                        type="button"
                        disabled={busy || sectionIndex === draft.sections.length - 1}
                        aria-label={`Перемістити ${section.name_uk} нижче`}
                        onClick={() => {
                          if (!session) return;
                          const ordered = draft.sections.map(({ id }) => id);
                          [ordered[sectionIndex], ordered[sectionIndex + 1]] = [
                            ordered[sectionIndex + 1],
                            ordered[sectionIndex],
                          ];
                          void mutate(() =>
                            client.request(`${basePath}/sections/reorder`, {
                              method: "POST",
                              csrfToken: session.csrf_token,
                              body: { ordered_ids: ordered, expected_revision: draft.revision },
                            }),
                          );
                        }}
                      >
                        Нижче
                      </button>
                    </div>
                  </div>
                  {section.categories.map((category) => (
                    <div className="menu-category-block" key={category.id}>
                      <h4>{category.name_uk}</h4>
                      <div className="menu-item-list">
                        {itemByCategory(category.id).map((item) => (
                          <MenuItemEditor
                            key={item.item_id}
                            item={item}
                            busy={busy}
                            onSave={(current, name, priceMinor) =>
                              mutate(() =>
                                client.request(`${basePath}/items/${current.item_id}`, {
                                  method: "PATCH",
                                  csrfToken: session?.csrf_token,
                                  body: {
                                    expected_revision: draft.revision,
                                    name_uk: name,
                                    price_minor: priceMinor,
                                  },
                                }),
                              )
                            }
                          />
                        ))}
                        {category.item_count === 0 ? (
                          <p className="menu-quiet-row">У категорії ще немає позицій.</p>
                        ) : null}
                      </div>
                    </div>
                  ))}
                  {section.category_count === 0 ? (
                    <p className="menu-quiet-row">У розділі ще немає категорій.</p>
                  ) : null}
                </section>
              ))
            )}
          </div>
        </div>
      )}
    </section>
  );
}

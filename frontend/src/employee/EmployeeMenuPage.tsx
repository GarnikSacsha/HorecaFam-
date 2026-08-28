import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import type {
  EmployeeMenuItemDetail,
  EmployeeMenuItemSummary,
  EmployeeMenuResponse,
  MenuAvailability,
} from "../api/contracts";
import { LogoutButton } from "../auth/LogoutButton";
import { useSession } from "../session/SessionContext";

const availabilityCopy: Record<MenuAvailability, string> = {
  available: "Доступно",
  temporarily_unavailable: "Тимчасово недоступно",
  seasonal: "Сезонна позиція",
  discontinued: "Знято з меню",
};

function formatPrice(item: EmployeeMenuItemSummary): string {
  if (item.price_minor === null) return "Ціну уточнюйте";
  return new Intl.NumberFormat(item.content_locale === "en" ? "en-US" : "uk-UA", {
    style: "currency",
    currency: item.currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(item.price_minor / 100);
}

function MenuDetail({
  item,
  loading,
  onClose,
}: {
  item: EmployeeMenuItemDetail | null;
  loading: boolean;
  onClose: () => void;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
      if (event.key !== "Tab") return;
      const focusable = panelRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div className="menu-detail-layer">
      <button
        className="menu-detail-backdrop"
        type="button"
        tabIndex={-1}
        aria-label="Закрити деталі позиції"
        onClick={onClose}
      />
      <div
        className="menu-detail-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="menu-detail-title"
        ref={panelRef}
      >
        <div className="menu-detail-heading">
          <div>
            <p className="eyebrow">Позиція меню</p>
            <h2 id="menu-detail-title">{item?.name ?? "Завантажуємо…"}</h2>
            {item ? <p>{item.category_name}</p> : null}
          </div>
          <button className="button button-quiet" type="button" onClick={onClose} ref={closeRef}>
            Закрити
          </button>
        </div>
        {loading ? <p aria-live="polite">Завантажуємо деталі…</p> : null}
        {item ? (
          <>
            <p className="menu-detail-price">{formatPrice(item)}</p>
            <p>{item.description ?? "Опис для цієї позиції не додано."}</p>
            <div className="menu-detail-facts">
              <section>
                <h3>Склад</h3>
                {item.components.length ? (
                  <ul>
                    {item.components.map((component) => (
                      <li key={`${component.position}-${component.name}`}>
                        {component.name}
                        {component.optional ? " (за бажанням)" : ""}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p>Компоненти не вказані.</p>
                )}
              </section>
              <section>
                <h3>Алергени</h3>
                {item.allergen_data_status === "unknown" ? (
                  <p>Інформацію про алергени ще не підтверджено.</p>
                ) : item.allergens.length ? (
                  <ul>
                    {item.allergens.map((allergen) => (
                      <li key={allergen.code}>{allergen.label}</li>
                    ))}
                  </ul>
                ) : (
                  <p>Підтверджених алергенів немає.</p>
                )}
              </section>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}

export function EmployeeMenuPage() {
  const { client } = useSession();
  const [searchParams] = useSearchParams();
  const [response, setResponse] = useState<EmployeeMenuResponse | null>(null);
  const [queryInput, setQueryInput] = useState("");
  const [query, setQuery] = useState("");
  const [sectionId, setSectionId] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [selected, setSelected] = useState<EmployeeMenuItemDetail | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const linkedItemOpenedRef = useRef(false);

  const loadMenu = useCallback(async () => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({ limit: "50" });
    if (query) params.set("q", query);
    if (sectionId) params.set("section_id", sectionId);
    if (categoryId) params.set("category_id", categoryId);
    try {
      setResponse(await client.request<EmployeeMenuResponse>(`/me/menu?${params}`));
    } catch {
      setError("Не вдалося завантажити меню. Спробуйте ще раз.");
    } finally {
      setLoading(false);
    }
  }, [categoryId, client, query, sectionId]);

  useEffect(() => {
    // Menu results are a server snapshot and state changes only after its response.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadMenu();
  }, [loadMenu]);

  const closeDetail = useCallback(() => {
    setDetailOpen(false);
    setSelected(null);
    window.requestAnimationFrame(() => returnFocusRef.current?.focus());
  }, []);

  const openDetail = useCallback(
    async (itemId: string) => {
      returnFocusRef.current = document.activeElement as HTMLElement | null;
      setDetailOpen(true);
      setDetailLoading(true);
      setSelected(null);
      try {
        setSelected(await client.request<EmployeeMenuItemDetail>(`/me/menu/items/${itemId}`));
      } catch {
        setError("Не вдалося завантажити деталі позиції.");
        setDetailOpen(false);
      } finally {
        setDetailLoading(false);
      }
    },
    [client],
  );

  useEffect(() => {
    const linkedItemId = searchParams.get("item");
    if (!linkedItemId || linkedItemOpenedRef.current) return;
    linkedItemOpenedRef.current = true;
    void openDetail(linkedItemId);
  }, [openDetail, searchParams]);

  const sections = response?.menu?.sections ?? [];
  const categories = sectionId
    ? (sections.find((section) => section.id === sectionId)?.categories ?? [])
    : sections.flatMap((section) => section.categories);

  return (
    <section className="employee-menu-page" aria-labelledby="employee-menu-title">
      <div className="employee-menu-heading">
        <div>
          <p className="eyebrow">Робочий довідник</p>
          <h1 id="employee-menu-title">Меню</h1>
          {response?.menu ? (
            <p className="menu-version-note">Опублікована версія {response.menu.version_number}</p>
          ) : null}
        </div>
        <LogoutButton />
      </div>

      <form
        className="employee-menu-search"
        role="search"
        onSubmit={(event) => {
          event.preventDefault();
          setQuery(queryInput.trim());
        }}
      >
        <label className="sr-only" htmlFor="employee-menu-search">
          Пошук у меню
        </label>
        <input
          id="employee-menu-search"
          type="search"
          placeholder="Назва або опис"
          value={queryInput}
          onChange={(event) => setQueryInput(event.target.value)}
        />
        <button className="button button-primary" type="submit">
          Знайти
        </button>
      </form>

      {response?.menu && sections.length ? (
        <div className="employee-menu-filters" aria-label="Фільтри меню">
          <label>
            Розділ
            <select
              value={sectionId}
              onChange={(event) => {
                setSectionId(event.target.value);
                setCategoryId("");
              }}
            >
              <option value="">Усі розділи</option>
              {sections.map((section) => (
                <option key={section.id} value={section.id}>
                  {section.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Категорія
            <select value={categoryId} onChange={(event) => setCategoryId(event.target.value)}>
              <option value="">Усі категорії</option>
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      ) : null}

      {error ? (
        <div className="inline-error" role="alert">
          <p>{error}</p>
          <button className="button button-quiet" type="button" onClick={() => void loadMenu()}>
            Повторити
          </button>
        </div>
      ) : null}
      {loading ? <p aria-live="polite">Завантажуємо меню…</p> : null}
      {!loading && response && !response.menu ? (
        <div className="empty-state">
          <h2>Меню ще не опубліковано</h2>
          <p>Коли адміністратор опублікує меню вашої локації, воно з’явиться тут.</p>
        </div>
      ) : null}
      {!loading && response?.menu && response.items.length === 0 ? (
        <div className="empty-state">
          <h2>Позицій не знайдено</h2>
          <p>Змініть пошук або фільтри й спробуйте ще раз.</p>
        </div>
      ) : null}
      {response?.items.length ? (
        <div className="employee-menu-results" aria-label="Позиції меню">
          {response.items.map((item) => (
            <button
              className="employee-menu-item"
              type="button"
              key={item.item_id}
              onClick={() => void openDetail(item.item_id)}
            >
              <span>
                <strong>{item.name}</strong>
                <small>
                  {item.section_name} · {item.category_name} · {availabilityCopy[item.availability]}
                </small>
                {item.description_excerpt ? <p>{item.description_excerpt}</p> : null}
                {item.translation_fallback ? (
                  <span className="menu-fallback-note">Показано українською</span>
                ) : null}
              </span>
              <span className="employee-menu-price">{formatPrice(item)}</span>
            </button>
          ))}
        </div>
      ) : null}
      {detailOpen ? (
        <MenuDetail item={selected} loading={detailLoading} onClose={closeDetail} />
      ) : null}
    </section>
  );
}

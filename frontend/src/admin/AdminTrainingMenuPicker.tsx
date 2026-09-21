import { useEffect, useRef, useState } from "react";
import type { ApiClient } from "../api/client";
import type { MenuItemListResponse, MenuItemResponse, MenuVersionDetail } from "../api/contracts";

export function AdminTrainingMenuPicker({
  client,
  base,
  value,
  disabled,
  onChange,
}: {
  client: ApiClient;
  base: string;
  value: string;
  disabled: boolean;
  onChange: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [items, setItems] = useState<MenuItemResponse[]>([]);
  const [menu, setMenu] = useState<MenuVersionDetail | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  const generation = useRef(0);
  const pending = useRef(false);
  useEffect(() => {
    const timer = setTimeout(() => setSearch(query.trim()), 250);
    return () => clearTimeout(timer);
  }, [query]);
  useEffect(() => {
    const current = ++generation.current;
    let active = true;
    const params = new URLSearchParams({ limit: "50" });
    if (search) params.set("q", search);
    void Promise.resolve().then(() => {
      if (!active) return;
      setLoading(true);
      setError(false);
      setItems([]);
      setCursor(null);
      setMenu(null);
      pending.current = true;
    });
    void Promise.all([
      client.request<MenuVersionDetail>(base),
      client.request<MenuItemListResponse>(`${base}/items?${params}`),
    ])
      .then(([detail, page]) => {
        if (!active || current !== generation.current) return;
        if (detail.revision !== page.revision) throw new Error("Menu revision changed");
        setMenu(detail);
        setItems(page.items);
        setCursor(page.next_cursor);
      })
      .catch(() => {
        if (active && current === generation.current) setError(true);
      })
      .finally(() => {
        if (active && current === generation.current) {
          setLoading(false);
          pending.current = false;
        }
      });
    return () => {
      active = false;
      generation.current = current + 1;
    };
  }, [base, client, search, retry]);
  const more = async () => {
    if (!cursor || !menu || pending.current) return;
    const current = generation.current;
    pending.current = true;
    setLoading(true);
    setError(false);
    const params = new URLSearchParams({ limit: "50", cursor });
    if (search) params.set("q", search);
    try {
      const page = await client.request<MenuItemListResponse>(`${base}/items?${params}`);
      if (current !== generation.current) return;
      if (page.revision !== menu.revision || page.next_cursor === cursor)
        throw new Error("Menu page changed");
      setItems((previous) => [
        ...new Map([...previous, ...page.items].map((item) => [item.item_id, item])).values(),
      ]);
      setCursor(page.next_cursor);
    } catch {
      if (current === generation.current) setError(true);
    } finally {
      if (current === generation.current) {
        pending.current = false;
        setLoading(false);
      }
    }
  };
  const categories = new Map(
    menu?.sections.flatMap((section) =>
      section.categories.map(
        (category) => [category.id, `${section.name_uk} / ${category.name_uk}`] as const,
      ),
    ),
  );
  return (
    <div className="field-group training-grow" aria-busy={loading}>
      <label htmlFor="menu-card-search">Знайти позицію меню</label>
      <input
        id="menu-card-search"
        type="search"
        maxLength={200}
        value={query}
        disabled={disabled}
        onChange={(event) => {
          setQuery(event.target.value);
          onChange("");
        }}
      />
      <label htmlFor="menu-card-choice">Позиція меню</label>
      <select
        id="menu-card-choice"
        required
        value={value}
        disabled={disabled || loading || query.trim() !== search || error}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">Оберіть позицію</option>
        {items.map((item) => (
          <option key={item.item_id} value={item.item_id}>
            {item.name_uk} — {categories.get(item.category_id) ?? "Категорія"} ·{" "}
            {item.source_item_key ?? item.stable_code ?? item.item_id}
          </option>
        ))}
      </select>
      {loading && <p role="status">Завантажуємо позиції…</p>}
      {!loading && !error && items.length === 0 && (
        <p role="status">Позицій не знайдено. Спробуйте коротшу назву або очистіть пошук.</p>
      )}
      {error && (
        <div role="alert">
          Не вдалося завантажити позиції.{" "}
          <button
            type="button"
            disabled={disabled || loading}
            onClick={() => {
              onChange("");
              setRetry((n) => n + 1);
            }}
          >
            Повторити пошук
          </button>
        </div>
      )}
      {cursor && (
        <button
          className="button button-secondary"
          type="button"
          disabled={disabled || loading || error || query.trim() !== search}
          onClick={() => void more()}
        >
          Показати ще позиції
        </button>
      )}
    </div>
  );
}

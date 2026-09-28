import { useEffect, useState } from "react";
import type { ApiClient } from "../api/client";
import type { MenuItemListResponse, MenuItemResponse } from "../api/contracts";

export function useTrainingMenuItems(client: ApiClient, base: string | null) {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<{
    base: string;
    attempt: number;
    items: Map<string, MenuItemResponse>;
    error: boolean;
  } | null>(null);
  useEffect(() => {
    if (!base) return;
    let active = true;
    const read = async () => {
      const items = new Map<string, MenuItemResponse>();
      const cursors = new Set<string>();
      let cursor: string | null = null;
      let revision: number | undefined;
      do {
        const params = new URLSearchParams({ limit: "100" });
        if (cursor) params.set("cursor", cursor);
        const page = await client.request<MenuItemListResponse>(`${base}/items?${params}`);
        if (!active) return;
        if (revision !== undefined && revision !== page.revision)
          throw new Error("Menu revision changed");
        revision = page.revision;
        for (const item of page.items) items.set(item.item_id, item);
        cursor = page.next_cursor;
        if (cursor) {
          if (cursors.has(cursor)) throw new Error("Menu cursor repeated");
          cursors.add(cursor);
        }
      } while (cursor);
      if (active) setResult({ base, attempt, items, error: false });
    };
    void read().catch(() => {
      if (active) setResult({ base, attempt, items: new Map(), error: true });
    });
    return () => {
      active = false;
    };
  }, [client, base, attempt]);
  const current = result?.base === base && result?.attempt === attempt ? result : null;
  return {
    items: current?.items ?? new Map<string, MenuItemResponse>(),
    loading: Boolean(base && !current),
    error: current?.error ?? false,
    retry: () => setAttempt((value) => value + 1),
  };
}

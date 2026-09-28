import { act, renderHook, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import type { ApiClient } from "../api/client";
import { useTrainingMenuItems } from "./useTrainingMenuItems";

function clientFor(read: (path: string) => unknown): ApiClient {
  return {
    request: <T,>(path: string) => Promise.resolve().then(() => read(path)) as Promise<T>,
    getSession: vi.fn(),
  };
}
const page = (id: string, cursor: string | null = null, revision = 1) => ({
  items: [{ item_id: id, name_uk: id }],
  next_cursor: cursor,
  revision,
});

it("resolves cards on later pages using opaque cursors", async () => {
  const paths: string[] = [];
  const client = clientFor((path) => {
    paths.push(path);
    return path.includes("cursor=") ? page("second") : page("first", "opaque/+?");
  });
  const { result } = renderHook(() => useTrainingMenuItems(client, "/bound"));
  await waitFor(() => expect(result.current.loading).toBe(false));
  expect([...result.current.items.keys()]).toEqual(["first", "second"]);
  expect(paths).toEqual([
    "/bound/items?limit=100",
    "/bound/items?limit=100&cursor=opaque%2F%2B%3F",
  ]);
});

it.each(["revision", "cursor", "network"])(
  "rejects partial labels after %s failure and retries",
  async (failure) => {
    let fail = true;
    const client = clientFor((path) => {
      if (!fail) return page("recovered");
      if (!path.includes("cursor=")) return page("partial", "next");
      if (failure === "network") throw new Error("offline");
      return page("unsafe", failure === "cursor" ? "next" : null, failure === "revision" ? 2 : 1);
    });
    const { result } = renderHook(() => useTrainingMenuItems(client, "/bound"));
    await waitFor(() => expect(result.current.error).toBe(true));
    expect(result.current.items.size).toBe(0);
    fail = false;
    act(() => result.current.retry());
    await waitFor(() => expect(result.current.items.has("recovered")).toBe(true));
    expect(result.current.error).toBe(false);
  },
);

it("hides old labels immediately and ignores late responses across scopes", async () => {
  let release!: (value: unknown) => void;
  const client = clientFor((path) =>
    path.startsWith("/pending")
      ? new Promise((resolve) => {
          release = resolve;
        })
      : page(path.startsWith("/new") ? "new" : "old"),
  );
  const { result, rerender } = renderHook(({ base }) => useTrainingMenuItems(client, base), {
    initialProps: { base: "/old" },
  });
  await waitFor(() => expect(result.current.items.has("old")).toBe(true));
  rerender({ base: "/pending" });
  expect(result.current.items.size).toBe(0);
  await waitFor(() => expect(release).toBeDefined());
  rerender({ base: "/new" });
  await waitFor(() => expect(result.current.items.has("new")).toBe(true));
  await act(async () => {
    release(page("late"));
    await Promise.resolve();
  });
  expect([...result.current.items.keys()]).toEqual(["new"]);
});

it("does not request an unbound menu", () => {
  const read = vi.fn();
  const { result } = renderHook(() => useTrainingMenuItems(clientFor(read), null));
  expect(read).not.toHaveBeenCalled();
  expect(result.current.loading).toBe(false);
});

import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import type { ApiClient } from "../api/client";
import { AdminTrainingMenuPicker } from "./AdminTrainingMenuPicker";

const menu = {
  revision: 2,
  sections: [{ name_uk: "Їжа", categories: [{ id: "cat", name_uk: "Супи" }] }],
};
const item = (id: string) => ({
  item_id: id,
  category_id: "cat",
  name_uk: "Суп",
  source_item_key: `dish-${id}`,
});
function clientFor(read: (path: string) => unknown): ApiClient {
  return {
    request: <T,>(path: string) => Promise.resolve().then(() => read(path)) as Promise<T>,
    getSession: vi.fn(),
  };
}

it("searches the bound version and follows opaque cursors without merging duplicates", async () => {
  const paths: string[] = [];
  const change = vi.fn();
  const client = clientFor((path) => {
    paths.push(path);
    if (!path.includes("/items?")) return menu;
    const params = new URL(path, "https://test.invalid").searchParams;
    return {
      revision: 2,
      next_cursor: params.has("cursor") ? null : "opaque/+?",
      items: [item(params.has("cursor") ? "two" : "one")],
    };
  });
  render(
    <AdminTrainingMenuPicker
      client={client}
      base="/bound"
      value=""
      disabled={false}
      onChange={change}
    />,
  );
  const user = userEvent.setup();
  await screen.findByRole("option", { name: /dish-one/ });
  await user.click(screen.getByRole("button", { name: "Показати ще позиції" }));
  await screen.findByRole("option", { name: /dish-two/ });
  expect(screen.getAllByRole("option")).toHaveLength(3);
  await user.selectOptions(screen.getByLabelText("Позиція меню"), "two");
  expect(change).toHaveBeenLastCalledWith("two");
  expect(paths.some((p) => p.includes("cursor=opaque%2F%2B%3F"))).toBe(true);
  await user.type(screen.getByLabelText("Знайти позицію меню"), "Суп");
  expect(change).toHaveBeenLastCalledWith("");
  await screen.findByRole("option", { name: /dish-one/ });
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 300));
  });
  expect(paths.some((p) => p.includes("q=%D0%A1%D1%83%D0%BF") && !p.includes("cursor="))).toBe(
    true,
  );
});

it("keeps retry available after a failed page and handles empty search", async () => {
  let fail = true;
  const client = clientFor((path) => {
    if (!path.includes("/items?")) return menu;
    if (fail) throw new Error("offline");
    return { revision: 2, items: [], next_cursor: null };
  });
  render(
    <AdminTrainingMenuPicker
      client={client}
      base="/bound"
      value=""
      disabled={false}
      onChange={vi.fn()}
    />,
  );
  const user = userEvent.setup();
  await screen.findByRole("alert");
  expect(screen.getByLabelText("Позиція меню")).toBeDisabled();
  fail = false;
  await user.click(screen.getByRole("button", { name: "Повторити пошук" }));
  await screen.findByText(/Позицій не знайдено/);
});

it("discards results from a previous bound version", async () => {
  let release!: (value: unknown) => void;
  const client = clientFor((path) =>
    path.startsWith("/old")
      ? new Promise((resolve) => {
          if (path.includes("items")) release = resolve;
          else resolve(menu);
        })
      : Promise.resolve(
          path.includes("items") ? { revision: 2, items: [item("new")], next_cursor: null } : menu,
        ),
  );
  const props = { client, value: "", disabled: false, onChange: vi.fn() };
  const view = render(<AdminTrainingMenuPicker key="old" {...props} base="/old" />);
  view.rerender(<AdminTrainingMenuPicker key="new" {...props} base="/new" />);
  await screen.findByRole("option", { name: /dish-new/ });
  await act(async () => {
    release({ revision: 2, items: [item("old")], next_cursor: null });
    await Promise.resolve();
  });
  expect(screen.queryByRole("option", { name: /dish-old/ })).not.toBeInTheDocument();
});

it("rejects mismatched menu revisions", async () => {
  const client = clientFor((path) =>
    path.includes("items") ? { revision: 3, items: [item("wrong")], next_cursor: null } : menu,
  );
  render(
    <AdminTrainingMenuPicker
      client={client}
      base="/bound"
      value=""
      disabled={false}
      onChange={vi.fn()}
    />,
  );
  await screen.findByRole("alert");
  expect(screen.queryByRole("option", { name: /dish-wrong/ })).not.toBeInTheDocument();
});

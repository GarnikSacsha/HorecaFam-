import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import type { ApiClient, RequestOptions } from "../api/client";
import type {
  MenuItemListResponse,
  MenuVersionCollection,
  MenuVersionDetail,
  SessionResponse,
} from "../api/contracts";
import { SessionProvider } from "../session/SessionContext";
import { AdminMenuPage } from "./AdminMenuPage";

const session: SessionResponse = {
  user: { id: "admin-1", email: "admin@example.com", preferred_locale: "uk" },
  session: { id: "session-1", absolute_expires_at: "2030-09-01T00:00:00Z", mfa_verified: true },
  organization_access: [
    {
      organization_id: "organization-1",
      membership_status: null,
      is_employee: false,
      is_organization_admin: true,
    },
  ],
  platform_operator: false,
  csrf_token: "csrf-safe",
};

const detail: MenuVersionDetail = {
  id: "version-1",
  menu_id: "menu-1",
  organization_id: "organization-1",
  location_id: "location-1",
  version_number: 2,
  status: "draft",
  base_version_id: "published-1",
  revision: 2,
  section_count: 2,
  category_count: 1,
  item_count: 1,
  created_at: "2030-08-27T00:00:00Z",
  published_at: null,
  archived_at: null,
  sections: [
    {
      id: "section-1",
      stable_code: "main",
      name_uk: "Основне",
      position: 0,
      category_count: 1,
      categories: [
        {
          id: "category-1",
          section_id: "section-1",
          stable_code: "soups",
          name_uk: "Супи",
          position: 0,
          item_count: 1,
        },
      ],
    },
    {
      id: "section-2",
      stable_code: "drinks",
      name_uk: "Напої",
      position: 1,
      category_count: 0,
      categories: [],
    },
  ],
};

const collection: MenuVersionCollection = {
  menu_id: "menu-1",
  organization_id: "organization-1",
  location_id: "location-1",
  current_published: {
    ...detail,
    id: "published-1",
    status: "published",
    published_at: "2030-08-26T00:00:00Z",
  },
  draft: detail,
  archived: [],
};

const itemList: MenuItemListResponse = {
  revision: 2,
  next_cursor: null,
  items: [
    {
      item_id: "item-1",
      item_version_id: "item-version-1",
      version_id: "version-1",
      category_id: "category-1",
      stable_code: "borshch",
      name_uk: "Борщ",
      description_uk: "Зі сметаною",
      price_minor: 32500,
      currency: "UAH",
      availability: "available",
      position: 0,
      component_data_status: "confirmed_none",
      components: [],
      allergen_data_status: "confirmed_none",
      allergen_codes: [],
      source_kind: "manual",
      source_reference: null,
      source_item_key: null,
      verified_at: null,
      delta_kind: "changed",
      training_impact: "none",
      changed_field_codes: ["price_minor"],
      created_at: "2030-08-27T00:00:00Z",
      updated_at: "2030-08-27T00:00:00Z",
    },
  ],
};

function menuClient(requests: Array<{ path: string; options?: RequestOptions }>): ApiClient {
  return {
    getSession: () => Promise.resolve(session),
    request: <T,>(path: string, options?: RequestOptions) => {
      requests.push({ path, options });
      if (path.endsWith("/locations"))
        return Promise.resolve([
          {
            id: "location-1",
            organization_id: "organization-1",
            name: "Хрещатик",
            status: "active",
            address: null,
            timezone: "Europe/Kyiv",
          },
        ] as T);
      if (path.endsWith("/menu-versions")) return Promise.resolve(collection as T);
      if (path.includes("/items?") || (path.endsWith("/items") && !options?.method))
        return Promise.resolve(itemList as T);
      if (!options?.method && path.endsWith("/version-1")) return Promise.resolve(detail as T);
      return Promise.resolve({ revision: detail.revision + 1 } as T);
    },
  };
}

describe("Admin Menu workspace", () => {
  it("rejects a next page from a changed revision and offers a fresh read", async () => {
    const original = menuClient([]);
    const client: ApiClient = {
      ...original,
      request: <T,>(path: string, options?: RequestOptions) => {
        if (!path.includes("/items?")) return original.request<T>(path, options);
        return Promise.resolve(
          path.includes("cursor=")
            ? ({
                ...itemList,
                revision: 3,
                items: [{ ...itemList.items[0], item_id: "other", name_uk: "Чужа ревізія" }],
              } as T)
            : ({ ...itemList, next_cursor: "next" } as T),
        );
      },
    };
    const user = userEvent.setup();
    render(
      <SessionProvider client={client}>
        <MemoryRouter>
          <AdminMenuPage />
        </MemoryRouter>
      </SessionProvider>,
    );
    await screen.findByText("Борщ");
    await user.click(screen.getByRole("button", { name: "Показати ще" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Меню змінилося");
    expect(screen.queryByText("Чужа ревізія")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Оновити меню" }));
    await screen.findByRole("button", { name: "Показати ще" });
  });

  it("ignores a late page from the previous location", async () => {
    const original = menuClient([]);
    let resolvePage!: (value: MenuItemListResponse) => void;
    const delayed = new Promise<MenuItemListResponse>((resolve) => {
      resolvePage = resolve;
    });
    const client: ApiClient = {
      ...original,
      request: <T,>(path: string, options?: RequestOptions) => {
        if (path.endsWith("/locations"))
          return Promise.resolve(
            ["location-1", "location-2"].map((id) => ({
              id,
              organization_id: "organization-1",
              name: id,
              status: "active",
              address: null,
              timezone: "Europe/Kyiv",
            })) as T,
          );
        if (path.includes("cursor=")) return delayed as Promise<T>;
        if (path.includes("/items?"))
          return Promise.resolve(
            path.includes("location-2")
              ? ({ ...itemList, items: [{ ...itemList.items[0], name_uk: "Інша локація" }] } as T)
              : ({ ...itemList, next_cursor: "next" } as T),
          );
        return original.request<T>(path, options);
      },
    };
    const user = userEvent.setup();
    render(
      <SessionProvider client={client}>
        <MemoryRouter>
          <AdminMenuPage />
        </MemoryRouter>
      </SessionProvider>,
    );
    await screen.findByText("Борщ");
    await user.click(screen.getByRole("button", { name: "Показати ще" }));
    await user.selectOptions(screen.getByLabelText("Локація"), "location-2");
    await screen.findByText("Інша локація");
    await act(async () => {
      resolvePage({
        ...itemList,
        items: [{ ...itemList.items[0], item_id: "late", name_uk: "Запізніла" }],
      });
      await delayed;
    });
    expect(screen.queryByText("Запізніла")).not.toBeInTheDocument();
    expect(screen.queryByText("Борщ")).not.toBeInTheDocument();
  });
  it("loads all 308 items through opaque cursors without duplicating a repeated item", async () => {
    const requests: Array<{ path: string; options?: RequestOptions }> = [];
    const original = menuClient(requests);
    const allItems = Array.from({ length: 308 }, (_, index) => ({
      ...itemList.items[0],
      item_id: `many-${index}`,
      name_uk: `Позиція ${index + 1}`,
      position: index,
    }));
    const client: ApiClient = {
      ...original,
      request: <T,>(path: string, options?: RequestOptions) => {
        if (!path.includes("/items?")) return original.request<T>(path, options);
        requests.push({ path, options });
        const cursor = new URL(path, "https://example.test").searchParams.get("cursor");
        const offset = cursor ? Number(cursor.split(":")[1]) : 0;
        return Promise.resolve({
          revision: 2,
          items: allItems.slice(Math.max(0, offset - 1), offset + 100),
          next_cursor: offset + 100 < 308 ? `opaque:${offset + 100}` : null,
        } as T);
      },
    };
    const user = userEvent.setup();
    render(
      <SessionProvider client={client}>
        <MemoryRouter>
          <AdminMenuPage />
        </MemoryRouter>
      </SessionProvider>,
    );
    await screen.findByText("Позиція 100");
    expect(screen.queryByText("Позиція 101")).not.toBeInTheDocument();
    for (const last of [200, 300, 308]) {
      await user.click(screen.getByRole("button", { name: "Показати ще" }));
      await screen.findByText(`Позиція ${last}`);
    }
    expect(screen.getAllByText(/^Позиція \d+$/)).toHaveLength(308);
    expect(screen.queryByRole("button", { name: "Показати ще" })).not.toBeInTheDocument();
    expect(requests.some(({ path }) => path.includes("cursor=opaque%3A100"))).toBe(true);
  });

  it("reads Published items without a Draft or any edit controls or mutations", async () => {
    const requests: Array<{ path: string; options?: RequestOptions }> = [];
    const original = menuClient(requests);
    const client: ApiClient = {
      ...original,
      request: <T,>(path: string, options?: RequestOptions) => {
        requests.push({ path, options });
        if (path.endsWith("/menu-versions"))
          return Promise.resolve({ ...collection, draft: null } as T);
        if (path.endsWith("/published-1"))
          return Promise.resolve({ ...detail, id: "published-1", status: "published" } as T);
        return original.request<T>(path, options);
      },
    };
    render(
      <SessionProvider client={client}>
        <MemoryRouter>
          <AdminMenuPage />
        </MemoryRouter>
      </SessionProvider>,
    );
    expect(await screen.findByText("Борщ")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Редагувати" })).not.toBeInTheDocument();
    expect(screen.queryByText("Додати", { selector: "summary" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Перемістити/ })).not.toBeInTheDocument();
    expect(requests.every(({ options }) => !options?.method)).toBe(true);
  });

  it("preserves the first page on a page failure and retries the same cursor", async () => {
    const requests: Array<{ path: string; options?: RequestOptions }> = [];
    const original = menuClient(requests);
    let attempts = 0;
    const client: ApiClient = {
      ...original,
      request: <T,>(path: string, options?: RequestOptions) => {
        if (!path.includes("/items?")) return original.request<T>(path, options);
        if (path.includes("cursor=")) {
          attempts += 1;
          if (attempts === 1) return Promise.reject(new Error("offline"));
          return Promise.resolve({
            ...itemList,
            items: [{ ...itemList.items[0], item_id: "last", name_uk: "Остання" }],
          } as T);
        }
        return Promise.resolve({ ...itemList, next_cursor: "next" } as T);
      },
    };
    const user = userEvent.setup();
    render(
      <SessionProvider client={client}>
        <MemoryRouter>
          <AdminMenuPage />
        </MemoryRouter>
      </SessionProvider>,
    );
    await screen.findByText("Борщ");
    await user.click(screen.getByRole("button", { name: "Показати ще" }));
    await screen.findByRole("alert");
    expect(screen.getByText("Борщ")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Показати ще" }));
    await screen.findByText("Остання");
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    expect(attempts).toBe(2);
  });
  it("renders hierarchy and keeps manual edit and reorder as revision-guarded actions", async () => {
    const requests: Array<{ path: string; options?: RequestOptions }> = [];
    const user = userEvent.setup();
    render(
      <SessionProvider client={menuClient(requests)}>
        <MemoryRouter>
          <AdminMenuPage />
        </MemoryRouter>
      </SessionProvider>,
    );

    expect(await screen.findByRole("heading", { name: "Основне" })).toBeInTheDocument();
    expect(screen.getByText("Борщ")).toBeInTheDocument();
    expect(screen.getByText("325.00 ₴")).toBeInTheDocument();

    const item = screen.getByText("Борщ").closest("article");
    if (!item) throw new Error("Menu Item card is missing");
    await user.click(within(item).getByRole("button", { name: "Редагувати" }));
    const price = within(item).getByLabelText("Ціна, ₴");
    await user.clear(price);
    await user.type(price, "350");
    await user.click(within(item).getByRole("button", { name: "Зберегти" }));

    expect(
      requests.some(({ path, options }) => {
        if (!path.endsWith("/items/item-1") || options?.method !== "PATCH") return false;
        return (
          JSON.stringify(options.body) ===
          JSON.stringify({ expected_revision: 2, name_uk: "Борщ", price_minor: 35000 })
        );
      }),
    ).toBe(true);

    await user.click(screen.getByRole("button", { name: "Перемістити Основне нижче" }));
    expect(
      requests.some(({ path, options }) => {
        if (!path.endsWith("/sections/reorder") || options?.method !== "POST") return false;
        return (
          JSON.stringify(options.body) ===
          JSON.stringify({ ordered_ids: ["section-2", "section-1"], expected_revision: 2 })
        );
      }),
    ).toBe(true);
  });

  it("uses progressive add controls for a new section", async () => {
    const requests: Array<{ path: string; options?: RequestOptions }> = [];
    const user = userEvent.setup();
    render(
      <SessionProvider client={menuClient(requests)}>
        <MemoryRouter>
          <AdminMenuPage />
        </MemoryRouter>
      </SessionProvider>,
    );
    await screen.findByRole("heading", { name: "Основне" });
    await user.click(screen.getByText("Додати", { selector: "summary" }));
    await user.type(screen.getByLabelText("Новий розділ"), "Десерти");
    await user.click(screen.getByRole("button", { name: "Додати розділ" }));
    expect(
      requests.some(({ path, options }) => {
        if (!path.endsWith("/sections") || options?.method !== "POST") return false;
        return (
          JSON.stringify(options.body) ===
          JSON.stringify({
            name_uk: "Десерти",
            stable_code: null,
            position: 2,
            expected_revision: 2,
          })
        );
      }),
    ).toBe(true);
  });
});

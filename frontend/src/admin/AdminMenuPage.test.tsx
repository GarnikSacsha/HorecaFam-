import { render, screen, within } from "@testing-library/react";
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

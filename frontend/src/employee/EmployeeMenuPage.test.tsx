import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import type { ApiClient } from "../api/client";
import type {
  EmployeeMenuItemDetail,
  EmployeeMenuResponse,
  SessionResponse,
} from "../api/contracts";
import { SessionProvider } from "../session/SessionContext";
import { EmployeeMenuPage } from "./EmployeeMenuPage";

const session: SessionResponse = {
  user: { id: "user-1", email: "employee@example.com", preferred_locale: "en" },
  session: { id: "session-1", absolute_expires_at: "2030-09-01T00:00:00Z", mfa_verified: false },
  organization_access: [
    {
      organization_id: "organization-1",
      membership_status: "active",
      is_employee: true,
      is_organization_admin: false,
    },
  ],
  platform_operator: false,
  csrf_token: "csrf-safe",
};

const menu: EmployeeMenuResponse = {
  menu: {
    menu_id: "menu-1",
    menu_version_id: "version-2",
    location_id: "location-1",
    version_number: 2,
    published_at: "2030-08-27T10:00:00Z",
    sections: [
      {
        id: "section-1",
        name: "Основне",
        position: 0,
        categories: [{ id: "category-1", section_id: "section-1", name: "Супи", position: 0 }],
      },
    ],
  },
  items: [
    {
      item_id: "item-1",
      name: "Борщ",
      description_excerpt: "Зі сметаною",
      category_id: "category-1",
      category_name: "Супи",
      section_id: "section-1",
      section_name: "Основне",
      availability: "available",
      price_minor: 32500,
      currency: "UAH",
      content_locale: "uk",
      translation_fallback: true,
    },
  ],
  next_cursor: null,
};

const detail: EmployeeMenuItemDetail = {
  ...menu.items[0],
  description: "Борщ на яловичому бульйоні.",
  components: [{ name: "Сметана", optional: true, position: 0 }],
  allergen_data_status: "confirmed_present",
  allergens: [{ code: "milk", label: "Молоко" }],
};

describe("Employee published Menu", () => {
  it("searches and filters the current published version and opens safe item facts", async () => {
    const requests: string[] = [];
    const client: ApiClient = {
      getSession: () => Promise.resolve(session),
      request: <T,>(path: string) => {
        requests.push(path);
        if (path === "/me/menu/items/item-1") return Promise.resolve(detail as T);
        return Promise.resolve(menu as T);
      },
    };
    const user = userEvent.setup();
    render(
      <SessionProvider client={client}>
        <MemoryRouter>
          <EmployeeMenuPage />
        </MemoryRouter>
      </SessionProvider>,
    );

    expect(await screen.findByRole("heading", { name: "Меню" })).toBeInTheDocument();
    expect(screen.getByText("Опублікована версія 2")).toBeInTheDocument();
    expect(screen.getByText("Борщ")).toBeInTheDocument();
    expect(screen.getByText("Показано українською")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Пошук у меню"), "бор");
    await user.click(screen.getByRole("button", { name: "Знайти" }));
    await waitFor(() =>
      expect(requests.some((path) => path.includes("q=%D0%B1%D0%BE%D1%80"))).toBe(true),
    );

    await user.selectOptions(screen.getByLabelText("Розділ"), "section-1");
    await user.selectOptions(screen.getByLabelText("Категорія"), "category-1");
    await waitFor(() =>
      expect(
        requests.some(
          (path) =>
            path.includes("section_id=section-1") && path.includes("category_id=category-1"),
        ),
      ).toBe(true),
    );

    await user.click(screen.getByRole("button", { name: /Борщ/ }));
    const dialog = await screen.findByRole("dialog", { name: "Борщ" });
    expect(dialog).toHaveTextContent("Борщ на яловичому бульйоні.");
    expect(dialog).toHaveTextContent("Сметана (за бажанням)");
    expect(dialog).toHaveTextContent("Молоко");
    expect(dialog).not.toHaveTextContent("source_reference");
  });

  it("shows the truthful no-publication state", async () => {
    const client: ApiClient = {
      getSession: () => Promise.resolve(session),
      request: <T,>() =>
        Promise.resolve({ menu: null, items: [], next_cursor: null } as EmployeeMenuResponse as T),
    };
    render(
      <SessionProvider client={client}>
        <MemoryRouter>
          <EmployeeMenuPage />
        </MemoryRouter>
      </SessionProvider>,
    );

    expect(
      await screen.findByRole("heading", { name: "Меню ще не опубліковано" }),
    ).toBeInTheDocument();
  });

  it("opens the exact Menu Item linked from a Training content card", async () => {
    const client: ApiClient = {
      getSession: () => Promise.resolve(session),
      request: <T,>(path: string) =>
        Promise.resolve((path === "/me/menu/items/item-1" ? detail : menu) as T),
    };
    render(
      <SessionProvider client={client}>
        <MemoryRouter initialEntries={["/employee/menu?item=item-1"]}>
          <EmployeeMenuPage />
        </MemoryRouter>
      </SessionProvider>,
    );

    expect(await screen.findByRole("dialog", { name: "Борщ" })).toHaveTextContent(
      "Борщ на яловичому бульйоні.",
    );
  });
});

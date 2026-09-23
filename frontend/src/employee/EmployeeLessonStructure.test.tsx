import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ApiClient } from "../api/client";
import type { SessionResponse } from "../api/contracts";
import { SessionProvider } from "../session/SessionContext";
import { EmployeeLearningLessonPage } from "./EmployeeLearningLessonPage";

const session: SessionResponse = {
  user: { id: "user", email: "employee@example.com", preferred_locale: "uk" },
  session: { id: "session", absolute_expires_at: "2030-09-01T00:00:00Z", mfa_verified: false },
  organization_access: [
    {
      organization_id: "org",
      membership_status: "active",
      is_employee: true,
      is_organization_admin: false,
    },
  ],
  platform_operator: false,
  csrf_token: "test",
};

function setup(moduleId: string | null = "module-1") {
  const requests: string[] = [];
  const client: ApiClient = {
    getSession: () => Promise.resolve(session),
    request: <T,>(path: string) => {
      requests.push(path);
      if (path.includes("interactive-training"))
        return Promise.resolve({
          availability: "preparing",
          can_start: false,
          reason_codes: [],
          active_attempt: null,
          latest: null,
          best: null,
          history: [],
        } as T);
      return Promise.resolve({
        id: "lesson-1",
        module_id: moduleId,
        title: "Страви",
        completed: true,
        content_blocks: [
          { id: "intro", type: "text", payload: { text_uk: "Почніть зі стартерів." } },
          { id: "starters", type: "heading", payload: { level: 2, text_uk: "Стартери" } },
          {
            id: "card",
            type: "menu_item_card",
            payload: { menu_item_id: "item" },
            menu_item: {
              item_id: "item",
              name: "Овочевий стартер",
              description_excerpt: "Запечені овочі.",
              category_name: "Стартери",
              section_name: "Їжа",
              translation_fallback: false,
            },
          },
          {
            id: "variant",
            type: "text",
            payload: { text_uk: "Варіант у навчальному знімку: 100 г; ціна 100 грн." },
          },
          { id: "breakfasts", type: "heading", payload: { level: 2, text_uk: "Сніданки" } },
          {
            id: "ordinary",
            type: "text",
            payload: { text_uk: "Не приховуйте важливі правила подачі." },
          },
        ],
      } as T);
    },
  };
  render(
    <SessionProvider client={client}>
      <MemoryRouter initialEntries={["/employee/learning/lessons/lesson-1"]}>
        <Routes>
          <Route
            path="/employee/learning/lessons/:lessonId"
            element={<EmployeeLearningLessonPage />}
          />
          <Route path="/employee/learning/modules/:moduleId" element={<h1>Уроки модуля</h1>} />
        </Routes>
      </MemoryRouter>
    </SessionProvider>,
  );
  return { requests, user: userEvent.setup() };
}

it("returns direct lesson visits and completed readers to their module", async () => {
  const { user, requests } = setup();
  const back = await screen.findByRole("link", { name: "← До уроків модуля" });
  expect(back).toHaveAttribute("href", "/employee/learning/modules/module-1");
  expect(screen.getByRole("link", { name: "Повернутися до уроків" })).toHaveAttribute(
    "href",
    "/employee/learning/modules/module-1",
  );
  await user.click(back);
  expect(screen.getByRole("heading", { name: "Уроки модуля" })).toBeInTheDocument();
  expect(requests.some((p) => p.endsWith("/complete"))).toBe(false);
});

it("shows named cards, category contents with counts and collapsible snapshot details", async () => {
  const { user, requests } = setup();
  expect(
    await screen.findByRole("button", { name: "Відкрити Овочевий стартер" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Запечені овочі.")).toBeVisible();
  const contents = screen.getByRole("navigation", { name: "Зміст уроку" });
  expect(within(contents).getByRole("link", { name: /Стартери.*1/ })).toHaveAttribute(
    "href",
    "#block-starters",
  );
  expect(screen.getByText("Не приховуйте важливі правила подачі.")).toBeVisible();
  const variant = screen.getByText("Варіант у навчальному знімку: 100 г; ціна 100 грн.");
  expect(variant.closest("details")).not.toHaveAttribute("open");
  await user.click(screen.getByText("Варіанти та дані знімка"));
  expect(variant.closest("details")).toHaveAttribute("open");
  expect(requests.some((p) => p.startsWith("/me/menu"))).toBe(false);
});

it("retains a safe Learning fallback for an older API", async () => {
  setup(null);
  expect(await screen.findByRole("link", { name: "← До навчальних модулів" })).toHaveAttribute(
    "href",
    "/employee/learning",
  );
});

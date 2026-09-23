import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import type { ApiClient } from "../api/client";
import type { EmployeeMenuItemDetail, SessionResponse } from "../api/contracts";
import { SessionProvider } from "../session/SessionContext";
import { EmployeeLearningLessonPage } from "./EmployeeLearningLessonPage";

const session: SessionResponse = {
  user: { id: "user-1", email: "employee@example.com", preferred_locale: "uk" },
  session: { id: "session-1", absolute_expires_at: "2030-09-01T00:00:00Z", mfa_verified: false },
  organization_access: [
    {
      organization_id: "org-1",
      membership_status: "active",
      is_employee: true,
      is_organization_admin: false,
    },
  ],
  platform_operator: false,
  csrf_token: "csrf-safe",
};
const detail: EmployeeMenuItemDetail = {
  item_id: "item-1",
  name: "Пломбір",
  description_excerpt: "Вершковий",
  description: "Вершковий пломбір.",
  category_id: "category-1",
  category_name: "Морозиво",
  section_id: "section-1",
  section_name: "Десерти",
  availability: "available",
  price_minor: 16500,
  currency: "UAH",
  content_locale: "uk",
  translation_fallback: false,
  components: [],
  allergen_data_status: "unknown",
  allergens: [],
};
function Location() {
  return <output data-testid="location">{useLocation().pathname}</output>;
}
function setup(load: () => Promise<EmployeeMenuItemDetail>) {
  const requests: string[] = [];
  const client: ApiClient = {
    getSession: () => Promise.resolve(session),
    request: <T,>(path: string) => {
      requests.push(path);
      if (path.startsWith("/me/menu/items/")) return load() as Promise<T>;
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
        title: "Десерти та морозиво",
        completed: false,
        content_blocks: [
          {
            id: "card-1",
            type: "menu_item_card",
            payload: { menu_item_id: "item-1" },
            translation_fallback: false,
          },
        ],
      } as T);
    },
  };
  render(
    <SessionProvider client={client}>
      <MemoryRouter initialEntries={["/employee/learning/lessons/lesson-1"]}>
        <Location />
        <Routes>
          <Route
            path="/employee/learning/lessons/:lessonId"
            element={<EmployeeLearningLessonPage />}
          />
        </Routes>
      </MemoryRouter>
    </SessionProvider>,
  );
  return { user: userEvent.setup(), requests };
}

describe("Lesson menu overlay", () => {
  it("opens details without catalog navigation or marking the lesson complete and restores focus", async () => {
    const { user, requests } = setup(() => Promise.resolve(detail));
    const trigger = await screen.findByRole("button", { name: "Відкрити позицію в меню" });
    await user.click(trigger);
    expect(await screen.findByRole("dialog", { name: "Пломбір" })).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent("/employee/learning/lessons/lesson-1");
    expect(screen.getByText("Інформацію про алергени ще не підтверджено.")).toBeInTheDocument();
    expect(requests.filter((p) => p.startsWith("/me/menu"))).toEqual(["/me/menu/items/item-1"]);
    expect(requests.some((p) => p.endsWith("/complete"))).toBe(false);
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it.each(["resolve", "reject"])("closes while loading and ignores late %s", async (outcome) => {
    let resolve!: (value: EmployeeMenuItemDetail) => void;
    let reject!: (reason: Error) => void;
    const pending = new Promise<EmployeeMenuItemDetail>((yes, no) => {
      resolve = yes;
      reject = no;
    });
    const { user } = setup(() => pending);
    await user.click(await screen.findByRole("button", { name: "Відкрити позицію в меню" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Закрити" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await act(async () => {
      if (outcome === "resolve") resolve(detail);
      else reject(new Error("offline"));
      await Promise.resolve();
    });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("retries a failed detail request without reloading the lesson", async () => {
    let calls = 0;
    const { user, requests } = setup(() =>
      ++calls === 1 ? Promise.reject(new Error("offline")) : Promise.resolve(detail),
    );
    await user.click(await screen.findByRole("button", { name: "Відкрити позицію в меню" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Не вдалося завантажити деталі позиції.",
    );
    await user.click(screen.getByRole("button", { name: "Повторити" }));
    expect(await screen.findByRole("dialog", { name: "Пломбір" })).toBeInTheDocument();
    expect(requests.filter((p) => p.includes("?locale="))).toHaveLength(1);
    expect(calls).toBe(2);
  });
});

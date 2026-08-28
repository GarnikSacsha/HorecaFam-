import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import type { ApiClient } from "../api/client";
import type { SessionResponse } from "../api/contracts";
import { SessionProvider } from "../session/SessionContext";
import { EmployeeLearningLessonPage } from "./EmployeeLearningLessonPage";
import { EmployeeLearningModulePage } from "./EmployeeLearningModulePage";
import { EmployeeLearningPage } from "./EmployeeLearningPage";

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

function renderWithClient(
  client: ApiClient,
  initialEntry: string,
  path: string,
  element: React.ReactNode,
) {
  return render(
    <SessionProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path={path} element={element} />
        </Routes>
      </MemoryRouter>
    </SessionProvider>,
  );
}

describe("Employee Training reference", () => {
  it("lists current published modules and exposes the truthful empty state", async () => {
    const requests: string[] = [];
    const client: ApiClient = {
      getSession: () => Promise.resolve(session),
      request: <T,>(path: string) => {
        requests.push(path);
        return Promise.resolve({
          training: { id: "training-1", version_number: 3, published_at: "2030-08-28T08:00:00Z" },
          modules: [
            {
              id: "module-1",
              domain_type: "menu",
              title: "Меню та рекомендації",
              description: "Короткий довідник для зміни.",
              position: 0,
              required: true,
              lesson_count: 2,
              content_locale: "uk",
              translation_fallback: true,
            },
          ],
          content_locale: "uk",
          translation_fallback: true,
        } as T);
      },
    };
    renderWithClient(client, "/employee/learning", "/employee/learning", <EmployeeLearningPage />);

    expect(await screen.findByRole("heading", { name: "Навчання" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /Меню та рекомендації/ })).toHaveAttribute(
      "href",
      "/employee/learning/modules/module-1",
    );
    expect(screen.getByText("Показано українською")).toBeInTheDocument();
    await waitFor(() => expect(requests.some((path) => path.includes("locale=en"))).toBe(true));

    const emptyClient: ApiClient = {
      getSession: () => Promise.resolve(session),
      request: <T,>() =>
        Promise.resolve({
          training: null,
          modules: [],
          content_locale: "en",
          translation_fallback: false,
        } as T),
    };
    renderWithClient(
      emptyClient,
      "/employee/learning",
      "/employee/learning",
      <EmployeeLearningPage />,
    );
    expect(
      await screen.findByRole("heading", { name: "Навчальні матеріали ще не опубліковано" }),
    ).toBeInTheDocument();
  });

  it("shows an ordered module lesson list with direct lesson navigation", async () => {
    const client: ApiClient = {
      getSession: () => Promise.resolve(session),
      request: <T,>() =>
        Promise.resolve({
          id: "module-1",
          domain_type: "menu",
          title: "Меню та рекомендації",
          description: "Короткий довідник для зміни.",
          position: 0,
          required: true,
          lesson_count: 2,
          content_locale: "uk",
          translation_fallback: true,
          lessons: [
            {
              id: "lesson-1",
              title: "Подача борщу",
              description: "Факти для гостя.",
              position: 0,
              required: true,
              estimated_minutes: 5,
              content_locale: "uk",
              translation_fallback: true,
            },
            {
              id: "lesson-2",
              title: "Напої",
              description: null,
              position: 1,
              required: false,
              estimated_minutes: null,
              content_locale: "en",
              translation_fallback: false,
            },
          ],
        } as T),
    };
    renderWithClient(
      client,
      "/employee/learning/modules/module-1",
      "/employee/learning/modules/:moduleId",
      <EmployeeLearningModulePage />,
    );

    expect(
      await screen.findByRole("heading", { name: "Меню та рекомендації" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Подача борщу/ })).toHaveAttribute(
      "href",
      "/employee/learning/lessons/lesson-1",
    );
    expect(screen.getByRole("link", { name: "До всіх модулів" })).toHaveAttribute(
      "href",
      "/employee/learning",
    );
  });

  it("renders every approved lesson block safely without Slice 4 behavior", async () => {
    const requests: string[] = [];
    const client: ApiClient = {
      getSession: () => Promise.resolve(session),
      request: <T,>(path: string) => {
        requests.push(path);
        if (path.includes("/assets/asset-1/access")) {
          return Promise.resolve({
            url: "https://assets.example.test/signed/image",
            expires_in: 300,
          } as T);
        }
        return Promise.resolve({
          id: "lesson-1",
          title: "Подача борщу",
          description: "Факти для гостя.",
          position: 0,
          required: true,
          estimated_minutes: 5,
          content_locale: "uk",
          translation_fallback: true,
          content_blocks: [
            {
              id: "b1",
              type: "heading",
              position: 0,
              payload: { level: 2, text_uk: "Головне" },
              content_locale: "uk",
              translation_fallback: false,
            },
            {
              id: "b2",
              type: "text",
              position: 1,
              payload: { text_uk: "Поясніть склад гостю." },
              content_locale: "uk",
              translation_fallback: false,
            },
            {
              id: "b3",
              type: "list",
              position: 2,
              payload: { style: "ordered", items_uk: ["Назвіть страву", "Уточніть алергени"] },
              content_locale: "uk",
              translation_fallback: false,
            },
            {
              id: "b4",
              type: "callout",
              position: 3,
              payload: { tone: "warning", title_uk: "Увага", text_uk: "Перевірте актуальність." },
              content_locale: "uk",
              translation_fallback: false,
            },
            {
              id: "b5",
              type: "menu_item_card",
              position: 4,
              payload: { menu_item_id: "menu-item-1", note_uk: "Подавайте зі сметаною." },
              content_locale: "uk",
              translation_fallback: false,
            },
            {
              id: "b6",
              type: "image",
              position: 5,
              payload: {
                asset_id: "asset-1",
                alt_uk: "Борщ у білій тарілці",
                caption_uk: "Приклад подачі",
              },
              content_locale: "uk",
              translation_fallback: false,
            },
            {
              id: "b7",
              type: "external_video",
              position: 6,
              payload: {
                provider: "youtube",
                video_id: "dQw4w9WgXcQ",
                title_uk: "Відео про подачу",
                summary_uk: "Коротка демонстрація.",
              },
              content_locale: "uk",
              translation_fallback: false,
            },
          ],
        } as T);
      },
    };
    renderWithClient(
      client,
      "/employee/learning/lessons/lesson-1",
      "/employee/learning/lessons/:lessonId",
      <EmployeeLearningLessonPage />,
    );

    expect(await screen.findByRole("heading", { name: "Подача борщу" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Головне" })).toBeInTheDocument();
    expect(screen.getByText("Поясніть склад гостю.")).toBeInTheDocument();
    expect(screen.getByText("Уточніть алергени")).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("Перевірте актуальність.");
    expect(screen.getByText("Подавайте зі сметаною.")).toBeInTheDocument();
    expect(await screen.findByRole("img", { name: "Борщ у білій тарілці" })).toHaveAttribute(
      "src",
      "https://assets.example.test/signed/image",
    );
    expect(screen.getByTitle("Відео про подачу")).toHaveAttribute(
      "src",
      "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
    );
    expect(document.body).not.toHaveTextContent(/завершити|прогрес|практика/i);
    expect(screen.getByRole("link", { name: "Відкрити позицію в меню" })).toHaveAttribute(
      "href",
      "/employee/menu?item=menu-item-1",
    );
    expect(requests.some((path) => path.includes("/assets/asset-1/access"))).toBe(true);
  });
});

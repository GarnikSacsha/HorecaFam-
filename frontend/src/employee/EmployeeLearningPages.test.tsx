import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ApiError } from "../api/client";
import type { ApiClient, RequestOptions } from "../api/client";
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
  it("offers whole-menu Practice as the next step after completed training", async () => {
    const client: ApiClient = {
      getSession: () => Promise.resolve(session),
      request: <T,>() =>
        Promise.resolve({
          assignment: {
            id: "assignment-1",
            status: "completed",
            assigned_at: "2030-08-28T08:00:00Z",
            started_at: "2030-08-28T09:00:00Z",
            completed_at: "2030-08-28T10:00:00Z",
          },
          training: {
            id: "training-1",
            version_number: 3,
            published_at: "2030-08-28T08:00:00Z",
          },
          modules: [],
          progress: {
            required_lesson_count: 1,
            completed_required_lesson_count: 1,
            percentage: 100,
            is_complete: true,
          },
          next_action: "open_practice",
          content_locale: "uk",
          translation_fallback: false,
        } as T),
    };

    renderWithClient(client, "/employee/learning", "/employee/learning", <EmployeeLearningPage />);

    expect(
      await screen.findByRole("heading", { name: "Практика по всьому меню" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Відкрити Практику" })).toHaveAttribute(
      "href",
      "/employee/practice",
    );
  });

  it("lists current published modules and exposes the truthful empty state", async () => {
    const requests: string[] = [];
    const client: ApiClient = {
      getSession: () => Promise.resolve(session),
      request: <T,>(path: string) => {
        requests.push(path);
        return Promise.resolve({
          assignment: {
            id: "assignment-1",
            status: "in_progress",
            assigned_at: "2030-08-28T08:00:00Z",
            started_at: "2030-08-28T09:00:00Z",
            completed_at: null,
          },
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
          progress: {
            required_lesson_count: 2,
            completed_required_lesson_count: 1,
            percentage: 50,
            is_complete: false,
          },
          next_action: "open_lesson",
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
    expect(screen.getByRole("heading", { name: "Продовжити" })).toBeInTheDocument();
    expect(screen.getByText("1 із 2 обов’язкових уроків завершено")).toBeInTheDocument();
    await waitFor(() => expect(requests.some((path) => path.includes("locale=en"))).toBe(true));

    const emptyClient: ApiClient = {
      getSession: () => Promise.resolve(session),
      request: <T,>() =>
        Promise.resolve({
          assignment: null,
          training: null,
          modules: [],
          progress: null,
          next_action: "none",
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
      await screen.findByRole("heading", { name: "Навчання ще не призначено" }),
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
              completed: true,
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
              completed: false,
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
    expect(screen.getByText("1 із 2 уроків завершено")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Подача борщу/ })).toHaveTextContent("Завершено");
    expect(screen.getByRole("link", { name: /Напої/ })).toHaveTextContent("Не завершено");
    expect(document.body).not.toHaveTextContent(/заблоковано|спочатку завершіть/i);
  });

  it("keeps a completed assigned version available for retained review", async () => {
    const client: ApiClient = {
      getSession: () => Promise.resolve(session),
      request: <T,>() =>
        Promise.resolve({
          assignment: {
            id: "assignment-archived-1",
            status: "completed",
            assigned_at: "2030-08-20T08:00:00Z",
            started_at: "2030-08-20T09:00:00Z",
            completed_at: "2030-08-21T10:00:00Z",
          },
          training: {
            id: "retained-version-2",
            version_number: 2,
            published_at: "2030-08-20T08:00:00Z",
          },
          modules: [
            {
              id: "module-retained",
              domain_type: "menu",
              title: "Призначений архівний модуль",
              description: null,
              position: 0,
              required: true,
              lesson_count: 1,
              content_locale: "uk",
              translation_fallback: false,
            },
          ],
          progress: {
            required_lesson_count: 1,
            completed_required_lesson_count: 1,
            percentage: 100,
            is_complete: true,
          },
          next_action: "review_training",
          content_locale: "uk",
          translation_fallback: false,
        } as T),
    };

    renderWithClient(client, "/employee/learning", "/employee/learning", <EmployeeLearningPage />);

    expect(await screen.findByRole("heading", { name: "Завершено" })).toBeInTheDocument();
    expect(screen.getByText("Призначена версія 2")).toBeInTheDocument();
    expect(
      screen.getByText("Матеріали призначеної версії доступні для повторення."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Призначений архівний модуль/ })).toHaveAttribute(
      "href",
      "/employee/learning/modules/module-retained",
    );
  });

  it("renders every approved lesson block safely with completion separate from viewing", async () => {
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
          completed: false,
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
    expect(screen.getByRole("button", { name: "Ознайомився" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Інтерактивне тренування" })).toBeInTheDocument();
    expect(screen.getByText("Спочатку завершіть урок")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Відкрити позицію в меню" })).toHaveAttribute(
      "href",
      "/employee/menu?item=menu-item-1",
    );
    expect(requests.some((path) => path.includes("/assets/asset-1/access"))).toBe(true);
  });

  it("announces completion pending and success while sending the protected idempotent mutation", async () => {
    const user = userEvent.setup();
    const requests: Array<{ path: string; options?: RequestOptions }> = [];
    let resolveCompletion: ((value: unknown) => void) | undefined;
    const completion = new Promise((resolve) => {
      resolveCompletion = resolve;
    });
    const client: ApiClient = {
      getSession: () => Promise.resolve(session),
      request: <T,>(path: string, options?: RequestOptions) => {
        requests.push({ path, options });
        if (options?.method === "POST") return completion as Promise<T>;
        if (path.endsWith("/interactive-training")) {
          return Promise.resolve({
            lesson_id: "lesson-1",
            lesson_version_id: "lesson-version-1",
            assessment_version_id: null,
            availability: "preparing",
            can_start: false,
            reason_codes: ["ASSESSMENT_NOT_PUBLISHED"],
            readiness_status: null,
            active_attempt: null,
            latest: null,
            best: null,
            history: [],
          } as T);
        }
        return Promise.resolve({
          id: "lesson-1",
          title: "Подача борщу",
          description: "Факти для гостя.",
          position: 0,
          required: true,
          estimated_minutes: 5,
          completed: false,
          content_locale: "uk",
          translation_fallback: false,
          content_blocks: [],
        } as T);
      },
    };
    renderWithClient(
      client,
      "/employee/learning/lessons/lesson-1",
      "/employee/learning/lessons/:lessonId",
      <EmployeeLearningLessonPage />,
    );

    await user.click(await screen.findByRole("button", { name: "Ознайомився" }));
    expect(screen.getByRole("button", { name: "Зберігаємо…" })).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("Зберігаємо завершення уроку");

    resolveCompletion?.({
      completion: {
        id: "completion-1",
        assignment_id: "assignment-1",
        lesson_id: "lesson-1",
        lesson_version_id: "lesson-version-1",
        completion_source: "employee",
        completed_at: "2030-08-28T10:00:00Z",
      },
      assignment: {
        id: "assignment-1",
        status: "completed",
        assigned_at: "2030-08-28T08:00:00Z",
        started_at: "2030-08-28T09:00:00Z",
        completed_at: "2030-08-28T10:00:00Z",
      },
      progress: {
        required_lesson_count: 1,
        completed_required_lesson_count: 1,
        percentage: 100,
        is_complete: true,
      },
      next_action: "review_training",
    });

    expect(await screen.findByRole("button", { name: "Ознайомлено" })).toBeDisabled();
    expect(screen.getByText("Урок завершено").closest('[role="status"]')).not.toBeNull();
    expect(screen.getByText("1 із 1 обов’язкових уроків завершено")).toBeInTheDocument();
    const mutation = requests.find(({ options }) => options?.method === "POST");
    expect(mutation?.path).toBe("/me/training/lessons/lesson-1/complete");
    expect(mutation?.options?.body).toBeUndefined();
    expect(mutation?.options?.csrfToken).toBe("csrf-safe");
    expect(typeof mutation?.options?.idempotencyKey).toBe("string");
  });

  it("keeps the completion action retryable after an ordinary error", async () => {
    const user = userEvent.setup();
    const client: ApiClient = {
      getSession: () => Promise.resolve(session),
      request: <T,>(_path: string, options?: RequestOptions) =>
        options?.method === "POST"
          ? Promise.reject(new ApiError(0, { code: "NETWORK_ERROR", message: "Немає мережі" }))
          : Promise.resolve({
              id: "lesson-1",
              title: "Подача борщу",
              description: null,
              position: 0,
              required: true,
              estimated_minutes: 5,
              completed: false,
              content_locale: "uk",
              translation_fallback: false,
              content_blocks: [],
            } as T),
    };
    renderWithClient(
      client,
      "/employee/learning/lessons/lesson-1",
      "/employee/learning/lessons/:lessonId",
      <EmployeeLearningLessonPage />,
    );

    await user.click(await screen.findByRole("button", { name: "Ознайомився" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Не вдалося зберегти завершення уроку",
    );
    expect(screen.getByRole("button", { name: "Спробувати ще раз" })).toBeEnabled();
  });

  it("keeps a paused employee in a calm read-only lesson state", async () => {
    const user = userEvent.setup();
    const client: ApiClient = {
      getSession: () => Promise.resolve(session),
      request: <T,>(_path: string, options?: RequestOptions) =>
        options?.method === "POST"
          ? Promise.reject(
              new ApiError(409, {
                code: "TRAINING_COMPLETION_NOT_ALLOWED",
                message: "Completion is not allowed",
              }),
            )
          : Promise.resolve({
              id: "lesson-1",
              title: "Подача борщу",
              description: null,
              position: 0,
              required: true,
              estimated_minutes: 5,
              completed: false,
              content_locale: "uk",
              translation_fallback: false,
              content_blocks: [],
            } as T),
    };
    renderWithClient(
      client,
      "/employee/learning/lessons/lesson-1",
      "/employee/learning/lessons/:lessonId",
      <EmployeeLearningLessonPage />,
    );

    await user.click(await screen.findByRole("button", { name: "Ознайомився" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Навчання призупинено");
    expect(screen.getByText("Матеріал залишається доступним для перегляду")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Навчання призупинено" })).toBeDisabled();
  });
});

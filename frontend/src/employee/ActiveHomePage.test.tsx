import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import type { ApiClient } from "../api/client";
import type { OwnEmployeeProfilesResponse, SessionResponse } from "../api/contracts";
import { SessionProvider } from "../session/SessionContext";
import { HomeRedirect } from "../session/SessionGate";
import { ActiveHomePage } from "./ActiveHomePage";

const activeSession: SessionResponse = {
  user: { id: "user-1", email: "employee@example.com", preferred_locale: "uk" },
  session: { id: "session-1", absolute_expires_at: "2026-09-01T00:00:00Z", mfa_verified: false },
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

describe("Active Employee Home", () => {
  it.each([false, true])(
    "shows earned certification with retake=%s without inviting a first exam",
    async (retake) => {
      const client: ApiClient = {
        getSession: () => Promise.resolve(activeSession),
        request: <T,>(path: string) =>
          Promise.resolve(
            (path === "/me/profile"
              ? {
                  profiles: [
                    {
                      id: "employee-1",
                      organization: { id: "organization-1", name: "Demo" },
                      membership_status: "active",
                      first_name: "Анна",
                    },
                  ],
                }
              : path === "/me/training/final-exam"
                ? {
                    availability: "certified",
                    can_start: false,
                    certification: {
                      result_id: "result-1",
                      attempt_id: "attempt-1",
                      certified_at: "2026-09-17T12:00:00Z",
                    },
                    current_retake_requirement: retake
                      ? { timing_state: "on_time", permitted_action: "start_retake" }
                      : null,
                  }
                : {
                    assignment: { id: "assignment-1", status: "completed" },
                    training: { id: "training-1", version_number: 1 },
                    progress: {
                      completed_required_lesson_count: 4,
                      required_lesson_count: 4,
                      percentage: 100,
                    },
                    next_action: "open_final_exam",
                  }) as T,
          ),
      };
      render(
        <SessionProvider client={client}>
          <MemoryRouter>
            <ActiveHomePage />
          </MemoryRouter>
        </SessionProvider>,
      );
      expect(
        await screen.findByRole("heading", { name: "Сертифікацію отримано" }),
      ).toBeInTheDocument();
      expect(screen.queryByText("Час пройти Final Exam")).not.toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Переглянути результат" })).toHaveAttribute(
        "href",
        "/employee/final-exam",
      );
      if (retake)
        expect(screen.getByRole("link", { name: "Почати перескладання" })).toBeInTheDocument();
    },
  );

  it("routes from the refreshed server session and renders a truthful zero-assignment state", async () => {
    const profiles: OwnEmployeeProfilesResponse = {
      profiles: [
        {
          id: "employee-1",
          organization: { id: "organization-1", name: "Bacara Kyiv" },
          membership_status: "active",
          first_name: "Анна",
          last_name: "Коваль",
          operational_role: {
            id: "role-1",
            organization_id: "organization-1",
            code: "waiter",
            name_uk: "Офіціант",
            status: "active",
          },
          location: {
            id: "location-1",
            organization_id: "organization-1",
            name: "Хрещатик",
            status: "active",
            address: null,
            timezone: "Europe/Kyiv",
          },
          profile_complete: true,
          updated_at: "2026-08-27T00:00:00Z",
        },
      ],
    };
    const client: ApiClient = {
      getSession: () => Promise.resolve(activeSession),
      request: <T,>() => Promise.resolve(profiles as T),
    };

    render(
      <SessionProvider client={client}>
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route path="/" element={<HomeRedirect />} />
            <Route path="/employee" element={<ActiveHomePage />} />
          </Routes>
        </MemoryRouter>
      </SessionProvider>,
    );

    expect(await screen.findByRole("heading", { name: "Вітаємо, Анна" })).toBeInTheDocument();
    expect(screen.getByText("Навчання ще не призначено")).toBeInTheDocument();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /іспит|практик/i })).not.toBeInTheDocument();
  });

  it("renders one assignment-aware next action with current progress", async () => {
    const profiles: OwnEmployeeProfilesResponse = {
      profiles: [
        {
          id: "employee-1",
          organization: { id: "organization-1", name: "Bacara Kyiv" },
          membership_status: "active",
          first_name: "Анна",
          last_name: "Коваль",
          operational_role: {
            id: "role-1",
            organization_id: "organization-1",
            code: "waiter",
            name_uk: "Офіціант",
            status: "active",
          },
          location: {
            id: "location-1",
            organization_id: "organization-1",
            name: "Хрещатик",
            status: "active",
            address: null,
            timezone: "Europe/Kyiv",
          },
          profile_complete: true,
          updated_at: "2026-08-27T00:00:00Z",
        },
      ],
    };
    const requests: string[] = [];
    const client: ApiClient = {
      getSession: () => Promise.resolve(activeSession),
      request: <T,>(path: string) => {
        requests.push(path);
        if (path === "/me/profile") return Promise.resolve(profiles as T);
        return Promise.resolve({
          assignment: {
            id: "assignment-1",
            status: "in_progress",
            assigned_at: "2026-08-28T08:00:00Z",
            started_at: "2026-08-28T09:00:00Z",
            completed_at: null,
          },
          training: {
            id: "training-1",
            version_number: 2,
            published_at: "2026-08-28T08:00:00Z",
          },
          modules: [
            {
              id: "module-1",
              domain_type: "menu",
              title: "Меню та рекомендації",
              description: null,
              position: 0,
              required: true,
              lesson_count: 3,
              content_locale: "uk",
              translation_fallback: false,
            },
          ],
          progress: {
            required_lesson_count: 3,
            completed_required_lesson_count: 1,
            percentage: 33,
            is_complete: false,
          },
          next_action: "open_lesson",
          content_locale: "uk",
          translation_fallback: false,
        } as T);
      },
    };

    render(
      <SessionProvider client={client}>
        <MemoryRouter>
          <ActiveHomePage />
        </MemoryRouter>
      </SessionProvider>,
    );

    expect(
      await screen.findByRole("heading", { name: "Продовжуйте навчання" }),
    ).toBeInTheDocument();
    expect(screen.getByText("1 із 3 обов’язкових уроків завершено")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Поточний прогрес" })).toHaveAttribute(
      "aria-valuenow",
      "33",
    );
    expect(screen.getByRole("link", { name: "Продовжити навчання" })).toHaveAttribute(
      "href",
      "/employee/learning",
    );
    expect(screen.queryByRole("link", { name: /іспит|практик/i })).not.toBeInTheDocument();
    expect(requests).toContain("/me/training?locale=uk");
  });

  it("opens whole-menu Practice after all required training is complete", async () => {
    const profiles: OwnEmployeeProfilesResponse = {
      profiles: [
        {
          id: "employee-1",
          organization: { id: "organization-1", name: "Bacara Kyiv" },
          membership_status: "active",
          first_name: "Анна",
          last_name: "Коваль",
          operational_role: null,
          location: null,
          profile_complete: true,
          updated_at: "2026-08-27T00:00:00Z",
        },
      ],
    };
    const client: ApiClient = {
      getSession: () => Promise.resolve(activeSession),
      request: <T,>(path: string) =>
        Promise.resolve(
          (path === "/me/profile"
            ? profiles
            : {
                assignment: {
                  id: "assignment-1",
                  status: "completed",
                  assigned_at: "2026-08-28T08:00:00Z",
                  started_at: "2026-08-28T09:00:00Z",
                  completed_at: "2026-08-28T10:00:00Z",
                },
                training: {
                  id: "training-1",
                  version_number: 2,
                  published_at: "2026-08-28T08:00:00Z",
                },
                modules: [],
                progress: {
                  required_lesson_count: 3,
                  completed_required_lesson_count: 3,
                  percentage: 100,
                  is_complete: true,
                },
                next_action: "open_practice",
                content_locale: "uk",
                translation_fallback: false,
              }) as T,
        ),
    };

    render(
      <SessionProvider client={client}>
        <MemoryRouter>
          <ActiveHomePage />
        </MemoryRouter>
      </SessionProvider>,
    );

    expect(
      await screen.findByRole("heading", { name: "Час перевірити знання меню" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Відкрити Практику" })).toHaveAttribute(
      "href",
      "/employee/practice",
    );
  });

  it("opens Final Exam after Practice has earned eligibility", async () => {
    const profiles: OwnEmployeeProfilesResponse = {
      profiles: [
        {
          id: "employee-1",
          organization: { id: "organization-1", name: "Bacara Kyiv" },
          membership_status: "active",
          first_name: "Анна",
          last_name: "Коваль",
          operational_role: null,
          location: null,
          profile_complete: true,
          updated_at: "2026-08-27T00:00:00Z",
        },
      ],
    };
    const client: ApiClient = {
      getSession: () => Promise.resolve(activeSession),
      request: <T,>(path: string) =>
        Promise.resolve(
          (path === "/me/profile"
            ? profiles
            : {
                assignment: {
                  id: "assignment-1",
                  status: "completed",
                  assigned_at: "2026-08-28T08:00:00Z",
                  started_at: "2026-08-28T09:00:00Z",
                  completed_at: "2026-08-28T10:00:00Z",
                },
                training: {
                  id: "training-1",
                  version_number: 2,
                  published_at: "2026-08-28T08:00:00Z",
                },
                modules: [],
                progress: {
                  required_lesson_count: 3,
                  completed_required_lesson_count: 3,
                  percentage: 100,
                  is_complete: true,
                },
                next_action: "open_final_exam",
                content_locale: "uk",
                translation_fallback: false,
              }) as T,
        ),
    };

    render(
      <SessionProvider client={client}>
        <MemoryRouter>
          <ActiveHomePage />
        </MemoryRouter>
      </SessionProvider>,
    );

    expect(
      await screen.findByRole("heading", { name: "Час пройти Final Exam" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Відкрити Final Exam" })).toHaveAttribute(
      "href",
      "/employee/final-exam",
    );
  });
});

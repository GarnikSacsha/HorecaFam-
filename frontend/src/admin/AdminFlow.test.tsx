import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ApiError } from "../api/client";
import type { ApiClient, RequestOptions } from "../api/client";
import type {
  AdminResultsOverviewResponse,
  EmployeeDetail,
  EmployeeListResponse,
  SessionResponse,
  TrainingAssignmentResponse,
} from "../api/contracts";
import { SessionProvider } from "../session/SessionContext";
import { AdminEmployeeDetailPage } from "./AdminEmployeeDetailPage";
import { AdminEmployeesPage } from "./AdminEmployeesPage";
import { AdminResultsPage } from "./AdminResultsPage";

const adminSession: SessionResponse = {
  user: { id: "admin-1", email: "admin@example.com", preferred_locale: "uk" },
  session: { id: "session-1", absolute_expires_at: "2026-09-01T00:00:00Z", mfa_verified: true },
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

const pendingEmployee: EmployeeDetail = {
  id: "employee-1",
  organization_id: "organization-1",
  email: "employee@example.com",
  first_name: null,
  last_name: null,
  membership_status: "pending",
  operational_role: null,
  location: null,
  profile_complete: false,
  created_at: "2026-08-27T00:00:00Z",
  updated_at: "2026-08-27T00:00:00Z",
  membership_created_at: "2026-08-27T00:00:00Z",
  activated_at: null,
  disabled_at: null,
  training_participation_status: "active",
  training_paused_at: null,
  training_pause_reason_code: null,
  training_pause_note: null,
  planned_resume_at: null,
  disabled_reason_code: null,
  disabled_note: null,
};

function adminClient(
  handler: <T>(path: string, options?: RequestOptions) => Promise<T>,
): ApiClient {
  return { getSession: () => Promise.resolve(adminSession), request: handler };
}

describe("Admin Employee flow", () => {
  it("shows Final Exam status without turning employee results into a leaderboard", async () => {
    const results: AdminResultsOverviewResponse = {
      items: [
        {
          employee_id: "employee-1",
          first_name: "Анна",
          last_name: "Коваль",
          location_id: "location-1",
          current_training_status: "completed",
          latest_practice_score_basis_points: 8700,
          certification: {
            result_id: "result-1",
            attempt_id: "attempt-1",
            certified_at: "2026-08-31T10:00:00Z",
          },
          latest_final_exam: {
            result_id: "result-1",
            attempt_id: "attempt-1",
            assessment_version_id: "assessment-1",
            completed_at: "2026-08-31T10:00:00Z",
            correct_count: 16,
            total_count: 20,
            score_basis_points: 8000,
            knowledge_level: "strong",
            pass_status: "passed",
            critical_error_count: 0,
          },
          critical_error_count: 0,
        },
      ],
      total: 1,
      next_cursor: null,
    };
    const client = adminClient(<T,>() => Promise.resolve(results as T));

    render(
      <SessionProvider client={client}>
        <MemoryRouter>
          <AdminResultsPage />
        </MemoryRouter>
      </SessionProvider>,
    );

    expect(
      await screen.findByRole("table", { name: "Результати працівників" }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Сертифіковано").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Відкрити" })).toHaveAttribute(
      "href",
      "/admin/results/employee-1",
    );
    expect(screen.queryByRole("columnheader", { name: /рейтинг/i })).not.toBeInTheDocument();
  });

  it("renders Employees as a semantic table and creates an invitation with protected headers", async () => {
    const requests: Array<{ path: string; options?: RequestOptions }> = [];
    const employees: EmployeeListResponse = { items: [pendingEmployee], next_cursor: null };
    const client = adminClient(<T,>(path: string, options?: RequestOptions) => {
      requests.push({ path, options });
      if (path.endsWith("/employees")) return Promise.resolve(employees as T);
      if (path.endsWith("/invitations")) {
        return Promise.resolve({ id: "invitation-1", email: "new@example.com" } as T);
      }
      return Promise.resolve({
        id: "organization-1",
        name: "Bacara Kyiv",
        status: "active",
        default_locale: "uk",
        timezone: "Europe/Kyiv",
      } as T);
    });
    const user = userEvent.setup();

    render(
      <SessionProvider client={client}>
        <MemoryRouter>
          <AdminEmployeesPage />
        </MemoryRouter>
      </SessionProvider>,
    );

    expect(await screen.findByRole("table", { name: "Працівники" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Електронна пошта нового працівника"), "new@example.com");
    await user.click(screen.getByRole("button", { name: "Надіслати запрошення" }));

    expect(await screen.findByText("Запрошення створено для new@example.com")).toBeInTheDocument();
    const invitationRequest = requests.at(-1);
    expect(invitationRequest?.path).toBe("/organizations/organization-1/invitations");
    expect(invitationRequest?.options?.method).toBe("POST");
    expect(invitationRequest?.options?.body).toEqual({ email: "new@example.com" });
    expect(invitationRequest?.options?.csrfToken).toBe("csrf-safe");
    expect(typeof invitationRequest?.options?.idempotencyKey).toBe("string");
  });

  it("keeps profile save and explicit Activation as separate server actions", async () => {
    const mutations: Array<{ path: string; options?: RequestOptions }> = [];
    let employee = pendingEmployee;
    const client = adminClient(<T,>(path: string, options?: RequestOptions) => {
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
      if (path.endsWith("/operational-roles"))
        return Promise.resolve([
          {
            id: "role-1",
            organization_id: "organization-1",
            code: "waiter",
            name_uk: "Офіціант",
            status: "active",
          },
        ] as T);
      if (path.endsWith("/activate")) {
        mutations.push({ path, options });
        employee = {
          ...employee,
          membership_status: "active",
          profile_complete: true,
          activated_at: "2026-08-27T10:00:00Z",
        };
        return Promise.resolve({
          employee_id: employee.id,
          organization_id: employee.organization_id,
          membership_status: "active",
          training_participation_status: "active",
          activated_at: employee.activated_at,
        } as T);
      }
      if (options?.method === "PATCH") {
        mutations.push({ path, options });
        employee = {
          ...employee,
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
        };
        return Promise.resolve(employee as T);
      }
      if (path.endsWith("/training-assignments"))
        return Promise.resolve({ current: null, history: [], progress: null } as T);
      return Promise.resolve(employee as T);
    });
    const user = userEvent.setup();

    render(
      <SessionProvider client={client}>
        <MemoryRouter initialEntries={["/admin/employees/employee-1"]}>
          <Routes>
            <Route path="/admin/employees/:employeeId" element={<AdminEmployeeDetailPage />} />
          </Routes>
        </MemoryRouter>
      </SessionProvider>,
    );

    await user.type(await screen.findByLabelText("Ім’я"), "Анна");
    await user.type(screen.getByLabelText("Прізвище"), "Коваль");
    await user.selectOptions(screen.getByLabelText("Роль"), "role-1");
    await user.selectOptions(screen.getByLabelText("Локація"), "location-1");
    await user.click(screen.getByRole("button", { name: "Зберегти профіль" }));

    expect(
      await screen.findByText("Профіль збережено. Працівник ще очікує активації."),
    ).toBeInTheDocument();
    expect(mutations).toHaveLength(1);
    expect(mutations[0]?.options?.method).toBe("PATCH");

    await user.click(screen.getByRole("button", { name: "Активувати працівника" }));
    await user.click(screen.getByRole("button", { name: "Підтвердити активацію" }));

    expect(await screen.findByText("Працівника активовано")).toBeInTheDocument();
    expect(mutations).toHaveLength(2);
    const activationRequest = mutations[1];
    expect(activationRequest?.path).toBe(
      "/organizations/organization-1/employees/employee-1/activate",
    );
    expect(activationRequest?.options?.method).toBe("POST");
    expect(activationRequest?.options?.csrfToken).toBe("csrf-safe");
    expect(typeof activationRequest?.options?.idempotencyKey).toBe("string");
  });

  it("assigns, revokes and reassigns Training without hiding retained history", async () => {
    const mutations: Array<{ path: string; options?: RequestOptions }> = [];
    const activeEmployee: EmployeeDetail = {
      ...pendingEmployee,
      first_name: "Анна",
      last_name: "Коваль",
      membership_status: "active",
      profile_complete: true,
      activated_at: "2026-08-27T10:00:00Z",
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
    };
    const assignment: TrainingAssignmentResponse = {
      id: "assignment-1",
      organization_id: "organization-1",
      location_id: "location-1",
      training_id: "training-1",
      employee_profile_id: "employee-1",
      training_version_id: "training-version-1",
      status: "assigned",
      source: "admin",
      previous_assignment_id: null,
      source_rollout_id: null,
      assigned_at: "2026-08-28T08:00:00Z",
      started_at: null,
      completed_at: null,
      revoked_at: null,
      revoke_reason: null,
      revoke_note: null,
    };
    let current: TrainingAssignmentResponse | null = null;
    let history: TrainingAssignmentResponse[] = [];
    const client = adminClient(<T,>(path: string, options?: RequestOptions) => {
      if (path.endsWith("/locations")) return Promise.resolve([activeEmployee.location] as T);
      if (path.endsWith("/operational-roles"))
        return Promise.resolve([activeEmployee.operational_role] as T);
      if (path.endsWith("/training-assignments") && !options?.method)
        return Promise.resolve({ current, history, progress: null } as T);
      if (path.endsWith("/training-assignments") && options?.method === "POST") {
        mutations.push({ path, options });
        current = assignment;
        return Promise.resolve(assignment as T);
      }
      if (path.endsWith("/training-assignments/assignment-1/revoke")) {
        mutations.push({ path, options });
        current = null;
        history = [
          {
            ...assignment,
            status: "revoked",
            revoked_at: "2026-08-28T10:00:00Z",
            revoke_reason: "admin",
            revoke_note: "Зміна програми",
          },
        ];
        return Promise.resolve(history[0] as T);
      }
      if (path.endsWith("/training-assignments/assignment-1/reassign")) {
        mutations.push({ path, options });
        current = { ...assignment, id: "assignment-2", source: "reassign" };
        return Promise.resolve(current as T);
      }
      return Promise.resolve(activeEmployee as T);
    });
    const user = userEvent.setup();

    render(
      <SessionProvider client={client}>
        <MemoryRouter initialEntries={["/admin/employees/employee-1"]}>
          <Routes>
            <Route path="/admin/employees/:employeeId" element={<AdminEmployeeDetailPage />} />
          </Routes>
        </MemoryRouter>
      </SessionProvider>,
    );

    expect(
      await screen.findByRole("heading", { name: "Призначення навчання" }),
    ).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Призначити поточну версію" }));
    expect(await screen.findByText("Навчання призначено")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Причина відкликання"), "Зміна програми");
    await user.click(screen.getByRole("button", { name: "Відкликати призначення" }));
    await user.click(screen.getByRole("button", { name: "Підтвердити відкликання" }));
    expect(await screen.findByText("Призначення відкликано")).toBeInTheDocument();
    expect(screen.getByText("Зміна програми")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Призначити повторно" }));
    expect(await screen.findByText("Навчання призначено повторно")).toBeInTheDocument();
    expect(mutations).toHaveLength(3);
    for (const mutation of mutations) {
      expect(mutation.options?.csrfToken).toBe("csrf-safe");
      expect(typeof mutation.options?.idempotencyKey).toBe("string");
    }
  });

  it("pauses an active employee only after explicit confirmation", async () => {
    const activeEmployee: EmployeeDetail = {
      ...pendingEmployee,
      first_name: "Анна",
      last_name: "Коваль",
      membership_status: "active",
      profile_complete: true,
      activated_at: "2031-01-01T10:00:00Z",
    };
    const mutations: Array<{ path: string; options?: RequestOptions }> = [];
    const client = adminClient(<T,>(path: string, options?: RequestOptions) => {
      if (path.endsWith("/locations") || path.endsWith("/operational-roles")) {
        return Promise.resolve([] as T);
      }
      if (path.endsWith("/training-assignments")) {
        return Promise.resolve({ current: null, history: [], progress: null } as T);
      }
      if (path.endsWith("/pause")) {
        mutations.push({ path, options });
        return Promise.resolve({
          employee_id: activeEmployee.id,
          organization_id: activeEmployee.organization_id,
          membership_status: "active",
          training_participation_status: "paused",
          activated_at: activeEmployee.activated_at,
          disabled_at: null,
          training_paused_at: "2031-02-01T10:00:00Z",
          training_pause_reason_code: "scheduled_leave",
          training_pause_note: "Погоджена відсутність",
          planned_resume_at: "2031-02-03T08:30:00Z",
          disabled_reason_code: null,
          disabled_note: null,
        } as T);
      }
      return Promise.resolve(activeEmployee as T);
    });
    const user = userEvent.setup();

    render(
      <SessionProvider client={client}>
        <MemoryRouter initialEntries={["/admin/employees/employee-1"]}>
          <Routes>
            <Route path="/admin/employees/:employeeId" element={<AdminEmployeeDetailPage />} />
          </Routes>
        </MemoryRouter>
      </SessionProvider>,
    );

    await user.selectOptions(await screen.findByLabelText("Причина"), "scheduled_leave");
    await user.type(screen.getByLabelText("Примітка"), "Погоджена відсутність");
    await user.type(screen.getByLabelText("Заплановане відновлення"), "2031-02-03T10:30");
    const pauseButton = screen.getByRole("button", { name: "Призупинити навчання" });
    await user.click(pauseButton);

    expect(mutations).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Підтвердити паузу" }));

    expect(await screen.findByText("Навчання працівника призупинено")).toBeInTheDocument();
    expect(screen.getAllByText("Навчання призупинено").length).toBeGreaterThan(0);
    expect(screen.getByText("Погоджена відсутність")).toBeInTheDocument();
    expect(mutations).toHaveLength(1);
    expect(mutations[0]?.path).toBe("/organizations/organization-1/employees/employee-1/pause");
    expect(mutations[0]?.options?.method).toBe("POST");
    expect(mutations[0]?.options?.csrfToken).toBe("csrf-safe");
    expect(typeof mutations[0]?.options?.idempotencyKey).toBe("string");
    expect(mutations[0]?.options?.body).toEqual({
      reason_code: "scheduled_leave",
      note: "Погоджена відсутність",
      planned_resume_at: new Date("2031-02-03T10:30").toISOString(),
    });
  });

  it("keeps the visible lifecycle state when the server rejects a stale transition", async () => {
    const activeEmployee: EmployeeDetail = {
      ...pendingEmployee,
      membership_status: "active",
      profile_complete: true,
      activated_at: "2031-01-01T10:00:00Z",
    };
    const client = adminClient(<T,>(path: string) => {
      if (path.endsWith("/locations") || path.endsWith("/operational-roles")) {
        return Promise.resolve([] as T);
      }
      if (path.endsWith("/training-assignments")) {
        return Promise.resolve({ current: null, history: [], progress: null } as T);
      }
      if (path.endsWith("/pause")) {
        return Promise.reject(
          new ApiError(409, {
            code: "EMPLOYEE_LIFECYCLE_CONFLICT",
            message: "Стан працівника вже змінився. Оновіть сторінку.",
            field_errors: [],
            request_id: "request-1",
          }),
        );
      }
      return Promise.resolve(activeEmployee as T);
    });
    const user = userEvent.setup();

    render(
      <SessionProvider client={client}>
        <MemoryRouter initialEntries={["/admin/employees/employee-1"]}>
          <Routes>
            <Route path="/admin/employees/:employeeId" element={<AdminEmployeeDetailPage />} />
          </Routes>
        </MemoryRouter>
      </SessionProvider>,
    );

    await user.click(await screen.findByRole("button", { name: "Призупинити навчання" }));
    await user.click(screen.getByRole("button", { name: "Підтвердити паузу" }));

    expect(
      await screen.findByText("Стан працівника вже змінився. Оновіть сторінку."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Призупинити навчання" })).toBeInTheDocument();
    expect(screen.queryByText("Навчання працівника призупинено")).not.toBeInTheDocument();
  });
});

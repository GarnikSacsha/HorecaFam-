import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import type { ApiClient, RequestOptions } from "../api/client";
import type { AdminAttentionCase, AdminRetakeRequirement, SessionResponse } from "../api/contracts";
import { SessionProvider } from "../session/SessionContext";
import { AdminAttentionPage } from "./AdminAttentionPage";

const session: SessionResponse = {
  user: { id: "admin-1", email: "admin@example.com", preferred_locale: "uk" },
  session: { id: "session-1", absolute_expires_at: "2031-03-01T00:00:00Z", mfa_verified: true },
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

const attentionCase: AdminAttentionCase = {
  id: "attention-1",
  organization_id: "organization-1",
  location_id: "location-1",
  training_id: "training-1",
  employee_profile_id: "employee-12345678",
  case_type: "critical_allergen",
  severity: "critical",
  subject_key: "menu_item:item-1:allergen:allergen-1",
  state: "open",
  revision: 0,
  acknowledged_at: null,
  resolution_type: null,
  resolved_at: null,
  resolution_comment: null,
  critical_error_ids: ["critical-1"],
  retake_requirement_id: null,
  created_at: "2031-02-01T10:00:00Z",
  updated_at: "2031-02-01T10:00:00Z",
};

const proposedRequirement: AdminRetakeRequirement = {
  id: "requirement-1",
  organization_id: "organization-1",
  location_id: "location-1",
  training_id: "training-1",
  employee_profile_id: attentionCase.employee_profile_id,
  assignment_id: "assignment-1",
  target_assessment_id: "assessment-1",
  reason: "critical_error",
  state: "proposed",
  timing_state: null,
  permitted_action: "wait",
  source_result_id: null,
  source_attempt_id: null,
  source_attention_case_id: attentionCase.id,
  management_source_key: null,
  target_policy: { assessment_type: "menu_final_exam", minimum_result: "passed" },
  proposed_at: "2031-02-01T10:00:00Z",
  confirmed_at: null,
  due_at: "2031-02-08T10:00:00Z",
  clock_frozen_at: null,
  completion_attempt_id: null,
  completed_at: null,
  cancelled_at: null,
  cancellation_comment: null,
  revision: 0,
};

it("renders responsive queues, acknowledges and creates a proposed requirement explicitly", async () => {
  const requests: Array<{ path: string; options?: RequestOptions }> = [];
  const client: ApiClient = {
    getSession: () => Promise.resolve(session),
    request: <T,>(path: string, options?: RequestOptions) => {
      requests.push({ path, options });
      if (path === "/organizations/organization-1/attention" && !options?.method) {
        return Promise.resolve({ items: [attentionCase], next_cursor: null } as T);
      }
      if (path === "/organizations/organization-1/retake-requirements") {
        return Promise.resolve({ items: [], next_cursor: null } as T);
      }
      if (path.endsWith("/acknowledge")) {
        return Promise.resolve({
          ...attentionCase,
          state: "acknowledged",
          revision: 1,
          acknowledged_at: "2031-02-01T10:05:00Z",
        } as T);
      }
      if (
        path === "/organizations/organization-1/employees/employee-12345678/retake-requirements" &&
        options?.method === "POST"
      ) {
        return Promise.resolve(proposedRequirement as T);
      }
      throw new Error(`Unexpected request: ${path}`);
    },
  };
  const user = userEvent.setup();
  render(
    <SessionProvider client={client}>
      <MemoryRouter>
        <AdminAttentionPage />
      </MemoryRouter>
    </SessionProvider>,
  );

  expect(await screen.findByRole("table")).toBeInTheDocument();
  const openButtons = await screen.findAllByRole("button", { name: "Відкрити" });
  expect(screen.getAllByText("Критичний алерген").length).toBeGreaterThan(0);
  await user.click(openButtons[0]);
  await user.click(screen.getByRole("button", { name: "Взяти в роботу" }));

  expect(await screen.findByText("Кейс взято в роботу.")).toBeInTheDocument();
  const mutation = requests.find(({ path }) => path.endsWith("/acknowledge"));
  expect(mutation?.options?.csrfToken).toBe("csrf-safe");
  expect(mutation?.options?.idempotencyKey).toBeTruthy();

  await user.selectOptions(screen.getByLabelText("Джерело Attention"), attentionCase.id);
  await user.click(screen.getByRole("button", { name: "Створити проєкт" }));

  expect(
    await screen.findByText(
      "Проєкт вимоги створено. Перевірте дедлайн і підтвердьте окремою дією.",
    ),
  ).toBeInTheDocument();
  const create = requests.find(
    ({ path, options }) =>
      path.endsWith("/employees/employee-12345678/retake-requirements") &&
      options?.method === "POST",
  );
  expect(create?.options?.csrfToken).toBe("csrf-safe");
  expect(create?.options?.idempotencyKey).toBeTruthy();
  expect(create?.options?.body).not.toHaveProperty("target_assessment_id");
});

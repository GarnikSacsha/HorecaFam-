import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import type { ApiClient, RequestOptions } from "../api/client";
import type { SessionResponse } from "../api/contracts";
import { AdminAuditPage } from "../admin/AdminAuditPage";
import { SessionProvider } from "../session/SessionContext";
import { OperatorAuditPage } from "./OperatorAuditPage";
import { OperatorJobDetailPage } from "./OperatorJobDetailPage";
import { OperatorJobsPage } from "./OperatorJobsPage";

const operatorSession: SessionResponse = {
  user: { id: "operator-1", email: "operator@example.com", preferred_locale: "uk" },
  session: {
    id: "session-operator",
    absolute_expires_at: "2031-03-01T00:00:00Z",
    mfa_verified: true,
  },
  organization_access: [],
  platform_operator: true,
  csrf_token: "operator-csrf",
};

const adminSession: SessionResponse = {
  ...operatorSession,
  user: { ...operatorSession.user, id: "admin-1", email: "admin@example.com" },
  organization_access: [
    {
      organization_id: "organization-1",
      membership_status: null,
      is_employee: false,
      is_organization_admin: true,
    },
  ],
  platform_operator: false,
};

const job = {
  id: "11111111-1111-4111-8111-111111111111",
  organization_id: null,
  job_type: "attempt_expiry" as const,
  status: "failed" as const,
  priority: 0,
  attempt_count: 5,
  max_attempts: 5,
  next_run_at: "2031-02-03T12:00:00Z",
  last_error_code: "JOB_HANDLER_ERROR",
  last_error_message: "Approved Job handler failed.",
  started_at: "2031-02-03T11:55:00Z",
  completed_at: null,
  failed_at: "2031-02-03T11:59:00Z",
  created_at: "2031-02-03T11:50:00Z",
  updated_at: "2031-02-03T11:59:00Z",
};

const event = {
  id: "22222222-2222-4222-8222-222222222222",
  organization_id: "organization-1",
  actor_user_id: "admin-1",
  actor_type: "user" as const,
  action: "employee.paused",
  target_type: "employee_profile",
  target_id: "33333333-3333-4333-8333-333333333333",
  old_values: null,
  new_values: { reason_code: "leave" },
  request_id: "44444444-4444-4444-8444-444444444444",
  outcome: "success" as const,
  error_code: null,
  created_at: "2031-02-03T12:00:00Z",
};

function renderWithSession(session: SessionResponse, client: ApiClient, element: React.ReactNode) {
  return render(
    <SessionProvider client={client}>
      <MemoryRouter>{element}</MemoryRouter>
    </SessionProvider>,
  );
}

it("renders Organization audit with controlled filters and responsive event views", async () => {
  const requests: string[] = [];
  const client: ApiClient = {
    getSession: () => Promise.resolve(adminSession),
    request: <T,>(path: string) => {
      requests.push(path);
      return Promise.resolve({ items: [event], next_cursor: null } as T);
    },
  };
  const user = userEvent.setup();
  renderWithSession(adminSession, client, <AdminAuditPage />);

  expect(
    await screen.findByRole("table", { name: "Події аудиту організації" }),
  ).toBeInTheDocument();
  expect(screen.getAllByText("employee.paused").length).toBeGreaterThan(0);
  await user.type(screen.getByLabelText("Дія"), "employee.paused");
  await user.click(screen.getByRole("button", { name: "Застосувати фільтри" }));

  expect(requests.at(-1)).toContain("action=employee.paused");
  expect(screen.getByLabelText("Мобільний список подій аудиту")).toBeInTheDocument();
});

it("renders Operator Jobs and system audit without generic mutation controls", async () => {
  const client: ApiClient = {
    getSession: () => Promise.resolve(operatorSession),
    request: <T,>(path: string) => {
      if (path === "/operator/jobs") {
        return Promise.resolve({ items: [job], next_cursor: null } as T);
      }
      if (path === "/operator/audit-events") {
        return Promise.resolve({ items: [event], next_cursor: null } as T);
      }
      throw new Error(`Unexpected request: ${path}`);
    },
  };
  renderWithSession(
    operatorSession,
    client,
    <>
      <OperatorJobsPage />
      <OperatorAuditPage />
    </>,
  );

  const jobLinks = await screen.findAllByRole("link", { name: "Відкрити Job" });
  expect(jobLinks[0]).toHaveAttribute("href", `/operator/jobs/${job.id}`);
  expect((await screen.findAllByText("employee.paused")).length).toBeGreaterThan(0);
  expect(screen.queryByRole("button", { name: /видалити|редагувати/i })).not.toBeInTheDocument();
});

it("requires a bounded reason and reuses one intent key for retry feedback", async () => {
  const requests: Array<{ path: string; options?: RequestOptions }> = [];
  const client: ApiClient = {
    getSession: () => Promise.resolve(operatorSession),
    request: <T,>(path: string, options?: RequestOptions) => {
      requests.push({ path, options });
      if (!options?.method) {
        return Promise.resolve({
          ...job,
          request_id: "55555555-5555-4555-8555-555555555555",
          locked_at: null,
          heartbeat_at: null,
          attempts: [
            {
              id: "66666666-6666-4666-8666-666666666666",
              attempt_number: 5,
              started_at: job.started_at,
              heartbeat_last_seen_at: job.started_at,
              finished_at: job.failed_at,
              outcome: "failed",
              error_code: job.last_error_code,
              error_message: job.last_error_message,
              next_retry_at: null,
            },
          ],
          delivery: null,
        } as T);
      }
      return Promise.resolve({
        source_job_id: job.id,
        job: { ...job, id: "77777777-7777-4777-8777-777777777777", status: "pending" },
        replayed: false,
      } as T);
    },
  };
  const user = userEvent.setup();
  render(
    <SessionProvider client={client}>
      <MemoryRouter initialEntries={[`/operator/jobs/${job.id}`]}>
        <Routes>
          <Route path="/operator/jobs/:jobId" element={<OperatorJobDetailPage />} />
        </Routes>
      </MemoryRouter>
    </SessionProvider>,
  );

  await user.click(await screen.findByRole("button", { name: "Повторити Failed Job" }));
  const reason = screen.getByLabelText("Причина повтору");
  expect(reason).toHaveFocus();
  await user.type(reason, "Перевірено тимчасову помилку worker");
  await user.click(screen.getByRole("button", { name: "Підтвердити повтор" }));

  expect(await screen.findByText("Створено контрольований повтор Job.")).toBeInTheDocument();
  const retry = requests.find(({ options }) => options?.method === "POST");
  expect(retry?.options?.csrfToken).toBe("operator-csrf");
  expect(retry?.options?.idempotencyKey).toBeTruthy();
  expect(retry?.options?.body).toEqual({ reason: "Перевірено тимчасову помилку worker" });
  expect(screen.getByRole("link", { name: "Відкрити новий Job" })).toHaveAttribute(
    "href",
    "/operator/jobs/77777777-7777-4777-8777-777777777777",
  );
});

import { expect, test, type Route } from "@playwright/test";

const anonymousError = {
  code: "UNAUTHENTICATED",
  message: "Сесію не знайдено.",
  field_errors: [],
  request_id: "request-anonymous",
};

const enrolledSession = {
  user: { id: "admin-1", email: "admin@example.com", preferred_locale: "uk" },
  session: {
    id: "session-1",
    absolute_expires_at: "2031-01-01T00:00:00Z",
    mfa_verified: true,
  },
  organization_access: [],
  platform_operator: false,
  csrf_token: "csrf-safe",
};

const adminOrganizationSession = {
  ...enrolledSession,
  organization_access: [
    {
      organization_id: "organization-1",
      membership_status: null,
      is_employee: false,
      is_organization_admin: true,
    },
  ],
};

const operatorSession = {
  ...enrolledSession,
  platform_operator: true,
};

const failedJob = {
  id: "00000000-0000-4000-8000-000000000077",
  organization_id: "organization-1",
  job_type: "password_reset_email",
  status: "failed",
  priority: 0,
  attempt_count: 5,
  max_attempts: 5,
  next_run_at: "2031-02-01T10:00:00Z",
  last_error_code: "DELIVERY_FAILED",
  last_error_message: "Delivery was not accepted.",
  started_at: "2031-02-01T09:55:00Z",
  completed_at: null,
  failed_at: "2031-02-01T10:00:00Z",
  created_at: "2031-02-01T09:50:00Z",
  updated_at: "2031-02-01T10:00:00Z",
  request_id: "00000000-0000-4000-8000-000000000078",
  locked_at: null,
  heartbeat_at: null,
  attempts: [
    {
      id: "00000000-0000-4000-8000-000000000079",
      attempt_number: 5,
      started_at: "2031-02-01T09:59:00Z",
      heartbeat_last_seen_at: "2031-02-01T09:59:30Z",
      finished_at: "2031-02-01T10:00:00Z",
      outcome: "failed",
      error_code: "DELIVERY_FAILED",
      error_message: "Delivery was not accepted.",
      next_retry_at: null,
    },
  ],
  delivery: null,
};

const auditEvent = {
  id: "00000000-0000-4000-8000-000000000080",
  organization_id: "organization-1",
  actor_user_id: "admin-1",
  actor_type: "user",
  action: "employee.paused",
  target_type: "employee_profile",
  target_id: "employee-1",
  old_values: { training_participation_status: "active" },
  new_values: { training_participation_status: "paused" },
  request_id: "00000000-0000-4000-8000-000000000081",
  outcome: "success",
  error_code: null,
  created_at: "2031-02-01T10:00:00Z",
};

test("password recovery keeps its token ephemeral and ends in a one-time success state", async ({
  page,
}) => {
  const requests: Array<{ pathname: string; body: unknown }> = [];
  await page.route("**/api/v1/**", async (route: Route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname.replace("/api/v1", "");
    if (request.method() === "GET" && pathname === "/auth/session") {
      await route.fulfill({ status: 401, json: anonymousError });
      return;
    }
    requests.push({ pathname, body: request.postDataJSON() });
    if (pathname === "/auth/password/forgot") {
      await route.fulfill({ status: 202, json: { status: "accepted" } });
      return;
    }
    if (pathname === "/auth/password/reset") {
      await route.fulfill({ status: 204 });
      return;
    }
    await route.fulfill({ status: 404, json: { code: "UNEXPECTED_TEST_REQUEST" } });
  });

  await page.goto("/forgot-password");
  await page.getByLabel("Робоча електронна пошта").fill("user@example.com");
  await page.getByRole("button", { name: "Надіслати інструкцію" }).click();
  await expect(page.getByRole("status")).toContainText("Якщо адреса зареєстрована");

  await page.goto("/reset-password?token=browser-reset-token-that-is-long-enough");
  await page.getByLabel("Новий пароль", { exact: true }).fill("correct horse battery staple");
  await page.getByLabel("Повторіть новий пароль").fill("correct horse battery staple");
  await page.getByRole("button", { name: "Змінити пароль" }).click();
  await expect(page.getByRole("status")).toContainText("Пароль змінено");
  await expect(page).toHaveURL(/token=browser-reset-token-that-is-long-enough/);
  expect(
    await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length })),
  ).toEqual({ local: 0, session: 0 });
  expect(requests).toEqual([
    { pathname: "/auth/password/forgot", body: { email: "user@example.com" } },
    {
      pathname: "/auth/password/reset",
      body: {
        token: "browser-reset-token-that-is-long-enough",
        new_password: "correct horse battery staple",
      },
    },
  ]);
});

test("first privileged login reveals recovery codes only after MFA enrollment", async ({
  page,
}) => {
  await page.route("**/api/v1/**", async (route: Route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname.replace("/api/v1", "");
    if (request.method() === "GET" && pathname === "/auth/session") {
      await route.fulfill({ status: 401, json: anonymousError });
      return;
    }
    if (pathname === "/auth/login") {
      await route.fulfill({
        status: 202,
        json: { status: "mfa_enrollment_required", expires_at: "2031-01-01T00:05:00Z" },
      });
      return;
    }
    if (pathname === "/auth/mfa/enrollment/start") {
      await route.fulfill({
        json: {
          secret: "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567",
          otpauth_uri: "otpauth://totp/Bacara:admin",
          expires_at: "2031-01-01T00:05:00Z",
        },
      });
      return;
    }
    if (pathname === "/auth/mfa/enrollment/confirm") {
      await route.fulfill({
        json: {
          session: enrolledSession,
          recovery_codes: ["ABCD-EFGH-IJKL-MNOP", "QRST-UVWX-YZ23-4567"],
        },
      });
      return;
    }
    await route.fulfill({ status: 404, json: { code: "UNEXPECTED_TEST_REQUEST" } });
  });

  await page.goto("/login");
  await page.getByLabel("Робоча електронна пошта").fill("admin@example.com");
  await page.getByLabel("Пароль").fill("correct horse battery staple");
  await page.getByRole("button", { name: "Увійти" }).click();
  await expect(page.getByRole("heading", { name: "Налаштуйте двофакторний вхід" })).toBeVisible();
  await page.getByLabel("Код підтвердження").fill("123456");
  await page.getByRole("button", { name: "Підтвердити й отримати резервні коди" }).click();

  await expect(page.getByText("ABCD-EFGH-IJKL-MNOP")).toBeVisible();
  expect(
    await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length })),
  ).toEqual({ local: 0, session: 0 });
  expect(await page.evaluate<number>("document.documentElement.scrollWidth")).toBeLessThanOrEqual(
    (page.viewportSize()?.width ?? 0) + 1,
  );
});

test("admin confirms pause, resume, disable and reactivation from the employee profile", async ({
  page,
}) => {
  const mutations: Array<{
    action: string;
    body: unknown;
    csrf: string | undefined;
    idempotencyKey: string | undefined;
  }> = [];
  const employee = {
    id: "employee-1",
    organization_id: "organization-1",
    email: "employee@example.com",
    first_name: "Анна",
    last_name: "Коваль",
    membership_status: "active",
    operational_role: null,
    location: null,
    profile_complete: true,
    created_at: "2031-01-01T09:00:00Z",
    updated_at: "2031-01-01T09:00:00Z",
    membership_created_at: "2031-01-01T09:00:00Z",
    activated_at: "2031-01-01T10:00:00Z",
    disabled_at: null as string | null,
    training_participation_status: "active",
    training_paused_at: null as string | null,
    training_pause_reason_code: null as string | null,
    training_pause_note: null as string | null,
    planned_resume_at: null as string | null,
    disabled_reason_code: null as string | null,
    disabled_note: null as string | null,
  };

  await page.route("**/api/v1/**", async (route: Route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname.replace("/api/v1", "");
    if (request.method() === "GET" && pathname === "/auth/session") {
      await route.fulfill({ json: adminOrganizationSession });
      return;
    }
    if (request.method() === "GET" && pathname.endsWith("/employees/employee-1")) {
      await route.fulfill({ json: employee });
      return;
    }
    if (
      request.method() === "GET" &&
      (pathname.endsWith("/locations") || pathname.endsWith("/operational-roles"))
    ) {
      await route.fulfill({ json: [] });
      return;
    }
    if (request.method() === "GET" && pathname.endsWith("/training-assignments")) {
      await route.fulfill({ json: { current: null, history: [], progress: null } });
      return;
    }

    const action = pathname.split("/").at(-1) ?? "";
    if (
      request.method() === "POST" &&
      ["pause", "resume", "disable", "reactivate"].includes(action)
    ) {
      mutations.push({
        action,
        body: request.postDataJSON(),
        csrf: request.headers()["x-csrf-token"],
        idempotencyKey: request.headers()["idempotency-key"],
      });
      if (action === "pause") {
        employee.training_participation_status = "paused";
        employee.training_paused_at = "2031-02-01T10:00:00Z";
        employee.training_pause_reason_code = "scheduled_leave";
        employee.training_pause_note = "Погоджена відсутність";
        employee.planned_resume_at = "2031-02-03T08:30:00Z";
      }
      if (action === "resume") {
        employee.training_participation_status = "active";
        employee.training_paused_at = null;
        employee.training_pause_reason_code = null;
        employee.training_pause_note = null;
        employee.planned_resume_at = null;
      }
      if (action === "disable") {
        employee.membership_status = "disabled";
        employee.disabled_at = "2031-02-02T10:00:00Z";
        employee.disabled_reason_code = "access_review";
        employee.disabled_note = "Перевірка доступу";
      }
      if (action === "reactivate") {
        employee.membership_status = "active";
        employee.disabled_at = null;
        employee.disabled_reason_code = null;
        employee.disabled_note = null;
      }
      await route.fulfill({
        json: {
          employee_id: employee.id,
          organization_id: employee.organization_id,
          membership_status: employee.membership_status,
          training_participation_status: employee.training_participation_status,
          activated_at: employee.activated_at,
          disabled_at: employee.disabled_at,
          training_paused_at: employee.training_paused_at,
          training_pause_reason_code: employee.training_pause_reason_code,
          training_pause_note: employee.training_pause_note,
          planned_resume_at: employee.planned_resume_at,
          disabled_reason_code: employee.disabled_reason_code,
          disabled_note: employee.disabled_note,
        },
      });
      return;
    }
    await route.fulfill({ status: 404, json: { code: "UNEXPECTED_TEST_REQUEST" } });
  });

  await page.goto("/admin/employees/employee-1");
  await page.getByLabel("Причина").selectOption("scheduled_leave");
  await page.getByLabel("Примітка").fill("Погоджена відсутність");
  await page.getByLabel("Заплановане відновлення").fill("2031-02-03T10:30");
  await page.getByRole("button", { name: "Призупинити навчання" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", { name: "Підтвердити паузу" }).click();
  await expect(page.getByText("Навчання працівника призупинено")).toBeVisible();

  await page.getByRole("button", { name: "Відновити навчання" }).click();
  await page.getByRole("button", { name: "Підтвердити відновлення" }).click();
  await expect(page.getByText("Навчання працівника відновлено")).toBeVisible();

  await page.getByLabel("Причина").selectOption("access_review");
  await page.getByLabel("Примітка").fill("Перевірка доступу");
  await page.getByRole("button", { name: "Вимкнути доступ" }).click();
  await page.getByRole("button", { name: "Підтвердити вимкнення" }).click();
  await expect(page.getByText("Доступ працівника вимкнено")).toBeVisible();

  await page.getByRole("button", { name: "Відновити доступ" }).click();
  await page.getByRole("button", { name: "Підтвердити відновлення" }).click();
  await expect(page.getByText("Доступ працівника відновлено")).toBeVisible();

  expect(mutations.map(({ action }) => action)).toEqual([
    "pause",
    "resume",
    "disable",
    "reactivate",
  ]);
  expect(mutations[0]?.body).toMatchObject({
    reason_code: "scheduled_leave",
    note: "Погоджена відсутність",
  });
  expect(mutations[2]?.body).toEqual({
    reason_code: "access_review",
    note: "Перевірка доступу",
  });
  for (const mutation of mutations) {
    expect(mutation.csrf).toBe("csrf-safe");
    expect(mutation.idempotencyKey).toBeTruthy();
  }
  expect(await page.evaluate<number>("document.documentElement.scrollWidth")).toBeLessThanOrEqual(
    (page.viewportSize()?.width ?? 0) + 1,
  );
});

test("organization audit stays tenant-scoped and responsive", async ({ page }) => {
  const requestedUrls: string[] = [];
  await page.route("**/api/v1/**", async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const pathname = url.pathname.replace("/api/v1", "");
    if (request.method() === "GET" && pathname === "/auth/session") {
      await route.fulfill({ json: adminOrganizationSession });
      return;
    }
    if (request.method() === "GET" && pathname === "/organizations/organization-1/audit-events") {
      requestedUrls.push(url.toString());
      await route.fulfill({ json: { items: [auditEvent], next_cursor: null } });
      return;
    }
    await route.fulfill({ status: 404, json: { code: "UNEXPECTED_TEST_REQUEST" } });
  });

  await page.goto("/admin/audit");
  await expect(page.getByRole("heading", { name: "Аудит організації" })).toBeVisible();
  await expect(page.locator("strong:visible").filter({ hasText: "employee.paused" })).toBeVisible();
  await page.getByLabel("Дія").fill("employee.paused");
  await page.getByLabel("Тип актора").selectOption("user");
  await page.getByRole("button", { name: "Застосувати фільтри" }).click();
  await expect.poll(() => requestedUrls.at(-1) ?? "").toContain("actor_type=user");
  expect(requestedUrls.at(-1)).toContain("action=employee.paused");
  expect(requestedUrls.at(-1)).toContain("actor_type=user");
  expect(requestedUrls.every((url) => url.includes("organization-1"))).toBeTruthy();
  expect(await page.evaluate<number>("document.documentElement.scrollWidth")).toBeLessThanOrEqual(
    (page.viewportSize()?.width ?? 0) + 1,
  );
});

test("operator retries only a Failed Job with a bounded reason and sees system audit", async ({
  page,
}) => {
  const retries: Array<{
    body: unknown;
    csrf: string | undefined;
    idempotencyKey: string | undefined;
  }> = [];
  await page.route("**/api/v1/**", async (route: Route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname.replace("/api/v1", "");
    if (request.method() === "GET" && pathname === "/auth/session") {
      await route.fulfill({ json: operatorSession });
      return;
    }
    if (request.method() === "GET" && pathname === `/operator/jobs/${failedJob.id}`) {
      await route.fulfill({ json: failedJob });
      return;
    }
    if (request.method() === "POST" && pathname === `/operator/jobs/${failedJob.id}/retry`) {
      retries.push({
        body: request.postDataJSON(),
        csrf: request.headers()["x-csrf-token"],
        idempotencyKey: request.headers()["idempotency-key"],
      });
      await route.fulfill({
        status: 201,
        json: {
          source_job_id: failedJob.id,
          job: {
            ...failedJob,
            id: "00000000-0000-4000-8000-000000000082",
            status: "pending",
            attempt_count: 0,
          },
          replayed: false,
        },
      });
      return;
    }
    if (request.method() === "GET" && pathname === "/operator/audit-events") {
      await route.fulfill({
        json: {
          items: [{ ...auditEvent, organization_id: null, action: "operator.job_retry_created" }],
          next_cursor: null,
        },
      });
      return;
    }
    await route.fulfill({ status: 404, json: { code: "UNEXPECTED_TEST_REQUEST" } });
  });

  await page.goto(`/operator/jobs/${failedJob.id}`);
  await page.getByRole("button", { name: "Повторити Failed Job" }).click();
  await expect(page.getByLabel("Причина повтору")).toBeFocused();
  await page.getByLabel("Причина повтору").fill("Підтверджено після перевірки доставки");
  await page.getByRole("button", { name: "Підтвердити повтор" }).click();
  await expect(page.getByRole("status")).toContainText("Створено контрольований повтор Job");
  expect(retries).toHaveLength(1);
  expect(retries[0]?.body).toEqual({ reason: "Підтверджено після перевірки доставки" });
  expect(retries[0]?.csrf).toBe("csrf-safe");
  expect(retries[0]?.idempotencyKey).toBeTruthy();

  await page.goto("/operator/audit");
  await expect(page.getByRole("heading", { name: "Системний аудит" })).toBeVisible();
  await expect(
    page.locator("strong:visible").filter({ hasText: "operator.job_retry_created" }),
  ).toBeVisible();
  expect(await page.evaluate<number>("document.documentElement.scrollWidth")).toBeLessThanOrEqual(
    (page.viewportSize()?.width ?? 0) + 1,
  );
});

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

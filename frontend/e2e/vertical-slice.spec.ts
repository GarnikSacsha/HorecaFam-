import { expect, test, type Page, type Request, type Route } from "@playwright/test";

type CurrentUser = "anonymous" | "admin" | "employee";
type EmployeeStatus = "pending" | "active";

const organization = {
  id: "organization-1",
  name: "Bacara Kyiv",
  status: "active",
  default_locale: "uk",
  timezone: "Europe/Kyiv",
};

const role = {
  id: "role-1",
  organization_id: organization.id,
  code: "waiter",
  name_uk: "Офіціант",
  status: "active",
};

const location = {
  id: "location-1",
  organization_id: organization.id,
  name: "Хрещатик",
  status: "active",
  address: null,
  timezone: "Europe/Kyiv",
};

function sessionFor(user: Exclude<CurrentUser, "anonymous">, status: EmployeeStatus) {
  const admin = user === "admin";
  return {
    user: {
      id: admin ? "admin-1" : "employee-user-1",
      email: admin ? "admin@example.com" : "employee@example.com",
      preferred_locale: "uk",
    },
    session: {
      id: admin ? "admin-session-1" : "employee-session-1",
      absolute_expires_at: "2026-09-01T00:00:00Z",
      mfa_verified: admin,
    },
    organization_access: [
      {
        organization_id: organization.id,
        membership_status: admin ? null : status,
        is_employee: !admin,
        is_organization_admin: admin,
      },
    ],
    platform_operator: false,
    csrf_token: "csrf-safe",
  };
}

function assertProtectedMutation(request: Request, idempotent = false) {
  expect(request.headers()["x-csrf-token"]).toBe("csrf-safe");
  if (idempotent) expect(request.headers()["idempotency-key"]).toBeTruthy();
}

async function loginAsAdmin(page: Page) {
  await page.getByLabel("Робоча електронна пошта").fill("admin@example.com");
  await page.getByLabel("Пароль").fill("correct horse battery staple");
  await page.getByRole("button", { name: "Увійти" }).click();
  await page.getByLabel("Код підтвердження").fill("123456");
  await page.getByRole("button", { name: "Підтвердити" }).click();
  await expect(page.getByRole("heading", { name: "Працівники", level: 1 })).toBeVisible();
}

test("admin invitation, pending setup, activation and active employee home", async ({ page }) => {
  let currentUser: CurrentUser = "anonymous";
  let employeeStatus: EmployeeStatus = "pending";
  let profileComplete = false;
  let firstName: string | null = null;
  let lastName: string | null = null;

  const employee = () => ({
    id: "employee-1",
    organization_id: organization.id,
    email: "employee@example.com",
    first_name: firstName,
    last_name: lastName,
    membership_status: employeeStatus,
    operational_role: profileComplete ? role : null,
    location: profileComplete ? location : null,
    profile_complete: profileComplete,
    created_at: "2026-08-27T00:00:00Z",
    updated_at: "2026-08-27T10:00:00Z",
    membership_created_at: "2026-08-27T00:00:00Z",
    activated_at: employeeStatus === "active" ? "2026-08-27T10:00:00Z" : null,
    disabled_at: null,
  });

  const ownProfile = () => ({
    id: "employee-1",
    organization: { id: organization.id, name: organization.name },
    membership_status: employeeStatus,
    first_name: firstName,
    last_name: lastName,
    operational_role: profileComplete ? role : null,
    location: profileComplete ? location : null,
    profile_complete: profileComplete,
    updated_at: "2026-08-27T10:00:00Z",
  });

  await page.route("**/api/v1/**", async (route: Route) => {
    const request = route.request();
    const method = request.method();
    const pathname = new URL(request.url()).pathname.replace("/api/v1", "");

    if (method === "GET" && pathname === "/auth/session") {
      if (currentUser === "anonymous") {
        await route.fulfill({
          status: 401,
          json: {
            code: "UNAUTHENTICATED",
            message: "Сесію не знайдено.",
            field_errors: [],
            request_id: "request-session-anonymous",
          },
        });
        return;
      }
      await route.fulfill({ json: sessionFor(currentUser, employeeStatus) });
      return;
    }

    if (method === "POST" && pathname === "/auth/login") {
      const body = request.postDataJSON() as { email: string };
      if (body.email === "admin@example.com") {
        await route.fulfill({
          json: { status: "mfa_required", expires_at: "2026-08-27T20:00:00Z" },
        });
        return;
      }
      currentUser = "employee";
      await route.fulfill({ json: sessionFor("employee", employeeStatus) });
      return;
    }

    if (method === "POST" && pathname === "/auth/mfa/verify") {
      currentUser = "admin";
      await route.fulfill({ json: sessionFor("admin", employeeStatus) });
      return;
    }

    if (method === "POST" && pathname === "/auth/logout") {
      assertProtectedMutation(request);
      currentUser = "anonymous";
      await route.fulfill({ status: 204 });
      return;
    }

    if (method === "POST" && pathname === "/invitations/validate") {
      await route.fulfill({
        json: {
          status: "valid",
          organization_id: organization.id,
          organization_name: organization.name,
          email_masked: "e***@example.com",
          acceptance_mode: "activate_access",
          expires_at: "2026-08-30T00:00:00Z",
        },
      });
      return;
    }

    if (method === "POST" && pathname === "/invitations/accept") {
      currentUser = "employee";
      employeeStatus = "pending";
      await route.fulfill({
        json: {
          ...sessionFor("employee", "pending"),
          status: "accepted",
          acceptance_mode: "activate_access",
          membership: {
            id: "membership-1",
            organization_id: organization.id,
            employee_profile_id: "employee-1",
            status: "pending",
          },
        },
      });
      return;
    }

    if (method === "GET" && pathname === `/organizations/${organization.id}`) {
      await route.fulfill({ json: organization });
      return;
    }

    if (method === "GET" && pathname === `/organizations/${organization.id}/employees`) {
      await route.fulfill({ json: { items: [employee()], next_cursor: null } });
      return;
    }

    if (method === "POST" && pathname === `/organizations/${organization.id}/invitations`) {
      assertProtectedMutation(request, true);
      await route.fulfill({
        status: 201,
        json: { id: "invitation-1", email: "new@example.com" },
      });
      return;
    }

    if (method === "GET" && pathname === `/organizations/${organization.id}/employees/employee-1`) {
      await route.fulfill({ json: employee() });
      return;
    }

    if (method === "GET" && pathname === `/organizations/${organization.id}/locations`) {
      await route.fulfill({ json: [location] });
      return;
    }

    if (method === "GET" && pathname === `/organizations/${organization.id}/operational-roles`) {
      await route.fulfill({ json: [role] });
      return;
    }

    if (
      method === "PATCH" &&
      pathname === `/organizations/${organization.id}/employees/employee-1`
    ) {
      assertProtectedMutation(request);
      const body = request.postDataJSON() as { first_name: string; last_name: string };
      firstName = body.first_name;
      lastName = body.last_name;
      profileComplete = true;
      await route.fulfill({ json: employee() });
      return;
    }

    if (
      method === "POST" &&
      pathname === `/organizations/${organization.id}/employees/employee-1/activate`
    ) {
      assertProtectedMutation(request, true);
      employeeStatus = "active";
      await route.fulfill({
        json: {
          employee_id: "employee-1",
          organization_id: organization.id,
          membership_status: "active",
          training_participation_status: "active",
          activated_at: "2026-08-27T10:00:00Z",
        },
      });
      return;
    }

    if (method === "GET" && pathname === "/me/profile") {
      await route.fulfill({ json: { profiles: [ownProfile()] } });
      return;
    }

    await route.fulfill({
      status: 404,
      json: {
        code: "UNEXPECTED_TEST_REQUEST",
        message: `${method} ${pathname}`,
        field_errors: [],
        request_id: "request-unexpected",
      },
    });
  });

  await page.goto("/login");
  await loginAsAdmin(page);

  await page.getByLabel("Електронна пошта нового працівника").fill("new@example.com");
  await page.getByRole("button", { name: "Надіслати запрошення" }).click();
  await expect(page.getByRole("status")).toContainText("new@example.com");

  await page.getByRole("button", { name: "Вийти" }).click();
  await page.goto("/invite?token=invitation-safe");
  await expect(page.getByRole("heading", { name: organization.name })).toBeVisible();
  await page.getByLabel("Створіть пароль").fill("strong-password");
  await page.getByLabel("Повторіть пароль").fill("strong-password");
  await page.getByRole("button", { name: "Прийняти запрошення" }).click();
  await expect(page.getByRole("heading", { name: "Майже готово" })).toBeVisible();
  await expect(page.getByText("Очікує налаштування адміністратором")).toBeVisible();
  await expect(page.getByRole("button", { name: /активувати/i })).toHaveCount(0);

  await page.getByRole("button", { name: "Вийти" }).click();
  await loginAsAdmin(page);
  await page
    .getByRole("link", { name: /Відкрити/ })
    .first()
    .click();

  await page.getByLabel("Ім’я").fill("Анна");
  await page.getByLabel("Прізвище").fill("Коваль");
  await page.getByLabel("Роль").selectOption(role.id);
  await page.getByLabel("Локація").selectOption(location.id);
  await page.getByRole("button", { name: "Зберегти профіль" }).click();
  await expect(page.getByRole("status")).toContainText("Профіль збережено");

  await page.getByRole("button", { name: "Активувати працівника" }).click();
  const dialog = page.getByRole("dialog", { name: "Активувати працівника?" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Підтвердити активацію" }).click();
  await expect(page.getByRole("status")).toHaveText("Працівника активовано");

  await page.getByRole("button", { name: "Вийти" }).click();
  await page.getByLabel("Робоча електронна пошта").fill("employee@example.com");
  await page.getByLabel("Пароль").fill("strong-password");
  await page.getByRole("button", { name: "Увійти" }).click();

  await expect(page.getByRole("heading", { name: "Вітаємо, Анна" })).toBeVisible();
  await expect(page.getByText("Навчання ще не призначено")).toBeVisible();
  await expect(page.getByText(/%/)).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Практика" })).toBeDisabled();
  await expect(page.getByRole("button", { name: /розпочати.*(іспит|практик)/i })).toHaveCount(0);
});

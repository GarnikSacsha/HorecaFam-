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

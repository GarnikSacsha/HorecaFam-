import { expect, test } from "@playwright/test";

test("other-device logout is retryable and keeps the current page", async ({ page }, testInfo) => {
  let attempts = 0;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/auth/session")
      return route.fulfill({
        json: {
          user: { id: "user-1", email: "employee@example.com", preferred_locale: "uk" },
          session: {
            id: "session-1",
            absolute_expires_at: "2031-01-01T00:00:00Z",
            mfa_verified: false,
          },
          organization_access: [
            {
              organization_id: "org-1",
              membership_status: "pending",
              is_employee: true,
              is_organization_admin: false,
            },
          ],
          platform_operator: false,
          csrf_token: "test-csrf",
        },
      });
    if (path === "/api/v1/me/profile")
      return route.fulfill({
        json: {
          profiles: [
            {
              id: "employee-1",
              organization: { id: "org-1", name: "Test venue" },
              membership_status: "pending",
              first_name: null,
              last_name: null,
              operational_role: null,
              location: null,
              profile_complete: false,
              updated_at: "2026-09-09T00:00:00Z",
            },
          ],
        },
      });
    expect(path).toBe("/api/v1/auth/logout-all");
    expect(route.request().method()).toBe("POST");
    expect(route.request().headers()["x-csrf-token"]).toBe("test-csrf");
    attempts++;
    return route.fulfill({ status: attempts === 1 ? 503 : 204 });
  });
  await page.goto("/employee/pending");
  const button = page.getByRole("button", { name: "Вийти з інших пристроїв" });
  await button.click();
  await expect(page.getByRole("alert")).toContainText("Не вдалося завершити інші сеанси.");
  await button.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("status")).toContainText("Поточний сеанс збережено.");
  await expect(page).toHaveURL(/\/employee\/pending$/);
  await expect(page.getByRole("button", { name: "Вийти", exact: true })).toBeEnabled();
  expect(await page.evaluate("document.documentElement.scrollWidth <= innerWidth")).toBe(true);
  expect(attempts).toBe(2);
  await page.screenshot({ path: testInfo.outputPath("logout-others.png"), fullPage: true });
});

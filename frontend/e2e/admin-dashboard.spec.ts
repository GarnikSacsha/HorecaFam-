import { expect, test } from "@playwright/test";

const session = {
  user: { id: "user-1", email: "admin@example.com", preferred_locale: "uk" },
  session: { id: "session-1", absolute_expires_at: "2031-01-01T00:00:00Z", mfa_verified: true },
  organization_access: [
    {
      organization_id: "org-1",
      membership_status: null,
      is_employee: false,
      is_organization_admin: true,
    },
  ],
  platform_operator: false,
  csrf_token: "test-csrf",
};
const summary = {
  organization_id: "org-1",
  location_id: null,
  employees: { total: 8, active: 6, pending: 1, paused: 2, disabled: 1 },
  training: { assigned: 3, in_progress: 2, completed: 4 },
  final_exam: { certified: 3, needs_exam: 2, retake: 1, overdue_retake: 1 },
  attention: { unresolved: 2, critical: 1 },
};

test("Admin opens Dashboard, filters location and follows results", async ({ page }, testInfo) => {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    expect(route.request().method()).toBe("GET");
    if (url.pathname.endsWith("/auth/session")) return route.fulfill({ json: session });
    if (url.pathname.endsWith("/locations"))
      return route.fulfill({
        json: [
          {
            id: "location-1",
            name: "Центр",
            organization_id: "org-1",
            status: "active",
            address: null,
            timezone: "Europe/Kyiv",
          },
        ],
      });
    if (url.pathname.endsWith("/dashboard"))
      return route.fulfill({
        json: url.searchParams.has("location_id")
          ? {
              ...summary,
              location_id: "location-1",
              employees: { total: 2, active: 2, pending: 0, paused: 0, disabled: 0 },
              final_exam: { certified: 1, needs_exam: 1, retake: 1, overdue_retake: 1 },
            }
          : summary,
      });
    if (url.pathname.endsWith("/results")) return route.fulfill({ json: { items: [], total: 0 } });
    return route.fulfill({ status: 404 });
  });
  await page.goto("/login");
  await expect(page).toHaveURL(/\/admin\/dashboard$/);
  await expect(page.getByRole("heading", { name: "Огляд команди" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Працівники" })).toContainText("8");
  await page.getByLabel("Локація").selectOption("location-1");
  await expect(page.getByRole("region", { name: "Працівники" })).toContainText("2");
  expect(await page.evaluate("document.documentElement.scrollWidth <= innerWidth")).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("dashboard.png"), fullPage: true });
  const link = page.getByRole("link", { name: "Відкрити результати" });
  await link.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/admin\/results$/);
});

test("Dashboard retries a failed read and shows a truthful empty team", async ({ page }) => {
  let available = false;
  await page.route("**/api/v1/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/session")) return route.fulfill({ json: session });
    if (path.endsWith("/locations")) return route.fulfill({ json: [] });
    if (!available) return route.fulfill({ status: 503 });
    return route.fulfill({
      json: {
        ...summary,
        employees: { total: 0, active: 0, pending: 0, paused: 0, disabled: 0 },
        training: { assigned: 0, in_progress: 0, completed: 0 },
        final_exam: { certified: 0, needs_exam: 0, retake: 0, overdue_retake: 0 },
        attention: { unresolved: 0, critical: 0 },
      },
    });
  });
  await page.goto("/admin/dashboard");
  await expect(page.getByRole("alert")).toContainText("Не вдалося завантажити огляд.");
  await expect(page.getByText("Працівників ще немає")).toHaveCount(0);
  available = true;
  await page.getByRole("button", { name: "Повторити", exact: true }).click();
  await expect(page.getByText("Працівників ще немає")).toBeVisible();
  await expect(page.getByRole("link", { name: "Відкрити працівників" })).toBeVisible();
});

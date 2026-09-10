import { expect, test } from "@playwright/test";

const session = {
  user: { id: "user-1", email: "employee@example.com", preferred_locale: "uk" },
  session: { id: "session-1", absolute_expires_at: "2031-01-01T00:00:00Z", mfa_verified: false },
  organization_access: [
    {
      organization_id: "org-1",
      membership_status: "active",
      is_employee: true,
      is_organization_admin: false,
    },
  ],
  platform_operator: false,
  csrf_token: "test-csrf",
};
const profile = {
  id: "employee-1",
  organization: { id: "org-1", name: "Bacara" },
  membership_status: "active",
  first_name: "Анна",
  last_name: "Коваль",
  operational_role: {
    id: "role-1",
    organization_id: "org-1",
    code: "waiter",
    name_uk: "Офіціант",
    status: "active",
  },
  location: {
    id: "location-1",
    organization_id: "org-1",
    name: "Центр",
    status: "active",
    address: null,
    timezone: "Europe/Kyiv",
  },
  profile_complete: true,
  updated_at: "2026-09-09T00:00:00Z",
};

test("employee opens read-only profile from navigation and logs out", async ({
  page,
}, testInfo) => {
  let loggedOut = false;
  const mutations: string[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (route.request().method() !== "GET") {
      mutations.push(path);
      expect(path).toBe("/api/v1/auth/logout");
      expect(route.request().headers()["x-csrf-token"]).toBe("test-csrf");
      loggedOut = true;
      return route.fulfill({ status: 204 });
    }
    if (path === "/api/v1/auth/session")
      return route.fulfill({ status: loggedOut ? 401 : 200, json: session });
    if (path === "/api/v1/me/profile") return route.fulfill({ json: { profiles: [profile] } });
    return route.fulfill({ status: 503, json: { code: "UNAVAILABLE", message: "Unavailable" } });
  });
  await page.goto("/employee");
  await page.getByRole("link", { name: "Профіль", exact: true }).click();
  await expect(page).toHaveURL(/\/employee\/profile$/);
  await expect(page.getByRole("heading", { name: "Анна Коваль" })).toBeVisible();
  await expect(page.getByText("Офіціант", { exact: true })).toBeVisible();
  await expect(page.locator("input, select, textarea")).toHaveCount(0);
  expect(await page.evaluate("document.documentElement.scrollWidth <= innerWidth")).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("employee-profile.png"), fullPage: true });
  await page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)");
  await expect
    .poll(async () => {
      const note = await page.locator(".employee-profile-note").boundingBox();
      const navigation = await page
        .getByRole("navigation", { name: "Основна навігація" })
        .boundingBox();
      return note && navigation ? note.y + note.height <= navigation.y : false;
    })
    .toBe(true);
  await page.screenshot({ path: testInfo.outputPath("employee-profile-bottom.png") });
  await page.getByRole("button", { name: "Вийти", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/login$/);
  expect(mutations).toEqual(["/api/v1/auth/logout"]);
});

test("profile recovers from an unavailable API", async ({ page }) => {
  let available = false;
  await page.route("**/api/v1/**", (route) => {
    if (route.request().url().endsWith("/auth/session")) return route.fulfill({ json: session });
    if (!available)
      return route.fulfill({ status: 503, json: { code: "UNAVAILABLE", message: "Unavailable" } });
    return route.fulfill({ json: { profiles: [profile] } });
  });
  await page.goto("/employee/profile");
  await expect(page.getByRole("alert")).toContainText("Не вдалося завантажити профіль.");
  await expect(page.getByRole("button", { name: "Вийти", exact: true })).toBeEnabled();
  available = true;
  await page.getByRole("button", { name: "Повторити", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Анна Коваль" })).toBeVisible();
});

test("profile route preserves anonymous, Pending, Disabled and Admin routing", async ({ page }) => {
  for (const [kind, destination] of [
    ["anonymous", "/login"],
    ["pending", "/employee/pending"],
    ["disabled", "/access-disabled"],
    ["admin", "/admin/employees"],
  ]) {
    await page.unroute("**/api/v1/**");
    await page.route("**/api/v1/**", (route) => {
      if (route.request().url().endsWith("/auth/session"))
        return route.fulfill({
          status: kind === "anonymous" ? 401 : 200,
          json: {
            ...session,
            session: { ...session.session, mfa_verified: kind === "admin" },
            organization_access: [
              {
                organization_id: "org-1",
                membership_status: kind === "admin" ? null : kind,
                is_employee: kind !== "admin",
                is_organization_admin: kind === "admin",
              },
            ],
          },
        });
      return route.fulfill({ status: 503, json: { code: "UNAVAILABLE", message: "Unavailable" } });
    });
    await page.goto("/employee/profile");
    await expect(page).toHaveURL(new RegExp(`${destination}$`));
    await expect(page.getByRole("heading", { name: "Мій профіль" })).toHaveCount(0);
  }
});

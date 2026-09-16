import { expect, test } from "@playwright/test";

test("Admin resends an expired invitation with keyboard and sees queued feedback", async ({
  page,
}, testInfo) => {
  const invitation = {
    id: "invite",
    organization_id: "org",
    email: "invited@example.com",
    status: "expired",
    expires_at: "2026-09-12T00:00:00Z",
    created_at: "2026-09-09T00:00:00Z",
    updated_at: "2026-09-09T00:00:00Z",
  };
  let sends = 0;
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path.endsWith("/auth/session"))
      return route.fulfill({
        json: {
          user: { id: "admin", email: "admin@example.com", preferred_locale: "uk" },
          session: { id: "s", absolute_expires_at: "2031-01-01T00:00:00Z", mfa_verified: true },
          organization_access: [
            {
              organization_id: "org",
              membership_status: null,
              is_employee: false,
              is_organization_admin: true,
            },
          ],
          platform_operator: false,
          csrf_token: "synthetic-csrf",
        },
      });
    if (path.endsWith("/invitations/invite/resend")) {
      expect(request.method()).toBe("POST");
      expect(request.headers()["x-csrf-token"]).toBe("synthetic-csrf");
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      sends++;
      return route.fulfill({
        json: { ...invitation, status: "pending", expires_at: "2026-09-18T00:00:00Z" },
      });
    }
    if (path.endsWith("/invitations"))
      return route.fulfill({ json: { items: [invitation], next_cursor: null } });
    if (path.endsWith("/employees"))
      return route.fulfill({ json: { items: [], next_cursor: null } });
    if (path.endsWith("/organizations/org"))
      return route.fulfill({ json: { id: "org", name: "Bacara" } });
    return route.fulfill({ status: 404 });
  });
  await page.goto("/admin/employees");
  await expect(page.getByText(/Термін минув/)).toBeVisible();
  const button = page.getByRole("button", { name: "Надіслати повторно invited@example.com" });
  await button.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("status")).toContainText("Лист поставлено в чергу");
  await expect(page.getByText(/Очікує прийняття/)).toBeVisible();
  expect(sends).toBe(1);
  expect(await page.evaluate("document.documentElement.scrollWidth <= innerWidth")).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("invitations.png"), fullPage: true });
});

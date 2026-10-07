import { expect, test } from "@playwright/test";

const article = {
  id: "article-1",
  slug: "welcome",
  title_uk: "Перші секунди зустрічі",
  summary_uk: "Увага до гостя без поспіху.",
  body_uk:
    "Привітайте гостя й уточніть, чи потрібна допомога.\n\nЯкщо ви зайняті, повідомте колегу та перевірте передачу.",
  category: "service",
  status: "published",
  position: 0,
  revision: 1,
  all_positions: true,
  operational_role_ids: [],
  cover_asset_id: null,
  created_at: "2026-10-01T10:00:00Z",
  updated_at: "2026-10-02T10:00:00Z",
};
test("employee reads optional Academy with stable mobile navigation and no progress writes", async ({
  page,
}) => {
  const mutations: string[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    if (route.request().method() !== "GET") mutations.push(path);
    if (path === "/auth/session")
      return route.fulfill({
        json: {
          user: { id: "u", email: "reader@example.com", preferred_locale: "uk" },
          session: { id: "s", absolute_expires_at: "2030-01-01T00:00:00Z", mfa_verified: false },
          organization_access: [
            {
              organization_id: "o",
              membership_status: "active",
              is_employee: true,
              is_organization_admin: false,
            },
          ],
          platform_operator: false,
          csrf_token: "test-csrf",
        },
      });
    if (path === "/me/academy")
      return route.fulfill({ json: { items: [article], next_offset: null } });
    if (path === "/me/academy/welcome") return route.fulfill({ json: article });
    return route.fulfill({
      status: 404,
      json: {
        code: "RESOURCE_NOT_FOUND",
        message: "Недоступно",
        field_errors: [],
        request_id: "test",
      },
    });
  });
  await page.goto("/employee/academy");
  await expect(page.getByRole("heading", { name: "Академія", exact: true })).toBeVisible();
  await page.getByRole("link", { name: article.title_uk }).click();
  await expect(
    page.getByText("Привітайте гостя й уточніть, чи потрібна допомога.", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/Необов’язкове читання/)).toBeVisible();
  await expect(page.getByRole("link", { name: "Меню", exact: true })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Основна навігація" })).toBeVisible();
  expect(await page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")).toBe(
    true,
  );
  await page.screenshot({
    path: `test-results/academy-${test.info().project.name}.png`,
    fullPage: true,
  });
  await page.getByRole("link", { name: "Усі статті" }).click();
  await expect(page.getByRole("link", { name: article.title_uk })).toBeVisible();
  expect(mutations).toEqual([]);
});

test("admin creates a position-scoped Academy draft without redesigning navigation", async ({
  page,
}) => {
  let saved: Record<string, unknown> | undefined;
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1", "");
    if (path === "/auth/session")
      return route.fulfill({
        json: {
          user: { id: "u", email: "admin@example.com", preferred_locale: "uk" },
          session: { id: "s", absolute_expires_at: "2030-01-01T00:00:00Z", mfa_verified: true },
          organization_access: [
            {
              organization_id: "o",
              membership_status: null,
              is_employee: false,
              is_organization_admin: true,
            },
          ],
          platform_operator: false,
          csrf_token: "test-csrf",
        },
      });
    if (path.endsWith("/locations"))
      return route.fulfill({ json: [{ id: "l", name: "Зал", status: "active" }] });
    if (path.endsWith("/operational-roles"))
      return route.fulfill({ json: [{ id: "runner", name_uk: "Runner", status: "active" }] });
    if (path.endsWith("/academy") && request.method() === "POST") {
      expect(request.headers()["x-csrf-token"]).toBe("test-csrf");
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      saved = request.postDataJSON() as Record<string, unknown>;
      return route.fulfill({ status: 201, json: { ...article, ...saved, revision: 0 } });
    }
    if (path.endsWith("/academy"))
      return route.fulfill({
        json: { items: saved ? [{ ...article, ...saved, revision: 0 }] : [], next_offset: null },
      });
    return route.fulfill({ status: 404, json: {} });
  });
  await page.goto("/admin/academy");
  await page.getByRole("button", { name: "Нова стаття" }).click();
  await page.getByLabel("Назва", { exact: true }).fill("Поради Runner");
  await page.getByLabel("Адреса статті (slug)").fill("runner-advice");
  await page.getByLabel("Короткий опис").fill("Передача замовлення");
  await page.getByLabel("Текст статті").fill("Звірте номер столу перед виходом із видачі.");
  await page.getByLabel("Усі посади, включно з майбутніми").uncheck();
  await page.getByRole("checkbox", { name: "Runner", exact: true }).check();
  await page.getByRole("button", { name: "Зберегти статтю" }).click();
  await expect(page.getByRole("heading", { name: "Поради Runner" })).toBeVisible();
  expect(saved).toMatchObject({
    all_positions: false,
    operational_role_ids: ["runner"],
    status: "draft",
  });
  expect(await page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")).toBe(
    true,
  );
});

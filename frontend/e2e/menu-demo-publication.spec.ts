import { expect, test } from "@playwright/test";

test("grouped findings stay compact and demo publish requires acknowledgement", async ({
  page,
}, testInfo) => {
  let published = false;
  const item = {
    item_id: "item-307",
    item_version_id: "iv-307",
    version_id: "draft",
    category_id: "category",
    name_uk: "Тестова позиція",
    description_uk: null,
    price_minor: null,
    currency: "UAH",
    position: 0,
    availability: "available",
    component_data_status: "unknown",
    components: [],
    allergen_data_status: "unknown",
    allergen_codes: [],
    delta_kind: "added",
    training_impact: "required",
  };
  const draft = {
    id: "draft",
    menu_id: "menu",
    organization_id: "org",
    location_id: "location",
    version_number: 1,
    status: "draft",
    base_version_id: null,
    revision: 1,
    section_count: 1,
    category_count: 1,
    item_count: 308,
    created_at: "2030-01-01T00:00:00Z",
    published_at: null,
    archived_at: null,
    sections: [
      {
        id: "section",
        name_uk: "Розділ",
        position: 0,
        category_count: 1,
        categories: [
          {
            id: "category",
            section_id: "section",
            name_uk: "Категорія",
            position: 0,
            item_count: 308,
          },
        ],
      },
    ],
  };
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
    if (path.endsWith("/locations"))
      return route.fulfill({
        json: [{ id: "location", organization_id: "org", name: "Demo", status: "active" }],
      });
    if (path.endsWith("/menu-versions"))
      return route.fulfill({
        json: {
          menu_id: "menu",
          organization_id: "org",
          location_id: "location",
          draft: published ? null : draft,
          current_published: published ? { ...draft, status: "published" } : null,
          archived: [],
        },
      });
    if (path.endsWith("/draft"))
      return route.fulfill({ json: { ...draft, status: published ? "published" : "draft" } });
    if (path.endsWith("/items"))
      return route.fulfill({ json: { revision: 1, items: [], next_cursor: null } });
    if (path.endsWith("/items/item-307")) return route.fulfill({ json: item });
    if (path.endsWith("/readiness"))
      return route.fulfill({
        json: {
          menu_id: "menu",
          menu_version_id: "draft",
          organization_id: "org",
          location_id: "location",
          revision: 1,
          can_publish: false,
          demo_publication_allowed: true,
          warnings: [],
          blocking_errors: Array.from({ length: 308 }, (_, i) => ({
            code: "FACTS_UNCONFIRMED",
            message: "Склад і алергени ще не підтверджені.",
            entity_type: "menu_item",
            entity_id: `item-${i}`,
          })),
        },
      });
    if (path.endsWith("/publish")) {
      expect(request.postDataJSON()).toEqual({
        expected_revision: 1,
        demo_with_unknown_facts: true,
      });
      expect(request.headers()["x-csrf-token"]).toBe("synthetic-csrf");
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      published = true;
      return route.fulfill({ json: { published: { ...draft, status: "published" } } });
    }
    return route.fulfill({ status: 404 });
  });
  await page.goto("/admin/menu");
  await expect(page.getByText("FACTS_UNCONFIRMED", { exact: true })).toHaveCount(1);
  const demo = page.getByRole("button", { name: "Опублікувати демо", exact: true });
  await expect(demo).toBeDisabled();
  await page.getByText("Показати позиції: 308", { exact: true }).click();
  await page.getByRole("button", { name: "Відкрити позицію item-307", exact: true }).click();
  await expect(page.getByText("Тестова позиція", { exact: true })).toBeVisible();
  await expect(page.locator("#menu-item-item-307")).toBeFocused();
  await page.getByText("Показати позиції: 308", { exact: true }).click();
  await page.getByRole("checkbox", { name: /Демо: склад і алергени/ }).check();
  await demo.scrollIntoViewIfNeeded();
  expect(await page.evaluate("document.documentElement.scrollWidth <= innerWidth")).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("grouped-readiness.png"), fullPage: true });
  await demo.click();
  await expect(page.getByRole("dialog")).toContainText("не підтверджує безпечність");
  await page.getByRole("button", { name: "Опублікувати", exact: true }).click();
  await expect(page.getByRole("button", { name: "Опублікувати демо", exact: true })).toHaveCount(0);
  expect(published).toBe(true);
});

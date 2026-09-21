import { expect, test } from "@playwright/test";
const organizationId = "organization-1",
  locationId = "location-1",
  versionId = "training-version-1";
function sessionFor(user: "admin" | "employee") {
  const admin = user === "admin";
  return {
    user: {
      id: admin ? "admin-1" : "employee-1",
      email: admin ? "admin@example.com" : "employee@example.com",
      preferred_locale: "uk",
    },
    session: {
      id: admin ? "admin-session" : "employee-session",
      absolute_expires_at: "2030-09-01T00:00:00Z",
      mfa_verified: admin,
    },
    organization_access: [
      {
        organization_id: organizationId,
        membership_status: admin ? null : "active",
        is_employee: !admin,
        is_organization_admin: admin,
      },
    ],
    platform_operator: false,
    csrf_token: "csrf-safe",
  };
}

test("picks a bound menu item by name on all viewports", async ({ page }, testInfo) => {
  const publishedAt = "2030-08-28T08:00:00Z";
  const summary = (status: "draft" | "published") => ({
    id: versionId,
    training_id: "training-1",
    location_id: locationId,
    version_number: 1,
    status,
    revision: 4,
    base_version_id: null,
    module_count: 1,
    lesson_count: 1,
    created_at: "2030-08-28T07:00:00Z",
    published_at: status === "published" ? publishedAt : null,
    archived_at: null,
  });
  const detail = {
    ...summary("draft"),
    menu_version_id: "menu-version-1",
    modules: [
      {
        id: "module-1",
        domain_type: "menu",
        position: 0,
        title_uk: "Меню та рекомендації",
        description_uk: "Короткий довідник для зміни.",
        required: true,
        translation_status_en: null,
        lessons: [
          {
            id: "lesson-1",
            position: 0,
            title_uk: "Подача борщу",
            description_uk: "Факти для гостя.",
            required: true,
            estimated_minutes: 5,
            translation_status_en: null,
            content_blocks: [
              {
                id: "block-1",
                type: "text",
                position: 0,
                payload: { text_uk: "Поясніть склад гостю." },
                menu_item_id: null,
                asset: null,
              },
            ],
          },
        ],
      },
    ],
  };

  let chosen: unknown;
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    let json: unknown;
    if (path.endsWith("/auth/session")) json = sessionFor("admin");
    else if (path.endsWith("/locations"))
      json = [{ id: locationId, name: "Demo", status: "active" }];
    else if (path.endsWith("/operational-roles")) json = [];
    else if (path.endsWith("/audiences"))
      json = { training_version_id: versionId, revision: 4, operational_role_ids: [] };
    else if (path.endsWith("/training-versions"))
      json = { draft: detail, published: null, archived: [] };
    else if (path.endsWith("/readiness"))
      json = { can_publish: false, blocking_errors: [], warnings: [] };
    else if (path.endsWith("/content-blocks")) {
      chosen = route.request().postDataJSON();
      json = { revision: 5 };
    } else if (path.endsWith("/training-version-1")) json = detail;
    else if (path.endsWith("/menu-version-1"))
      json = {
        revision: 1,
        sections: [{ name_uk: "Їжа", categories: [{ id: "cat", name_uk: "Супи" }] }],
      };
    else if (path.endsWith("/items"))
      json = {
        revision: 1,
        next_cursor: null,
        items: [
          { item_id: "chosen", category_id: "cat", name_uk: "Суп дня", source_item_key: "dish-1" },
        ],
      };
    else {
      await route.abort();
      return;
    }
    await route.fulfill({ json });
  });
  await page.goto("/admin/content");
  await page.getByLabel("Тип блока", { exact: true }).selectOption("menu_item_card");
  await page.getByLabel("Знайти позицію меню").fill("Суп");
  await page.getByRole("option", { name: /Суп дня/ }).waitFor({ state: "attached" });
  await expect(page.getByLabel("Позиція меню", { exact: true })).toBeEnabled();
  await page.getByLabel("Позиція меню", { exact: true }).selectOption("chosen");
  await expect(page.getByLabel("ID позиції меню")).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("menu-picker.png"), fullPage: true });
  await page.getByRole("button", { name: "Додати блок", exact: true }).click();
  await expect
    .poll(() => chosen)
    .toEqual({
      expected_revision: 4,
      type: "menu_item_card",
      payload: { menu_item_id: "chosen", note_uk: null },
    });
  const body = await page.locator("body").boundingBox();
  expect(body!.width).toBeLessThanOrEqual(page.viewportSize()!.width);
});

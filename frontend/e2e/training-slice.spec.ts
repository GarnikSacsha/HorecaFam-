import { expect, test, type Request, type Route } from "@playwright/test";

type CurrentUser = "admin" | "employee";

const organizationId = "organization-1";
const locationId = "location-1";
const versionId = "training-version-1";

function sessionFor(user: CurrentUser) {
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

function assertProtectedMutation(request: Request) {
  expect(request.headers()["x-csrf-token"]).toBe("csrf-safe");
  expect(request.headers()["idempotency-key"]).toBeTruthy();
}

test("admin publishes Training and employee reads the current editorial reference", async ({
  page,
}) => {
  let currentUser: CurrentUser = "admin";
  let published = false;
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

  await page.route("**/api/v1/**", async (route: Route) => {
    const request = route.request();
    const method = request.method();
    const pathname = new URL(request.url()).pathname.replace("/api/v1", "");
    if (method === "GET" && pathname === "/auth/session") {
      await route.fulfill({ json: sessionFor(currentUser) });
      return;
    }
    if (method === "GET" && pathname === `/organizations/${organizationId}/locations`) {
      await route.fulfill({
        json: [
          {
            id: locationId,
            organization_id: organizationId,
            name: "Хрещатик",
            status: "active",
            address: null,
            timezone: "Europe/Kyiv",
          },
        ],
      });
      return;
    }
    const versionsPath = `/organizations/${organizationId}/locations/${locationId}/training-versions`;
    if (method === "GET" && pathname === versionsPath) {
      await route.fulfill({
        json: {
          published: published ? summary("published") : null,
          draft: published ? null : summary("draft"),
          archived: [],
        },
      });
      return;
    }
    if (method === "GET" && pathname === `${versionsPath}/${versionId}`) {
      await route.fulfill({ json: detail });
      return;
    }
    if (method === "GET" && pathname === `${versionsPath}/${versionId}/readiness`) {
      await route.fulfill({
        json: {
          training_id: "training-1",
          training_version_id: versionId,
          organization_id: organizationId,
          location_id: locationId,
          revision: 4,
          can_publish: true,
          blocking_errors: [],
          warnings: [
            {
              code: "EN_TRANSLATION_PENDING",
              message: "Англійський переклад ще не готовий.",
              entity_type: "lesson",
              entity_id: "lesson-1",
            },
          ],
          counts: {
            module_count: 1,
            lesson_count: 1,
            required_lesson_count: 1,
            content_block_count: 1,
            required_asset_count: 0,
            ready_asset_count: 0,
            menu_item_link_count: 0,
          },
        },
      });
      return;
    }
    if (method === "POST" && pathname === `${versionsPath}/${versionId}/publish`) {
      assertProtectedMutation(request);
      expect(request.postDataJSON()).toEqual({ expected_revision: 4 });
      published = true;
      await route.fulfill({
        json: {
          published: summary("published"),
          previous_published_version_id: null,
          employee_reference_switched: true,
          assignment_count: 0,
          completion_count: 0,
          progress_count: 0,
          rollout_count: 0,
          notification_count: 0,
        },
      });
      return;
    }
    if (method === "GET" && pathname === "/me/training") {
      await route.fulfill({
        json: {
          training: published
            ? { id: "training-1", version_number: 1, published_at: publishedAt }
            : null,
          modules: published
            ? [
                {
                  id: "module-1",
                  domain_type: "menu",
                  title: "Меню та рекомендації",
                  description: "Короткий довідник для зміни.",
                  position: 0,
                  required: true,
                  lesson_count: 1,
                  content_locale: "uk",
                  translation_fallback: false,
                },
              ]
            : [],
          content_locale: "uk",
          translation_fallback: false,
        },
      });
      return;
    }
    if (method === "GET" && pathname === "/me/training/modules/module-1") {
      await route.fulfill({
        json: {
          id: "module-1",
          domain_type: "menu",
          title: "Меню та рекомендації",
          description: "Короткий довідник для зміни.",
          position: 0,
          required: true,
          lesson_count: 1,
          content_locale: "uk",
          translation_fallback: false,
          lessons: [
            {
              id: "lesson-1",
              title: "Подача борщу",
              description: "Факти для гостя.",
              position: 0,
              required: true,
              estimated_minutes: 5,
              content_locale: "uk",
              translation_fallback: false,
            },
          ],
        },
      });
      return;
    }
    if (method === "GET" && pathname === "/me/training/lessons/lesson-1") {
      await route.fulfill({
        json: {
          id: "lesson-1",
          title: "Подача борщу",
          description: "Факти для гостя.",
          position: 0,
          required: true,
          estimated_minutes: 5,
          content_locale: "uk",
          translation_fallback: false,
          content_blocks: [
            {
              id: "b1",
              type: "heading",
              position: 0,
              payload: { level: 2, text_uk: "Головне" },
              content_locale: "uk",
              translation_fallback: false,
            },
            {
              id: "b2",
              type: "text",
              position: 1,
              payload: { text_uk: "Поясніть склад гостю." },
              content_locale: "uk",
              translation_fallback: false,
            },
            {
              id: "b3",
              type: "list",
              position: 2,
              payload: { style: "unordered", items_uk: ["Назвіть страву", "Уточніть алергени"] },
              content_locale: "uk",
              translation_fallback: false,
            },
            {
              id: "b4",
              type: "callout",
              position: 3,
              payload: { tone: "tip", title_uk: "Порада", text_uk: "Говоріть просто." },
              content_locale: "uk",
              translation_fallback: false,
            },
            {
              id: "b5",
              type: "menu_item_card",
              position: 4,
              payload: { menu_item_id: "menu-item-1", note_uk: "Подавайте зі сметаною." },
              content_locale: "uk",
              translation_fallback: false,
            },
            {
              id: "b6",
              type: "image",
              position: 5,
              payload: {
                asset_id: "asset-1",
                alt_uk: "Борщ у білій тарілці",
                caption_uk: "Приклад подачі",
              },
              content_locale: "uk",
              translation_fallback: false,
            },
            {
              id: "b7",
              type: "external_video",
              position: 6,
              payload: {
                provider: "youtube",
                video_id: "dQw4w9WgXcQ",
                title_uk: "Відео про подачу",
                summary_uk: "Коротка демонстрація.",
              },
              content_locale: "uk",
              translation_fallback: false,
            },
          ],
        },
      });
      return;
    }
    if (method === "GET" && pathname === "/me/training/assets/asset-1/access") {
      await route.fulfill({
        json: {
          url: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='640' height='360'%3E%3Crect width='640' height='360' fill='%23f2e7d5'/%3E%3C/svg%3E",
          expires_in: 300,
        },
      });
      return;
    }
    await route.fulfill({
      status: 404,
      json: {
        code: "UNEXPECTED_TEST_REQUEST",
        message: `${method} ${pathname}`,
        field_errors: [],
        request_id: "training-unexpected",
      },
    });
  });

  await page.goto("/admin/content");
  await expect(page.getByRole("heading", { name: "Навчальні матеріали", level: 1 })).toBeVisible();
  await expect(page.getByText("Англійський переклад ще не готовий.")).toBeVisible();
  await page.getByRole("button", { name: "Опублікувати навчання" }).click();
  const publishDialog = page.getByRole("dialog", {
    name: "Опублікувати цю версію навчання?",
  });
  await publishDialog.getByRole("button", { name: "Опублікувати" }).click();
  await expect(page.getByText("Опубліковано v1")).toBeVisible();

  currentUser = "employee";
  await page.goto("/employee/learning");
  await expect(page.getByRole("heading", { name: "Навчання", level: 1 })).toBeVisible();
  await page.getByRole("link", { name: /Меню та рекомендації/ }).click();
  await expect(page.getByRole("heading", { name: "Меню та рекомендації", level: 1 })).toBeVisible();
  await page.getByRole("link", { name: /Подача борщу/ }).click();
  await expect(page.getByRole("heading", { name: "Подача борщу", level: 1 })).toBeVisible();
  await expect(page.getByRole("img", { name: "Борщ у білій тарілці" })).toBeVisible();
  await expect(page.getByTitle("Відео про подачу")).toBeVisible();
  await expect(page.getByText("Подавайте зі сметаною.")).toBeVisible();
  await expect(page.getByText(/завершити|прогрес|призначено/i)).toHaveCount(0);
});

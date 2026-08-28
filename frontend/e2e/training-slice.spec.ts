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
          assignment: published
            ? {
                id: "assignment-1",
                status: "in_progress",
                assigned_at: publishedAt,
                started_at: publishedAt,
                completed_at: null,
              }
            : null,
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
          progress: published
            ? {
                required_lesson_count: 1,
                completed_required_lesson_count: 0,
                percentage: 0,
                is_complete: false,
              }
            : null,
          next_action: published ? "open_lesson" : "none",
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
              completed: false,
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
          completed: false,
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
    if (method === "POST" && pathname === "/me/training/lessons/lesson-1/complete") {
      assertProtectedMutation(request);
      await route.fulfill({
        json: {
          completion: {
            id: "completion-1",
            assignment_id: "assignment-1",
            lesson_id: "lesson-1",
            lesson_version_id: "lesson-version-1",
            completion_source: "employee",
            completed_at: "2030-08-28T10:00:00Z",
          },
          assignment: {
            id: "assignment-1",
            status: "completed",
            assigned_at: publishedAt,
            started_at: publishedAt,
            completed_at: "2030-08-28T10:00:00Z",
          },
          progress: {
            required_lesson_count: 1,
            completed_required_lesson_count: 1,
            percentage: 100,
            is_complete: true,
          },
          next_action: "review_training",
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
  await page.getByRole("button", { name: "Ознайомився" }).click();
  await expect(page.getByRole("status")).toContainText("Урок завершено");
});

test("admin assigns Training and confirms a replacement rollout", async ({ page }) => {
  let assignmentCreated = false;
  let ruleResolved = false;
  let previewReady = false;
  let rolloutCompleted = false;
  const oldVersionId = "training-version-old";
  const targetVersionId = "training-version-target";
  const versionsPath = `/organizations/${organizationId}/locations/${locationId}/training-versions`;
  const rolloutPath = `/organizations/${organizationId}/locations/${locationId}/training-rollouts/rollout-1`;
  const versionSummary = (
    id: string,
    versionNumber: number,
    status: "draft" | "published" | "archived",
  ) => ({
    id,
    training_id: "training-1",
    location_id: locationId,
    version_number: versionNumber,
    status,
    revision: status === "draft" ? 4 : 3,
    base_version_id: id === targetVersionId ? oldVersionId : null,
    module_count: 1,
    lesson_count: 1,
    created_at: "2030-08-28T07:00:00Z",
    published_at: status === "draft" ? null : "2030-08-28T08:00:00Z",
    archived_at: status === "archived" ? "2030-08-28T09:00:00Z" : null,
  });
  const targetDetail = {
    ...versionSummary(targetVersionId, 2, "draft"),
    menu_version_id: "menu-version-1",
    modules: [
      {
        id: "module-1",
        domain_type: "menu",
        position: 0,
        title_uk: "Оновлене меню",
        description_uk: "Зміни для команди.",
        required: true,
        translation_status_en: null,
        lessons: [
          {
            id: "lesson-1",
            position: 0,
            title_uk: "Оновлена подача",
            description_uk: null,
            required: true,
            estimated_minutes: 5,
            translation_status_en: null,
            content_blocks: [
              {
                id: "block-1",
                type: "text",
                position: 0,
                payload: { text_uk: "Нові факти." },
                menu_item_id: null,
                asset: null,
              },
            ],
          },
        ],
      },
    ],
  };
  const assignment = {
    id: "assignment-admin-1",
    organization_id: organizationId,
    location_id: locationId,
    training_id: "training-1",
    employee_profile_id: "employee-1",
    training_version_id: oldVersionId,
    status: "assigned",
    source: "admin",
    previous_assignment_id: null,
    source_rollout_id: null,
    assigned_at: "2030-08-28T08:00:00Z",
    started_at: null,
    completed_at: null,
    revoked_at: null,
    revoke_reason: null,
    revoke_note: null,
  };
  const rollout = () => ({
    id: "rollout-1",
    organization_id: organizationId,
    location_id: locationId,
    training_id: "training-1",
    from_version: { id: oldVersionId, version_number: 1, status: "archived", revision: 3 },
    to_version: { id: targetVersionId, version_number: 2, status: "published", revision: 4 },
    status: rolloutCompleted ? "completed" : previewReady ? "preview_ready" : "draft",
    revision: rolloutCompleted ? 5 : previewReady ? 4 : ruleResolved ? 3 : 2,
    rules: [
      {
        lesson_id: "lesson-1",
        from_lesson_version_id: "lesson-old",
        to_lesson_version_id: "lesson-new",
        rule: ruleResolved ? "preserve_completion" : null,
        requires_admin_decision: !ruleResolved,
        decided_by_user_id: ruleResolved ? "admin-1" : null,
        decided_at: ruleResolved ? "2030-08-28T10:00:00Z" : null,
      },
    ],
    employee_impacts: [
      {
        employee_profile_id: "employee-1",
        source_assignment_id: assignment.id,
        target_assignment_id: rolloutCompleted ? "assignment-target" : null,
        current_required_count: 1,
        current_completed_count: 1,
        current_progress_percentage: 100,
        projected_required_count: 1,
        projected_completed_count: ruleResolved ? 1 : 0,
        projected_progress_percentage: ruleResolved ? 100 : 0,
        lesson_impact: { materially_changed: ["lesson-1"] },
        validation_codes: [],
        warning_codes: [],
      },
    ],
    impact_counts: { employee_count: 1, unresolved_rule_count: ruleResolved ? 0 : 1 },
    is_stale: ruleResolved && !previewReady,
    warning_codes: [],
    previewed_at: previewReady ? "2030-08-28T10:10:00Z" : null,
    created_at: "2030-08-28T09:00:00Z",
  });

  await page.route("**/api/v1/**", async (route: Route) => {
    const request = route.request();
    const method = request.method();
    const pathname = new URL(request.url()).pathname.replace("/api/v1", "");
    if (method === "GET" && pathname === "/auth/session") {
      await route.fulfill({ json: sessionFor("admin") });
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
    if (method === "GET" && pathname === `/organizations/${organizationId}/operational-roles`) {
      await route.fulfill({
        json: [
          {
            id: "role-1",
            organization_id: organizationId,
            code: "waiter",
            name_uk: "Офіціант",
            status: "active",
          },
        ],
      });
      return;
    }
    if (method === "GET" && pathname === `/organizations/${organizationId}/employees/employee-1`) {
      await route.fulfill({
        json: {
          id: "employee-1",
          organization_id: organizationId,
          email: "employee@example.com",
          first_name: "Анна",
          last_name: "Коваль",
          membership_status: "active",
          operational_role: {
            id: "role-1",
            organization_id: organizationId,
            code: "waiter",
            name_uk: "Офіціант",
            status: "active",
          },
          location: {
            id: locationId,
            organization_id: organizationId,
            name: "Хрещатик",
            status: "active",
            address: null,
            timezone: "Europe/Kyiv",
          },
          profile_complete: true,
          created_at: "2030-08-27T00:00:00Z",
          updated_at: "2030-08-27T00:00:00Z",
          membership_created_at: "2030-08-27T00:00:00Z",
          activated_at: "2030-08-27T10:00:00Z",
          disabled_at: null,
        },
      });
      return;
    }
    const assignmentsPath = `/organizations/${organizationId}/employees/employee-1/training-assignments`;
    if (method === "GET" && pathname === assignmentsPath) {
      await route.fulfill({
        json: { current: assignmentCreated ? assignment : null, history: [], progress: null },
      });
      return;
    }
    if (method === "POST" && pathname === assignmentsPath) {
      assertProtectedMutation(request);
      assignmentCreated = true;
      await route.fulfill({ status: 201, json: assignment });
      return;
    }
    if (method === "GET" && pathname === versionsPath) {
      await route.fulfill({
        json: {
          published: versionSummary(oldVersionId, 1, "published"),
          draft: versionSummary(targetVersionId, 2, "draft"),
          archived: [],
        },
      });
      return;
    }
    if (method === "GET" && pathname === `${versionsPath}/${targetVersionId}`) {
      await route.fulfill({ json: targetDetail });
      return;
    }
    if (method === "GET" && pathname === `${versionsPath}/${targetVersionId}/readiness`) {
      await route.fulfill({
        json: {
          training_id: "training-1",
          training_version_id: targetVersionId,
          organization_id: organizationId,
          location_id: locationId,
          revision: 4,
          can_publish: true,
          blocking_errors: [],
          warnings: [],
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
    if (method === "POST" && pathname === `${versionsPath}/${targetVersionId}/publish`) {
      assertProtectedMutation(request);
      await route.fulfill({
        json: {
          published: versionSummary(targetVersionId, 2, "published"),
          previous_published_version_id: oldVersionId,
          employee_reference_switched: true,
          assignment_count: 0,
          completion_count: 0,
          progress_count: 0,
          rollout_count: 1,
          notification_count: 0,
          rollout_id: "rollout-1",
        },
      });
      return;
    }
    if (method === "GET" && pathname === rolloutPath) {
      await route.fulfill({ json: rollout() });
      return;
    }
    if (method === "PATCH" && pathname === `${rolloutPath}/lesson-rules/lesson-1`) {
      expect(request.headers()["x-csrf-token"]).toBe("csrf-safe");
      ruleResolved = true;
      previewReady = false;
      await route.fulfill({ json: rollout() });
      return;
    }
    if (method === "POST" && pathname === `${rolloutPath}/preview`) {
      assertProtectedMutation(request);
      previewReady = true;
      await route.fulfill({ json: rollout() });
      return;
    }
    if (method === "POST" && pathname === `${rolloutPath}/confirm`) {
      assertProtectedMutation(request);
      rolloutCompleted = true;
      await route.fulfill({ json: rollout() });
      return;
    }
    await route.fulfill({
      status: 404,
      json: {
        code: "UNEXPECTED_TEST_REQUEST",
        message: `${method} ${pathname}`,
        field_errors: [],
        request_id: "rollout-unexpected",
      },
    });
  });

  await page.goto("/admin/employees/employee-1");
  await page.getByRole("button", { name: "Призначити поточну версію" }).click();
  await expect(page.getByRole("status")).toContainText("Навчання призначено");

  await page.goto("/admin/content");
  await page.getByRole("button", { name: "Опублікувати навчання" }).click();
  await page.getByRole("button", { name: "Опублікувати", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Перенесення прогресу" })).toBeVisible();
  await page.getByRole("button", { name: "Зберегти завершення" }).click();
  await page.getByRole("button", { name: "Оновити попередній перегляд" }).click();
  await page.getByRole("button", { name: "Підтвердити перенесення" }).click();
  await page.getByRole("button", { name: "Перенести прогрес" }).click();
  await expect(page.getByText("Перенесення завершено")).toBeVisible();
});

import { expect, test, type Page, type Request, type Route } from "@playwright/test";

type CurrentUser = "anonymous" | "admin" | "employee";
type EmployeeStatus = "pending" | "active";

const organization = {
  id: "organization-1",
  name: "Bacara Kyiv",
  status: "active",
  default_locale: "uk",
  timezone: "Europe/Kyiv",
};

const role = {
  id: "role-1",
  organization_id: organization.id,
  code: "waiter",
  name_uk: "Офіціант",
  status: "active",
};

const location = {
  id: "location-1",
  organization_id: organization.id,
  name: "Хрещатик",
  status: "active",
  address: null,
  timezone: "Europe/Kyiv",
};

function sessionFor(user: Exclude<CurrentUser, "anonymous">, status: EmployeeStatus) {
  const admin = user === "admin";
  return {
    user: {
      id: admin ? "admin-1" : "employee-user-1",
      email: admin ? "admin@example.com" : "employee@example.com",
      preferred_locale: "uk",
    },
    session: {
      id: admin ? "admin-session-1" : "employee-session-1",
      absolute_expires_at: "2026-09-01T00:00:00Z",
      mfa_verified: admin,
    },
    organization_access: [
      {
        organization_id: organization.id,
        membership_status: admin ? null : status,
        is_employee: !admin,
        is_organization_admin: admin,
      },
    ],
    platform_operator: false,
    csrf_token: "csrf-safe",
  };
}

function assertProtectedMutation(request: Request, idempotent = false) {
  expect(request.headers()["x-csrf-token"]).toBe("csrf-safe");
  if (idempotent) expect(request.headers()["idempotency-key"]).toBeTruthy();
}

async function loginAsAdmin(page: Page) {
  await page.getByLabel("Робоча електронна пошта").fill("admin@example.com");
  await page.getByLabel("Пароль").fill("correct horse battery staple");
  await page.getByRole("button", { name: "Увійти" }).click();
  await page.getByLabel("Код підтвердження").fill("123456");
  await page.getByRole("button", { name: "Підтвердити" }).click();
  await expect(page.getByRole("heading", { name: "Працівники", level: 1 })).toBeVisible();
}

test("admin invitation, pending setup, activation and active employee home", async ({ page }) => {
  let currentUser: CurrentUser = "anonymous";
  let employeeStatus: EmployeeStatus = "pending";
  let profileComplete = false;
  let firstName: string | null = null;
  let lastName: string | null = null;

  const employee = () => ({
    id: "employee-1",
    organization_id: organization.id,
    email: "employee@example.com",
    first_name: firstName,
    last_name: lastName,
    membership_status: employeeStatus,
    operational_role: profileComplete ? role : null,
    location: profileComplete ? location : null,
    profile_complete: profileComplete,
    created_at: "2026-08-27T00:00:00Z",
    updated_at: "2026-08-27T10:00:00Z",
    membership_created_at: "2026-08-27T00:00:00Z",
    activated_at: employeeStatus === "active" ? "2026-08-27T10:00:00Z" : null,
    disabled_at: null,
  });

  const ownProfile = () => ({
    id: "employee-1",
    organization: { id: organization.id, name: organization.name },
    membership_status: employeeStatus,
    first_name: firstName,
    last_name: lastName,
    operational_role: profileComplete ? role : null,
    location: profileComplete ? location : null,
    profile_complete: profileComplete,
    updated_at: "2026-08-27T10:00:00Z",
  });

  await page.route("**/api/v1/**", async (route: Route) => {
    const request = route.request();
    const method = request.method();
    const pathname = new URL(request.url()).pathname.replace("/api/v1", "");

    if (method === "GET" && pathname === "/auth/session") {
      if (currentUser === "anonymous") {
        await route.fulfill({
          status: 401,
          json: {
            code: "UNAUTHENTICATED",
            message: "Сесію не знайдено.",
            field_errors: [],
            request_id: "request-session-anonymous",
          },
        });
        return;
      }
      await route.fulfill({ json: sessionFor(currentUser, employeeStatus) });
      return;
    }

    if (method === "POST" && pathname === "/auth/login") {
      const body = request.postDataJSON() as { email: string };
      if (body.email === "admin@example.com") {
        await route.fulfill({
          json: { status: "mfa_required", expires_at: "2026-08-27T20:00:00Z" },
        });
        return;
      }
      currentUser = "employee";
      await route.fulfill({ json: sessionFor("employee", employeeStatus) });
      return;
    }

    if (method === "POST" && pathname === "/auth/mfa/verify") {
      currentUser = "admin";
      await route.fulfill({ json: sessionFor("admin", employeeStatus) });
      return;
    }

    if (method === "POST" && pathname === "/auth/logout") {
      assertProtectedMutation(request);
      currentUser = "anonymous";
      await route.fulfill({ status: 204 });
      return;
    }

    if (method === "POST" && pathname === "/invitations/validate") {
      await route.fulfill({
        json: {
          status: "valid",
          organization_id: organization.id,
          organization_name: organization.name,
          email_masked: "e***@example.com",
          acceptance_mode: "activate_access",
          expires_at: "2026-08-30T00:00:00Z",
        },
      });
      return;
    }

    if (method === "POST" && pathname === "/invitations/accept") {
      currentUser = "employee";
      employeeStatus = "pending";
      await route.fulfill({
        json: {
          ...sessionFor("employee", "pending"),
          status: "accepted",
          acceptance_mode: "activate_access",
          membership: {
            id: "membership-1",
            organization_id: organization.id,
            employee_profile_id: "employee-1",
            status: "pending",
          },
        },
      });
      return;
    }

    if (method === "GET" && pathname === `/organizations/${organization.id}`) {
      await route.fulfill({ json: organization });
      return;
    }

    if (method === "GET" && pathname === `/organizations/${organization.id}/employees`) {
      await route.fulfill({ json: { items: [employee()], next_cursor: null } });
      return;
    }

    if (method === "POST" && pathname === `/organizations/${organization.id}/invitations`) {
      assertProtectedMutation(request, true);
      await route.fulfill({
        status: 201,
        json: { id: "invitation-1", email: "new@example.com" },
      });
      return;
    }

    if (method === "GET" && pathname === `/organizations/${organization.id}/employees/employee-1`) {
      await route.fulfill({ json: employee() });
      return;
    }

    if (method === "GET" && pathname === `/organizations/${organization.id}/locations`) {
      await route.fulfill({ json: [location] });
      return;
    }

    if (method === "GET" && pathname === `/organizations/${organization.id}/operational-roles`) {
      await route.fulfill({ json: [role] });
      return;
    }

    if (
      method === "PATCH" &&
      pathname === `/organizations/${organization.id}/employees/employee-1`
    ) {
      assertProtectedMutation(request);
      const body = request.postDataJSON() as { first_name: string; last_name: string };
      firstName = body.first_name;
      lastName = body.last_name;
      profileComplete = true;
      await route.fulfill({ json: employee() });
      return;
    }

    if (
      method === "POST" &&
      pathname === `/organizations/${organization.id}/employees/employee-1/activate`
    ) {
      assertProtectedMutation(request, true);
      employeeStatus = "active";
      await route.fulfill({
        json: {
          employee_id: "employee-1",
          organization_id: organization.id,
          membership_status: "active",
          training_participation_status: "active",
          activated_at: "2026-08-27T10:00:00Z",
        },
      });
      return;
    }

    if (method === "GET" && pathname === "/me/profile") {
      await route.fulfill({ json: { profiles: [ownProfile()] } });
      return;
    }

    if (method === "GET" && pathname === "/me/training") {
      await route.fulfill({
        json: {
          assignment: null,
          training: null,
          modules: [],
          progress: null,
          next_action: "none",
          content_locale: "uk",
          translation_fallback: false,
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
        request_id: "request-unexpected",
      },
    });
  });

  await page.goto("/login");
  await loginAsAdmin(page);

  await page.getByLabel("Електронна пошта нового працівника").fill("new@example.com");
  await page.getByRole("button", { name: "Надіслати запрошення" }).click();
  await expect(page.getByRole("status")).toContainText("new@example.com");

  await page.getByRole("button", { name: "Вийти" }).click();
  await page.goto("/invite?token=invitation-safe");
  await expect(page.getByRole("heading", { name: organization.name })).toBeVisible();
  await page.getByLabel("Створіть пароль").fill("strong-password");
  await page.getByLabel("Повторіть пароль").fill("strong-password");
  await page.getByRole("button", { name: "Прийняти запрошення" }).click();
  await expect(page.getByRole("heading", { name: "Майже готово" })).toBeVisible();
  await expect(page.getByText("Очікує налаштування адміністратором")).toBeVisible();
  await expect(page.getByRole("button", { name: /активувати/i })).toHaveCount(0);

  await page.getByRole("button", { name: "Вийти" }).click();
  await loginAsAdmin(page);
  await page
    .getByRole("link", { name: /Відкрити/ })
    .first()
    .click();

  await page.getByLabel("Ім’я").fill("Анна");
  await page.getByLabel("Прізвище").fill("Коваль");
  await page.getByLabel("Роль").selectOption(role.id);
  await page.getByLabel("Локація").selectOption(location.id);
  await page.getByRole("button", { name: "Зберегти профіль" }).click();
  await expect(page.getByRole("status")).toContainText("Профіль збережено");

  await page.getByRole("button", { name: "Активувати працівника" }).click();
  const dialog = page.getByRole("dialog", { name: "Активувати працівника?" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Підтвердити активацію" }).click();
  await expect(page.getByRole("status")).toHaveText("Працівника активовано");

  await page.getByRole("button", { name: "Вийти" }).click();
  await page.getByLabel("Робоча електронна пошта").fill("employee@example.com");
  await page.getByLabel("Пароль").fill("strong-password");
  await page.getByRole("button", { name: "Увійти" }).click();

  await expect(page.getByRole("heading", { name: "Вітаємо, Анна" })).toBeVisible();
  await expect(page.getByText("Навчання ще не призначено")).toBeVisible();
  await expect(page.getByText(/%/)).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Практика" })).toBeDisabled();
  await expect(page.getByRole("button", { name: /розпочати.*(іспит|практик)/i })).toHaveCount(0);
});

test("admin JSON review confirm and atomic menu publication", async ({ page }) => {
  let currentUser: CurrentUser = "anonymous";
  let published = false;
  let draftRevision = 0;
  let findingResolved = false;
  const draft = () => ({
    id: "menu-version-1",
    menu_id: "menu-1",
    organization_id: organization.id,
    location_id: location.id,
    version_number: 1,
    status: "draft",
    base_version_id: null,
    revision: draftRevision,
    section_count: 1,
    category_count: 1,
    item_count: 1,
    created_at: "2026-08-27T00:00:00Z",
    published_at: null,
    archived_at: null,
    sections: [
      {
        id: "section-1",
        stable_code: "main",
        name_uk: "Основне",
        position: 0,
        category_count: 1,
        categories: [
          {
            id: "category-1",
            section_id: "section-1",
            stable_code: "soups",
            name_uk: "Супи",
            position: 0,
            item_count: 1,
          },
        ],
      },
    ],
  });
  const finding = () => ({
    id: "finding-1",
    severity: "requires_review",
    code: "CRITICAL_FACT_CHANGE",
    entity_type: "menu_item",
    source_key: "borshch",
    message: "Критичні факти позиції змінено.",
    resolution_status: findingResolved ? "resolved" : "unresolved",
    allowed_actions: ["confirm_critical_change"],
    resolution_action: findingResolved ? "confirm_critical_change" : null,
    target_entity_id: null,
    resolution_comment: null,
    resolved_at: findingResolved ? "2026-08-27T01:00:00Z" : null,
  });
  const menuImport = (status = "ready_for_review") => ({
    id: "import-1",
    organization_id: organization.id,
    location_id: location.id,
    menu_id: "menu-1",
    base_menu_version_id: null,
    status,
    review_revision: findingResolved ? 1 : 0,
    source_filename: "menu.json",
    source_reference: null,
    source_checksum: "a".repeat(64),
    section_count: 1,
    category_count: 1,
    item_count: 1,
    added_count: 1,
    changed_count: 0,
    removed_count: 0,
    unchanged_count: 0,
    blocker_count: 0,
    review_count: 1,
    warning_count: 0,
    findings: [finding()],
    created_at: "2026-08-27T00:00:00Z",
    confirmed_at: status === "confirmed" ? "2026-08-27T02:00:00Z" : null,
    failure_code: null,
  });

  await page.route("**/api/v1/**", async (route: Route) => {
    const request = route.request();
    const method = request.method();
    const pathname = new URL(request.url()).pathname.replace("/api/v1", "");
    if (method === "GET" && pathname === "/auth/session") {
      if (currentUser === "anonymous") {
        await route.fulfill({
          status: 401,
          json: {
            code: "UNAUTHENTICATED",
            message: "Сесію не знайдено.",
            field_errors: [],
            request_id: "menu-session",
          },
        });
      } else await route.fulfill({ json: sessionFor(currentUser, "active") });
      return;
    }
    if (method === "POST" && pathname === "/auth/login") {
      await route.fulfill({ json: { status: "mfa_required", expires_at: "2026-08-27T20:00:00Z" } });
      return;
    }
    if (method === "POST" && pathname === "/auth/mfa/verify") {
      currentUser = "admin";
      await route.fulfill({ json: sessionFor("admin", "active") });
      return;
    }
    if (method === "GET" && pathname === "/me/menu") {
      await route.fulfill({
        json: published
          ? {
              menu: {
                menu_id: "menu-1",
                menu_version_id: "menu-version-1",
                location_id: location.id,
                version_number: 1,
                published_at: "2026-08-27T03:00:00Z",
                sections: [
                  {
                    id: "section-1",
                    name: "Основне",
                    position: 0,
                    categories: [
                      {
                        id: "category-1",
                        section_id: "section-1",
                        name: "Супи",
                        position: 0,
                      },
                    ],
                  },
                ],
              },
              items: [
                {
                  item_id: "item-1",
                  name: "Борщ",
                  description_excerpt: "Зі сметаною",
                  category_id: "category-1",
                  category_name: "Супи",
                  section_id: "section-1",
                  section_name: "Основне",
                  availability: "available",
                  price_minor: 32500,
                  currency: "UAH",
                  content_locale: "uk",
                  translation_fallback: false,
                },
              ],
              next_cursor: null,
            }
          : { menu: null, items: [], next_cursor: null },
      });
      return;
    }
    if (method === "GET" && pathname === "/me/menu/items/item-1") {
      await route.fulfill({
        json: {
          item_id: "item-1",
          name: "Борщ",
          description_excerpt: "Зі сметаною",
          category_id: "category-1",
          category_name: "Супи",
          section_id: "section-1",
          section_name: "Основне",
          availability: "available",
          price_minor: 32500,
          currency: "UAH",
          content_locale: "uk",
          translation_fallback: false,
          description: "Борщ на яловичому бульйоні.",
          components: [{ name: "Сметана", optional: true, position: 0 }],
          allergen_data_status: "confirmed_present",
          allergens: [{ code: "milk", label: "Молоко" }],
        },
      });
      return;
    }
    if (method === "GET" && pathname === `/organizations/${organization.id}`) {
      await route.fulfill({ json: organization });
      return;
    }
    if (method === "GET" && pathname === `/organizations/${organization.id}/employees`) {
      await route.fulfill({ json: { items: [], next_cursor: null } });
      return;
    }
    if (method === "GET" && pathname === `/organizations/${organization.id}/locations`) {
      await route.fulfill({ json: [location] });
      return;
    }
    const versionsPath = `/organizations/${organization.id}/locations/${location.id}/menu-versions`;
    if (method === "GET" && pathname === versionsPath) {
      await route.fulfill({
        json: {
          menu_id: "menu-1",
          organization_id: organization.id,
          location_id: location.id,
          current_published: published
            ? { ...draft(), status: "published", published_at: "2026-08-27T03:00:00Z" }
            : null,
          draft: published ? null : draft(),
          archived: [],
        },
      });
      return;
    }
    if (method === "GET" && pathname === `${versionsPath}/menu-version-1`) {
      await route.fulfill({ json: draft() });
      return;
    }
    if (method === "GET" && pathname === `${versionsPath}/menu-version-1/items`) {
      await route.fulfill({ json: { items: [], next_cursor: null, revision: draftRevision } });
      return;
    }
    if (method === "GET" && pathname === `${versionsPath}/menu-version-1/readiness`) {
      await route.fulfill({
        json: {
          menu_id: "menu-1",
          menu_version_id: "menu-version-1",
          organization_id: organization.id,
          location_id: location.id,
          revision: draftRevision,
          can_publish: true,
          blocking_errors: [],
          warnings: [],
          required_training_asset_count: 0,
          ready_training_asset_count: 0,
          applicable_training_content_count: 0,
        },
      });
      return;
    }
    const importsPath = `/organizations/${organization.id}/locations/${location.id}/menu-imports`;
    if (method === "POST" && pathname === importsPath) {
      assertProtectedMutation(request, true);
      await route.fulfill({ status: 201, json: menuImport() });
      return;
    }
    if (method === "POST" && pathname.endsWith("/findings/finding-1/resolve")) {
      assertProtectedMutation(request, true);
      findingResolved = true;
      await route.fulfill({ json: { finding: finding(), review_revision: 1 } });
      return;
    }
    if (method === "POST" && pathname === `${importsPath}/import-1/confirm`) {
      assertProtectedMutation(request, true);
      draftRevision = 1;
      await route.fulfill({ json: { import: menuImport("confirmed"), draft: draft() } });
      return;
    }
    if (method === "POST" && pathname === `${versionsPath}/menu-version-1/publish`) {
      assertProtectedMutation(request, true);
      published = true;
      await route.fulfill({
        json: {
          published: { ...draft(), status: "published", published_at: "2026-08-27T03:00:00Z" },
          previous_published_version_id: null,
          diff_counts: { added: 1, changed: 0, removed: 0, unchanged: 0 },
          training_impact_counts: { none: 0, review: 0, required: 1 },
          applicability: { published_content_count: 0, assignment_count: 0, notification_count: 0 },
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
        request_id: "menu-unexpected",
      },
    });
  });

  await page.goto("/login");
  await loginAsAdmin(page);
  await page.goto("/admin/menu");
  await expect(page.getByRole("heading", { name: "Меню", level: 1 })).toBeVisible();
  await page.getByLabel("JSON-файл меню").setInputFiles({
    name: "menu.json",
    mimeType: "application/json",
    buffer: Buffer.from('{"source_filename":"ignored.json","source_reference":null,"sections":[]}'),
  });
  await page.getByRole("button", { name: "Перевірити JSON" }).click();
  await expect(page.getByText("CRITICAL_FACT_CHANGE")).toBeVisible();
  await page.getByRole("button", { name: "Підтвердити критичну зміну" }).click();
  await expect(page.getByText("Вирішено")).toBeVisible();
  await page.getByRole("button", { name: "Підтвердити в чернетку" }).click();
  await page.getByRole("button", { name: "Опублікувати меню" }).click();
  const dialog = page.getByRole("dialog", { name: "Опублікувати цю версію меню?" });
  await dialog.getByRole("button", { name: "Опублікувати" }).click();
  await expect(page.getByText("Опубліковано v1")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Чернетки немає" })).toBeVisible();

  currentUser = "employee";
  await page.goto("/employee/menu");
  await expect(page.getByRole("heading", { name: "Меню", level: 1 })).toBeVisible();
  await page.getByLabel("Пошук у меню").fill("бор");
  await page.getByRole("button", { name: "Знайти" }).click();
  await page.getByRole("button", { name: /Борщ/ }).click();
  const itemDialog = page.getByRole("dialog", { name: "Борщ" });
  await expect(itemDialog).toContainText("Борщ на яловичому бульйоні.");
  await expect(itemDialog).toContainText("Сметана (за бажанням)");
  await expect(itemDialog).toContainText("Молоко");
});

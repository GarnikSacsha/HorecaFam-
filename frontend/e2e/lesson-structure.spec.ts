import { expect, test } from "@playwright/test";

test("reader provides category navigation, named cards, compact details and module return", async ({
  page,
}) => {
  const writes: string[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    if (route.request().method() !== "GET") writes.push(path);
    if (path === "/auth/session")
      return route.fulfill({
        json: {
          user: { id: "employee", email: "employee@example.com", preferred_locale: "uk" },
          session: {
            id: "session",
            absolute_expires_at: "2030-09-01T00:00:00Z",
            mfa_verified: false,
          },
          organization_access: [
            {
              organization_id: "org",
              membership_status: "active",
              is_employee: true,
              is_organization_admin: false,
            },
          ],
          platform_operator: false,
          csrf_token: "synthetic",
        },
      });
    if (path === "/me/training/lessons/lesson")
      return route.fulfill({
        json: {
          id: "lesson",
          module_id: "module",
          title: "Страви та подача",
          completed: true,
          content_blocks: [
            { id: "starters", type: "heading", payload: { level: 2, text_uk: "Стартери" } },
            {
              id: "card",
              type: "menu_item_card",
              payload: { menu_item_id: "item" },
              menu_item: {
                item_id: "item",
                name: "Овочевий стартер",
                description_excerpt: "Запечені овочі з соусом.",
                section_name: "Їжа",
                category_name: "Стартери",
              },
            },
            {
              id: "variant",
              type: "text",
              payload: { text_uk: "Варіант у навчальному знімку: 100 г; ціна 100 грн." },
            },
            { id: "breakfasts", type: "heading", payload: { level: 2, text_uk: "Сніданки" } },
            { id: "text", type: "text", payload: { text_uk: "Правила подачі сніданків." } },
          ],
        },
      });
    if (path === "/me/training/modules/module")
      return route.fulfill({
        json: {
          id: "module",
          title: "Меню",
          lessons: [{ id: "lesson", title: "Страви та подача", completed: true }],
        },
      });
    if (path === "/me/menu/items/item")
      return route.fulfill({
        json: {
          item_id: "item",
          name: "Овочевий стартер",
          category_name: "Стартери",
          description: "Запечені овочі з соусом.",
          components: [],
          allergens: [],
          allergen_data_status: "unknown",
          price_minor: null,
        },
      });
    if (path.includes("interactive-training"))
      return route.fulfill({
        json: {
          availability: "preparing",
          can_start: false,
          reason_codes: [],
          active_attempt: null,
          latest: null,
          best: null,
          history: [],
        },
      });
    return route.fulfill({ status: 404, json: { code: "NOT_FOUND" } });
  });
  await page.goto("/employee/learning/lessons/lesson");
  await expect(page.getByRole("heading", { name: "Страви та подача" })).toBeVisible();
  const contents = page.getByRole("navigation", { name: "Зміст уроку" });
  await expect(contents.getByRole("link", { name: "Стартери 1" })).toBeVisible();
  await contents.getByRole("link", { name: "Сніданки 0" }).click();
  await expect(page.locator("#block-breakfasts")).toBeFocused();
  await expect(page.getByText("Правила подачі сніданків.")).toBeVisible();
  const details = page.locator(".lesson-snapshot-details");
  await expect(details).not.toHaveAttribute("open");
  await details.locator("summary").click();
  await expect(details).toHaveAttribute("open");
  const trigger = page.getByRole("button", { name: "Відкрити Овочевий стартер" });
  await trigger.click();
  await expect(page.getByRole("dialog", { name: "Овочевий стартер" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(trigger).toBeFocused();
  expect(await page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")).toBe(
    true,
  );
  await page.screenshot({
    path: `../outputs/lesson-ux/reader-${test.info().project.name}.png`,
    fullPage: true,
  });
  await page.getByRole("link", { name: "← До уроків модуля" }).click();
  await expect(page).toHaveURL(/\/employee\/learning\/modules\/module$/);
  await expect(page.getByRole("list", { name: "Уроки модуля" })).toBeVisible();
  expect(writes).toEqual([]);
});

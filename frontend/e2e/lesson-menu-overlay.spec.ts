import { expect, test } from "@playwright/test";

test("lesson opens menu details in place and preserves keyboard focus and scroll", async ({
  page,
}) => {
  const errors: string[] = [];
  const requests: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    requests.push(path);
    if (path === "/auth/session")
      return route.fulfill({
        json: {
          user: { id: "employee-1", email: "employee@example.com", preferred_locale: "uk" },
          session: {
            id: "session-1",
            absolute_expires_at: "2030-09-01T00:00:00Z",
            mfa_verified: false,
          },
          organization_access: [
            {
              organization_id: "org-1",
              membership_status: "active",
              is_employee: true,
              is_organization_admin: false,
            },
          ],
          platform_operator: false,
          csrf_token: "csrf-safe",
        },
      });
    if (path === "/me/training/lessons/lesson-1")
      return route.fulfill({
        json: {
          id: "lesson-1",
          title: "Десерти та морозиво",
          completed: false,
          content_blocks: [
            { id: "text", type: "text", payload: { text_uk: "Навчальний матеріал. ".repeat(160) } },
            { id: "card", type: "menu_item_card", payload: { menu_item_id: "item-1" } },
          ],
        },
      });
    if (path.endsWith("/interactive-training"))
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
    if (path === "/me/menu/items/item-1")
      return route.fulfill({
        json: {
          item_id: "item-1",
          name: "Пломбір",
          category_name: "Морозиво",
          price_minor: 16500,
          currency: "UAH",
          content_locale: "uk",
          description: "Вершковий пломбір.",
          components: [],
          allergen_data_status: "unknown",
          allergens: [],
          source_note: {
            source_date: "2026-08-20",
            guest_description: "Можу запропонувати вершковий пломбір.",
            composition: null,
            allergen_labels: ["Молоко"],
            verification_status: "unverified",
          },
        },
      });
    return route.fulfill({ status: 404, json: { code: "NOT_FOUND", message: "Not found" } });
  });
  await page.goto("/employee/learning/lessons/lesson-1");
  const trigger = page.getByRole("button", { name: "Відкрити позицію в меню" });
  await trigger.scrollIntoViewIfNeeded();
  const before = await page.evaluate<number>("window.scrollY");
  await trigger.click();
  const dialog = page.getByRole("dialog", { name: "Пломбір" });
  await expect(dialog).toBeVisible();
  await expect(page).toHaveURL(/\/employee\/learning\/lessons\/lesson-1$/);
  await expect(dialog).toContainText("Інформацію про алергени ще не підтверджено.");
  await expect(dialog).toContainText("Можу запропонувати вершковий пломбір.");
  await expect(dialog).toContainText("Повноту відомостей не підтверджено");
  await expect(dialog.getByText("Молоко", { exact: true })).toBeVisible();
  const close = dialog.getByRole("button", { name: "Закрити", exact: true });
  await expect(close).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(dialog.locator("summary")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(close).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(dialog.locator("summary")).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(close).toBeFocused();
  expect(await page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")).toBe(
    true,
  );
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(trigger).toBeFocused();
  expect(Math.abs((await page.evaluate<number>("window.scrollY")) - before)).toBeLessThan(3);
  await trigger.click();
  await expect(dialog).toBeVisible();
  await close.click();
  await expect(dialog).toBeHidden();
  expect(requests.filter((p) => p.startsWith("/me/menu"))).toEqual([
    "/me/menu/items/item-1",
    "/me/menu/items/item-1",
  ]);
  expect(requests.some((p) => p.endsWith("/complete"))).toBe(false);
  expect(errors).toEqual([]);
});

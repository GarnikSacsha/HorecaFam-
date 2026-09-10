import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/**", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ error: { code: "unavailable", message: "Unavailable" } }),
    }),
  );
});

test("public story survives unavailable API and loads local photography without overflow", async ({
  page,
}, testInfo) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Гостинність починається");
  await expect(page.getByRole("alert")).toHaveCount(0);
  const images = page.locator(".bacara-public img");
  await expect(images).toHaveCount(5);
  for (const image of await images.all()) {
    await image.scrollIntoViewIfNeeded();
    await expect
      .poll(() =>
        image.evaluate(
          (node: { complete: boolean; naturalWidth: number }) =>
            node.complete && node.naturalWidth > 0,
        ),
      )
      .toBe(true);
  }
  expect(await page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")).toBe(
    true,
  );
  await page.screenshot({ path: testInfo.outputPath("public-start-full.png"), fullPage: true });
});

test("navigation reaches sections and existing login has a return path", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Ресурси", exact: true }).click();
  await expect(page).toHaveURL(/#resources$/);
  await expect(page.locator("#resources")).toBeInViewport();
  await page.getByRole("link", { name: "Для кого", exact: true }).click();
  await expect(page).toHaveURL(/#for-whom$/);
  await expect(page.locator("#for-whom")).toBeInViewport();
  await page.getByRole("link", { name: "Увійти до платформи" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByLabel("Робоча електронна пошта", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "На головну" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Гостинність починається");
});

test("keyboard skip link and reduced motion remain available", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await page.keyboard.press("Tab");
  const skip = page.locator(".bacara-skip");
  await expect(skip).toBeFocused();
  await expect(skip).toBeInViewport();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
  expect(await page.evaluate("getComputedStyle(document.documentElement).scrollBehavior")).toBe(
    "auto",
  );
});

import { expect, test } from "@playwright/test";

test("employee completes a course and receives the server result after explicit finish", async ({
  page,
}, testInfo) => {
  const answered = new Set<string>();
  let finished = false;
  const attempt = () => ({
    id: "attempt-1",
    assessment_version_id: "assessment-1",
    assignment_id: "assignment-1",
    status: finished ? "completed" : "in_progress",
    presentation_locale: "uk",
    lease_generation: 1,
    writable: !finished,
    expires_at: "2030-10-01T00:00:00Z",
    questions: Array.from({ length: 15 }, (_, index) => ({
      id: `question-${index}`,
      position: index,
      mechanic: "single_choice",
      prompt_payload: { stem: `Ситуація ${index + 1}: гість просить допомоги. Яка дія доречна?` },
      options: [
        { id: `a-${index}`, position: 0, payload: { text: "Уточнити запит гостя" } },
        { id: `b-${index}`, position: 1, payload: { text: "Проігнорувати запит" } },
      ],
      answer_payload: answered.has(`question-${index}`)
        ? { mechanic: "single_choice", option_id: `a-${index}` }
        : null,
      review: finished
        ? {
            is_correct: index < 12,
            correct_option_ids: [`a-${index}`],
            explanation_payload: { text: "Пояснення після завершення перевірки." },
          }
        : null,
    })),
    result: finished
      ? {
          id: "result-1",
          correct_count: 12,
          total_count: 15,
          score_basis_points: 8000,
          knowledge_level: "good",
          pass_status: null,
          completed_at: "2030-09-01T10:00:00Z",
        }
      : null,
  });
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1", "");
    if (path === "/auth/session") {
      await route.fulfill({
        json: {
          user: { id: "employee-1", email: "employee@example.com", preferred_locale: "uk" },
          session: {
            id: "session-1",
            absolute_expires_at: "2030-10-01T00:00:00Z",
            mfa_verified: false,
          },
          organization_access: [
            {
              organization_id: "organization-1",
              membership_status: "active",
              is_employee: true,
              is_organization_admin: false,
            },
          ],
          platform_operator: false,
          csrf_token: "course-csrf",
        },
      });
      return;
    }
    if (path === "/me/training/modules/module-1") {
      await route.fulfill({
        json: {
          id: "module-1",
          title: "Runner: робота в залі",
          description: "Навчання та перевірка знань.",
          domain_type: "service",
          position: 1,
          required: true,
          lesson_count: 1,
          content_locale: "uk",
          translation_fallback: false,
          lessons: [
            {
              id: "lesson-1",
              title: "Комунікація з гостем",
              position: 0,
              required: true,
              completed: true,
              estimated_minutes: 5,
              description: null,
              translation_fallback: false,
            },
          ],
          course: {
            module_version_id: "module-version-1",
            question_count: 15,
            can_start: true,
            ready: true,
            active_attempt_id: null,
            history: [],
          },
        },
      });
      return;
    }
    if (path.includes("/course/attempts") && request.method() === "POST") {
      expect(request.headers()["x-csrf-token"]).toBe("course-csrf");
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      if (path.endsWith("/answer")) {
        const body = request.postDataJSON() as { attempt_question_id: string };
        answered.add(body.attempt_question_id);
      }
      if (path.endsWith("/finish")) {
        expect(answered.size).toBe(15);
        finished = true;
      }
      await route.fulfill({ json: attempt() });
      return;
    }
    await route.fulfill({
      status: 404,
      json: {
        code: "RESOURCE_NOT_FOUND",
        message: "Не знайдено",
        field_errors: [],
        request_id: "test",
      },
    });
  });
  await page.goto("/employee/learning/modules/module-1");
  await page.getByRole("button", { name: "Розпочати перевірку" }).click();
  const section = page.getByRole("region", { name: "Перевірка модуля" });
  await expect(section.getByText("Ситуація 1:", { exact: false })).toBeVisible();
  await expect(page.getByText("Пояснення після завершення перевірки.")).toHaveCount(0);
  await expect(page.locator("body")).toHaveJSProperty(
    "scrollWidth",
    await page
      .locator("body")
      .evaluate((body: unknown) => (body as { clientWidth: number }).clientWidth),
  );
  await section.screenshot({ path: testInfo.outputPath("course-question.png") });
  for (let index = 0; index < 15; index += 1) {
    await expect(section.getByText(`Ситуація ${index + 1}:`, { exact: false })).toBeVisible();
    await section.getByRole("radio", { name: "Уточнити запит гостя" }).check();
    await section.getByRole("button", { name: "Зберегти відповідь" }).click();
  }
  expect(finished).toBe(false);
  await section.getByRole("button", { name: "Завершити перевірку" }).click();
  await expect(section.getByText("12 із 15", { exact: true })).toBeVisible();
  await expect(section.getByText("80%", { exact: true })).toBeVisible();
  await expect(section.getByText("Пояснення після завершення перевірки.")).toHaveCount(15);
});

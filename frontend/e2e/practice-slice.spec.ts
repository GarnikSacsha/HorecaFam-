import { expect, test, type Request, type Route } from "@playwright/test";

const assessmentVersionId = "practice-assessment-version-1";

const session = {
  user: { id: "employee-1", email: "employee@example.com", preferred_locale: "uk" },
  session: {
    id: "employee-session",
    absolute_expires_at: "2030-09-01T00:00:00Z",
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
  csrf_token: "csrf-safe",
};

const questions = Array.from({ length: 10 }, (_, index) => {
  const id = `practice-question-${index + 1}`;
  return {
    id,
    position: index,
    mechanic: "single_choice",
    prompt_payload: { stem: `Питання про страву ${index + 1}` },
    coverage_key: `menu-item-${index + 1}`,
    options: [
      { id: `${id}-correct`, position: 0, payload: { text: "Борщ" } },
      { id: `${id}-wrong`, position: 1, payload: { text: "Салат" } },
    ],
    saved_answer: null,
  };
});

const attempt = {
  id: "practice-attempt-1",
  assignment_id: "assignment-1",
  assessment_version_id: assessmentVersionId,
  status: "in_progress",
  presentation_locale: "uk",
  started_at: "2030-08-31T08:00:00Z",
  last_activity_at: "2030-08-31T08:00:00Z",
  expires_at: "2030-09-07T08:00:00Z",
  lease_generation: 1,
  writable: true,
  answered_count: 0,
  questions,
};

function expectProtectedMutation(request: Request) {
  expect(request.headers()["x-csrf-token"]).toBe("csrf-safe");
  expect(request.headers()["idempotency-key"]).toBeTruthy();
}

test("Employee completes ten-question Practice without feedback before explicit finish", async ({
  page,
}) => {
  let answerCount = 0;
  let finished = false;

  await page.route("**/api/v1/**", async (route: Route) => {
    const request = route.request();
    const method = request.method();
    const pathname = new URL(request.url()).pathname.replace("/api/v1", "");

    if (method === "GET" && pathname === "/auth/session") {
      await route.fulfill({ json: session });
      return;
    }
    if (method === "GET" && pathname === "/me/training/practice") {
      await route.fulfill({
        json: {
          availability: "ready",
          can_start: true,
          reason_codes: [],
          readiness_status: "ready",
          active_attempt: null,
          qualified: false,
          latest: null,
          best: null,
        },
      });
      return;
    }
    if (method === "GET" && pathname === "/me/training/practice/attempts") {
      const summary = {
        result_id: "practice-result-1",
        attempt_id: attempt.id,
        assessment_version_id: assessmentVersionId,
        completed_at: "2030-08-31T08:15:00Z",
        correct_count: 6,
        total_count: 10,
        score_basis_points: 6000,
        knowledge_level: "good",
        critical_error_count: 1,
      };
      await route.fulfill({
        json: finished
          ? { qualified: true, latest: summary, best: summary, history: [summary] }
          : { qualified: false, latest: null, best: null, history: [] },
      });
      return;
    }
    if (method === "POST" && pathname === "/me/training/practice/attempts") {
      expectProtectedMutation(request);
      expect(new URL(request.url()).searchParams.get("locale")).toBe("uk");
      await route.fulfill({ json: { attempt, created: true, replayed: false } });
      return;
    }
    if (method === "POST" && pathname === `/me/training/practice/attempts/${attempt.id}/answer`) {
      expectProtectedMutation(request);
      const question = questions[answerCount];
      expect(request.postDataJSON()).toEqual({
        attempt_question_id: question.id,
        answer_payload: { mechanic: "single_choice", option_id: question.options[0].id },
        lease_generation: 1,
      });
      answerCount += 1;
      await route.fulfill({
        json: {
          answer: {
            id: `practice-answer-${answerCount}`,
            answer_payload: {
              mechanic: "single_choice",
              option_id: question.options[0].id,
            },
            submitted_at: `2030-08-31T08:${String(answerCount).padStart(2, "0")}:00Z`,
          },
          answered_count: answerCount,
          next_question_id: answerCount === 10 ? null : questions[answerCount].id,
          attempt_status: "in_progress",
          replayed: false,
        },
      });
      return;
    }
    if (method === "POST" && pathname === `/me/training/practice/attempts/${attempt.id}/finish`) {
      expectProtectedMutation(request);
      expect(request.postDataJSON()).toEqual({ lease_generation: 1 });
      expect(answerCount).toBe(10);
      finished = true;
      await route.fulfill({
        json: {
          result: {
            id: "practice-result-1",
            correct_count: 6,
            total_count: 10,
            score_basis_points: 6000,
            knowledge_level: "good",
            pass_status: null,
            critical_error_count: 1,
            completed_at: "2030-08-31T08:15:00Z",
          },
          qualified: true,
          eligibility_earned: true,
          review: questions.map((question, index) => ({
            attempt_question_id: question.id,
            position: index,
            mechanic: question.mechanic,
            prompt_payload: question.prompt_payload,
            options: question.options,
            answer: {
              id: `practice-answer-${index + 1}`,
              answer_payload: {
                mechanic: "single_choice",
                option_id: question.options[0].id,
              },
              submitted_at: "2030-08-31T08:10:00Z",
            },
            is_correct: index < 6,
            correct_option_ids: [question.options[index < 6 ? 0 : 1].id],
            explanation_payload: { text: `Перевірений факт ${index + 1}` },
            is_critical: index === 9,
            is_critical_error: index === 9,
          })),
          replayed: false,
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
        request_id: "practice-unexpected",
      },
    });
  });

  await page.goto("/employee/practice");
  await expect(page.getByRole("heading", { name: "Практика", level: 1 })).toBeVisible();
  await page.getByRole("button", { name: "Почати Практику" }).click();

  for (let questionNumber = 1; questionNumber <= 10; questionNumber += 1) {
    await expect(
      page.getByRole("heading", { name: `Питання ${questionNumber}`, level: 2 }),
    ).toBeVisible();
    await expect(page.getByText("Правильно", { exact: true })).toHaveCount(0);
    await expect(page.getByText(/Перевірений факт/)).toHaveCount(0);
    const option = page.getByRole("radio", { name: "Борщ" });
    await option.check();
    if (questionNumber === 1) {
      const target = option.locator("xpath=ancestor::label");
      const box = await target.boundingBox();
      expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
    }
    await page.getByRole("button", { name: "Зберегти відповідь" }).click();
  }

  await expect(page.getByText("Усі 10 відповідей збережено")).toBeVisible();
  await expect(page.getByText(/Перевірений факт/)).toHaveCount(0);
  await page.getByRole("button", { name: "Завершити Практику" }).click();

  await expect(
    page.getByRole("heading", { name: "6 з 10 правильних відповідей", level: 2 }),
  ).toBeVisible();
  await expect(page.getByText("Перевірений факт 1", { exact: true })).toBeVisible();
  await expect(page.getByText("Критична помилка щодо алергенів.")).toBeVisible();
  await expect(page.getByText("Останній результат")).toBeVisible();
  await expect(page.getByText("Найкращий результат")).toBeVisible();
  await expect(page.getByText("Пройдено", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Не пройдено", { exact: true })).toHaveCount(0);
  expect(answerCount).toBe(10);
  expect(finished).toBeTruthy();
  const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
  expect(scrollWidth).toBeLessThanOrEqual((page.viewportSize()?.width ?? 0) + 1);
});

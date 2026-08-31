import { expect, test, type Request, type Route } from "@playwright/test";

const assessmentVersionId = "final-exam-version-1";

const session = {
  user: { id: "employee-1", email: "employee@example.com", preferred_locale: "uk" },
  session: {
    id: "employee-session",
    absolute_expires_at: "2030-09-08T00:00:00Z",
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

const questions = Array.from({ length: 20 }, (_, index) => {
  const id = `final-exam-question-${index + 1}`;
  return {
    id,
    position: index,
    mechanic: "single_choice",
    prompt_payload: { stem: `Питання Final Exam ${index + 1}` },
    coverage_key: `menu-item-${index + 1}`,
    options: [
      { id: `${id}-correct`, position: 0, payload: { text: "Перевірений варіант" } },
      { id: `${id}-wrong`, position: 1, payload: { text: "Інший варіант" } },
    ],
    saved_answer: null,
  };
});

const attempt = {
  id: "final-exam-attempt-1",
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

test("Employee completes Final Exam without feedback and sees certification only after confirmation", async ({
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
    if (method === "GET" && pathname === "/me/training/final-exam") {
      await route.fulfill({
        json: {
          availability: "eligible",
          can_start: true,
          reason_codes: [],
          readiness_status: "ready",
          active_attempt: null,
          certification: null,
          retake_available: false,
        },
      });
      return;
    }
    if (method === "GET" && pathname === "/me/training/final-exam/attempts") {
      const summary = {
        result_id: "final-exam-result-1",
        attempt_id: attempt.id,
        assessment_version_id: assessmentVersionId,
        completed_at: "2030-08-31T08:25:00Z",
        correct_count: 14,
        total_count: 20,
        score_basis_points: 7000,
        knowledge_level: "strong",
        pass_status: "passed",
        critical_error_count: 0,
      };
      await route.fulfill({
        json: finished
          ? {
              certification: {
                result_id: summary.result_id,
                attempt_id: summary.attempt_id,
                certified_at: summary.completed_at,
              },
              latest: summary,
              best: summary,
              history: [summary],
            }
          : { certification: null, latest: null, best: null, history: [] },
      });
      return;
    }
    if (method === "POST" && pathname === "/me/training/final-exam/attempts") {
      expectProtectedMutation(request);
      expect(new URL(request.url()).searchParams.get("locale")).toBe("uk");
      await route.fulfill({ json: { attempt, created: true, replayed: false } });
      return;
    }
    if (method === "POST" && pathname === `/me/training/final-exam/attempts/${attempt.id}/answer`) {
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
            id: `final-exam-answer-${answerCount}`,
            answer_payload: {
              mechanic: "single_choice",
              option_id: question.options[0].id,
            },
            submitted_at: `2030-08-31T08:${String(answerCount).padStart(2, "0")}:00Z`,
          },
          answered_count: answerCount,
          next_question_id: answerCount === 20 ? null : questions[answerCount].id,
          attempt_status: "in_progress",
          replayed: false,
        },
      });
      return;
    }
    if (method === "POST" && pathname === `/me/training/final-exam/attempts/${attempt.id}/finish`) {
      expectProtectedMutation(request);
      expect(request.postDataJSON()).toEqual({ lease_generation: 1 });
      expect(answerCount).toBe(20);
      finished = true;
      await route.fulfill({
        json: {
          result: {
            id: "final-exam-result-1",
            correct_count: 14,
            total_count: 20,
            score_basis_points: 7000,
            knowledge_level: "strong",
            pass_status: "passed",
            critical_error_count: 0,
            section_breakdown: {},
            completed_at: "2030-08-31T08:25:00Z",
          },
          certification: {
            result_id: "final-exam-result-1",
            attempt_id: attempt.id,
            certified_at: "2030-08-31T08:25:00Z",
          },
          newly_certified: true,
          retake_available: false,
          review: questions.map((question, index) => ({
            attempt_question_id: question.id,
            position: index,
            mechanic: question.mechanic,
            prompt_payload: question.prompt_payload,
            options: question.options,
            answer: {
              id: `final-exam-answer-${index + 1}`,
              answer_payload: {
                mechanic: "single_choice",
                option_id: question.options[0].id,
              },
              submitted_at: "2030-08-31T08:20:00Z",
            },
            is_correct: index < 14,
            correct_option_ids: [question.options[index < 14 ? 0 : 1].id],
            explanation_payload: { text: `Пояснення Final Exam ${index + 1}` },
            is_critical: false,
            is_critical_error: false,
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
        request_id: "final-exam-unexpected",
      },
    });
  });

  await page.goto("/employee/final-exam");
  await expect(page.getByRole("heading", { name: "Final Exam", level: 1 })).toBeVisible();
  await page.getByRole("button", { name: "Почати Final Exam" }).click();

  for (let questionNumber = 1; questionNumber <= 20; questionNumber += 1) {
    await expect(
      page.getByRole("heading", { name: `Питання ${questionNumber}`, level: 2 }),
    ).toBeVisible();
    await expect(page.getByText("Правильно", { exact: true })).toHaveCount(0);
    await expect(page.getByText(/Пояснення Final Exam/)).toHaveCount(0);
    await page.getByRole("radio", { name: "Перевірений варіант" }).check();
    await page.getByRole("button", { name: "Зберегти відповідь" }).click();
  }

  await expect(page.getByText("Усі 20 відповідей збережено")).toBeVisible();
  await expect(page.getByText(/Пояснення Final Exam/)).toHaveCount(0);
  await page.getByRole("button", { name: "Завершити Final Exam" }).click();
  await expect(page.getByRole("dialog", { name: "Підтвердити завершення" })).toBeVisible();
  await page.getByRole("button", { name: "Підтвердити та завершити" }).click();

  const resultHeading = page.getByRole("heading", {
    name: "14 з 20 правильних відповідей",
    level: 2,
  });
  await expect(resultHeading).toBeVisible();
  await expect(
    resultHeading.locator("xpath=..").getByText("Пройдено", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Сертифікацію збережено.")).toBeVisible();
  await expect(page.getByText("Пояснення Final Exam 1", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Повторити Final Exam" })).toHaveCount(0);
  expect(answerCount).toBe(20);
  expect(finished).toBeTruthy();
  const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
  expect(scrollWidth).toBeLessThanOrEqual((page.viewportSize()?.width ?? 0) + 1);
});

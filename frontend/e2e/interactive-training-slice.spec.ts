import { expect, test, type Request, type Route } from "@playwright/test";

type CurrentUser = "admin" | "employee";

const organizationId = "organization-1";
const locationId = "location-1";
const menuVersionId = "menu-version-1";
const trainingVersionId = "training-version-1";
const lessonId = "lesson-1";
const assessmentVersionId = "assessment-version-1";

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

function expectCsrf(request: Request) {
  expect(request.headers()["x-csrf-token"]).toBe("csrf-safe");
}

function expectIdempotency(request: Request) {
  expect(request.headers()["idempotency-key"]).toBeTruthy();
}

const candidate = {
  id: "candidate-1",
  training_version_id: trainingVersionId,
  lesson_version_id: "lesson-version-1",
  mechanic: "single_choice",
  prompt_payload: {
    locale: "uk",
    stem: "До якої категорії належить Борщ?",
    options: [
      { stable_key: "soups", text: "Супи" },
      { stable_key: "salads", text: "Салати" },
    ],
  },
  answer_payload: { correct_option_keys: ["soups"] },
  explanation_payload: { locale: "uk", text: "Борщ належить до категорії супів." },
  source_fingerprint: "a".repeat(64),
  status: "needs_review",
  revision: 1,
  reviewed_at: null,
  rejection_reason_code: null,
  sources: [
    {
      source_role: "correct_fact",
      menu_item_version_id: "menu-item-version-1",
      menu_item_version_component_id: null,
      menu_item_version_allergen_id: null,
    },
  ],
};

const attemptQuestions = Array.from({ length: 5 }, (_, index) => ({
  id: `attempt-question-${index + 1}`,
  position: index,
  mechanic: "single_choice",
  prompt_payload: { stem: `Питання ${index + 1}: оберіть Борщ` },
  options: [
    { id: `option-${index + 1}-correct`, position: 0, payload: { text: "Борщ" } },
    { id: `option-${index + 1}-wrong`, position: 1, payload: { text: "Салат" } },
  ],
  answered: false,
  confirmed_answer: null,
  feedback: null,
}));

const attempt = {
  id: "attempt-1",
  lesson_id: lessonId,
  lesson_version_id: "lesson-version-1",
  assessment_version_id: assessmentVersionId,
  status: "in_progress",
  presentation_locale: "uk",
  started_at: "2030-08-29T08:00:00Z",
  expires_at: "2030-09-05T08:00:00Z",
  lease_generation: 1,
  writable: true,
  questions: attemptQuestions,
};

test("Admin publishes a candidate and Employee completes five-question Interactive Training", async ({
  page,
}) => {
  let currentUser: CurrentUser = "admin";
  let generated = false;
  let approved = false;
  let answerCount = 0;
  const base = `/organizations/${organizationId}/locations/${locationId}`;

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
    if (method === "GET" && pathname === `${base}/menu-versions`) {
      await route.fulfill({
        json: {
          menu_id: "menu-1",
          organization_id: organizationId,
          location_id: locationId,
          current_published: { id: menuVersionId, version_number: 3, status: "published" },
          draft: null,
          archived: [],
        },
      });
      return;
    }
    if (method === "GET" && pathname === `${base}/training-versions`) {
      await route.fulfill({
        json: {
          published: { id: trainingVersionId, version_number: 2, status: "published" },
          draft: null,
          archived: [],
        },
      });
      return;
    }
    if (method === "GET" && pathname === `${base}/question-candidates`) {
      await route.fulfill({
        json: {
          items: generated && !approved ? [candidate] : [],
          total: generated && !approved ? 1 : 0,
        },
      });
      return;
    }
    if (
      method === "GET" &&
      pathname === `${base}/training-versions/${trainingVersionId}/interactive-training/readiness`
    ) {
      await route.fulfill({
        json: {
          training_version_id: trainingVersionId,
          lessons: approved
            ? [
                {
                  assessment_version_id: assessmentVersionId,
                  lesson_id: lessonId,
                  lesson_version_id: "lesson-version-1",
                  status: "ready",
                  eligible_count: 5,
                  required_count: 5,
                  coverage_evidence: { distinct_coverage_count: 5 },
                  rotation_supported: true,
                  basis_fingerprint: "b".repeat(64),
                  blocking_codes: [],
                  warning_codes: [],
                  computed_at: "2030-08-29T08:00:00Z",
                  can_start: true,
                },
              ]
            : [],
        },
      });
      return;
    }
    if (method === "POST" && pathname === `${base}/question-candidates/generate`) {
      expectCsrf(request);
      expectIdempotency(request);
      expect(request.postDataJSON()).toEqual({
        menu_version_id: menuVersionId,
        training_version_id: trainingVersionId,
      });
      generated = true;
      await route.fulfill({
        json: {
          created_count: 1,
          existing_count: 0,
          stale_candidate_count: 0,
          stale_question_count: 0,
          replayed: false,
        },
      });
      return;
    }
    if (method === "POST" && pathname === `${base}/question-candidates/candidate-1/approve`) {
      expectCsrf(request);
      expect(request.postDataJSON()).toEqual({ expected_revision: 1, edited_payload: null });
      approved = true;
      await route.fulfill({ json: { candidate: { ...candidate, status: "approved" } } });
      return;
    }
    if (method === "GET" && pathname === `/me/training/lessons/${lessonId}`) {
      await route.fulfill({
        json: {
          id: lessonId,
          title: "Подача борщу",
          description: "Закріпіть перевірені факти після уроку.",
          position: 0,
          required: true,
          estimated_minutes: 5,
          completed: true,
          content_locale: "uk",
          translation_fallback: false,
          content_blocks: [
            {
              id: "block-1",
              type: "text",
              position: 0,
              payload: { text_uk: "Борщ належить до категорії супів." },
              content_locale: "uk",
              translation_fallback: false,
            },
          ],
        },
      });
      return;
    }
    if (method === "GET" && pathname === `/me/training/lessons/${lessonId}/interactive-training`) {
      expect(approved).toBeTruthy();
      await route.fulfill({
        json: {
          lesson_id: lessonId,
          lesson_version_id: "lesson-version-1",
          assessment_version_id: assessmentVersionId,
          availability: "ready",
          can_start: true,
          reason_codes: [],
          readiness_status: "ready",
          active_attempt: null,
          latest: null,
          best: null,
          history: [],
        },
      });
      return;
    }
    if (
      method === "POST" &&
      pathname === `/me/training/lessons/${lessonId}/interactive-training/attempts`
    ) {
      expectIdempotency(request);
      await route.fulfill({ json: { attempt, created: true, replayed: false } });
      return;
    }
    if (
      method === "POST" &&
      pathname === "/me/training/interactive-training/attempts/attempt-1/answer"
    ) {
      expectCsrf(request);
      expectIdempotency(request);
      const payload = request.postDataJSON() as {
        attempt_question_id: string;
        answer_payload: { mechanic: string; option_id: string };
        lease_generation: number;
      };
      const expectedQuestion = attemptQuestions[answerCount];
      expect(payload).toEqual({
        attempt_question_id: expectedQuestion.id,
        answer_payload: {
          mechanic: "single_choice",
          option_id: expectedQuestion.options[0].id,
        },
        lease_generation: 1,
      });
      answerCount += 1;
      const completed = answerCount === 5;
      await route.fulfill({
        json: {
          answer: {
            id: `answer-${answerCount}`,
            answer_payload: payload.answer_payload,
            is_correct: true,
            submitted_at: `2030-08-29T08:0${answerCount}:00Z`,
          },
          feedback: {
            is_correct: true,
            correct_option_ids: [expectedQuestion.options[0].id],
            explanation_payload: { text: "Підтверджено перевіреним фактом меню." },
          },
          next_question_id: completed ? null : attemptQuestions[answerCount].id,
          attempt_status: completed ? "completed" : "in_progress",
          result: completed
            ? {
                id: "result-1",
                correct_count: 5,
                total_count: 5,
                score_basis_points: 10000,
                knowledge_level: "strong",
                pass_status: null,
                completed_at: "2030-08-29T08:05:00Z",
              }
            : null,
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
        request_id: "interactive-training-unexpected",
      },
    });
  });

  await page.goto("/admin/questions");
  await expect(page.getByRole("heading", { name: "Банк питань", level: 1 })).toBeVisible();
  await page.getByRole("button", { name: "Згенерувати кандидатів" }).click();
  await expect(page.getByText("До якої категорії належить Борщ?")).toBeVisible();
  await page.getByText("Джерела та provenance").click();
  await expect(page.getByText("menu-item-version-1")).toBeVisible();
  await page.getByRole("button", { name: "Схвалити", exact: true }).click();
  await expect(page.getByText("Кандидата схвалено та опубліковано в Банку питань.")).toBeVisible();

  currentUser = "employee";
  await page.goto(`/employee/learning/lessons/${lessonId}`);
  await expect(page.getByRole("heading", { name: "Подача борщу", level: 1 })).toBeVisible();
  await page.getByRole("button", { name: "Почати тренування" }).click();

  for (let questionNumber = 1; questionNumber <= 5; questionNumber += 1) {
    await expect(
      page.getByRole("heading", {
        name: `Питання ${questionNumber}: оберіть Борщ`,
        level: 3,
      }),
    ).toBeVisible();
    const option = page.getByRole("radio", { name: "Борщ" });
    await option.check();
    if (questionNumber === 1) {
      const target = option.locator("xpath=ancestor::label");
      const box = await target.boundingBox();
      expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
    }
    await page.getByRole("button", { name: "Підтвердити відповідь" }).click();
    await expect(page.getByText("Підтверджено перевіреним фактом меню.")).toBeVisible();
    if (questionNumber < 5) {
      await page.getByRole("button", { name: "Наступне питання" }).click();
    }
  }

  await expect(page.getByRole("heading", { name: "5 з 5 правильних відповідей" })).toBeVisible();
  await expect(page.getByText("Сильне знання · 100%")).toBeVisible();
  await expect(page.getByRole("button", { name: "Повторити тренування" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Продовжити навчання" })).toBeVisible();
  expect(answerCount).toBe(5);
  const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
  expect(scrollWidth).toBeLessThanOrEqual((page.viewportSize()?.width ?? 0) + 1);
});

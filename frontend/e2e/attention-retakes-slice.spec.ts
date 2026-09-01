import { expect, test, type Request, type Route } from "@playwright/test";

const organizationId = "00000000-0000-4000-8000-000000000001";
const employeeId = "00000000-0000-4000-8000-000000000002";
const attentionId = "00000000-0000-4000-8000-000000000003";
const requirementId = "00000000-0000-4000-8000-000000000004";
const attemptId = "00000000-0000-4000-8000-000000000005";

function protectedMutation(request: Request) {
  expect(request.headers()["x-csrf-token"]).toBe("csrf-safe");
  expect(request.headers()["idempotency-key"]).toBeTruthy();
}

const employeeSession = {
  user: { id: "employee-user", email: "employee@example.com", preferred_locale: "uk" },
  session: {
    id: "employee-session",
    absolute_expires_at: "2031-03-01T00:00:00Z",
    mfa_verified: false,
  },
  organization_access: [
    {
      organization_id: organizationId,
      membership_status: "active",
      is_employee: true,
      is_organization_admin: false,
    },
  ],
  platform_operator: false,
  csrf_token: "csrf-safe",
};

const answeredQuestions = Array.from({ length: 20 }, (_, index) => {
  const id = `retake-question-${index + 1}`;
  const optionId = `${id}-answer`;
  return {
    id,
    position: index,
    mechanic: "single_choice",
    prompt_payload: { stem: `Питання перескладання ${index + 1}` },
    coverage_key: `menu-item-${index + 1}`,
    options: [{ id: optionId, position: 0, payload: { text: "Підтверджена відповідь" } }],
    saved_answer: {
      id: `retake-answer-${index + 1}`,
      answer_payload: { mechanic: "single_choice", option_id: optionId },
      submitted_at: "2031-02-07T09:00:00Z",
    },
  };
});

function resultSummary(passStatus: "failed" | "passed") {
  const passed = passStatus === "passed";
  return {
    result_id: passed ? "result-passed" : "result-failed",
    attempt_id: passed ? attemptId : "attempt-failed",
    assessment_version_id: "final-version-1",
    completed_at: passed ? "2031-02-08T10:00:00Z" : "2031-02-01T10:00:00Z",
    correct_count: passed ? 14 : 13,
    total_count: 20,
    score_basis_points: passed ? 7000 : 6500,
    knowledge_level: passed ? "strong" : "good",
    pass_status: passStatus,
    critical_error_count: 0,
  };
}

test("failed retake moves from approaching through overdue to Passed without rewriting history", async ({
  page,
}) => {
  let timing: "approaching" | "overdue" = "approaching";
  let finished = false;
  const requirement = () => ({
    id: requirementId,
    training_id: "training-1",
    target_assessment_id: "assessment-1",
    reason: "failed_exam",
    state: "active",
    timing_state: timing,
    due_at: "2031-02-08T10:00:00Z",
    permitted_action: "resume_retake",
    source_attempt_id: "attempt-failed",
    completion_attempt_id: null,
    completed_at: null,
    cancelled_at: null,
  });
  const activeAttempt = {
    id: attemptId,
    assignment_id: "assignment-1",
    assessment_version_id: "final-version-1",
    status: "in_progress",
    presentation_locale: "uk",
    started_at: "2031-02-07T09:00:00Z",
    last_activity_at: "2031-02-07T09:20:00Z",
    expires_at: "2031-02-14T09:00:00Z",
    lease_generation: 1,
    writable: true,
    answered_count: 20,
    questions: answeredQuestions,
  };

  await page.route("**/api/v1/**", async (route: Route) => {
    const request = route.request();
    const method = request.method();
    const pathname = new URL(request.url()).pathname.replace("/api/v1", "");
    if (method === "GET" && pathname === "/auth/session") {
      await route.fulfill({ json: employeeSession });
      return;
    }
    if (method === "GET" && pathname === "/me/training/final-exam") {
      await route.fulfill({
        json: {
          availability: finished ? "already_certified" : "eligible",
          can_start: false,
          reason_codes: finished ? ["FINAL_EXAM_ALREADY_PASSED"] : [],
          readiness_status: "ready",
          active_attempt: finished ? null : activeAttempt,
          certification: finished
            ? {
                result_id: "result-passed",
                attempt_id: attemptId,
                certified_at: "2031-02-08T10:00:00Z",
              }
            : null,
          retake_available: !finished,
          current_retake_requirement: finished ? null : requirement(),
          attention_summary: {
            open_count: finished ? 0 : timing === "overdue" ? 1 : 0,
            has_critical_follow_up: false,
            has_overdue_follow_up: !finished && timing === "overdue",
          },
        },
      });
      return;
    }
    if (method === "GET" && pathname === "/me/training/final-exam/attempts") {
      const failed = resultSummary("failed");
      const passed = resultSummary("passed");
      await route.fulfill({
        json: {
          certification: finished
            ? {
                result_id: passed.result_id,
                attempt_id: passed.attempt_id,
                certified_at: passed.completed_at,
              }
            : null,
          latest: finished ? passed : failed,
          best: finished ? passed : failed,
          history: finished ? [passed, failed] : [failed],
        },
      });
      return;
    }
    if (method === "POST" && pathname === `/me/training/final-exam/attempts/${attemptId}/finish`) {
      protectedMutation(request);
      finished = true;
      await route.fulfill({
        json: {
          result: {
            id: "result-passed",
            correct_count: 14,
            total_count: 20,
            score_basis_points: 7000,
            knowledge_level: "strong",
            pass_status: "passed",
            critical_error_count: 0,
            section_breakdown: {},
            completed_at: "2031-02-08T10:00:00Z",
          },
          certification: {
            result_id: "result-passed",
            attempt_id: attemptId,
            certified_at: "2031-02-08T10:00:00Z",
          },
          newly_certified: true,
          retake_available: false,
          review: answeredQuestions.map((question, index) => ({
            attempt_question_id: question.id,
            position: index,
            mechanic: question.mechanic,
            prompt_payload: question.prompt_payload,
            options: question.options,
            answer: question.saved_answer,
            is_correct: index < 14,
            correct_option_ids: [question.options[0].id],
            explanation_payload: { text: "Перевірене пояснення" },
            is_critical: false,
            is_critical_error: false,
          })),
          replayed: false,
        },
      });
      return;
    }
    await route.fulfill({ status: 404, json: { code: "UNEXPECTED_TEST_REQUEST" } });
  });

  await page.goto("/employee/final-exam");
  await expect(page.getByRole("heading", { name: "Дедлайн наближається" })).toBeVisible();

  timing = "overdue";
  await page.reload();
  await expect(page.getByRole("heading", { name: "Дедлайн минув" })).toBeVisible();
  await expect(page.getByText(/Доступ не вимикається автоматично/)).toBeVisible();
  await page.getByRole("button", { name: "Завершити Final Exam" }).click();
  await page.getByRole("button", { name: "Підтвердити та завершити" }).click();

  await expect(page.getByRole("heading", { name: "14 з 20 правильних відповідей" })).toBeVisible();
  await expect(page.getByText("Сертифікацію збережено.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Дедлайн минув" })).toHaveCount(0);
  await expect(page.getByText("13/20")).toBeVisible();
  expect(finished).toBeTruthy();
  expect(await page.evaluate<number>("document.documentElement.scrollWidth")).toBeLessThanOrEqual(
    (page.viewportSize()?.width ?? 0) + 1,
  );
});

test("Passed with a critical signal stays Passed through explicit Admin follow-up resolution", async ({
  page,
}) => {
  let caseState: "open" | "acknowledged" | "resolved" = "open";
  const adminSession = {
    ...employeeSession,
    user: { ...employeeSession.user, id: "admin-user", email: "admin@example.com" },
    session: { ...employeeSession.session, id: "admin-session", mfa_verified: true },
    organization_access: [
      {
        organization_id: organizationId,
        membership_status: null,
        is_employee: false,
        is_organization_admin: true,
      },
    ],
  };
  const attentionCase = () => ({
    id: attentionId,
    organization_id: organizationId,
    location_id: "location-1",
    training_id: "training-1",
    employee_profile_id: employeeId,
    case_type: "critical_allergen",
    severity: "critical",
    subject_key: "menu_item:item-1:allergen:allergen-1",
    state: caseState,
    revision: caseState === "open" ? 0 : caseState === "acknowledged" ? 1 : 2,
    acknowledged_at: caseState === "open" ? null : "2031-02-01T11:00:00Z",
    resolution_type: caseState === "resolved" ? "admin_follow_up" : null,
    resolved_at: caseState === "resolved" ? "2031-02-01T12:00:00Z" : null,
    resolution_comment: caseState === "resolved" ? "Проведено окремий інструктаж." : null,
    critical_error_ids: ["critical-1"],
    retake_requirement_id: null,
    created_at: "2031-02-01T10:00:00Z",
    updated_at: "2031-02-01T10:00:00Z",
  });

  await page.route("**/api/v1/**", async (route: Route) => {
    const request = route.request();
    const method = request.method();
    const url = new URL(request.url());
    const pathname = url.pathname.replace("/api/v1", "");
    if (method === "GET" && pathname === "/auth/session") {
      await route.fulfill({ json: adminSession });
      return;
    }
    if (method === "GET" && pathname === `/organizations/${organizationId}/attention`) {
      await route.fulfill({ json: { items: [attentionCase()], next_cursor: null } });
      return;
    }
    if (
      method === "GET" &&
      pathname === `/organizations/${organizationId}/employees/${employeeId}/attention`
    ) {
      await route.fulfill({ json: { items: [attentionCase()], next_cursor: null } });
      return;
    }
    if (method === "GET" && pathname === `/organizations/${organizationId}/retake-requirements`) {
      await route.fulfill({ json: { items: [], next_cursor: null } });
      return;
    }
    if (method === "POST" && pathname.endsWith("/acknowledge")) {
      protectedMutation(request);
      caseState = "acknowledged";
      await route.fulfill({ json: attentionCase() });
      return;
    }
    if (method === "POST" && pathname.endsWith("/resolve")) {
      protectedMutation(request);
      expect(request.postDataJSON()).toMatchObject({ resolution_type: "admin_follow_up" });
      caseState = "resolved";
      await route.fulfill({ json: attentionCase() });
      return;
    }
    if (
      method === "GET" &&
      pathname === `/organizations/${organizationId}/results/employees/${employeeId}`
    ) {
      const passed = { ...resultSummary("passed"), critical_error_count: 1 };
      await route.fulfill({
        json: {
          employee: {
            employee_id: employeeId,
            email: "employee@example.com",
            first_name: "Олена",
            last_name: "Коваль",
            location_id: "location-1",
            current_training_status: "completed",
            latest_practice_score_basis_points: 8000,
            certification: {
              result_id: passed.result_id,
              attempt_id: passed.attempt_id,
              certified_at: passed.completed_at,
            },
            latest_final_exam: passed,
            critical_error_count: 1,
          },
          final_exam: {
            certification: {
              result_id: passed.result_id,
              attempt_id: passed.attempt_id,
              certified_at: passed.completed_at,
            },
            latest: passed,
            best: passed,
            history: [passed],
          },
        },
      });
      return;
    }
    await route.fulfill({ status: 404, json: { code: "UNEXPECTED_TEST_REQUEST" } });
  });

  await page.goto("/admin/attention");
  await page
    .getByRole("button", { name: /^Відкрити( кейс)?$/ })
    .first()
    .click();
  await page.getByRole("button", { name: "Взяти в роботу" }).click();
  await page.getByLabel("Підсумок follow-up").fill("Проведено окремий інструктаж.");
  await page.getByRole("button", { name: "Завершити після розмови" }).click();
  await expect(page.getByText("Кейс завершено.")).toBeVisible();

  await page
    .getByRole("link", { name: "Переглянути незмінну історію результатів" })
    .first()
    .click();
  await expect(page.getByText("Сертифіковано")).toBeVisible();
  await expect(page.getByText("Критичні помилки: 1")).toBeVisible();
  await expect(page.getByText("14/20").first()).toBeVisible();
  expect(caseState).toBe("resolved");
  expect(await page.evaluate<number>("document.documentElement.scrollWidth")).toBeLessThanOrEqual(
    (page.viewportSize()?.width ?? 0) + 1,
  );
});

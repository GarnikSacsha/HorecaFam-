import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import type { ApiClient, RequestOptions } from "../api/client";
import type { SessionResponse } from "../api/contracts";
import { SessionProvider } from "../session/SessionContext";
import { EmployeeFinalExamPage } from "./EmployeeFinalExamPage";

const session: SessionResponse = {
  user: { id: "employee-1", email: "employee@example.com", preferred_locale: "uk" },
  session: { id: "session-1", absolute_expires_at: "2030-09-01T00:00:00Z", mfa_verified: false },
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

const questions = Array.from({ length: 20 }, (_, index) => ({
  id: `question-${index + 1}`,
  position: index,
  mechanic: "single_choice",
  prompt_payload: { stem: `Питання ${index + 1}` },
  coverage_key: `menu.item.${index + 1}`,
  options: [
    { id: `question-${index + 1}-a`, position: 0, payload: { text: "Варіант А" } },
    { id: `question-${index + 1}-b`, position: 1, payload: { text: "Варіант Б" } },
  ],
  saved_answer: null,
}));

const attempt = {
  id: "attempt-1",
  assignment_id: "assignment-1",
  assessment_version_id: "assessment-1",
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

const emptyHistory = { certification: null, latest: null, best: null, history: [] };

function renderExam(client: ApiClient) {
  return render(
    <SessionProvider client={client}>
      <MemoryRouter>
        <EmployeeFinalExamPage />
      </MemoryRouter>
    </SessionProvider>,
  );
}

describe("Employee Final Exam", () => {
  it("starts exactly twenty questions and saves an answer without feedback", async () => {
    const requests: Array<{ path: string; options?: RequestOptions }> = [];
    const client: ApiClient = {
      getSession: () => Promise.resolve(session),
      request: <T,>(path: string, options?: RequestOptions) => {
        requests.push({ path, options });
        if (path === "/me/training/final-exam") {
          return Promise.resolve({
            availability: "eligible",
            can_start: true,
            reason_codes: [],
            readiness_status: "ready",
            active_attempt: null,
            certification: null,
            retake_available: false,
          } as T);
        }
        if (path === "/me/training/final-exam/attempts" && !options?.method) {
          return Promise.resolve(emptyHistory as T);
        }
        if (path.startsWith("/me/training/final-exam/attempts?") && options?.method === "POST") {
          return Promise.resolve({ attempt, created: true, replayed: false } as T);
        }
        if (path.endsWith("/answer")) {
          return Promise.resolve({
            answer: {
              id: "answer-1",
              answer_payload: { mechanic: "single_choice", option_id: "question-1-a" },
              submitted_at: "2030-08-31T08:01:00Z",
            },
            answered_count: 1,
            next_question_id: "question-2",
            attempt_status: "in_progress",
            replayed: false,
          } as T);
        }
        throw new Error(`Unexpected request: ${path}`);
      },
    };
    const user = userEvent.setup();

    renderExam(client);

    await user.click(await screen.findByRole("button", { name: "Почати Final Exam" }));
    expect(await screen.findByText("0 з 20 відповідей збережено")).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: "Варіант А" }));
    await user.click(screen.getByRole("button", { name: "Зберегти відповідь" }));

    expect(await screen.findByRole("heading", { name: "Питання 2" })).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("Правильно");
    expect(document.body).not.toHaveTextContent("правильна відповідь");
    const answerRequest = requests.find(({ path }) => path.endsWith("/answer"));
    expect(answerRequest?.options?.body).toEqual({
      attempt_question_id: "question-1",
      answer_payload: { mechanic: "single_choice", option_id: "question-1-a" },
      lease_generation: 1,
    });
  });

  it("requires final confirmation, then shows pass status, review and immediate retake", async () => {
    const completedQuestions = questions.map((question, index) => ({
      ...question,
      saved_answer: {
        id: `answer-${index + 1}`,
        answer_payload: { mechanic: "single_choice", option_id: `${question.id}-a` },
        submitted_at: "2030-08-31T08:01:00Z",
      },
    }));
    const completedAttempt = { ...attempt, answered_count: 20, questions: completedQuestions };
    const resultSummary = {
      result_id: "result-1",
      attempt_id: "attempt-1",
      assessment_version_id: "assessment-1",
      completed_at: "2030-08-31T08:20:00Z",
      correct_count: 13,
      total_count: 20,
      score_basis_points: 6500,
      knowledge_level: "good",
      pass_status: "failed",
      critical_error_count: 1,
    };
    const client: ApiClient = {
      getSession: () => Promise.resolve(session),
      request: <T,>(path: string, options?: RequestOptions) => {
        if (path === "/me/training/final-exam") {
          return Promise.resolve({
            availability: "in_progress",
            can_start: false,
            reason_codes: [],
            readiness_status: "ready",
            active_attempt: completedAttempt,
            certification: null,
            retake_available: false,
          } as T);
        }
        if (path === "/me/training/final-exam/attempts" && !options?.method) {
          return Promise.resolve(emptyHistory as T);
        }
        if (path.endsWith("/finish")) {
          return Promise.resolve({
            result: {
              id: "result-1",
              correct_count: 13,
              total_count: 20,
              score_basis_points: 6500,
              knowledge_level: "good",
              pass_status: "failed",
              critical_error_count: 1,
              section_breakdown: {},
              completed_at: "2030-08-31T08:20:00Z",
            },
            certification: null,
            newly_certified: false,
            retake_available: true,
            review: [
              {
                attempt_question_id: "question-1",
                position: 0,
                mechanic: "single_choice",
                prompt_payload: { stem: "Питання 1" },
                options: questions[0].options,
                answer: completedQuestions[0].saved_answer,
                is_correct: false,
                correct_option_ids: ["question-1-b"],
                explanation_payload: { text: "Перевірений факт" },
                is_critical: true,
                is_critical_error: true,
              },
            ],
            replayed: false,
          } as T);
        }
        if (path.startsWith("/me/training/final-exam/attempts?") && options?.method === "POST") {
          return Promise.resolve({ attempt, created: true, replayed: false } as T);
        }
        if (path === "/me/training/final-exam/attempts") {
          return Promise.resolve({
            ...emptyHistory,
            latest: resultSummary,
            best: resultSummary,
            history: [resultSummary],
          } as T);
        }
        throw new Error(`Unexpected request: ${path}`);
      },
    };
    const user = userEvent.setup();

    renderExam(client);

    await user.click(await screen.findByRole("button", { name: "Завершити Final Exam" }));
    expect(screen.getByRole("dialog", { name: "Підтвердити завершення" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Підтвердити та завершити" }));

    expect(
      await screen.findByRole("heading", { name: "13 з 20 правильних відповідей" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Не пройдено")).toBeInTheDocument();
    expect(screen.getByText("Перевірений факт")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Повторити Final Exam" })).toBeInTheDocument();
  });
});

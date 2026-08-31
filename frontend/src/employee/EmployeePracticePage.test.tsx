import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { ApiClient, RequestOptions } from "../api/client";
import type {
  PracticeAttempt,
  PracticeFinishResponse,
  PracticeHistoryResponse,
  PracticeSummaryResponse,
  SessionResponse,
} from "../api/contracts";
import { SessionProvider } from "../session/SessionContext";
import { EmployeePracticePage } from "./EmployeePracticePage";

const session: SessionResponse = {
  user: { id: "user-1", email: "employee@example.com", preferred_locale: "uk" },
  session: {
    id: "session-1",
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

const options = (questionId: string) => [
  { id: `${questionId}-a`, position: 0, payload: { text: "Борщ" } },
  { id: `${questionId}-b`, position: 1, payload: { text: "Салат" } },
];

const questions = Array.from({ length: 10 }, (_, index) => {
  const id = `question-${index + 1}`;
  return {
    id,
    position: index,
    mechanic: "single_choice",
    prompt_payload: { stem: `Питання про страву ${index + 1}` },
    coverage_key: `menu-item-${index + 1}`,
    options: options(id),
    saved_answer: null,
  };
});

const attempt: PracticeAttempt = {
  id: "attempt-1",
  assignment_id: "assignment-1",
  assessment_version_id: "assessment-version-1",
  status: "in_progress",
  presentation_locale: "uk",
  started_at: "2030-08-29T08:00:00Z",
  last_activity_at: "2030-08-29T08:00:00Z",
  expires_at: "2030-09-05T08:00:00Z",
  lease_generation: 1,
  writable: true,
  answered_count: 0,
  questions,
};

const emptyHistory: PracticeHistoryResponse = {
  qualified: false,
  latest: null,
  best: null,
  history: [],
};

const readySummary: PracticeSummaryResponse = {
  availability: "ready",
  can_start: true,
  reason_codes: [],
  readiness_status: "ready",
  active_attempt: null,
  qualified: false,
  latest: null,
  best: null,
};

function renderPractice(client: ApiClient) {
  return render(
    <SessionProvider client={client}>
      <MemoryRouter>
        <EmployeePracticePage />
      </MemoryRouter>
    </SessionProvider>,
  );
}

describe("Employee Practice", () => {
  it("starts exactly ten questions and saves an answer without revealing feedback", async () => {
    const user = userEvent.setup();
    const requests: Array<{ path: string; options?: RequestOptions }> = [];
    const client: ApiClient = {
      getSession: () => Promise.resolve(session),
      request: <T,>(path: string, requestOptions?: RequestOptions) => {
        requests.push({ path, options: requestOptions });
        if (path === "/me/training/practice") return Promise.resolve(readySummary as T);
        if (path === "/me/training/practice/attempts") {
          return Promise.resolve(emptyHistory as T);
        }
        if (path.includes("/practice/attempts?")) {
          return Promise.resolve({ attempt, created: true, replayed: false } as T);
        }
        if (path.endsWith("/answer")) {
          return Promise.resolve({
            answer: {
              id: "answer-1",
              answer_payload: { mechanic: "single_choice", option_id: "question-1-a" },
              submitted_at: "2030-08-29T08:01:00Z",
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

    renderPractice(client);
    await user.click(await screen.findByRole("button", { name: "Почати Практику" }));

    expect(await screen.findByRole("heading", { name: "Питання 1" })).toBeInTheDocument();
    expect(screen.getByText("0 з 10 відповідей збережено")).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("Правильно");
    expect(document.body).not.toHaveTextContent("Перевірений факт");

    await user.click(screen.getByRole("radio", { name: "Борщ" }));
    await user.click(screen.getByRole("button", { name: "Зберегти відповідь" }));

    expect(await screen.findByRole("heading", { name: "Питання 2" })).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("Правильно");
    expect(document.body).not.toHaveTextContent("Перевірений факт");
    const answerRequest = requests.find(({ path }) => path.endsWith("/answer"));
    expect(answerRequest?.options?.body).toEqual({
      attempt_question_id: "question-1",
      answer_payload: { mechanic: "single_choice", option_id: "question-1-a" },
      lease_generation: 1,
    });
    expect(answerRequest?.options?.csrfToken).toBe("csrf-safe");
    expect(typeof answerRequest?.options?.idempotencyKey).toBe("string");
  });

  it("resumes an active attempt read-only and supports explicit device takeover", async () => {
    const user = userEvent.setup();
    const requests: Array<{ path: string; options?: RequestOptions }> = [];
    const client: ApiClient = {
      getSession: () => Promise.resolve(session),
      request: <T,>(path: string, requestOptions?: RequestOptions) => {
        requests.push({ path, options: requestOptions });
        if (path.endsWith("/takeover")) {
          return Promise.resolve({
            attempt_id: "attempt-1",
            lease_generation: 2,
            replayed: false,
          } as T);
        }
        if (path === "/me/training/practice") {
          return Promise.resolve({
            ...readySummary,
            active_attempt: { ...attempt, writable: false },
          } as T);
        }
        if (path === "/me/training/practice/attempts") {
          return Promise.resolve(emptyHistory as T);
        }
        throw new Error(`Unexpected request: ${path}`);
      },
    };

    renderPractice(client);

    expect(await screen.findByText("Відкрито на іншому пристрої")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Борщ" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Продовжити на цьому пристрої" }));

    await waitFor(() => expect(screen.getByRole("radio", { name: "Борщ" })).toBeEnabled());
    const takeoverRequest = requests.find(({ path }) => path.endsWith("/takeover"));
    expect(takeoverRequest?.options?.csrfToken).toBe("csrf-safe");
    expect(typeof takeoverRequest?.options?.idempotencyKey).toBe("string");
  });

  it("reveals review and durable eligibility only after explicit finish", async () => {
    const user = userEvent.setup();
    const completedQuestions = questions.map((question, index) => ({
      ...question,
      saved_answer: {
        id: `answer-${index + 1}`,
        answer_payload: { mechanic: "single_choice", option_id: `${question.id}-a` },
        submitted_at: "2030-08-29T08:01:00Z",
      },
    }));
    const activeAttempt: PracticeAttempt = {
      ...attempt,
      answered_count: 10,
      questions: completedQuestions,
    };
    const resultSummary = {
      result_id: "result-1",
      attempt_id: "attempt-1",
      assessment_version_id: "assessment-version-1",
      completed_at: "2030-08-29T08:05:00Z",
      correct_count: 6,
      total_count: 10 as const,
      score_basis_points: 6000,
      knowledge_level: "good" as const,
      critical_error_count: 1,
    };
    const finish: PracticeFinishResponse = {
      result: {
        id: "result-1",
        correct_count: 6,
        total_count: 10,
        score_basis_points: 6000,
        knowledge_level: "good",
        pass_status: null,
        critical_error_count: 1,
        completed_at: "2030-08-29T08:05:00Z",
      },
      qualified: true,
      eligibility_earned: true,
      review: completedQuestions.map((question, index) => ({
        attempt_question_id: question.id,
        position: index,
        mechanic: question.mechanic,
        prompt_payload: question.prompt_payload,
        options: question.options,
        answer: question.saved_answer,
        is_correct: index < 6,
        correct_option_ids: [`${question.id}-${index < 6 ? "a" : "b"}`],
        explanation_payload: { text: `Перевірений факт ${index + 1}` },
        is_critical: index === 9,
        is_critical_error: index === 9,
      })),
      replayed: false,
    };
    let historyCalls = 0;
    const requests: Array<{ path: string; options?: RequestOptions }> = [];
    const client: ApiClient = {
      getSession: () => Promise.resolve(session),
      request: <T,>(path: string, requestOptions?: RequestOptions) => {
        requests.push({ path, options: requestOptions });
        if (path === "/me/training/practice") {
          return Promise.resolve({ ...readySummary, active_attempt: activeAttempt } as T);
        }
        if (path === "/me/training/practice/attempts") {
          historyCalls += 1;
          return Promise.resolve(
            (historyCalls === 1
              ? emptyHistory
              : {
                  qualified: true,
                  latest: resultSummary,
                  best: resultSummary,
                  history: [resultSummary],
                }) as T,
          );
        }
        if (path.endsWith("/finish")) return Promise.resolve(finish as T);
        throw new Error(`Unexpected request: ${path}`);
      },
    };

    renderPractice(client);

    expect(await screen.findByText("Усі 10 відповідей збережено")).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("Перевірений факт 1");
    expect(document.body).not.toHaveTextContent("Правильно");
    await user.click(screen.getByRole("button", { name: "Завершити Практику" }));

    expect(
      await screen.findByRole("heading", { name: "6 з 10 правильних відповідей" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Перевірений факт 1")).toBeInTheDocument();
    expect(screen.getByText("Критична помилка щодо алергенів.")).toBeInTheDocument();
    expect(screen.getByText("Останній результат")).toBeInTheDocument();
    expect(screen.getByText("Найкращий результат")).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("Пройдено");
    expect(document.body).not.toHaveTextContent("Не пройдено");
    const finishRequest = requests.find(({ path }) => path.endsWith("/finish"));
    expect(finishRequest?.options?.body).toEqual({ lease_generation: 1 });
    expect(finishRequest?.options?.csrfToken).toBe("csrf-safe");
    expect(typeof finishRequest?.options?.idempotencyKey).toBe("string");
  });
});

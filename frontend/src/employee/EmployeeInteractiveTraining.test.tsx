import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { ApiClient, RequestOptions } from "../api/client";
import { ApiError } from "../api/client";
import { EmployeeInteractiveTraining } from "./EmployeeInteractiveTraining";

const option = (id: string, text: string, position: number) => ({
  id,
  position,
  payload: { text },
});

const question = (id: string, position: number, stem: string) => ({
  id,
  position,
  mechanic: "single_choice",
  prompt_payload: { stem },
  options: [option(`${id}-a`, "Борщ", 0), option(`${id}-b`, "Салат", 1)],
  answered: false,
  confirmed_answer: null,
  feedback: null,
});

const attempt = {
  id: "attempt-1",
  lesson_id: "lesson-1",
  lesson_version_id: "lesson-version-1",
  assessment_version_id: "assessment-version-1",
  status: "in_progress",
  presentation_locale: "uk",
  started_at: "2030-08-29T08:00:00Z",
  expires_at: "2030-09-05T08:00:00Z",
  lease_generation: 1,
  writable: true,
  questions: Array.from({ length: 5 }, (_, index) =>
    question(`question-${index + 1}`, index, `Питання ${index + 1}`),
  ),
};

const emptySummary = {
  lesson_id: "lesson-1",
  lesson_version_id: "lesson-version-1",
  assessment_version_id: "assessment-version-1",
  availability: "ready",
  can_start: true,
  reason_codes: [],
  readiness_status: "ready",
  active_attempt: null,
  latest: null,
  best: null,
  history: [],
};

function renderTraining(client: ApiClient, lessonCompleted = true) {
  render(
    <MemoryRouter>
      <EmployeeInteractiveTraining
        client={client}
        csrfToken="csrf-safe"
        lessonCompleted={lessonCompleted}
        lessonId="lesson-1"
        preferredLocale="uk"
      />
    </MemoryRouter>,
  );
}

describe("Employee Interactive Training", () => {
  it("does not load or expose practice before explicit lesson completion", () => {
    const requests: string[] = [];
    const client: ApiClient = {
      getSession: () => Promise.reject(new Error("unused")),
      request: <T,>(path: string) => {
        requests.push(path);
        return Promise.resolve(emptySummary as T);
      },
    };

    renderTraining(client, false);

    expect(screen.getByRole("heading", { name: "Інтерактивне тренування" })).toBeInTheDocument();
    expect(screen.getByText("Спочатку завершіть урок")).toBeInTheDocument();
    expect(requests).toHaveLength(0);
  });

  it("starts an exact five-question attempt and reveals feedback only after confirmation", async () => {
    const user = userEvent.setup();
    const requests: Array<{ path: string; options?: RequestOptions }> = [];
    let resolveAnswer: ((value: unknown) => void) | undefined;
    const answerResponse = new Promise((resolve) => {
      resolveAnswer = resolve;
    });
    const client: ApiClient = {
      getSession: () => Promise.reject(new Error("unused")),
      request: <T,>(path: string, options?: RequestOptions) => {
        requests.push({ path, options });
        if (path.includes("/interactive-training/attempts?")) {
          return Promise.resolve({ attempt, created: true, replayed: false } as T);
        }
        if (path.endsWith("/answer")) return answerResponse as Promise<T>;
        return Promise.resolve(emptySummary as T);
      },
    };

    renderTraining(client);
    await user.click(await screen.findByRole("button", { name: "Почати тренування" }));

    expect(await screen.findByRole("heading", { name: "Питання 1" })).toBeInTheDocument();
    expect(screen.getByText("1 з 5")).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("Правильна відповідь");
    expect(document.body).not.toHaveTextContent("Перевірений факт");

    await user.click(screen.getByRole("radio", { name: "Борщ" }));
    await user.click(screen.getByRole("button", { name: "Підтвердити відповідь" }));
    expect(screen.getByRole("button", { name: "Зберігаємо відповідь…" })).toBeDisabled();
    expect(document.body).not.toHaveTextContent("Правильна відповідь");

    resolveAnswer?.({
      answer: {
        id: "answer-1",
        answer_payload: { mechanic: "single_choice", option_id: "question-1-a" },
        is_correct: true,
        submitted_at: "2030-08-29T08:01:00Z",
      },
      feedback: {
        is_correct: true,
        correct_option_ids: ["question-1-a"],
        explanation_payload: { text: "Перевірений факт" },
      },
      next_question_id: "question-2",
      attempt_status: "in_progress",
      result: null,
      replayed: false,
    });

    expect(await screen.findByRole("status")).toHaveTextContent("Правильна відповідь");
    expect(screen.getByText("Перевірений факт")).toBeInTheDocument();
    const answerRequest = requests.find(({ path }) => path.endsWith("/answer"));
    expect(answerRequest?.options?.csrfToken).toBe("csrf-safe");
    expect(typeof answerRequest?.options?.idempotencyKey).toBe("string");
    expect(answerRequest?.options?.body).toEqual({
      attempt_question_id: "question-1",
      answer_payload: { mechanic: "single_choice", option_id: "question-1-a" },
      lease_generation: 1,
    });
  });

  it("keeps the selected answer retryable after a failed save", async () => {
    const user = userEvent.setup();
    let answerCalls = 0;
    const answerKeys: Array<string | undefined> = [];
    const client: ApiClient = {
      getSession: () => Promise.reject(new Error("unused")),
      request: <T,>(path: string, options?: RequestOptions) => {
        if (path.includes("/interactive-training/attempts?")) {
          return Promise.resolve({ attempt, created: true, replayed: false } as T);
        }
        if (path.endsWith("/answer")) {
          answerCalls += 1;
          answerKeys.push(options?.idempotencyKey);
          return Promise.reject(new ApiError(0, { code: "NETWORK_ERROR", message: "Offline" }));
        }
        return Promise.resolve(emptySummary as T);
      },
    };

    renderTraining(client);
    await user.click(await screen.findByRole("button", { name: "Почати тренування" }));
    await user.click(await screen.findByRole("radio", { name: "Борщ" }));
    await user.click(screen.getByRole("button", { name: "Підтвердити відповідь" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Відповідь не збережено");
    expect(screen.getByRole("radio", { name: "Борщ" })).toBeChecked();
    const retry = screen.getByRole("button", { name: "Спробувати ще раз" });
    expect(retry).toBeEnabled();
    await user.click(retry);
    await waitFor(() => expect(answerCalls).toBe(2));
    expect(answerKeys[0]).toBe(answerKeys[1]);
  });

  it("resumes the next unanswered question and supports explicit device takeover", async () => {
    const user = userEvent.setup();
    const resumedAttempt = {
      ...attempt,
      writable: false,
      questions: [
        {
          ...attempt.questions[0],
          answered: true,
          confirmed_answer: {
            id: "answer-1",
            answer_payload: { mechanic: "single_choice", option_id: "question-1-a" },
            is_correct: true,
            submitted_at: "2030-08-29T08:01:00Z",
          },
          feedback: {
            is_correct: true,
            correct_option_ids: ["question-1-a"],
            explanation_payload: { text: "Перевірений факт" },
          },
        },
        ...attempt.questions.slice(1),
      ],
    };
    const requests: Array<{ path: string; options?: RequestOptions }> = [];
    const client: ApiClient = {
      getSession: () => Promise.reject(new Error("unused")),
      request: <T,>(path: string, options?: RequestOptions) => {
        requests.push({ path, options });
        if (path.endsWith("/takeover")) {
          return Promise.resolve({
            attempt_id: "attempt-1",
            lease_generation: 2,
            replayed: false,
          } as T);
        }
        return Promise.resolve({ ...emptySummary, active_attempt: resumedAttempt } as T);
      },
    };

    renderTraining(client);

    expect(await screen.findByRole("heading", { name: "Питання 2" })).toBeInTheDocument();
    expect(screen.getByText("Відкрито на іншому пристрої")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Продовжити на цьому пристрої" }));

    await waitFor(() => expect(screen.getByRole("radio", { name: "Борщ" })).toBeEnabled());
    const takeover = requests.find(({ path }) => path.endsWith("/takeover"));
    expect(takeover?.options?.csrfToken).toBe("csrf-safe");
    expect(typeof takeover?.options?.idempotencyKey).toBe("string");
  });

  it("shows the final Knowledge result and weak items after the fifth confirmed answer", async () => {
    const user = userEvent.setup();
    const finalAttempt = {
      ...attempt,
      questions: attempt.questions.map((item, index) =>
        index < 4
          ? {
              ...item,
              answered: true,
              confirmed_answer: {
                id: `answer-${index + 1}`,
                answer_payload: { mechanic: "single_choice", option_id: `${item.id}-a` },
                is_correct: index !== 2,
                submitted_at: "2030-08-29T08:01:00Z",
              },
              feedback: {
                is_correct: index !== 2,
                correct_option_ids: [`${item.id}-a`],
                explanation_payload: { text: `Пояснення ${index + 1}` },
              },
            }
          : item,
      ),
    };
    const client: ApiClient = {
      getSession: () => Promise.reject(new Error("unused")),
      request: <T,>(path: string) => {
        if (path.endsWith("/answer")) {
          return Promise.resolve({
            answer: {
              id: "answer-5",
              answer_payload: { mechanic: "single_choice", option_id: "question-5-b" },
              is_correct: false,
              submitted_at: "2030-08-29T08:05:00Z",
            },
            feedback: {
              is_correct: false,
              correct_option_ids: ["question-5-a"],
              explanation_payload: { text: "Пояснення 5" },
            },
            next_question_id: null,
            attempt_status: "completed",
            result: {
              id: "result-1",
              correct_count: 3,
              total_count: 5,
              score_basis_points: 6000,
              knowledge_level: "good",
              pass_status: null,
              completed_at: "2030-08-29T08:05:00Z",
            },
            replayed: false,
          } as T);
        }
        return Promise.resolve({ ...emptySummary, active_attempt: finalAttempt } as T);
      },
    };

    renderTraining(client);
    expect(await screen.findByRole("heading", { name: "Питання 5" })).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: "Салат" }));
    await user.click(screen.getByRole("button", { name: "Підтвердити відповідь" }));

    expect(
      await screen.findByRole("heading", { name: "3 з 5 правильних відповідей" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Добре знання · 60%")).toBeInTheDocument();
    expect(screen.getByText("Пояснення 5")).toBeInTheDocument();
    expect(screen.getByText("Борщ")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Що варто повторити" })).toBeInTheDocument();
    expect(screen.getByText("Питання 3")).toBeInTheDocument();
    expect(screen.getByText("Питання 5")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Повторити тренування" })).toBeEnabled();
    expect(screen.getByRole("link", { name: "Продовжити навчання" })).toHaveAttribute(
      "href",
      "/employee/learning",
    );
    expect(document.body).not.toHaveTextContent(/складено|не складено/i);
  });

  it("shows paused history with distinct Latest and Best without Passed or Failed", async () => {
    const client: ApiClient = {
      getSession: () => Promise.reject(new Error("unused")),
      request: <T,>() =>
        Promise.resolve({
          ...emptySummary,
          availability: "paused",
          can_start: false,
          readiness_status: "warning",
          latest: {
            result_id: "result-latest",
            attempt_id: "attempt-latest",
            assessment_version_id: "assessment-version-1",
            completed_at: "2030-08-29T10:00:00Z",
            correct_count: 3,
            total_count: 5,
            score_basis_points: 6000,
            knowledge_level: "good",
            is_current: true,
          },
          best: {
            result_id: "result-best",
            attempt_id: "attempt-best",
            assessment_version_id: "assessment-version-1",
            completed_at: "2030-08-28T10:00:00Z",
            correct_count: 5,
            total_count: 5,
            score_basis_points: 10000,
            knowledge_level: "strong",
            is_current: true,
          },
          history: [
            {
              result_id: "result-latest",
              attempt_id: "attempt-latest",
              assessment_version_id: "assessment-version-1",
              completed_at: "2030-08-29T10:00:00Z",
              correct_count: 3,
              total_count: 5,
              score_basis_points: 6000,
              knowledge_level: "good",
              is_current: true,
            },
            {
              result_id: "result-best",
              attempt_id: "attempt-best",
              assessment_version_id: "assessment-version-1",
              completed_at: "2030-08-28T10:00:00Z",
              correct_count: 5,
              total_count: 5,
              score_basis_points: 10000,
              knowledge_level: "strong",
              is_current: true,
            },
          ],
        } as T),
    };

    renderTraining(client);

    expect(await screen.findByText("Навчання призупинено")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Останній результат" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Найкращий результат" })).toBeInTheDocument();
    expect(screen.getByText("3 з 5")).toBeInTheDocument();
    expect(screen.getByText("5 з 5")).toBeInTheDocument();
    expect(screen.getByText("Історія спроб")).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(/складено|не складено/i);
    expect(screen.queryByRole("button", { name: /тренування/i })).not.toBeInTheDocument();
  });
});

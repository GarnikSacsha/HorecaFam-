import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ApiClient } from "../api/client";
import type { SessionResponse } from "../api/contracts";
import { SessionProvider } from "../session/SessionContext";
import { AdminResultDetailPage } from "./AdminResultDetailPage";

it("opens an existing completed exam review with actual answers and score", async () => {
  const session: SessionResponse = {
    user: { id: "admin", email: "admin@example.com", preferred_locale: "uk" },
    session: { id: "session", absolute_expires_at: "2030-09-01T00:00:00Z", mfa_verified: true },
    organization_access: [
      {
        organization_id: "org",
        is_organization_admin: true,
        is_employee: false,
        membership_status: null,
      },
    ],
    platform_operator: false,
    csrf_token: "test",
  };
  const result = {
    result_id: "result",
    attempt_id: "attempt",
    correct_count: 19,
    total_count: 20,
    score_basis_points: 9500,
    pass_status: "passed",
    critical_error_count: 0,
    completed_at: "2026-09-17T12:00:00Z",
  };
  const paths: string[] = [];
  const client: ApiClient = {
    getSession: () => Promise.resolve(session),
    request: <T,>(path: string) => {
      paths.push(path);
      if (path.endsWith("/final-exams/attempt"))
        return Promise.resolve({
          result: { ...result, id: "result" },
          review: [
            {
              attempt_question_id: "q",
              position: 0,
              prompt_payload: { stem: "Який напій?" },
              options: [
                { id: "a", payload: { text: "Чай" } },
                { id: "b", payload: { text: "Кава" } },
              ],
              answer: { answer_payload: { option_id: "a" } },
              correct_option_ids: ["b"],
              is_correct: false,
              explanation_payload: { text: "Повторіть опис кави." },
            },
          ],
        } as T);
      if (path.endsWith("/employees/employee"))
        return Promise.resolve({
          employee: {
            first_name: "Тест",
            current_training_status: "completed",
            latest_practice_score_basis_points: 8000,
          },
          final_exam: {
            certification: { certified_at: result.completed_at },
            latest: result,
            best: result,
            history: [result],
          },
        } as T);
      return Promise.resolve({ items: [] } as T);
    },
  };
  render(
    <SessionProvider client={client}>
      <MemoryRouter initialEntries={["/admin/results/employee"]}>
        <Routes>
          <Route path="/admin/results/:employeeId" element={<AdminResultDetailPage />} />
        </Routes>
      </MemoryRouter>
    </SessionProvider>,
  );
  await userEvent.click(await screen.findByRole("button", { name: "Розбір спроби" }));
  expect(await screen.findByText("Повторіть опис кави.")).toBeInTheDocument();
  expect(paths).toContain("/organizations/org/results/final-exams/attempt");
  expect(screen.getAllByText("95%").length).toBeGreaterThan(0);
});

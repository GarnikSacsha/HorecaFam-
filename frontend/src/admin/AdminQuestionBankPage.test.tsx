import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { ApiError, type ApiClient, type RequestOptions } from "../api/client";
import type { SessionResponse } from "../api/contracts";
import { SessionProvider } from "../session/SessionContext";
import { AdminQuestionBankPage } from "./AdminQuestionBankPage";

const session: SessionResponse = {
  user: { id: "admin-1", email: "admin@example.com", preferred_locale: "uk" },
  session: { id: "session-1", absolute_expires_at: "2030-09-01T00:00:00Z", mfa_verified: true },
  organization_access: [
    {
      organization_id: "organization-1",
      membership_status: null,
      is_employee: false,
      is_organization_admin: true,
    },
  ],
  platform_operator: false,
  csrf_token: "csrf-safe",
};

const candidates = [
  {
    id: "candidate-1",
    training_version_id: "training-version-1",
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
    revision: 3,
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
  },
  {
    id: "candidate-2",
    training_version_id: "training-version-1",
    lesson_version_id: "lesson-version-2",
    mechanic: "single_choice",
    prompt_payload: {
      locale: "uk",
      stem: "До якої категорії належить Цезар?",
      options: [
        { stable_key: "soups", text: "Супи" },
        { stable_key: "salads", text: "Салати" },
      ],
    },
    answer_payload: { correct_option_keys: ["salads"] },
    explanation_payload: { locale: "uk", text: "Цезар належить до категорії салатів." },
    source_fingerprint: "b".repeat(64),
    status: "needs_review",
    revision: 1,
    reviewed_at: null,
    rejection_reason_code: null,
    sources: [
      {
        source_role: "correct_fact",
        menu_item_version_id: "menu-item-version-2",
        menu_item_version_component_id: null,
        menu_item_version_allergen_id: null,
      },
    ],
  },
] as const;

const readiness = {
  training_version_id: "training-version-1",
  lessons: [
    {
      assessment_version_id: "assessment-version-1",
      lesson_id: "lesson-1",
      lesson_version_id: "lesson-version-1",
      status: "warning",
      eligible_count: 5,
      required_count: 5,
      coverage_evidence: { distinct_coverage_count: 5 },
      rotation_supported: false,
      basis_fingerprint: "c".repeat(64),
      blocking_codes: [],
      warning_codes: ["REPEAT_ROTATION_LIMITED"],
      computed_at: "2030-08-29T10:00:00Z",
      can_start: true,
    },
  ],
};

function questionBankClient(
  requests: Array<{ path: string; options?: RequestOptions }>,
  staleApproval = false,
  batchFails = false,
): ApiClient {
  return {
    getSession: () => Promise.resolve(session),
    request: <T,>(path: string, options?: RequestOptions) => {
      requests.push({ path, options });
      if (path.endsWith("/locations"))
        return Promise.resolve([
          {
            id: "location-1",
            organization_id: "organization-1",
            name: "Хрещатик",
            status: "active",
            address: null,
            timezone: "Europe/Kyiv",
          },
        ] as T);
      if (path.endsWith("/menu-versions"))
        return Promise.resolve({
          menu_id: "menu-1",
          organization_id: "organization-1",
          location_id: "location-1",
          current_published: { id: "menu-version-1", version_number: 4, status: "published" },
          draft: null,
          archived: [],
        } as T);
      if (path.endsWith("/training-versions"))
        return Promise.resolve({
          published: { id: "training-version-1", version_number: 2, status: "published" },
          draft: null,
          archived: [],
        } as T);
      if (path.includes("/interactive-training/readiness")) return Promise.resolve(readiness as T);
      if (path.includes("/question-candidates?") || path.endsWith("/question-candidates"))
        return Promise.resolve({ items: candidates, total: 2 } as T);
      if (path.endsWith("/generate"))
        return Promise.resolve({
          created_count: 2,
          existing_count: 0,
          stale_candidate_count: 0,
          stale_question_count: 0,
          replayed: false,
        } as T);
      if (path.endsWith("/batch-approve") && batchFails)
        return Promise.reject(
          new ApiError(409, { code: "REVISION_CONFLICT", message: "Batch is stale" }),
        );
      if (path.endsWith("/batch-approve")) return Promise.resolve({ items: [] } as T);
      if (path.endsWith("/candidate-1/approve") && staleApproval)
        return Promise.reject(
          new ApiError(409, { code: "QUESTION_CANDIDATE_STALE", message: "Candidate is stale" }),
        );
      if (path.endsWith("/candidate-1/approve"))
        return Promise.resolve({ candidate: { ...candidates[0], status: "approved" } } as T);
      return Promise.resolve({} as T);
    },
  };
}

function renderPage(client: ApiClient) {
  return render(
    <SessionProvider client={client}>
      <MemoryRouter>
        <AdminQuestionBankPage />
      </MemoryRouter>
    </SessionProvider>,
  );
}

describe("Admin Question Bank", () => {
  it("shows exact queue counts, provenance and lesson readiness, then generates for exact versions", async () => {
    const requests: Array<{ path: string; options?: RequestOptions }> = [];
    const user = userEvent.setup();
    renderPage(questionBankClient(requests));

    expect(await screen.findByRole("heading", { name: "Банк питань" })).toBeInTheDocument();
    expect(await screen.findByText("2 кандидати")).toBeInTheDocument();
    expect(screen.getByText("До якої категорії належить Борщ?")).toBeInTheDocument();
    expect(screen.getByText("menu-item-version-1")).toBeInTheDocument();
    expect(screen.getAllByText("Один варіант")[0]).toBeInTheDocument();
    expect(screen.getByText("REPEAT_ROTATION_LIMITED")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Згенерувати кандидатів" }));
    const generated = requests.find(({ path }) => path.endsWith("/generate"));
    expect(generated?.options?.body).toEqual({
      menu_version_id: "menu-version-1",
      training_version_id: "training-version-1",
    });
    expect(generated?.options?.csrfToken).toBe("csrf-safe");
    expect(typeof generated?.options?.idempotencyKey).toBe("string");
  });

  it("sends one atomic batch with the selected candidate revisions", async () => {
    const requests: Array<{ path: string; options?: RequestOptions }> = [];
    const user = userEvent.setup();
    renderPage(questionBankClient(requests));

    await screen.findByText("До якої категорії належить Борщ?");
    await user.click(screen.getByRole("checkbox", { name: /Вибрати.*Борщ/ }));
    await user.click(screen.getByRole("checkbox", { name: /Вибрати.*Цезар/ }));
    await user.click(screen.getByRole("button", { name: "Схвалити вибрані (2)" }));

    const batch = requests.find(({ path }) => path.endsWith("/batch-approve"));
    expect(batch?.options?.body).toEqual({
      items: [
        { candidate_id: "candidate-1", expected_revision: 3 },
        { candidate_id: "candidate-2", expected_revision: 1 },
      ],
    });
    expect(batch?.options?.csrfToken).toBe("csrf-safe");
  });

  it("keeps an edited candidate recoverable when approval is stale", async () => {
    const requests: Array<{ path: string; options?: RequestOptions }> = [];
    const user = userEvent.setup();
    renderPage(questionBankClient(requests, true));

    const card = (await screen.findByText("До якої категорії належить Борщ?")).closest("article");
    expect(card).not.toBeNull();
    await user.click(within(card as HTMLElement).getByRole("button", { name: "Редагувати" }));
    const stem = within(card as HTMLElement).getByLabelText("Текст питання");
    await user.clear(stem);
    await user.type(stem, "Оновлене питання про Борщ");
    await user.click(
      within(card as HTMLElement).getByRole("button", { name: "Зберегти та схвалити" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Кандидат застарів");
    expect(stem).toHaveValue("Оновлене питання про Борщ");
    expect(screen.getByRole("button", { name: "Оновити дані" })).toBeEnabled();
    const approvalBody = requests.find(({ path }) => path.endsWith("/candidate-1/approve"))?.options
      ?.body as
      | {
          expected_revision?: number;
          edited_payload?: { prompt_payload?: { stem?: string } };
        }
      | undefined;
    expect(approvalBody?.expected_revision).toBe(3);
    expect(approvalBody?.edited_payload?.prompt_payload?.stem).toBe("Оновлене питання про Борщ");
  });

  it("announces an atomic batch failure without clearing the selection", async () => {
    const user = userEvent.setup();
    renderPage(questionBankClient([], false, true));

    await screen.findByText("До якої категорії належить Борщ?");
    await user.click(screen.getByRole("checkbox", { name: /Вибрати.*Борщ/ }));
    await user.click(screen.getByRole("checkbox", { name: /Вибрати.*Цезар/ }));
    await user.click(screen.getByRole("button", { name: "Схвалити вибрані (2)" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Жоден кандидат не змінений");
    expect(screen.getByRole("button", { name: "Схвалити вибрані (2)" })).toBeEnabled();
  });
});

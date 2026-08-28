import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import type { ApiClient, RequestOptions } from "../api/client";
import { ApiError } from "../api/client";
import type { SessionResponse } from "../api/contracts";
import { SessionProvider } from "../session/SessionContext";
import { AdminTrainingPage } from "./AdminTrainingPage";
import { AdminTrainingRolloutPanel } from "./AdminTrainingRolloutPanel";

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

const detail = {
  id: "training-version-1",
  training_id: "training-1",
  location_id: "location-1",
  version_number: 2,
  status: "draft",
  revision: 4,
  base_version_id: "published-training-1",
  module_count: 1,
  lesson_count: 2,
  created_at: "2030-08-27T00:00:00Z",
  published_at: null,
  archived_at: null,
  menu_version_id: "menu-version-1",
  modules: [
    {
      id: "module-version-1",
      domain_type: "menu",
      position: 0,
      title_uk: "Меню ресторану",
      description_uk: "Базові знання",
      required: true,
      translation_status_en: null,
      lessons: [
        {
          id: "lesson-1",
          position: 0,
          title_uk: "Супи",
          description_uk: null,
          required: true,
          estimated_minutes: 8,
          translation_status_en: null,
          content_blocks: [
            {
              id: "block-1",
              type: "text",
              position: 0,
              payload: { text_uk: "Про супи" },
              menu_item_id: null,
              asset: null,
            },
          ],
        },
        {
          id: "lesson-2",
          position: 1,
          title_uk: "Салати",
          description_uk: null,
          required: false,
          estimated_minutes: 5,
          translation_status_en: "ready",
          content_blocks: [],
        },
      ],
    },
  ],
};

const collection = {
  published: {
    ...detail,
    id: "published-training-1",
    status: "published",
    published_at: "2030-08-26T00:00:00Z",
  },
  draft: detail,
  archived: [],
};

const readiness = {
  training_id: "training-1",
  training_version_id: "training-version-1",
  organization_id: "organization-1",
  location_id: "location-1",
  revision: 4,
  can_publish: true,
  blocking_errors: [],
  warnings: [
    {
      code: "EN_TRANSLATION_PENDING",
      message: "Англійський переклад ще не готовий.",
      entity_type: "lesson",
      entity_id: "lesson-1",
    },
  ],
  counts: {
    module_count: 1,
    lesson_count: 2,
    required_lesson_count: 1,
    content_block_count: 1,
    required_asset_count: 0,
    ready_asset_count: 0,
    menu_item_link_count: 0,
  },
};

function trainingClient(
  requests: Array<{ path: string; options?: RequestOptions }>,
  conflict = false,
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
      if (path.endsWith("/training-versions")) return Promise.resolve(collection as T);
      if (path.endsWith("/readiness")) return Promise.resolve(readiness as T);
      if (!options?.method && path.endsWith("/training-version-1"))
        return Promise.resolve(detail as T);
      if (path.endsWith("/assets/upload-intents"))
        return Promise.resolve({
          asset_id: "asset-1",
          upload_url: "https://storage.test/upload",
          upload_fields: { key: "opaque-key" },
          expires_at: "2030-08-27T00:15:00Z",
        } as T);
      if (path.endsWith("/assets/asset-1/complete"))
        return Promise.resolve({
          id: "asset-1",
          original_filename: "dish.png",
          mime_type: "image/png",
          size_bytes: 4,
          status: "ready",
          ready_at: "2030-08-27T00:01:00Z",
          created_at: "2030-08-27T00:00:00Z",
        } as T);
      if (conflict && options?.method === "PATCH")
        return Promise.reject(
          new ApiError(409, {
            code: "REVISION_CONFLICT",
            message: "Чернетку вже змінено.",
          }),
        );
      if (path.endsWith("/publish"))
        return Promise.resolve({
          published: { ...detail, status: "published" },
          previous_published_version_id: "published-training-1",
          employee_reference_switched: true,
          assignment_count: 0,
          completion_count: 0,
          progress_count: 0,
          rollout_count: 0,
          notification_count: 0,
        } as T);
      return Promise.resolve({ revision: 5 } as T);
    },
  };
}

describe("Admin Training workspace", () => {
  it("edits the fixed module, reorders lessons and publishes the readiness revision", async () => {
    const requests: Array<{ path: string; options?: RequestOptions }> = [];
    const user = userEvent.setup();
    render(
      <SessionProvider client={trainingClient(requests)}>
        <MemoryRouter>
          <AdminTrainingPage />
        </MemoryRouter>
      </SessionProvider>,
    );

    expect(await screen.findByRole("heading", { name: "Навчальні матеріали" })).toBeInTheDocument();
    expect(await screen.findByText("Англійський переклад ще не готовий.")).toBeInTheDocument();

    const moduleForm = screen.getByRole("form", { name: "Налаштування модуля" });
    const moduleTitle = within(moduleForm).getByLabelText("Назва модуля");
    await user.clear(moduleTitle);
    await user.type(moduleTitle, "Меню Bacara");
    await user.click(within(moduleForm).getByRole("button", { name: "Зберегти модуль" }));
    expect(
      requests.some(
        ({ path, options }) =>
          path.endsWith("/modules/module-version-1") &&
          options?.method === "PATCH" &&
          JSON.stringify(options.body) ===
            JSON.stringify({
              expected_revision: 4,
              title_uk: "Меню Bacara",
              description_uk: "Базові знання",
              required: true,
            }),
      ),
    ).toBe(true);

    await user.click(screen.getByRole("button", { name: "Перемістити Супи нижче" }));
    expect(
      requests.some(
        ({ path, options }) =>
          path.endsWith("/lessons/reorder") &&
          options?.method === "POST" &&
          JSON.stringify(options.body) ===
            JSON.stringify({ expected_revision: 4, ordered_ids: ["lesson-2", "lesson-1"] }),
      ),
    ).toBe(true);

    await user.click(screen.getByRole("button", { name: "Опублікувати навчання" }));
    expect(
      screen.getByRole("dialog", { name: "Опублікувати цю версію навчання?" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Опублікувати" }));
    const publishRequest = requests.find(({ path }) => path.endsWith("/publish"));
    expect(publishRequest?.options?.body).toEqual({ expected_revision: 4 });
    expect(publishRequest?.options?.csrfToken).toBe("csrf-safe");
    expect(typeof publishRequest?.options?.idempotencyKey).toBe("string");
  });

  it("preserves local input and announces revision conflicts", async () => {
    const user = userEvent.setup();
    render(
      <SessionProvider client={trainingClient([], true)}>
        <MemoryRouter>
          <AdminTrainingPage />
        </MemoryRouter>
      </SessionProvider>,
    );
    const moduleTitle = await screen.findByLabelText("Назва модуля");
    await user.clear(moduleTitle);
    await user.type(moduleTitle, "Локальний текст");
    await user.click(screen.getByRole("button", { name: "Зберегти модуль" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Чернетку вже змінили");
    expect(moduleTitle).toHaveValue("Локальний текст");
    expect(screen.getByRole("button", { name: "Оновити дані" })).toBeInTheDocument();
  });

  it("keeps save state in an aria-live region", async () => {
    render(
      <SessionProvider client={trainingClient([])}>
        <MemoryRouter>
          <AdminTrainingPage />
        </MemoryRouter>
      </SessionProvider>,
    );
    expect(await screen.findByText("Збережено")).toHaveAttribute("aria-live", "polite");
  });

  it("uploads a private image before linking it to a lesson block", async () => {
    const requests: Array<{ path: string; options?: RequestOptions }> = [];
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
    render(
      <SessionProvider client={trainingClient(requests)}>
        <MemoryRouter>
          <AdminTrainingPage />
        </MemoryRouter>
      </SessionProvider>,
    );
    await screen.findByText("Англійський переклад ще не готовий.");
    await user.selectOptions(screen.getByLabelText("Тип блока"), "image");
    await user.upload(
      screen.getByLabelText("Зображення уроку"),
      new File([new Uint8Array([1, 2, 3, 4])], "dish.png", { type: "image/png" }),
    );
    await user.click(screen.getByRole("button", { name: "Завантажити зображення" }));
    expect(await screen.findByText("Зображення готове")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Основний текст українською"), "Подача страви");
    await user.click(screen.getByRole("button", { name: "Додати блок" }));

    expect(
      requests.some(
        ({ path, options }) =>
          path.endsWith("/lessons/lesson-1/content-blocks") &&
          options?.method === "POST" &&
          JSON.stringify(options.body) ===
            JSON.stringify({
              expected_revision: 4,
              type: "image",
              payload: { asset_id: "asset-1", alt_uk: "Подача страви", caption_uk: null },
            }),
      ),
    ).toBe(true);
    vi.unstubAllGlobals();
  });

  it("previews changed lessons, records the preserve choice and confirms rollout", async () => {
    const requests: Array<{ path: string; options?: RequestOptions }> = [];
    const base = trainingClient(requests);
    let ruleResolved = false;
    let previewed = false;
    let completed = false;
    const rollout = () => ({
      id: "rollout-1",
      organization_id: "organization-1",
      location_id: "location-1",
      training_id: "training-1",
      from_version: {
        id: "published-training-1",
        version_number: 1,
        status: "archived",
        revision: 3,
      },
      to_version: {
        id: "training-version-1",
        version_number: 2,
        status: "published",
        revision: 4,
      },
      status: completed ? "completed" : previewed ? "preview_ready" : "draft",
      revision: completed ? 5 : previewed ? 4 : ruleResolved ? 3 : 2,
      rules: [
        {
          lesson_id: "lesson-1",
          from_lesson_version_id: "lesson-version-old",
          to_lesson_version_id: "lesson-version-new",
          rule: ruleResolved ? "preserve_completion" : null,
          requires_admin_decision: !ruleResolved,
          decided_by_user_id: ruleResolved ? "admin-1" : null,
          decided_at: ruleResolved ? "2030-08-28T11:00:00Z" : null,
        },
      ],
      employee_impacts: [
        {
          employee_profile_id: "employee-1",
          source_assignment_id: "assignment-1",
          target_assignment_id: completed ? "assignment-2" : null,
          current_required_count: 3,
          current_completed_count: 3,
          current_progress_percentage: 100,
          projected_required_count: 3,
          projected_completed_count: ruleResolved ? 2 : 1,
          projected_progress_percentage: ruleResolved ? 66 : 33,
          lesson_impact: { materially_changed: ["lesson-1"] },
          validation_codes: [],
          warning_codes: [],
        },
      ],
      impact_counts: { employee_count: 1, unresolved_rule_count: ruleResolved ? 0 : 1 },
      is_stale: ruleResolved && !previewed,
      warning_codes: [],
      previewed_at: previewed ? "2030-08-28T11:10:00Z" : null,
      created_at: "2030-08-28T10:00:00Z",
    });
    const client: ApiClient = {
      getSession: () => base.getSession(),
      request: <T,>(path: string, options?: RequestOptions) => {
        if (path.endsWith("/publish")) {
          requests.push({ path, options });
          return Promise.resolve({
            published: { ...detail, status: "published", version_number: 2 },
            previous_published_version_id: "published-training-1",
            employee_reference_switched: true,
            assignment_count: 0,
            completion_count: 0,
            progress_count: 0,
            rollout_count: 1,
            notification_count: 0,
            rollout_id: "rollout-1",
          } as T);
        }
        if (path.endsWith("/lesson-rules/lesson-1")) {
          requests.push({ path, options });
          ruleResolved = true;
          previewed = false;
          return Promise.resolve(rollout() as T);
        }
        if (path.endsWith("/rollout-1/preview")) {
          requests.push({ path, options });
          previewed = true;
          return Promise.resolve(rollout() as T);
        }
        if (path.endsWith("/rollout-1/confirm")) {
          requests.push({ path, options });
          completed = true;
          return Promise.resolve(rollout() as T);
        }
        if (path.endsWith("/training-rollouts/rollout-1")) return Promise.resolve(rollout() as T);
        return base.request<T>(path, options);
      },
    };
    const user = userEvent.setup();
    render(
      <SessionProvider client={client}>
        <MemoryRouter>
          <AdminTrainingPage />
        </MemoryRouter>
      </SessionProvider>,
    );

    await user.click(await screen.findByRole("button", { name: "Опублікувати навчання" }));
    await user.click(screen.getByRole("button", { name: "Опублікувати" }));
    expect(
      await screen.findByRole("heading", { name: "Перенесення прогресу" }),
    ).toBeInTheDocument();
    expect(screen.getByText("1 працівник")).toBeInTheDocument();
    expect(screen.getByText("1 рішення для змінених уроків")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Зберегти завершення" }));
    expect(await screen.findByText("Потрібен новий перегляд")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Оновити попередній перегляд" }));
    expect(await screen.findByText("Прогноз: 2 із 3 · 66%")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Підтвердити перенесення" }));
    await user.click(screen.getByRole("button", { name: "Перенести прогрес" }));
    expect(await screen.findByText("Перенесення завершено")).toBeInTheDocument();

    const ruleRequest = requests.find(({ path }) => path.endsWith("/lesson-rules/lesson-1"));
    expect(ruleRequest?.options?.body).toEqual({
      expected_revision: 2,
      rule: "preserve_completion",
    });
    const confirmRequest = requests.find(({ path }) => path.endsWith("/rollout-1/confirm"));
    expect(confirmRequest?.options?.body).toEqual({ expected_revision: 4 });
    expect(confirmRequest?.options?.csrfToken).toBe("csrf-safe");
    expect(typeof confirmRequest?.options?.idempotencyKey).toBe("string");
  });

  it("announces a stale rollout conflict and keeps the preview recoverable", async () => {
    const user = userEvent.setup();
    const preview = {
      id: "rollout-stale",
      organization_id: "organization-1",
      location_id: "location-1",
      training_id: "training-1",
      from_version: { id: "v1", version_number: 1, status: "archived", revision: 2 },
      to_version: { id: "v2", version_number: 2, status: "published", revision: 3 },
      status: "preview_ready",
      revision: 4,
      rules: [],
      employee_impacts: [],
      impact_counts: { employee_count: 1, unresolved_rule_count: 0 },
      is_stale: false,
      warning_codes: [],
      previewed_at: "2030-08-28T11:00:00Z",
      created_at: "2030-08-28T10:00:00Z",
    };
    const client: ApiClient = {
      getSession: () => Promise.resolve(session),
      request: <T,>(_path: string, options?: RequestOptions) =>
        options?.method === "POST"
          ? Promise.reject(
              new ApiError(409, {
                code: "TRAINING_ROLLOUT_STALE",
                message: "Rollout preview is stale",
              }),
            )
          : Promise.resolve(preview as T),
    };

    render(
      <AdminTrainingRolloutPanel
        client={client}
        csrfToken="csrf-safe"
        locationId="location-1"
        organizationId="organization-1"
        rolloutId="rollout-stale"
      />,
    );

    await user.click(await screen.findByRole("button", { name: "Підтвердити перенесення" }));
    await user.click(screen.getByRole("button", { name: "Перенести прогрес" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Попередній перегляд застарів");
    expect(screen.getByRole("button", { name: "Оновити дані" })).toBeEnabled();
  });
});

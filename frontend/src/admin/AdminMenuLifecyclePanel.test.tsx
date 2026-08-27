import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import type { ApiClient, RequestOptions } from "../api/client";
import type {
  MenuImportDetail,
  MenuReadinessResponse,
  MenuVersionDetail,
  SessionResponse,
} from "../api/contracts";
import { SessionProvider } from "../session/SessionContext";
import { AdminMenuLifecyclePanel } from "./AdminMenuLifecyclePanel";

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

const draft: MenuVersionDetail = {
  id: "draft-1",
  menu_id: "menu-1",
  organization_id: "organization-1",
  location_id: "location-1",
  version_number: 2,
  status: "draft",
  base_version_id: "published-1",
  revision: 4,
  section_count: 1,
  category_count: 1,
  item_count: 1,
  created_at: "2030-08-27T00:00:00Z",
  published_at: null,
  archived_at: null,
  sections: [],
};

const readiness: MenuReadinessResponse = {
  menu_id: "menu-1",
  menu_version_id: "draft-1",
  organization_id: "organization-1",
  location_id: "location-1",
  revision: 4,
  can_publish: true,
  blocking_errors: [],
  warnings: [
    {
      code: "EN_TRANSLATION_PENDING",
      message: "Англійський переклад ще не готовий.",
      entity_type: "menu_item",
      entity_id: "item-1",
    },
  ],
  required_training_asset_count: 0,
  ready_training_asset_count: 0,
  applicable_training_content_count: 0,
};

const preview: MenuImportDetail = {
  id: "import-1",
  organization_id: "organization-1",
  location_id: "location-1",
  menu_id: "menu-1",
  base_menu_version_id: "published-1",
  status: "ready_for_review",
  review_revision: 0,
  source_filename: "menu.json",
  source_reference: null,
  source_checksum: "a".repeat(64),
  section_count: 1,
  category_count: 1,
  item_count: 1,
  added_count: 0,
  changed_count: 1,
  removed_count: 0,
  unchanged_count: 0,
  blocker_count: 0,
  review_count: 1,
  warning_count: 0,
  findings: [
    {
      id: "finding-1",
      severity: "requires_review",
      code: "CRITICAL_FACT_CHANGE",
      entity_type: "menu_item",
      source_key: "borshch",
      message: "Критичні факти позиції змінено.",
      resolution_status: "unresolved",
      allowed_actions: ["confirm_critical_change"],
      resolution_action: null,
      target_entity_id: null,
      resolution_comment: null,
      resolved_at: null,
    },
  ],
  created_at: "2030-08-27T00:00:00Z",
  confirmed_at: null,
  failure_code: null,
};

describe("Admin Menu import and publish lifecycle", () => {
  it("keeps JSON preview, finding resolution and Draft confirm explicit", async () => {
    const requests: Array<{ path: string; options?: RequestOptions }> = [];
    const confirmedDraft = vi.fn();
    const client: ApiClient = {
      getSession: () => Promise.resolve(session),
      request: <T,>(path: string, options?: RequestOptions) => {
        requests.push({ path, options });
        if (path.endsWith("/readiness")) return Promise.resolve(readiness as T);
        if (path.endsWith("/menu-imports")) return Promise.resolve(preview as T);
        if (path.endsWith("/resolve"))
          return Promise.resolve({
            finding: {
              ...preview.findings[0],
              resolution_status: "resolved",
              resolution_action: "confirm_critical_change",
              resolved_at: "2030-08-27T01:00:00Z",
            },
            review_revision: 1,
          } as T);
        if (path.endsWith("/confirm"))
          return Promise.resolve({
            import: { ...preview, status: "confirmed", review_revision: 1 },
            draft: { ...draft, revision: 5 },
          } as T);
        throw new Error(`Unexpected request ${path}`);
      },
    };
    const user = userEvent.setup();
    render(
      <SessionProvider client={client}>
        <AdminMenuLifecyclePanel
          organizationId="organization-1"
          locationId="location-1"
          draft={draft}
          onDraftConfirmed={confirmedDraft}
          onPublished={vi.fn()}
        />
      </SessionProvider>,
    );
    const file = new File(["{}"], "menu.json", { type: "application/json" });
    Object.defineProperty(file, "text", {
      value: () => Promise.resolve('{"source_reference":null,"sections":[]}'),
    });
    await user.upload(screen.getByLabelText("JSON-файл меню"), file);
    await user.click(screen.getByRole("button", { name: "Перевірити JSON" }));
    expect(await screen.findByText("CRITICAL_FACT_CHANGE")).toBeInTheDocument();
    const importRequest = requests.find(({ path }) => path.endsWith("/menu-imports"));
    expect(importRequest?.options?.body).toEqual({
      source_reference: null,
      sections: [],
      source_filename: "menu.json",
    });
    expect(importRequest?.options?.csrfToken).toBe("csrf-safe");

    await user.click(screen.getByRole("button", { name: "Підтвердити критичну зміну" }));
    expect(await screen.findByText("Вирішено")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Підтвердити в чернетку" }));
    expect(confirmedDraft).toHaveBeenCalledWith({ ...draft, revision: 5 });
    const confirmRequest = requests.find(({ path }) => path.endsWith("/confirm"));
    expect(confirmRequest?.options?.body).toEqual({
      expected_revision: 1,
      acknowledge_warnings: false,
    });
  });

  it("requires a confirmation dialog and publishes the readiness revision", async () => {
    const requests: Array<{ path: string; options?: RequestOptions }> = [];
    const onPublished = vi.fn();
    const client: ApiClient = {
      getSession: () => Promise.resolve(session),
      request: <T,>(path: string, options?: RequestOptions) => {
        requests.push({ path, options });
        if (path.endsWith("/readiness")) return Promise.resolve(readiness as T);
        if (path.endsWith("/publish"))
          return Promise.resolve({
            published: { ...draft, status: "published", published_at: "2030-08-27T02:00:00Z" },
            previous_published_version_id: "published-1",
            diff_counts: { added: 0, changed: 1, removed: 0, unchanged: 0 },
            training_impact_counts: { none: 1, review: 0, required: 0 },
            applicability: {
              published_content_count: 0,
              assignment_count: 0,
              notification_count: 0,
            },
          } as T);
        throw new Error(`Unexpected request ${path}`);
      },
    };
    const user = userEvent.setup();
    render(
      <SessionProvider client={client}>
        <AdminMenuLifecyclePanel
          organizationId="organization-1"
          locationId="location-1"
          draft={draft}
          onDraftConfirmed={vi.fn()}
          onPublished={onPublished}
        />
      </SessionProvider>,
    );
    expect(await screen.findByText("Готово")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Опублікувати меню" }));
    expect(
      screen.getByRole("dialog", { name: "Опублікувати цю версію меню?" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Опублікувати" }));
    expect(onPublished).toHaveBeenCalledTimes(1);
    const request = requests.find(({ path }) => path.endsWith("/publish"));
    expect(request?.options?.body).toEqual({ expected_revision: 4 });
    expect(request?.options?.csrfToken).toBe("csrf-safe");
    expect(typeof request?.options?.idempotencyKey).toBe("string");
  });
});

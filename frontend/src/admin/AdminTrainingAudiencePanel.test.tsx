import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { ApiError, type ApiClient, type RequestOptions } from "../api/client";
import { SessionProvider } from "../session/SessionContext";
import type { SessionResponse } from "../api/contracts";
import { AdminTrainingAudiencePanel } from "./AdminTrainingAudiencePanel";

const session: SessionResponse = {
  user: { id: "admin", email: "admin@example.test", preferred_locale: "uk" },
  session: { id: "session", absolute_expires_at: "2030-09-01T00:00:00Z", mfa_verified: true },
  organization_access: [
    {
      organization_id: "org",
      membership_status: null,
      is_employee: false,
      is_organization_admin: true,
    },
  ],
  platform_operator: false,
  csrf_token: "synthetic-csrf",
};
const roles = ["Офіціант", "Кухар"].map((name_uk, index) => ({
  id: `role-${index}`,
  organization_id: "org",
  code: `role-${index}`,
  name_uk,
  status: "active",
}));
const audience = { training_version_id: "version", revision: 4, operational_role_ids: ["role-0"] };
function setup(handler?: (path: string, options?: RequestOptions) => unknown) {
  const requests: Array<{ path: string; options?: RequestOptions }> = [];
  const client: ApiClient = {
    getSession: () => Promise.resolve(session),
    request: <T,>(path: string, options?: RequestOptions) => {
      requests.push({ path, options });
      return Promise.resolve().then(() => {
        if (handler) return handler(path, options) as T;
        if (options?.method === "PUT")
          return { ...audience, revision: 5, operational_role_ids: ["role-1"] } as T;
        return (path.endsWith("operational-roles") ? roles : audience) as T;
      });
    },
  };
  const onSaved = vi.fn(() => Promise.resolve());
  const onBusyChange = vi.fn();
  const view = render(
    <SessionProvider client={client}>
      <AdminTrainingAudiencePanel
        organizationId="org"
        locationId="location"
        versionId="version"
        busy={false}
        onBusyChange={onBusyChange}
        onSaved={onSaved}
      />
    </SessionProvider>,
  );
  return { requests, client, onSaved, onBusyChange, ...view };
}

it("reads the exact selection and explicitly replaces it with CSRF and snapshot revision", async () => {
  const { requests, onSaved } = setup();
  const user = userEvent.setup();
  expect(await screen.findByLabelText("Офіціант")).toBeChecked();
  expect(screen.getByLabelText("Кухар")).not.toBeChecked();
  expect(requests.every(({ options }) => !options?.method)).toBe(true);
  await user.click(screen.getByLabelText("Офіціант"));
  expect(screen.getByRole("button", { name: "Зберегти аудиторію" })).toBeDisabled();
  await user.click(screen.getByLabelText("Кухар"));
  await user.click(screen.getByRole("button", { name: "Зберегти аудиторію" }));
  expect(await screen.findByText("Аудиторію збережено.")).toBeVisible();
  expect(requests.find(({ options }) => options?.method === "PUT")?.options).toMatchObject({
    body: { expected_revision: 4, operational_role_ids: ["role-1"] },
    csrfToken: "synthetic-csrf",
  });
  expect(onSaved).toHaveBeenCalledWith(5);
});

it("blocks saving after a failed read and supports explicit retry", async () => {
  let failed = true;
  setup((path) => {
    if (path.endsWith("operational-roles")) return roles;
    if (failed) throw new Error("offline");
    return audience;
  });
  await screen.findByRole("alert");
  expect(screen.queryByRole("button", { name: "Зберегти аудиторію" })).not.toBeInTheDocument();
  failed = false;
  await userEvent.click(screen.getByRole("button", { name: "Завантажити аудиторію знову" }));
  expect(await screen.findByLabelText("Офіціант")).toBeChecked();
});

it("preserves selection on conflict and requires an explicit reload before another save", async () => {
  setup((path, options) => {
    if (options?.method === "PUT")
      throw new ApiError(409, {
        code: "REVISION_CONFLICT",
        message: "stale",
        field_errors: [],
        request_id: "test",
      });
    return path.endsWith("operational-roles") ? roles : audience;
  });
  const user = userEvent.setup();
  await screen.findByLabelText("Кухар");
  await user.click(screen.getByLabelText("Кухар"));
  await user.click(screen.getByRole("button", { name: "Зберегти аудиторію" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Чернетку вже змінено");
  expect(screen.getByLabelText("Кухар")).toBeChecked();
  expect(screen.getByRole("button", { name: "Зберегти аудиторію" })).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "Завантажити аудиторію знову" }));
  expect(await screen.findByLabelText("Офіціант")).toBeChecked();
  expect(screen.getByLabelText("Кухар")).not.toBeChecked();
});

it("shows selected archived and unavailable roles until explicitly removed", async () => {
  setup((path) =>
    path.endsWith("operational-roles")
      ? [{ ...roles[0], status: "archived" }, roles[1]]
      : { ...audience, operational_role_ids: ["role-0", "missing"] },
  );
  const user = userEvent.setup();
  expect(await screen.findByLabelText("Офіціант · неактивна роль")).toBeChecked();
  expect(screen.getByLabelText("Недоступна роль · missing")).toBeChecked();
  expect(screen.getByRole("button", { name: "Зберегти аудиторію" })).toBeDisabled();
  await user.click(screen.getByLabelText("Офіціант · неактивна роль"));
  await user.click(screen.getByLabelText("Недоступна роль · missing"));
  await user.click(screen.getByLabelText("Кухар"));
  expect(screen.getByRole("button", { name: "Зберегти аудиторію" })).toBeEnabled();
});

it("keeps local choices after a failed save and retries without a duplicate request", async () => {
  let attempts = 0;
  let resolve!: (value: typeof audience) => void;
  const delayed = new Promise<typeof audience>((done) => {
    resolve = done;
  });
  const { requests } = setup((path, options) => {
    if (options?.method === "PUT") {
      attempts += 1;
      if (attempts === 1) throw new Error("offline");
      return delayed;
    }
    return path.endsWith("operational-roles") ? roles : audience;
  });
  const user = userEvent.setup();
  await screen.findByLabelText("Кухар");
  await user.click(screen.getByLabelText("Кухар"));
  await user.click(screen.getByRole("button", { name: "Зберегти аудиторію" }));
  await screen.findByRole("alert");
  expect(screen.getByLabelText("Кухар")).toBeChecked();
  await user.dblClick(screen.getByRole("button", { name: "Зберегти аудиторію" }));
  expect(screen.getByRole("button", { name: "Збереження аудиторії…" })).toBeDisabled();
  expect(requests.filter(({ options }) => options?.method === "PUT")).toHaveLength(2);
  await act(async () => {
    resolve({ ...audience, revision: 5, operational_role_ids: ["role-0", "role-1"] });
    await delayed;
  });
  expect(await screen.findByText("Аудиторію збережено.")).toBeVisible();
});

it("discards the previous version's late audience when the scope changes", async () => {
  let resolve!: (value: typeof audience) => void;
  const delayed = new Promise<typeof audience>((done) => {
    resolve = done;
  });
  const { rerender, client, onSaved, onBusyChange, requests } = setup((path) => {
    if (path.endsWith("operational-roles")) return roles;
    if (path.includes("/version-2/"))
      return {
        ...audience,
        training_version_id: "version-2",
        operational_role_ids: ["role-1"],
      };
    return delayed;
  });
  await waitFor(() =>
    expect(requests.some(({ path }) => path.endsWith("/version/audiences"))).toBe(true),
  );
  rerender(
    <SessionProvider client={client}>
      <AdminTrainingAudiencePanel
        organizationId="org"
        locationId="location-2"
        versionId="version-2"
        busy={false}
        onBusyChange={onBusyChange}
        onSaved={onSaved}
      />
    </SessionProvider>,
  );
  expect(await screen.findByLabelText("Кухар")).toBeChecked();
  await act(async () => {
    resolve(audience);
    await delayed;
  });
  expect(screen.getByLabelText("Кухар")).toBeChecked();
  expect(screen.getByLabelText("Офіціант")).not.toBeChecked();
  expect(onSaved).not.toHaveBeenCalled();
});

import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { ApiError, type ApiClient, type RequestOptions } from "../api/client";
import type { SessionResponse } from "../api/contracts";
import { SessionProvider } from "../session/SessionContext";
import { AdminEmployeesPage } from "./AdminEmployeesPage";

const session: SessionResponse = {
  user: { id: "admin", email: "admin@example.com", preferred_locale: "uk" },
  session: { id: "s", absolute_expires_at: "2030-01-01T00:00:00Z", mfa_verified: true },
  organization_access: [
    {
      organization_id: "org",
      membership_status: null,
      is_employee: false,
      is_organization_admin: true,
    },
  ],
  platform_operator: false,
  csrf_token: "test-csrf",
};
const invitation = {
  id: "invite",
  organization_id: "org",
  email: "invited@example.com",
  status: "expired",
  expires_at: "2026-09-12T00:00:00Z",
  created_at: "2026-09-09T00:00:00Z",
  updated_at: "2026-09-09T00:00:00Z",
};
function setup(handler?: (path: string, options?: RequestOptions) => unknown) {
  const requests: Array<{ path: string; options?: RequestOptions }> = [];
  const client: ApiClient = {
    getSession: () => Promise.resolve(session),
    request: async <T,>(path: string, options?: RequestOptions) => {
      requests.push({ path, options });
      if (path.includes("/invitations"))
        return (
          handler ? await handler(path, options) : { items: [invitation], next_cursor: null }
        ) as T;
      return (
        path.endsWith("/employees")
          ? { items: [], next_cursor: null }
          : { id: "org", name: "Bacara" }
      ) as T;
    },
  };
  render(
    <SessionProvider client={client}>
      <MemoryRouter>
        <AdminEmployeesPage />
      </MemoryRouter>
    </SessionProvider>,
  );
  return requests;
}

it("resends an expired invitation once with protected headers and queued feedback", async () => {
  let complete!: (value: unknown) => void;
  const pending = new Promise((resolve) => {
    complete = resolve;
  });
  const requests = setup((_path, options) =>
    options?.method === "POST" ? pending : { items: [invitation], next_cursor: null },
  );
  const user = userEvent.setup();
  const button = await screen.findByRole("button", {
    name: /Надіслати повторно.*invited@example.com/,
  });
  await user.dblClick(button);
  expect(button).toBeDisabled();
  const writes = requests.filter(({ options }) => options?.method === "POST");
  expect(writes).toHaveLength(1);
  expect(writes[0].path).toBe("/organizations/org/invitations/invite/resend");
  expect(writes[0].options).toMatchObject({
    csrfToken: "test-csrf",
  });
  expect(typeof writes[0].options?.idempotencyKey).toBe("string");
  await act(async () => {
    complete({ ...invitation, status: "pending" });
    await pending;
  });
  expect(await screen.findByText(/Лист поставлено в чергу/)).toBeVisible();
});

it("reuses the idempotency key after an uncertain network failure", async () => {
  let attempts = 0;
  const requests = setup((_path, options) => {
    if (options?.method !== "POST") return { items: [invitation], next_cursor: null };
    if (++attempts === 1) throw new ApiError(0, { code: "NETWORK_ERROR" });
    return { ...invitation, status: "pending" };
  });
  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("button", { name: /Надіслати повторно.*invited@example.com/ }),
  );
  expect(await screen.findByRole("alert")).toBeVisible();
  await user.click(screen.getByRole("button", { name: /Надіслати повторно.*invited@example.com/ }));
  await screen.findByText(/Лист поставлено в чергу/);
  const writes = requests.filter(({ options }) => options?.method === "POST");
  expect(writes[0].options?.idempotencyKey).toBe(writes[1].options?.idempotencyKey);
});

it("loads additional invitations and keeps terminal invitations non-actionable", async () => {
  setup((path) =>
    path.includes("cursor=")
      ? {
          items: [
            { ...invitation, id: "accepted", email: "accepted@example.com", status: "accepted" },
          ],
          next_cursor: null,
        }
      : { items: [invitation], next_cursor: "next-page" },
  );
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Ще запрошення" }));
  expect(await screen.findByText("accepted@example.com")).toBeVisible();
  expect(
    screen.queryByRole("button", { name: /Надіслати повторно.*accepted@example.com/ }),
  ).not.toBeInTheDocument();
  expect(screen.getByText("invited@example.com")).toBeVisible();
});

it("shows a recoverable read error without breaking the employee page", async () => {
  let fail = true;
  setup(() => {
    if (fail) throw new Error("offline");
    return { items: [], next_cursor: null };
  });
  const user = userEvent.setup();
  expect(await screen.findByText("Не вдалося завантажити запрошення.")).toBeVisible();
  fail = false;
  await user.click(screen.getByRole("button", { name: "Оновити запрошення" }));
  await waitFor(() => expect(screen.getByText("Запрошень ще немає.")).toBeVisible());
});

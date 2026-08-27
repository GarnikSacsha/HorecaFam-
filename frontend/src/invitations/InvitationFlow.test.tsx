import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import type { ApiClient, RequestOptions } from "../api/client";
import type { SessionResponse } from "../api/contracts";
import { SessionProvider } from "../session/SessionContext";
import { InvitationAcceptPage } from "./InvitationAcceptPage";

const pendingSession: SessionResponse = {
  user: { id: "user-1", email: "employee@example.com", preferred_locale: "uk" },
  session: { id: "session-1", absolute_expires_at: "2026-09-01T00:00:00Z", mfa_verified: false },
  organization_access: [
    {
      organization_id: "organization-1",
      membership_status: "pending",
      is_employee: true,
      is_organization_admin: false,
    },
  ],
  platform_operator: false,
  csrf_token: "csrf-safe",
};

describe("invitation acceptance", () => {
  it("validates and accepts the server-selected first-account path", async () => {
    const requests: Array<{ path: string; options?: RequestOptions }> = [];
    const client: ApiClient = {
      getSession: () =>
        Promise.reject(Object.assign(new Error("Unauthenticated"), { status: 401 })),
      request: <T,>(path: string, options?: RequestOptions) => {
        requests.push({ path, options });
        if (path === "/invitations/validate") {
          return Promise.resolve({
            status: "valid",
            organization_id: "organization-1",
            organization_name: "Bacara Kyiv",
            email_masked: "e***@example.com",
            acceptance_mode: "activate_access",
            expires_at: "2026-08-30T00:00:00Z",
          } as T);
        }
        return Promise.resolve({
          ...pendingSession,
          status: "accepted",
          acceptance_mode: "activate_access",
          membership: {
            id: "membership-1",
            organization_id: "organization-1",
            employee_profile_id: "employee-1",
            status: "pending",
          },
        } as T);
      },
    };
    const user = userEvent.setup();

    render(
      <SessionProvider client={client}>
        <MemoryRouter initialEntries={["/invite?token=invitation-safe"]}>
          <Routes>
            <Route path="/invite" element={<InvitationAcceptPage />} />
            <Route path="/" element={<p>Сесію створено</p>} />
          </Routes>
        </MemoryRouter>
      </SessionProvider>,
    );

    expect(await screen.findByText("Bacara Kyiv")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Створіть пароль"), "strong-password");
    await user.type(screen.getByLabelText("Повторіть пароль"), "strong-password");
    await user.click(screen.getByRole("button", { name: "Прийняти запрошення" }));

    expect(await screen.findByText("Сесію створено")).toBeInTheDocument();
    expect(requests.at(-1)).toEqual({
      path: "/invitations/accept",
      options: {
        method: "POST",
        body: {
          token: "invitation-safe",
          acceptance_mode: "activate_access",
          password: "strong-password",
        },
      },
    });
  });
});

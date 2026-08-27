import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import type { ApiClient } from "../api/client";
import type { OwnEmployeeProfilesResponse, SessionResponse } from "../api/contracts";
import { SessionProvider } from "../session/SessionContext";
import { PendingPage } from "./PendingPage";

const session: SessionResponse = {
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

describe("Pending Employee", () => {
  it("shows the server profile state without exposing self-activation", async () => {
    const profiles: OwnEmployeeProfilesResponse = {
      profiles: [
        {
          id: "employee-1",
          organization: { id: "organization-1", name: "Bacara Kyiv" },
          membership_status: "pending",
          first_name: null,
          last_name: null,
          operational_role: null,
          location: null,
          profile_complete: false,
          updated_at: "2026-08-27T00:00:00Z",
        },
      ],
    };
    const client: ApiClient = {
      getSession: () => Promise.resolve(session),
      request: <T,>() => Promise.resolve(profiles as T),
    };

    render(
      <SessionProvider client={client}>
        <MemoryRouter>
          <PendingPage />
        </MemoryRouter>
      </SessionProvider>,
    );

    expect(await screen.findByText("Bacara Kyiv")).toBeInTheDocument();
    expect(screen.getByText("Очікує налаштування адміністратором")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /активувати/i })).not.toBeInTheDocument();
  });
});

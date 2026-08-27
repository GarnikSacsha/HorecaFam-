import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import type { ApiClient } from "../api/client";
import type { OwnEmployeeProfilesResponse, SessionResponse } from "../api/contracts";
import { SessionProvider } from "../session/SessionContext";
import { HomeRedirect } from "../session/SessionGate";
import { ActiveHomePage } from "./ActiveHomePage";

const activeSession: SessionResponse = {
  user: { id: "user-1", email: "employee@example.com", preferred_locale: "uk" },
  session: { id: "session-1", absolute_expires_at: "2026-09-01T00:00:00Z", mfa_verified: false },
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

describe("Active Employee Home", () => {
  it("routes from the refreshed server session and renders a truthful zero-assignment state", async () => {
    const profiles: OwnEmployeeProfilesResponse = {
      profiles: [
        {
          id: "employee-1",
          organization: { id: "organization-1", name: "Bacara Kyiv" },
          membership_status: "active",
          first_name: "Анна",
          last_name: "Коваль",
          operational_role: {
            id: "role-1",
            organization_id: "organization-1",
            code: "waiter",
            name_uk: "Офіціант",
            status: "active",
          },
          location: {
            id: "location-1",
            organization_id: "organization-1",
            name: "Хрещатик",
            status: "active",
            address: null,
            timezone: "Europe/Kyiv",
          },
          profile_complete: true,
          updated_at: "2026-08-27T00:00:00Z",
        },
      ],
    };
    const client: ApiClient = {
      getSession: () => Promise.resolve(activeSession),
      request: <T,>() => Promise.resolve(profiles as T),
    };

    render(
      <SessionProvider client={client}>
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route path="/" element={<HomeRedirect />} />
            <Route path="/employee" element={<ActiveHomePage />} />
          </Routes>
        </MemoryRouter>
      </SessionProvider>,
    );

    expect(await screen.findByRole("heading", { name: "Вітаємо, Анна" })).toBeInTheDocument();
    expect(screen.getByText("Навчання ще не призначено")).toBeInTheDocument();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /іспит|практик/i })).not.toBeInTheDocument();
  });
});

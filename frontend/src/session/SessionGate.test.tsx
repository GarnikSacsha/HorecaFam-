import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import type { ApiClient } from "../api/client";
import type { SessionResponse } from "../api/contracts";
import { SessionProvider } from "./SessionContext";
import { HomeRedirect, ProtectedRoute } from "./SessionGate";

const adminSession: SessionResponse = {
  user: { id: "user-1", email: "admin@example.com", preferred_locale: "uk" },
  session: {
    id: "session-1",
    absolute_expires_at: "2026-09-01T00:00:00Z",
    mfa_verified: true,
  },
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

function clientWithSession(session: SessionResponse | null): ApiClient {
  return {
    request: vi.fn(),
    getSession: session
      ? vi.fn().mockResolvedValue(session)
      : vi.fn().mockRejectedValue({ status: 401 }),
  };
}

describe("session routing", () => {
  it("routes an MFA-verified Admin from the server session to Employees", async () => {
    render(
      <SessionProvider client={clientWithSession(adminSession)}>
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route path="/" element={<HomeRedirect />} />
            <Route path="/admin/employees" element={<p>Команда</p>} />
          </Routes>
        </MemoryRouter>
      </SessionProvider>,
    );

    expect(await screen.findByText("Команда")).toBeInTheDocument();
  });

  it("routes an unauthenticated visitor to login", async () => {
    render(
      <SessionProvider client={clientWithSession(null)}>
        <MemoryRouter initialEntries={["/employee"]}>
          <Routes>
            <Route path="/login" element={<p>Вхід</p>} />
            <Route
              path="/employee"
              element={
                <ProtectedRoute audience="active-employee">
                  <p>Головна</p>
                </ProtectedRoute>
              }
            />
          </Routes>
        </MemoryRouter>
      </SessionProvider>,
    );

    await waitFor(() => expect(screen.getByText("Вхід")).toBeInTheDocument());
  });
});

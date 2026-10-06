import { act, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ApiError, type ApiClient } from "../api/client";
import userEvent from "@testing-library/user-event";
import type { SessionResponse } from "../api/contracts";
import { SessionProvider, useSession } from "./SessionContext";
import { LoginPage } from "../auth/LoginPage";
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

const operatorSession: SessionResponse = {
  ...adminSession,
  organization_access: [],
  platform_operator: true,
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
  it("does not invalidate a new login when an old request returns 401", async () => {
    let rejectRequest!: (reason: unknown) => void;
    const pending = new Promise<never>((_resolve, reject) => {
      rejectRequest = reject;
    });
    const client = clientWithSession(adminSession);
    client.request = vi.fn().mockReturnValue(pending);
    function Probe() {
      const { client: scoped, session, setSession } = useSession();
      return (
        <>
          <p>{session?.session.id}</p>
          <button onClick={() => void scoped.request("/protected").catch(() => undefined)}>
            Load
          </button>
          <button
            onClick={() =>
              setSession({
                ...adminSession,
                session: { ...adminSession.session, id: "new-session" },
              })
            }
          >
            New login
          </button>
        </>
      );
    }
    render(
      <SessionProvider client={client}>
        <Probe />
      </SessionProvider>,
    );
    await screen.findByText("session-1");
    await userEvent.click(screen.getByRole("button", { name: "Load" }));
    await userEvent.click(screen.getByRole("button", { name: "New login" }));
    await act(async () => {
      rejectRequest(new ApiError(401));
      await pending.catch(() => undefined);
    });
    expect(screen.getByText("new-session")).toBeInTheDocument();
  });
  it.each([401, 403, 0])(
    "handles a protected request failure %s without confusing it with network loss",
    async (status) => {
      function Probe() {
        const { client } = useSession();
        return (
          <button
            onClick={() =>
              void client.request("/organizations/organization-1/employees").catch(() => undefined)
            }
          >
            Load protected data
          </button>
        );
      }
      const client = clientWithSession(adminSession);
      client.request = vi.fn().mockRejectedValue(new ApiError(status));
      render(
        <SessionProvider client={client}>
          <MemoryRouter initialEntries={["/protected"]}>
            <Routes>
              <Route
                path="/protected"
                element={
                  <ProtectedRoute audience="admin">
                    <Probe />
                  </ProtectedRoute>
                }
              />
              <Route path="/login" element={<LoginPage />} />
            </Routes>
          </MemoryRouter>
        </SessionProvider>,
      );
      await userEvent.click(await screen.findByRole("button", { name: "Load protected data" }));
      if (status === 401) {
        expect(
          await screen.findByRole("heading", { name: "Увійдіть до свого простору" }),
        ).toBeInTheDocument();
        expect(screen.getByRole("status")).toHaveTextContent("Сесію завершено або відкликано");
      } else {
        expect(screen.getByRole("button", { name: "Load protected data" })).toBeInTheDocument();
      }
    },
  );
  it("routes an MFA-verified Admin from the server session to Dashboard", async () => {
    render(
      <SessionProvider client={clientWithSession(adminSession)}>
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route path="/" element={<HomeRedirect />} />
            <Route path="/admin/dashboard" element={<p>Команда</p>} />
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

  it("routes an MFA-verified Platform Operator to Jobs", async () => {
    render(
      <SessionProvider client={clientWithSession(operatorSession)}>
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route path="/" element={<HomeRedirect />} />
            <Route path="/operator/jobs" element={<p>Operator Jobs</p>} />
          </Routes>
        </MemoryRouter>
      </SessionProvider>,
    );

    expect(await screen.findByText("Operator Jobs")).toBeInTheDocument();
  });
});

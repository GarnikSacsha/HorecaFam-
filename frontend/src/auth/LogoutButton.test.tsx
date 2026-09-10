import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import type { ApiClient } from "../api/client";
import { SessionProvider, useSession } from "../session/SessionContext";
import { LogoutButton } from "./LogoutButton";

function SessionProbe() {
  const { status } = useSession();
  return <p>{status}</p>;
}

function setup(request: ApiClient["request"]) {
  const client: ApiClient = {
    request,
    getSession: vi.fn().mockResolvedValue({
      user: { id: "user-1", email: "employee@example.com", preferred_locale: "uk" },
      session: {
        id: "session-1",
        absolute_expires_at: "2031-01-01T00:00:00Z",
        mfa_verified: false,
      },
      organization_access: [],
      platform_operator: false,
      csrf_token: "test-csrf",
    }),
  };
  render(
    <MemoryRouter>
      <SessionProvider client={client}>
        <LogoutButton />
        <SessionProbe />
      </SessionProvider>
    </MemoryRouter>,
  );
}

it("revokes other devices with CSRF while retaining the current session", async () => {
  const request = vi.fn().mockResolvedValue(undefined);
  setup(request);
  await screen.findByText("authenticated");
  await userEvent.click(screen.getByRole("button", { name: "Вийти з інших пристроїв" }));
  expect(request).toHaveBeenCalledWith("/auth/logout-all", {
    method: "POST",
    csrfToken: "test-csrf",
  });
  expect(await screen.findByRole("status")).toHaveTextContent(
    "На інших пристроях виконано вихід. Поточний сеанс збережено.",
  );
  expect(screen.getByText("authenticated")).toBeInTheDocument();
});

it("blocks duplicate actions and permits retry after a safe error", async () => {
  let rejectRequest: (error: Error) => void = () => {};
  const request = vi
    .fn()
    .mockImplementationOnce(
      () =>
        new Promise((_resolve, reject) => {
          rejectRequest = reject;
        }),
    )
    .mockResolvedValue(undefined);
  setup(request);
  await screen.findByText("authenticated");
  await userEvent.click(screen.getByRole("button", { name: "Вийти з інших пристроїв" }));
  expect(screen.getByRole("button", { name: "Вийти" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Завершуємо сеанси…" })).toBeDisabled();
  rejectRequest(new Error("private failure"));
  expect(await screen.findByRole("alert")).toHaveTextContent("Не вдалося завершити інші сеанси.");
  expect(screen.queryByText("private failure")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Вийти з інших пристроїв" }));
  await waitFor(() => expect(request).toHaveBeenCalledTimes(2));
  expect(await screen.findByRole("status")).toBeInTheDocument();
  expect(screen.getByText("authenticated")).toBeInTheDocument();
});

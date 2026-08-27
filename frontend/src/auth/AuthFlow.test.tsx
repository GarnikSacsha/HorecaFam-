import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import type { ApiClient, RequestOptions } from "../api/client";
import { SessionProvider } from "../session/SessionContext";
import { LoginPage } from "./LoginPage";

interface CapturedRequest {
  path: string;
  options?: RequestOptions;
}

describe("authentication flow", () => {
  it("continues an Admin login through the server-driven MFA challenge", async () => {
    const requests: CapturedRequest[] = [];
    const client: ApiClient = {
      getSession: () =>
        Promise.reject(Object.assign(new Error("Unauthenticated"), { status: 401 })),
      request: <T,>(path: string, options?: RequestOptions) => {
        requests.push({ path, options });
        return Promise.resolve({
          status: "mfa_required",
          expires_at: "2026-08-27T20:00:00Z",
        } as T);
      },
    };
    const user = userEvent.setup();

    render(
      <SessionProvider client={client}>
        <MemoryRouter initialEntries={["/login"]}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/mfa" element={<p>Підтвердження входу</p>} />
          </Routes>
        </MemoryRouter>
      </SessionProvider>,
    );

    await user.type(screen.getByLabelText("Робоча електронна пошта"), "admin@example.com");
    await user.type(screen.getByLabelText("Пароль"), "correct horse battery staple");
    await user.click(screen.getByRole("button", { name: "Увійти" }));

    expect(await screen.findByText("Підтвердження входу")).toBeInTheDocument();
    expect(requests).toEqual([
      {
        path: "/auth/login",
        options: {
          method: "POST",
          body: { email: "admin@example.com", password: "correct horse battery staple" },
        },
      },
    ]);
  });
});

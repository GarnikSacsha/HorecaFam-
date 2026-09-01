import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import type { ApiClient, RequestOptions } from "../api/client";
import type { SessionResponse } from "../api/contracts";
import { SessionProvider } from "../session/SessionContext";
import { ForgotPasswordPage } from "./ForgotPasswordPage";
import { MfaEnrollmentPage } from "./MfaEnrollmentPage";
import { MfaRecoveryPage } from "./MfaRecoveryPage";
import { ResetPasswordPage } from "./ResetPasswordPage";

interface CapturedRequest {
  path: string;
  options?: RequestOptions;
}

const authenticatedSession: SessionResponse = {
  user: { id: "user-1", email: "admin@example.com", preferred_locale: "uk" },
  session: {
    id: "session-1",
    absolute_expires_at: "2031-01-01T00:00:00Z",
    mfa_verified: true,
  },
  organization_access: [],
  platform_operator: false,
  csrf_token: "csrf-safe",
};

function anonymousSession() {
  return Promise.reject(Object.assign(new Error("Unauthenticated"), { status: 401 }));
}

describe("security recovery flow", () => {
  it("shows the same accepted state after requesting a password reset", async () => {
    const requests: CapturedRequest[] = [];
    const client: ApiClient = {
      getSession: anonymousSession,
      request: <T,>(path: string, options?: RequestOptions) => {
        requests.push({ path, options });
        return Promise.resolve({ status: "accepted" } as T);
      },
    };
    const user = userEvent.setup();

    render(
      <SessionProvider client={client}>
        <MemoryRouter>
          <ForgotPasswordPage />
        </MemoryRouter>
      </SessionProvider>,
    );

    await user.type(screen.getByLabelText("Робоча електронна пошта"), "user@example.com");
    await user.click(screen.getByRole("button", { name: "Надіслати інструкцію" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Якщо адреса зареєстрована");
    expect(requests).toEqual([
      {
        path: "/auth/password/forgot",
        options: { method: "POST", body: { email: "user@example.com" } },
      },
    ]);
  });

  it("keeps the reset token in the URL and clears password fields after one use", async () => {
    const requests: CapturedRequest[] = [];
    const client: ApiClient = {
      getSession: anonymousSession,
      request: <T,>(path: string, options?: RequestOptions) => {
        requests.push({ path, options });
        return Promise.resolve(undefined as T);
      },
    };
    const user = userEvent.setup();

    render(
      <SessionProvider client={client}>
        <MemoryRouter initialEntries={["/reset-password?token=reset-token-that-is-long-enough"]}>
          <ResetPasswordPage />
        </MemoryRouter>
      </SessionProvider>,
    );

    await user.type(screen.getByLabelText("Новий пароль"), "correct horse battery staple");
    await user.type(
      screen.getByLabelText("Повторіть новий пароль"),
      "correct horse battery staple",
    );
    await user.click(screen.getByRole("button", { name: "Змінити пароль" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Пароль змінено");
    expect(requests).toEqual([
      {
        path: "/auth/password/reset",
        options: {
          method: "POST",
          body: {
            token: "reset-token-that-is-long-enough",
            new_password: "correct horse battery staple",
          },
        },
      },
    ]);
    expect(screen.queryByDisplayValue("correct horse battery staple")).not.toBeInTheDocument();
  });

  it("does not call the API when the reset link has no token", () => {
    const client: ApiClient = {
      getSession: () => new Promise(() => undefined),
      request: () => Promise.reject(new Error("must not be called")),
    };

    render(
      <SessionProvider client={client}>
        <MemoryRouter initialEntries={["/reset-password"]}>
          <ResetPasswordPage />
        </MemoryRouter>
      </SessionProvider>,
    );

    expect(screen.getByRole("heading", { name: "Запросіть нове посилання" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Запросити нове посилання" })).toHaveAttribute(
      "href",
      "/forgot-password",
    );
  });

  it("offers a fresh login when the MFA enrollment challenge is expired", async () => {
    const client: ApiClient = {
      getSession: anonymousSession,
      request: () => Promise.reject(new Error("expired challenge")),
    };

    render(
      <SessionProvider client={client}>
        <MemoryRouter>
          <MfaEnrollmentPage />
        </MemoryRouter>
      </SessionProvider>,
    );

    expect(await screen.findByRole("heading", { name: "Почніть вхід ще раз" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Повернутися до входу" })).toHaveAttribute(
      "href",
      "/login",
    );
  });

  it("shows generated recovery codes once before activating the enrolled session", async () => {
    const requests: CapturedRequest[] = [];
    const client: ApiClient = {
      getSession: anonymousSession,
      request: <T,>(path: string, options?: RequestOptions) => {
        requests.push({ path, options });
        if (path.endsWith("/start")) {
          return Promise.resolve({
            secret: "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567",
            otpauth_uri: "otpauth://totp/Bacara:test",
            expires_at: "2031-01-01T00:05:00Z",
          } as T);
        }
        return Promise.resolve({
          session: authenticatedSession,
          recovery_codes: ["ABCD-EFGH-IJKL-MNOP", "QRST-UVWX-YZ23-4567"],
        } as T);
      },
    };
    const user = userEvent.setup();

    render(
      <SessionProvider client={client}>
        <MemoryRouter initialEntries={["/mfa/enroll"]}>
          <Routes>
            <Route path="/mfa/enroll" element={<MfaEnrollmentPage />} />
            <Route path="/" element={<p>Authenticated home</p>} />
          </Routes>
        </MemoryRouter>
      </SessionProvider>,
    );

    expect(await screen.findByText("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Код підтвердження"), "123456");
    await user.click(screen.getByRole("button", { name: "Підтвердити й отримати резервні коди" }));

    expect(await screen.findByText("ABCD-EFGH-IJKL-MNOP")).toBeInTheDocument();
    expect(screen.queryByText("Authenticated home")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Я зберіг коди" }));
    expect(await screen.findByText("Authenticated home")).toBeInTheDocument();
    expect(screen.queryByText("ABCD-EFGH-IJKL-MNOP")).not.toBeInTheDocument();
    expect(requests).toEqual([
      { path: "/auth/mfa/enrollment/start", options: { method: "POST" } },
      {
        path: "/auth/mfa/enrollment/confirm",
        options: { method: "POST", body: { code: "123456" } },
      },
    ]);
  });

  it("normalizes a pasted recovery code and completes its one-time login", async () => {
    const requests: CapturedRequest[] = [];
    const client: ApiClient = {
      getSession: anonymousSession,
      request: <T,>(path: string, options?: RequestOptions) => {
        requests.push({ path, options });
        return Promise.resolve(authenticatedSession as T);
      },
    };
    const user = userEvent.setup();

    render(
      <SessionProvider client={client}>
        <MemoryRouter initialEntries={["/mfa/recovery"]}>
          <Routes>
            <Route path="/mfa/recovery" element={<MfaRecoveryPage />} />
            <Route path="/" element={<p>Authenticated home</p>} />
          </Routes>
        </MemoryRouter>
      </SessionProvider>,
    );

    await user.type(screen.getByLabelText("Резервний код"), "abcd efgh ijkl mnop");
    await user.click(screen.getByRole("button", { name: "Увійти з резервним кодом" }));

    expect(await screen.findByText("Authenticated home")).toBeInTheDocument();
    expect(requests).toEqual([
      {
        path: "/auth/mfa/recovery/verify",
        options: { method: "POST", body: { code: "ABCDEFGHIJKLMNOP" } },
      },
    ]);
  });
});

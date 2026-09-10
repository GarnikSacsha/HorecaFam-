import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { apiClient } from "../api/client";
import type { OwnEmployeeProfile, SessionResponse } from "../api/contracts";
import { App } from "../app/App";

const session: SessionResponse = {
  user: { id: "user-1", email: "employee@example.com", preferred_locale: "uk" },
  session: { id: "session-1", absolute_expires_at: "2031-01-01T00:00:00Z", mfa_verified: false },
  organization_access: [
    {
      organization_id: "org-1",
      membership_status: "active",
      is_employee: true,
      is_organization_admin: false,
    },
  ],
  platform_operator: false,
  csrf_token: "test-csrf",
};
const profile: OwnEmployeeProfile = {
  id: "employee-1",
  organization: { id: "org-1", name: "Bacara" },
  membership_status: "active",
  first_name: "Анна",
  last_name: "Коваль",
  operational_role: {
    id: "role-1",
    organization_id: "org-1",
    code: "waiter",
    name_uk: "Офіціант",
    status: "active",
  },
  location: {
    id: "location-1",
    organization_id: "org-1",
    name: "Центр",
    status: "active",
    address: null,
    timezone: "Europe/Kyiv",
  },
  profile_complete: true,
  updated_at: "2026-09-09T00:00:00Z",
};

beforeEach(() => {
  window.history.replaceState(null, "", "/employee/profile");
  vi.spyOn(apiClient, "getSession").mockResolvedValue(session);
});
afterEach(() => vi.restoreAllMocks());

it("opens the protected profile and selects the active session organization", async () => {
  vi.spyOn(apiClient, "request").mockResolvedValue({
    profiles: [
      { ...profile, organization: { id: "other", name: "Інше місце" }, first_name: "Інша" },
      profile,
    ],
  });
  render(<App />);
  expect(await screen.findByText("Анна Коваль")).toBeInTheDocument();
  expect(screen.getByText("Центр")).toBeInTheDocument();
  expect(screen.getByText("Офіціант")).toBeInTheDocument();
  expect(screen.getByText("Активний")).toBeInTheDocument();
  expect(screen.queryByText("Інше місце")).not.toBeInTheDocument();
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Профіль" })).toHaveAttribute("aria-current", "page");
});

it("keeps logout available while the profile is loading", async () => {
  vi.spyOn(apiClient, "request").mockImplementation(() => new Promise(() => {}));
  render(<App />);
  expect(await screen.findByText("Завантажуємо профіль…")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Вийти" })).toBeEnabled();
});

it("retries a failed read without exposing the raw error", async () => {
  const request = vi
    .spyOn(apiClient, "request")
    .mockRejectedValueOnce(new Error("private diagnostic"))
    .mockResolvedValue({ profiles: [profile] });
  render(<App />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Не вдалося завантажити профіль.");
  expect(screen.queryByText("private diagnostic")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Повторити" }));
  expect(await screen.findByText("Анна Коваль")).toBeInTheDocument();
  expect(request).toHaveBeenCalledTimes(2);
});

it("shows an explicit missing-profile state", async () => {
  vi.spyOn(apiClient, "request").mockResolvedValue({ profiles: [] });
  render(<App />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Активний профіль працівника не знайдено.",
  );
  expect(screen.getByRole("button", { name: "Вийти" })).toBeEnabled();
});

it("does not invent missing profile fields", async () => {
  vi.spyOn(apiClient, "request").mockResolvedValue({
    profiles: [
      { ...profile, first_name: null, last_name: null, operational_role: null, location: null },
    ],
  });
  render(<App />);
  expect(await screen.findByText("Ім’я не вказано")).toBeInTheDocument();
  expect(screen.getAllByText("Не вказано")).toHaveLength(2);
});

it("uses current-session logout with CSRF and retains retry after failure", async () => {
  let logoutCalls = 0;
  const request = vi.spyOn(apiClient, "request").mockImplementation((path) => {
    if (path === "/auth/logout") {
      if (++logoutCalls === 1) return Promise.reject(new Error("unavailable"));
      return Promise.resolve(undefined);
    }
    return Promise.resolve({ profiles: [profile] });
  });
  render(<App />);
  await screen.findByText("Анна Коваль");
  await userEvent.click(screen.getByRole("button", { name: "Вийти" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Не вдалося вийти.");
  await userEvent.click(screen.getByRole("button", { name: "Вийти" }));
  await waitFor(() => expect(window.location.pathname).toBe("/login"));
  expect(request).toHaveBeenCalledWith("/auth/logout", { method: "POST", csrfToken: "test-csrf" });
});

it("redirects anonymous entry without loading profile data", async () => {
  vi.spyOn(apiClient, "getSession").mockRejectedValue({ status: 401 });
  const request = vi.spyOn(apiClient, "request");
  render(<App />);
  await waitFor(() => expect(window.location.pathname).toBe("/login"));
  expect(request).not.toHaveBeenCalled();
});

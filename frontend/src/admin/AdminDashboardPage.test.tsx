import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { apiClient } from "../api/client";
import { App } from "../app/App";

const summary = {
  organization_id: "org-1",
  location_id: null,
  employees: { total: 8, active: 6, pending: 1, paused: 2, disabled: 1 },
  training: { assigned: 3, in_progress: 2, completed: 4 },
  final_exam: { certified: 3, needs_exam: 2, retake: 1, overdue_retake: 1 },
  attention: { unresolved: 2, critical: 1 },
};
const locations = [
  {
    id: "location-1",
    organization_id: "org-1",
    name: "Центр",
    status: "active",
    address: null,
    timezone: "Europe/Kyiv",
  },
];

beforeEach(() => {
  window.history.replaceState(null, "", "/admin/dashboard");
  vi.spyOn(apiClient, "getSession").mockResolvedValue({
    user: { id: "user-1", email: "admin@example.com", preferred_locale: "uk" },
    session: { id: "session-1", absolute_expires_at: "2031-01-01T00:00:00Z", mfa_verified: true },
    organization_access: [
      {
        organization_id: "org-1",
        membership_status: null,
        is_employee: false,
        is_organization_admin: true,
      },
    ],
    platform_operator: false,
    csrf_token: "csrf",
  });
});
afterEach(() => vi.restoreAllMocks());

it("loads the organization overview and filters the read by location", async () => {
  const request = vi
    .spyOn(apiClient, "request")
    .mockImplementation((path) =>
      Promise.resolve(path.endsWith("/locations") ? locations : summary),
    );
  render(<App />);
  expect(await screen.findByRole("heading", { name: "Огляд команди" })).toBeInTheDocument();
  expect(await screen.findByRole("region", { name: "Працівники" })).toBeInTheDocument();
  expect(
    within(screen.getByRole("region", { name: "Працівники" })).getByText("8"),
  ).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByLabelText("Локація"), "location-1");
  await waitFor(() =>
    expect(request).toHaveBeenCalledWith("/organizations/org-1/dashboard?location_id=location-1"),
  );
  expect(screen.getByRole("link", { name: "Відкрити результати" })).toHaveAttribute(
    "href",
    "/admin/results",
  );
  expect(screen.getByRole("link", { name: "Відкрити Attention" })).toHaveAttribute(
    "href",
    "/admin/attention",
  );
});

it("retries an API failure without showing fake zero counts", async () => {
  let available = false;
  vi.spyOn(apiClient, "request").mockImplementation((path) => {
    if (path.endsWith("/locations")) return Promise.resolve(locations);
    return available ? Promise.resolve(summary) : Promise.reject(new Error("private diagnostic"));
  });
  render(<App />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Не вдалося завантажити огляд.");
  expect(screen.queryByText("private diagnostic")).not.toBeInTheDocument();
  expect(screen.queryByText("Працівників ще немає")).not.toBeInTheDocument();
  available = true;
  await userEvent.click(screen.getByRole("button", { name: "Повторити" }));
  expect(await screen.findByRole("region", { name: "Працівники" })).toBeInTheDocument();
});

it("shows the empty team next step", async () => {
  vi.spyOn(apiClient, "request").mockImplementation((path) =>
    Promise.resolve(
      path.endsWith("/locations")
        ? []
        : { ...summary, employees: { total: 0, active: 0, pending: 0, paused: 0, disabled: 0 } },
    ),
  );
  render(<App />);
  expect(await screen.findByText("Працівників ще немає")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Відкрити працівників" })).toHaveAttribute(
    "href",
    "/admin/employees",
  );
});

it("announces loading without showing stale counts", async () => {
  vi.spyOn(apiClient, "request").mockImplementation(() => new Promise(() => {}));
  render(<App />);
  expect(await screen.findByRole("status")).toHaveTextContent("Завантажуємо огляд…");
  expect(screen.getByLabelText("Локація")).toBeDisabled();
  expect(screen.queryByRole("region", { name: "Працівники" })).not.toBeInTheDocument();
});

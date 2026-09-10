import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { apiClient } from "../api/client";
import { App } from "./App";

describe("App", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the public story before the session request completes", () => {
    vi.spyOn(apiClient, "getSession").mockImplementation(() => new Promise(() => {}));
    render(<App />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Гостинність починається з тебе",
    );
    expect(screen.getByRole("main")).toHaveAccessibleName("Bacara Coffee — HoReCaFam");
  });

  it.each([401, 503])("keeps the public story readable after session HTTP %s", async (status) => {
    const getSession = vi.spyOn(apiClient, "getSession").mockRejectedValue({ status });
    render(<App />);
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent(
      "Гостинність починається з тебе",
    );
    await waitFor(() => expect(getSession).toHaveBeenCalled());
    expect(screen.queryByText("Не вдалося перевірити сесію")).not.toBeInTheDocument();
    expect(window.location.pathname).toBe("/");
  });

  it("exposes real section anchors and leads to the existing login", async () => {
    vi.spyOn(apiClient, "getSession").mockRejectedValue({ status: 401 });
    const user = userEvent.setup();
    render(<App />);
    const navigation = within(
      screen.getByRole("navigation", { name: "Навігація головної сторінки" }),
    );
    for (const [name, id] of [
      ["Ресурси", "resources"],
      ["Для кого", "for-whom"],
    ]) {
      expect(navigation.getByRole("link", { name })).toHaveAttribute("href", `#${id}`);
      expect(document.getElementById(id)).not.toBeNull();
    }
    expect(screen.getByRole("link", { name: "Увійти до платформи" })).toHaveAttribute(
      "href",
      "/login",
    );
    expect(screen.queryByText("Про нас")).not.toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: /^Увійти$/ }));
    expect(await screen.findByLabelText("Робоча електронна пошта")).toBeInTheDocument();
    expect(window.location.pathname).toBe("/login");
  });

  it("keeps authenticated Admin entry directed to the existing workspace", async () => {
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
      csrf_token: "test-csrf",
    });
    vi.spyOn(apiClient, "request").mockRejectedValue({ status: 503 });
    render(<App />);
    await waitFor(() => expect(window.location.pathname).toBe("/admin/dashboard"));
    expect(screen.queryByText("Гостинність починається з тебе")).not.toBeInTheDocument();
  });
});

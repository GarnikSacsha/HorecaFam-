import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { AdminShell } from "./AdminShell";
import { EmployeeShell } from "./EmployeeShell";
import { OperatorShell } from "../operator/OperatorShell";
import type { ApiClient } from "../api/client";
import type { SessionResponse } from "../api/contracts";
import { SessionProvider } from "../session/SessionContext";

const operatorAdminSession: SessionResponse = {
  user: { id: "user-1", email: "owner@example.com", preferred_locale: "uk" },
  session: { id: "session-1", absolute_expires_at: "2026-12-01T00:00:00Z", mfa_verified: true },
  organization_access: [
    {
      organization_id: "organization-1",
      membership_status: null,
      is_employee: false,
      is_organization_admin: true,
    },
  ],
  platform_operator: true,
  csrf_token: "csrf-safe",
};

function clientWith(session: SessionResponse): ApiClient {
  return { request: vi.fn(), getSession: vi.fn().mockResolvedValue(session) };
}

vi.mock("../auth/LogoutButton", () => ({
  LogoutButton: () => <button type="button">Вийти</button>,
}));

describe("application shells", () => {
  it("opens and closes the accessible Admin navigation drawer", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <AdminShell>
          <p>Працівники</p>
        </AdminShell>
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Банк питань" })).toHaveAttribute(
      "href",
      "/admin/questions",
    );
    expect(screen.getByRole("link", { name: "Результати" })).toHaveAttribute(
      "href",
      "/admin/results",
    );
    expect(screen.getByRole("link", { name: "Історія змін" })).toHaveAttribute(
      "href",
      "/admin/audit",
    );

    const trigger = screen.getByRole("button", { name: "Відкрити навігацію" });
    await user.click(trigger);
    expect(screen.getByRole("dialog", { name: "Навігація адміністратора" })).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("exposes only the approved read-only Operator destinations", () => {
    render(
      <MemoryRouter>
        <OperatorShell>
          <p>Operations</p>
        </OperatorShell>
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Jobs" })).toHaveAttribute("href", "/operator/jobs");
    expect(screen.getByRole("link", { name: "Системний аудит" })).toHaveAttribute(
      "href",
      "/operator/audit",
    );
    expect(
      screen.queryByRole("link", { name: /налаштування|користувачі/i }),
    ).not.toBeInTheDocument();
  });

  it("shows all five Employee destinations including the read-only Profile", () => {
    render(
      <MemoryRouter>
        <EmployeeShell>
          <p>Головна сторінка</p>
        </EmployeeShell>
      </MemoryRouter>,
    );

    expect(screen.getByRole("navigation", { name: "Основна навігація" })).toHaveTextContent(
      "ГоловнаНавчанняМенюПрактикаПрофіль",
    );
    expect(screen.getByRole("link", { name: "Меню" })).toHaveAttribute("href", "/employee/menu");
    expect(screen.getByRole("link", { name: "Академія" })).toHaveAttribute(
      "href",
      "/employee/academy",
    );
    expect(screen.getByRole("link", { name: "Профіль" })).toHaveAttribute(
      "href",
      "/employee/profile",
    );
    expect(screen.getByRole("link", { name: "Навчання" })).toHaveAttribute(
      "href",
      "/employee/learning",
    );
    expect(screen.getByRole("link", { name: "Практика" })).toHaveAttribute(
      "href",
      "/employee/practice",
    );
  });

  it("links an operator-admin between the Admin workspace and the Operator console", async () => {
    render(
      <SessionProvider client={clientWith(operatorAdminSession)}>
        <MemoryRouter>
          <AdminShell>
            <p>Огляд</p>
          </AdminShell>
          <OperatorShell>
            <p>Operations</p>
          </OperatorShell>
        </MemoryRouter>
      </SessionProvider>,
    );

    expect(await screen.findByRole("link", { name: "Платформа (оператор)" })).toHaveAttribute(
      "href",
      "/operator/jobs",
    );
    expect(screen.getByRole("link", { name: "← До адміністрування" })).toHaveAttribute(
      "href",
      "/admin/dashboard",
    );
  });

  it("does not show the Operator link to a regular Admin", () => {
    render(
      <MemoryRouter>
        <AdminShell>
          <p>Огляд</p>
        </AdminShell>
      </MemoryRouter>,
    );

    expect(screen.queryByRole("link", { name: "Платформа (оператор)" })).not.toBeInTheDocument();
  });
});

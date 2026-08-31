import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { AdminShell } from "./AdminShell";
import { EmployeeShell } from "./EmployeeShell";

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

    const trigger = screen.getByRole("button", { name: "Відкрити навігацію" });
    await user.click(trigger);
    expect(screen.getByRole("dialog", { name: "Навігація адміністратора" })).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("shows the approved four Employee destinations with Learning and Practice enabled", () => {
    render(
      <MemoryRouter>
        <EmployeeShell>
          <p>Головна сторінка</p>
        </EmployeeShell>
      </MemoryRouter>,
    );

    expect(screen.getByRole("navigation", { name: "Основна навігація" })).toHaveTextContent(
      "ГоловнаНавчанняПрактикаПрофіль",
    );
    expect(screen.queryByRole("link", { name: "Меню" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Навчання" })).toHaveAttribute(
      "href",
      "/employee/learning",
    );
    expect(screen.getByRole("link", { name: "Практика" })).toHaveAttribute(
      "href",
      "/employee/practice",
    );
  });
});

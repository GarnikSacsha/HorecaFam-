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

    const trigger = screen.getByRole("button", { name: "Відкрити навігацію" });
    await user.click(trigger);
    expect(screen.getByRole("dialog", { name: "Навігація адміністратора" })).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("shows the four approved Employee destinations", () => {
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
  });
});

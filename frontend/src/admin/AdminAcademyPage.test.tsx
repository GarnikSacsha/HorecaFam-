import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ApiClient } from "../api/client";
import type { SessionResponse } from "../api/contracts";
import { SessionProvider } from "../session/SessionContext";
import { AdminAcademyPage } from "./AdminAcademyPage";

const session: SessionResponse = {
  user: { id: "u", email: "admin@example.com", preferred_locale: "uk" },
  session: { id: "s", absolute_expires_at: "2030-01-01T00:00:00Z", mfa_verified: true },
  organization_access: [
    {
      organization_id: "o",
      membership_status: null,
      is_employee: false,
      is_organization_admin: true,
    },
  ],
  platform_operator: false,
  csrf_token: "test-csrf",
};
function show() {
  const request = vi.fn().mockImplementation((path: string, options?: { method?: string }) => {
    if (path.endsWith("/locations"))
      return Promise.resolve([{ id: "l", name: "Зал", status: "active" }]);
    if (path.endsWith("/operational-roles"))
      return Promise.resolve(
        ["waiter", "runner", "bartender"].map((id) => ({ id, name_uk: id, status: "active" })),
      );
    if (options?.method === "POST") return Promise.resolve({ created_count: 13 });
    return Promise.resolve({ items: [], next_offset: null });
  });
  const client: ApiClient = { getSession: vi.fn().mockResolvedValue(session), request };
  render(
    <SessionProvider client={client}>
      <AdminAcademyPage />
    </SessionProvider>,
  );
  return request;
}
it("creates a reviewed role-scoped draft with CSRF and idempotency", async () => {
  const request = show();
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Нова стаття" }));
  await user.type(screen.getByLabelText("Назва"), "Порада");
  await user.type(screen.getByLabelText("Адреса статті (slug)"), "tip");
  await user.type(screen.getByLabelText("Короткий опис"), "Опис");
  await user.type(screen.getByLabelText("Текст статті"), "Підтверджуйте передачу.");
  await user.click(screen.getByLabelText("Усі посади, включно з майбутніми"));
  expect(screen.getByRole("button", { name: "Зберегти статтю" })).toBeDisabled();
  await user.click(screen.getByLabelText("runner"));
  await user.click(screen.getByRole("button", { name: "Зберегти статтю" }));
  await waitFor(() =>
    expect(request).toHaveBeenCalledWith(
      "/organizations/o/locations/l/academy",
      expect.objectContaining({
        method: "POST",
        csrfToken: "test-csrf",
        idempotencyKey: expect.any(String) as unknown,
        body: expect.objectContaining({
          all_positions: false,
          operational_role_ids: ["runner"],
          status: "draft",
          slug: "tip",
        }) as unknown,
      }),
    ),
  );
});
it("requires distinct mapped positions before adding starter drafts", async () => {
  const request = show();
  const user = userEvent.setup();
  await screen.findByRole("button", { name: "Нова стаття" });
  await user.click(screen.getByText("13 стартових статей", { selector: "summary" }));
  const add = screen.getByRole("button", { name: "Додати 13 чернеток" });
  expect(add).toBeDisabled();
  await user.selectOptions(screen.getByLabelText("Офіціант"), "waiter");
  await user.selectOptions(screen.getByLabelText("Runner"), "runner");
  await user.selectOptions(screen.getByLabelText("Bartender"), "bartender");
  await user.click(add);
  expect(await screen.findByText(/Додано чернеток: 13/)).toBeInTheDocument();
  expect(request).toHaveBeenCalledWith(
    "/organizations/o/locations/l/academy/seed",
    expect.objectContaining({ method: "POST", csrfToken: "test-csrf" }),
  );
});

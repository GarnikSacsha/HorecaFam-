import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ApiClient } from "../api/client";
import type { AcademyArticle, SessionResponse } from "../api/contracts";
import { SessionProvider } from "../session/SessionContext";
import { EmployeeAcademyPage } from "./EmployeeAcademyPage";

const session: SessionResponse = {
  user: { id: "u", email: "reader@example.com", preferred_locale: "uk" },
  session: { id: "s", absolute_expires_at: "2030-01-01T00:00:00Z", mfa_verified: false },
  organization_access: [
    {
      organization_id: "o",
      membership_status: "active",
      is_employee: true,
      is_organization_admin: false,
    },
  ],
  platform_operator: false,
  csrf_token: "test-csrf",
};
export const article: AcademyArticle = {
  id: "a",
  slug: "welcome",
  title_uk: "Зустріч гостя",
  summary_uk: "Почніть із уваги",
  body_uk: "Привітайте гостя.\n\nУточніть потребу.",
  category: "service",
  status: "published",
  position: 0,
  revision: 1,
  all_positions: true,
  operational_role_ids: [],
  cover_asset_id: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
};
function show(request: ApiClient["request"], path = "/employee/academy") {
  const client: ApiClient = { getSession: vi.fn().mockResolvedValue(session), request };
  render(
    <MemoryRouter initialEntries={[path]}>
      <SessionProvider client={client}>
        <Routes>
          <Route path="/employee/academy" element={<EmployeeAcademyPage />} />
          <Route path="/employee/academy/:slug" element={<EmployeeAcademyPage />} />
        </Routes>
      </SessionProvider>
    </MemoryRouter>,
  );
}
it("opens optional articles without writing completion and renders plain text safely", async () => {
  const request = vi
    .fn()
    .mockImplementation((path: string) =>
      Promise.resolve(
        path.includes("?")
          ? { items: [article], next_offset: null }
          : { ...article, body_uk: "<script>bad()</script>\n\nУточніть потребу." },
      ),
    );
  show(request);
  await userEvent.click(await screen.findByRole("link", { name: article.title_uk }));
  expect(await screen.findByText("<script>bad()</script>")).toBeInTheDocument();
  expect(document.querySelector("script")).toBeNull();
  expect(screen.getByText(/Необов’язкове читання/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /завершити/i })).not.toBeInTheDocument();
  expect(request.mock.calls.every((call) => call[1] === undefined)).toBe(true);
});
it("does not render content on a denied direct link and allows retry", async () => {
  const request = vi.fn().mockRejectedValueOnce(new Error("denied")).mockResolvedValue(article);
  show(request, "/employee/academy/welcome");
  expect(await screen.findByRole("alert")).toHaveTextContent("Стаття недоступна");
  expect(screen.queryByText(article.body_uk)).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Спробувати ще раз" }));
  expect(await screen.findByText("Привітайте гостя.")).toBeInTheDocument();
});
it("requests a protected cover separately and keeps the article when it fails", async () => {
  const request = vi
    .fn()
    .mockImplementation((path: string) =>
      path.endsWith("/cover")
        ? Promise.reject(new Error("unavailable"))
        : Promise.resolve({ ...article, cover_asset_id: "asset" }),
    );
  show(request, "/employee/academy/welcome");
  expect(await screen.findByText("Обкладинка тимчасово недоступна.")).toBeInTheDocument();
  expect(screen.getByText("Привітайте гостя.")).toBeInTheDocument();
  expect(request).toHaveBeenCalledWith("/me/academy/welcome/cover");
});

import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AdminEmployeeDetailPage } from "../admin/AdminEmployeeDetailPage";
import { AdminEmployeesPage } from "../admin/AdminEmployeesPage";
import { LoginPage } from "../auth/LoginPage";
import { MfaPage } from "../auth/MfaPage";
import { PendingPage } from "../employee/PendingPage";
import { InvitationAcceptPage } from "../invitations/InvitationAcceptPage";
import { AdminShell } from "../shells/AdminShell";
import { EmployeeShell } from "../shells/EmployeeShell";
import { HomeRedirect, ProtectedRoute } from "../session/SessionGate";
import { SessionProvider } from "../session/SessionContext";

function Placeholder({ eyebrow, title }: { eyebrow: string; title: string }) {
  return (
    <section className="content-section">
      <p className="eyebrow">{eyebrow}</p>
      <h1>{title}</h1>
    </section>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <SessionProvider>
        <Routes>
          <Route path="/" element={<HomeRedirect />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/mfa" element={<MfaPage />} />
          <Route path="/invite" element={<InvitationAcceptPage />} />
          <Route
            path="/admin/employees"
            element={
              <ProtectedRoute audience="admin">
                <AdminShell>
                  <AdminEmployeesPage />
                </AdminShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/employees/:employeeId"
            element={
              <ProtectedRoute audience="admin">
                <AdminShell>
                  <AdminEmployeeDetailPage />
                </AdminShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/employee/pending"
            element={
              <ProtectedRoute audience="pending-employee">
                <EmployeeShell>
                  <PendingPage />
                </EmployeeShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/employee"
            element={
              <ProtectedRoute audience="active-employee">
                <EmployeeShell>
                  <Placeholder eyebrow="Головна" title="Вітаємо в Bacara Academy" />
                </EmployeeShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/forbidden"
            element={
              <main aria-label="Bacara Academy" className="state-page">
                <Placeholder eyebrow="Доступ" title="Ця сторінка недоступна" />
              </main>
            }
          />
          <Route
            path="/access-disabled"
            element={
              <main aria-label="Bacara Academy" className="state-page">
                <Placeholder eyebrow="Доступ" title="Обліковий запис вимкнено" />
              </main>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </SessionProvider>
    </BrowserRouter>
  );
}

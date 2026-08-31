import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AdminEmployeeDetailPage } from "../admin/AdminEmployeeDetailPage";
import { AdminEmployeesPage } from "../admin/AdminEmployeesPage";
import { AdminMenuPage } from "../admin/AdminMenuPage";
import { AdminQuestionBankPage } from "../admin/AdminQuestionBankPage";
import { AdminResultDetailPage } from "../admin/AdminResultDetailPage";
import { AdminResultsPage } from "../admin/AdminResultsPage";
import { AdminTrainingPage } from "../admin/AdminTrainingPage";
import { LoginPage } from "../auth/LoginPage";
import { MfaPage } from "../auth/MfaPage";
import { PendingPage } from "../employee/PendingPage";
import { ActiveHomePage } from "../employee/ActiveHomePage";
import { EmployeeMenuPage } from "../employee/EmployeeMenuPage";
import { EmployeeLearningLessonPage } from "../employee/EmployeeLearningLessonPage";
import { EmployeeLearningModulePage } from "../employee/EmployeeLearningModulePage";
import { EmployeeLearningPage } from "../employee/EmployeeLearningPage";
import { EmployeePracticePage } from "../employee/EmployeePracticePage";
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
            path="/admin/menu"
            element={
              <ProtectedRoute audience="admin">
                <AdminShell>
                  <AdminMenuPage />
                </AdminShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/content"
            element={
              <ProtectedRoute audience="admin">
                <AdminShell>
                  <AdminTrainingPage />
                </AdminShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/questions"
            element={
              <ProtectedRoute audience="admin">
                <AdminShell>
                  <AdminQuestionBankPage />
                </AdminShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/results"
            element={
              <ProtectedRoute audience="admin">
                <AdminShell>
                  <AdminResultsPage />
                </AdminShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/results/:employeeId"
            element={
              <ProtectedRoute audience="admin">
                <AdminShell>
                  <AdminResultDetailPage />
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
                  <ActiveHomePage />
                </EmployeeShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/employee/menu"
            element={
              <ProtectedRoute audience="active-employee">
                <EmployeeShell>
                  <EmployeeMenuPage />
                </EmployeeShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/employee/learning"
            element={
              <ProtectedRoute audience="active-employee">
                <EmployeeShell>
                  <EmployeeLearningPage />
                </EmployeeShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/employee/learning/modules/:moduleId"
            element={
              <ProtectedRoute audience="active-employee">
                <EmployeeShell>
                  <EmployeeLearningModulePage />
                </EmployeeShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/employee/learning/lessons/:lessonId"
            element={
              <ProtectedRoute audience="active-employee">
                <EmployeeShell>
                  <EmployeeLearningLessonPage />
                </EmployeeShell>
              </ProtectedRoute>
            }
          />
          <Route
            path="/employee/practice"
            element={
              <ProtectedRoute audience="active-employee">
                <EmployeeShell>
                  <EmployeePracticePage />
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

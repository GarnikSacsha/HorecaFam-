import { Navigate } from "react-router-dom";

import { ErrorState, LoadingState } from "../ui/States";
import { useSession } from "./SessionContext";

type Audience = "admin" | "pending-employee" | "active-employee";
type ActiveSession = NonNullable<ReturnType<typeof useSession>["session"]>;

function sessionDestination(session: ActiveSession): string {
  const adminAccess = session.organization_access.find((access) => access.is_organization_admin);
  if (adminAccess && session.session.mfa_verified) return "/admin/employees";
  const employeeAccess = session.organization_access.find((access) => access.is_employee);
  if (employeeAccess?.membership_status === "pending") return "/employee/pending";
  if (employeeAccess?.membership_status === "active") return "/employee";
  if (employeeAccess?.membership_status === "disabled") return "/access-disabled";
  return "/forbidden";
}

function SessionBoundary({ children }: { children: (session: ActiveSession) => React.ReactNode }) {
  const { refreshSession, session, status } = useSession();
  if (status === "bootstrapping") return <LoadingState label="Перевіряємо сесію…" />;
  if (status === "error") {
    return (
      <ErrorState
        title="Не вдалося перевірити сесію"
        description="Перевірте з’єднання та повторіть спробу."
        onRetry={() => void refreshSession()}
      />
    );
  }
  if (status === "anonymous" || !session) return <Navigate to="/login" replace />;
  return children(session);
}

export function HomeRedirect() {
  return (
    <SessionBoundary>
      {(session) => <Navigate to={sessionDestination(session)} replace />}
    </SessionBoundary>
  );
}

export function ProtectedRoute({
  audience,
  children,
}: {
  audience: Audience;
  children: React.ReactNode;
}) {
  return (
    <SessionBoundary>
      {(session) => {
        const allowed = session.organization_access.some((access) => {
          if (audience === "admin")
            return access.is_organization_admin && session.session.mfa_verified;
          if (!access.is_employee) return false;
          return audience === "pending-employee"
            ? access.membership_status === "pending"
            : access.membership_status === "active";
        });
        return allowed ? children : <Navigate to={sessionDestination(session)} replace />;
      }}
    </SessionBoundary>
  );
}

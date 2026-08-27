import { NavLink } from "react-router-dom";

const destinations = [
  { label: "Головна", to: "/employee", enabled: true },
  { label: "Навчання", to: "/employee/learning", enabled: false },
  { label: "Практика", to: "/employee/practice", enabled: false },
  { label: "Профіль", to: "/employee/profile", enabled: false },
];

export function EmployeeShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="employee-layout">
      <header className="employee-header">
        <span className="brand-mark">Bacara Academy</span>
      </header>
      <main aria-label="Bacara Academy" className="employee-content">
        {children}
      </main>
      <nav aria-label="Основна навігація" className="employee-nav">
        {destinations.map((destination) =>
          destination.enabled ? (
            <NavLink
              key={destination.to}
              to={destination.to}
              end
              className={({ isActive }) => `employee-nav-link${isActive ? " is-active" : ""}`}
            >
              <span className="nav-dot" aria-hidden="true" />
              {destination.label}
            </NavLink>
          ) : (
            <button key={destination.to} className="employee-nav-link" type="button" disabled>
              <span className="nav-dot" aria-hidden="true" />
              {destination.label}
            </button>
          ),
        )}
      </nav>
    </div>
  );
}

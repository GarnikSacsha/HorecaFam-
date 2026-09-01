import { useEffect, useRef, useState } from "react";
import { NavLink } from "react-router-dom";

import { LogoutButton } from "../auth/LogoutButton";

const links = [
  { to: "/operator/jobs", label: "Jobs" },
  { to: "/operator/audit", label: "Системний аудит" },
];

function OperatorNavigation({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav aria-label="Навігація Platform Operator" className="admin-nav">
      {links.map((link) => (
        <NavLink
          key={link.to}
          to={link.to}
          onClick={onNavigate}
          className={({ isActive }) => `admin-nav-link${isActive ? " is-active" : ""}`}
        >
          {link.label}
        </NavLink>
      ))}
    </nav>
  );
}

export function OperatorShell({ children }: { children: React.ReactNode }) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  const closeDrawer = () => {
    setDrawerOpen(false);
    triggerRef.current?.focus();
  };

  useEffect(() => {
    if (!drawerOpen) return;
    const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    focusable?.[0]?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeDrawer();
        return;
      }
      if (event.key !== "Tab" || !focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [drawerOpen]);

  return (
    <div className="admin-layout operator-layout">
      <aside className="admin-sidebar operator-sidebar">
        <p className="brand-mark">Bacara Academy</p>
        <p className="workspace-label">Platform Operations</p>
        <OperatorNavigation />
        <LogoutButton />
      </aside>
      <div className="admin-workspace">
        <header className="admin-mobile-header">
          <span className="brand-mark">Bacara Academy</span>
          <button
            className="button button-quiet"
            type="button"
            onClick={() => setDrawerOpen(true)}
            ref={triggerRef}
            aria-expanded={drawerOpen}
          >
            Відкрити навігацію
          </button>
        </header>
        <main aria-label="Робоча область Platform Operator" className="admin-content">
          {children}
        </main>
      </div>
      {drawerOpen ? (
        <div className="drawer-layer">
          <button
            className="drawer-backdrop"
            type="button"
            onClick={closeDrawer}
            tabIndex={-1}
            aria-label="Закрити навігацію"
          />
          <div
            className="drawer-panel"
            role="dialog"
            aria-modal="true"
            aria-label="Навігація Platform Operator"
            ref={dialogRef}
          >
            <div className="drawer-heading">
              <span className="brand-mark">Bacara Academy</span>
              <button className="button button-quiet" type="button" onClick={closeDrawer}>
                Закрити
              </button>
            </div>
            <OperatorNavigation onNavigate={closeDrawer} />
            <LogoutButton />
          </div>
        </div>
      ) : null}
    </div>
  );
}

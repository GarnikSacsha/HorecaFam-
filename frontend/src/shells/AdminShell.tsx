import { useEffect, useRef, useState } from "react";
import { NavLink } from "react-router-dom";

const links = [
  { to: "/admin/employees", label: "Працівники" },
  { to: "/admin/menu", label: "Меню" },
  { to: "/admin/content", label: "Навчальні матеріали" },
  { to: "/admin/questions", label: "Банк питань" },
  { to: "/admin/results", label: "Результати" },
];

function AdminNavigation({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav aria-label="Навігація адміністратора" className="admin-nav">
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

export function AdminShell({ children }: { children: React.ReactNode }) {
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
    <div className="admin-layout">
      <aside className="admin-sidebar">
        <p className="brand-mark">Bacara Academy</p>
        <p className="workspace-label">Адміністрування</p>
        <AdminNavigation />
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
        <main aria-label="Робоча область адміністратора" className="admin-content">
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
            aria-label="Навігація адміністратора"
            ref={dialogRef}
          >
            <div className="drawer-heading">
              <span className="brand-mark">Bacara Academy</span>
              <button className="button button-quiet" type="button" onClick={closeDrawer}>
                Закрити
              </button>
            </div>
            <AdminNavigation onNavigate={closeDrawer} />
          </div>
        </div>
      ) : null}
    </div>
  );
}

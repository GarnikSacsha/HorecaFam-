export function LoadingState({ label }: { label: string }) {
  return (
    <main aria-label="Bacara Academy" className="state-page" aria-busy="true">
      <span className="state-spinner" aria-hidden="true" />
      <p>{label}</p>
    </main>
  );
}

export function ErrorState({
  title,
  description,
  onRetry,
}: {
  title: string;
  description: string;
  onRetry?: () => void;
}) {
  return (
    <main aria-label="Bacara Academy" className="state-page">
      <p className="eyebrow">Потрібна дія</p>
      <h1>{title}</h1>
      <p className="state-description">{description}</p>
      {onRetry ? (
        <button className="button button-primary" type="button" onClick={onRetry}>
          Повторити
        </button>
      ) : null}
    </main>
  );
}

export function StatusPill({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: "neutral" | "info" | "success" | "warning" | "danger";
}) {
  return <span className={`status-pill status-${tone}`}>{children}</span>;
}

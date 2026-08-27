import { useEffect, useRef } from "react";

import type { FieldError } from "../api/contracts";

export function ErrorSummary({
  title = "Перевірте введені дані",
  errors,
}: {
  title?: string;
  errors: FieldError[];
}) {
  const summaryRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (errors.length > 0) summaryRef.current?.focus();
  }, [errors]);
  if (errors.length === 0) return null;
  return (
    <div className="error-summary" role="alert" tabIndex={-1} ref={summaryRef}>
      <h2>{title}</h2>
      <ul>
        {errors.map((error) => (
          <li key={`${error.field}-${error.code}`}>
            <a href={`#${error.field}`}>{error.message}</a>
          </li>
        ))}
      </ul>
    </div>
  );
}

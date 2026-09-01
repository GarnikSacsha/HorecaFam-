import type { AuditEventResponse } from "../api/contracts";
import { StatusPill } from "./States";

function formatDate(value: string) {
  return new Intl.DateTimeFormat("uk-UA", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function EventOutcome({ outcome }: { outcome: AuditEventResponse["outcome"] }) {
  return (
    <StatusPill tone={outcome === "success" ? "success" : "danger"}>
      {outcome === "success" ? "Успішно" : "Помилка"}
    </StatusPill>
  );
}

export function AuditEventList({
  items,
  tableLabel,
  mobileLabel,
}: {
  items: AuditEventResponse[];
  tableLabel: string;
  mobileLabel: string;
}) {
  return (
    <>
      <div className="desktop-table-wrap operations-table-wrap">
        <table className="data-table" aria-label={tableLabel}>
          <thead>
            <tr>
              <th>Час</th>
              <th>Дія</th>
              <th>Актор</th>
              <th>Ціль</th>
              <th>Результат</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td>
                  <time dateTime={item.created_at}>{formatDate(item.created_at)}</time>
                </td>
                <td>
                  <strong>{item.action}</strong>
                </td>
                <td>{item.actor_type}</td>
                <td>
                  {item.target_type}
                  {item.target_id ? (
                    <small className="operations-id">{item.target_id}</small>
                  ) : null}
                </td>
                <td>
                  <EventOutcome outcome={item.outcome} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="operations-mobile-list" aria-label={mobileLabel}>
        {items.map((item) => (
          <article className="operations-card" key={item.id}>
            <div className="operations-card-heading">
              <strong>{item.action}</strong>
              <EventOutcome outcome={item.outcome} />
            </div>
            <p>{item.target_type}</p>
            <p>
              {item.actor_type} ·{" "}
              <time dateTime={item.created_at}>{formatDate(item.created_at)}</time>
            </p>
          </article>
        ))}
      </div>
    </>
  );
}

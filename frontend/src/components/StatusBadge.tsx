interface StatusBadgeProps {
  status: "checking" | "ok" | "error";
  apiBase: string;
}

export function StatusBadge({ status, apiBase }: StatusBadgeProps) {
  const label =
    status === "checking" ? "Connecting…" : status === "ok" ? "API ready" : "API offline";

  return (
    <div className={`status-badge status-${status}`} title={apiBase}>
      <span className="status-dot" />
      {label}
    </div>
  );
}

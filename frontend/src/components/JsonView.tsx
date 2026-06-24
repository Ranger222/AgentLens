// Zero-dependency pretty JSON. Strings are shown as-is; everything else is
// stringified with indentation. (A richer tree view is a future enhancement.)

function render(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export function JsonView({ value }: { value: unknown }) {
  if (value == null) return <span className="muted">—</span>;
  return <pre className="json">{render(value)}</pre>;
}

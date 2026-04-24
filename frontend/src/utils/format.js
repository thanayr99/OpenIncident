export function formatPercent(value) {
  if (typeof value !== "number") return "50%";
  return `${Math.round(value * 100)}%`;
}

export function formatTime(value) {
  if (!value) return "No timestamp";
  try {
    return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return String(value);
  }
}

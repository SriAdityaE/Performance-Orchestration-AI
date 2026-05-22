export function formatSingleRunReport(payload: Record<string, unknown>): string {
  const sections = Object.entries(payload).map(([key, value]) => {
    return `*${key}*\n${formatValue(value)}`;
  });
  return sections.join("\n\n");
}

function formatValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map((item) => `- ${formatValue(item)}`).join("\n");
  }
  if (value && typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, nested]) => `${key}: ${formatValue(nested)}`)
      .join("\n");
  }
  return String(value);
}

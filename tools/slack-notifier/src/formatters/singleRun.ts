export function formatSingleRunReport(payload: Record<string, unknown>): string {
  const summary = (payload["Test Summary"] as Record<string, unknown> | undefined) ?? undefined;
  const execution =
    (payload["Test Execution Summary"] as Record<string, unknown> | undefined) ?? undefined;
  const observations =
    (payload["Detailed Observations and Analysis"] as unknown[] | undefined) ?? undefined;

  const sections: string[] = [];
  if (summary) {
    sections.push(formatSummary(summary));
  }
  if (execution) {
    sections.push(`*Test Execution Summary*\n${formatValue(execution)}`);
  }
  if (Array.isArray(observations)) {
    sections.push(
      "*Test Observations*\n" + observations.map((line) => `- ${String(line)}`).join("\n"),
    );
  }

  const rendered = sections.join("\n\n");
  return rendered || formatValue(payload);
}

function formatSummary(summary: Record<string, unknown>): string {
  const aggregate = Array.isArray(summary.jmeter_aggregate)
    ? (summary.jmeter_aggregate as Record<string, unknown>[])
    : [];
  const transactionLabel = String(summary.test_name ?? "ALL");
  const environment = String(summary.environment ?? "N/A");
  const transactions = Number(summary.transactions ?? 0);

  const header = [
    "*JMeter Aggregate Summary (Stakeholder View)*",
    `Test: ${transactionLabel}`,
    `Environment: ${environment}`,
    `Transactions: ${transactions}`,
  ].join("\n");

  if (aggregate.length === 0) {
    return `${header}\n${formatValue(summary)}`;
  }

  const row = aggregate[0];
  const table = [
    "```",
    "Label | Samples | Avg(ms) | P95(ms) | P99(ms) | Max(ms) | Error% | Throughput/s",
    "----- | ------- | ------- | ------- | ------- | ------- | ------ | ------------",
    `${String(row.label ?? transactionLabel)} | ${Number(row.samples ?? transactions)} | ${Number(row.average_ms ?? 0).toFixed(2)} | ${Number(row.p95_ms ?? 0).toFixed(2)} | ${Number(row.p99_ms ?? 0).toFixed(2)} | ${Number(row.max_ms ?? 0).toFixed(2)} | ${Number(row.error_pct ?? 0).toFixed(2)} | ${Number(row.throughput_per_sec ?? 0).toFixed(2)}`,
    "```",
  ].join("\n");

  return `${header}\n${table}`;
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

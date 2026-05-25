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
  const transactionLabel = String(summary.test_name ?? "N/A");
  const environment = String(summary.environment ?? "N/A");
  const transactions = Number(summary.transactions ?? 0);
  const transactionNames = Array.isArray(summary.transaction_names)
    ? summary.transaction_names
    : [];
  const transactionsDetected = Number(summary.transactions_detected ?? transactionNames.length ?? 0);
  const transactionList = transactionNames.length > 0 ? transactionNames.join(", ") : "N/A";

  const header = [
    "*JMeter Aggregate Summary (Stakeholder View)*",
    `Test: ${transactionLabel}`,
    `Environment: ${environment}`,
    `Samples: ${transactions}`,
    `Transactions Detected: ${transactionsDetected}`,
    `Transaction Names: ${transactionList}`,
  ].join("\n");

  if (aggregate.length === 0) {
    return `${header}\n${formatValue(summary)}`;
  }

  const rows = aggregate.map((row) => {
    return `${String(row.label ?? "UNNAMED")} | ${Number(row.samples ?? 0)} | ${Number(row.average_ms ?? 0).toFixed(2)} | ${Number(row.median_ms ?? 0).toFixed(2)} | ${Number(row.p90_ms ?? 0).toFixed(2)} | ${Number(row.p95_ms ?? 0).toFixed(2)} | ${Number(row.p99_ms ?? 0).toFixed(2)} | ${Number(row.max_ms ?? 0).toFixed(2)} | ${Number(row.error_pct ?? 0).toFixed(2)} | ${Number(row.throughput_per_sec ?? 0).toFixed(2)}`;
  });

  const table = [
    "```",
    "Label | Samples | Avg(ms) | Median(ms) | P90(ms) | P95(ms) | P99(ms) | Max(ms) | Error% | Throughput/s",
    "----- | ------- | ------- | ---------- | ------- | ------- | ------- | ------- | ------ | ------------",
    ...rows,
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

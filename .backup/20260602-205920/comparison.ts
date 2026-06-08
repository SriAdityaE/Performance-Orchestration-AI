export type SlackRenderedMessage = {
  text: string;
  blocks: Record<string, unknown>[];
};

export function formatComparisonReport(
  payload: Record<string, unknown>,
  context?: { occurredAt?: string; signerName?: string },
): string | SlackRenderedMessage {
  const todaySummary = (payload["Today's Test Results Summary"] as Record<string, unknown> | undefined) ?? undefined;
  const execution = (payload["Test Execution Summary"] as Record<string, unknown> | undefined) ?? undefined;
  const analysis = (payload["Detailed Observations and Analysis"] as unknown[] | undefined) ?? undefined;
  const recommendation = String(payload["Recommendation or Conclusion"] ?? "N/A");

  if (!todaySummary || !execution) {
    const sections = Object.entries(payload).map(([key, value]) => {
      return `*${key}*\n${formatValue(value)}`;
    });
    return sections.join("\n\n");
  }

  const runNames = Object.keys(todaySummary);
  const reportDate = formatReportDate(context?.occurredAt);
  const subjectLabel = runNames[0] ?? "Performance Comparison";
  const emailSubject = `${subjectLabel} ${reportDate}`;
  const runCount = runNames.length;
  const signerName = context?.signerName ?? "Performance Team";

  const blocks: Record<string, unknown>[] = [
    {
      type: "section",
      text: {
        type: "mrkdwn",
        text:
          `*Subject:* ${emailSubject}\n\n` +
          "Hello Team,\n\n" +
          `Please find the reviewed performance comparison for ${runNames.join(" vs ")} executed on ${reportDate}. ` +
          "The attached summary includes validation checks, baseline-candidate deltas, and detailed observations. " +
          "Please find below the detailed comparison observations and recommendations.\n\n",
      },
    },
    {
      type: "header",
      text: {
        type: "plain_text",
        text: `Performance Comparison Report (${runCount} Runs)`,
      },
    },
    {
      type: "section",
      text: {
        type: "mrkdwn",
        text: `*Run Pair:* ${runNames.join(" vs ")}\n*Execution Date:* ${reportDate}`,
      },
    },
    {
      type: "section",
      text: {
        type: "mrkdwn",
        text: formatRunSummaryMarkdown(todaySummary),
      },
    },
    {
      type: "section",
      text: {
        type: "mrkdwn",
        text: formatExecutionSummaryMarkdown(execution),
      },
    },
  ];

  if (Array.isArray(analysis) && analysis.length > 0) {
    blocks.push({
      type: "section",
      text: {
        type: "mrkdwn",
        text:
          "*Trend Analysis*\n" +
          `${analysis.map((item) => `• ${formatDeltaLine(item)}`).join("\n")}`,
      },
    });
  }

  blocks.push({
    type: "section",
    text: {
      type: "mrkdwn",
      text: `*Recommendation or Conclusion*\n${recommendation}`,
    },
  });

  blocks.push({
    type: "section",
    text: {
      type: "mrkdwn",
      text: `Thanks,\n${signerName}`,
    },
  });

  return {
    text: `Performance Comparison Report: ${runNames.join(" vs ")}`,
    blocks,
  };
}

function formatRunSummaryMarkdown(todaySummary: Record<string, unknown>): string {
  const lines = ["*Today's Test Results Summary*"];
  for (const [runName, value] of Object.entries(todaySummary)) {
    const metrics = value as Record<string, unknown>;
    lines.push(
      `• *${runName}:* tx=${Number(metrics.transactions ?? 0)}, throughput=${Number(metrics.throughput ?? 0).toFixed(2)} req/sec, avg=${Number(metrics.avg_ms ?? 0).toFixed(2)} ms, p95=${Number(metrics.p95_ms ?? 0).toFixed(2)} ms, p99=${Number(metrics.p99_ms ?? 0).toFixed(2)} ms, err=${Number(metrics.error_rate_pct ?? 0).toFixed(2)}%`,
    );
  }
  return lines.join("\n");
}

function formatExecutionSummaryMarkdown(execution: Record<string, unknown>): string {
  const baseline = String(execution.baseline ?? "N/A");
  const candidate = String(execution.candidate ?? "N/A");
  const observations = Array.isArray(execution.observations)
    ? execution.observations.map((item) => `• ${String(item)}`).join("\n")
    : "• No comparison observations captured.";
  return `*Test Execution Summary*\n*Baseline:* ${baseline}\n*Candidate:* ${candidate}\n*Observations:*\n${observations}`;
}

function formatDeltaLine(item: unknown): string {
  if (!item || typeof item !== "object") {
    return String(item);
  }
  const delta = item as Record<string, unknown>;
  return `${String(delta.metric ?? "metric")}: baseline=${Number(delta.baseline ?? 0).toFixed(2)}, candidate=${Number(delta.candidate ?? 0).toFixed(2)}, delta=${Number(delta.delta_pct ?? 0).toFixed(2)}%, classification=${String(delta.classification ?? "N/A")}`;
}

function formatReportDate(occurredAt?: string): string {
  const parsed = occurredAt ? new Date(occurredAt) : new Date();
  if (Number.isNaN(parsed.getTime())) {
    const fallback = new Date();
    return `${fallback.getUTCFullYear()}-${String(fallback.getUTCMonth() + 1).padStart(2, "0")}-${String(fallback.getUTCDate()).padStart(2, "0")}`;
  }
  return `${parsed.getUTCFullYear()}-${String(parsed.getUTCMonth() + 1).padStart(2, "0")}-${String(parsed.getUTCDate()).padStart(2, "0")}`;
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

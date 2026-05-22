import { formatComparisonReport } from "./formatters/comparison.js";
import { formatSingleRunReport } from "./formatters/singleRun.js";

type EventType =
  | "test_started"
  | "test_ended"
  | "report_preparation_in_progress"
  | "final_report_ready";

type LifecycleEvent = {
  event_type: EventType;
  run_id: string;
  message: string;
  test_name?: string | null;
  details?: Record<string, unknown> & {
    report_payload?: Record<string, unknown>;
    custom_report_format?: Record<string, unknown> | null;
  };
  occurred_at: string;
};

const allowedEvents = new Set<EventType>([
  "test_started",
  "test_ended",
  "report_preparation_in_progress",
  "final_report_ready",
]);

async function readStdin(): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of process.stdin) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  return Buffer.concat(chunks).toString("utf8");
}

function formatEvent(event: LifecycleEvent): string {
  if (
    event.event_type === "final_report_ready" &&
    event.details?.report_payload &&
    typeof event.details.report_payload === "object"
  ) {
    return formatFinalReport(event);
  }

  const headerMap: Record<EventType, string> = {
    test_started: "TEST STARTED",
    test_ended: "TEST ENDED",
    report_preparation_in_progress: "REPORT PREPARATION IN PROGRESS",
    final_report_ready: "FINAL REPORT READY",
  };

  const parts = [
    `*${headerMap[event.event_type]}*`,
    `Run ID: ${event.run_id}`,
    `Time: ${event.occurred_at}`,
    `Message: ${event.message}`,
  ];

  if (event.test_name) {
    parts.push(`Test: ${event.test_name}`);
  }
  if (event.details && Object.keys(event.details).length > 0) {
    parts.push(`Details: ${JSON.stringify(event.details)}`);
  }
  return parts.join("\n");
}

function formatFinalReport(event: LifecycleEvent): string {
  const reportPayload = event.details?.report_payload as Record<string, unknown>;
  const customFormat = event.details?.custom_report_format as Record<string, unknown> | null | undefined;
  const reportSectionKeys = Object.keys(reportPayload);
  const isComparisonReport = reportSectionKeys.includes("Today's Test Results Summary");

  let body = isComparisonReport
    ? formatComparisonReport(reportPayload)
    : formatSingleRunReport(reportPayload);

  if (customFormat?.title && typeof customFormat.title === "string") {
    body = `*${customFormat.title}*\n\n${body}`;
  }

  return [
    `*FINAL REPORT READY*`,
    `Run ID: ${event.run_id}`,
    `Time: ${event.occurred_at}`,
    "",
    body,
  ].join("\n");
}

function parseEvent(raw: string): LifecycleEvent {
  const payload = JSON.parse(raw) as LifecycleEvent;
  if (!allowedEvents.has(payload.event_type)) {
    throw new Error(`Unsupported event type: ${payload.event_type}`);
  }
  return payload;
}

async function postToSlack(webhookUrl: string, body: string): Promise<void> {
  const response = await fetch(webhookUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ text: body }),
  });

  if (!response.ok) {
    throw new Error(`Slack notification failed with status ${response.status}`);
  }
}

async function main(): Promise<void> {
  const raw = await readStdin();
  const event = parseEvent(raw);
  const message = formatEvent(event);
  const channel = (process.env.NOTIFICATION_CHANNEL ?? "slack").toLowerCase();

  if (channel === "terminal") {
    process.stdout.write(message + "\n");
    return;
  }

  const webhook = process.env.SLACK_WEBHOOK_URL;
  if (!webhook) {
    throw new Error("SLACK_WEBHOOK_URL is required for Slack delivery");
  }

  await postToSlack(webhook, message);
  process.stdout.write("sent\n");
}

main().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(message + "\n");
  process.exitCode = 1;
});
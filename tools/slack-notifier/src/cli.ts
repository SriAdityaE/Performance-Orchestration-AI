import { formatComparisonReport } from "./formatters/comparison.js";
import { formatSingleRunReport, type SlackRenderedMessage } from "./formatters/singleRun.js";

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

type SlackPostPayload = {
  text: string;
  blocks?: Record<string, unknown>[];
};

async function readStdin(): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of process.stdin) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  return Buffer.concat(chunks).toString("utf8");
}

function formatEvent(event: LifecycleEvent): SlackPostPayload {
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
  return { text: parts.join("\n") };
}

function formatFinalReport(event: LifecycleEvent): SlackPostPayload {
  const reportPayload = event.details?.report_payload as Record<string, unknown>;
  const customFormat = event.details?.custom_report_format as Record<string, unknown> | null | undefined;
  const reportSectionKeys = Object.keys(reportPayload);
  const isComparisonReport = reportSectionKeys.includes("Today's Test Results Summary");

  const rendered = isComparisonReport
    ? formatComparisonReport(reportPayload)
    : formatSingleRunReport(reportPayload);

  if (typeof rendered === "string") {
    const titlePrefix = customFormat?.title && typeof customFormat.title === "string"
      ? `*${customFormat.title}*\n\n`
      : "";
    return {
      text: [
        `*FINAL REPORT READY*`,
        `Run ID: ${event.run_id}`,
        `Time: ${event.occurred_at}`,
        "",
        `${titlePrefix}${rendered}`,
      ].join("\n"),
    };
  }

  const blocks = withReportHeaderBlocks(event, rendered, customFormat);
  return {
    text: `FINAL REPORT READY | Run ID: ${event.run_id}`,
    blocks,
  };
}

function withReportHeaderBlocks(
  event: LifecycleEvent,
  report: SlackRenderedMessage,
  customFormat: Record<string, unknown> | null | undefined,
): Record<string, unknown>[] {
  const blocks: Record<string, unknown>[] = [];

  blocks.push({
    type: "section",
    text: {
      type: "mrkdwn",
      text: `*FINAL REPORT READY*\nRun ID: ${event.run_id}\nTime: ${event.occurred_at}`,
    },
  });

  if (customFormat?.title && typeof customFormat.title === "string") {
    blocks.push({
      type: "header",
      text: {
        type: "plain_text",
        text: customFormat.title,
      },
    });
  }

  blocks.push(...report.blocks);
  return blocks;
}

function parseEvent(raw: string): LifecycleEvent {
  const payload = JSON.parse(raw) as LifecycleEvent;
  if (!allowedEvents.has(payload.event_type)) {
    throw new Error(`Unsupported event type: ${payload.event_type}`);
  }
  return payload;
}

async function postToSlack(webhookUrl: string, payload: SlackPostPayload): Promise<void> {
  const response = await fetch(webhookUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
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
    process.stdout.write(JSON.stringify(message, null, 2) + "\n");
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
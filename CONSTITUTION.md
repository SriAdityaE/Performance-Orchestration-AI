# Performance Orchestration AI Constitution

## Core Principles

### I. Production-Grade Execution First
Every workflow must be operable in a production-like setting without manual patching during execution. The system must support performance test initiation from the local machine and controlled execution on the remote VM, with deterministic configuration, repeatable startup steps, and explicit failure handling. Convenience shortcuts that reduce reliability, traceability, or operational safety are not acceptable.

### II. Local-to-VM Orchestration Is Mandatory
Performance test execution must begin from the local environment and then coordinate execution on the VM environment when required by the run plan. The shared repository root is the handoff boundary for artifacts, scripts, and result files. JMeter startup on the VM must use the configured VM installation path and must accept user-provided test plan paths and execution inputs without requiring code changes per test.

### III. Validation Before Reporting
No performance report may be sent until the run results have been validated. Validation must cover, at minimum, response times, throughput, error rate, and pass/fail determination against the active test criteria. If two tests are queued, the second test must run only after the first execution flow completes, and the final reporting step must validate both runs and include comparative observations across them.

### IV. Slack-First Structured Reporting
Slack is the primary delivery channel for post-execution reporting unless explicitly changed by configuration. Reports must be sent only in the user-requested format when that format is provided; otherwise, the system must use a standard structured summary that highlights metrics, validation outcome, environment, and actionable observations. Notification payloads must be concise enough for channel consumption while preserving a clear link between raw measurements and summary conclusions.

### V. Secure, Observable, and Auditable Automation
All credentials, webhook URLs, and environment-specific endpoints must be supplied through environment variables or approved secret storage and must never be committed into repository content. Every execution step must emit logs, timestamps, environment identity, artifact paths, and failure reasons sufficient for diagnosis. Queue handling, retries, report generation, and VM invocation must remain observable and auditable end to end.

## Runtime and Environment Standards

The platform shall support the following operating model and environment constraints:

- Shared execution root: `PERF_SHARED_ROOT`
- Local shared root path: `C:\Users\erraguntlaaditya\OneDrive - Nagarro\Documents\Practice\MCPServer\Performance_TestExecution&Reporting`
- VM shared root path: `L:\MCP\Performance_TestExecution-Reporting`
- VM JMeter home: `JMETER_HOME=L:\apache-jmeter-5.5_New\apache-jmeter-5.5`
- Notification channel values allowed: `terminal`, `teams`, `slack`, `both`
- Default notification mode for this project: `slack`

The runtime must satisfy these additional standards:

- Test plans, execution profiles, and report artifacts must be sourced from version-controlled or explicitly traceable locations.
- The user may provide the JMeter test path and the desired report format at runtime; the system must treat both as first-class inputs.
- The Slack webhook must be read from `SLACK_WEBHOOK_URL` at runtime and must not be embedded in configuration files, documentation, or code.
- `TEAMS_WEBHOOK_URL` remains optional and must not block execution when unset.
- Any missing required path, unreadable artifact, failed JMeter startup, or failed result parse must stop reporting and surface a clear failure status.
- Comparative reporting for queued runs must include a baseline-versus-follow-up view that highlights regressions, improvements, and inconclusive outcomes.

## Execution Workflow and Quality Gates

The project shall implement and preserve the following workflow:

1. Accept run input including test plan path, environment selection, optional report template, and notification configuration.
2. Validate prerequisites before execution: shared root availability, script presence, JMeter path availability on the target machine, writable output location, and webhook presence when Slack reporting is selected.
3. Execute the first test from the local orchestration flow and invoke VM-side JMeter execution when the run requires the remote server.
4. Collect raw outputs, logs, and result artifacts immediately after execution and store them in traceable run folders.
5. Validate the completed run against required metrics and produce a structured result summary.
6. If a second test is queued, repeat the same execution and validation flow sequentially, without overlapping the two runs unless concurrency is explicitly designed and documented later.
7. When two runs exist, perform post-run comparison covering throughput delta, latency delta, error behavior delta, and notable observations that explain operational impact.
8. Deliver the final Slack report in the user-requested format only, including validation status and comparison notes when applicable.

Quality gates are mandatory for every change and execution path:

- Production-grade readiness must be demonstrated through configuration-driven execution rather than machine-specific code edits.
- Result validation logic must be deterministic and testable against representative JMeter outputs.
- Reporting logic must support both single-run and two-run comparative summaries.
- Failure notifications must distinguish between execution failure, validation failure, and notification failure.
- Any change affecting orchestration, validation, or reporting must be reviewed against this constitution before acceptance.

## Governance

This constitution is the controlling guidance for feature planning, implementation, and review in this repository. Any plan, spec, task list, or implementation that conflicts with these rules must be updated to comply before approval.

- Amendments require a documented reason, an explicit update to impacted templates or workflows, and a new amendment date.
- Secret values, including webhook URLs, must be rotated outside the repository if they were ever exposed during drafting or testing.
- Reviews must verify compliance with local-to-VM execution, validation-before-reporting, structured Slack delivery, and secret handling.
- Exceptions are temporary, must be recorded, and must include an expiration or replacement plan.
- Operational guidance should remain aligned with `.github/copilot-instructions.md` and any future approved plan artifacts.

**Version**: 1.0.0 | **Ratified**: 2026-05-22 | **Last Amended**: 2026-05-22


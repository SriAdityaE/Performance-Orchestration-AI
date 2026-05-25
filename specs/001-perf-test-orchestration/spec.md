# Feature Specification: Remote Performance Test Orchestration

**Feature Branch**: `[001-perf-test-orchestration]`

**Created**: 2026-05-22

**Status**: Draft

**Input**: User description: "Build a production-grade performance test orchestration workflow for remote server execution and Slack-based reporting."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run and Report a Single Test (Priority: P1)

An operator starts a performance test orchestration flow from the local machine, the system runs the requested test on the remote execution environment when required, validates the produced results, and sends a final Slack report with clear pass or fail reasoning.

**Why this priority**: Single-run orchestration, validation, and reporting is the minimum valuable workflow and establishes the production path that all higher-order scenarios depend on.

**Independent Test**: Can be fully tested by submitting one valid test request with a reachable remote execution target and confirming that execution, validation, artifact storage, and Slack reporting complete without manual intervention.

**Acceptance Scenarios**:

1. **Given** a user provides a valid test plan path, test name, environment label, load parameters, and Slack delivery is enabled, **When** the orchestration is started from the local machine, **Then** the system executes the test on the required target, validates response time, throughput, and error rate against the configured defaults or approved overrides, stores traceable artifacts, and sends one final Slack report.
2. **Given** a user provides a valid test request without a custom report format, **When** execution and validation finish successfully, **Then** the system sends a standard structured performance summary that contains Test Summary, Test Execution Summary, and Detailed Observations and Analysis sections with the run identity, validation outcome, key metrics, and observations.
3. **Given** a user provides an invalid test path or the remote JMeter startup fails, **When** the orchestration performs prerequisite checks or begins execution, **Then** the system stops safely, classifies the failure, and does not send a misleading success report.

---

### User Story 2 - Compare Two Sequential Test Runs (Priority: P2)

An operator queues two performance tests in one orchestration request, the system executes them one after the other, validates both independently, compares the outcomes, and sends a single comparison report with detailed observations.

**Why this priority**: Comparative analysis is a core business requirement for detecting regressions and improvements, but it depends on the single-run workflow being reliable first.

**Independent Test**: Can be fully tested by submitting exactly two valid queued test requests and verifying that the second run starts only after the first run completes, both runs receive independent validation results, and the final report contains comparison deltas and observations.

**Acceptance Scenarios**:

1. **Given** two valid test requests are queued together, **When** the first run completes its execution, artifact capture, and validation flow, **Then** the second run begins and no overlap occurs between the two execution flows.
2. **Given** both queued runs complete successfully, **When** the comparison step is performed, **Then** the system sends a comparative report containing Today's Test Results Summary, Test Execution Summary, historical or baseline comparison details, Detailed Observations and Analysis, and an explicit recommendation or conclusion based on the metric deltas.
3. **Given** the first run fails before producing valid results, **When** the workflow reaches the failure point, **Then** the system records the failure clearly and does not produce a false comparison summary.

---

### User Story 3 - Respect Requested Report Format (Priority: P3)

An operator provides a custom reporting format for Slack delivery, and the system sends only that requested format while preserving the validated outcome and observations.

**Why this priority**: Custom reporting improves adoption by allowing the workflow output to fit team-specific review standards without changing the underlying execution and validation behavior.

**Independent Test**: Can be fully tested by running a successful orchestration request with custom formatting instructions and verifying that the Slack message follows only the requested format while still reflecting the validated results.

**Acceptance Scenarios**:

1. **Given** a user supplies custom Slack reporting instructions with a valid test request, **When** the final report is generated, **Then** the Slack output follows only the requested format as long as mandatory metrics, pass or fail status, and observations remain present.
2. **Given** a custom reporting request is absent, **When** the final report is generated, **Then** the system falls back to the standard structured performance summary.
3. **Given** a custom reporting request cannot be fulfilled because required result data is missing or unreadable, **When** reporting is attempted, **Then** the system marks the reporting step as failed with a clear reason instead of inventing missing content.

### Edge Cases

- A queued second test is present, but the first run ends in execution failure, validation failure, or result parsing failure.
- The remote target is reachable, but the configured JMeter home path is unavailable or not executable at run time.
- The request includes a custom Slack format that tries to omit mandatory metrics, validation status, or observations.
- Raw result files are produced, but one or more expected metrics cannot be parsed for validation.
- Slack delivery is selected, but secure webhook configuration is missing, invalid, or unavailable at notification time.
- Artifact output locations exist, but the workflow cannot write logs or generated reports to the expected run folder.
- The declared test duration is shorter or longer than the actual execution window recorded by the runner.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST accept a run request initiated from the local machine for either one test or two sequentially queued tests.
- **FR-002**: The system MUST accept runtime input for each requested test, including at minimum a test name, JMeter test plan path, environment label, thread or user count, ramp-up setting, planned duration, and any execution parameters required by the active run contract.
- **FR-003**: The system MUST validate required runtime inputs and execution prerequisites before starting a run, including path availability, target environment readiness, writable artifact locations, and notification prerequisites for the selected delivery channel.
- **FR-004**: The system MUST support local orchestration with remote execution on a VM when the run plan requires it, including operation through a VM-side runner process that is started and made available on the VM for the orchestration flow.
- **FR-005**: The system MUST start JMeter on the VM by using the configured VM JMeter home path defined for the environment.
- **FR-006**: The system MUST store raw results, logs, and generated reports in a traceable run structure that links each artifact set to the originating request, execution target, timestamps, and final status.
- **FR-007**: The system MUST validate each completed test run against active response time, throughput, and error rate criteria and produce a pass or fail outcome with explicit reasoning.
- **FR-007A**: Unless an approved override is supplied for a run, the default validation threshold MUST require error rate to remain at or below 1.00%, P95 response time to remain at or below 2000 ms, P99 response time to remain at or below 3000 ms, and throughput to remain greater than zero for the full completed run window.
- **FR-007B**: When an expected throughput target is supplied as part of the run request, the system MUST include that target in validation and report whether the observed throughput met or missed the stated target.
- **FR-008**: The system MUST classify failures distinctly as execution failures, validation failures, parsing failures, or notification failures and record the step where the failure occurred.
- **FR-009**: The system MUST complete validation for a single run before any final report is sent.
- **FR-010**: When exactly two tests are queued in one request, the system MUST execute the second test only after the first test flow has fully completed.
- **FR-011**: When two validated runs are available, the system MUST compare the runs and produce detailed observations that identify regressions, improvements, or inconclusive outcomes using metric deltas.
- **FR-012**: When a user provides report formatting requirements, the system MUST send the Slack output only in the requested format.
- **FR-012A**: Custom report formatting MAY change headings, ordering, narrative wording, and presentation style, but it MUST NOT suppress mandatory metrics, validation outcome, or required observations.
- **FR-013**: When no custom report format is provided for a single-test run, the system MUST generate a standard Slack report containing Test Summary, Test Execution Summary, and Detailed Observations and Analysis sections.
- **FR-014**: When no custom report format is provided for a two-test comparative run, the system MUST generate a standard Slack report containing Today's Test Results Summary, Test Execution Summary, comparison details against the prior or baseline run set, Detailed Observations and Analysis, and an explicit Recommendation or Conclusion section.
- **FR-015**: The default single-test summary MUST include the executed test identity, test window, key transaction and throughput metrics, response-time metrics, error rate, validation outcome, and narrative observations.
- **FR-016**: The default two-test comparison summary MUST include per-run metrics for both current runs, comparative deltas against the chosen baseline or prior run set when available, highlighted regressions or improvements, and narrative findings that explain operational significance.
- **FR-016A**: For two-test comparisons without an externally supplied baseline, the system MUST treat the first completed run in the request as the comparison baseline for the second run.
- **FR-016B**: The comparison summary MUST classify a regression when throughput decreases by more than 5%, when P95 or P99 response time increases by more than 10%, or when error rate increases by more than 0.50 percentage points between compared runs.
- **FR-017**: The system MUST send the final single-run or comparative report to Slack by using secure runtime configuration for the webhook and MUST avoid storing secret webhook values in repository artifacts.
- **FR-018**: The system MUST treat Teams delivery as optional and out of scope for the initial implementation unless it is explicitly enabled later through configuration.
- **FR-019**: The system MUST maintain logs for orchestration, execution, validation, comparison, and notification activities with sufficient detail for production operations, troubleshooting, and audit review.
- **FR-020**: The system MUST be configuration-driven so that environment paths, execution target selection, notification mode, validation criteria, and operational policies can change without repository code edits for each test.
- **FR-021**: The system MUST stop safely and surface a clear final status when it encounters invalid paths, failed remote startup, unreadable results, incomplete metrics, or notification delivery problems.
- **FR-022**: The system MUST preserve enough run metadata to support repeatable re-execution analysis and future automation of the same workflow.
- **FR-023**: The system MUST expose the configured retry and timeout policy used for execution, validation, and notification steps in run records, even if the initial policy values are finalized later.
- **FR-024**: The default retry policy MUST retry VM-side runner startup once after an initial failure, MUST retry Slack notification delivery up to three times, and MUST avoid automatic re-execution of a completed performance test unless the operator explicitly requests a new run.
- **FR-025**: The default timeout policy MUST fail prerequisite validation after 5 minutes, MUST fail VM-side runner startup after 10 minutes, MUST fail result parsing after 5 minutes, and MUST allow test execution to continue until the declared test duration plus a 15-minute completion buffer has elapsed.
- **FR-026**: The system MUST support optional terminal-first status visibility by allowing operators to watch run state transitions and lifecycle events from the submit side when the submit environment can access the same physical shared-root storage.
- **FR-027**: Any script change MUST pass local PowerShell parse checks and targeted unit tests before commit/push, and the successful validation output MUST be available in terminal history for auditability.
- **FR-028**: The one-terminal VM command (`scripts/Run-OneTerminal.ps1`) MUST send a startup Slack notification by default when notification channel is `slack` or `both`, before submitting and processing the run.

### Key Entities *(include if feature involves data)*

- **Run Request**: The operator-submitted instruction set for one or two tests, including test plan location, execution inputs, target selection, notification preference, and optional report formatting instructions.
- **Run Request**: The operator-submitted instruction set for one or two tests, including test name, environment label, test plan location, execution inputs, target selection, notification preference, expected throughput target when applicable, and optional report formatting instructions.
- **Orchestration Run**: The tracked lifecycle record for a submitted request, including run identity, status transitions, execution target, timestamps, failure classification, and linked artifacts.
- **Artifact Set**: The grouped raw results, logs, and generated report outputs produced by one test run and stored in a traceable folder structure.
- **Validation Result**: The structured outcome of applying response time, throughput, and error rate criteria to one run, including pass or fail status and supporting reasons.
- **Validation Result**: The structured outcome of applying response time, throughput, and error rate criteria to one run, including pass or fail status, threshold checks, target checks when applicable, and supporting reasons.
- **Comparison Summary**: The final analytical result produced when two runs are completed, including per-metric deltas, regression or improvement labels, and detailed observations.
- **Notification Record**: The auditable record of the final report delivery attempt, including channel, payload type, delivery status, failure reason when applicable, and the report structure used.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a controlled production-like environment, operators can complete a valid single-test orchestration from local start to final Slack report without manual intervention in at least 95% of scheduled runs during an agreed evaluation period.
- **SC-002**: For valid two-test requests, 100% of successful workflow completions produce one comparison report that includes independent validation outcomes for both runs and explicit delta-based observations.
- **SC-003**: For invalid inputs or remote startup failures, the workflow halts before sending a misleading success report and presents a classified failure outcome within 5 minutes of detection in 100% of observed cases.
- **SC-004**: For 100% of completed runs, reviewers can trace the final reported outcome back to the originating request, stored artifacts, execution target, and run status history.
- **SC-005**: When custom reporting instructions are supplied, 100% of successful Slack notifications follow only the requested format; when custom instructions are absent, 100% of successful Slack notifications use the standard structured performance summary.
- **SC-006**: For 100% of completed runs without approved threshold overrides, the system evaluates the run against the default thresholds for error rate, P95, P99, and throughput and records the outcome in the final report.
- **SC-007**: For environments where submit and runner share physical shared-root access, operators can observe status transitions (`queued_for_vm_runner`, `running`, terminal state) and emitted lifecycle events from submit-side terminal output in at least 95% of validation runs.
- **SC-008**: For 100% of pushed script-related changes, local verification commands complete successfully before push and no script parse errors are introduced.

## Assumptions

- The initial scope supports one test or two queued tests executed sequentially within a single orchestration request.
- Secure environment configuration is available for required notification secrets and environment-specific settings, and secret values are never committed to repository content.
- The local shared root and VM shared root are available to the workflow before execution begins.
- The operator can log in to the VM, establish VPN connectivity when required, and make the VM-side runner available before triggering orchestration.
- The default validation thresholds defined in this specification are acceptable for the initial release and may be overridden per run or per environment through approved configuration.
- Teams notifications remain out of scope for the first implementation unless explicitly enabled later.
- The workflow is expected to remain suitable for future automation beyond the initial operator-triggered use case.
- Custom Slack formatting for the initial release remains bounded by the requirement to preserve mandatory metrics, validation outcome, and observations.

## Resolved Defaults

- Per-test runtime input defaults are test name, environment label, JMeter test plan path, thread or user count, ramp-up setting, planned duration, and optional expected throughput target.
- Default validation thresholds are error rate less than or equal to 1.00%, P95 less than or equal to 2000 ms, P99 less than or equal to 3000 ms, and throughput greater than zero unless a stricter approved target is supplied.
- Default custom reporting rules allow presentation changes but still require mandatory metrics, validation outcome, and observations in the Slack message.
- Default retry and timeout policy is one retry for VM-side runner startup, up to three retries for Slack delivery, no automatic rerun of a finished test, 5-minute prerequisite and parsing timeouts, 10-minute VM-runner startup timeout, and declared duration plus 15 minutes for execution completion.
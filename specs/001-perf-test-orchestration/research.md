# Research: Remote Performance Test Orchestration

## Key Decisions

### Python for Core Orchestration

- Decision: Use Python as the primary language for config, orchestration, VM-side runner behavior, JMeter parsing, validation, comparison, and report generation.
- Rationale: The workflow is file/process heavy, benefits from standard-library support, and already has initial Python scaffolding in place.

### TypeScript for Slack Notification Delivery

- Decision: Keep TypeScript limited to Slack formatting and delivery scripts.
- Rationale: This satisfies the approved requirement to use TS scripts while isolating notification formatting from orchestration logic.

### Shared-Root Pull Model for VM Execution

- Decision: Use a pull model where the VM-side runner watches a shared-root request folder for new manifests.
- Rationale: The operator starts the VM runner after VPN login, and the local orchestrator can then proceed without direct remote-invocation dependencies.

### File-Based State, No Database

- Decision: Persist all state in run folders, manifests, status files, logs, result artifacts, and report outputs under `PERF_SHARED_ROOT`.
- Rationale: The constitution and spec prohibit introducing a database and require auditability through artifacts.

### Default Validation and Comparison Rules

- Decision: Keep the approved defaults from the spec for error rate, P95, P99, throughput, and regression/improvement classification.
- Rationale: Tasks and implementation should inherit the current accepted thresholds rather than reopen requirements.

## Operational Assumptions

- The operator logs in to the VM and connects VPN before kickoff.
- The VM-side runner is started manually before local orchestration begins.
- Slack webhook values are supplied at runtime through environment variables and are never stored in repo files.

## Risks to Address in Tasks

- Real JMeter invocation may fail due to missing `.bat` path, malformed `.jmx`, or environment-specific execution permissions.
- Shared-root watcher coordination needs safe status transitions to avoid duplicate claims.
- Notification failure must not mask execution or validation failure.
- Parser robustness depends on the exact JMeter CSV fields present in the exported result files.

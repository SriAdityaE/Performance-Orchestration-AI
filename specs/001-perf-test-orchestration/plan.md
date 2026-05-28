# Implementation Plan: Remote Performance Test Orchestration

**Branch**: `[001-perf-test-orchestration]` | **Date**: 2026-05-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-perf-test-orchestration/spec.md`

## Summary

Build a production-grade, file-based performance test orchestration system that starts from the local machine, hands execution to a VM-side runner through the shared root, validates JMeter outputs, compares up to two sequential runs, and sends only the approved Slack lifecycle events plus the final report. Python owns orchestration, VM execution, parsing, validation, comparison, and report generation. TypeScript is limited to Slack notification formatting and delivery. No database is introduced.

## Technical Context

**Language/Version**: Python 3.11+ and TypeScript 5.6

**Primary Dependencies**: Python standard library for v1, pytest for Python tests, TypeScript compiler for Slack notifier build

**Storage**: Files only under `PERF_SHARED_ROOT`; no database

**Testing**: pytest for Python unit/integration tests, direct Python smoke checks, TypeScript compile checks

**Target Platform**: Windows local machine plus Windows VM with VPN connectivity and JMeter installed on the VM

**Project Type**: CLI-driven orchestration tool with VM-side watcher process and supporting notifier script

**Performance Goals**: Complete orchestration flow without manual intervention after VM runner startup; support one or two sequential tests with final validated Slack reporting

**Constraints**: Local-to-VM shared-root handoff, Slack-first delivery, no secret values in repo files, no database, event noise limited to approved lifecycle messages only

**Scale/Scope**: Initial v1 supports one-run and two-run sequential requests, default validation thresholds, default single-run and comparative report structures, and one shared-root watcher model

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Pass: Configuration-driven execution is preserved; machine-specific values are kept in environment variables.
- Pass: Local-to-VM orchestration remains mandatory through the shared-root handoff.
- Pass: Validation occurs before final reporting.
- Pass: Slack remains the primary reporting channel and uses runtime webhook configuration only.
- Pass: No database is introduced; artifacts, status, and logs remain auditable on disk.

## Project Structure

### Documentation (this feature)

```text
specs/001-perf-test-orchestration/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── shared-root-run-contract.md
└── tasks.md
```

### Source Code (repository root)

```text
src/
└── perf_orchestrator/
    ├── cli/
    ├── config.py
    ├── models/
    ├── runner/
    └── services/

tests/
└── unit/

tools/
└── slack-notifier/
    ├── src/
    └── tsconfig.json
```

**Structure Decision**: Use a single Python project for orchestration and execution logic plus a small TypeScript tooling directory for Slack notification scripting. This matches the approved requirement to use Python and TypeScript without splitting the system into separate deployable services.

## Implementation Phases

### Phase 0 - Planning Artifacts

- Capture research decisions, shared-root data model, operator quickstart, and the request/status contract.

### Phase 1 - Foundation Stabilization

- Keep the current Python and TypeScript scaffolding as the baseline.
- Align the formal plan with the implementation already started in the repo.

### Phase 2 - Shared-Root Contract

- Standardize request manifest shape, request-folder and run-folder layout, status transitions, artifact paths, and failure taxonomy.
- Explicitly adopt the pull model: the VM-side runner watches the shared-root request folder for manifests.

### Phase 3 - Local Orchestrator Completion

- Validate prerequisites and build run folders.
- Queue one or two sequential tests.
- Monitor runner status, apply timeouts/retries, and trigger reporting only after real outputs exist.

### Phase 4 - VM Runner Completion

- Watch the shared-root request folder.
- Start JMeter using `JMETER_HOME`.
- Capture stdout/stderr, JTL files, and execution timing metadata.

### Phase 5 - Parsing, Validation, and Comparison

- Parse JMeter CSV outputs.
- Apply thresholds and expected-throughput checks.
- Compare two runs using the first run as baseline when no external baseline exists.

### Phase 6 - Reporting and Notification Integration

- Build final single-run and comparative reports.
- Keep lifecycle Slack events limited to `test started`, `test ended`, `report preparation in progress`, and `final report ready`.
- Compile and invoke the TypeScript notifier artifact.

### Phase 7 - Hardening and Verification

- Add structured logging, failure classification, safe-stop behavior, and integration tests.
- Perform a manual end-to-end rehearsal in the real VM environment.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Separate TypeScript notifier tool | Required to satisfy the approved Python + TS split | Putting all notification logic in Python would ignore the approved tooling direction |

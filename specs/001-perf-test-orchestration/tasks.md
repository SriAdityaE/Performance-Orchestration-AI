# Tasks: Remote Performance Test Orchestration

**Input**: Design documents from `/specs/001-perf-test-orchestration/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: No standalone test-first task set is included because the specification did not require TDD. Validation-focused implementation and quickstart verification are included instead.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Finalize the project manifests and implementation scaffolding used by all stories.

- [x] T001 Finalize Python project metadata and developer dependencies in pyproject.toml
- [x] T002 [P] Finalize TypeScript notifier workspace metadata in package.json
- [x] T003 [P] Finalize Slack notifier compiler configuration in tools/slack-notifier/tsconfig.json

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core shared-root contracts, configuration, status handling, and common services that block all user stories.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T004 Implement configuration loading, thresholds, retry policy, and timeout policy in src/perf_orchestrator/config.py
- [x] T005 [P] Implement shared run request and notification preference deserialization in src/perf_orchestrator/models/run_request.py
- [x] T006 [P] Implement shared metrics, validation, comparison, and lifecycle event models in src/perf_orchestrator/models/results.py and src/perf_orchestrator/models/events.py
- [x] T007 Implement shared-root run folder creation, status persistence, and manifest helpers in src/perf_orchestrator/services/run_layout.py
- [x] T008 Implement Python notifier bridge and terminal fallback in src/perf_orchestrator/services/notifier.py
- [x] T009 Implement local orchestration CLI request loading in src/perf_orchestrator/cli/main.py
- [x] T010 Implement VM-side runner CLI startup and polling loop in src/perf_orchestrator/runner/main.py

**Checkpoint**: Foundation ready - user story implementation can now begin.

---

## Phase 3: User Story 1 - Run and Report a Single Test (Priority: P1) 🎯 MVP

**Goal**: Start a performance test from the local machine, execute it through the VM-side runner, validate the results, and send the approved Slack lifecycle events plus the final single-run report.

**Independent Test**: Submit one valid run request, start the VM runner, confirm the run reaches `completed`, and confirm Slack receives `test started`, `test ended`, `report preparation in progress`, and the final report for one run.

- [x] T011 [US1] Complete local request queueing and top-level status transitions in src/perf_orchestrator/services/orchestrator.py
- [x] T012 [P] [US1] Implement VM-side manifest pickup and JMeter command execution in src/perf_orchestrator/runner/vm_runner.py
- [x] T013 [P] [US1] Implement JMeter CSV result parsing for single-run metrics in src/perf_orchestrator/services/jmeter_parser.py
- [x] T014 [US1] Implement single-run threshold evaluation and pass/fail reasoning in src/perf_orchestrator/services/validator.py
- [x] T015 [US1] Implement default single-run report payload assembly in src/perf_orchestrator/services/report_builder.py
- [x] T016 [US1] Implement approved single-run Slack lifecycle message formatting and delivery in tools/slack-notifier/src/cli.ts

**Checkpoint**: User Story 1 should be fully functional and independently testable.

---

## Phase 4: User Story 2 - Compare Two Sequential Test Runs (Priority: P2)

**Goal**: Accept two queued tests in one request, execute them sequentially, validate both, compare both, and deliver a comparative final report.

**Independent Test**: Submit a two-test request, confirm the second test starts only after the first completes, and confirm the final report includes both runs plus comparative observations.

- [x] T017 [US2] Extend run status and per-test tracking for two sequential runs in src/perf_orchestrator/services/run_layout.py and src/perf_orchestrator/runner/vm_runner.py
- [x] T018 [US2] Implement sequential two-test processing and baseline selection in src/perf_orchestrator/services/orchestrator.py and src/perf_orchestrator/runner/vm_runner.py
- [x] T019 [P] [US2] Implement comparative delta classification and observations in src/perf_orchestrator/services/comparator.py
- [x] T020 [US2] Implement default two-run comparative report assembly in src/perf_orchestrator/services/report_builder.py
- [x] T021 [US2] Persist per-test summaries and final comparative report artifacts in src/perf_orchestrator/runner/vm_runner.py

**Checkpoint**: User Stories 1 and 2 should both work independently.

---

## Phase 5: User Story 3 - Respect Requested Report Format (Priority: P3)

**Goal**: Support custom Slack report formatting while preserving mandatory metrics, validation outcome, and required observations.

**Independent Test**: Submit a valid run request with custom report formatting instructions and confirm the final Slack report follows the requested structure without dropping mandatory content.

- [x] T022 [US3] Implement custom report format handling rules in src/perf_orchestrator/models/run_request.py and src/perf_orchestrator/services/report_builder.py
- [x] T023 [P] [US3] Create single-run Slack formatter module in tools/slack-notifier/src/formatters/singleRun.ts
- [x] T024 [P] [US3] Create comparative Slack formatter module in tools/slack-notifier/src/formatters/comparison.ts
- [x] T025 [US3] Wire custom-versus-default payload selection into the notifier flow in src/perf_orchestrator/services/notifier.py and tools/slack-notifier/src/cli.ts

**Checkpoint**: All user stories should now be independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Harden production behavior and align docs with the implemented flow.

- [x] T026 [P] Implement structured logging and failure classification across src/perf_orchestrator/services/orchestrator.py, src/perf_orchestrator/runner/vm_runner.py, src/perf_orchestrator/services/jmeter_parser.py, and src/perf_orchestrator/services/notifier.py
- [x] T027 Implement retry and timeout enforcement in src/perf_orchestrator/config.py, src/perf_orchestrator/services/orchestrator.py, and src/perf_orchestrator/runner/vm_runner.py
- [x] T028 [P] Update operator flow and command usage in specs/001-perf-test-orchestration/quickstart.md
- [x] T029 [P] Align the shared-root contract with final implementation details in specs/001-perf-test-orchestration/contracts/shared-root-run-contract.md
- [x] T030 Validate the end-to-end operator flow described in specs/001-perf-test-orchestration/quickstart.md
- [x] T031 Remove duplicate `test_started` preflight notification from the one-terminal workflow in scripts/Run-OneTerminal.ps1
- [x] T032 Fix Slack final report delivery to send real block payloads and include JMeter aggregate rows in tools/slack-notifier/src/cli.ts and tools/slack-notifier/src/formatters/singleRun.ts
- [x] T033 Fix single-run final report presentation to preserve transaction-level labels, suppress parent controller labels when child rows exist, and show target-miss as a distinct status in src/perf_orchestrator/runner/vm_runner.py, src/perf_orchestrator/services/report_builder.py, and tools/slack-notifier/src/formatters/singleRun.ts
- [x] T034 Add email-ready subject/intro at the top and simple closing signature for single-run and two-run final Slack reports, and harden two-run labeling for duplicate test names in tools/slack-notifier/src/formatters/singleRun.ts, tools/slack-notifier/src/formatters/comparison.ts, tools/slack-notifier/src/cli.ts, and src/perf_orchestrator/runner/vm_runner.py
- [x] T035 Remove Senior Architect review narrative block from single-run and two-run Slack report formatters in tools/slack-notifier/src/formatters/singleRun.ts and tools/slack-notifier/src/formatters/comparison.ts

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion - blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational completion.
- **User Story 2 (Phase 4)**: Depends on User Story 1 execution flow being complete enough to reuse for sequential comparison.
- **User Story 3 (Phase 5)**: Depends on User Story 1 reporting flow and TypeScript notifier path.
- **Polish (Phase 6)**: Depends on all desired user stories being complete.

### User Story Dependencies

- **User Story 1 (P1)**: Starts after Phase 2 and establishes the MVP.
- **User Story 2 (P2)**: Builds on the single-run execution and reporting path from User Story 1.
- **User Story 3 (P3)**: Builds on the existing reporting path from User Stories 1 and 2.

### Within Each User Story

- Shared contracts before runtime wiring.
- Execution before validation.
- Validation before final report delivery.
- Default report flow before custom formatting.

### Parallel Opportunities

- T002 and T003 can run in parallel.
- T005 and T006 can run in parallel.
- T012 and T013 can run in parallel once the foundational contract is complete.
- T019 can run in parallel with T020 after two-run sequencing is defined.
- T023 and T024 can run in parallel.
- T026, T028, and T029 can run in parallel during polish.

---

## Parallel Example: User Story 1

```text
T012 [US1] Implement VM-side manifest pickup and JMeter command execution in src/perf_orchestrator/runner/vm_runner.py
T013 [US1] Implement JMeter CSV result parsing for single-run metrics in src/perf_orchestrator/services/jmeter_parser.py
```

---

## Parallel Example: User Story 3

```text
T023 [US3] Create single-run Slack formatter module in tools/slack-notifier/src/formatters/singleRun.ts
T024 [US3] Create comparative Slack formatter module in tools/slack-notifier/src/formatters/comparison.ts
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational.
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: Run the quickstart single-run flow independently.

### Incremental Delivery

1. Complete Setup + Foundational.
2. Deliver User Story 1 as the single-run MVP.
3. Add User Story 2 for sequential comparison.
4. Add User Story 3 for custom report formatting.
5. Finish with polish and end-to-end quickstart validation.

### Parallel Team Strategy

With multiple developers:

1. Complete Setup + Foundational together.
2. Then split by slices:
   - Developer A: Local/VM orchestration flow.
   - Developer B: Parsing, validation, and comparison.
   - Developer C: TypeScript notifier and documentation alignment.

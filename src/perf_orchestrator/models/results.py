from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AggregateRow:
    label: str
    samples: int
    average_ms: float
    median_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    error_pct: float
    throughput_per_sec: float


@dataclass(frozen=True)
class TestMetrics:
    transactions: int
    throughput: float
    avg_response_ms: float
    p95_response_ms: float
    p99_response_ms: float
    max_response_ms: float
    error_rate_pct: float
    duration_minutes: int
    aggregate_rows: tuple[AggregateRow, ...] = ()
    transaction_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    reasons: tuple[str, ...] = ()
    threshold_checks: dict[str, bool] = field(default_factory=dict)
    target_checks: dict[str, bool] = field(default_factory=dict)


@dataclass(frozen=True)
class ComparisonDelta:
    metric_name: str
    baseline_value: float
    candidate_value: float
    delta_pct: float
    classification: str


@dataclass(frozen=True)
class ComparisonSummary:
    baseline_label: str
    candidate_label: str
    deltas: tuple[ComparisonDelta, ...]
    observations: tuple[str, ...]
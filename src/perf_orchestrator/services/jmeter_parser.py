from __future__ import annotations

import csv
import logging
from pathlib import Path

from perf_orchestrator.models.results import AggregateRow, TestMetrics


class JMeterParseError(ValueError):
    """Raised when a JMeter result file cannot be parsed into metrics."""


def parse_jmeter_csv(result_file: Path, planned_duration_minutes: int) -> TestMetrics:
    logger = logging.getLogger(__name__)
    if not result_file.exists():
        raise JMeterParseError(f"JMeter result file not found: {result_file}")

    elapsed_values: list[float] = []
    success_values: list[bool] = []
    timestamps: list[int] = []
    aggregate_bucket: dict[str, dict[str, list[float] | int]] = {}
    label_order: list[str] = []

    with result_file.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if "elapsed" not in row or "success" not in row:
                raise JMeterParseError("JMeter CSV must include 'elapsed' and 'success' columns")
            elapsed = float(row["elapsed"] or 0)
            success = str(row["success"]).strip().lower() == "true"
            elapsed_values.append(elapsed)
            success_values.append(success)

            label = str(row.get("label") or "UNNAMED").strip() or "UNNAMED"
            if label not in aggregate_bucket:
                aggregate_bucket[label] = {"elapsed": [], "success_count": 0}
                label_order.append(label)
            aggregate_bucket[label]["elapsed"].append(elapsed)  # type: ignore[index]
            if success:
                aggregate_bucket[label]["success_count"] = int(aggregate_bucket[label]["success_count"]) + 1

            if row.get("timeStamp"):
                timestamps.append(int(float(row["timeStamp"])))

    if not elapsed_values:
        raise JMeterParseError("JMeter result file does not contain any samples")

    elapsed_sorted = sorted(elapsed_values)
    sample_count = len(elapsed_sorted)
    error_count = sum(1 for item in success_values if not item)
    actual_duration_seconds = planned_duration_minutes * 60
    if len(timestamps) >= 2:
        actual_duration_seconds = max((max(timestamps) - min(timestamps)) / 1000, 1)

    aggregate_rows = _build_aggregate_rows(
        elapsed_values=elapsed_values,
        success_values=success_values,
        aggregate_bucket=aggregate_bucket,
        label_order=label_order,
        actual_duration_seconds=actual_duration_seconds,
    )

    metrics = TestMetrics(
        transactions=sample_count,
        throughput=sample_count / actual_duration_seconds,
        avg_response_ms=sum(elapsed_sorted) / sample_count,
        p95_response_ms=_percentile(elapsed_sorted, 0.95),
        p99_response_ms=_percentile(elapsed_sorted, 0.99),
        max_response_ms=max(elapsed_sorted),
        error_rate_pct=(error_count / sample_count) * 100,
        duration_minutes=planned_duration_minutes,
        aggregate_rows=tuple(aggregate_rows),
        transaction_names=tuple(label_order),
    )
    logger.info("Parsed JMeter CSV metrics", extra={"samples": sample_count, "path": str(result_file)})
    return metrics


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    rank = max(0, min(len(values) - 1, int(round(percentile * (len(values) - 1)))))
    return values[rank]


def _build_aggregate_rows(
    *,
    elapsed_values: list[float],
    success_values: list[bool],
    aggregate_bucket: dict[str, dict[str, list[float] | int]],
    label_order: list[str],
    actual_duration_seconds: float,
) -> list[AggregateRow]:
    rows: list[AggregateRow] = []

    for label in label_order:
        bucket = aggregate_bucket[label]
        values = sorted(bucket["elapsed"])  # type: ignore[index]
        sample_count = len(values)
        success_count = int(bucket["success_count"])
        error_count = sample_count - success_count

        rows.append(
            AggregateRow(
                label=label,
                samples=sample_count,
                average_ms=sum(values) / sample_count,
                median_ms=_percentile(values, 0.50),
                p90_ms=_percentile(values, 0.90),
                p95_ms=_percentile(values, 0.95),
                p99_ms=_percentile(values, 0.99),
                min_ms=min(values),
                max_ms=max(values),
                error_pct=(error_count / sample_count) * 100,
                throughput_per_sec=sample_count / actual_duration_seconds,
            )
        )

    total_values = sorted(elapsed_values)
    total_samples = len(total_values)
    total_error_count = sum(1 for item in success_values if not item)
    rows.append(
        AggregateRow(
            label="TOTAL",
            samples=total_samples,
            average_ms=sum(total_values) / total_samples,
            median_ms=_percentile(total_values, 0.50),
            p90_ms=_percentile(total_values, 0.90),
            p95_ms=_percentile(total_values, 0.95),
            p99_ms=_percentile(total_values, 0.99),
            min_ms=min(total_values),
            max_ms=max(total_values),
            error_pct=(total_error_count / total_samples) * 100,
            throughput_per_sec=total_samples / actual_duration_seconds,
        )
    )

    return rows
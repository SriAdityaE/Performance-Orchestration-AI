from __future__ import annotations

import csv
import logging
from pathlib import Path

from perf_orchestrator.models.results import TestMetrics


class JMeterParseError(ValueError):
    """Raised when a JMeter result file cannot be parsed into metrics."""


def parse_jmeter_csv(result_file: Path, planned_duration_minutes: int) -> TestMetrics:
    logger = logging.getLogger(__name__)
    if not result_file.exists():
        raise JMeterParseError(f"JMeter result file not found: {result_file}")

    elapsed_values: list[float] = []
    success_values: list[bool] = []
    timestamps: list[int] = []

    with result_file.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if "elapsed" not in row or "success" not in row:
                raise JMeterParseError("JMeter CSV must include 'elapsed' and 'success' columns")
            elapsed_values.append(float(row["elapsed"] or 0))
            success_values.append(str(row["success"]).strip().lower() == "true")
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

    metrics = TestMetrics(
        transactions=sample_count,
        throughput=sample_count / actual_duration_seconds,
        avg_response_ms=sum(elapsed_sorted) / sample_count,
        p95_response_ms=_percentile(elapsed_sorted, 0.95),
        p99_response_ms=_percentile(elapsed_sorted, 0.99),
        max_response_ms=max(elapsed_sorted),
        error_rate_pct=(error_count / sample_count) * 100,
        duration_minutes=planned_duration_minutes,
    )
    logger.info("Parsed JMeter CSV metrics", extra={"samples": sample_count, "path": str(result_file)})
    return metrics


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    rank = max(0, min(len(values) - 1, int(round(percentile * (len(values) - 1)))))
    return values[rank]
#!/usr/bin/env python3
"""Fail CI when ASR evaluator metrics violate configured safety thresholds."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_THRESHOLDS = {
    "normalized_wer_max": 0.18,
    "negation_accuracy_min": 0.98,
    "critical_name_accuracy_min": 0.95,
}


def load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def check(metrics: dict[str, Any], thresholds: dict[str, float] | None = None) -> list[str]:
    limits = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    values = metrics["metrics"]
    failures: list[str] = []
    wer = float(values["normalized_wer"]["wer"])
    negation = float(values["negation_accuracy"]["accuracy"])
    names = float(values["critical_name_accuracy"]["accuracy"])
    if wer > limits["normalized_wer_max"]:
        failures.append(f"normalized WER {wer:.4f} exceeds maximum {limits['normalized_wer_max']:.4f}")
    if negation < limits["negation_accuracy_min"]:
        failures.append(f"negation accuracy {negation:.4f} is below minimum {limits['negation_accuracy_min']:.4f}")
    if names < limits["critical_name_accuracy_min"]:
        failures.append(f"critical-name accuracy {names:.4f} is below minimum {limits['critical_name_accuracy_min']:.4f}")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metrics", type=Path)
    parser.add_argument("--thresholds", type=Path)
    args = parser.parse_args()
    thresholds = load(args.thresholds) if args.thresholds else None
    metrics = load(args.metrics)
    failures = check(metrics, thresholds)
    if failures:
        print("ASR evaluator threshold check: FAIL")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)
    print("ASR evaluator threshold check: PASS")
    values = metrics["metrics"]
    print(f"- normalized WER: {values['normalized_wer']['wer']:.4f}")
    print(f"- negation accuracy: {values['negation_accuracy']['accuracy']:.4f}")
    print(f"- critical-name accuracy: {values['critical_name_accuracy']['accuracy']:.4f}")


if __name__ == "__main__":
    main()

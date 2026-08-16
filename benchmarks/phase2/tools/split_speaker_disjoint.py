#!/usr/bin/env python3
"""Create deterministic, speaker-disjoint Bayenat benchmark splits.

Input: a JSON manifest with a top-level ``recordings`` array.
Output: a JSON manifest with a ``split`` field on each eligible recording.

The algorithm uses a seeded greedy assignment. Speakers are indivisible units;
recordings from one speaker can never cross split boundaries. Assignment is
ordered by descending speaker duration and then stable speaker ID, which makes
results reproducible for the same input, seed, and split configuration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

DEFAULT_SPLITS = {"development": 0.20, "calibration": 0.20, "test": 0.30, "challenge": 0.30}


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest.get("recordings"), list):
        raise ValueError("manifest.recordings must be a list")
    return manifest


def stable_rank(speaker_id: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{speaker_id}".encode("utf-8")).hexdigest()


def assign_speakers(recordings: list[dict[str, Any]], seed: int, ratios: dict[str, float]) -> dict[str, str]:
    speaker_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in recordings:
        if row.get("split_eligibility", {}).get("eligible", True):
            speaker_rows[row["speaker_id"]].append(row)
    if not speaker_rows:
        raise ValueError("no eligible recordings available for splitting")

    total_ms = sum(int(row["audio"]["duration_ms"]) for rows in speaker_rows.values() for row in rows)
    targets = {name: total_ms * ratio for name, ratio in ratios.items()}
    assigned_duration = {name: 0 for name in ratios}
    assigned: dict[str, str] = {}

    ordered_speakers = sorted(
        speaker_rows,
        key=lambda speaker: (-sum(int(row["audio"]["duration_ms"]) for row in speaker_rows[speaker]), stable_rank(speaker, seed)),
    )
    split_order = list(ratios)
    for speaker_id in ordered_speakers:
        duration = sum(int(row["audio"]["duration_ms"]) for row in speaker_rows[speaker_id])
        chosen = min(
            split_order,
            key=lambda split: (assigned_duration[split] / targets[split], stable_rank(f"{split}:{speaker_id}", seed)),
        )
        assigned[speaker_id] = chosen
        assigned_duration[chosen] += duration

    return assigned


def split_manifest(manifest: dict[str, Any], seed: int, ratios: dict[str, float]) -> dict[str, Any]:
    if abs(sum(ratios.values()) - 1.0) > 1e-9:
        raise ValueError("split ratios must sum to 1.0")
    assignments = assign_speakers(manifest["recordings"], seed, ratios)
    output = dict(manifest)
    output["split_seed"] = seed
    output["split_ratios"] = ratios
    output["recordings"] = []
    for original in manifest["recordings"]:
        row = dict(original)
        if row.get("split_eligibility", {}).get("eligible", True):
            row["split"] = assignments[row["speaker_id"]]
        else:
            row["split"] = "excluded"
        output["recordings"].append(row)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", type=int, default=20260816)
    args = parser.parse_args()
    manifest = load_manifest(args.input)
    result = split_manifest(manifest, args.seed, DEFAULT_SPLITS)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    main()

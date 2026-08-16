#!/usr/bin/env python3
"""Validate Bayenat Phase 2 manifest invariants without external dependencies."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ALLOWED_SPLITS = {"development", "calibration", "test", "challenge", "excluded"}


def validate(manifest: dict[str, Any], consent_ids: set[str] | None = None) -> list[str]:
    errors: list[str] = []
    recordings = manifest.get("recordings")
    if not isinstance(recordings, list) or not recordings:
        return ["recordings must be a non-empty list"]

    seen_recordings: set[str] = set()
    speaker_splits: dict[str, set[str]] = defaultdict(set)
    for index, row in enumerate(recordings):
        prefix = f"recordings[{index}]"
        required = ["recording_id", "speaker_id", "consent_id", "rights_status", "audio", "annotation"]
        for field in required:
            if field not in row:
                errors.append(f"{prefix} missing {field}")
        recording_id = row.get("recording_id")
        if recording_id in seen_recordings:
            errors.append(f"{prefix} duplicate recording_id {recording_id}")
        seen_recordings.add(recording_id)
        if row.get("rights_status") != "AUTHORIZED_PRIVATE":
            errors.append(f"{prefix} rights_status must be AUTHORIZED_PRIVATE for the pilot")
        consent_id = row.get("consent_id")
        if consent_ids is not None and consent_id not in consent_ids:
            errors.append(f"{prefix} references unknown consent_id {consent_id}")
        audio = row.get("audio", {})
        if not isinstance(audio.get("duration_ms"), int) or audio.get("duration_ms", 0) < 1000:
            errors.append(f"{prefix} audio.duration_ms must be an integer >= 1000")
        if not isinstance(audio.get("sha256"), str) or len(audio.get("sha256", "")) != 64:
            errors.append(f"{prefix} audio.sha256 must be a 64-character SHA-256 hex digest")
        annotation = row.get("annotation", {})
        if annotation.get("adjudicated") is not True:
            errors.append(f"{prefix} annotation.adjudicated must be true before official evaluation")
        if annotation.get("critical_token_reviewed") is not True:
            errors.append(f"{prefix} annotation.critical_token_reviewed must be true")
        split = row.get("split")
        if split is not None:
            if split not in ALLOWED_SPLITS:
                errors.append(f"{prefix} invalid split {split}")
            if split != "excluded":
                speaker_splits[row.get("speaker_id")].add(split)

    for speaker_id, splits in speaker_splits.items():
        if len(splits) > 1:
            errors.append(f"speaker {speaker_id} appears in multiple splits: {sorted(splits)}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    with args.manifest.open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    errors = validate(manifest)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print("manifest valid")


if __name__ == "__main__":
    main()

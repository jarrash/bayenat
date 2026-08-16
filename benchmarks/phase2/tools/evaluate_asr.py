#!/usr/bin/env python3
"""Evaluate Bayenat ASR output against a reference manifest.

The evaluator expects a manifest whose recordings point to reference transcript
JSON files through ``annotation.reference_transcript_path``. Each reference
transcript has this shape:

{
  "recording_id": "rec_001",
  "text": "...",
  "critical_items": [
    {"item_id": "neg_001", "type": "NEGATION", "reference_text": "...",
     "required_tokens": ["لم"], "forbidden_tokens": ["تم"]},
    {"item_id": "name_001", "type": "NAME", "reference_text": "شركة بيان"}
  ]
}

The evaluation output JSON has this shape:

{
  "engine": {"name": "faster-whisper", "model_family": "whisper", "model": "large-v3"},
  "recordings": [{"recording_id": "rec_001", "text": "...", "critical_items": {"neg_001": "...", "name_001": "..."}}]
}

Critical-item hypotheses are optional. When absent, the full hypothesis text is
used for matching. The result is JSON suitable for CI artifacts and reports.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
PUNCTUATION = re.compile(r"[^\w\u0600-\u06FF]+", re.UNICODE)
DIGIT_TRANSLATION = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
CHARACTER_TRANSLATION = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي"})


@dataclass(frozen=True)
class Metric:
    correct: int
    total: int
    accuracy: float


@dataclass(frozen=True)
class WERResult:
    substitutions: int
    deletions: int
    insertions: int
    reference_words: int
    errors: int
    wer: float


def normalize_arabic(text: str) -> str:
    """Normalize only comparison-safe variants; preserve negation and grammar."""
    value = unicodedata.normalize("NFKC", text or "")
    value = value.translate(DIGIT_TRANSLATION).translate(CHARACTER_TRANSLATION)
    value = value.replace("ـ", "")
    value = ARABIC_DIACRITICS.sub("", value)
    value = PUNCTUATION.sub(" ", value)
    return " ".join(value.split()).strip()


def tokens(text: str) -> list[str]:
    normalized = normalize_arabic(text)
    return normalized.split() if normalized else []


def normalized_wer(reference: str, hypothesis: str) -> WERResult:
    """Compute word error rate using Levenshtein alignment on normalized words."""
    ref = tokens(reference)
    hyp = tokens(hypothesis)
    rows = len(ref) + 1
    cols = len(hyp) + 1
    costs = [[0] * cols for _ in range(rows)]
    ops: list[list[str | None]] = [[None] * cols for _ in range(rows)]
    for i in range(1, rows):
        costs[i][0] = i
        ops[i][0] = "D"
    for j in range(1, cols):
        costs[0][j] = j
        ops[0][j] = "I"
    for i in range(1, rows):
        for j in range(1, cols):
            if ref[i - 1] == hyp[j - 1]:
                costs[i][j] = costs[i - 1][j - 1]
                ops[i][j] = "C"
                continue
            choices = [
                (costs[i - 1][j - 1] + 1, "S"),
                (costs[i - 1][j] + 1, "D"),
                (costs[i][j - 1] + 1, "I"),
            ]
            costs[i][j], ops[i][j] = min(choices, key=lambda item: (item[0], {"S": 0, "D": 1, "I": 2}[item[1]]))

    substitutions = deletions = insertions = 0
    i, j = len(ref), len(hyp)
    while i or j:
        operation = ops[i][j]
        if operation == "C":
            i -= 1
            j -= 1
        elif operation == "S":
            substitutions += 1
            i -= 1
            j -= 1
        elif operation == "D":
            deletions += 1
            i -= 1
        elif operation == "I":
            insertions += 1
            j -= 1
        else:
            raise RuntimeError(f"invalid alignment state at {i},{j}")
    errors = substitutions + deletions + insertions
    return WERResult(substitutions, deletions, insertions, len(ref), errors, errors / len(ref) if ref else (0.0 if not hyp else 1.0))


def contains_phrase(haystack: list[str], phrase: list[str]) -> bool:
    if not phrase:
        return False
    width = len(phrase)
    return any(haystack[i : i + width] == phrase for i in range(len(haystack) - width + 1))


def score_negation(reference_item: dict[str, Any], hypothesis: str) -> bool:
    hypothesis_tokens = tokens(hypothesis)
    required = [normalize_arabic(value) for value in reference_item.get("required_tokens", [])]
    forbidden = [normalize_arabic(value) for value in reference_item.get("forbidden_tokens", [])]
    required_ok = all(token in hypothesis_tokens for token in required)
    forbidden_ok = all(token not in hypothesis_tokens for token in forbidden)
    return required_ok and forbidden_ok


def score_name(reference_item: dict[str, Any], hypothesis: str) -> bool:
    expected = tokens(reference_item.get("reference_text", ""))
    return contains_phrase(tokens(hypothesis), expected)


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def evaluate(manifest: dict[str, Any], evaluation: dict[str, Any], root: Path) -> dict[str, Any]:
    hypotheses = {row["recording_id"]: row for row in evaluation.get("recordings", [])}
    reference_rows = {row["recording_id"]: row for row in manifest.get("recordings", []) if row.get("split") not in {"excluded"}}
    missing = sorted(set(reference_rows) - set(hypotheses))
    if missing:
        raise ValueError(f"evaluation output is missing recording IDs: {', '.join(missing)}")

    wer_results: list[WERResult] = []
    negation_results: list[dict[str, Any]] = []
    name_results: list[dict[str, Any]] = []
    per_recording: list[dict[str, Any]] = []
    for recording_id, manifest_row in reference_rows.items():
        reference_path = root / manifest_row["annotation"]["reference_transcript_path"]
        reference = load_json(reference_path)
        hypothesis_row = hypotheses[recording_id]
        hypothesis_text = hypothesis_row.get("text", "")
        wer = normalized_wer(reference.get("text", ""), hypothesis_text)
        wer_results.append(wer)
        item_hypotheses = hypothesis_row.get("critical_items", {})
        for item in reference.get("critical_items", []):
            item_id = item["item_id"]
            item_hypothesis = item_hypotheses.get(item_id, hypothesis_text)
            item_type = item.get("type")
            if item_type == "NEGATION":
                correct = score_negation(item, item_hypothesis)
                negation_results.append({"recording_id": recording_id, "item_id": item_id, "correct": correct})
            elif item_type == "NAME":
                correct = score_name(item, item_hypothesis)
                name_results.append({"recording_id": recording_id, "item_id": item_id, "correct": correct})
        per_recording.append({"recording_id": recording_id, "normalized_wer": asdict(wer)})

    def aggregate(items: list[dict[str, Any]]) -> Metric:
        correct = sum(1 for item in items if item["correct"])
        total = len(items)
        return Metric(correct, total, correct / total if total else 0.0)

    total_reference_words = sum(item.reference_words for item in wer_results)
    total_errors = sum(item.errors for item in wer_results)
    aggregate_wer = total_errors / total_reference_words if total_reference_words else 0.0
    return {
        "engine": evaluation.get("engine", {}),
        "corpus_id": manifest.get("corpus_id"),
        "corpus_version": manifest.get("corpus_version"),
        "metrics": {
            "normalized_wer": {"errors": total_errors, "reference_words": total_reference_words, "wer": aggregate_wer},
            "negation_accuracy": asdict(aggregate(negation_results)),
            "critical_name_accuracy": asdict(aggregate(name_results)),
        },
        "per_recording": per_recording,
        "items": {"negation": negation_results, "critical_name": name_results},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("."), help="Root used to resolve reference_transcript_path")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(load_json(args.manifest), load_json(args.evaluation), args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps(result["metrics"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

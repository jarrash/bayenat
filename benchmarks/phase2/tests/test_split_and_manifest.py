from pathlib import Path
import sys

TOOLS = Path(__file__).parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from split_speaker_disjoint import split_manifest  # noqa: E402
from validate_manifest import validate  # noqa: E402


def recording(recording_id: str, speaker_id: str, duration_ms: int) -> dict:
    return {
        "recording_id": recording_id,
        "speaker_id": speaker_id,
        "consent_id": f"cons_{speaker_id}",
        "rights_status": "AUTHORIZED_PRIVATE",
        "audio": {
            "relative_path": f"audio/{recording_id}.wav",
            "sha256": "a" * 64,
            "duration_ms": duration_ms,
            "sample_rate_hz": 16000,
            "channels": 1,
            "capture_condition": "CLEAN_CLOSE_MIC",
        },
        "language": "ar",
        "dialect": "SAUDI_GULF",
        "speaker": {"age_band": "30_44", "gender_self_reported": "WITHHELD", "dialect_basis": "SELF_REPORTED"},
        "scenario": {"register": "CONVERSATIONAL", "content_tags": [], "prompt_id": "prompt_001"},
        "annotation": {
            "reference_transcript_path": f"annotations/{recording_id}.json",
            "normalized_transcript_path": f"annotations/{recording_id}.normalized.json",
            "annotator_ids": ["ann_1", "ann_2"],
            "adjudicated": True,
            "critical_token_reviewed": True,
        },
        "split_eligibility": {"eligible": True, "exclusion_reasons": []},
    }


def test_split_is_deterministic_and_speaker_disjoint():
    manifest = {"manifest_version": "1.0.0", "corpus_id": "pilot", "corpus_version": "v0.1.0", "recordings": [
        recording("r1", "s1", 120000), recording("r2", "s1", 90000), recording("r3", "s2", 100000),
        recording("r4", "s3", 80000), recording("r5", "s4", 70000), recording("r6", "s5", 60000),
    ]}
    first = split_manifest(manifest, 7, {"development": .2, "calibration": .2, "test": .3, "challenge": .3})
    second = split_manifest(manifest, 7, {"development": .2, "calibration": .2, "test": .3, "challenge": .3})
    assert first == second
    by_speaker = {}
    for row in first["recordings"]:
        by_speaker.setdefault(row["speaker_id"], set()).add(row["split"])
    assert all(len(splits) == 1 for splits in by_speaker.values())


def test_validator_rejects_cross_split_speaker():
    manifest = {"recordings": [recording("r1", "s1", 1000), recording("r2", "s1", 1000)]}
    manifest["recordings"][0]["split"] = "test"
    manifest["recordings"][1]["split"] = "challenge"
    errors = validate(manifest, {"cons_s1"})
    assert any("multiple splits" in error for error in errors)

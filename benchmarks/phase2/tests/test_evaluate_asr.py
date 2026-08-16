from pathlib import Path
import json
import sys

TOOLS = Path(__file__).parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from evaluate_asr import evaluate, normalize_arabic, normalized_wer  # noqa: E402


def test_normalization_is_conservative_for_meaning():
    assert normalize_arabic("إحالةٌ ــ إلى ١٥") == "احالة الي 15"
    assert normalize_arabic("لم يتم") != normalize_arabic("تم")


def test_normalized_wer_uses_micro_aggregation():
    first = normalized_wer("هذا اختبار", "هذا")
    second = normalized_wer("كلمة", "كلمة إضافية")
    assert first.errors == 1
    assert second.errors == 1
    assert (first.errors + second.errors) / (first.reference_words + second.reference_words) == 2 / 3


def test_evaluate_scores_negation_and_name(tmp_path):
    reference_dir = tmp_path / "annotations"
    reference_dir.mkdir()
    reference = {
        "recording_id": "rec_1",
        "text": "لم يتم تسليم شركة بيان في ١٥ مايو",
        "critical_items": [
            {"item_id": "neg_1", "type": "NEGATION", "reference_text": "لم يتم", "required_tokens": ["لم"], "forbidden_tokens": ["تم"]},
            {"item_id": "name_1", "type": "NAME", "reference_text": "شركة بيان"},
        ],
    }
    (reference_dir / "rec_1.json").write_text(json.dumps(reference, ensure_ascii=False), encoding="utf-8")
    manifest = {"corpus_id": "pilot", "corpus_version": "v0.1.0", "recordings": [{
        "recording_id": "rec_1", "split": "test", "annotation": {"reference_transcript_path": "annotations/rec_1.json"}
    }]}
    evaluation = {"engine": {"name": "test"}, "recordings": [{
        "recording_id": "rec_1", "text": "لم يتم تسليم شركة بيان في 15 مايو"
    }]}
    result = evaluate(manifest, evaluation, tmp_path)
    assert result["metrics"]["normalized_wer"]["wer"] == 0.0
    assert result["metrics"]["negation_accuracy"]["accuracy"] == 1.0
    assert result["metrics"]["critical_name_accuracy"]["accuracy"] == 1.0


def test_negation_conflict_is_not_hidden_by_other_words(tmp_path):
    reference_dir = tmp_path / "annotations"
    reference_dir.mkdir()
    (reference_dir / "rec_1.json").write_text(json.dumps({
        "recording_id": "rec_1", "text": "لم يتم تسليم النظام",
        "critical_items": [{"item_id": "neg_1", "type": "NEGATION", "reference_text": "لم يتم", "required_tokens": ["لم"], "forbidden_tokens": ["تم"]}],
    }, ensure_ascii=False), encoding="utf-8")
    manifest = {"corpus_id": "pilot", "corpus_version": "v0.1.0", "recordings": [{"recording_id": "rec_1", "annotation": {"reference_transcript_path": "annotations/rec_1.json"}}]}
    evaluation = {"recordings": [{"recording_id": "rec_1", "text": "تم تسليم النظام"}]}
    result = evaluate(manifest, evaluation, tmp_path)
    assert result["metrics"]["negation_accuracy"]["correct"] == 0

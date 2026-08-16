from pathlib import Path
from types import SimpleNamespace

import pytest

from app.engines.faster_whisper import FasterWhisperEngine


class FakeModel:
    def __init__(self):
        self.calls = []

    def transcribe(self, audio_path: str, **kwargs):
        self.calls.append((audio_path, kwargs))
        segments = [
            SimpleNamespace(
                start=1.25,
                end=3.5,
                text=" السلام عليكم ",
                avg_logprob=-0.1,
                words=[
                    SimpleNamespace(word="السلام", start=1.25, end=2.1, probability=0.97),
                    SimpleNamespace(word="عليكم", start=2.1, end=3.5, probability=0.95),
                ],
            )
        ]
        info = SimpleNamespace(duration=3.5, language="ar", language_probability=0.99)
        return iter(segments), info


def test_faster_whisper_adapter_returns_common_result(tmp_path: Path):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"RIFF")
    fake_model = FakeModel()
    engine = FasterWhisperEngine(
        model_name="small",
        device="cpu",
        compute_type="int8",
        language="ar",
        model=fake_model,
    )

    result = engine.transcribe(audio)

    assert result.text == "السلام عليكم"
    assert result.duration_ms == 3500
    assert result.segments[0].start_ms == 1250
    assert result.segments[0].end_ms == 3500
    assert result.segments[0].confidence == pytest.approx(0.9048, rel=1e-3)
    assert result.segments[0].words[0].start_ms == 1250
    assert result.segments[0].words[1].confidence == pytest.approx(0.95)
    assert result.engine_metadata.engine == "faster-whisper"
    assert result.engine_metadata.model_family == "whisper"
    assert result.engine_metadata.model_name == "small"
    assert result.engine_metadata.implementation == "ctranslate2"
    assert fake_model.calls[0][1]["language"] == "ar"
    assert fake_model.calls[0][1]["word_timestamps"] is True


def test_explicit_language_is_recorded_in_metadata(tmp_path: Path):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"RIFF")
    engine = FasterWhisperEngine(model=FakeModel(), language=None)
    result = engine.transcribe(audio, language="ar-en")
    assert result.engine_metadata.language == "ar-en"


def test_missing_audio_fails_before_model_call(tmp_path: Path):
    fake_model = FakeModel()
    engine = FasterWhisperEngine(model=fake_model)
    with pytest.raises(FileNotFoundError):
        engine.transcribe(tmp_path / "missing.wav")
    assert fake_model.calls == []

# Bayenat STT Engines

## Contract

All speech-to-text engines implement the `STTEngine` protocol in `backend/app/engines/base.py`. An engine accepts an audio path and optional language, then returns a `TranscriptionResult` containing typed segments, optional word timestamps, confidence values where available, and engine metadata.

The metadata records engine name, model family, model name and version, implementation, language, device, compute type, decoding parameters, library version, Python version, CUDA version when available, and configuration version. Model-family metadata is required because two implementations may share the same underlying model family and must not be treated as statistically independent votes by the future consensus layer.

## Faster-Whisper adapter

`backend/app/engines/faster_whisper.py` provides the local `FasterWhisperEngine`. The `faster-whisper` package is optional and is listed in `backend/requirements-speech.txt`, not the lightweight base requirements used by CI. The adapter lazily imports the package and constructs the model only on first use. Tests inject a compatible fake model, so normal tests never download model weights.

Example local setup:

```bash
sudo pip3 install -r backend/requirements-speech.txt
export BAYENAT_STT_MODEL_NAME=large-v3
```

The current adapter exposes constructor configuration for model name, device, compute type, language, beam size, VAD filtering, word timestamps, previous-text conditioning, download root, and configuration version. It preserves the detected language separately from the requested language and converts seconds to integer millisecond coordinates.

## Confidence limitation

Faster-Whisper exposes average log probability and word probabilities when available. Bayenat maps average log probability to a bounded segment-level indicator for display and downstream analysis, but this is not a calibrated probability of transcript correctness. The confidence model must later be evaluated against the authorized pilot corpus.

## Current boundary

The adapter performs local inference only. It does not perform VAD, diarization, alignment, consensus, disagreement detection, persistence, or background job orchestration. Those services should consume the common result contract rather than access Faster-Whisper objects directly.

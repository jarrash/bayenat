# Bayenat Phase 2: 8-Hour Arabic Pilot

This package defines the first authorized Arabic evaluation corpus for Bayenat. The target is **Saudi/Gulf Arabic**, with formal MSA and Arabic-English professional slices. The official pilot corpus is newly collected volunteer/role-play speech and must not contain real case evidence.

## Package layout

```text
schema/consent.schema.json
schema/recording_manifest.schema.json
tools/split_speaker_disjoint.py
tools/validate_manifest.py
tests/test_split_and_manifest.py
```

## Required metadata

Each recording requires a stable recording ID, a stable speaker ID, a consent ID, private authorization status, immutable audio metadata including SHA-256, dialect and language metadata, scenario tags, two-annotator plus adjudication status, and split eligibility. Consent metadata is stored separately because it is more sensitive than the benchmark manifest.

The manifest may contain only restricted internal paths. It must never contain public links to raw audio or signed storage URLs. Raw consent records remain access-controlled.

## Creating speaker-disjoint splits

From the repository root:

```bash
python3 benchmarks/phase2/tools/split_speaker_disjoint.py \
  benchmarks/phase2/manifests/pilot_manifest.json \
  benchmarks/phase2/manifests/pilot_manifest.split.json \
  --seed 20260816
```

The splitter assigns whole speakers to `development`, `calibration`, `test`, or `challenge`. It uses a seeded greedy duration balancer and is deterministic for the same input, seed, and ratios. It never splits a speaker across partitions.

Validate the output:

```bash
python3 benchmarks/phase2/tools/validate_manifest.py \
  benchmarks/phase2/manifests/pilot_manifest.split.json
```

## Pilot gates

The pilot is ready to proceed toward the 24-hour benchmark when Saudi/Gulf normalized WER is at most 18%, difficult-audio normalized WER is at most 30%, negation accuracy is at least 98%, number/date/currency accuracy is at least 97%, critical-name accuracy is at least 95%, high-risk recall is at least 95%, and the calibration-approved `HIGH` confidence band is at least 95% precise. Negation, material-number, and integrity failures are hard stops.

See `docs/phase-2-pilot-decisions.md` for governance roles, retention, corpus composition, and the complete decision record.

## Computing pilot metrics

The evaluator is `tools/evaluate_asr.py`. Each reference transcript JSON contains a `text` field and optional `critical_items`. A negation item declares `required_tokens` and `forbidden_tokens`; a name item declares `reference_text`. The evaluation output contains one hypothesis `text` per `recording_id`, plus optional per-item hypotheses under `critical_items`.

Run it from the repository root:

```bash
python3 benchmarks/phase2/tools/evaluate_asr.py \
  --manifest benchmarks/phase2/manifests/pilot_manifest.split.json \
  --evaluation results/faster_whisper.json \
  --root benchmarks/phase2 \
  --output results/faster_whisper.metrics.json
```

The result reports micro-aggregated normalized WER, negation accuracy, critical-name accuracy, per-recording WER, and item-level outcomes. Normalization is deliberately conservative: it removes diacritics, tatweel, punctuation, and spacing variation, maps common Alef variants and `ى`, and converts Arabic/Persian digits, but it does not map `ة` to `ه`, remove negation, or rewrite grammar.

The negation metric is a polarity-preservation check, not a complete semantic entailment metric. The critical-name metric requires the normalized reference name phrase to occur contiguously in the normalized hypothesis. Both metrics require careful reference annotation and should be reported with item counts and error examples.

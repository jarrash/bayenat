# Bayenat Phase 2 Arabic Evaluation Protocol

## Executive decision

Bayenat should **not** define Arabic transcription success from one public dataset or one aggregate WER number. Phase 2 will use a two-layer evaluation corpus:

1. A **public/licensed research layer** for reproducible engineering regression tests.
2. A **newly collected, consented Bayenat challenge layer** that reflects the intended operating environment: Arabic and mixed Arabic-English evidence, multiple speakers, realistic noise, spontaneous speech, numbers, names, dates, currency, legal and technical terminology, and dialect variation.

The challenge layer is the decision-making benchmark. Public datasets are useful for comparison and pipeline debugging, but they cannot substitute for an authorized corpus representative of Bayenat’s future users.

> **No real case evidence belongs in model development or benchmarking unless the organization has documented authority, participant rights, purpose limitation, retention rules, and a safe handling environment.**

## What “authorized” means

Every recording in the official Bayenat benchmark must have a provenance record proving that Bayenat is permitted to store, process, annotate, evaluate, and—if applicable—share the recording or derived features. The minimum record contains the source owner, collection date, speaker or rights-holder consent basis, permitted purposes, geography/jurisdiction, retention deadline, access classification, redistribution status, and revocation or deletion procedure.

For newly collected speech, each speaker signs or records consent in Arabic and, where relevant, English. Consent must state that the speech will be transcribed by automated systems, compared across multiple systems, reviewed by humans, and used to evaluate software. It must state whether the recording may be retained, whether de-identified derivatives may be shared, and how withdrawal works. Participation must not depend on surrendering unrelated rights.

For lawfully provided operational samples, the supplying organization must warrant that it has authority to provide the recordings for the stated evaluation purpose. Bayenat should prefer **synthetic, scripted, role-play, or volunteer-recorded scenarios** in Phase 2 rather than importing real disputes. If real evidence is later used for a private validation, it must be a sealed, access-controlled holdout and must never be copied into public artifacts.

## Corpus composition

The recommended initial challenge corpus is **24 hours of speech**, with approximately 300 speakers and a balanced design. The target is large enough to expose speaker and condition variance while remaining feasible for careful human annotation. A smaller 8-hour pilot may be used to validate the protocol, but it must not be treated as the final acceptance benchmark.

| Stratum | Target share | Design requirement |
|---|---:|---|
| Saudi / Gulf Arabic | 25% | Include urban and non-urban speakers; do not equate nationality with dialect identity |
| Egyptian Arabic | 15% | Include conversational and formal registers |
| Levantine Arabic | 15% | Include at least two country backgrounds where feasible |
| Hijazi / Western Saudi | 10% | Include locally relevant vocabulary and code-switching |
| Iraqi / Mesopotamian | 10% | Include conversational speech |
| North African Arabic | 10% | Include Maghrebi variation and difficult lexical items |
| Modern Standard Arabic | 10% | Read and prepared speech |
| Mixed Arabic-English | 5% | Code-switching, names, technical terms, and product terminology |

The exact regional allocation may change if recruitment is difficult, but the final report must disclose the actual distribution. Dialect labels are speaker- or annotator-supported metadata, not automatic assumptions from nationality.

The speech conditions must include clean and noisy recordings, close and far microphones, telephone-like audio, reverberation, overlapping speech, interruptions, hesitation, numbers, dates, names, monetary values, negations, legal/technical phrases, and spontaneous conversational speech. At least 20% of the corpus should be mixed Arabic-English or contain English terms because Bayenat’s intended evidence is unlikely to be perfectly monolingual.

## Public and licensed component choices

The public Arabic Speech Corpus can be used as a **sanity-check set** because its site describes a Creative Commons Attribution 4.0 release with 1,813 WAV utterances, text labels, phonetic labels, and an additional annotated evaluation portion. It is narrow and studio-oriented, so it must not be used as Bayenat’s principal acceptance set [1].

QASR can be considered for a licensed or rights-verified comparison layer. Its publication describes a 2,000-hour, 16 kHz, broadcast-domain, multi-dialect corpus with aligned lightly supervised transcripts and speaker information [2]. Bayenat must verify the current terms before downloading, redistributing, or claiming reproducibility from it.

L2-KSU can be considered as a licensed MSA read-speech component. The LDC catalog describes approximately six hours from 80 native and non-native speakers with transcripts and metadata, but access is governed by an LDC agreement [3]. The benchmark manifest should record the license identifier and prohibit redistribution where the agreement does.

Masader and Arab Voices should be used for discovery, metadata comparison, and external benchmarking context rather than treated as blanket authorization for their underlying datasets. Masader catalogs Arabic datasets and their attributes [4], while Arab Voices reports a framework spanning 31 datasets and 14 dialects [5].

## Annotation protocol

The reference transcript is a **human annotation**, not the output of any Bayenat engine. Annotators work from the audio and may use a playback waveform, but they must not see model outputs during first-pass transcription. A second annotator independently checks every segment in the evaluation and challenge subsets. A senior adjudicator resolves disagreements, especially negations, numbers, names, dates, currency, and speaker boundaries.

The reference package stores the raw orthographic transcription, a normalized comparison form, segment start and end times, speaker IDs, language tags, uncertainty markers, and annotation provenance. Raw and normalized forms are never conflated. Annotators must mark unintelligible speech, overlapping speech, non-speech events, code-switching, and uncertain words instead of guessing.

Arabic normalization for scoring is versioned and conservative. The benchmark reports at least two views: **strict orthographic scoring** and **comparison-normalized scoring**. Normalization may address Unicode form, tatweel, punctuation, whitespace, and documented character variants. It must not remove negation, change a number, merge distinct words, or rewrite grammar.

## Data splits and leakage controls

The corpus is split by speaker, not by random audio segment. No speaker, near-duplicate recording, or scripted sentence instance may cross train, development, and test partitions. The official challenge holdout is sealed and is not used for engine tuning.

| Split | Purpose | Recommended size |
|---|---|---:|
| Development | Debugging adapters, normalization, and alignment | 20% |
| Calibration | Choosing thresholds and confidence behavior | 20% |
| Official test | One-time acceptance measurement | 30% |
| Challenge holdout | Locked, unseen, high-risk evaluation | 30% |

The public/licensed layer may be used for development and external comparison. The newly collected challenge layer is the authority for Bayenat release gates. Every run records corpus version, split, speaker exclusion rules, engine versions, configuration version, and random seeds where applicable.

## Metrics

### Transcription quality

WER is reported because it is a conventional ASR measure based on edit distance between reference and hypothesis word sequences [6]. For Arabic, Bayenat also reports character error rate (CER), normalized WER, and error rates for high-risk token classes. Aggregate scores alone are insufficient.

| Metric | Purpose |
|---|---|
| Strict WER | Measures literal orthographic errors |
| Normalized WER | Measures comparison quality after the documented normalization |
| CER | Helps expose Arabic tokenization and spelling variation |
| Negation accuracy | Measures preservation of meaning-changing negation |
| Number/date/currency accuracy | Measures material factual-token preservation |
| Named-entity token accuracy | Measures names, organizations, and locations where annotated |
| Speaker-attributed WER | Measures transcription quality with speaker labels |
| Diarization error rate | Reported only when diarization is enabled and reference speaker labels exist |
| Insertion/deletion/substitution rates | Explains the source of errors rather than hiding them in WER |

### Comparison and review quality

Bayenat is not only an ASR engine. It must measure whether its comparison layer directs human attention correctly.

| Metric | Definition |
|---|---|
| High-risk recall | Share of adjudicated high-risk disagreements that Bayenat flags |
| High-risk precision | Share of Bayenat high-risk flags confirmed by annotation/adjudication |
| Negation-conflict recall | Recall specifically for meaning-reversing negation differences |
| Numeric-conflict recall | Recall for numbers, dates, and currency discrepancies |
| Review burden | Fraction of segments sent to review at each confidence threshold |
| Selective accuracy | Accuracy on segments not sent to review |
| Calibration error | Difference between predicted confidence bands and observed correctness |
| Partial-success correctness | Whether a failed engine is surfaced without corrupting the result |

## Proposed Phase 2 success gates

These thresholds are **release gates for the benchmark protocol**, not universal claims about Arabic ASR. They should be revisited after the 8-hour pilot and frozen before the official test is opened.

| Gate | Pass criterion |
|---|---|
| Reference quality | At least 95% segment-level agreement after adjudication sampling; all critical-token conflicts adjudicated |
| Reproducibility | Same corpus, configuration, and engine versions reproduce aggregate metrics within ±0.5 WER points and identical artifact hashes for deterministic stages |
| Basic Arabic transcription | Normalized WER ≤ 15% on the overall challenge test set, with per-stratum WER reported |
| Difficult audio | Normalized WER ≤ 25% on the designated noisy/telephone/overlap subset |
| High-risk token preservation | Negation accuracy ≥ 98%; numeric/date/currency accuracy ≥ 97% |
| High-risk detection | High-risk disagreement recall ≥ 95%; precision ≥ 70% |
| Review usefulness | At least 80% of segments classified `REVIEW_REQUIRED` contain a confirmed material issue or documented audio uncertainty |
| Confidence behavior | The `HIGH` band has at least 95% observed segment correctness on the calibration-approved operating point; otherwise it cannot be shown as HIGH |
| Failure transparency | 100% of injected engine failures appear in job metadata and result in correct `COMPLETED` or `PARTIAL_SUCCESS` state according to policy |
| Integrity | 100% of original, artifact, and audit-chain tamper tests detect the injected modification |

A failure on negation, numeric accuracy, or integrity is a **hard stop**, even if aggregate WER passes. Bayenat must never compensate for meaning-changing errors with a favorable average score.

## Engine-comparison policy

Phase 2 should begin with at least two local engines, but the benchmark report must distinguish implementation diversity from model-family diversity. Faster-Whisper and Whisper may share the Whisper model family and therefore cannot be presented as two independent expert opinions. Their agreement is useful operationally but receives a correlation adjustment. A genuinely different third architecture may be added only when its license, model provenance, hardware requirements, and output reproducibility are documented.

The initial acceptance requirement is therefore **two working adapters plus a transparent correlation-aware consensus layer**, not an unsupported claim that three engines provide independent truth.

## Governance and access

The official test manifest is access-controlled. Raw recordings are encrypted at rest in the deployment environment, and benchmark exports contain only the minimum data required. Model developers may receive derived metrics and approved excerpts, not unrestricted recordings. Every access, annotation, export, and deletion is logged. Consent withdrawal or rights revocation triggers a documented impact assessment and, where required, removal from future benchmark versions.

The benchmark report must include corpus version, rights status, speaker and dialect distributions, recording conditions, annotation procedure, normalization version, engine metadata, confidence calibration, all strata metrics, failures, and known limitations. A single headline WER without these disclosures is not an acceptable Bayenat result.

## Phase 2 implementation gates

Phase 2 may proceed in four controlled increments:

1. **Pilot gate:** collect and annotate 8 hours; validate consent, annotation agreement, storage controls, and metric scripts.
2. **Adapter gate:** run two local engines on the pilot; preserve raw outputs and reproducibility metadata; do not yet tune consensus thresholds on the official holdout.
3. **Comparison gate:** implement alignment, disagreement classes, correlation-aware consensus, and confidence calibration against the calibration split.
4. **Acceptance gate:** freeze the corpus and configuration, run once on the official test and challenge holdout, publish the full report internally, and decide whether the Phase 2 claims are supported.

## Decisions required from Bayenat leadership

The technical protocol is defined, but four organizational decisions remain mandatory: the jurisdiction and organization responsible for consent and retention; the first target dialect/user population; whether the benchmark will permit any real operational recordings or remain fully role-play/synthetic; and the person or role authorized to approve the official corpus version and release gate.

My challenge is direct: **if Bayenat cannot obtain consent for 24 hours of representative speech, it should narrow its Phase 2 claims rather than quietly benchmark on scraped or ambiguous data.** A smaller authorized corpus with transparent limits is more defensible than a larger corpus with unclear rights.

## References

[1]: https://en.arabicspeechcorpus.com/ "Arabic Speech Corpus: corpus description and CC BY 4.0 notice"
[2]: https://aclanthology.org/2021.acl-long.177/ "QASR: QCRI Aljazeera Speech Resource"
[3]: https://catalog.ldc.upenn.edu/LDC2024S11 "L2-KSU Native and Non-Native Arabic Speech, LDC catalog"
[4]: https://aclanthology.org/2022.lrec-1.681/ "Masader: Metadata sourcing for Arabic text and speech data resources"
[5]: https://aclanthology.org/2026.findings-acl.575/ "Arab Voices: Mapping Standard and Dialectal Arabic Speech Technology"
[6]: https://www.isca-archive.org/interspeech_2004/morris04_interspeech.html "From WER and RIL to MER and WIL"

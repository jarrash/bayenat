# Bayenat Phase 2 Pilot Decisions

## Decision status

These decisions define the **8-hour pilot**. They are deliberately narrower than the eventual 24-hour challenge corpus and may be revised only through a versioned benchmark decision record.

## 1. Target dialect and user population

**Primary target:** Saudi/Gulf Arabic, with the first operational emphasis on Saudi speakers and Saudi professional vocabulary.

The pilot will target a mixed register rather than a single accent: approximately 60% Saudi/Gulf conversational speech, 20% Modern Standard Arabic or formal prepared speech, and 20% Arabic-English code-switching and professional terminology. This gives Bayenat a clear initial market wedge while retaining enough variation to expose failure modes.

The pilot will record dialect metadata at the speaker level using self-identification plus annotator review. Nationality is not used as a proxy for dialect. Non-target dialects may appear in a small robustness slice, but they do not determine the Saudi/Gulf release gate.

## 2. Corpus source

The official 8-hour pilot will be **newly collected, volunteer/role-play speech**, not real case evidence and not scraped media. Participants will read controlled prompts and perform authorized simulated evidence scenarios covering technical disputes, contract discussions, internal investigations, digital incidents, dates, amounts, names, negations, and mixed Arabic-English terminology.

The pilot will include approximately 100 speakers with 4–6 minutes of usable speech per speaker on average. It will contain read, prompted spontaneous, and paired-dialogue recordings. Public or licensed corpora may be used as non-gating regression sets, but they will not replace the newly collected challenge data.

## 3. Governance

The governance owner is the **Bayenat Data Governance Owner**, a named organizational role accountable for consent, purpose limitation, retention, access approvals, and benchmark release. The **Corpus Custodian** manages storage, manifest integrity, access logs, and deletion workflows. The **Annotation Lead** manages annotator training and adjudication. The **Independent Evaluation Lead** freezes splits, runs the official metrics, and has authority to reject a contaminated or non-reproducible result.

The benchmark is private by default. Raw audio is encrypted at rest, access is role-based, and derived benchmark metrics may be shared only after governance approval. The initial retention period is **12 months after the pilot report**, unless a participant withdraws earlier or the Data Governance Owner approves a documented extension. Consent records must state automated transcription, cross-engine comparison, human review, retention, withdrawal, and whether de-identified derivatives may be retained for research.

No raw pilot audio may be used to train a production model during the pilot unless a separate training-purpose consent and approval exists. This keeps evaluation independent from tuning.

## 4. Review-grade WER gates for the 8-hour pilot

The pilot is a readiness gate, not a production accuracy claim. Thresholds are intentionally stricter for meaning-changing tokens than for aggregate transcription.

| Gate | Pilot threshold | Consequence |
|---|---:|---|
| Saudi/Gulf normalized WER, overall | ≤ 18% | Passes only if critical-token gates also pass |
| Saudi/Gulf normalized WER, difficult-audio slice | ≤ 30% | No production-style claim if failed |
| MSA/formal slice normalized WER | ≤ 15% | Diagnostic and readiness gate |
| Arabic-English slice normalized WER | ≤ 25% | Diagnostic and readiness gate |
| Negation accuracy | ≥ 98% | Hard stop if failed |
| Number/date/currency accuracy | ≥ 97% | Hard stop if failed |
| Critical-name accuracy | ≥ 95% | Hard stop for review-grade positioning |
| Segment-level high-risk recall | ≥ 95% | Hard stop for consensus/review claims |
| `HIGH` confidence precision | ≥ 95% on calibration split | Otherwise disable `HIGH` label |
| Review queue precision | ≥ 70% | Otherwise tune thresholds; do not hide uncertainty |

A pilot pass means the pipeline is ready for a locked 24-hour benchmark and controlled product testing. It does **not** mean Bayenat is courtroom-grade, legally authoritative, or safe for unsupervised transcription.

## Required pilot composition

| Slice | Target duration | Purpose |
|---|---:|---|
| Saudi/Gulf conversational | 4h 48m | Primary release gate |
| MSA/formal prepared | 1h 36m | Formal register behavior |
| Arabic-English professional | 1h 36m | Code-switching and technical vocabulary |
| Difficult-audio subset, crossing the above | ≥ 1h 36m | Noise, far-field, overlap, telephone-like audio |

The difficult-audio subset overlaps the language/register slices; it is not additional duration. Critical-token items must be deliberately over-sampled and reported separately rather than hidden inside the average.

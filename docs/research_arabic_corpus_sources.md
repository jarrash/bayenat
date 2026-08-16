# Research Notes: Arabic Evaluation Corpus Sources

## Findings

The Arabic Speech Corpus site describes 1,813 WAV utterances in South Levantine/Damascian Arabic, paired with orthographic and phonetic annotations, plus an additional 18-minute fully annotated evaluation corpus. The site states that the corpus is released under Creative Commons Attribution 4.0. This makes it a useful **public sanity-check component**, but not a sufficient benchmark for Bayenat because it is single-speaker/studio-style and narrow in dialect and task conditions.

QASR is described by its ACL publication as a 2,000-hour, 16 kHz broadcast-domain, multi-dialect Arabic corpus collected from Aljazeera, with lightly supervised aligned transcriptions, segmentation, punctuation, and speaker information. It may be valuable for broad research benchmarking, but Bayenat must verify the current license and permitted redistribution/use before including it in an official benchmark package.

L2-KSU Native and Non-Native Arabic Speech is an LDC catalog item containing approximately six hours of Modern Standard Arabic read speech from 80 subjects, including native speakers from Saudi Arabia, Egypt, and Palestine and non-native speakers from Central and West Africa. It includes transcripts and speaker metadata, but access is governed by an LDC agreement; it should be treated as a licensed optional component, not assumed to be freely redistributable.

Masader catalogs Arabic NLP datasets and highlights the importance of dataset metadata and licensing attributes. It is useful for discovery and provenance tracking, not as a direct license grant.

Arab Voices is a 2026 framework described by ACL Findings as unifying 31 datasets across 14 dialects and providing an Arabic dialect ASR benchmark. It reinforces the need to report dialect, domain, and audio-quality strata instead of one aggregate Arabic score. Bayenat should use it as a discovery and comparison reference while independently verifying each underlying dataset's rights.

WER is a conventional ASR metric based on the edit cost needed to restore the reference word sequence. The ISCA reference also discusses MER and WIL, which can complement WER when the operational question is information lost rather than raw word edits.

## Source URLs

- https://en.arabicspeechcorpus.com/
- https://aclanthology.org/2021.acl-long.177/
- https://catalog.ldc.upenn.edu/LDC2024S11
- https://aclanthology.org/2022.lrec-1.681/
- https://aclanthology.org/2026.findings-acl.575/
- https://www.isca-archive.org/interspeech_2004/morris04_interspeech.html

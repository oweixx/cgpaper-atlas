# Research topic classification

CG Paper Atlas uses `cg-topics-v3.0` for its 10 research areas and 30 subtopics. The same labels drive the explorer, research trends, country profiles and exports. These are automatic, overlapping labels, not conference tracks or expert-verified judgments.

## Evidence and mapping

1. Preserve the eight-venue corpus and exact publication identities. Match OpenAlex works by exact DOI; never match a title approximately to borrow another paper's subjects.
2. Collect OpenAlex predicted keywords and topics into a dated snapshot. The collection queried 27,318 distinct DOIs and matched 27,106. All requested batches completed; unmatched publications use local text evidence.
3. Map specific keyword phrases to the CG taxonomy using [curated aliases](../pipeline/topic_keyword_map.py). Consider only the first five returned keywords with source scores at least 0.65. Preserve the provider's keyword order; it is not a score ranking. Broad OpenAlex topics are retained as provenance but are not directly treated as CG subtopics.
4. Use specific title phrases and context-aware abstract rules. Abstract rules consider introductory/contribution sentences, repeated signals, background comparisons and ambiguous terms. Examples include motion versus image retargeting, geometric versus generative diffusion, and haptic versus optical rendering. With mapped keyword areas, abstract labels must corroborate those areas; without mapped keywords, the full local fallback applies. Specific title evidence can add another area.
5. Keep multi-label results and abstain when no rule has adequate evidence. `Other / Unclassified` means insufficient classification evidence, not that a paper is outside CG. This is a rule-based abstention, not calibrated uncertainty detection; confidently wrong labels remain possible.

The local mapping does not use venue, year, country, author identity, or paper-specific overrides. OpenAlex predictions themselves can use source venue as an input, so they are not venue-independent evidence. Their keyword scores express source relevance, **not** the probability that our mapped CG label is correct. The 0.65 cutoff is a development choice, not an accuracy guarantee.

The [SIGGRAPH technical-paper scope](https://s2026.siggraph.org/program/technical-papers/) provides context for the broad CG domains. OpenAlex describes [topics](https://help.openalex.org/data/topics/) and [keywords](https://help.openalex.org/data/keywords/) as machine-assigned metadata; keywords are not necessarily supplied by authors. Our 10-area taxonomy is an editorial grouping rather than an official SIGGRAPH taxonomy.

## Evaluation and its limits

Reference labels were written by **Codex AI, also the classifier developer** after reading available titles and abstracts. No independent human expert annotated these references. Labels cover central research targets and substantive methods; an incidental application, comparison or routine evaluation does not automatically establish another field. This judgment is debatable, especially for multidisciplinary papers.

Development used 80 initial references, then 48 and 32 additional references from earlier iterations. The first rules-only revision improved on its 48-paper validation, but a later rules-only revision underperformed the baseline on a fresh 32-paper sample. Both reports are retained; they motivated using semantic keywords rather than claiming the rules-only approach had solved classification. These 160 papers subsequently became development material for v3.

For the final v3 evaluation, the classifier and keyword map were frozen **before** selecting another 64 papers (seed 60261116). Each of eight primary venues contributes eight papers: four before 2015 and four from 2015 onward. All 160 previous references and 30 initial diagnostic examples were excluded. Reference labels were recorded before v3 predictions were displayed. Code hashes, text hashes and annotation rationales are published in the [reference file](../data/topic_reference_holdout.json). The [report](../data/topic_validation.json) includes the metadata hash, venue/era/abstract-availability breakdowns and every disagreement.

| Area-level metric on 64 references | Old title-only rules | Context-aware local rules | Hybrid v3 |
|---|---:|---:|---:|
| Micro precision | 77.6% | 82.8% | 81.5% |
| Micro recall | 46.8% | 47.7% | 59.5% |
| Micro F1 | 58.4% | 60.6% | 68.8% |
| Exact set of areas | 29.7% | 31.2% | 34.4% |

V3 has 66 true-positive area assignments, 15 false positives and 45 false negatives on these references. An unclassified prediction contributes false negatives when the reference has an area. Empty reference labels are allowed for insufficient evidence. The equal venue/era sample is not proportional to the corpus, the annotator is not independent, and some records lack abstracts. **These figures are not estimates of whole-corpus accuracy. They also do not validate all 30 subtopics.**

Remaining errors include missing secondary methods in multidisciplinary research, unfamiliar historical terminology, keywords describing a tool rather than the contribution, and confusion between visual analytics *of* learning models and learning *as* a graphics method. For example, v3 still misses the visualization area for *Splatterplots* and assigns an animation label to *A Hybrid Approach for Stroke-Based Letterform Composition*. These are visible disagreements, not hidden exceptions corrected specifically to fit the test.

The [classification audit](../data/topic_classification_audit.json) reports changes in area counts and unclassified coverage, including venue and abstract availability. A reduction in unclassified records does not establish accuracy. Old area trends are not directly comparable with the new labels without accounting for the classifier change.

## Inspect and reproduce

Open **Topic evidence** on a paper to see every assigned area/subtopic, source keyword or normalized text excerpt, matching terms, source score where available, and classifier version. Evidence files are split into 16 shards and loaded only when opened. Source scores are explicitly distinguished from classification accuracy. Failed requests can be retried.

- [Keyword snapshot](../data/topic_metadata.json) and [collection ledger](../data/coverage_topics.json)
- [Current classifier](../pipeline/taxonomy.py), [local rules](../pipeline/taxonomy_rules.py), and [original baseline](../pipeline/taxonomy_v1.py)
- [v2.0 validation](../data/topic_validation_v2_0.json) and [v2.1 validation](../data/topic_validation_v2_1.json), retained as historical reports

```sh
# Optional new collection: set OPENALEX_API_KEY only in the process environment.
python pipeline/collect_topics.py
# Reproduce from the committed snapshots without network access:
python pipeline/build_cg.py
python pipeline/evaluate_topics.py --reference topic_reference_holdout.json --output data/topic_validation.json
python -m unittest discover -s pipeline -p test_cg.py
python pipeline/validate_cg.py
```

The validator reproduces every paper's labels and evidence, verifies source terms and scores, checks exports and statistics, and reproduces the held-out report. Software checks establish consistency, not scientific correctness.

The next useful step is an independently expert-annotated set across areas, venues and eras, with a separate validation of subtopics. Also review historical catalog entries: some panels, bibliographies and workshop reports remain in the inherited snapshot despite existing exclusion rules. This classification update preserves corpus membership; it does not silently remove those records or claim all are full research papers.

# Evaluation

Evaluation date: June 14, 2026

## Local OCR Acceptance

Command:

```bash
ALV_OCR_ENGINE=paddle .venv/bin/python scripts/evaluate.py
```

Results on the development Mac:

| Measure | Result |
| --- | --- |
| Applications | 2 |
| Findings | 12 |
| Expected fully matching | 1 |
| Actual fully matching | 1 |
| Median analysis time | 2,282 ms |
| Slowest analysis time | 2,858 ms |
| Five-second target | Pass |

The compliant sample passed every implemented comparison and health-warning
check. The intentionally degraded sample produced mismatches and remained
available for officer judgment.

## Batch Integrity

Command:

```bash
.venv/bin/python scripts/run_batch_test.py --applications 300
```

Results:

- 300 applications requested
- 300 terminal review artifacts produced
- 300 unique application identifiers retained
- no lost or duplicate terminal results

## Real-Image Evaluation Set

`fixtures/evaluation-real/` contains a committed, publication-safe set of
ordinary retail-bottle photographs. It includes readable front and back labels
plus perspective, glare, curvature, small-print, and uneven-lighting cases.
The images were reviewed for visible personal information and stripped of
EXIF/GPS metadata.

## Real-Image OCR Baseline

Command:

```bash
ALV_OCR_ENGINE=paddle .venv/bin/python scripts/evaluate.py \
  --fixture-dir fixtures/evaluation-real \
  --max-ms 5000
```

The resident PaddleOCR mobile models processed six application records covering
five distinct image-pair conditions. Model startup was excluded from
per-application analysis time.

| Measure | Result |
| --- | --- |
| Applications | 6 |
| Findings | 42 |
| Match | 19 |
| Mismatch | 11 |
| Needs Human Review | 12 |
| Median analysis time | 4,324 ms |
| P95 analysis time | 7,154 ms |
| Slowest analysis time | 7,154 ms |
| Median five-second target | Pass |
| All-cases five-second target | Fail |

Observed behavior:

- Crown Royal brand, alcohol content, net contents, producer, and country were
  recovered after OCR-tolerant spacing normalization. The ornate class text was
  misread, and no statutory government warning was present in the submitted
  package photographs.
- Glenlivet brand, class/type, and net contents were recovered from the curved
  bottle labels. The alcohol content was not visible in the supplied frames.
  OCR detected the government warning but did not recover enough small print
  for exact verification, so the result is `Needs Human Review`.
- The Red Blend photographs were the most difficult because the front design,
  curvature, and small back-label text produced low or incomplete OCR
  confidence. Unreliable comparisons route to `Needs Human Review`.
- Bounding OCR input to a 1,200-pixel maximum dimension reduced median time
  from 14,581 ms on the original 12-megapixel input path to 4,324 ms without
  materially weakening the useful field extraction.

Release implications:

- The human-review behavior is appropriate for incomplete real-image evidence.
- The current local implementation meets five seconds for the median case but
  not for every two-image case.
- Before release, either optimize repeated/image-heavy OCR further or state the
  five-second result precisely as a typical warm-case target rather than an
  all-input guarantee.

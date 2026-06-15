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
per-application analysis time. The current quality-first configuration submits
the original images to PaddleOCR and relies only on Paddle's own internal
4,000-pixel safety limit when it chooses to resize.

| Measure | Result |
| --- | --- |
| Applications | 6 |
| Findings | 42 |
| Match | 6 |
| Mismatch | 6 |
| Needs Human Review | 30 |
| Median analysis time | 14,971 ms |
| P95 analysis time | 17,627 ms |
| Slowest analysis time | 17,627 ms |
| Reviewer-visible latency impact | None after preprocessing completes |

Observed behavior:

- Crown Royal remains difficult because of ornate packaging, metallic finish,
  and low OCR confidence. The current quality-first run keeps most fields in
  `Needs Human Review`, while the missing statutory government warning still
  fails correctly.
- Glenlivet brand, class/type, and net contents were recovered from the curved
  bottle labels. The alcohol content was not visible in the supplied frames.
  OCR detected the government warning but did not recover enough small print
  for exact verification, so the warning result correctly fails on the
  submitted evidence.
- The Red Blend photographs remain the most difficult because the front design,
  curvature, and small back-label text produce low or incomplete OCR
  confidence. Those cases now conservatively route to `Needs Human Review`
  except for the strict warning failure.
- The current repository configuration uses full submitted image resolution by
  default because preprocessing is a background task and OCR quality takes
  priority over inline speed.

Release implications:

- The human-review behavior remains appropriate for non-warning fields with
  incomplete real-image evidence.
- The relevant release criterion is now evidence quality and correctness rather
  than inline OCR completion time, because officers open already-preprocessed
  applications.
- Operational timing is still worth recording for capacity planning, but it is
  no longer a reviewer-experience gate.

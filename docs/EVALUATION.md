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

## Remaining Evaluation

The generated fixtures prove pipeline integration and provide deterministic
ground truth. Before submission, add several publication-safe photographs of
ordinary retail bottles and rerun the same evaluation to measure glare,
curvature, perspective, blur, small print, and uneven lighting on deployed
hardware.

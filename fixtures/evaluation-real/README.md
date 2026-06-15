# Real-Label Evaluation Fixtures

This directory contains the publication-safe retail-label photographs used for
the final OCR and image-quality evaluation.

- The photographs were captured by the applicant from ordinary retail bottles.
- No applicant, account, payment, or other COLA personally identifiable
  information is present.
- The images were reviewed for visible personal information.
- EXIF and GPS metadata were removed during conversion to JPEG.
- `real-bottle-evaluation-batch.json` references every image in this directory.

To run the application with only this evaluation set:

Linux:

```bash
ALV_FIXTURE_DIR=fixtures/evaluation-real ALV_OCR_ENGINE=paddle ./run.sh
```

Windows PowerShell:

```powershell
$env:ALV_FIXTURE_DIR = "fixtures/evaluation-real"
$env:ALV_OCR_ENGINE = "paddle"
powershell -ExecutionPolicy Bypass -File .\run.ps1
```


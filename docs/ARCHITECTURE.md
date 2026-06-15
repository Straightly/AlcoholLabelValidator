# Architecture

The prototype uses one FastAPI process and one browser origin. FastAPI serves
the built React application, API, and label images.

```text
Sample package trigger
  -> background preprocessing job
  -> immutable submission and images
  -> OpenCV quality measurements
  -> local PaddleOCR detection and recognition
  -> deterministic field and warning checks
  -> immutable review package
  -> compliance-officer decision
```

PaddleOCR uses the local mobile detection and recognition models in the
quality-first background preprocessing path. Reviewer interaction reads the
completed analysis artifacts rather than waiting on OCR inline. OpenCV provides
inexpensive quality signals, while uncertain evidence remains with the officer.

The committed fixtures include OCR sidecars for deterministic automated tests.
The launch scripts and evaluation script enable PaddleOCR by default for the
POC and exercise the real local OCR pipeline used for deployment.

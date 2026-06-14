# Architecture

The prototype uses one FastAPI process and one browser origin. FastAPI serves
the built React application, API, and label images.

```text
Sample package
  -> immutable submission and images
  -> OpenCV quality measurements
  -> local PaddleOCR detection and recognition
  -> deterministic field and warning checks
  -> immutable review package
  -> compliance-officer decision
```

PaddleOCR uses the mobile detection and recognition models to stay within the
five-second interaction target. More expensive orientation and unwarping
models were evaluated but removed from the default path after measurement.
OpenCV provides inexpensive quality signals, while uncertain evidence remains
with the officer.

The committed fixtures include OCR sidecars for deterministic automated tests.
`ALV_OCR_ENGINE=paddle` ignores those sidecars and exercises the real local OCR
pipeline used for deployment.

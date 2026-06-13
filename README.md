# Alcohol Label Validator

Prototype for Treasury's AI-Powered Alcohol Label Verification assessment.

The primary product is a standalone compliance-officer review aid. A manually triggered synthetic intake stands in for the future authorized handoff from COLA:

```text
Synthetic intake -> Process Sample Intake -> analysis artifacts -> officer decision
```

## Current Vertical Slice

- Import and preprocess a synthetic distilled-spirits batch on demand.
- Compare submitted fields with fixture label text.
- Check the statutory government warning.
- Review evidence and record an approval or rejection.
- Preserve submissions, analyses, and decisions as separate immutable JSON artifacts.

The current fixture uses `label_text` as deterministic OCR input. OpenCV and PaddleOCR will replace that fixture boundary without changing the API or rule engine.

`Process Sample Intake` runs synchronously in the POC. There is no separate background preprocessing service. Analysis artifacts are retained so reviewed applications open immediately without repeating OCR.

The backend will load and warm one reusable OCR engine during startup, then keep it resident in memory. Readiness will be withheld until initialization succeeds, preventing officer requests from paying model-loading or first-inference cost.

## Stakeholder Alignment

- No COLA integration is attempted.
- No applicant PII is accepted or stored. The contract uses opaque IDs and a non-PII source label.
- Runtime operation does not call cloud OCR/model APIs, CDNs, or third-party font services.
- Azure, .NET, FedRAMP authorization, retention, and production identity controls are future procurement and integration concerns, not claims made by this POC.
- A future authorized .NET/COLA adapter could strip PII, invoke the documented JSON/HTTP boundary, and reattach results outside this application.
- The preferred production integration would invoke analysis when COLA receives an application. This keeps OCR latency and failures outside the officer interaction, enables controlled retries, and makes each immutable analysis artifact reusable by authorized downstream workflows.
- Intake-time preprocessing remains preferable for robustness and reuse even when synchronous analysis is well below five seconds; it also provides headroom if future image volume, models, or rules make performance a concern.

## Repository Layout

```text
backend/             FastAPI service, contracts, analysis, and artifact storage
portals/officer/     Separate React compliance-officer application
fixtures/intake/     Committed synthetic, non-PII sample packages
data/                Runtime artifacts; ignored by Git
```

## Local Setup

Backend:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn backend.app.main:app --reload --port 8000
```

```bash
cd portals/officer
npm install
npm run dev
```

The officer portal dev server proxies `/api` to `http://127.0.0.1:8000`.

## Important Limitations

- Fake login is demonstration context, not authentication.
- Use synthetic or public sample data only.
- The prototype assists a human reviewer and does not make a legal compliance determination.
- OCR and image upload are the next implementation layer.

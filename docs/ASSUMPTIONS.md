# Assumptions

## Product Boundary

- The prototype is a standalone compliance-officer review aid.
- It does not connect directly to COLAs Online.
- Sample packages represent applications received from an upstream system.
- `Process Sample Intake` manually starts a background preprocessing job.
- The officer remains responsible for the final approval or rejection.
- The fake login supplies demonstration context only.

## Data Boundary

- Inputs use opaque submission and application identifiers.
- Applicant names, contact information, account information, payment
  information, and unrelated COLA data remain outside the prototype.
- Seeded fixtures use generated label images and synthetic application records.
- The committed real-image evaluation set uses applicant-captured retail-label
  photographs reviewed for visible personal information and stripped of
  EXIF/GPS metadata.
- A package may contain one or many applications.
- An application may contain one or many label images.
- Seeded UI samples use no more than two images per application.

## Verification

- TTB guidance was reviewed for context, but the POC implements only the
  assignment's representative field comparisons and health-warning checks.
- Beverage category is retained as application context; it does not select a
  comprehensive beverage-specific compliance profile.
- Case, spacing, and ordinary punctuation may be normalized for descriptive
  field comparisons.
- Government-warning wording and punctuation are checked strictly. Capitalization (case) is normalized (case-insensitive) to prevent minor OCR character recognition layout discrepancies from causing false failures, but incomplete wording or punctuation warnings still definitively fail.
- Conditional disclosures, subtype-specific rules, formulation-dependent
  requirements, and definitive physical measurements are outside the POC.
- Unreadable or uncertain non-warning evidence returns `Needs Human Review`.
- Physical dimensions cannot be established definitively from an uncalibrated
  image.

## Runtime

- Image preparation and OCR run locally in the backend.
- The browser requires access only to the deployed application origin.
- The demonstration uses one FastAPI process serving both the API and the built
  React application.
- Sample-intake imports are analyzed in a background job before officer review.
- **Multi-Engine Vision Fallback**: The architecture supports three runtime configurations for OCR:
  - **PaddleOCR** (local weights) for primary high-performance deep-learning OCR.
  - **Tesseract OCR** (pytesseract) as a native local CPU package fallback for systems where PaddlePaddle fails to run or causes CPU segmentation faults.
  - **Ollama Local VLM API** as a high-fidelity visual-language reasoning engine (supporting models like `moondream` and `minicpm-v`).
- **Production Deployment Pattern**: The deployment process was adjusted to separate the build directory from the runtime `/opt/AlcoholLabelValidator` directory. Uvicorn runs as a systemd service with custom environment parameters and binary PATH allocations.
- **Hardware & Model Evaluation**: We experimented extensively on CPU-only VM hardware with different local vision models. Small models (like `moondream` 1.5B) execute quickly but tend to caption images rather than transcribing verbatim. Larger models (like `minicpm-v` 8B) perform extremely accurate OCR but run into severe CPU execution bottlenecks and disk-swapping latency due to limited physical VM RAM constraints (10 GB RAM).
- If the budget allows, the system can transition to high-accuracy commercial cloud OCR APIs (e.g., Microsoft Azure Read API) or Multimodal LLM APIs.
- To balance cost and performance, cloud/LLM models can be queried selectively as fallbacks (i.e., routing requests to the expensive model only when the local/offline model fails to match or returns low confidence).


## Production Boundary

- Authentication, authorization, FedRAMP deployment, retention policy,
  production PII handling, and direct COLAs Online integration are outside the
  prototype.
- A production upstream adapter would retain identity correlation outside this
  application and provide only the label-review data required by this service.

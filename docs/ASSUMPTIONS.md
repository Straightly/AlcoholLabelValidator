# Assumptions

## Product Boundary

- The prototype is a standalone compliance-officer review aid.
- It does not connect directly to COLAs Online.
- Sample packages represent applications received from an upstream system.
- `Process Sample Intake` manually starts sample analysis.
- The officer remains responsible for the final approval or rejection.
- The fake login supplies demonstration context only.

## Data Boundary

- Inputs use opaque submission and application identifiers.
- Applicant names, contact information, account information, payment
  information, and unrelated COLA data remain outside the prototype.
- Seeded fixtures use publication-safe retail-label images and synthetic
  application records.
- A package may contain one or many applications.
- An application may contain one or many label images.
- Seeded UI samples use no more than two images per application.

## Verification

- Case, spacing, and ordinary punctuation may be normalized for descriptive
  field comparisons.
- Government-warning wording, capitalization, and punctuation are checked
  strictly.
- Conditional rules return `Not Evaluated` when applicability cannot be
  established from supplied facts.
- Unreadable or uncertain evidence returns `Needs Human Review`.
- Physical dimensions cannot be established definitively from an uncalibrated
  image.

## Runtime

- Image preparation and OCR run locally in the backend.
- Runtime processing uses prepared local model files.
- The browser requires access only to the deployed application origin.
- The demonstration uses one FastAPI process serving both the API and the built
  React application.

## Production Boundary

- Authentication, authorization, FedRAMP deployment, retention policy,
  production PII handling, and direct COLAs Online integration are outside the
  prototype.
- A production upstream adapter would retain identity correlation outside this
  application and provide only the label-review data required by this service.

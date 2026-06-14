# Alcohol Label Validator

Standalone prototype for assisting TTB compliance officers with alcohol-label
application review.

```text
Sample intake -> local image analysis -> field and warning checks
              -> officer review -> officer decision
```

## Test The Deployed Application

Use the deployed URL submitted with the assessment. A reviewer needs only a
current browser with JavaScript enabled.

1. Open the application and select `Open review queue`.
2. Select `Process Sample Intake`.
3. Confirm that the seeded applications appear in the queue.
4. Open the compliant samples and confirm that the expected fields and
   government warning are marked `Match`.
5. Open the attention-required samples and confirm that the seeded mismatches
   are clearly identified.
6. Confirm that submitted values, label images, extracted evidence, confidence,
   explanations, and rule sources are visible together.
7. Confirm that low-confidence or unreadable evidence is marked
   `Needs Human Review`, not silently accepted or rejected.
8. Confirm that each ordinary one- or two-image application reports an
   end-to-end analysis time below five seconds.
9. Edit the suggested decision reason and record an approval or rejection.
10. Confirm that the decided application leaves the active queue.
11. Select `Process Sample Intake` again and confirm that existing artifacts are
    not overwritten.
12. Select `Reset Demo Data` to restore the original samples.

## Requirement Verification

| Requirement | How to verify |
| --- | --- |
| Routine field matching | Compare each submitted value with the extracted label evidence shown beside it |
| Government warning | Verify complete wording, capitalization, and punctuation results; inspect presentation evidence when human review is required |
| Human judgment | Review `Needs Human Review` results and confirm the officer makes the final decision |
| Five-second response | Check the displayed end-to-end analysis duration for each ordinary application |
| Batch handling | Run the 300-application batch test described below |
| Image quality | Review skew, glare, rotation, blur, curvature, and low-resolution samples |
| Simple operation | Complete the primary workflow using the visible login, intake, queue, review, and decision controls |
| Standalone operation | Verify that the browser communicates only with the deployed application and that no cloud OCR/model endpoint is used |
| COLAs Online boundary | Confirm that sample packages use opaque identifiers and no COLAs Online connection |
| Error handling | Run the invalid-input tests and confirm failures do not publish partial or overwritten artifacts |

## Verification Scope

The prototype supports distilled spirits, wine, and malt beverages through
beverage-specific rule profiles.

| Check | Behavior |
| --- | --- |
| Brand name | Compare submitted value with extracted evidence using normalized case, spacing, and ordinary punctuation |
| Class/type designation | Compare submitted value with extracted evidence |
| Alcohol content and proof | Compare normalized submitted and extracted values when required |
| Net contents | Compare normalized submitted and extracted values |
| Producer/bottler name and address | Compare submitted value with extracted evidence |
| Country of origin | Compare when supplied and applicable |
| Government warning | Check the prescribed wording, capitalization, and punctuation |
| Warning presentation | Evaluate heading prominence and probable boldness using image/style signals; physical measurements require calibrated evidence |

Each check returns `Match`, `Mismatch`, `Needs Human Review`, or
`Not Evaluated`. The officer remains responsible for the final decision.

## Approach

- React/TypeScript compliance-officer interface
- Python/FastAPI API
- OpenCV image preparation and quality signals
- PaddleOCR local text detection and recognition
- Deterministic field comparison and versioned regulatory rules
- Separate immutable submission, analysis, and decision artifacts
- One FastAPI process serving the API and built React application
- Local runtime processing using packaged OCR models and application assets

## Tools

- CPython 3.11 or 3.12
- FastAPI, Pydantic, and Uvicorn
- OpenCV, PaddlePaddle, and PaddleOCR
- React, TypeScript, and Vite
- pytest and Ruff

## Regulatory Sources

Rules are versioned and cite the applicable source in each review result.

- [TTB distilled-spirits labeling](https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/labeling)
- [TTB wine labeling](https://www.ttb.gov/regulated-commodities/beverage-alcohol/wine/labeling)
- [TTB malt-beverage labeling](https://www.ttb.gov/regulated-commodities/beverage-alcohol/beer/labeling)
- [27 CFR Part 4](https://www.ecfr.gov/current/title-27/chapter-I/subchapter-A/part-4)
- [27 CFR Part 5](https://www.ecfr.gov/current/title-27/chapter-I/subchapter-A/part-5)
- [27 CFR Part 7](https://www.ecfr.gov/current/title-27/chapter-I/subchapter-A/part-7)
- [27 CFR Part 16](https://www.ecfr.gov/current/title-27/chapter-I/subchapter-A/part-16)

## Documentation

- [Assumptions](docs/ASSUMPTIONS.md)

## Repository Layout

```text
backend/             FastAPI API, image analysis, rules, and artifact storage
backend/tests/       Unit, integration, batch, and performance tests
portals/officer/     React compliance-officer application
fixtures/intake/     Seeded non-PII application packages and label images
fixtures/evaluation/ Controlled OCR and rule-evaluation cases
models/              Prepared local OCR model files
scripts/             Model preparation and evaluation utilities
data/                Generated runtime artifacts; ignored by Git
run.sh               Linux/macOS application launcher
run.ps1              Windows PowerShell application launcher
docs/                Assumptions and supporting technical documentation
```

## Source-Run Prerequisites

Use a 64-bit Linux or Windows machine.

| Tool | Required version |
| --- | --- |
| Git | Current supported release |
| Python | CPython 3.11 or 3.12, 64-bit |
| `pip` | Included with Python |
| `venv` | Included with Python; may be a separate Linux package |
| Node.js | 22 LTS or 24 LTS, 64-bit |
| `npm` | Included with Node.js |
| PowerShell | Windows PowerShell 5.1 or PowerShell 7+; Windows only |
| Bash | Bash 4+; Linux only |
| Browser | Current Edge, Chrome, Firefox, or Safari |

Source installation requires HTTPS access to:

- The Git repository host, unless a ZIP archive is used
- `pypi.org` and `files.pythonhosted.org`, or an approved Python package mirror
- `registry.npmjs.org`, or an approved npm registry mirror
- The configured OCR model source, or an approved offline model bundle

Package and model access is needed only during setup. Runtime processing is
local and does not require outbound access.

## Linux Setup And Run

Install Git, Python 3.11 or 3.12 with `pip` and `venv`, Node.js 22 or 24 LTS
with `npm`, and Bash.

Example Ubuntu 24.04 Python and Git installation:

```bash
sudo apt update
sudo apt install -y git python3.12 python3.12-venv python3-pip
```

Install Node.js 22 or 24 LTS separately. On Oracle Linux, install the equivalent
packages from approved enabled repositories.

Verify the tools:

```bash
git --version
python3.12 --version
python3.12 -m pip --version
node --version
npm --version
bash --version
```

Acquire and prepare the source:

```bash
git clone https://github.com/Straightly/AlcoholLabelValidator.git
cd AlcoholLabelValidator
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
npm --prefix portals/officer ci
npm --prefix portals/officer run build
.venv/bin/python scripts/prepare_models.py
chmod +x run.sh
```

Use `python3.11` instead when Python 3.11 is installed. A repository ZIP and an
approved offline model bundle may be used instead of direct downloads:

```bash
.venv/bin/python scripts/prepare_models.py --archive /path/to/model-bundle.zip
```

Start the application:

```bash
./run.sh
```

Open `http://127.0.0.1:8000/`. Press `Ctrl+C` to stop the application.

## Windows Setup And Run

Install:

- Git for Windows: `https://git-scm.com/download/win`
- CPython 3.11 or 3.12: `https://www.python.org/downloads/windows/`
- Node.js 22 or 24 LTS: `https://nodejs.org/en/download`
- Windows PowerShell 5.1 or PowerShell 7+

Optional `winget` commands:

```powershell
winget install --id Git.Git --exact
winget install --id Python.Python.3.12 --exact
winget install --id OpenJS.NodeJS.LTS --exact
```

Install the Python Launcher and add Python to `PATH`. Open a new PowerShell
window and verify:

```powershell
git --version
py -3.12 --version
py -3.12 -m pip --version
node --version
npm.cmd --version
$PSVersionTable.PSVersion
```

Acquire and prepare the source:

```powershell
git clone https://github.com/Straightly/AlcoholLabelValidator.git
Set-Location .\AlcoholLabelValidator
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
npm.cmd --prefix portals/officer ci
npm.cmd --prefix portals/officer run build
.\.venv\Scripts\python.exe scripts\prepare_models.py
```

Use `py -3.11` instead when Python 3.11 is installed. A repository ZIP and an
approved offline model bundle may be used instead of direct downloads:

```powershell
.\.venv\Scripts\python.exe scripts\prepare_models.py --archive C:\path\to\model-bundle.zip
```

Start the application:

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

Open `http://127.0.0.1:8000/`. Press `Ctrl+C` to stop the application.

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `ALV_HOST` | `127.0.0.1` | Bind address |
| `ALV_PORT` | `8000` | HTTP port |
| `ALV_DATA_DIR` | `./data` | Runtime artifact directory |
| `ALV_FIXTURE_DIR` | `./fixtures/intake` | Sample intake directory |
| `ALV_MODEL_DIR` | `./models` | Prepared OCR model directory |

## Manual Acceptance Test

Start with the seeded demo state.

1. Open the application.
2. Select `Open review queue`.
3. Confirm the queue initially contains no unreviewed applications.
4. Select `Process Sample Intake`.
5. Confirm that the seeded packages and applications are processed.
6. Confirm that the queue contains the expected applications.
7. Open each compliant sample and confirm that all expected checks are `Match`.
8. Open each attention-required sample and confirm that the seeded field,
   warning, or image-quality issue is identified.
9. Confirm that submitted images, expected values, extracted evidence,
   confidence, explanations, and rule sources are visible.
10. Confirm that skewed, rotated, curved, or unevenly lit readable labels are
    processed and that unreadable evidence returns `Needs Human Review`.
11. Confirm that ordinary one- and two-image applications report an end-to-end
    server-side analysis duration below five seconds.
12. Confirm that a rejection reason is prefilled from mismatches and remains
    editable.
13. Record an approval or rejection.
14. Confirm that the decided application leaves the active queue.
15. Select `Process Sample Intake` again and confirm that existing artifacts are
    not overwritten.
16. Select `Reset Demo Data` and confirm that the original seeded state returns.

## Batch Test

Run the 300-application fixture:

Linux:

```bash
.venv/bin/python scripts/run_batch_test.py --applications 300
```

Windows:

```powershell
.\.venv\Scripts\python.exe scripts\run_batch_test.py --applications 300
```

Confirm:

- All 300 applications receive a terminal analysis result.
- A failed application does not discard successful results from the same batch.
- No application is processed more than once.
- The review queue contains each successfully analyzed, undecided application.
- The report includes total duration, throughput, failures, and per-application
  latency.

## Error-Handling Test

The automated suite verifies:

| Condition | Expected behavior |
| --- | --- |
| Malformed package JSON | Reject the package without publishing partial artifacts |
| Duplicate package or decision | Return a conflict and preserve the first artifact |
| Missing, duplicate, or unreferenced image | Reject the affected input with a clear error |
| Unsupported, empty, corrupt, or oversized image | Reject the affected input with a clear error |
| Unreadable or low-confidence evidence | Return `Needs Human Review` rather than `Match` |
| One failed application in a batch | Preserve completed results for other applications and report the failed application |
| Unexpected processing failure | Publish a terminal error result and prevent repeated automatic selection |

## Automated Tests

Linux:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check backend scripts
.venv/bin/python scripts/check_fixtures.py
npm --prefix portals/officer run build
```

Windows:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check backend scripts
.\.venv\Scripts\python.exe scripts\check_fixtures.py
npm.cmd --prefix portals/officer run build
```

All commands must complete successfully.

`check_fixtures.py` verifies the allowed non-PII schema, image references,
publication-safe file types, and removal of EXIF/GPS metadata.

## OCR And Performance Evaluation

Linux:

```bash
.venv/bin/python scripts/evaluate.py --fixtures fixtures/evaluation --max-latency-ms 5000
```

Windows:

```powershell
.\.venv\Scripts\python.exe scripts\evaluate.py --fixtures fixtures\evaluation --max-latency-ms 5000
```

The report includes:

- Field extraction accuracy
- Government-warning result accuracy
- `Needs Human Review` behavior for unreadable evidence
- Median, p95, and slowest end-to-end latency
- A failure result when any ordinary one- or two-image application exceeds five
  seconds

## Health And Readiness

While the application is running:

```text
GET http://127.0.0.1:8000/api/health
GET http://127.0.0.1:8000/api/ready
```

Expected responses:

```json
{"status":"ok"}
{"status":"ready","ocr":"ready"}
```

The readiness endpoint returns success only after the local OCR engine and model
files are loaded and warmed.

## Runtime Network Test

After packages and model files are prepared, start the application with outbound
internet access blocked.

1. Open the application.
2. Process the seeded intake.
3. Complete one review decision.
4. Confirm that the workflow succeeds without an outbound connection.
5. Confirm in the browser network log that requests use only the application
   origin.

## Reset Test Data

Use `Reset Demo Data` in the application, or stop the application and remove the
runtime directory.

Linux:

```bash
rm -rf data
```

Windows:

```powershell
Remove-Item -Recurse -Force .\data
```

The directory is recreated on the next startup. Preserve `fixtures/` and
`models/`.

## Runtime Files

```text
data/
  submissions/       Imported package data and copied label images
  preprocessed/      Extraction, evidence, results, timing, and rule versions
  decisions/         Officer decisions and reasons
  errors/            Terminal processing-error artifacts
  staging/           Temporary publication files
```

## Limitations

- Physical type size requires calibrated evidence; uncertain presentation is
  sent to human review.
- The demo identity is not an authentication or authorization mechanism.
- The standalone prototype boundary excludes applicant PII and direct COLAs
  Online integration.
- The prototype assists a reviewer; the officer makes the legal determination.

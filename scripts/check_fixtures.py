import sys
from pathlib import Path

from backend.app.models import SubmissionCreate

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "intake"
ALLOWED = {".png", ".jpg", ".jpeg", ".webp", ".svg"}


def main() -> int:
    errors: list[str] = []
    referenced: set[str] = set()
    for manifest in sorted(FIXTURES.glob("*.json")):
        try:
            submission = SubmissionCreate.model_validate_json(manifest.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{manifest.name}: invalid manifest: {exc}")
            continue
        for application in submission.applications:
            for filename in application.image_filenames:
                referenced.add(filename)
                path = FIXTURES / filename
                if path.suffix.casefold() not in ALLOWED:
                    errors.append(f"{filename}: unsupported file type")
                if not path.is_file():
                    errors.append(f"{filename}: missing")
    available = {
        path.name
        for path in FIXTURES.iterdir()
        if path.is_file() and path.suffix.casefold() in ALLOWED
    }
    for filename in sorted(available - referenced):
        errors.append(f"{filename}: unreferenced image")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Fixture validation passed: {len(referenced)} images referenced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import sys
from pathlib import Path

from PIL import Image

from backend.app.models import SubmissionCreate

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_SETS = (
    ROOT / "fixtures" / "intake",
    ROOT / "fixtures" / "evaluation-real",
)
ALLOWED = {".png", ".jpg", ".jpeg", ".webp", ".svg"}


def validate_fixture_set(directory: Path) -> tuple[list[str], int]:
    errors: list[str] = []
    referenced: set[str] = set()
    for manifest in sorted(directory.glob("*.json")):
        try:
            submission = SubmissionCreate.model_validate_json(manifest.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{manifest.relative_to(ROOT)}: invalid manifest: {exc}")
            continue
        for application in submission.applications:
            for filename in application.image_filenames:
                referenced.add(filename)
                path = directory / filename
                if path.suffix.casefold() not in ALLOWED:
                    errors.append(f"{filename}: unsupported file type")
                if not path.is_file():
                    errors.append(f"{filename}: missing")
    available = {
        path.name
        for path in directory.iterdir()
        if path.is_file() and path.suffix.casefold() in ALLOWED
    }
    for filename in sorted(available - referenced):
        errors.append(f"{directory.relative_to(ROOT)}/{filename}: unreferenced image")

    for filename in sorted(available):
        path = directory / filename
        if path.suffix.casefold() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        try:
            with Image.open(path) as image:
                if image.getexif():
                    errors.append(f"{path.relative_to(ROOT)}: EXIF metadata is present")
        except Exception as exc:
            errors.append(f"{path.relative_to(ROOT)}: cannot inspect metadata: {exc}")
    return errors, len(referenced)


def main() -> int:
    errors: list[str] = []
    referenced_count = 0
    for directory in FIXTURE_SETS:
        fixture_errors, count = validate_fixture_set(directory)
        errors.extend(fixture_errors)
        referenced_count += count
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Fixture validation passed: {referenced_count} images referenced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

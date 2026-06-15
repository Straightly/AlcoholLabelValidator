import json
import os
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from .models import DecisionArtifact, ReviewPackage, SubmissionArtifact


class ArtifactExistsError(Exception):
    pass


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        for name in ("submissions", "preprocessed", "decisions", "staging"):
            (root / name).mkdir(parents=True, exist_ok=True)

    def _write_once(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        staging = self.root / "staging" / f"{path.parent.name}-{path.name}.{uuid4().hex}.tmp"
        claim = path.with_name(f".{path.name}.publish-lock")
        claim_acquired = False

        try:
            with staging.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, default=str)
                handle.flush()
                os.fsync(handle.fileno())

            # Directory creation is an atomic, cross-platform claim operation.
            claim.mkdir()
            claim_acquired = True
            if path.exists():
                raise ArtifactExistsError(str(path))

            # Staging and destination share a filesystem, so replace publishes atomically.
            os.replace(staging, path)
        except FileExistsError as exc:
            raise ArtifactExistsError(str(path)) from exc
        finally:
            staging.unlink(missing_ok=True)
            if claim_acquired:
                claim.rmdir()

    def save_submission(self, artifact: SubmissionArtifact) -> None:
        path = self.root / "submissions" / artifact.submission_id / "submission.json"
        self._write_once(path, artifact.model_dump(mode="json"))

    def import_images(self, submission_id: str, source_dir: Path, filenames: list[str]) -> None:
        target = self.root / "submissions" / submission_id / "images"
        target.mkdir(parents=True, exist_ok=True)
        for filename in filenames:
            source = source_dir / filename
            if not source.is_file():
                continue
            destination = target / filename
            if destination.exists():
                continue
            shutil.copy2(source, destination)
            sidecar = source.with_suffix(source.suffix + ".ocr.txt")
            if sidecar.is_file():
                shutil.copy2(sidecar, destination.with_suffix(destination.suffix + ".ocr.txt"))

    def image_dir(self, submission_id: str) -> Path:
        return self.root / "submissions" / submission_id / "images"

    def save_review(self, artifact: ReviewPackage) -> None:
        path = (
            self.root
            / "preprocessed"
            / artifact.submission_id
            / f"{artifact.application_id}.json"
        )
        self._write_once(path, artifact.model_dump(mode="json"))

    def save_decision(self, artifact: DecisionArtifact) -> None:
        path = (
            self.root
            / "decisions"
            / artifact.submission_id
            / f"{artifact.application_id}.json"
        )
        self._write_once(path, artifact.model_dump(mode="json"))

    def read_json(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def get_submission(self, submission_id: str) -> dict[str, Any]:
        return self.read_json(self.root / "submissions" / submission_id / "submission.json")

    def list_submissions(self) -> list[dict[str, Any]]:
        paths = sorted((self.root / "submissions").glob("*/submission.json"))
        return [self.read_json(path) for path in paths]

    def list_reviews(self) -> list[dict[str, Any]]:
        paths = sorted((self.root / "preprocessed").glob("*/*.json"))
        return [self.read_json(path) for path in paths]

    def get_review(self, submission_id: str, application_id: str) -> dict[str, Any]:
        return self.read_json(
            self.root / "preprocessed" / submission_id / f"{application_id}.json"
        )

    def get_decision(self, submission_id: str, application_id: str) -> dict[str, Any] | None:
        path = self.root / "decisions" / submission_id / f"{application_id}.json"
        return self.read_json(path) if path.exists() else None

    def clear_decisions(self) -> None:
        path = self.root / "decisions"
        shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True, exist_ok=True)

    def reset(self) -> None:
        for name in ("submissions", "preprocessed", "decisions", "staging"):
            path = self.root / name
            shutil.rmtree(path, ignore_errors=True)
            path.mkdir(parents=True, exist_ok=True)

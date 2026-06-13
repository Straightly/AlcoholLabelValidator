import json
import os
from pathlib import Path
from typing import Any

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
        staging = self.root / "staging" / f"{path.parent.name}-{path.name}.{os.getpid()}.tmp"
        staging.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        try:
            os.link(staging, path)
        except FileExistsError as exc:
            raise ArtifactExistsError(str(path)) from exc
        finally:
            staging.unlink(missing_ok=True)

    def save_submission(self, artifact: SubmissionArtifact) -> None:
        path = self.root / "submissions" / artifact.submission_id / "submission.json"
        self._write_once(path, artifact.model_dump(mode="json"))

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


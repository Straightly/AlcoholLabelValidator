import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .analysis import analyze_application
from .models import DecisionArtifact, DecisionCreate, SubmissionArtifact, SubmissionCreate
from .store import ArtifactExistsError, ArtifactStore


def create_app(
    data_dir: Path | None = None,
    fixture_dir: Path | None = None,
) -> FastAPI:
    app = FastAPI(title="Alcohol Label Validator API", version="0.1.0")
    root = data_dir or Path(os.getenv("ALV_DATA_DIR", "./data"))
    intake = fixture_dir or Path(
        os.getenv(
            "ALV_FIXTURE_DIR",
            str(Path(__file__).resolve().parents[2] / "fixtures" / "intake"),
        )
    )
    store = ArtifactStore(root)
    app.state.store = store
    app.state.fixture_dir = intake

    origins = os.getenv(
        "ALV_ALLOWED_ORIGINS",
        "http://localhost:5174",
    ).split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/demo/process-sample-intake")
    def process_sample_intake() -> dict[str, int]:
        result = {
            "packages_found": 0,
            "packages_imported": 0,
            "packages_skipped": 0,
            "applications_preprocessed": 0,
        }
        for path in sorted(intake.glob("*.json")):
            result["packages_found"] += 1
            payload = SubmissionCreate.model_validate_json(path.read_text(encoding="utf-8"))
            artifact = SubmissionArtifact(**payload.model_dump())
            try:
                store.save_submission(artifact)
            except ArtifactExistsError:
                result["packages_skipped"] += 1
                continue
            result["packages_imported"] += 1
            for application in artifact.applications:
                store.save_review(analyze_application(artifact, application))
                result["applications_preprocessed"] += 1
        return result

    @app.post("/api/submissions", status_code=201)
    def create_submission(payload: SubmissionCreate) -> dict[str, object]:
        artifact = SubmissionArtifact(**payload.model_dump())
        try:
            store.save_submission(artifact)
            for application in artifact.applications:
                store.save_review(analyze_application(artifact, application))
        except ArtifactExistsError as exc:
            raise HTTPException(status_code=409, detail="Artifact already exists.") from exc
        return submission_view(store, artifact.model_dump(mode="json"))

    @app.get("/api/submissions")
    def list_submissions(source_label: str | None = None) -> list[dict[str, object]]:
        submissions = store.list_submissions()
        if source_label:
            submissions = [
                item for item in submissions if item["source_label"] == source_label
            ]
        return [submission_view(store, item) for item in submissions]

    @app.get("/api/review-queue")
    def review_queue() -> list[dict[str, object]]:
        queue = []
        for review in store.list_reviews():
            if not store.get_decision(review["submission_id"], review["application_id"]):
                queue.append(review)
        return queue

    @app.get("/api/reviews/{submission_id}/{application_id}")
    def get_review(submission_id: str, application_id: str) -> dict[str, object]:
        try:
            review = store.get_review(submission_id, application_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Review package not found.") from exc
        review["decision"] = store.get_decision(submission_id, application_id)
        return review

    @app.post("/api/reviews/{submission_id}/{application_id}/decision", status_code=201)
    def create_decision(
        submission_id: str,
        application_id: str,
        payload: DecisionCreate,
    ) -> dict[str, object]:
        try:
            store.get_review(submission_id, application_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Review package not found.") from exc
        artifact = DecisionArtifact(
            **payload.model_dump(),
            submission_id=submission_id,
            application_id=application_id,
        )
        try:
            store.save_decision(artifact)
        except ArtifactExistsError as exc:
            raise HTTPException(status_code=409, detail="A decision already exists.") from exc
        return artifact.model_dump(mode="json")

    return app


def submission_view(store: ArtifactStore, submission: dict[str, object]) -> dict[str, object]:
    applications = []
    completed = 0
    for application in submission["applications"]:
        application_id = application["application_id"]
        decision = store.get_decision(str(submission["submission_id"]), application_id)
        status = "Completed" if decision else "Preprocessed"
        completed += int(decision is not None)
        applications.append(
            {
                "application_id": application_id,
                "status": status,
                "decision": decision,
            }
        )
    aggregate = "Completed" if completed == len(applications) else (
        "In Review" if completed else "Ready For Review"
    )
    return {
        **submission,
        "status": aggregate,
        "completed_application_count": completed,
        "applications": applications,
    }


app = create_app()

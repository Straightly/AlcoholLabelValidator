import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from .analysis import analyze_application
from .intake_jobs import IntakeJobRunner
from .models import DecisionArtifact, DecisionCreate, SubmissionArtifact, SubmissionCreate
from .store import ArtifactExistsError, ArtifactStore
from .vision import LocalVisionEngine

ROOT_DIR = Path(__file__).resolve().parents[2]


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 120, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.history: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/"):
            client_ip = request.client.host if request.client else "unknown"
            now = time.time()
            timestamps = self.history.get(client_ip, [])
            timestamps = [t for t in timestamps if now - t < self.window_seconds]
            if len(timestamps) >= self.max_requests:
                return Response(
                    content="Rate limit exceeded. Try again later.",
                    status_code=429,
                )
            timestamps.append(now)
            self.history[client_ip] = timestamps

        if request.method in {"POST", "PUT"}:
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    size = int(content_length)
                    if size > 20 * 1024 * 1024:  # 20 MB payload limit
                        return Response(
                            content="Payload too large. Max allowed is 20 MB.",
                            status_code=413,
                        )
                except ValueError:
                    pass

        return await call_next(request)


def create_app(
    data_dir: Path | None = None,
    fixture_dir: Path | None = None,
) -> FastAPI:
    root = data_dir or Path(os.getenv("ALV_DATA_DIR", "./data"))
    intake = fixture_dir or Path(
        os.getenv("ALV_FIXTURE_DIR", str(ROOT_DIR / "fixtures" / "evaluation-real"))
    )
    store = ArtifactStore(root)
    vision = LocalVisionEngine()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        vision.prepare()
        yield

    app = FastAPI(title="Alcohol Label Validator API", version="1.0.0", lifespan=lifespan)
    app.state.store = store
    app.state.fixture_dir = intake
    app.state.vision = vision

    def sample_intake_packages() -> list[Path]:
        return sorted(
            path
            for path in intake.glob("*.json")
            if path.is_file() and not path.name.startswith(".")
        )

    def import_and_preprocess_sample_intake() -> dict[str, int]:
        result = {
            "packages_found": 0,
            "packages_imported": 0,
            "packages_skipped": 0,
            "applications_preprocessed": 0,
            "applications_needing_manual_review": 0,
        }
        for path in sample_intake_packages():
            result["packages_found"] += 1
            try:
                payload = SubmissionCreate.model_validate_json(path.read_text(encoding="utf-8"))
            except Exception:
                result["packages_skipped"] += 1
                continue
            artifact = SubmissionArtifact(**payload.model_dump())
            try:
                store.save_submission(artifact)
            except ArtifactExistsError:
                result["packages_skipped"] += 1
                continue
            image_names = [name for item in artifact.applications for name in item.image_filenames]
            store.import_images(artifact.submission_id, path.parent, image_names)
            result["packages_imported"] += 1
            for application in artifact.applications:
                review = analyze_application(
                    artifact,
                    application,
                    store.image_dir(artifact.submission_id),
                    vision,
                )
                store.save_review(review)
                result["applications_preprocessed"] += 1
                result["applications_needing_manual_review"] += int(review.processing_error is not None)
        return result

    intake_jobs = IntakeJobRunner(import_and_preprocess_sample_intake)
    app.state.intake_jobs = intake_jobs

    origins = os.getenv("ALV_ALLOWED_ORIGINS", "http://localhost:5174").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RateLimitMiddleware, max_requests=120, window_seconds=60)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/ready")
    def ready() -> dict[str, object]:
        return {
            "status": "ready" if vision.ready else "initializing",
            "ready": vision.ready,
            "engine": vision.engine_name,
            "detail": vision.detail,
        }

    @app.get("/api/demo/process-sample-intake")
    def sample_intake_status() -> dict[str, object]:
        return intake_jobs.status()

    @app.post("/api/demo/process-sample-intake", status_code=202)
    def process_sample_intake() -> dict[str, object]:
        started, status = intake_jobs.start()
        return {
            **status,
            "started": started,
        }

    @app.post("/api/demo/reset")
    def reset_demo() -> dict[str, str]:
        store.reset()
        intake_jobs.reset()
        return {"status": "reset"}

    @app.post("/api/demo/refresh-queue")
    def refresh_demo_queue() -> dict[str, object]:
        store.clear_decisions()
        return {
            "status": "queue-restored",
            "message": "All preprocessed sample applications have been returned to the review queue.",
        }

    @app.post("/api/submissions", status_code=201)
    def create_submission(payload: SubmissionCreate) -> dict[str, object]:
        artifact = SubmissionArtifact(**payload.model_dump())
        try:
            store.save_submission(artifact)
            store.import_images(
                artifact.submission_id,
                intake,
                [name for item in artifact.applications for name in item.image_filenames],
            )
            for application in artifact.applications:
                store.save_review(
                    analyze_application(
                        artifact,
                        application,
                        store.image_dir(artifact.submission_id),
                        vision,
                    )
                )
        except ArtifactExistsError as exc:
            raise HTTPException(status_code=409, detail="Artifact already exists.") from exc
        return submission_view(store, artifact.model_dump(mode="json"))

    @app.get("/api/images/{submission_id}/{filename}")
    def get_image(submission_id: str, filename: str) -> FileResponse:
        if filename != Path(filename).name:
            raise HTTPException(status_code=400, detail="Invalid image filename.")
        path = store.image_dir(submission_id) / filename
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Image not found.")
        return FileResponse(path)

    @app.get("/api/submissions")
    def list_submissions(source_label: str | None = None) -> list[dict[str, object]]:
        submissions = store.list_submissions()
        if source_label:
            submissions = [item for item in submissions if item["source_label"] == source_label]
        return [submission_view(store, item) for item in submissions]

    @app.get("/api/review-queue")
    def review_queue() -> list[dict[str, object]]:
        return [
            review
            for review in store.list_reviews()
            if not store.get_decision(review["submission_id"], review["application_id"])
        ]

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
            review = store.get_review(submission_id, application_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Review package not found.") from exc
        unresolved = any(item["result"] != "Match" for item in review["findings"])
        if payload.decision == "Approved" and unresolved and not payload.override_note:
            raise HTTPException(
                status_code=422,
                detail="An override note is required to approve unresolved findings.",
            )
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

    frontend = ROOT_DIR / "portals" / "officer" / "dist"
    if frontend.is_dir():
        assets = frontend / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def frontend_app(path: str) -> FileResponse:
            candidate = frontend / path
            return FileResponse(candidate if candidate.is_file() else frontend / "index.html")

    return app


def submission_view(store: ArtifactStore, submission: dict[str, object]) -> dict[str, object]:
    applications = []
    completed = 0
    for application in submission["applications"]:
        application_id = application["application_id"]
        decision = store.get_decision(str(submission["submission_id"]), application_id)
        try:
            review = store.get_review(str(submission["submission_id"]), application_id)
            status = "Completed" if decision else (
                "Needs Attention" if review.get("processing_error") else "Ready For Review"
            )
        except FileNotFoundError:
            status = "Processing"
        completed += int(decision is not None)
        applications.append(
            {"application_id": application_id, "status": status, "decision": decision}
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

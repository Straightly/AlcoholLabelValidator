import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app


def isolated_fixture_dir(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[2] / "fixtures" / "intake"
    destination = tmp_path / "test-fixtures"
    destination.mkdir()
    for path in source.iterdir():
        if path.is_file() and not path.name.startswith("."):
            shutil.copy2(path, destination / path.name)
    return destination


def sample_submission() -> dict:
    return {
        "submission_id": "submission-001",
        "source_label": "Synthetic direct-entry demo",
        "submission_type": "single",
        "applications": [
            {
                "application_id": "application-001",
                "beverage_category": "distilled_spirits",
                "fields": {
                    "brand_name": "OLD TOM DISTILLERY",
                    "class_type": "Kentucky Straight Bourbon Whiskey",
                    "alcohol_content": "45% Alc./Vol. (90 Proof)",
                    "net_contents": "750 mL",
                    "producer_name_address": "Old Tom Distillery, Louisville, Kentucky",
                },
                "image_filenames": [
                    "sample-compliant-front.png",
                    "sample-compliant-back.png",
                ],
            }
        ],
    }


def test_submit_review_decide_flow(tmp_path: Path) -> None:
    fixture_dir = isolated_fixture_dir(tmp_path)
    client = TestClient(create_app(tmp_path, fixture_dir))

    with client:
        created = client.post("/api/submissions", json=sample_submission())
        assert created.status_code == 201
        assert created.json()["status"] == "Ready For Review"

        queue = client.get("/api/review-queue")
        assert queue.status_code == 200
        assert len(queue.json()) == 1
        assert len(queue.json()[0]["images"]) == 2
        assert all(item["result"] == "Match" for item in queue.json()[0]["findings"])

        decision = client.post(
            "/api/reviews/submission-001/application-001/decision",
            json={
                "decision": "Approved",
                "public_reason": "All implemented checks match the supplied evidence.",
                "officer_name": "Demo Compliance Officer",
            },
        )
        assert decision.status_code == 201

        submissions = client.get(
            "/api/submissions",
            params={"source_label": "Synthetic direct-entry demo"},
        )
        assert submissions.json()[0]["status"] == "Completed"
        assert submissions.json()[0]["applications"][0]["decision"]["decision"] == "Approved"

        duplicate = client.post(
            "/api/reviews/submission-001/application-001/decision",
            json={
                "decision": "Rejected",
                "public_reason": "This second decision must not overwrite the first.",
                "officer_name": "Another Officer",
            },
        )
        assert duplicate.status_code == 409

        preserved = client.get(
            "/api/submissions",
            params={"source_label": "Synthetic direct-entry demo"},
        )
        assert preserved.json()[0]["applications"][0]["decision"]["decision"] == "Approved"
    assert not list(tmp_path.rglob("*.publish-lock"))
    assert not list((tmp_path / "staging").glob("*.tmp"))


def test_process_sample_intake_is_idempotent(tmp_path: Path) -> None:
    fixture_dir = isolated_fixture_dir(tmp_path)
    with TestClient(create_app(tmp_path, fixture_dir)) as client:
        assert client.get("/api/ready").json()["ready"] is True
        first = client.post("/api/demo/process-sample-intake")
        assert first.status_code == 200
        assert first.json() == {
            "packages_found": 1,
            "packages_imported": 1,
            "packages_skipped": 0,
            "applications_preprocessed": 2,
            "applications_with_errors": 0,
        }
        queue = client.get("/api/review-queue").json()
        assert len(queue) == 2
        attention = next(item for item in queue if "attention" in item["application_id"])
        assert any(item["result"] == "Mismatch" for item in attention["findings"])

        second = client.post("/api/demo/process-sample-intake")
        assert second.status_code == 200
        assert second.json()["packages_skipped"] == 1

        assert client.post("/api/demo/reset").status_code == 200
        assert client.get("/api/review-queue").json() == []


def test_approval_requires_override_for_unresolved_findings(tmp_path: Path) -> None:
    fixture_dir = isolated_fixture_dir(tmp_path)
    with TestClient(create_app(tmp_path, fixture_dir)) as client:
        client.post("/api/demo/process-sample-intake")
        review = next(
            item
            for item in client.get("/api/review-queue").json()
            if "attention" in item["application_id"]
        )
        url = f"/api/reviews/{review['submission_id']}/{review['application_id']}/decision"
        denied = client.post(
            url,
            json={
                "decision": "Approved",
                "public_reason": "Officer accepts the submitted evidence.",
                "officer_name": "Demo Compliance Officer",
            },
        )
        assert denied.status_code == 422
        accepted = client.post(
            url,
            json={
                "decision": "Approved",
                "public_reason": "Officer accepts the submitted evidence.",
                "officer_name": "Demo Compliance Officer",
                "override_note": "Reviewed the original image manually.",
            },
        )
        assert accepted.status_code == 201


def test_frontend_and_images_are_served_by_fastapi(tmp_path: Path) -> None:
    fixture_dir = Path(__file__).resolve().parents[2] / "fixtures" / "intake"
    with TestClient(create_app(tmp_path, fixture_dir)) as client:
        assert client.get("/").status_code == 200
        client.post("/api/demo/process-sample-intake")
        image = client.get("/api/images/sample-intake-001/sample-compliant-front.png")
        assert image.status_code == 200
        assert image.headers["content-type"].startswith("image/png")

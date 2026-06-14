from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.analysis import HEALTH_WARNING
from backend.app.main import create_app


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
                "image_filenames": ["front.png", "back.png"],
                "label_text": (
                    "OLD TOM DISTILLERY Kentucky Straight Bourbon Whiskey "
                    "45% Alc./Vol. (90 Proof) 750 mL "
                    "Old Tom Distillery, Louisville, Kentucky "
                    f"{HEALTH_WARNING}"
                ),
            }
        ],
    }


def test_submit_review_decide_flow(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))

    created = client.post("/api/submissions", json=sample_submission())
    assert created.status_code == 201
    assert created.json()["status"] == "Ready For Review"

    queue = client.get("/api/review-queue")
    assert queue.status_code == 200
    assert len(queue.json()) == 1
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
    fixture_dir = Path(__file__).resolve().parents[2] / "fixtures" / "intake"
    client = TestClient(create_app(tmp_path, fixture_dir))

    first = client.post("/api/demo/process-sample-intake")
    assert first.status_code == 200
    assert first.json() == {
        "packages_found": 1,
        "packages_imported": 1,
        "packages_skipped": 0,
        "applications_preprocessed": 2,
    }
    assert len(client.get("/api/review-queue").json()) == 2

    second = client.post("/api/demo/process-sample-intake")
    assert second.status_code == 200
    assert second.json() == {
        "packages_found": 1,
        "packages_imported": 0,
        "packages_skipped": 1,
        "applications_preprocessed": 0,
    }

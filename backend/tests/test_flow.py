import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.analysis import compare_field, warning_finding
from backend.app.main import create_app
from backend.app.models import CheckResult


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


def wait_for_sample_intake(client: TestClient, timeout_seconds: float = 5.0) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        status = client.get("/api/demo/process-sample-intake")
        assert status.status_code == 200
        body = status.json()
        if body["state"] in {"completed", "failed", "idle"}:
            return body
        time.sleep(0.05)
    raise AssertionError("Timed out waiting for sample intake background job.")


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
        assert first.status_code == 202
        assert first.json()["state"] == "running"
        completed = wait_for_sample_intake(client)
        assert completed | {"started": True} == {
            "state": "completed",
            "message": (
                "Background preprocessing completed. Refresh the queue to review new applications. "
                "This simulates AI image processing of submitted applications. In production, "
                "all submitted applications would be pre-processed before compliance officers "
                "view and process them, so the background work would not slow officers down at all."
            ),
            "started_at": completed["started_at"],
            "finished_at": completed["finished_at"],
            "packages_found": 1,
            "packages_imported": 1,
            "packages_skipped": 0,
            "applications_preprocessed": 2,
            "applications_needing_manual_review": 0,
            "started": True,
        }
        queue = client.get("/api/review-queue").json()
        assert len(queue) == 2
        attention = next(item for item in queue if "attention" in item["application_id"])
        assert any(item["result"] == "Missing" for item in attention["findings"])

        second = client.post("/api/demo/process-sample-intake")
        assert second.status_code == 202
        second_complete = wait_for_sample_intake(client)
        assert second_complete["packages_skipped"] == 1

        assert client.post("/api/demo/reset").status_code == 200
        assert client.get("/api/review-queue").json() == []


def test_process_sample_intake_ignores_user_working_files(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    source = Path(__file__).resolve().parents[2] / "fixtures" / "intake"
    shutil.copy2(source / "sample-distilled-spirits-batch.json", fixture_dir / "sample-distilled-spirits-batch.json")
    for image_name in (
        "sample-compliant-front.png",
        "sample-compliant-back.png",
        "sample-attention-front.png",
        "sample-attention-back.png",
    ):
        shutil.copy2(source / image_name, fixture_dir / image_name)
        shutil.copy2(source / f"{image_name}.ocr.txt", fixture_dir / f"{image_name}.ocr.txt")

    user_dir = fixture_dir / "user"
    user_dir.mkdir()
    (user_dir / "single-submission-bad.json").write_text('{"not":"a valid submission"}', encoding="utf-8")

    with TestClient(create_app(tmp_path, fixture_dir)) as client:
        client.post("/api/demo/process-sample-intake")
        completed = wait_for_sample_intake(client)
        assert completed["packages_found"] == 1
        assert completed["packages_imported"] == 1
        assert completed["packages_skipped"] == 0
        assert completed["applications_preprocessed"] == 2


def test_process_sample_intake_imports_all_top_level_packages(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    source = Path(__file__).resolve().parents[2] / "fixtures" / "evaluation-real"
    for name in (
        "real-bottle-evaluation-batch.json",
        "single-submission-canada.json",
        "crown-royal-reserve-front.jpg",
        "crown-royal-reserve-back.jpg",
        "glenlivet-good-front.jpg",
        "glenlivet-good-back.jpg",
        "glenlivet-bad-front1.jpg",
        "glenlivet-bad-front2.jpg",
        "glenlivet-bad-back1.jpg",
        "red-blend-portugal-good-front.jpg",
        "red-blend-portugal-good-back.jpg",
        "red-blend-portugal-skewed-back.jpg",
        "sample-compliant-front.png",
        "sample-compliant-back.png",
        "sample-compliant-front.png.ocr.txt",
        "sample-compliant-back.png.ocr.txt",
    ):
        shutil.copy2(source / name, fixture_dir / name)

    with TestClient(create_app(tmp_path, fixture_dir)) as client:
        client.post("/api/demo/process-sample-intake")
        completed = wait_for_sample_intake(client)
        assert completed["packages_found"] == 2
        assert completed["packages_imported"] == 2
        assert completed["packages_skipped"] == 0
        assert completed["applications_preprocessed"] == 8
        assert len(client.get("/api/review-queue").json()) == 8



def test_approval_requires_override_for_unresolved_findings(tmp_path: Path) -> None:
    fixture_dir = isolated_fixture_dir(tmp_path)
    with TestClient(create_app(tmp_path, fixture_dir)) as client:
        client.post("/api/demo/process-sample-intake")
        wait_for_sample_intake(client)
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


def test_refresh_queue_restores_preprocessed_samples(tmp_path: Path) -> None:
    fixture_dir = isolated_fixture_dir(tmp_path)
    with TestClient(create_app(tmp_path, fixture_dir)) as client:
        client.post("/api/demo/process-sample-intake")
        wait_for_sample_intake(client)
        original_queue = client.get("/api/review-queue").json()
        assert len(original_queue) == 2

        first = next(
            item for item in original_queue if all(finding["result"] == "Match" for finding in item["findings"])
        )
        decision = client.post(
            f"/api/reviews/{first['submission_id']}/{first['application_id']}/decision",
            json={
                "decision": "Approved",
                "public_reason": "All implemented checks match the supplied evidence.",
                "officer_name": "Demo Compliance Officer",
            },
        )
        assert decision.status_code == 201
        assert len(client.get("/api/review-queue").json()) == 1

        restored = client.post("/api/demo/refresh-queue")
        assert restored.status_code == 200
        assert restored.json()["status"] == "queue-restored"

        queue_after_restore = client.get("/api/review-queue").json()
        assert len(queue_after_restore) == 2
        assert {
            item["application_id"] for item in queue_after_restore
        } == {item["application_id"] for item in original_queue}


def test_frontend_and_images_are_served_by_fastapi(tmp_path: Path) -> None:
    fixture_dir = Path(__file__).resolve().parents[2] / "fixtures" / "intake"
    frontend = Path(__file__).resolve().parents[2] / "portals" / "officer" / "dist" / "index.html"
    if not frontend.is_file():
        pytest.skip("Frontend build artifacts are not present.")
    with TestClient(create_app(tmp_path, fixture_dir)) as client:
        assert client.get("/").status_code == 200
        client.post("/api/demo/process-sample-intake")
        wait_for_sample_intake(client)
        image = client.get("/api/images/sample-intake-001/sample-compliant-front.png")
        assert image.status_code == 200
        assert image.headers["content-type"].startswith("image/png")


def test_partial_warning_text_fails() -> None:
    finding = warning_finding(
        "GOVERNMENT WARNING: (1) ACCORDING TO THE SURGEON GENERAL",
        0.99,
    )
    assert finding.result == "Missing"


def test_rate_limiting_middleware(tmp_path: Path) -> None:
    fixture_dir = isolated_fixture_dir(tmp_path)
    app = create_app(tmp_path, fixture_dir)
    with TestClient(app) as client:
        responses = [client.get("/api/health") for _ in range(130)]
        status_codes = [r.status_code for r in responses]
        assert 200 in status_codes
        assert 429 in status_codes


def test_payload_size_limit(tmp_path: Path) -> None:
    fixture_dir = isolated_fixture_dir(tmp_path)
    app = create_app(tmp_path, fixture_dir)
    with TestClient(app) as client:
        response = client.post(
            "/api/submissions",
            headers={"content-length": str(30 * 1024 * 1024)},
            content=b"x" * 100,
        )
        assert response.status_code == 413


def test_smart_compare_field_normalizations() -> None:
    # Test volume abbreviation normalization
    finding_vol = compare_field(
        "net_contents",
        "750 Milliliters",
        "750 mL",
        1.0,
        False,
    )
    assert finding_vol.result == CheckResult.MATCH

    finding_vol2 = compare_field(
        "net_contents",
        "1 Liter",
        "1 L",
        1.0,
        False,
    )
    assert finding_vol2.result == CheckResult.MATCH

    # Test address abbreviation & state abbreviation normalization
    finding_addr = compare_field(
        "producer_name_address",
        "Old Tom Distillery, Louisville, Kentucky",
        "Old Tom Distillery, Louisville, KY",
        1.0,
        False,
    )
    assert finding_addr.result == CheckResult.MATCH

    finding_addr2 = compare_field(
        "producer_name_address",
        "123 Main Street, California",
        "123 Main St, CA",
        1.0,
        False,
    )
    assert finding_addr2.result == CheckResult.MATCH

    # Test compass direction and business normalizations
    finding_addr3 = compare_field(
        "producer_name_address",
        "123 North Main Street, Old Tom Distilling Company Incorporated",
        "123 N Main St, Old Tom Distilling Co. Inc.",
        1.0,
        False,
    )
    assert finding_addr3.result == CheckResult.MATCH

    # Test volume equivalency (750 ml == 0.75 l)
    finding_vol_eq = compare_field(
        "net_contents",
        "750 ml",
        "0.75 L",
        1.0,
        False,
    )
    assert finding_vol_eq.result == CheckResult.MATCH

    finding_vol_eq2 = compare_field(
        "net_contents",
        "1.75 Liters",
        "1750 mL",
        1.0,
        False,
    )
    assert finding_vol_eq2.result == CheckResult.MATCH

    # Test float-based alcohol/proof matching
    finding_alc = compare_field(
        "alcohol_content",
        "45% Alc./Vol. (90 Proof)",
        "45.0% alc/vol 90.0 proof",
        1.0,
        False,
    )
    assert finding_alc.result == CheckResult.MATCH

    # Test country of origin synonym normalizations
    finding_country = compare_field(
        "country_of_origin",
        "United States of America",
        "Product of U.S.A.",
        1.0,
        False,
    )
    assert finding_country.result == CheckResult.MATCH

    finding_country2 = compare_field(
        "country_of_origin",
        "United Kingdom",
        "Made in the U.K.",
        1.0,
        False,
    )
    assert finding_country2.result == CheckResult.MATCH



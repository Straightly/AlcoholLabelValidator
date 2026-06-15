import argparse
import statistics
import tempfile
import time
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app

ROOT = Path(__file__).resolve().parents[1]


def wait_for_sample_intake(client: TestClient, timeout_seconds: float = 300.0) -> dict[str, object]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = client.get("/api/demo/process-sample-intake")
        response.raise_for_status()
        status = response.json()
        if status["state"] in {"completed", "failed"}:
            return status
        time.sleep(0.25)
    raise TimeoutError("Timed out waiting for background sample preprocessing to finish.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate label-review fixtures.")
    parser.add_argument("--max-ms", type=int, default=5000)
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=ROOT / "fixtures" / "intake",
        help="Directory containing fixture manifests and images.",
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="Print OCR evidence and image-quality measurements for every image.",
    )
    args = parser.parse_args()
    fixture_dir = args.fixture_dir.resolve()
    with tempfile.TemporaryDirectory() as directory:
        with TestClient(create_app(Path(directory), fixture_dir)) as client:
            response = client.post("/api/demo/process-sample-intake")
            response.raise_for_status()
            status = wait_for_sample_intake(client)
            if status["state"] != "completed":
                print(f"Sample preprocessing failed: {status['message']}")
                return 1
            reviews = client.get("/api/review-queue").json()
    durations = [item["processing_duration_ms"] for item in reviews]
    findings = [finding for item in reviews for finding in item["findings"]]
    result_counts = {
        result: sum(finding["result"] == result for finding in findings)
        for result in ("Match", "Mismatch", "Needs Human Review")
    }
    actual_matches = sum(all(f["result"] == "Match" for f in item["findings"]) for item in reviews)
    generated_set = fixture_dir == (ROOT / "fixtures" / "intake").resolve()
    expected_matches = (
        sum(item["application_id"].startswith("sample-compliant") for item in reviews)
        if generated_set
        else None
    )
    print(f"Fixture directory: {fixture_dir}")
    print(f"Applications: {len(reviews)}")
    if expected_matches is not None:
        print(f"Expected fully matching: {expected_matches}; actual: {actual_matches}")
    else:
        print(f"Fully matching: {actual_matches}")
    print(f"Findings: {len(findings)}")
    print(
        "Finding results: "
        + ", ".join(f"{result}={count}" for result, count in result_counts.items())
    )
    for review in reviews:
        failed = [
            f"{item['field_name']}={item['result']}"
            for item in review["findings"]
            if item["result"] != "Match"
        ]
        print(
            f"{review['application_id']} ({review['processing_duration_ms']} ms): "
            f"{', '.join(failed) if failed else 'all implemented checks match'}"
        )
        if failed or args.details:
            for image in review["images"]:
                print(
                    f"  {image['filename']}: confidence={image['confidence']:.3f}, "
                    f"size={image['width']}x{image['height']}, "
                    f"blur={image['blur_score']}, glare={image['glare_ratio']}, "
                    f"flags={image['quality_flags']}"
                )
                print(f"    OCR: {image['extracted_text']!r}")
    print(f"Median: {statistics.median(durations):.1f} ms")
    ordered = sorted(durations)
    p95_index = max(0, round(0.95 * len(ordered) + 0.5) - 1)
    print(f"P95: {ordered[p95_index]:.1f} ms")
    print(f"Slowest: {max(durations)} ms")
    print(
        f"Timing threshold ({args.max_ms} ms): "
        f"{'within threshold' if max(durations) < args.max_ms else 'above threshold'}"
    )
    accuracy_failed = expected_matches is not None and expected_matches != actual_matches
    return int(accuracy_failed)


if __name__ == "__main__":
    raise SystemExit(main())

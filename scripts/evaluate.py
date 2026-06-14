import argparse
import statistics
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate seeded label-review fixtures.")
    parser.add_argument("--max-ms", type=int, default=5000)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        with TestClient(create_app(Path(directory), ROOT / "fixtures" / "intake")) as client:
            response = client.post("/api/demo/process-sample-intake")
            response.raise_for_status()
            reviews = client.get("/api/review-queue").json()
    durations = [item["processing_duration_ms"] for item in reviews]
    findings = [finding for item in reviews for finding in item["findings"]]
    expected_matches = sum(item["application_id"].startswith("sample-compliant") for item in reviews)
    actual_matches = sum(all(f["result"] == "Match" for f in item["findings"]) for item in reviews)
    print(f"Applications: {len(reviews)}")
    print(f"Expected fully matching: {expected_matches}; actual: {actual_matches}")
    print(f"Findings: {len(findings)}")
    for review in reviews:
        failed = [
            f"{item['field_name']}={item['result']}"
            for item in review["findings"]
            if item["result"] != "Match"
        ]
        print(
            f"{review['application_id']}: "
            f"{', '.join(failed) if failed else 'all implemented checks match'}"
        )
        if failed:
            for image in review["images"]:
                print(f"  {image['filename']}: {image['extracted_text']!r}")
    print(f"Median: {statistics.median(durations):.1f} ms")
    print(f"P95: {max(durations):.1f} ms (small seeded set)")
    print(f"Slowest: {max(durations)} ms")
    print(f"Five-second target: {'PASS' if max(durations) < args.max_ms else 'FAIL'}")
    return int(expected_matches != actual_matches or max(durations) >= args.max_ms)


if __name__ == "__main__":
    raise SystemExit(main())

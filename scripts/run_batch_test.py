import argparse
import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "intake"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify one large batch without lost results.")
    parser.add_argument("--applications", type=int, default=300)
    args = parser.parse_args()
    if args.applications < 2:
        parser.error("--applications must be at least 2")

    seeded = json.loads((FIXTURES / "sample-distilled-spirits-batch.json").read_text())
    templates = seeded["applications"]
    applications = []
    for index in range(args.applications):
        item = json.loads(json.dumps(templates[index % len(templates)]))
        item["application_id"] = f"batch-{index + 1:04d}"
        applications.append(item)
    payload = {
        "submission_id": "batch-load-test",
        "source_label": "Generated 300-application load test",
        "submission_type": "batch",
        "applications": applications,
    }

    with tempfile.TemporaryDirectory() as directory:
        with TestClient(create_app(Path(directory), FIXTURES)) as client:
            response = client.post("/api/submissions", json=payload)
            if response.status_code != 201:
                print(f"Batch submission failed: {response.text}")
                return 1
            reviews = client.get("/api/review-queue").json()

    ids = [item["application_id"] for item in reviews]
    passed = len(ids) == args.applications and len(set(ids)) == args.applications
    print(f"Requested applications: {args.applications}")
    print(f"Terminal review artifacts: {len(ids)}")
    print(f"Unique application IDs: {len(set(ids))}")
    print(f"Batch integrity: {'PASS' if passed else 'FAIL'}")
    return int(not passed)


if __name__ == "__main__":
    raise SystemExit(main())

import re
import time

from .models import (
    ApplicationInput,
    CheckResult,
    Finding,
    ReviewPackage,
    SubmissionArtifact,
)

HEALTH_WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink "
    "alcoholic beverages during pregnancy because of the risk of birth defects. "
    "(2) Consumption of alcoholic beverages impairs your ability to drive a car or "
    "operate machinery, and may cause health problems."
)

RULE_SOURCE = "27 CFR Part 16 and current TTB labeling guidance"


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def compare_field(field_name: str, expected: str, label_text: str) -> Finding:
    expected_normalized = normalize(expected)
    label_normalized = normalize(label_text)
    matched = expected_normalized in label_normalized
    return Finding(
        rule_id=f"application-label-{field_name.replace('_', '-')}",
        field_name=field_name,
        result=CheckResult.MATCH if matched else CheckResult.MISMATCH,
        expected=expected,
        observed=expected if matched else None,
        confidence=0.99,
        explanation=(
            "The normalized submitted value appears in the supplied label evidence."
            if matched
            else "The submitted value was not found in the supplied label evidence."
        ),
        source="Application-to-label comparison",
    )


def warning_finding(label_text: str) -> Finding:
    matched = normalize(HEALTH_WARNING) in normalize(label_text)
    return Finding(
        rule_id="health-warning-text",
        field_name="government_warning",
        result=CheckResult.MATCH if matched else CheckResult.MISMATCH,
        expected=HEALTH_WARNING,
        observed=HEALTH_WARNING if matched else None,
        confidence=0.99,
        explanation=(
            "The required warning wording appears in the fixture text."
            if matched
            else "The complete required warning wording was not found."
        ),
        source=RULE_SOURCE,
    )


def analyze_application(
    submission: SubmissionArtifact,
    application: ApplicationInput,
) -> ReviewPackage:
    started = time.perf_counter()
    findings = [
        compare_field(name, value, application.label_text)
        for name, value in application.fields.model_dump(exclude_none=True).items()
    ]
    findings.append(warning_finding(application.label_text))
    failures = [finding for finding in findings if finding.result == CheckResult.MISMATCH]
    reason = None
    if failures:
        reason = "; ".join(f"{item.field_name}: {item.explanation}" for item in failures)
    duration = max(1, round((time.perf_counter() - started) * 1000))
    return ReviewPackage(
        submission_id=submission.submission_id,
        application_id=application.application_id,
        source_label=submission.source_label,
        processing_duration_ms=duration,
        findings=findings,
        suggested_rejection_reason=reason,
    )

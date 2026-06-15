import re
import time
from pathlib import Path

from .models import (
    ApplicationInput,
    CheckResult,
    Finding,
    ImageEvidence,
    ReviewPackage,
    SubmissionArtifact,
)
from .vision import LocalVisionEngine

HEALTH_WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink "
    "alcoholic beverages during pregnancy because of the risk of birth defects. "
    "(2) Consumption of alcoholic beverages impairs your ability to drive a car or "
    "operate machinery, and may cause health problems."
)

WARNING_SOURCE = "27 CFR 16.21 and 16.22, accessed 2026-06-14"
ALLOWED_IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
MAX_IMAGE_BYTES = 15 * 1024 * 1024


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def compare_field(
    field_name: str,
    expected: str,
    label_text: str,
    confidence: float,
    has_low_confidence_image: bool,
) -> Finding:
    expected_normalized = normalize(expected)
    label_normalized = normalize(label_text)
    if field_name == "alcohol_content":
        expected_numbers = re.findall(r"\d+(?:\.\d+)?", expected)
        observed_numbers = re.findall(r"\d+(?:\.\d+)?", label_text)
        matched = bool(expected_numbers) and all(number in observed_numbers for number in expected_numbers)
    elif field_name == "class_type":
        expected_tokens = set(expected_normalized.split())
        observed_tokens = set(label_normalized.split())
        matched = bool(expected_tokens) and expected_tokens <= observed_tokens
    else:
        matched = compact(expected) in compact(label_text)
    uncertain = confidence < 0.65 or (not matched and has_low_confidence_image)
    result = (
        CheckResult.NEEDS_HUMAN_REVIEW
        if uncertain
        else CheckResult.MATCH if matched else CheckResult.MISMATCH
    )
    return Finding(
        rule_id=f"application-label-{field_name.replace('_', '-')}",
        field_name=field_name,
        result=result,
        expected=expected,
        observed=expected if matched else None,
        confidence=confidence,
        explanation=(
            "OCR confidence is too low for a reliable automated comparison."
            if uncertain
            else "The normalized submitted value appears in the extracted label evidence."
            if matched
            else "The submitted value was not found in the extracted label evidence."
        ),
        source="Application-to-label comparison",
    )


def warning_finding(label_text: str, confidence: float) -> Finding:
    exact = HEALTH_WARNING in " ".join(label_text.split())
    normalized = normalize(HEALTH_WARNING) in normalize(label_text)
    warning_detected = "government warning" in normalize(label_text)
    uncertain = confidence < 0.65 or (warning_detected and not exact)
    result = (
        CheckResult.NEEDS_HUMAN_REVIEW
        if uncertain
        else CheckResult.MATCH if exact else CheckResult.MISMATCH
    )
    explanation = (
        "OCR confidence is too low to verify the statutory warning."
        if confidence < 0.65
        else "A government warning is visible, but OCR did not recover enough text for exact verification."
        if uncertain
        else "The complete warning wording, capitalization, and punctuation match."
        if exact
        else "The complete exact warning was not found."
        + (" Similar wording was found, but exact presentation differs." if normalized else "")
    )
    return Finding(
        rule_id="health-warning-text",
        field_name="government_warning",
        result=result,
        expected=HEALTH_WARNING,
        observed=HEALTH_WARNING if exact else None,
        confidence=confidence,
        explanation=explanation,
        source=WARNING_SOURCE,
    )


def analyze_application(
    submission: SubmissionArtifact,
    application: ApplicationInput,
    image_root: Path,
    vision: LocalVisionEngine,
) -> ReviewPackage:
    started = time.perf_counter()
    images: list[ImageEvidence] = []
    errors: list[str] = []

    for filename in application.image_filenames:
        image_path = image_root / filename
        if not image_path.is_file():
            errors.append(f"Missing image: {filename}")
            continue
        if image_path.suffix.casefold() not in ALLOWED_IMAGE_TYPES:
            errors.append(f"Unsupported image type: {filename}")
            continue
        if image_path.stat().st_size == 0:
            errors.append(f"Empty image: {filename}")
            continue
        if image_path.stat().st_size > MAX_IMAGE_BYTES:
            errors.append(f"Image exceeds the 15 MB POC limit: {filename}")
            continue
        try:
            result = vision.analyze(image_path)
            images.append(
                ImageEvidence(
                    filename=filename,
                    url=f"/api/images/{submission.submission_id}/{filename}",
                    extracted_text=result.text,
                    confidence=result.confidence,
                    width=result.width,
                    height=result.height,
                    blur_score=result.blur_score,
                    glare_ratio=result.glare_ratio,
                    rotation_degrees=result.rotation_degrees,
                    quality_flags=result.quality_flags,
                    engine=result.engine,
                )
            )
        except Exception as exc:
            errors.append(f"{filename}: {exc}")

    combined_text = "\n".join(item.extracted_text for item in images)
    # Fields may appear on only one of several submitted labels. A weak front
    # image must not invalidate reliable evidence recovered from the back.
    confidence = max((item.confidence for item in images), default=0.0)
    has_low_confidence_image = any(item.confidence < 0.65 for item in images)
    findings = [
        compare_field(name, value, combined_text, confidence, has_low_confidence_image)
        for name, value in application.fields.model_dump(exclude_none=True).items()
    ]
    findings.append(warning_finding(combined_text, confidence))

    if errors:
        findings.append(
            Finding(
                rule_id="image-processing",
                field_name="image_processing",
                result=CheckResult.NEEDS_HUMAN_REVIEW,
                expected="Every referenced image can be decoded and analyzed.",
                observed="; ".join(errors),
                confidence=0,
                explanation="One or more label images could not be processed.",
                source="POC input contract",
            )
        )

    attention = [
        finding
        for finding in findings
        if finding.result in {CheckResult.MISMATCH, CheckResult.NEEDS_HUMAN_REVIEW}
    ]
    reason = "; ".join(f"{item.field_name}: {item.explanation}" for item in attention) or None
    duration = max(1, round((time.perf_counter() - started) * 1000))
    return ReviewPackage(
        submission_id=submission.submission_id,
        application_id=application.application_id,
        source_label=submission.source_label,
        processing_duration_ms=duration,
        images=images,
        findings=findings,
        suggested_rejection_reason=reason,
        processing_error="; ".join(errors) or None,
    )

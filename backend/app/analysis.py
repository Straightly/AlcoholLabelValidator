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


STATE_MAPPING = {
    "alabama": "al", "alaska": "ak", "arizona": "az", "arkansas": "ar", "california": "ca",
    "colorado": "co", "connecticut": "ct", "delaware": "de", "florida": "fl", "georgia": "ga",
    "hawaii": "hi", "idaho": "id", "illinois": "il", "indiana": "in", "iowa": "ia",
    "kansas": "ks", "kentucky": "ky", "louisiana": "la", "maine": "me", "maryland": "md",
    "massachusetts": "ma", "michigan": "mi", "minnesota": "mn", "mississippi": "ms", "missouri": "mo",
    "montana": "mt", "nebraska": "ne", "nevada": "nv", "new hampshire": "nh", "new jersey": "nj",
    "new mexico": "nm", "new york": "ny", "north carolina": "nc", "north-dakota": "nd", "ohio": "oh",
    "oklahoma": "ok", "oregon": "or", "pennsylvania": "pa", "rhode island": "ri", "south carolina": "sc",
    "south dakota": "sd", "tennessee": "tn", "texas": "tx", "utah": "ut", "vermont": "vt",
    "virginia": "va", "washington": "wa", "west virginia": "wv", "wisconsin": "wi", "wyoming": "wy"
}

ADDRESS_ABBREVIATIONS = {
    "street": "st",
    "avenue": "ave",
    "road": "rd",
    "boulevard": "blvd",
    "drive": "dr",
    "court": "ct",
    "lane": "ln",
    "highway": "hwy",
    "parkway": "pkwy",
    "north": "n",
    "south": "s",
    "east": "e",
    "west": "w",
    "suite": "ste",
    "apartment": "apt",
    "building": "bldg",
    "floor": "fl",
    "room": "rm",
    "square": "sq",
    "terrace": "ter",
    "place": "pl",
    "expressway": "expy",
    "incorporated": "inc",
    "corporation": "corp",
    "company": "co",
    "limited": "ltd",
}


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def parse_volume_ml(text: str) -> float | None:
    text_lower = text.lower()
    text_lower = re.sub(r"\bmilliliters?\b", "ml", text_lower)
    text_lower = re.sub(r"\bcentiliters?\b", "cl", text_lower)
    text_lower = re.sub(r"\bliters?\b", "l", text_lower)
    match = re.search(r"(\d+(?:\.\d+)?)\s*(ml|cl|l)\b", text_lower)
    if match:
        val = float(match.group(1))
        unit = match.group(2)
        if unit == "ml":
            return val
        elif unit == "cl":
            return val * 10.0
        elif unit == "l":
            return val * 1000.0
    return None


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
        expected_numbers = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", expected)]
        observed_numbers = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", label_text)]
        matched = bool(expected_numbers) and all(
            any(abs(exp - obs) < 0.1 for obs in observed_numbers)
            for exp in expected_numbers
        )
    elif field_name == "class_type":
        expected_tokens = set(expected_normalized.split())
        observed_tokens = set(label_normalized.split())
        matched = bool(expected_tokens) and expected_tokens <= observed_tokens
    elif field_name == "producer_name_address":
        norm_expected = expected_normalized
        norm_label = label_normalized
        for state, abbr in STATE_MAPPING.items():
            norm_expected = re.sub(rf"\b{state}\b", abbr, norm_expected)
            norm_label = re.sub(rf"\b{state}\b", abbr, norm_label)
        for full_word, abbr in ADDRESS_ABBREVIATIONS.items():
            norm_expected = re.sub(rf"\b{full_word}\b", abbr, norm_expected)
            norm_label = re.sub(rf"\b{full_word}\b", abbr, norm_label)
        matched = compact(norm_expected) in compact(norm_label)
    elif field_name == "net_contents":
        norm_expected = expected_normalized
        norm_label = label_normalized
        norm_expected = re.sub(r"\bmilliliters?\b", "ml", norm_expected)
        norm_expected = re.sub(r"\bliters?\b", "l", norm_expected)
        norm_label = re.sub(r"\bmilliliters?\b", "ml", norm_label)
        norm_label = re.sub(r"\bliters?\b", "l", norm_label)
        
        exp_val = parse_volume_ml(expected)
        lbl_val = parse_volume_ml(label_text)
        if exp_val is not None and lbl_val is not None:
            matched = abs(exp_val - lbl_val) < 1.0
        else:
            matched = compact(norm_expected) in compact(norm_label)
    elif field_name == "country_of_origin":
        norm_expected = expected_normalized
        norm_label = label_normalized
        us_synonyms = [r"\bunited states of america\b", r"\bunited states\b", r"\bu\s*s\s*a\b", r"\bu\s*s\b"]
        for syn in us_synonyms:
            norm_expected = re.sub(syn, "usa", norm_expected)
            norm_label = re.sub(syn, "usa", norm_label)
        uk_synonyms = [r"\bunited kingdom\b", r"\bu\s*k\b", r"\bgreat britain\b", r"\bgb\b"]
        for syn in uk_synonyms:
            norm_expected = re.sub(syn, "uk", norm_expected)
            norm_label = re.sub(syn, "uk", norm_label)
        matched = compact(norm_expected) in compact(norm_label)
    else:
        matched = compact(expected) in compact(label_text)
    uncertain = confidence < 0.54 or (not matched and has_low_confidence_image)
    if matched:
        result = CheckResult.MATCH if not uncertain else CheckResult.LIKELY_MATCH
    else:
        result = CheckResult.MISSING if not uncertain else CheckResult.LIKELY_MISSING

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
    exact = HEALTH_WARNING.casefold() in " ".join(label_text.split()).casefold()
    normalized = normalize(HEALTH_WARNING) in normalize(label_text)
    warning_detected = "government warning" in normalize(label_text)
    
    matched = False
    if exact:
        matched = True
    else:
        # Check if the warning is present but has minor OCR typos
        content_words = [
            "government", "warning", "according", "surgeon", "general", "women", "should",
            "drink", "alcoholic", "beverages", "pregnancy", "because", "risk", "birth",
            "defects", "consumption", "impairs", "ability", "drive", "operate", "machinery",
            "cause", "health", "problems"
        ]
        from difflib import SequenceMatcher
        observed_compact = compact(label_text)
        matched_count = 0
        for word in content_words:
            if word in observed_compact:
                matched_count += 1
            else:
                # Check fuzzy substring match
                for k in range(len(observed_compact) - len(word) + 1):
                    sub = observed_compact[k : k + len(word)]
                    if SequenceMatcher(None, word, sub).ratio() >= 0.75:
                        matched_count += 1
                        break
        
        match_ratio = matched_count / len(content_words)
        if match_ratio >= 0.80 and warning_detected:
            matched = True

    uncertain = confidence < 0.54
    if matched:
        result = CheckResult.MATCH if not uncertain else CheckResult.LIKELY_MATCH
    else:
        result = CheckResult.MISSING if not uncertain else CheckResult.LIKELY_MISSING

    explanation = (
        "The complete warning wording, capitalization, and punctuation match."
        if exact
        else "The warning wording is detected with minor character recognition discrepancies, matching the required statutory statement."
        if result in {CheckResult.MATCH, CheckResult.LIKELY_MATCH}
        else "The submitted evidence does not establish the complete exact warning text."
        + (" A partial warning was detected, but the small print is not readable enough to pass." if warning_detected else "")
        + (" Similar wording was found, but exact presentation differs." if normalized else "")
    )
    return Finding(
        rule_id="health-warning-text",
        field_name="government_warning",
        result=result,
        expected=HEALTH_WARNING,
        observed=HEALTH_WARNING if result in {CheckResult.MATCH, CheckResult.LIKELY_MATCH} else None,
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
    has_low_confidence_image = any(item.confidence < 0.54 for item in images)
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
                result=CheckResult.LIKELY_MISSING,
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
        if finding.result != CheckResult.MATCH
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

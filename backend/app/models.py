from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BeverageCategory(StrEnum):
    DISTILLED_SPIRITS = "distilled_spirits"
    WINE = "wine"
    MALT_BEVERAGE = "malt_beverage"


class SubmissionType(StrEnum):
    SINGLE = "single"
    BATCH = "batch"


class CheckResult(StrEnum):
    MATCH = "Match"
    LIKELY_MATCH = "Likely Match"
    LIKELY_MISSING = "Likely Missing"
    MISSING = "Missing"
    NOT_EVALUATED = "Not Evaluated"



class DecisionType(StrEnum):
    APPROVED = "Approved"
    REJECTED = "Rejected"


class ApplicationFields(BaseModel):
    brand_name: str = Field(min_length=1)
    class_type: str = Field(min_length=1)
    alcohol_content: str = Field(min_length=1)
    net_contents: str = Field(min_length=1)
    producer_name_address: str = Field(min_length=1)
    country_of_origin: str | None = None


class ApplicationInput(BaseModel):
    application_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    beverage_category: BeverageCategory
    fields: ApplicationFields
    image_filenames: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_image_names(self) -> "ApplicationInput":
        if len(self.image_filenames) != len(set(self.image_filenames)):
            raise ValueError("Image filenames must be unique within an application.")
        for filename in self.image_filenames:
            if not filename or filename != filename.replace("\\", "/").split("/")[-1]:
                raise ValueError("Image filenames must be simple filenames.")
        return self


class SubmissionCreate(BaseModel):
    submission_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    source_label: str = Field(
        min_length=1,
        description="Non-PII operational label for the synthetic or upstream intake source.",
    )
    submission_type: SubmissionType
    applications: list[ApplicationInput] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_cardinality_and_ids(self) -> "SubmissionCreate":
        expected = 1 if self.submission_type == SubmissionType.SINGLE else 2
        if self.submission_type == SubmissionType.SINGLE and len(self.applications) != expected:
            raise ValueError("A single submission must contain exactly one application.")
        if self.submission_type == SubmissionType.BATCH and len(self.applications) < expected:
            raise ValueError("A batch submission must contain at least two applications.")
        ids = [item.application_id for item in self.applications]
        if len(ids) != len(set(ids)):
            raise ValueError("Application identifiers must be unique within a submission.")
        return self


class SubmissionArtifact(SubmissionCreate):
    submitted_at: datetime = Field(default_factory=utc_now)
    schema_version: str = "1.0"


class Finding(BaseModel):
    rule_id: str
    field_name: str
    result: CheckResult
    expected: str
    observed: str | None
    confidence: float = Field(ge=0, le=1)
    explanation: str
    source: str


class ImageEvidence(BaseModel):
    filename: str
    url: str
    extracted_text: str
    confidence: float = Field(ge=0, le=1)
    width: int | None = None
    height: int | None = None
    blur_score: float | None = None
    glare_ratio: float | None = None
    rotation_degrees: float | None = None
    quality_flags: list[str] = Field(default_factory=list)
    engine: str


class ReviewPackage(BaseModel):
    submission_id: str
    application_id: str
    source_label: str
    analyzed_at: datetime = Field(default_factory=utc_now)
    pipeline_version: str = "local-vision-1.0"
    processing_duration_ms: int = Field(ge=0)
    images: list[ImageEvidence] = Field(default_factory=list)
    findings: list[Finding]
    suggested_rejection_reason: str | None = None
    processing_error: str | None = None


class DecisionCreate(BaseModel):
    decision: DecisionType
    public_reason: str = Field(min_length=1)
    officer_name: str = Field(min_length=1)
    override_note: str | None = None

    @model_validator(mode="after")
    def validate_decision(self) -> "DecisionCreate":
        if self.decision == DecisionType.REJECTED and not self.public_reason.strip():
            raise ValueError("A rejection reason is required.")
        return self


class DecisionArtifact(DecisionCreate):
    submission_id: str
    application_id: str
    decided_at: datetime = Field(default_factory=utc_now)
    schema_version: str = "1.0"

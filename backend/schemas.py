from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from autoannotation import gene_names


def _normalize_optional_string(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class AnnotationJobRequest(BaseModel):
    # cache/output fields are server filesystem paths passed through to the
    # existing annotator. Add validation here before exposing this API beyond a
    # trusted/local deployment.
    profile: str | None = None
    organism: str | None = None
    strain: str | None = None
    locus: str | None = None
    name: str | None = None
    cache_dir: str = "./.cache"
    output_dir: str = "gen_json"
    gene_name_cache: str = gene_names.DEFAULT_GENE_NAME_CACHE_DIR
    allow_online_name_lookup: bool = True
    refresh_gene_name_cache: bool = False
    cache_supplied_name: bool = False
    profile_config: dict[str, Any] | None = Field(default=None, exclude=True)
    locus_regex: str | None = None
    search_terms: list[str] = Field(default_factory=list)
    target_patterns: list[str] = Field(default_factory=list)
    off_target_patterns: list[str] = Field(default_factory=list)
    excluded_species_patterns: list[str] = Field(default_factory=list)

    @field_validator(
        "profile",
        "organism",
        "strain",
        "locus",
        "name",
        "locus_regex",
        mode="before",
    )
    @classmethod
    def normalize_optional_strings(cls, value):
        return _normalize_optional_string(value)

    @model_validator(mode="after")
    def validate_target_shape(self):
        if self.profile and self.organism:
            raise ValueError("use either profile or organism, not both")
        if not self.profile and not self.organism:
            raise ValueError("profile or organism is required")
        if not self.locus and not self.name:
            raise ValueError("name or locus is required")
        return self


class ValidationRequest(BaseModel):
    profile: str | None = None
    organism: str | None = None
    strain: str | None = None
    locus: str | None = None
    name: str | None = None
    locus_regex: str | None = None
    search_terms: list[str] = Field(default_factory=list)
    target_patterns: list[str] = Field(default_factory=list)
    off_target_patterns: list[str] = Field(default_factory=list)
    excluded_species_patterns: list[str] = Field(default_factory=list)

    @field_validator(
        "profile",
        "organism",
        "strain",
        "locus",
        "name",
        "locus_regex",
        mode="before",
    )
    @classmethod
    def normalize_optional_strings(cls, value):
        return _normalize_optional_string(value)

    @model_validator(mode="after")
    def validate_target_shape(self):
        if self.profile and self.organism:
            raise ValueError("use either profile or organism, not both")
        if not self.profile and not self.organism:
            raise ValueError("profile or organism is required")
        if not self.locus and not self.name:
            raise ValueError("name or locus is required")
        return self


class ProfileResponse(BaseModel):
    profile_id: str
    canonical_name: str
    species_name: str
    strain: str | None
    synonyms: list[str]
    species_synonyms: list[str]
    strain_synonyms: list[str]
    locus_regex: str | None


class ProfilePayload(BaseModel):
    profile_id: str = Field(min_length=1)
    canonical_name: str = Field(min_length=1)
    species_name: str = Field(min_length=1)
    strain: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    species_synonyms: list[str] = Field(default_factory=list)
    strain_synonyms: list[str] = Field(default_factory=list)
    locus_regex: str | None = None
    search_terms: list[str] = Field(default_factory=list)
    target_patterns: list[str] = Field(default_factory=list)
    off_target_patterns: list[str] = Field(default_factory=list)
    excluded_species_patterns: list[str] = Field(default_factory=list)


class ProfileDetailResponse(ProfileResponse):
    source: str = "builtin"
    trusted: bool = True
    read_only: bool = True
    search_terms: list[str] = Field(default_factory=list)
    target_patterns: list[str] = Field(default_factory=list)
    off_target_patterns: list[str] = Field(default_factory=list)
    excluded_species_patterns: list[str] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None


class ProfilesResponse(BaseModel):
    profiles: list[ProfileDetailResponse]


class TargetWarning(BaseModel):
    code: str
    message: str


class TargetPreflightResponse(BaseModel):
    valid: bool = True
    profile_id: str | None = None
    profile_source: str = "ad_hoc"
    canonical_name: str | None = None
    species_name: str | None = None
    strain: str | None = None
    submitted_locus: str | None = None
    submitted_name: str | None = None
    resolved_locus: str | None = None
    resolved_name: str | None = None
    primary_identifier: str
    warnings: list[TargetWarning] = Field(default_factory=list)


class JobCreateResponse(BaseModel):
    job_id: str
    status: str


class JobRecordResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: str
    status: str
    current_step: str = "queued"
    request: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None
    annotation_persisted: bool = False
    annotation_error: str | None = None
    output_path: str | None = None
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    result_available: bool = False
    queue_position: int | None = None


class QueueSummaryResponse(BaseModel):
    queued: int
    running: int
    completed: int
    failed: int


class JobsListResponse(BaseModel):
    jobs: list[JobRecordResponse]
    queue: QueueSummaryResponse


class AnnotationSearchResult(BaseModel):
    id: str
    profile_id: str
    canonical_name: str
    species_name: str | None = None
    strain: str | None = None
    normalized_locus: str | None = None
    gene_name: str | None = None
    generated_at: str | None = None
    version_count: int = 0


class AnnotationSearchResponse(BaseModel):
    query: str
    matches: list[AnnotationSearchResult]


class AnnotationDetailResponse(AnnotationSearchResult):
    result: dict[str, Any]
    job_id: str | None = None
    output_path: str | None = None


class AnnotationVersionsResponse(BaseModel):
    annotation_id: str
    versions: list[dict[str, Any]]

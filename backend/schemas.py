from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from autoannotation import gene_names


class AnnotationJobRequest(BaseModel):
    # cache/output fields are server filesystem paths passed through to the
    # existing annotator. Add validation here before exposing this API beyond a
    # trusted/local deployment.
    profile: str | None = None
    organism: str | None = None
    strain: str | None = None
    locus: str = Field(min_length=1)
    name: str | None = None
    cache_dir: str = "./.cache"
    output_dir: str = "gen_json"
    gene_name_cache: str = gene_names.DEFAULT_GENE_NAME_CACHE_DIR
    allow_online_name_lookup: bool = True
    refresh_gene_name_cache: bool = False
    cache_supplied_name: bool = False

    @model_validator(mode="after")
    def reject_conflicting_profile_and_organism(self):
        if self.profile and self.organism:
            raise ValueError("use either profile or organism, not both")
        return self


class ValidationRequest(BaseModel):
    profile: str | None = None
    organism: str | None = None
    strain: str | None = None
    locus: str = Field(min_length=1)

    @model_validator(mode="after")
    def reject_conflicting_profile_and_organism(self):
        if self.profile and self.organism:
            raise ValueError("use either profile or organism, not both")
        if not self.profile and not self.organism:
            raise ValueError("profile or organism is required")
        return self


class ProfileResponse(BaseModel):
    profile_id: str
    canonical_name: str
    species_name: str
    strain: str | None
    synonyms: list[str]
    species_synonyms: list[str]
    strain_synonyms: list[str]
    locus_regex: str


class ProfilesResponse(BaseModel):
    profiles: list[ProfileResponse]


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
    normalized_locus: str
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

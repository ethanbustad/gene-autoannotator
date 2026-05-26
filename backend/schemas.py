from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from autoannotation import gene_names


class AnnotationJobRequest(BaseModel):
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
    request: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None
    output_path: str | None = None
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    result_available: bool = False

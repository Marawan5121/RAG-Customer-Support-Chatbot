"""Schemas for the indexing endpoints (Milestone 1 / 2)."""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

# Allowed chunk profile keys (token sizes mandated by the lecturer).
ChunkProfile = str  # one of: "256", "512", "1024"


class IndexRequest(BaseModel):
    """Parameters controlling an indexing job."""

    chunk_profile: Optional[ChunkProfile] = Field(
        default=None,
        description="Chunk profile to use: '256', '512' or '1024'. Defaults to configured value.",
    )
    limit: Optional[int] = Field(
        default=None,
        ge=1,
        description="Optional cap on the number of records to index (useful for testing).",
    )
    recreate_index: bool = Field(
        default=True,
        description="Create the Azure AI Search index with the agreed schema if it is missing.",
    )
    dedupe: bool = Field(default=True, description="Remove duplicate documents before chunking.")


class TokenStats(BaseModel):
    """Token distribution statistics for a set of chunks."""

    min: int
    max: int
    avg: float
    total: int


class IndexJobStats(BaseModel):
    """Consolidated statistics produced by a completed indexing job."""

    rows_loaded: int
    duplicates_removed: int
    rows_after_dedup: int
    chunks_created: int
    chunks_embedded: int
    chunks_uploaded: int
    chunks_failed: int
    token_stats: TokenStats
    avg_chunks_per_document: float
    intent_distribution: Dict[str, int]
    category_distribution: Dict[str, int]


class IndexJobStatus(BaseModel):
    """Current status of an indexing job."""

    job_id: str
    status: str = Field(description="pending | running | completed | failed")
    chunk_profile: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
    stats: Optional[IndexJobStats] = None


class ChunkingStudyRequest(BaseModel):
    """Parameters for the chunk-size optimisation study."""

    sample_size: Optional[int] = Field(
        default=2000,
        ge=1,
        description="Number of records to sample for the study (None/omit for the full corpus).",
    )
    profiles: Optional[List[ChunkProfile]] = Field(
        default=None,
        description="Subset of profiles to compare; defaults to all of 256/512/1024.",
    )


class ChunkProfileResult(BaseModel):
    """Chunking distribution result for a single profile."""

    chunk_size: int
    chunk_overlap: int
    total_documents: int
    total_chunks: int
    avg_chunks_per_document: float
    token_stats: TokenStats


class ChunkingStudyResponse(BaseModel):
    """Comparison of chunk profiles for the optimisation study."""

    sample: Dict[str, int]
    profiles: Dict[str, ChunkProfileResult]

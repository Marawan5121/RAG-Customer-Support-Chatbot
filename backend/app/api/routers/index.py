"""Indexing router - ingest, preprocess, chunk, embed and upload to Azure AI Search.

The POST /index endpoint schedules the work as a detached background job and
returns immediately (HTTP 202) so the request never blocks. Progress is polled
via GET /index/status/{job_id}. The chunking study endpoint runs the
optimisation comparison without embedding or uploading.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_indexing_service
from app.schemas.indexing import (
    ChunkingStudyRequest,
    ChunkingStudyResponse,
    IndexJobStatus,
    IndexRequest,
)
from app.services.indexing_service import IndexingService
from app.services.preprocessing_service import CHUNK_PROFILES

router = APIRouter(prefix="/index", tags=["indexing"])


@router.post("", response_model=IndexJobStatus, status_code=status.HTTP_202_ACCEPTED)
async def start_indexing(
    payload: IndexRequest,
    indexing: IndexingService = Depends(get_indexing_service),
) -> IndexJobStatus:
    """Schedule a knowledge-base indexing job and return its initial status."""
    try:
        job = indexing.start_job(
            chunk_profile=payload.chunk_profile,
            limit=payload.limit,
            recreate_index=payload.recreate_index,
            dedupe=payload.dedupe,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return IndexJobStatus(**job)


@router.get("/profiles")
async def list_profiles() -> dict:
    """Return the available chunk profiles (token size / overlap)."""
    return {"profiles": CHUNK_PROFILES}


@router.get("/status/{job_id}", response_model=IndexJobStatus)
async def get_job_status(
    job_id: str,
    indexing: IndexingService = Depends(get_indexing_service),
) -> IndexJobStatus:
    """Return the current status (and stats) of an indexing job."""
    job = indexing.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown job id '{job_id}'."
        )
    return IndexJobStatus(**job)


@router.get("/status")
async def list_jobs(
    indexing: IndexingService = Depends(get_indexing_service),
) -> dict:
    """Return the status of all known indexing jobs."""
    return {"jobs": indexing.list_jobs()}


@router.post("/chunking-study", response_model=ChunkingStudyResponse)
async def chunking_study(
    payload: ChunkingStudyRequest,
    indexing: IndexingService = Depends(get_indexing_service),
) -> ChunkingStudyResponse:
    """Run the chunk-size optimisation study (256/64 vs 512/128 vs 1024/256).

    Returns the chunk distribution per profile so the trade-off can be compared.
    No embeddings are generated and nothing is uploaded.
    """
    try:
        result = await indexing.run_chunking_study(
            sample_size=payload.sample_size,
            profiles=payload.profiles,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return ChunkingStudyResponse(**result)

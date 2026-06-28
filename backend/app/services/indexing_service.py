"""Indexing service - orchestrates the end-to-end ingestion -> index pipeline.

Pipeline:
    1. (optional) Provision the Azure AI Search index with the agreed schema.
    2. Ingest + preprocess + deduplicate the Bitext corpus (PreprocessingService).
    3. Chunk documents using the selected token profile.
    4. Generate 768-dim embeddings with Google ``text-embedding-004`` (LLMService).
    5. Upload the embedded documents to Azure AI Search (SearchService).

Jobs run as detached asyncio tasks and their progress is tracked in memory so the
indexing work never blocks the request handler or the application lifespan. Every
job is wrapped in a try/except so a failure is recorded but never propagates.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from app.core.config import Settings
from app.core.logging import get_logger
from app.services.llm_service import LLMService
from app.services.preprocessing_service import CHUNK_PROFILES, PreprocessingService
from app.services.search_service import SearchService

logger = get_logger(__name__)


class IndexingService:
    """Coordinates preprocessing, embedding and Azure AI Search upload."""

    def __init__(
        self,
        settings: Settings,
        search_service: SearchService,
        llm_service: LLMService,
        preprocessing_service: PreprocessingService,
    ) -> None:
        self._settings = settings
        self._search = search_service
        self._llm = llm_service
        self._preprocessing = preprocessing_service
        # In-memory job registry (job_id -> status dict).
        self._jobs: Dict[str, dict] = {}
        # Strong references to running tasks so they are not garbage collected.
        self._tasks: Set[asyncio.Task] = set()

    # ------------------------------------------------------------------
    # Job lifecycle
    # ------------------------------------------------------------------
    def start_job(
        self,
        chunk_profile: Optional[str] = None,
        limit: Optional[int] = None,
        recreate_index: bool = True,
        dedupe: bool = True,
    ) -> dict:
        """Register a new indexing job and schedule it as a detached task."""
        profile = chunk_profile or self._settings.default_chunk_profile
        if profile not in CHUNK_PROFILES:
            raise ValueError(
                f"Unknown chunk profile '{profile}'. Valid profiles: {list(CHUNK_PROFILES)}"
            )

        job_id = uuid.uuid4().hex
        self._jobs[job_id] = {
            "job_id": job_id,
            "status": "pending",
            "chunk_profile": profile,
            "started_at": None,
            "finished_at": None,
            "error": None,
            "stats": None,
        }

        task = asyncio.create_task(
            self._run_job(
                job_id=job_id,
                profile=profile,
                limit=limit,
                recreate_index=recreate_index,
                dedupe=dedupe,
            )
        )
        # Track the task and clean up the reference once it finishes.
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

        logger.info("Indexing job %s scheduled (profile=%s, limit=%s).", job_id, profile, limit)
        return self._jobs[job_id]

    def get_job(self, job_id: str) -> Optional[dict]:
        """Return the status of a single job, or None if unknown."""
        return self._jobs.get(job_id)

    def list_jobs(self) -> List[dict]:
        """Return the status of all known jobs (most recent first)."""
        return list(reversed(list(self._jobs.values())))

    # ------------------------------------------------------------------
    # Pipeline execution
    # ------------------------------------------------------------------
    async def _run_job(
        self,
        job_id: str,
        profile: str,
        limit: Optional[int],
        recreate_index: bool,
        dedupe: bool,
    ) -> None:
        """Execute the full indexing pipeline for a job, recording progress."""
        job = self._jobs[job_id]
        job["status"] = "running"
        job["started_at"] = datetime.now(timezone.utc)
        logger.info("Indexing job %s started.", job_id)

        try:
            # Pre-flight checks: required integrations must be configured.
            if not self._llm.is_configured:
                raise RuntimeError("Google Generative AI is not configured; cannot embed.")
            if not self._search.is_configured:
                raise RuntimeError("Azure AI Search is not configured; cannot upload.")

            # 1. Provision the index if requested.
            if recreate_index:
                await self._search.ensure_index_exists()

            # 2. Ingest + preprocess + deduplicate.
            records, prep_stats = self._preprocessing.prepare_records(limit=limit, dedupe=dedupe)
            if not records:
                raise RuntimeError("No records to index after preprocessing.")

            # 3. Chunk with the selected profile.
            chunk_docs, chunk_stats = self._preprocessing.chunk_records(records, profile)

            # 4. Generate embeddings for every chunk.
            texts = [doc["content_text"] for doc in chunk_docs]
            logger.info("Embedding %d chunks for job %s.", len(texts), job_id)
            vectors = await self._llm.embed_documents(texts)
            if len(vectors) != len(chunk_docs):
                raise RuntimeError(
                    f"Embedding count mismatch: got {len(vectors)} for {len(chunk_docs)} chunks."
                )

            # 5. Attach vectors + metadata and build the final documents.
            indexed_at = datetime.now(timezone.utc).isoformat()
            model_ver = self._settings.gemini_embedding_model
            documents = []
            for doc, vector in zip(chunk_docs, vectors):
                documents.append(
                    {
                        "chunk_id": doc["chunk_id"],
                        "content_text": doc["content_text"],
                        self._settings.azure_search_vector_field: vector,
                        "intent_label": doc["intent_label"],
                        "category": doc["category"],
                        "source_row_id": doc["source_row_id"],
                        "embedding_model_ver": model_ver,
                        "indexed_at": indexed_at,
                    }
                )

            # 6. Upload to Azure AI Search.
            logger.info("Uploading %d documents to Azure AI Search for job %s.", len(documents), job_id)
            upload_result = await self._search.upload_documents(documents)

            # Record consolidated statistics on the job.
            job["stats"] = {
                "rows_loaded": prep_stats["rows_loaded"],
                "duplicates_removed": prep_stats["duplicates_removed"],
                "rows_after_dedup": prep_stats["rows_after_dedup"],
                "chunks_created": chunk_stats["total_chunks"],
                "chunks_embedded": len(vectors),
                "chunks_uploaded": upload_result["succeeded"],
                "chunks_failed": upload_result["failed"],
                "token_stats": chunk_stats["token_stats"],
                "avg_chunks_per_document": chunk_stats["avg_chunks_per_document"],
                "intent_distribution": chunk_stats["intent_distribution"],
                "category_distribution": chunk_stats["category_distribution"],
            }
            job["status"] = "completed"
            logger.info(
                "Indexing job %s completed: %d uploaded, %d failed.",
                job_id,
                upload_result["succeeded"],
                upload_result["failed"],
            )

        except Exception as exc:  # noqa: BLE001 - a job failure must never crash the app
            job["status"] = "failed"
            job["error"] = str(exc)
            logger.exception("Indexing job %s failed: %s", job_id, exc)
        finally:
            job["finished_at"] = datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # Chunking optimisation study (no embedding / upload)
    # ------------------------------------------------------------------
    async def run_chunking_study(
        self,
        sample_size: Optional[int] = None,
        profiles: Optional[List[str]] = None,
    ) -> dict:
        """Run the chunk-size comparison study off the event loop.

        Preprocessing and chunking are CPU/IO bound and synchronous, so they are
        offloaded to a worker thread to keep the event loop responsive.
        """
        return await asyncio.to_thread(
            self._preprocessing.benchmark_chunk_profiles, sample_size, profiles
        )

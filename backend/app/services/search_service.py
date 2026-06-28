"""Azure AI Search service - hybrid (vector + BM25) retrieval with semantic ranking.

Built on the official ``azure-search-documents`` async client. In addition to the
retrieval entry point used by the RAG pipeline, this service can provision the
knowledge-base index with the exact schema agreed for the project and upload
embedded documents in batches.

Clients are created lazily so the application can boot even before credentials
are provided.
"""

from typing import List, Optional

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class SearchService:
    """Thin wrapper around the Azure AI Search async clients."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = None  # azure.search.documents.aio.SearchClient

    @property
    def is_configured(self) -> bool:
        """Return True when the Azure AI Search endpoint and key are present."""
        return self._settings.azure_search_configured

    async def connect(self) -> None:
        """Initialise the async SearchClient if credentials are configured."""
        if not self.is_configured:
            logger.warning("Azure AI Search is not configured; retrieval is disabled.")
            return

        # Imported lazily so the dependency is only required when actually used.
        from azure.core.credentials import AzureKeyCredential
        from azure.search.documents.aio import SearchClient

        self._client = SearchClient(
            endpoint=self._settings.azure_search_endpoint,
            index_name=self._settings.azure_search_index_name,
            credential=AzureKeyCredential(self._settings.azure_search_api_key),
        )
        logger.info(
            "Azure AI Search client initialised for index '%s'.",
            self._settings.azure_search_index_name,
        )

    async def close(self) -> None:
        """Release the underlying HTTP session."""
        if self._client is not None:
            await self._client.close()
            self._client = None

    # ------------------------------------------------------------------
    # Index provisioning
    # ------------------------------------------------------------------
    async def ensure_index_exists(self) -> bool:
        """Create the knowledge-base index if it does not already exist.

        The index is created with the agreed schema: a key, a BM25-searchable
        text field, a 768-dim HNSW vector field, filterable/facetable metadata,
        and a semantic configuration for L2 re-ranking.

        Returns:
            True if the index was created, False if it already existed.
        """
        if not self.is_configured:
            raise RuntimeError("Azure AI Search is not configured.")

        from azure.core.credentials import AzureKeyCredential
        from azure.core.exceptions import ResourceNotFoundError
        from azure.search.documents.indexes.aio import SearchIndexClient
        from azure.search.documents.indexes.models import (
            HnswAlgorithmConfiguration,
            SearchableField,
            SearchField,
            SearchFieldDataType,
            SearchIndex,
            SemanticConfiguration,
            SemanticField,
            SemanticPrioritizedFields,
            SemanticSearch,
            SimpleField,
            VectorSearch,
            VectorSearchProfile,
        )

        index_name = self._settings.azure_search_index_name
        index_client = SearchIndexClient(
            endpoint=self._settings.azure_search_endpoint,
            credential=AzureKeyCredential(self._settings.azure_search_api_key),
        )

        try:
            await index_client.get_index(index_name)
            logger.info("Azure AI Search index '%s' already exists.", index_name)
            return False
        except ResourceNotFoundError:
            logger.info("Index '%s' not found; creating it.", index_name)

        # Field schema - matches the agreed knowledge-base contract exactly.
        fields = [
            SimpleField(
                name="chunk_id",
                type=SearchFieldDataType.String,
                key=True,
                filterable=True,
            ),
            SearchableField(
                name="content_text",
                type=SearchFieldDataType.String,
                analyzer_name="en.lucene",  # BM25 keyword search leg
            ),
            SearchField(
                name=self._settings.azure_search_vector_field,  # content_vector
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=self._settings.embedding_dimensions,  # 768
                vector_search_profile_name="vector-profile",
            ),
            SimpleField(
                name="intent_label",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True,
            ),
            SimpleField(
                name="category",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True,
            ),
            SimpleField(
                name="source_row_id",
                type=SearchFieldDataType.Int32,
                filterable=True,
                sortable=True,
            ),
            SimpleField(
                name="embedding_model_ver",
                type=SearchFieldDataType.String,
                filterable=True,
            ),
            SimpleField(
                name="indexed_at",
                type=SearchFieldDataType.DateTimeOffset,
                sortable=True,
                filterable=True,
            ),
        ]

        # HNSW vector configuration (cosine similarity by default).
        vector_search = VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="hnsw-config")],
            profiles=[
                VectorSearchProfile(
                    name="vector-profile",
                    algorithm_configuration_name="hnsw-config",
                )
            ],
        )

        # Semantic configuration used for L2 semantic ranking on content_text.
        semantic_search = SemanticSearch(
            configurations=[
                SemanticConfiguration(
                    name=self._settings.azure_search_semantic_config,
                    prioritized_fields=SemanticPrioritizedFields(
                        content_fields=[SemanticField(field_name="content_text")],
                    ),
                )
            ]
        )

        index = SearchIndex(
            name=index_name,
            fields=fields,
            vector_search=vector_search,
            semantic_search=semantic_search,
        )

        try:
            await index_client.create_or_update_index(index)
            logger.info("Azure AI Search index '%s' created successfully.", index_name)
            return True
        finally:
            await index_client.close()

    # ------------------------------------------------------------------
    # Document upload
    # ------------------------------------------------------------------
    async def upload_documents(self, documents: List[dict]) -> dict:
        """Upload documents to the index in batches using merge-or-upload.

        Returns a summary dict with succeeded/failed counts. Per-document and
        per-batch failures are logged but never raised, so a partial failure does
        not abort the whole indexing job.
        """
        if self._client is None:
            raise RuntimeError("Azure AI Search client is not ready.")

        from azure.core.exceptions import HttpResponseError

        batch_size = max(1, self._settings.upload_batch_size)
        succeeded = 0
        failed = 0

        for start in range(0, len(documents), batch_size):
            batch = documents[start : start + batch_size]
            try:
                results = await self._client.merge_or_upload_documents(documents=batch)
                for result in results:
                    if result.succeeded:
                        succeeded += 1
                    else:
                        failed += 1
                        logger.error(
                            "Upload failed for chunk_id=%s: %s",
                            result.key,
                            result.error_message,
                        )
            except HttpResponseError as exc:
                failed += len(batch)
                logger.error("Batch upload failed (%d docs): %s", len(batch), exc)

            logger.info(
                "Upload progress: %d succeeded, %d failed (of %d).",
                succeeded,
                failed,
                len(documents),
            )

        return {"succeeded": succeeded, "failed": failed}

    # ------------------------------------------------------------------
    # Retrieval (implemented in Milestone 2)
    # ------------------------------------------------------------------
    async def hybrid_search(
        self,
        query_text: str,
        query_vector: Optional[List[float]] = None,
        top_k: Optional[int] = None,
        intent_filter: Optional[str] = None,
    ) -> List[dict]:
        """Run a hybrid (BM25 + vector) query with semantic ranking.

        Wired here for completeness; the retrieval logic is implemented in the
        Milestone 2 RAG pipeline work.
        """
        if self._client is None:
            logger.warning("hybrid_search called but Azure AI Search client is not ready.")
            return []
        raise NotImplementedError("Hybrid retrieval will be implemented in Milestone 2.")

    async def ping(self) -> bool:
        """Lightweight health probe used by the /health endpoint."""
        return self._client is not None

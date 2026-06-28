"""Azure AI Search service - hybrid (vector + BM25) retrieval with semantic ranking.

This is a configuration placeholder: it wires up the official
``azure-search-documents`` async client and exposes a ``hybrid_search`` method
whose retrieval logic will be completed during Milestone 2. The client is created
lazily so the application can boot even before credentials are provided.
"""

from typing import List, Optional

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class SearchService:
    """Thin wrapper around the Azure AI Search async client."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = None  # type: ignore[var-annotated]  # azure.search.documents.aio.SearchClient

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

    async def hybrid_search(
        self,
        query_text: str,
        query_vector: Optional[List[float]] = None,
        top_k: Optional[int] = None,
        intent_filter: Optional[str] = None,
    ) -> List[dict]:
        """Run a hybrid (BM25 + vector) query with semantic ranking.

        Args:
            query_text: Raw user query for the BM25 (keyword) leg of the search.
            query_vector: 768-dim embedding (from Gemini embeddings) for the vector leg.
            top_k: Number of chunks to return; defaults to the configured value.
            intent_filter: Optional OData filter to scope results to one intent label.

        Returns:
            A list of knowledge-base chunk dictionaries (empty when not configured).
        """
        if self._client is None:
            logger.warning("hybrid_search called but Azure AI Search client is not ready.")
            return []

        top_k = top_k or self._settings.azure_search_top_k

        # TODO (Milestone 2): build and execute the hybrid + semantic query, e.g.
        #   from azure.search.documents.models import VectorizedQuery
        #   vector_query = VectorizedQuery(
        #       vector=query_vector,
        #       k_nearest_neighbors=top_k,
        #       fields=self._settings.azure_search_vector_field,
        #   )
        #   results = await self._client.search(
        #       search_text=query_text,
        #       vector_queries=[vector_query],
        #       query_type="semantic",
        #       semantic_configuration_name=self._settings.azure_search_semantic_config,
        #       filter=f"intent_label eq '{intent_filter}'" if intent_filter else None,
        #       top=top_k,
        #   )
        #   return [doc async for doc in results]
        raise NotImplementedError("Hybrid retrieval will be implemented in Milestone 2.")

    async def ping(self) -> bool:
        """Lightweight health probe used by the /health endpoint."""
        return self._client is not None

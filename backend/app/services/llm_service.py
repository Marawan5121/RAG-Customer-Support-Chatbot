"""Google Generative AI service - Gemini 1.5 Flash generation and 768-dim embeddings.

Configuration placeholder built on the official ``google-generativeai`` library.
The same service exposes both the embedding model (used to build vectors for
Azure AI Search) and the generation model (used for grounded responses).

Note: the ``google-generativeai`` SDK is synchronous, so blocking calls are
offloaded to a worker thread with ``asyncio.to_thread`` to keep the event loop free.
"""

import asyncio
from typing import List

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class LLMService:
    """Wrapper around Gemini generation and embedding endpoints."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._configured = False
        self._genai = None  # google.generativeai module handle

    @property
    def is_configured(self) -> bool:
        """Return True when a Google API key is present."""
        return self._settings.google_configured

    async def connect(self) -> None:
        """Configure the Google Generative AI client with the API key."""
        if not self.is_configured:
            logger.warning("Google Generative AI is not configured; LLM features are disabled.")
            return

        import google.generativeai as genai

        genai.configure(api_key=self._settings.google_api_key)
        self._genai = genai
        self._configured = True
        logger.info(
            "Google Generative AI configured (model=%s, embeddings=%s, dims=%d).",
            self._settings.gemini_model,
            self._settings.gemini_embedding_model,
            self._settings.embedding_dimensions,
        )

    async def close(self) -> None:
        """No persistent connection to release; kept for lifecycle symmetry."""
        self._genai = None
        self._configured = False

    async def embed_text(self, text: str) -> List[float]:
        """Generate a 768-dim embedding vector for the given text."""
        if not self._configured:
            raise RuntimeError("LLMService is not configured.")

        def _embed() -> List[float]:
            result = self._genai.embed_content(
                model=self._settings.gemini_embedding_model,
                content=text,
                task_type="retrieval_query",
            )
            return result["embedding"]

        # TODO (Milestone 2): switch task_type to 'retrieval_document' when indexing.
        return await asyncio.to_thread(_embed)

    async def generate(self, prompt: str) -> str:
        """Generate a grounded response with Gemini 1.5 Flash."""
        if not self._configured:
            raise RuntimeError("LLMService is not configured.")

        def _generate() -> str:
            model = self._genai.GenerativeModel(self._settings.gemini_model)
            response = model.generate_content(prompt)
            return response.text

        # TODO (Milestone 2): build a RAG prompt template that injects retrieved
        # context chunks and enforces the no-PII / cite-policy system instructions.
        return await asyncio.to_thread(_generate)

    async def ping(self) -> bool:
        """Lightweight health probe used by the /health endpoint."""
        return self._configured

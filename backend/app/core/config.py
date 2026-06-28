"""Application configuration and environment variable loaders.

All settings are loaded from environment variables (or a local .env file) using
pydantic-settings. Grouped settings keep the Azure, Redis and Google
credentials clearly separated and easy to override per environment.
"""

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings loaded from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # General application settings
    # ------------------------------------------------------------------
    app_name: str = Field(default="Customer Support RAG Chatbot")
    environment: str = Field(default="development")  # development | staging | production
    debug: bool = Field(default=True)
    log_level: str = Field(default="INFO")
    api_v1_prefix: str = Field(default="/api/v1")

    # Comma-separated list of allowed CORS origins (e.g. the Next.js frontend)
    cors_origins: List[str] = Field(default=["http://localhost:3000"])

    # ------------------------------------------------------------------
    # Azure AI Search (vector + BM25 hybrid retrieval with semantic ranking)
    # ------------------------------------------------------------------
    azure_search_endpoint: str = Field(default="")
    azure_search_api_key: str = Field(default="")
    azure_search_index_name: str = Field(default="support-knowledge-index")
    azure_search_semantic_config: str = Field(default="mySemanticConfig")
    azure_search_vector_field: str = Field(default="content_vector")
    azure_search_top_k: int = Field(default=4)

    # ------------------------------------------------------------------
    # Azure Cosmos DB (session & message chat history)
    # ------------------------------------------------------------------
    cosmos_endpoint: str = Field(default="")
    cosmos_key: str = Field(default="")
    cosmos_database: str = Field(default="support-chat")
    cosmos_sessions_container: str = Field(default="sessions")
    cosmos_messages_container: str = Field(default="messages")

    # ------------------------------------------------------------------
    # Azure Cache for Redis (response caching)
    # ------------------------------------------------------------------
    redis_host: str = Field(default="redis")
    redis_port: int = Field(default=6379)
    redis_password: str = Field(default="")
    redis_ssl: bool = Field(default=False)  # True for Azure Cache for Redis, False for local
    redis_db: int = Field(default=0)
    redis_cache_ttl_seconds: int = Field(default=3600)  # 1 hour response cache TTL

    # ------------------------------------------------------------------
    # Google Generative AI (Gemini 1.5 Flash generation + 768-dim embeddings)
    # ------------------------------------------------------------------
    google_api_key: str = Field(default="")
    gemini_model: str = Field(default="gemini-2.0-flash")
    gemini_embedding_model: str = Field(default="text-embedding-004")
    embedding_dimensions: int = Field(default=768)

    # ------------------------------------------------------------------
    # Data ingestion, preprocessing & indexing (Milestone 1 / 2)
    # ------------------------------------------------------------------
    huggingface_dataset: str = Field(
        default="bitext/Bitext-customer-support-llm-chatbot-training-dataset"
    )
    # Default chunking profile key: "256", "512" or "1024" (token sizes)
    default_chunk_profile: str = Field(default="512")
    # When True, compose the customer query together with the support answer into
    # each indexed document; when False, index the support answer only.
    index_include_instruction: bool = Field(default=False)
    # Batch sizes for embedding requests and Azure AI Search uploads
    embedding_batch_size: int = Field(default=100)
    upload_batch_size: int = Field(default=500)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        """Allow CORS origins to be provided as a comma-separated string."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    # ------------------------------------------------------------------
    # Convenience flags used by services to decide if they are configured
    # ------------------------------------------------------------------
    @property
    def azure_search_configured(self) -> bool:
        return bool(self.azure_search_endpoint and self.azure_search_api_key)

    @property
    def cosmos_configured(self) -> bool:
        return bool(self.cosmos_endpoint and self.cosmos_key)

    @property
    def google_configured(self) -> bool:
        return bool(self.google_api_key)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (loaded once per process)."""
    return Settings()

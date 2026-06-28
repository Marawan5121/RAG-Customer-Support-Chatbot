"""Preprocessing service - Milestone 1 (Data Ingestion & Preprocessing).

Responsibilities:
    * Ingest the Bitext customer-support dataset via the Hugging Face ``datasets``
      library.
    * Clean and unify the text (Unicode normalisation, whitespace collapsing).
    * Resolve Bitext PII placeholder templates (e.g. ``{{Order Number}}``) into a
      consistent normalised token.
    * Deduplicate the corpus.
    * Split documents into chunks with LangChain's ``RecursiveCharacterTextSplitter``,
      configured for the three lecturer-mandated token profiles (256/64, 512/128,
      1024/256), and report chunk distribution statistics for the optimisation study.

The heavy third-party imports (datasets, langchain, tiktoken) are loaded lazily so
the application can boot without them and only requires them at indexing time.
"""

import hashlib
import re
import unicodedata
from collections import Counter
from typing import Dict, List, Optional, Tuple

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Lecturer-mandated chunking profiles: key -> (chunk_size, chunk_overlap) in TOKENS.
CHUNK_PROFILES: Dict[str, Dict[str, int]] = {
    "256": {"chunk_size": 256, "chunk_overlap": 64},
    "512": {"chunk_size": 512, "chunk_overlap": 128},
    "1024": {"chunk_size": 1024, "chunk_overlap": 256},
}

# Matches Bitext PII placeholders such as {{Order Number}} or {{Customer Name}}.
_PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*(.*?)\s*\}\}")
_WHITESPACE_PATTERN = re.compile(r"\s+")
# Token encoding used both by the splitter and for token-count statistics.
_TOKEN_ENCODING = "cl100k_base"


class PreprocessingService:
    """Stateless utility for ingesting and preparing the Bitext corpus."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._raw_cache: Optional[List[dict]] = None  # cached cleaned raw rows
        self._encoder = None  # cached tiktoken encoder

    # ------------------------------------------------------------------
    # Text cleaning & placeholder normalisation
    # ------------------------------------------------------------------
    @staticmethod
    def resolve_placeholders(text: str) -> str:
        """Normalise ``{{Some Placeholder}}`` templates into ``[SOME_PLACEHOLDER]``.

        This removes the noisy double-brace syntax while preserving the semantic
        slot, so embeddings see a consistent token across all placeholder variants.
        """

        def _normalise(match: re.Match) -> str:
            inner = match.group(1).strip().upper()
            inner = re.sub(r"[^A-Z0-9]+", "_", inner).strip("_")
            return f"[{inner}]" if inner else ""

        return _PLACEHOLDER_PATTERN.sub(_normalise, text)

    def clean_text(self, text: str) -> str:
        """Apply Unicode normalisation, placeholder resolution and whitespace cleanup."""
        if not text:
            return ""
        text = unicodedata.normalize("NFKC", text)
        text = self.resolve_placeholders(text)
        text = _WHITESPACE_PATTERN.sub(" ", text).strip()
        return text

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------
    def _load_raw(self) -> List[dict]:
        """Load and clean the raw dataset rows (cached after the first call).

        Returns a list of dicts with: source_row_id, intent, category,
        instruction (cleaned), response (cleaned).
        """
        if self._raw_cache is not None:
            return self._raw_cache

        from datasets import load_dataset

        dataset_name = self._settings.huggingface_dataset
        logger.info("Loading Hugging Face dataset '%s' (split=train).", dataset_name)
        dataset = load_dataset(dataset_name, split="train")
        logger.info("Dataset loaded: %d raw rows.", len(dataset))

        rows: List[dict] = []
        for idx, row in enumerate(dataset):
            rows.append(
                {
                    "source_row_id": idx,
                    "intent": (row.get("intent") or "").strip(),
                    "category": (row.get("category") or "").strip(),
                    "instruction": self.clean_text(row.get("instruction") or ""),
                    "response": self.clean_text(row.get("response") or ""),
                }
            )

        self._raw_cache = rows
        logger.info("Cleaning complete: %d rows cleaned and cached.", len(rows))
        return rows

    def _build_content(self, row: dict) -> str:
        """Compose the indexable content for a row.

        Defaults to the support answer only; when ``index_include_instruction`` is
        enabled, the customer query is prepended to enrich retrieval signal and to
        make the chunking study more meaningful on longer documents.
        """
        if self._settings.index_include_instruction:
            return f"Customer query: {row['instruction']}\nSupport answer: {row['response']}"
        return row["response"]

    def prepare_records(
        self,
        limit: Optional[int] = None,
        dedupe: bool = True,
    ) -> Tuple[List[dict], dict]:
        """Build deduplicated, indexable records from the cleaned corpus.

        Returns a tuple of (records, stats). Each record contains: source_row_id,
        intent, category, content_text.
        """
        raw_rows = self._load_raw()

        records: List[dict] = []
        seen_hashes: set = set()
        duplicates = 0

        for row in raw_rows:
            content = self._build_content(row)
            if not content:
                continue

            if dedupe:
                fingerprint = hashlib.sha256(content.lower().encode("utf-8")).hexdigest()
                if fingerprint in seen_hashes:
                    duplicates += 1
                    continue
                seen_hashes.add(fingerprint)

            records.append(
                {
                    "source_row_id": row["source_row_id"],
                    "intent": row["intent"],
                    "category": row["category"],
                    "content_text": content,
                }
            )

            if limit is not None and len(records) >= limit:
                break

        stats = {
            "rows_loaded": len(raw_rows),
            "duplicates_removed": duplicates,
            "rows_after_dedup": len(records),
        }
        logger.info(
            "Prepared records: loaded=%d, duplicates_removed=%d, kept=%d (dedupe=%s, limit=%s).",
            stats["rows_loaded"],
            duplicates,
            len(records),
            dedupe,
            limit,
        )
        return records, stats

    # ------------------------------------------------------------------
    # Chunking
    # ------------------------------------------------------------------
    def _get_encoder(self):
        """Return a cached tiktoken encoder used for token counting."""
        if self._encoder is None:
            import tiktoken

            self._encoder = tiktoken.get_encoding(_TOKEN_ENCODING)
        return self._encoder

    def count_tokens(self, text: str) -> int:
        """Count tokens in ``text`` using the configured encoding."""
        return len(self._get_encoder().encode(text))

    def _build_splitter(self, profile: str):
        """Create a token-based RecursiveCharacterTextSplitter for a profile."""
        if profile not in CHUNK_PROFILES:
            raise ValueError(
                f"Unknown chunk profile '{profile}'. Valid profiles: {list(CHUNK_PROFILES)}"
            )

        from langchain_text_splitters import RecursiveCharacterTextSplitter

        config = CHUNK_PROFILES[profile]
        # from_tiktoken_encoder measures chunk_size / overlap in TOKENS rather than
        # characters, so the configured 256/512/1024 sizes are honoured precisely.
        return RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name=_TOKEN_ENCODING,
            chunk_size=config["chunk_size"],
            chunk_overlap=config["chunk_overlap"],
        )

    def chunk_records(self, records: List[dict], profile: str) -> Tuple[List[dict], dict]:
        """Split records into chunks using the given profile.

        Returns a tuple of (chunk_docs, stats). Each chunk doc contains:
        chunk_id, content_text, intent_label, category, source_row_id.
        """
        splitter = self._build_splitter(profile)

        chunk_docs: List[dict] = []
        token_counts: List[int] = []
        intent_counter: Counter = Counter()
        category_counter: Counter = Counter()

        for record in records:
            pieces = splitter.split_text(record["content_text"])
            for chunk_index, piece in enumerate(pieces):
                chunk_id = f"row{record['source_row_id']}_chunk{chunk_index}"
                chunk_docs.append(
                    {
                        "chunk_id": chunk_id,
                        "content_text": piece,
                        "intent_label": record["intent"],
                        "category": record["category"],
                        "source_row_id": int(record["source_row_id"]),
                    }
                )
                token_counts.append(self.count_tokens(piece))
                intent_counter[record["intent"]] += 1
                category_counter[record["category"]] += 1

        stats = {
            "profile": profile,
            "chunk_size": CHUNK_PROFILES[profile]["chunk_size"],
            "chunk_overlap": CHUNK_PROFILES[profile]["chunk_overlap"],
            "total_documents": len(records),
            "total_chunks": len(chunk_docs),
            "token_stats": self._token_stats(token_counts),
            "avg_chunks_per_document": round(len(chunk_docs) / len(records), 3) if records else 0,
            "intent_distribution": dict(intent_counter),
            "category_distribution": dict(category_counter),
        }
        logger.info(
            "Chunking (profile=%s): %d documents -> %d chunks (avg %.2f tokens/chunk).",
            profile,
            len(records),
            len(chunk_docs),
            stats["token_stats"]["avg"],
        )
        return chunk_docs, stats

    @staticmethod
    def _token_stats(token_counts: List[int]) -> dict:
        """Compute min/max/avg/total token statistics for a list of chunks."""
        if not token_counts:
            return {"min": 0, "max": 0, "avg": 0.0, "total": 0}
        return {
            "min": min(token_counts),
            "max": max(token_counts),
            "avg": round(sum(token_counts) / len(token_counts), 2),
            "total": sum(token_counts),
        }

    # ------------------------------------------------------------------
    # Chunking optimisation study (lecturer requirement)
    # ------------------------------------------------------------------
    def benchmark_chunk_profiles(
        self,
        sample_size: Optional[int] = None,
        profiles: Optional[List[str]] = None,
    ) -> dict:
        """Run all (or selected) chunk profiles over a sample and report distributions.

        This produces the comparison data for the chunk-size optimisation study
        (256/64 vs 512/128 vs 1024/256) without performing any embedding or upload.
        """
        profiles = profiles or list(CHUNK_PROFILES.keys())
        records, prep_stats = self.prepare_records(limit=sample_size, dedupe=True)

        results: Dict[str, dict] = {}
        for profile in profiles:
            _, stats = self.chunk_records(records, profile)
            # Drop the verbose distributions for a compact comparison payload.
            results[profile] = {
                "chunk_size": stats["chunk_size"],
                "chunk_overlap": stats["chunk_overlap"],
                "total_documents": stats["total_documents"],
                "total_chunks": stats["total_chunks"],
                "avg_chunks_per_document": stats["avg_chunks_per_document"],
                "token_stats": stats["token_stats"],
            }

        return {
            "sample": prep_stats,
            "profiles": results,
        }

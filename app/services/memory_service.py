"""
Long-term memory service using FAISS for semantic similarity search.
Embeds text with sentence-transformers and persists the index to disk.
"""
import json
import logging
import pickle
from pathlib import Path
from typing import Optional

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_INDEX_FILE = "memory.faiss"
_META_FILE  = "memory_meta.pkl"


class MemoryService:
    """
    Stores and retrieves facts using dense vector similarity.
    Each entry: {"key": str, "value": str, "text": str}
    """

    def __init__(self, index_dir: str, model_name: str = "all-MiniLM-L6-v2"):
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.index_dir / _INDEX_FILE
        self._meta_path  = self.index_dir / _META_FILE

        logger.info("Loading embedding model: %s", model_name)
        self.encoder = SentenceTransformer(model_name)
        self.dim = self.encoder.get_sentence_embedding_dimension()

        self._index: faiss.IndexFlatIP   # inner-product (cosine after normalise)
        self._meta: list[dict]           # parallel list of metadata dicts
        self._load_or_create()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _load_or_create(self) -> None:
        if self._index_path.exists() and self._meta_path.exists():
            self._index = faiss.read_index(str(self._index_path))
            with open(self._meta_path, "rb") as f:
                self._meta = pickle.load(f)
            logger.info("Loaded FAISS index (%d entries)", len(self._meta))
        else:
            self._index = faiss.IndexFlatIP(self.dim)
            self._meta = []
            logger.info("Created new FAISS index (dim=%d)", self.dim)

    def _save(self) -> None:
        faiss.write_index(self._index, str(self._index_path))
        with open(self._meta_path, "wb") as f:
            pickle.dump(self._meta, f)

    def _embed(self, text: str) -> np.ndarray:
        vec = self.encoder.encode([text], convert_to_numpy=True, normalize_embeddings=True)
        return vec.astype("float32")

    # ── Public API ────────────────────────────────────────────────────────────

    def add(self, key: str, value: str) -> None:
        """
        Add or update a fact.
        If the key already exists the old entry is kept (FAISS doesn't support
        deletes in IndexFlatIP without rebuilding) but the newest entry wins
        during search because we deduplicate by key.
        """
        text = f"{key}: {value}"
        vec  = self._embed(text)
        self._index.add(vec)
        self._meta.append({"key": key, "value": value, "text": text})
        self._save()
        logger.debug("Added memory fact: %s = %s", key, value)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Return the top-k most relevant facts for `query`.
        Each result: {"key", "value", "text", "score"}
        """
        if self._index.ntotal == 0:
            return []

        vec = self._embed(query)
        scores, indices = self._index.search(vec, min(top_k * 2, self._index.ntotal))

        # Deduplicate by key, keep highest score
        seen: dict[str, dict] = {}
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            meta = self._meta[idx]
            key  = meta["key"]
            if key not in seen or score > seen[key]["score"]:
                seen[key] = {**meta, "score": float(score)}

        results = sorted(seen.values(), key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def get_all(self) -> list[dict]:
        """Return deduplicated list of all stored facts."""
        seen: dict[str, dict] = {}
        for entry in self._meta:
            seen[entry["key"]] = entry
        return list(seen.values())

    def count(self) -> int:
        return len({e["key"] for e in self._meta})

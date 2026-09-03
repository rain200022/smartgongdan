import hashlib
import math
import re
from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings
from app.core.exceptions import EmbeddingServiceError


class EmbeddingService(Protocol):
    model_name: str
    dimensions: int

    def embed(self, text: str) -> list[float]: ...


class LocalEmbeddingService:
    """Stable feature-hashing embedding for offline MVP development."""

    def __init__(self, model_name: str = "local-hash-v1", dimensions: int = 128) -> None:
        self.model_name = model_name
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        tokens = self._tokenize(text)
        if not tokens:
            raise EmbeddingServiceError("Cannot embed empty text")
        vector = [0.0] * self.dimensions
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            raise EmbeddingServiceError("Embedding normalization failed")
        return [value / norm for value in vector]

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        lowered = text.lower()
        tokens = re.findall(r"[a-z0-9][a-z0-9_.-]*", lowered)
        for sequence in re.findall(r"[\u4e00-\u9fff]+", lowered):
            tokens.extend(sequence)
            tokens.extend(sequence[index : index + 2] for index in range(len(sequence) - 1))
        return tokens


@lru_cache
def get_embedding_service() -> EmbeddingService:
    settings = get_settings()
    if settings.embedding_provider == "local":
        return LocalEmbeddingService(settings.embedding_model, settings.embedding_dimensions)
    raise EmbeddingServiceError(f"Unsupported EMBEDDING_PROVIDER: {settings.embedding_provider}")

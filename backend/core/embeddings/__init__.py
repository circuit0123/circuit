"""Embeddings behind one interface: fastembed in real use, a deterministic fake in tests."""

import hashlib
import math
import struct
from typing import TYPE_CHECKING, Protocol

from django.conf import settings

if TYPE_CHECKING:
    from fastembed import TextEmbedding

DIMS = 384


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FakeEmbeddingProvider:
    """Hashes words into a fixed vector, so texts sharing words are closer. No network, no model."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    @staticmethod
    def _one(text: str) -> list[float]:
        vec = [0.0] * DIMS
        for word in text.lower().split():
            digest = hashlib.sha256(word.encode()).digest()
            for i in range(0, 16, 4):
                idx = struct.unpack("<I", digest[i : i + 4])[0] % DIMS
                vec[idx] += 1.0 if digest[i] % 2 else -1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class FastEmbedProvider:
    """BAAI/bge-small-en-v1.5 (384 dims). The model is loaded lazily on first use."""

    _model: "TextEmbedding | None" = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        if FastEmbedProvider._model is None:
            from fastembed import TextEmbedding

            FastEmbedProvider._model = TextEmbedding("BAAI/bge-small-en-v1.5")
        model = FastEmbedProvider._model
        return [list(map(float, v)) for v in model.embed(texts)]


_provider: EmbeddingProvider | None = None


def get_embedder() -> EmbeddingProvider:
    global _provider
    if _provider is None:
        _provider = FakeEmbeddingProvider() if settings.EMBEDDING_PROVIDER == "fake" else FastEmbedProvider()
    return _provider


def set_embedder(provider: EmbeddingProvider | None) -> None:
    global _provider
    _provider = provider


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0

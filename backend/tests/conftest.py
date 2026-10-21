import fakeredis
import pytest

from core import cache, embeddings, llm


@pytest.fixture(autouse=True)
def fakes():
    """No live network in tests: fake Redis, fake embeddings, mocked LLM."""
    cache.set_cache(cache.Cache(fakeredis.FakeRedis()))
    embeddings.set_embedder(embeddings.FakeEmbeddingProvider())
    fake = llm.FakeLLM()
    llm.set_llm(fake)
    yield fake
    cache.set_cache(None)
    embeddings.set_embedder(None)
    llm.set_llm(None)


@pytest.fixture
def fake_llm(fakes):
    return fakes

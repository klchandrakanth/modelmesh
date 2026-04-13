"""Tests for RedisCache using fakeredis."""
import pytest
import fakeredis.aioredis  # type: ignore
from modelmesh.cache.redis_cache import RedisCache

MESSAGES = [{"role": "user", "content": "Hello, world"}]
MODEL = "llama3.2:3b"
RESPONSE = {
    "id": "chatcmpl-1",
    "model": MODEL,
    "choices": [{"message": {"role": "assistant", "content": "Hi!"}}],
    "usage": {"total_tokens": 10},
}


@pytest.fixture
async def cache():
    """RedisCache backed by fakeredis (no real Redis needed)."""
    c = RedisCache(url="redis://localhost:6379", ttl=60)
    # Replace the redis instance with a fake one
    c._redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    return c


@pytest.mark.asyncio
async def test_get_returns_none_when_empty(cache):
    result = await cache.get(MODEL, MESSAGES)
    assert result is None


@pytest.mark.asyncio
async def test_set_and_get_roundtrip(cache):
    await cache.set(MODEL, MESSAGES, RESPONSE)
    result = await cache.get(MODEL, MESSAGES)
    assert result == RESPONSE


@pytest.mark.asyncio
async def test_different_messages_have_different_keys(cache):
    msgs_a = [{"role": "user", "content": "Hello"}]
    msgs_b = [{"role": "user", "content": "World"}]
    await cache.set(MODEL, msgs_a, RESPONSE)

    result_a = await cache.get(MODEL, msgs_a)
    result_b = await cache.get(MODEL, msgs_b)

    assert result_a == RESPONSE
    assert result_b is None


@pytest.mark.asyncio
async def test_different_models_have_different_keys(cache):
    await cache.set("model-a", MESSAGES, RESPONSE)

    result_a = await cache.get("model-a", MESSAGES)
    result_b = await cache.get("model-b", MESSAGES)

    assert result_a == RESPONSE
    assert result_b is None


@pytest.mark.asyncio
async def test_health_check_true_when_connected(cache):
    assert await cache.health_check() is True


@pytest.mark.asyncio
async def test_get_returns_none_when_redis_unavailable():
    c = RedisCache()
    c._redis = None
    result = await c.get(MODEL, MESSAGES)
    assert result is None


@pytest.mark.asyncio
async def test_set_is_noop_when_redis_unavailable():
    c = RedisCache()
    c._redis = None
    # Should not raise
    await c.set(MODEL, MESSAGES, RESPONSE)


@pytest.mark.asyncio
async def test_health_check_false_when_redis_unavailable():
    c = RedisCache()
    c._redis = None
    assert await c.health_check() is False

import asyncio
import pytest
from modelmesh.router.circuit_breaker import CircuitBreaker, CircuitState


async def _ok():
    return "ok"


async def _fail():
    raise ValueError("boom")


@pytest.mark.asyncio
async def test_closed_by_default():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0, name="test")
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_success_passes_through():
    cb = CircuitBreaker(failure_threshold=3)
    result = await cb.call(_ok())
    assert result == "ok"


@pytest.mark.asyncio
async def test_failure_re_raises():
    cb = CircuitBreaker(failure_threshold=3)
    with pytest.raises(ValueError, match="boom"):
        await cb.call(_fail())


@pytest.mark.asyncio
async def test_opens_after_threshold_failures():
    cb = CircuitBreaker(failure_threshold=3)
    for _ in range(3):
        with pytest.raises(ValueError):
            await cb.call(_fail())
    assert cb.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_open_rejects_calls_immediately():
    cb = CircuitBreaker(failure_threshold=3)
    for _ in range(3):
        with pytest.raises(ValueError):
            await cb.call(_fail())

    # When circuit is open, cb.call raises before awaiting — pass a coroutine
    # that we close afterward to silence the "never awaited" warning.
    coro = _ok()
    with pytest.raises(RuntimeError, match="OPEN"):
        await cb.call(coro)
    coro.close()  # suppress ResourceWarning


@pytest.mark.asyncio
async def test_transitions_to_half_open_after_timeout():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.05)
    for _ in range(2):
        with pytest.raises(ValueError):
            await cb.call(_fail())
    assert cb.state == CircuitState.OPEN
    await asyncio.sleep(0.1)
    assert cb.state == CircuitState.HALF_OPEN


@pytest.mark.asyncio
async def test_closes_after_success_in_half_open():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.05)
    for _ in range(2):
        with pytest.raises(ValueError):
            await cb.call(_fail())
    await asyncio.sleep(0.1)
    assert cb.state == CircuitState.HALF_OPEN
    await cb.call(_ok())
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_resets_failure_count_on_success():
    cb = CircuitBreaker(failure_threshold=3)
    for _ in range(2):
        with pytest.raises(ValueError):
            await cb.call(_fail())
    await cb.call(_ok())  # success resets
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0

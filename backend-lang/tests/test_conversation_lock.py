import asyncio

import pytest

from services import inbound_message_service as ims


@pytest.mark.asyncio
async def test_candado_serializa_la_misma_conversacion(monkeypatch):
    class _Sess:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def execute(self, *a, **k): return None

    monkeypatch.setattr(ims, "AsyncSessionLocal", lambda: _Sess())
    inside, overlap = 0, False

    async def job():
        nonlocal inside, overlap
        async with ims._conversation_lock("c1"):
            inside += 1
            overlap = overlap or inside > 1
            await asyncio.sleep(0.01)
            inside -= 1

    await asyncio.gather(*(job() for _ in range(5)))
    assert overlap is False


@pytest.mark.asyncio
async def test_candado_sigue_si_la_bd_falla(monkeypatch):
    class _Boom:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def execute(self, *a, **k): raise RuntimeError("db caída")

    monkeypatch.setattr(ims, "AsyncSessionLocal", lambda: _Boom())
    async with ims._conversation_lock("c2"):
        pass

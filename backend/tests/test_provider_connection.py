import asyncio

import httpx
import pytest

from app.providers.base import ProviderError, ProviderTimeout
from app.providers.hcompany import HCompanyProvider


@pytest.mark.parametrize("failure,expected", [(httpx.ReadTimeout, ProviderTimeout), (httpx.ConnectError, ProviderError)])
def test_transport_failure_does_not_expose_credentials(monkeypatch, failure, expected):
    class Client:
        def __init__(self, **_): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        async def post(self, *_args, **_kwargs):
            raise failure("transport detail that must stay private: test-key")
    monkeypatch.setattr(httpx, "AsyncClient", Client)
    provider = HCompanyProvider("test-key", "https://api.hcompany.ai/v1", "holo4-27b")
    with pytest.raises(expected) as error:
        asyncio.run(provider.complete_json("Return an object", {"type": "object"}, "test"))
    assert "test-key" not in str(error.value)
    assert "transport detail" not in str(error.value)

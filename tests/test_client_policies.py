"""
ADR-003: Client Policies Tests
"""

from unittest.mock import patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


class FakeResponse:
    def __init__(self, status_code=200, content=b"OK"):
        self.status_code = status_code
        self._content = content

    async def aread(self):
        return self._content


class FakeClient:
    def __init__(self, sequence):
        self.sequence = sequence
        self.calls = 0

    async def get(self, url):
        i = self.calls
        self.calls += 1
        item = self.sequence[i] if i < len(self.sequence) else self.sequence[-1]
        if isinstance(item, Exception):
            raise item
        return item


@pytest.mark.asyncio
async def test_fetch_valid_url_accepted(client):
    fake = FakeClient([FakeResponse(200, b"Hello world")])

    async def fake_get_client():
        return fake

    with patch("app.main.get_http_client", fake_get_client):
        r = await client.post("/fetch", json={"url": "http://example.com/"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == 200
        assert "Hello world" in data["content_snippet"]


@pytest.mark.asyncio
async def test_fetch_timeout_then_success_retries(client):
    seq = [httpx.ReadTimeout("read timeout"), FakeResponse(200, b"Recovered")]
    fake = FakeClient(seq)

    async def fake_get_client():
        return fake

    with patch("app.main.get_http_client", fake_get_client):
        r = await client.post("/fetch", json={"url": "http://example.com/"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == 200
        assert "Recovered" in data["content_snippet"]
        assert fake.calls >= 2


@pytest.mark.asyncio
async def test_fetch_private_ip_blocked(client):
    r = await client.post("/fetch", json={"url": "http://127.0.0.1/secret"})
    assert r.status_code == 422
    body = r.json()
    assert "local" in body["detail"].lower() or "127.0.0.1" in body["detail"]

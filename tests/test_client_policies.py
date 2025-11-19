"""
ADR-003: Client Policies Tests
"""

import httpx
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


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


def test_fetch_valid_url_accepted(monkeypatch):
    fake = FakeClient([FakeResponse(200, b"Hello world")])

    async def fake_get_client():
        return fake

    monkeypatch.setattr("app.main.get_http_client", fake_get_client)

    r = client.post("/fetch", json={"url": "http://example.com/"})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == 200
    assert "Hello world" in data["content_snippet"]


def test_fetch_timeout_then_success_retries(monkeypatch):
    seq = [httpx.ReadTimeout("read timeout"), FakeResponse(200, b"Recovered")]
    fake = FakeClient(seq)

    async def fake_get_client():
        return fake

    monkeypatch.setattr("app.main.get_http_client", fake_get_client)

    r = client.post("/fetch", json={"url": "http://example.com/"})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == 200
    assert "Recovered" in data["content_snippet"]
    assert fake.calls >= 2


def test_fetch_private_ip_blocked():
    r = client.post("/fetch", json={"url": "http://127.0.0.1/secret"})
    assert r.status_code == 422
    body = r.json()
    assert "local" in body["detail"].lower() or "127.0.0.1" in body["detail"]

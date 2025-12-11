"""
ADR-003: Client Policies Tests
"""

from unittest.mock import patch

import httpx
import pytest


@pytest.mark.asyncio
async def test_fetch_valid_url_accepted(client_no_db, fake_response, fake_client):
    fake = fake_client([fake_response(200, b"Hello world")])

    async def fake_get_client():
        return fake

    with patch("app.main.get_http_client", fake_get_client):
        r = await client_no_db.post("/fetch", json={"url": "http://example.com/"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == 200
        assert "Hello world" in data["content_snippet"]


@pytest.mark.asyncio
async def test_fetch_timeout_then_success_retries(
    client_no_db, fake_response, fake_client
):
    seq = [httpx.ReadTimeout("read timeout"), fake_response(200, b"Recovered")]
    fake = fake_client(seq)

    async def fake_get_client():
        return fake

    with patch("app.main.get_http_client", fake_get_client):
        r = await client_no_db.post("/fetch", json={"url": "http://example.com/"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == 200
        assert "Recovered" in data["content_snippet"]
        assert fake.calls >= 2


@pytest.mark.asyncio
async def test_fetch_private_ip_blocked(client_no_db):
    r = await client_no_db.post("/fetch", json={"url": "http://127.0.0.1/secret"})
    assert r.status_code == 422
    body = r.json()
    assert "local" in body["detail"].lower() or "127.0.0.1" in body["detail"]

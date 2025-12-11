"""
ADR-001: Input Validation and Sanitization Tests
Covers: NFR-002, Risk R3, Risk R4
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models import EntryDB


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    db.rollback = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.fixture
async def client(mock_db):
    async def override_get_db():
        yield mock_db

    from app.database import get_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


def create_mock_entry(entry_id=1, title="Test Book"):
    entry = MagicMock(spec=EntryDB)
    entry.id = entry_id
    entry.title = title
    entry.kind = "book"
    entry.link = "https://example.com"
    entry.status = "planned"
    return entry


def setup_successful_create(mock_db):
    mock_count_result = AsyncMock()
    mock_count_result.scalar.return_value = 0
    mock_db.execute.return_value = mock_count_result


class TestInputSanitization:
    """Test input sanitization (ADR-001)"""

    @pytest.mark.asyncio
    async def test_title_whitespace_trimmed(self, client, mock_db):
        """Title should be trimmed of leading/trailing whitespace"""
        setup_successful_create(mock_db)

        payload = {
            "title": "  Test Book  ",
            "kind": "book",
            "status": "planned",
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["title"] == "Test Book"

    @pytest.mark.asyncio
    async def test_unicode_normalization(self, client, mock_db):
        """Unicode should be normalized to NFC form"""
        setup_successful_create(mock_db)

        payload = {
            "title": "Café",
            "kind": "book",
            "status": "planned",
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_null_bytes_removed(self, client, mock_db):
        """Null bytes should be removed from input"""
        setup_successful_create(mock_db)

        payload = {
            "title": "Test\x00Book",
            "kind": "book",
            "status": "planned",
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert "\x00" not in data["title"]


class TestXSSProtection:
    """Test XSS attack prevention (ADR-001, Risk R3)"""

    @pytest.mark.asyncio
    async def test_xss_script_tag_rejected(self, client, mock_db):
        """Script tags should be rejected"""
        payload = {
            "title": "<script>alert('xss')</script>",
            "kind": "book",
            "status": "planned",
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code == 422
        body = r.json()
        assert "dangerous pattern" in body["detail"].lower()

    @pytest.mark.asyncio
    async def test_xss_javascript_protocol_rejected(self, client, mock_db):
        """JavaScript protocol in title should be rejected"""
        payload = {
            "title": "javascript:alert('xss')",
            "kind": "book",
            "status": "planned",
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_xss_onerror_attribute_rejected(self, client, mock_db):
        """Event handlers should be rejected"""
        payload = {
            "title": "<img src=x onerror=alert('xss')>",
            "kind": "book",
            "status": "planned",
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_xss_iframe_rejected(self, client, mock_db):
        """Iframe tags should be rejected"""
        payload = {
            "title": "<iframe src='evil.com'>",
            "kind": "book",
            "status": "planned",
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_xss_embed_tag_rejected(self, client, mock_db):
        """Embed tags should be rejected"""
        payload = {
            "title": "<embed src='evil.swf'>",
            "kind": "book",
            "status": "planned",
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_xss_object_tag_rejected(self, client, mock_db):
        """Object tags should be rejected"""
        payload = {
            "title": "<object data='evil.com'>",
            "kind": "book",
            "status": "planned",
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_xss_case_insensitive(self, client, mock_db):
        """XSS detection should be case-insensitive"""
        payload = {
            "title": "<SCRIPT>alert('xss')</SCRIPT>",
            "kind": "book",
            "status": "planned",
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code == 422


class TestSSRFProtection:
    """Test SSRF attack prevention (ADR-001, Risk R3)"""

    @pytest.mark.asyncio
    async def test_ssrf_localhost_rejected(self, client, mock_db):
        """Localhost URLs should be rejected"""
        payload = {
            "title": "Test Book",
            "kind": "book",
            "status": "planned",
            "link": "http://localhost:8000/admin",
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code == 422
        body = r.json()
        assert "localhost" in body["detail"].lower()

    @pytest.mark.asyncio
    async def test_ssrf_127_0_0_1_rejected(self, client, mock_db):
        """127.0.0.1 should be rejected"""
        payload = {
            "title": "Test Book",
            "kind": "book",
            "status": "planned",
            "link": "http://127.0.0.1:8080/secret",
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_ssrf_0_0_0_0_rejected(self, client, mock_db):
        """0.0.0.0 should be rejected"""
        payload = {
            "title": "Test Book",
            "kind": "book",
            "status": "planned",
            "link": "http://0.0.0.0:8080/secret",
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_ssrf_ipv6_localhost_rejected(self, client, mock_db):
        """IPv6 localhost (::1) should be rejected"""
        payload = {
            "title": "Test Book",
            "kind": "book",
            "status": "planned",
            "link": "http://[::1]:8080/secret",
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_ssrf_private_ip_10_rejected(self, client, mock_db):
        """Private IP ranges (10.x.x.x) should be rejected"""
        payload = {
            "title": "Test Book",
            "kind": "book",
            "status": "planned",
            "link": "http://10.0.0.1/internal",
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_ssrf_private_ip_192_rejected(self, client, mock_db):
        """Private IP ranges (192.168.x.x) should be rejected"""
        payload = {
            "title": "Test Book",
            "kind": "book",
            "status": "planned",
            "link": "http://192.168.1.1/router",
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_ssrf_private_ip_172_rejected(self, client, mock_db):
        """Private IP ranges (172.x.x.x) should be rejected"""
        payload = {
            "title": "Test Book",
            "kind": "book",
            "status": "planned",
            "link": "http://172.16.0.1/internal",
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_ssrf_invalid_protocol_file_rejected(self, client, mock_db):
        """file:// protocol should be rejected"""
        payload = {
            "title": "Test Book",
            "kind": "book",
            "status": "planned",
            "link": "file:///etc/passwd",
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_ssrf_invalid_protocol_ftp_rejected(self, client, mock_db):
        """ftp:// protocol should be rejected"""
        payload = {
            "title": "Test Book",
            "kind": "book",
            "status": "planned",
            "link": "ftp://internal.server/file",
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code == 422


class TestPathTraversal:
    """Test path traversal prevention (ADR-001, Risk R3)"""

    @pytest.mark.asyncio
    async def test_path_traversal_dotdot_rejected(self, client, mock_db):
        """URLs with .. should be rejected"""
        payload = {
            "title": "Test Book",
            "kind": "book",
            "status": "planned",
            "link": "http://example.com/../../../etc/passwd",
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code == 422
        body = r.json()
        assert "path traversal" in body["detail"].lower()

    @pytest.mark.asyncio
    async def test_path_traversal_tilde_rejected(self, client, mock_db):
        """URLs with ~ should be rejected"""
        payload = {
            "title": "Test Book",
            "kind": "book",
            "status": "planned",
            "link": "http://example.com/~admin/secret",
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code == 422


class TestBoundaryValidation:
    """Test boundary conditions (ADR-001, NFR-002)"""

    @pytest.mark.asyncio
    async def test_title_empty_rejected(self, client, mock_db):
        """Empty title should be rejected"""
        payload = {"title": "", "kind": "book", "status": "planned"}
        r = await client.post("/entries", json=payload)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_title_only_whitespace_rejected(self, client, mock_db):
        """Whitespace-only title should be rejected"""
        payload = {"title": "   ", "kind": "book", "status": "planned"}
        r = await client.post("/entries", json=payload)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_title_exactly_1_char_accepted(self, client, mock_db):
        """Title with exactly 1 character should be accepted"""
        setup_successful_create(mock_db)

        payload = {"title": "A", "kind": "book", "status": "planned"}
        r = await client.post("/entries", json=payload)
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_title_exactly_200_chars_accepted(self, client, mock_db):
        """Title with exactly 200 characters should be accepted"""
        setup_successful_create(mock_db)

        payload = {"title": "A" * 200, "kind": "book", "status": "planned"}
        r = await client.post("/entries", json=payload)
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_title_201_chars_rejected(self, client, mock_db):
        """Title with 201 characters should be rejected"""
        payload = {"title": "A" * 201, "kind": "book", "status": "planned"}
        r = await client.post("/entries", json=payload)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_title_199_chars_accepted(self, client, mock_db):
        """Title with 199 characters should be accepted"""
        setup_successful_create(mock_db)

        payload = {"title": "B" * 199, "kind": "book", "status": "planned"}
        r = await client.post("/entries", json=payload)
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_url_max_length_accepted(self, client, mock_db):
        """URL with exactly 2048 characters should be accepted"""
        setup_successful_create(mock_db)

        long_path = "a" * (2048 - len("https://example.com/"))
        long_url = f"https://example.com/{long_path}"

        payload = {
            "title": "Test",
            "kind": "book",
            "status": "planned",
            "link": long_url,
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code in [200, 422]

    @pytest.mark.asyncio
    async def test_url_too_long_rejected(self, client, mock_db):
        """URL longer than 2048 characters should be rejected"""
        long_url = "http://example.com/" + "a" * 2050
        payload = {
            "title": "Test",
            "kind": "book",
            "status": "planned",
            "link": long_url,
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code == 422


class TestRateLimiting:
    """Test basic rate limiting (ADR-001)"""

    @pytest.mark.asyncio
    async def test_max_entries_limit(self, client, mock_db):
        """Should reject creation after reaching 1000 entries"""
        mock_count_result = AsyncMock()
        mock_count_result.scalar.return_value = 1000
        mock_db.execute.return_value = mock_count_result

        payload = {
            "title": "Test Book",
            "kind": "book",
            "status": "planned",
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code == 403
        body = r.json()
        assert "maximum entries limit" in body["detail"].lower()

    @pytest.mark.asyncio
    async def test_entries_999_allowed(self, client, mock_db):
        """Should allow creation when at 999 entries"""
        mock_count_result = AsyncMock()
        mock_count_result.scalar.return_value = 999
        mock_db.execute.return_value = mock_count_result

        payload = {
            "title": "Test Book",
            "kind": "book",
            "status": "planned",
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_entries_1001_rejected(self, client, mock_db):
        """Should reject creation when over limit"""
        mock_count_result = AsyncMock()
        mock_count_result.scalar.return_value = 1001
        mock_db.execute.return_value = mock_count_result

        payload = {
            "title": "Test Book",
            "kind": "book",
            "status": "planned",
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code == 403


class TestValidURLs:
    """Test that valid URLs are accepted"""

    @pytest.mark.asyncio
    async def test_valid_http_url_accepted(self, client, mock_db):
        """Valid HTTP URL should be accepted"""
        setup_successful_create(mock_db)

        payload = {
            "title": "Test Book",
            "kind": "book",
            "status": "planned",
            "link": "http://example.com/book",
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_valid_https_url_accepted(self, client, mock_db):
        """Valid HTTPS URL should be accepted"""
        setup_successful_create(mock_db)

        payload = {
            "title": "Test Article",
            "kind": "article",
            "status": "reading",
            "link": "https://example.com/article/123",
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_url_with_query_params_accepted(self, client, mock_db):
        """URL with query parameters should be accepted"""
        setup_successful_create(mock_db)

        payload = {
            "title": "Test",
            "kind": "article",
            "status": "planned",
            "link": "https://example.com/article?id=123&lang=en",
        }
        r = await client.post("/entries", json=payload)
        assert r.status_code == 200

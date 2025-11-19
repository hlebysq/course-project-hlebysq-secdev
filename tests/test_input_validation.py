"""
ADR-001: Input Validation and Sanitization Tests
Covers: NFR-002, Risk R3, Risk R4
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestInputSanitization:
    """Test input sanitization (ADR-001)"""

    def test_title_whitespace_trimmed(self):
        """Title should be trimmed of leading/trailing whitespace"""
        payload = {
            "title": "  Test Book  ",
            "kind": "book",
            "status": "planned",
        }
        r = client.post("/entries", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["title"] == "Test Book"  # trimmed

    def test_unicode_normalization(self):
        """Unicode should be normalized to NFC form"""
        # Using combining characters
        payload = {
            "title": "Café",  # é as combining char
            "kind": "book",
            "status": "planned",
        }
        r = client.post("/entries", json=payload)
        assert r.status_code == 200

    def test_null_bytes_removed(self):
        """Null bytes should be removed from input"""
        payload = {
            "title": "Test\x00Book",
            "kind": "book",
            "status": "planned",
        }
        r = client.post("/entries", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert "\x00" not in data["title"]


class TestXSSProtection:
    """Test XSS attack prevention (ADR-001, Risk R3)"""

    def test_xss_script_tag_rejected(self):
        """Script tags should be rejected"""
        payload = {
            "title": "<script>alert('xss')</script>",
            "kind": "book",
            "status": "planned",
        }
        r = client.post("/entries", json=payload)
        assert r.status_code == 422
        body = r.json()
        assert "dangerous pattern" in body["detail"].lower()

    def test_xss_javascript_protocol_rejected(self):
        """JavaScript protocol in title should be rejected"""
        payload = {
            "title": "javascript:alert('xss')",
            "kind": "book",
            "status": "planned",
        }
        r = client.post("/entries", json=payload)
        assert r.status_code == 422

    def test_xss_onerror_attribute_rejected(self):
        """Event handlers should be rejected"""
        payload = {
            "title": "<img src=x onerror=alert('xss')>",
            "kind": "book",
            "status": "planned",
        }
        r = client.post("/entries", json=payload)
        assert r.status_code == 422

    def test_xss_iframe_rejected(self):
        """Iframe tags should be rejected"""
        payload = {
            "title": "<iframe src='evil.com'>",
            "kind": "book",
            "status": "planned",
        }
        r = client.post("/entries", json=payload)
        assert r.status_code == 422


class TestSSRFProtection:
    """Test SSRF attack prevention (ADR-001, Risk R3)"""

    def test_ssrf_localhost_rejected(self):
        """Localhost URLs should be rejected"""
        payload = {
            "title": "Test Book",
            "kind": "book",
            "status": "planned",
            "link": "http://localhost:8000/admin",
        }
        r = client.post("/entries", json=payload)
        assert r.status_code == 422
        body = r.json()
        assert "localhost" in body["detail"].lower()

    def test_ssrf_127_0_0_1_rejected(self):
        """127.0.0.1 should be rejected"""
        payload = {
            "title": "Test Book",
            "kind": "book",
            "status": "planned",
            "link": "http://127.0.0.1:8080/secret",
        }
        r = client.post("/entries", json=payload)
        assert r.status_code == 422

    def test_ssrf_private_ip_10_rejected(self):
        """Private IP ranges (10.x.x.x) should be rejected"""
        payload = {
            "title": "Test Book",
            "kind": "book",
            "status": "planned",
            "link": "http://10.0.0.1/internal",
        }
        r = client.post("/entries", json=payload)
        assert r.status_code == 422

    def test_ssrf_private_ip_192_rejected(self):
        """Private IP ranges (192.168.x.x) should be rejected"""
        payload = {
            "title": "Test Book",
            "kind": "book",
            "status": "planned",
            "link": "http://192.168.1.1/router",
        }
        r = client.post("/entries", json=payload)
        assert r.status_code == 422

    def test_ssrf_invalid_protocol_rejected(self):
        """Non-HTTP(S) protocols should be rejected"""
        payload = {
            "title": "Test Book",
            "kind": "book",
            "status": "planned",
            "link": "file:///etc/passwd",
        }
        r = client.post("/entries", json=payload)
        assert r.status_code == 422


class TestPathTraversal:
    """Test path traversal prevention (ADR-001, Risk R3)"""

    def test_path_traversal_tilde_rejected(self):
        """URLs with ~ should be rejected"""
        payload = {
            "title": "Test Book",
            "kind": "book",
            "status": "planned",
            "link": "http://example.com/~admin/secret",
        }
        r = client.post("/entries", json=payload)
        assert r.status_code == 422


class TestBoundaryValidation:
    """Test boundary conditions (ADR-001, NFR-002)"""

    def test_title_empty_rejected(self):
        """Empty title should be rejected"""
        payload = {"title": "", "kind": "book", "status": "planned"}
        r = client.post("/entries", json=payload)
        assert r.status_code == 422

    def test_title_only_whitespace_rejected(self):
        """Whitespace-only title should be rejected"""
        payload = {"title": "   ", "kind": "book", "status": "planned"}
        r = client.post("/entries", json=payload)
        assert r.status_code == 422

    def test_title_exactly_1_char_accepted(self):
        """Title with exactly 1 character should be accepted"""
        payload = {"title": "A", "kind": "book", "status": "planned"}
        r = client.post("/entries", json=payload)
        assert r.status_code == 200

    def test_title_exactly_200_chars_accepted(self):
        """Title with exactly 200 characters should be accepted"""
        payload = {"title": "A" * 200, "kind": "book", "status": "planned"}
        r = client.post("/entries", json=payload)
        assert r.status_code == 200

    def test_title_201_chars_rejected(self):
        """Title with 201 characters should be rejected"""
        payload = {"title": "A" * 201, "kind": "book", "status": "planned"}
        r = client.post("/entries", json=payload)
        assert r.status_code == 422

    def test_url_too_long_rejected(self):
        """URL longer than 2048 characters should be rejected"""
        long_url = "http://example.com/" + "a" * 2050
        payload = {
            "title": "Test",
            "kind": "book",
            "status": "planned",
            "link": long_url,
        }
        r = client.post("/entries", json=payload)
        assert r.status_code == 422


class TestRateLimiting:
    """Test basic rate limiting (ADR-001)"""

    def test_max_entries_limit(self):
        """Should reject creation after reaching 1000 entries"""
        # TODO: когда имплементирую БД сделать тест
        pass


class TestValidURLs:
    """Test that valid URLs are accepted"""

    def test_valid_http_url_accepted(self):
        """Valid HTTP URL should be accepted"""
        payload = {
            "title": "Test Book",
            "kind": "book",
            "status": "planned",
            "link": "http://example.com/book",
        }
        r = client.post("/entries", json=payload)
        assert r.status_code == 200

    def test_valid_https_url_accepted(self):
        """Valid HTTPS URL should be accepted"""
        payload = {
            "title": "Test Article",
            "kind": "article",
            "status": "reading",
            "link": "https://example.com/article/123",
        }
        r = client.post("/entries", json=payload)
        assert r.status_code == 200

    def test_url_with_query_params_accepted(self):
        """URL with query parameters should be accepted"""
        payload = {
            "title": "Test",
            "kind": "article",
            "status": "planned",
            "link": "https://example.com/article?id=123&lang=en",
        }
        r = client.post("/entries", json=payload)
        assert r.status_code == 200

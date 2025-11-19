"""
ADR-002: RFC 7807 Error Handling Tests
Covers: NFR-001, Risk R4
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestRFC7807Format:
    """Test RFC 7807 Problem Details format (ADR-002)"""

    def test_not_found_rfc7807_structure(self):
        """Not found error should follow RFC 7807 format"""
        r = client.get("/entries/999")
        assert r.status_code == 404

        body = r.json()

        # Check all required RFC 7807 fields
        assert "type" in body
        assert "title" in body
        assert "status" in body
        assert "detail" in body
        assert "instance" in body
        assert "correlationId" in body

        assert body["status"] == 404
        assert "not-found" in body["type"]
        assert body["title"] == "Resource Not Found"
        assert body["instance"] == "/entries/999"

    def test_validation_error_rfc7807_structure(self):
        """Validation error should follow RFC 7807 format"""
        payload = {"title": "", "kind": "book", "status": "planned"}
        r = client.post("/entries", json=payload)
        assert r.status_code == 422

        body = r.json()

        # Check RFC 7807 structure
        assert "type" in body
        assert "title" in body
        assert "status" in body
        assert "detail" in body
        assert "instance" in body
        assert "correlationId" in body

        # Check values
        assert body["status"] == 422
        assert "validation-error" in body["type"]
        assert body["title"] == "Validation Error"

    def test_correlation_id_is_uuid(self):
        """Correlation ID should be a valid UUID format"""
        r = client.get("/entries/999")
        body = r.json()

        correlation_id = body["correlationId"]

        # Check UUID format (rough check)
        assert len(correlation_id) == 36  # UUID length with dashes
        assert correlation_id.count("-") == 4  # UUID has 4 dashes

    def test_correlation_id_in_response_header(self):
        """Correlation ID should also be in response headers"""
        r = client.get("/entries/999")

        assert "X-Correlation-ID" in r.headers
        header_id = r.headers["X-Correlation-ID"]

        # Should match body correlation ID
        body_id = r.json()["correlationId"]
        assert header_id == body_id

    def test_correlation_id_unique_per_request(self):
        """Each request should get a unique correlation ID"""
        r1 = client.get("/entries/999")
        r2 = client.get("/entries/998")

        id1 = r1.json()["correlationId"]
        id2 = r2.json()["correlationId"]

        assert id1 != id2


class TestErrorTypes:
    """Test different error types mapping (ADR-002)"""

    def test_not_found_error_type(self):
        """Not found should have correct type URI"""
        r = client.get("/entries/999")
        body = r.json()

        assert body["type"] == "https://api.secdev.com/errors/not-found"
        assert body["title"] == "Resource Not Found"

    def test_validation_error_type(self):
        """Validation error should have correct type URI"""
        payload = {"title": "", "kind": "book", "status": "planned"}
        r = client.post("/entries", json=payload)
        body = r.json()

        assert body["type"] == "https://api.secdev.com/errors/validation-error"
        assert body["title"] == "Validation Error"


class TestErrorDetailMasking:
    """Test that error details don't leak sensitive info (ADR-002, Risk R4)"""

    def test_validation_error_no_stack_trace(self):
        """Validation errors should not include stack traces"""
        payload = {"title": "", "kind": "book", "status": "planned"}
        r = client.post("/entries", json=payload)
        body = r.json()

        # Should not contain stack trace keywords
        body_str = str(body)
        assert "Traceback" not in body_str
        assert 'File "' not in body_str
        assert ".py" not in body_str or ".py" in body["type"]

    def test_not_found_no_internal_details(self):
        """Not found error should not leak internal implementation details"""
        r = client.get("/entries/999")
        body = r.json()

        detail = body["detail"].lower()

        # Should not contain internal implementation details
        assert "_db" not in detail
        assert "dict" not in detail
        assert "list" not in detail
        assert "index" not in detail

    def test_error_has_user_friendly_message(self):
        """Errors should have user-friendly messages"""
        r = client.get("/entries/999")
        body = r.json()

        # Message should be concise and clear
        assert len(body["detail"]) < 200
        assert body["detail"] == "entry not found"


class TestErrorConsistency:
    """Test that all endpoints return consistent error format (ADR-002, NFR-001)"""

    def test_get_not_found_consistent(self):
        """GET not found should follow standard format"""
        r = client.get("/entries/999")
        assert r.status_code == 404
        body = r.json()
        assert "type" in body and "correlationId" in body

    def test_put_not_found_consistent(self):
        """PUT not found should follow standard format"""
        payload = {"title": "Test", "kind": "book", "status": "planned"}
        r = client.put("/entries/999", json=payload)
        assert r.status_code == 404
        body = r.json()
        assert "type" in body and "correlationId" in body

    def test_delete_not_found_consistent(self):
        """DELETE not found should follow standard format"""
        r = client.delete("/entries/999")
        assert r.status_code == 404
        body = r.json()
        assert "type" in body and "correlationId" in body

    def test_post_validation_error_consistent(self):
        """POST validation error should follow standard format"""
        payload = {"title": "", "kind": "book", "status": "planned"}
        r = client.post("/entries", json=payload)
        assert r.status_code == 422
        body = r.json()
        assert "type" in body and "correlationId" in body


class TestSuccessfulOperations:
    """Test that successful operations don't return error format"""

    def test_successful_post_no_error_format(self):
        """Successful POST should not use error format"""
        payload = {"title": "Test Book", "kind": "book", "status": "planned"}
        r = client.post("/entries", json=payload)
        assert r.status_code == 200

        body = r.json()
        # Should not have error fields
        assert "correlationId" not in body

        # Should have entry fields
        assert "id" in body
        assert "title" in body

    def test_successful_get_no_error_format(self):
        """Successful GET should not use error format"""
        # Create an entry first
        payload = {"title": "Test", "kind": "book", "status": "planned"}
        create_r = client.post("/entries", json=payload)
        entry_id = create_r.json()["id"]

        # Get the entry
        r = client.get(f"/entries/{entry_id}")
        assert r.status_code == 200

        body = r.json()
        assert "correlationId" not in body


class TestNFR001Compliance:
    """Test NFR-001: 100% errors return JSON error envelope"""

    def test_all_4xx_errors_have_envelope(self):
        """All 4xx errors should use error envelope"""
        # Test various 4xx scenarios
        test_cases = [
            (client.get("/entries/999"), 404),
            (client.post("/entries", json={"title": ""}), 422),
            (
                client.put(
                    "/entries/999",
                    json={"title": "x", "kind": "book", "status": "planned"},
                ),
                404,
            ),
        ]

        for response, expected_status in test_cases:
            assert response.status_code == expected_status
            body = response.json()
            assert "type" in body
            assert "title" in body
            assert "status" in body
            assert "detail" in body
            assert "correlationId" in body

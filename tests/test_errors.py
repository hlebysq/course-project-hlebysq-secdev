"""
ADR-002: RFC 7807 Error Handling Tests
Covers: NFR-001, Risk R4
"""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError


class TestRFC7807Format:
    """Test RFC 7807 Problem Details format (ADR-002)"""

    @pytest.mark.asyncio
    async def test_not_found_rfc7807_structure(self, client, mock_db):
        """Not found error should follow RFC 7807 format"""
        # Настраиваем мок для возврата None (запись не найдена)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        r = await client.get("/entries/999")
        assert r.status_code == 404

        body = r.json()

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

    @pytest.mark.asyncio
    async def test_validation_error_rfc7807_structure(self, client):
        """Validation error should follow RFC 7807 format"""
        payload = {"title": "", "kind": "book", "status": "planned"}
        r = await client.post("/entries", json=payload)
        assert r.status_code == 422

        body = r.json()

        assert "type" in body
        assert "title" in body
        assert "status" in body
        assert "detail" in body
        assert "instance" in body
        assert "correlationId" in body

        assert body["status"] == 422
        assert "validation-error" in body["type"]
        assert body["title"] == "Validation Error"

    @pytest.mark.asyncio
    async def test_correlation_id_is_uuid(self, client, mock_db):
        """Correlation ID should be a valid UUID format"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        r = await client.get("/entries/999")
        body = r.json()

        correlation_id = body["correlationId"]

        assert len(correlation_id) == 36
        assert correlation_id.count("-") == 4

    @pytest.mark.asyncio
    async def test_correlation_id_in_response_header(self, client, mock_db):
        """Correlation ID should also be in response headers"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        r = await client.get("/entries/999")

        assert "X-Correlation-ID" in r.headers
        header_id = r.headers["X-Correlation-ID"]

        body_id = r.json()["correlationId"]
        assert header_id == body_id

    @pytest.mark.asyncio
    async def test_correlation_id_unique_per_request(self, client, mock_db):
        """Each request should get a unique correlation ID"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        r1 = await client.get("/entries/999")
        r2 = await client.get("/entries/998")

        id1 = r1.json()["correlationId"]
        id2 = r2.json()["correlationId"]

        assert id1 != id2


class TestErrorTypes:
    """Test different error types mapping (ADR-002)"""

    @pytest.mark.asyncio
    async def test_not_found_error_type(self, client, mock_db):
        """Not found should have correct type URI"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        r = await client.get("/entries/999")
        body = r.json()

        assert body["type"] == "https://api.secdev.com/errors/not-found"
        assert body["title"] == "Resource Not Found"

    @pytest.mark.asyncio
    async def test_validation_error_type(self, client):
        """Validation error should have correct type URI"""
        payload = {"title": "", "kind": "book", "status": "planned"}
        r = await client.post("/entries", json=payload)
        body = r.json()

        assert body["type"] == "https://api.secdev.com/errors/validation-error"
        assert body["title"] == "Validation Error"


class TestErrorDetailMasking:
    """Test that error details don't leak sensitive info (ADR-002, Risk R4)"""

    @pytest.mark.asyncio
    async def test_validation_error_no_stack_trace(self, client):
        """Validation errors should not include stack traces"""
        payload = {"title": "", "kind": "book", "status": "planned"}
        r = await client.post("/entries", json=payload)
        body = r.json()

        body_str = str(body)
        assert "Traceback" not in body_str
        assert 'File "' not in body_str
        assert ".py" not in body_str or ".py" in body["type"]

    @pytest.mark.asyncio
    async def test_not_found_no_internal_details(self, client, mock_db):
        """Not found error should not leak internal implementation details"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        r = await client.get("/entries/999")
        body = r.json()

        detail = body["detail"].lower()

        assert "_db" not in detail
        assert "dict" not in detail
        assert "list" not in detail
        assert "index" not in detail

    @pytest.mark.asyncio
    async def test_error_has_user_friendly_message(self, client, mock_db):
        """Errors should have user-friendly messages"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        r = await client.get("/entries/999")
        body = r.json()

        assert len(body["detail"]) < 200
        assert body["detail"] == "entry not found"


class TestErrorConsistency:
    """Test that all endpoints return consistent error format (ADR-002, NFR-001)"""

    @pytest.mark.asyncio
    async def test_get_not_found_consistent(self, client, mock_db):
        """GET not found should follow standard format"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        r = await client.get("/entries/999")
        assert r.status_code == 404
        body = r.json()
        assert "type" in body and "correlationId" in body

    @pytest.mark.asyncio
    async def test_put_not_found_consistent(self, client, mock_db):
        """PUT not found should follow standard format"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        payload = {"title": "Test", "kind": "book", "status": "planned"}
        r = await client.put("/entries/999", json=payload)
        assert r.status_code == 404
        body = r.json()
        assert "type" in body and "correlationId" in body

    @pytest.mark.asyncio
    async def test_delete_not_found_consistent(self, client, mock_db):
        """DELETE not found should follow standard format"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        r = await client.delete("/entries/999")
        assert r.status_code == 404
        body = r.json()
        assert "type" in body and "correlationId" in body

    @pytest.mark.asyncio
    async def test_post_validation_error_consistent(self, client):
        """POST validation error should follow standard format"""
        payload = {"title": "", "kind": "book", "status": "planned"}
        r = await client.post("/entries", json=payload)
        assert r.status_code == 422
        body = r.json()
        assert "type" in body and "correlationId" in body


class TestDatabaseErrorHandling:
    """Test error handling for database failures"""

    @pytest.mark.asyncio
    async def test_database_connection_error(self, client, mock_db):
        """Test that database connection errors are properly handled"""
        mock_db.execute.side_effect = SQLAlchemyError("Connection failed")

        r = await client.get("/entries/1")
        assert r.status_code == 500
        body = r.json()
        assert "type" in body
        assert "correlationId" in body
        assert body["status"] == 500

    @pytest.mark.asyncio
    async def test_database_error_on_create(self, client, mock_db):
        """Test database error during entry creation"""
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 5
        mock_db.execute.return_value = mock_count_result

        mock_db.commit.side_effect = SQLAlchemyError("DB error")

        payload = {"title": "Test", "kind": "book", "status": "planned"}
        r = await client.post("/entries", json=payload)

        assert r.status_code == 500
        body = r.json()
        assert "type" in body
        assert "correlationId" in body
        assert "database error" in body["detail"].lower()

    @pytest.mark.asyncio
    async def test_update_calls_rollback_on_error(
        self, client, mock_db, create_mock_entry
    ):
        """Test that rollback is called when update fails"""
        mock_entry = create_mock_entry()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_entry
        mock_db.execute.return_value = mock_result

        mock_db.commit.side_effect = SQLAlchemyError("Update failed")

        payload = {"title": "Updated", "kind": "book", "status": "reading"}
        r = await client.put("/entries/1", json=payload)

        mock_db.rollback.assert_called_once()
        assert r.status_code == 500
        body = r.json()
        assert "type" in body
        assert "database error" in body["detail"].lower()

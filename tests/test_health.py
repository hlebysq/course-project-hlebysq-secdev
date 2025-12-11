from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError


class TestHealthEndpoint:
    """Test /health endpoint basic functionality"""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        """Health endpoint should return 200 OK"""
        r = await client.get("/health")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_health_returns_json(self, client):
        """Health endpoint should return JSON response"""
        r = await client.get("/health")
        assert r.headers["content-type"] == "application/json"
        body = r.json()
        assert isinstance(body, dict)

    @pytest.mark.asyncio
    async def test_health_has_status_and_database_fields(self, client):
        """Health response should have required fields"""
        r = await client.get("/health")
        body = r.json()

        assert "status" in body
        assert body["status"] == "ok"
        assert "database" in body
        assert body["database"] == "connected"


class TestHealthDatabaseCheck:
    """Test database connectivity check in health endpoint"""

    @pytest.mark.asyncio
    async def test_health_checks_database_connection(self, client, mock_db):
        """Health endpoint should execute database queries"""
        await client.get("/health")
        assert mock_db.execute.called

    @pytest.mark.asyncio
    async def test_health_with_entries_count(self, client, mock_db):
        """Health should return entries count when table exists"""
        mock_result1 = MagicMock()
        mock_result2 = MagicMock()
        mock_result2.scalar = MagicMock(return_value=42)

        mock_db.execute.side_effect = [mock_result1, mock_result2]

        r = await client.get("/health")
        body = r.json()

        assert body["status"] == "ok"
        assert body["database"] == "connected"
        assert "entries_count" in body
        assert body["entries_count"] == 42

    @pytest.mark.asyncio
    async def test_health_when_table_not_initialized(self, client, mock_db):
        """Health should handle case when entries table doesn't exist"""
        call_count = 0

        def execute_side_effect(arg):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                return MagicMock()
            else:
                raise Exception("relation 'entries' does not exist")

        mock_db.execute.side_effect = execute_side_effect

        r = await client.get("/health")
        body = r.json()

        assert r.status_code == 200
        assert body["status"] == "ok"
        assert body["database"] == "connected"
        assert body["table"] == "not_initialized"

    @pytest.mark.asyncio
    async def test_health_with_zero_entries(self, client, mock_db):
        """Health should correctly report zero entries"""
        mock_result1 = MagicMock()
        mock_result2 = MagicMock()
        mock_result2.scalar = MagicMock(return_value=0)

        mock_db.execute.side_effect = [mock_result1, mock_result2]

        r = await client.get("/health")
        body = r.json()

        assert body["entries_count"] == 0

    @pytest.mark.asyncio
    async def test_health_with_large_entries_count(self, client, mock_db):
        """Health should handle large number of entries"""
        mock_result1 = MagicMock()
        mock_result2 = MagicMock()
        mock_result2.scalar = MagicMock(return_value=999999)

        mock_db.execute.side_effect = [mock_result1, mock_result2]

        r = await client.get("/health")
        body = r.json()

        assert body["entries_count"] == 999999


class TestHealthDatabaseFailure:
    """Test health endpoint behavior when database fails"""

    @pytest.mark.asyncio
    async def test_health_database_connection_failure(self, client, mock_db):
        """Health should return 503 when database connection fails"""
        mock_db.execute.side_effect = SQLAlchemyError("Connection refused")

        r = await client.get("/health")
        assert r.status_code == 503

    @pytest.mark.asyncio
    async def test_health_database_failure_returns_rfc7807(self, client, mock_db):
        """Database failure should return RFC 7807 error format"""
        mock_db.execute.side_effect = SQLAlchemyError("Connection timeout")

        r = await client.get("/health")
        body = r.json()

        assert "type" in body
        assert "title" in body
        assert "status" in body
        assert "detail" in body
        assert "instance" in body
        assert "correlationId" in body

        assert body["status"] == 503

    @pytest.mark.asyncio
    async def test_health_database_failure_error_message(self, client, mock_db):
        """Database failure should include error message in detail"""
        mock_db.execute.side_effect = SQLAlchemyError("Could not connect to server")

        r = await client.get("/health")
        body = r.json()

        assert "Database connection failed" in body["detail"]
        assert "Could not connect to server" in body["detail"]

    @pytest.mark.asyncio
    async def test_health_database_failure_correlation_id(self, client, mock_db):
        """Database failure should include correlation ID"""
        mock_db.execute.side_effect = Exception("Network error")

        r = await client.get("/health")
        body = r.json()

        assert "correlationId" in body
        assert len(body["correlationId"]) == 36


class TestHealthResponseStructure:
    """Test health endpoint response structure"""

    @pytest.mark.asyncio
    async def test_healthy_response_structure(self, client, mock_db):
        """Test complete structure of healthy response"""
        mock_result1 = MagicMock()
        mock_result2 = MagicMock()
        mock_result2.scalar = MagicMock(return_value=10)

        mock_db.execute.side_effect = [mock_result1, mock_result2]

        r = await client.get("/health")
        body = r.json()

        required_fields = ["status", "database", "entries_count"]
        for field in required_fields:
            assert field in body

    @pytest.mark.asyncio
    async def test_healthy_response_no_error_fields(self, client, mock_db):
        """Healthy response should not contain error fields"""
        mock_result1 = MagicMock()
        mock_result2 = MagicMock()
        mock_result2.scalar = MagicMock(return_value=5)

        mock_db.execute.side_effect = [mock_result1, mock_result2]

        r = await client.get("/health")
        body = r.json()

        error_fields = ["type", "title", "detail", "correlationId"]
        for field in error_fields:
            assert field not in body

    @pytest.mark.asyncio
    async def test_unhealthy_response_structure(self, client, mock_db):
        """Test complete structure of unhealthy response"""
        mock_db.execute.side_effect = SQLAlchemyError("Connection failed")

        r = await client.get("/health")
        body = r.json()

        required_fields = [
            "type",
            "title",
            "status",
            "detail",
            "instance",
            "correlationId",
        ]
        for field in required_fields:
            assert field in body


class TestHealthEndpointIntegration:
    """Test health endpoint integration with middleware"""

    @pytest.mark.asyncio
    async def test_health_has_correlation_id_header_on_error(self, client, mock_db):
        """Health error response should have correlation ID in header"""
        mock_db.execute.side_effect = SQLAlchemyError("Connection failed")

        r = await client.get("/health")

        assert "X-Correlation-ID" in r.headers
        header_id = r.headers["X-Correlation-ID"]
        body_id = r.json()["correlationId"]

        assert header_id == body_id

    @pytest.mark.asyncio
    async def test_health_success_has_correlation_id_header(self, client, mock_db):
        """Health success response should also have correlation ID in header"""
        mock_result1 = MagicMock()
        mock_result2 = MagicMock()
        mock_result2.scalar = MagicMock(return_value=5)

        mock_db.execute.side_effect = [mock_result1, mock_result2]

        r = await client.get("/health")

        assert "X-Correlation-ID" in r.headers
        correlation_id = r.headers["X-Correlation-ID"]

        assert len(correlation_id) == 36
        assert correlation_id.count("-") == 4

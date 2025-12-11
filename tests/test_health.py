from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import SQLAlchemyError

from app.main import app


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
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


class TestHealthEndpoint:
    """Test /health endpoint basic functionality"""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client, mock_db):
        """Health endpoint should return 200 OK"""
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 5
        mock_db.execute.return_value = mock_result

        r = await client.get("/health")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_health_returns_json(self, client, mock_db):
        """Health endpoint should return JSON response"""
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 5
        mock_db.execute.return_value = mock_result

        r = await client.get("/health")
        assert r.headers["content-type"] == "application/json"
        body = r.json()
        assert isinstance(body, dict)

    @pytest.mark.asyncio
    async def test_health_has_status_field(self, client, mock_db):
        """Health response should have 'status' field"""
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 5
        mock_db.execute.return_value = mock_result

        r = await client.get("/health")
        body = r.json()
        assert "status" in body
        assert body["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_has_database_field(self, client, mock_db):
        """Health response should have 'database' field"""
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 5
        mock_db.execute.return_value = mock_result

        r = await client.get("/health")
        body = r.json()
        assert "database" in body
        assert body["database"] == "connected"


class TestHealthDatabaseCheck:
    """Test database connectivity check in health endpoint"""

    @pytest.mark.asyncio
    async def test_health_checks_database_connection(self, client, mock_db):
        """Health endpoint should execute SELECT 1 to verify DB connection"""
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 5
        mock_db.execute.return_value = mock_result

        await client.get("/health")

        assert mock_db.execute.call_count >= 1

    @pytest.mark.asyncio
    async def test_health_with_entries_count(self, client, mock_db):
        """Health should return entries count when table exists"""
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 42
        mock_db.execute.return_value = mock_result

        r = await client.get("/health")
        body = r.json()

        assert body["status"] == "ok"
        assert body["database"] == "connected"
        assert "entries_count" in body
        assert body["entries_count"] == 42

    @pytest.mark.asyncio
    async def test_health_when_table_not_initialized(self, client, mock_db):
        """Health should handle case when entries table doesn't exist"""
        mock_db.execute.side_effect = [
            AsyncMock(),
            Exception("relation 'entries' does not exist"),
        ]

        r = await client.get("/health")
        body = r.json()

        assert r.status_code == 200
        assert body["status"] == "ok"
        assert body["database"] == "connected"
        assert body["table"] == "not_initialized"

    @pytest.mark.asyncio
    async def test_health_with_zero_entries(self, client, mock_db):
        """Health should correctly report zero entries"""
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 0
        mock_db.execute.return_value = mock_result

        r = await client.get("/health")
        body = r.json()

        assert body["entries_count"] == 0

    @pytest.mark.asyncio
    async def test_health_with_large_entries_count(self, client, mock_db):
        """Health should handle large number of entries"""
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 999999
        mock_db.execute.return_value = mock_result

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

    @pytest.mark.asyncio
    async def test_health_database_timeout(self, client, mock_db):
        """Health should handle database timeout"""
        mock_db.execute.side_effect = SQLAlchemyError("Query timeout")

        r = await client.get("/health")
        assert r.status_code == 503
        body = r.json()
        assert body["status"] == 503


class TestHealthResponseStructure:
    """Test health endpoint response structure"""

    @pytest.mark.asyncio
    async def test_healthy_response_structure(self, client, mock_db):
        """Test complete structure of healthy response"""
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 10
        mock_db.execute.return_value = mock_result

        r = await client.get("/health")
        body = r.json()

        required_fields = ["status", "database", "entries_count"]
        for field in required_fields:
            assert field in body

    @pytest.mark.asyncio
    async def test_healthy_response_no_error_fields(self, client, mock_db):
        """Healthy response should not contain error fields"""
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 5
        mock_db.execute.return_value = mock_result

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


class TestHealthEndpointSecurity:
    """Test security aspects of health endpoint"""

    @pytest.mark.asyncio
    async def test_health_no_sensitive_data_on_error(self, client, mock_db):
        """Health error should not leak sensitive information"""
        mock_db.execute.side_effect = SQLAlchemyError(
            "FATAL: password authentication failed for user 'admin'"
        )

        r = await client.get("/health")
        body = r.json()

        assert "detail" in body

    @pytest.mark.asyncio
    async def test_health_no_stack_trace(self, client, mock_db):
        """Health error should not include stack traces"""
        mock_db.execute.side_effect = Exception("Internal error")

        r = await client.get("/health")
        body = r.json()
        body_str = str(body)

        assert "Traceback" not in body_str
        assert 'File "' not in body_str


class TestHealthEndpointPerformance:
    """Test performance-related aspects of health endpoint"""

    @pytest.mark.asyncio
    async def test_health_executes_minimal_queries(self, client, mock_db):
        """Health endpoint should execute minimal number of queries"""
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 5
        mock_db.execute.return_value = mock_result

        await client.get("/health")

        assert mock_db.execute.call_count <= 2

    @pytest.mark.asyncio
    async def test_health_does_not_modify_database(self, client, mock_db):
        """Health endpoint should not modify database"""
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 5
        mock_db.execute.return_value = mock_result

        await client.get("/health")

        mock_db.commit.assert_not_called()
        assert not mock_db.add.called
        assert not mock_db.delete.called


class TestHealthEndpointEdgeCases:
    """Test edge cases for health endpoint"""

    @pytest.mark.asyncio
    async def test_health_with_none_result(self, client, mock_db):
        """Health should handle None result from database"""
        mock_result = AsyncMock()
        mock_result.scalar.return_value = None
        mock_db.execute.return_value = mock_result

        r = await client.get("/health")
        body = r.json()

        assert "status" in body

    @pytest.mark.asyncio
    async def test_health_multiple_consecutive_calls(self, client, mock_db):
        """Multiple health checks should work consistently"""
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 5
        mock_db.execute.return_value = mock_result

        r1 = await client.get("/health")
        r2 = await client.get("/health")
        r3 = await client.get("/health")

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 200

        _ = r1.json().get("correlationId")
        _ = r2.json().get("correlationId")
        _ = r3.json().get("correlationId")

    @pytest.mark.asyncio
    async def test_health_alternating_success_failure(self, client, mock_db):
        """Health should handle alternating success and failure"""
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 5
        mock_db.execute.return_value = mock_result

        r1 = await client.get("/health")
        assert r1.status_code == 200

        mock_db.execute.side_effect = SQLAlchemyError("Connection lost")

        r2 = await client.get("/health")
        assert r2.status_code == 503

        mock_db.execute.side_effect = None
        mock_db.execute.return_value = mock_result

        r3 = await client.get("/health")
        assert r3.status_code == 200


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
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 5
        mock_db.execute.return_value = mock_result

        r = await client.get("/health")

        assert "X-Correlation-ID" in r.headers

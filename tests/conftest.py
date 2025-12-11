import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost:5432/test_db"
os.environ["APP_ENV"] = "test"
os.environ["LOG_LEVEL"] = "debug"
os.environ["SQL_DEBUG"] = "false"
os.environ["OUTGOING_TIMEOUT_CONNECT"] = "1.0"
os.environ["OUTGOING_TIMEOUT_READ"] = "1.0"
os.environ["OUTGOING_MAX_RETRIES"] = "1"
os.environ["OUTGOING_MAX_RESPONSE_BYTES"] = "1024"
os.environ["OUTGOING_MAX_CONN"] = "5"

from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def mock_db():
    """Создает мок базы данных с правильной настройкой."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    db.rollback = AsyncMock()
    db.add = MagicMock()

    # Создаем результат по умолчанию
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalar.return_value = 0  # Возвращает 0, а не мок!
    mock_result.scalars.return_value.all.return_value = []

    db.execute.return_value = mock_result
    return db


@pytest.fixture
def client(mock_db):
    """Синхронная фикстура для тестового клиента."""

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def client_no_db():
    """Синхронная фикстура для тестового клиента без БД."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
def cleanup_dependencies():
    """Автоматически очищает зависимости после каждого теста."""
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def create_mock_entry():
    """Фабрика для создания моков EntryDB."""

    def _create(entry_id=1, title="Test Book"):
        entry = MagicMock()
        entry.id = entry_id
        entry.title = title
        entry.kind = "book"
        entry.link = "https://example.com"
        entry.status = "planned"
        return entry

    return _create


@pytest.fixture
def mock_count_result():
    """Создает мок для COUNT запроса."""

    def _create(count=0):
        mock_result = MagicMock()
        mock_result.scalar.return_value = count  # Возвращает число!
        return mock_result

    return _create


@pytest.fixture
def mock_select_result():
    """Создает мок для SELECT запроса."""

    def _create(entry=None):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = entry
        mock_result.scalars.return_value.all.return_value = [entry] if entry else []
        return mock_result

    return _create


@pytest.fixture
def fake_response():
    class FakeResponse:
        def __init__(self, status_code=200, content=b"OK"):
            self.status_code = status_code
            self._content = content

        async def aread(self):
            return self._content

    return FakeResponse


@pytest.fixture
def fake_client():
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

    return FakeClient


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

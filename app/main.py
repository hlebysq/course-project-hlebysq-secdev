import asyncio
import os
import unicodedata
import uuid
from enum import Enum
from typing import List, Optional
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl, field_validator

app = FastAPI(title="SecDev Course App", version="0.2.1")

# ADR-002: RFC 7807 Error Type Registry
ERROR_TYPE_REGISTRY = {
    "validation_error": {
        "type": "https://api.secdev.com/errors/validation-error",
        "title": "Validation Error",
    },
    "not_found": {
        "type": "https://api.secdev.com/errors/not-found",
        "title": "Resource Not Found",
    },
    "forbidden": {
        "type": "https://api.secdev.com/errors/forbidden",
        "title": "Forbidden",
    },
    "http_error": {
        "type": "https://api.secdev.com/errors/http-error",
        "title": "HTTP Error",
    },
}


class ProblemDetail(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    instance: str
    correlationId: str
    errors: Optional[List[dict]] = None


class ApiError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code = code
        self.message = message
        self.status = status


# ADR-002: Middleware для correlation ID
@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    correlation_id = str(uuid.uuid4())
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


# ADR-002: Enhanced error handler с RFC 7807
@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    error_info = ERROR_TYPE_REGISTRY.get(exc.code, ERROR_TYPE_REGISTRY["http_error"])
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))

    problem = ProblemDetail(
        type=error_info["type"],
        title=error_info["title"],
        status=exc.status,
        detail=exc.message,
        instance=str(request.url.path),
        correlationId=correlation_id,
    )

    return JSONResponse(status_code=exc.status, content=problem.model_dump())


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else "http_error"
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))

    error_info = ERROR_TYPE_REGISTRY.get("http_error")
    problem = ProblemDetail(
        type=error_info["type"],
        title=error_info["title"],
        status=exc.status_code,
        detail=detail,
        instance=str(request.url.path),
        correlationId=correlation_id,
    )

    return JSONResponse(status_code=exc.status_code, content=problem.model_dump())


@app.get("/health")
def health():
    return {"status": "ok"}


_DB = {"entries": []}


class EntryKind(str, Enum):
    book = "book"
    article = "article"
    other = "other"


class EntryStatus(str, Enum):
    planned = "planned"
    reading = "reading"
    done = "done"


# ADR-001: Input sanitization utilities
def sanitize_string(value: str) -> str:
    """
    Sanitize string input:
    - Remove leading/trailing whitespace
    - Normalize Unicode to NFC
    - Remove null bytes and control characters
    """
    if not value:
        return value

    value = value.strip()
    value = unicodedata.normalize("NFC", value)
    value = value.replace("\x00", "")
    value = "".join(
        char
        for char in value
        if unicodedata.category(char)[0] != "C" or char in "\n\r\t"
    )

    return value


def validate_no_dangerous_chars(value: str) -> str:
    """
    Check for dangerous characters that could lead to XSS or injection
    """
    dangerous_patterns = [
        r"<script",
        r"javascript:",
        r"onerror=",
        r"onload=",
        r"<iframe",
        r"<embed",
        r"<object",
    ]

    value_lower = value.lower()
    for pattern in dangerous_patterns:
        if pattern in value_lower:
            raise ApiError(
                "validation_error", f"Dangerous pattern detected: {pattern}", 422
            )

    return value


def validate_url_safety(url: Optional[str]) -> Optional[str]:
    """
    ADR-001: Validate URL for SSRF protection
    - Only http/https allowed
    - Block private IP ranges
    - Block localhost
    - Max length 2048
    """
    if not url:
        return url

    if len(url) > 2048:
        raise ApiError("validation_error", "URL too long (max 2048 chars)", 422)

    try:
        parsed = urlparse(str(url))

        # Check protocol
        if parsed.scheme not in ["http", "https"]:
            raise ApiError("validation_error", "Only http/https protocols allowed", 422)

        # Check for localhost
        hostname = parsed.hostname or ""
        if hostname.lower() in ["localhost", "127.0.0.1", "0.0.0.0", "::1"]:
            raise ApiError("validation_error", "Localhost URLs not allowed", 422)

        # Check for private IP ranges (basic check)
        if (
            hostname.startswith("10.")
            or hostname.startswith("192.168.")
            or hostname.startswith("172.")
        ):
            raise ApiError("validation_error", "Private IP addresses not allowed", 422)

        # Check for path traversal
        if ".." in parsed.path or "~" in parsed.path:
            raise ApiError(
                "validation_error", "Path traversal patterns not allowed", 422
            )

    except ApiError:
        raise
    except Exception as e:
        raise ApiError("validation_error", f"Invalid URL format: {str(e)}", 422)

    return url


class EntryCreate(BaseModel):
    title: str
    kind: EntryKind
    link: Optional[HttpUrl] = None
    status: EntryStatus

    @field_validator("title")
    def validate_title(cls, v):
        # ADR-001: Sanitize input
        v = sanitize_string(v)

        if not (1 <= len(v) <= 200):
            raise ApiError("validation_error", "title must be 1..200 chars", 422)

        # ADR-001: Check for dangerous characters
        v = validate_no_dangerous_chars(v)

        return v

    @field_validator("link")
    def validate_link(cls, v):
        # ADR-001: Additional URL validation
        if v:
            validate_url_safety(str(v))
        return v


class Entry(EntryCreate):
    id: int


@app.post("/entries", response_model=Entry)
def create_entry(data: EntryCreate):
    """
    Create a new entry
    ADR-001: All inputs are sanitized and validated
    """

    if len(_DB["entries"]) >= 1000:
        raise ApiError("forbidden", "Maximum entries limit reached (1000)", 403)

    entry = Entry(id=len(_DB["entries"]) + 1, **data.model_dump())
    _DB["entries"].append(entry.model_dump())
    return entry


@app.get("/entries", response_model=List[Entry])
def list_entries(status: Optional[EntryStatus] = None):
    """
    List all entries with optional status filter
    """
    entries = _DB["entries"]
    if status:
        entries = [e for e in entries if e["status"] == status]
    return entries


@app.get("/entries/{entry_id}", response_model=Entry)
def get_entry(entry_id: int):
    """
    Get a single entry by ID
    ADR-002: Returns RFC 7807 error on not found
    """
    for e in _DB["entries"]:
        if e["id"] == entry_id:
            return e
    raise ApiError("not_found", "entry not found", 404)


@app.put("/entries/{entry_id}", response_model=Entry)
def update_entry(entry_id: int, data: EntryCreate):
    """
    Update an existing entry
    ADR-001: All inputs are sanitized and validated
    """
    for i, e in enumerate(_DB["entries"]):
        if e["id"] == entry_id:
            updated = Entry(id=entry_id, **data.model_dump())
            _DB["entries"][i] = updated.model_dump()
            return updated
    raise ApiError("not_found", "entry not found", 404)


@app.delete("/entries/{entry_id}")
def delete_entry(entry_id: int):
    """
    Delete an entry by ID
    """
    for i, e in enumerate(_DB["entries"]):
        if e["id"] == entry_id:
            del _DB["entries"][i]
            return {"status": "deleted"}
    raise ApiError("not_found", "entry not found", 404)


# ADR-003: Client policies configuration (defaults, can be overridden by env)
OUTGOING_CONNECT_TIMEOUT = float(os.getenv("OUTGOING_TIMEOUT_CONNECT", "5.0"))
OUTGOING_READ_TIMEOUT = float(os.getenv("OUTGOING_TIMEOUT_READ", "5.0"))
OUTGOING_MAX_RETRIES = int(os.getenv("OUTGOING_MAX_RETRIES", "2"))
OUTGOING_MAX_RESPONSE_BYTES = int(
    os.getenv("OUTGOING_MAX_RESPONSE_BYTES", str(1024 * 1024))
)  # 1MB
OUTGOING_MAX_CONN = int(os.getenv("OUTGOING_MAX_CONN", "10"))


async def get_http_client() -> httpx.AsyncClient:
    """Return a shared AsyncClient configured with limits/timeouts."""
    if getattr(app.state, "http_client", None) is None:
        limits = httpx.Limits(
            max_connections=OUTGOING_MAX_CONN, max_keepalive_connections=5
        )
        timeout = httpx.Timeout(
            connect=OUTGOING_CONNECT_TIMEOUT, read=OUTGOING_READ_TIMEOUT
        )
        app.state.http_client = httpx.AsyncClient(
            timeout=timeout, limits=limits, follow_redirects=True
        )
    return app.state.http_client


@app.post("/fetch")
async def fetch_url(request: Request):
    """
    Fetch a remote URL with client policies (SSRF checks, timeout, retries, max response size)
    Body: {"url": "https://example.com"}
    """
    body = await request.json()
    url = body.get("url")

    # Reuse SSRF / URL safety checks
    validate_url_safety(url)

    client = await get_http_client()

    last_exc = None
    for attempt in range(1, OUTGOING_MAX_RETRIES + 2):
        try:
            resp = await client.get(url)
            content = await resp.aread()
            if len(content) > OUTGOING_MAX_RESPONSE_BYTES:
                raise ApiError("validation_error", "Fetched content too large", 422)

            snippet = content[:200].decode("utf-8", errors="replace")
            return {"status": resp.status_code, "content_snippet": snippet}

        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError) as e:
            last_exc = e
            await asyncio.sleep(0)
            continue
        except ApiError:
            raise
        except Exception as e:
            raise ApiError("http_error", f"Upstream fetch failed: {str(e)}", 502)

    raise ApiError(
        "http_error", f"Upstream fetch failed after retries: {str(last_exc)}", 502
    )

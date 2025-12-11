# ===== Build stage =====
FROM python:3.11.9-slim@sha256:7cd0079a9bd8800c81632d65251048fc2848bf9afda542224b1b10e0cae45575 AS build
WORKDIR /app

COPY requirements.txt ./

RUN pip wheel --no-cache-dir -r requirements.txt -w /wheels

# ===== Test stage =====
FROM python:3.11.9-slim@sha256:7cd0079a9bd8800c81632d65251048fc2848bf9afda542224b1b10e0cae45575 AS test
WORKDIR /app
COPY . .
COPY requirements-dev.txt ./

RUN pip install --no-cache-dir -r requirements-dev.txt
RUN pytest -q

# ===== Runtime stage =====
FROM python:3.11.9-slim@sha256:7cd0079a9bd8800c81632d65251048fc2848bf9afda542224b1b10e0cae45575 AS runtime
WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN groupadd -r appuser -g 1001 && \
    useradd -r -u 1001 -g appuser appuser

COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt

COPY --from=test /app /app

RUN chown -R appuser:appuser /app

USER appuser

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD curl -fs http://localhost:8000/health || exit 1

EXPOSE 8000
ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

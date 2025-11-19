# ADR-002 — Error Handling: RFC 7807 Problem Details

**Status:** Accepted
**Date:** 2025-10-31
**Owner:** @owner

## Context

Ранее сервис возвращал упрощённый формат ошибок `{ "error": { "code": ..., "message": ... } }`. Это затрудняет автоматизированную обработку ошибок клиентами, не даёт type URI для машинно-читаемой идентификации и не обеспечивает корреляции между логами и ответами (correlation ID). Кроме того, в продакшене необходимо маскировать подробные детали стектрейсов.

## Decision

Принять формат RFC 7807 (Problem Details for HTTP APIs) как стандарт для всех ошибок API. Компоненты решения:

1. **Problem Detail model** — поля: `type`, `title`, `status`, `detail`, `instance`, `correlationId`, `errors` (опционально).
2. **Error Type Registry** — словарь, маппящий внутренние коды на type-URI + title, например:
   - `validation_error` → `https://api.secdev.com/errors/validation-error`
   - `not_found` → `https://api.secdev.com/errors/not-found`
   - `forbidden` → `https://api.secdev.com/errors/forbidden`
   - `http_error` → `https://api.secdev.com/errors/http-error`
3. **Correlation ID middleware** — уникальный UUID генерируется для каждого запроса и добавляется в ответ-хедер `X-Correlation-ID` и в тело ошибки `correlationId`.
4. **Environment-sensitive masking** — в development: полные детали и стектрейсы; в production: минимальные сообщения и отсутствие стектрейсов в теле ответа.
5. **Structured logging** — все ошибки логируются с `correlationId` для упрощения расследования.

## Consequences

**Положительные:**
- Соответствие NFR-001 (единый формат ошибок).
- Улучшенная трассируемость через correlationId.
- Машиночитаемость и совместимость с мониторингом (Sentry/ELK).

**Отрицательные:**
- Увеличение размера ответа об ошибке (~100–200 bytes).
- Необходимость поддерживать registry type URIs.

**Operational:**
- В runbook указать, как использовать `correlationId` при поиске логов/трассировок.

## Links (Traceability)

- **NFRs:** NFR-001 (Error envelope).
- **Threat Model:** влияет на Risk R4 (Information Disclosure).
- **Functional:** все endpoints (где возвращаются ошибки).
- **Tests / Artifacts:** `tests/test_errors.py` (проверяет формат RFC 7807 и присутствие correlationId).
- **Acceptance / Closure Criteria:** Unit tests, проверяющие структуру problem details, и маскирование стектрейсов в production mode.

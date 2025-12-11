# SecDev Course

Репозиторий с основным проектом по Разработке Безопасного Программного Обеспечения.

## Быстрый старт
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
pre-commit install
uvicorn app.main:app --reload
```

## Ритуал перед PR
```bash
ruff --fix .
black .
isort .
pytest -q
pre-commit run --all-files
```

## Тесты
```bash
pytest -q
```

## CI
В репозитории настроен workflow **CI** (GitHub Actions) — required check для `main`.
Badge добавится автоматически после загрузки шаблона в GitHub.

## Контейнеры
```bash
docker-compose build
docker-compose --profile dev up -d
docker-compose exec app alembic upgrade head
```

## Эндпойнты

### `GET /health`

Проверка состояния сервиса и БД.

**Пример ответа:**

``` json
{
  "status": "ok",
  "database": "connected",
  "entries_count": 42
}
```

------------------------------------------------------------------------

### `POST /entries`

Создаёт новую запись.

**Поля запроса:** - `title` --- строка (1--200 символов),
автоматически: - триммируется, - нормализуется, - очищается от опасных
символов, - проверяется на XSS-паттерны. - `kind` --- одно из: -
`"book"` - `"article"` - `"other"` - `link` --- `http(s)` URL, проходит
строгую SSRF-валидацию (запрещены localhost, приватные сети, `file://`,
path traversal). - `status` --- `"planned" | "reading" | "done"`

**Пример успешного ответа:**

``` json
{
  "id": 1,
  "title": "Example",
  "kind": "book",
  "link": "https://example.com",
  "status": "planned"
}
```

------------------------------------------------------------------------

### `GET /entries`

Список всех записей.

**Параметры:** - `status` --- необязательный фильтр
(`planned|reading|done`)

**Пример ответа:**

``` json
[
  {
    "id": 1,
    "title": "Example",
    "kind": "book",
    "link": "https://example.com",
    "status": "reading"
  }
]
```

------------------------------------------------------------------------

### `GET /entries/{id}`

Возвращает запись по ID.

**Пример ответа:**

``` json
{
  "id": 1,
  "title": "Example",
  "kind": "article",
  "link": "https://example.com",
  "status": "done"
}
```

------------------------------------------------------------------------

### `PUT /entries/{id}`

Полностью обновляет запись (все поля как в `POST /entries`).

------------------------------------------------------------------------

### `DELETE /entries/{id}`

Удаляет запись.

**Пример ответа:**

``` json
{"status": "deleted"}
```

------------------------------------------------------------------------

### `POST /fetch`

Безопасный HTTP-клиент (SSRF-защита, лимиты, retries).

**Тело:**

``` json
{"url": "https://example.com"}
```

**Пример ответа:**

``` json
{
  "status": 200,
  "content_snippet": "<!doctype html>..."
}
```

------------------------------------------------------------------------

## Формат ошибок (RFC 7807)

Все ошибки возвращаются в формате RFC 7807 + correlation ID:

``` json
{
  "type": "https://api.secdev.com/errors/not-found",
  "title": "Resource Not Found",
  "status": 404,
  "detail": "entry not found",
  "instance": "/entries/999",
  "correlationId": "7f8b1c75-9a33-4a32-a7d9-1b9d8d4af001"
}
```


См. также: `SECURITY.md`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`.

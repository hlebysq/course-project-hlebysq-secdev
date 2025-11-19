# Non-Functional Requirements

| ID | Название | Метрика / Порог | Способ проверки | Компонент | Приоритет |
|----|----------|----------------|----------------|-----------|-----------|
| NFR-001 | Единый формат ошибок | 100% ошибок → JSON `{error:{code,message}}` | Unit tests | Exception Handlers | High |
| NFR-002 | Валидация данных | 100% нарушений → 422 `validation_error` | Unit tests | Request Models | High |
| NFR-003 | Производительность API | 95% запросов < 200ms | Load tests | CRUD Endpoints | Medium |
| NFR-004 | Тестовое покрытие | ≥ 80% строк бизнес-логики | `pytest -q` | Services | Medium |
| NFR-005 | Защита от SQL-инъекций | 0 успешных инъекций | Code review | DB Layer | High |
| NFR-006 | Авторизация владельца | Нет доступа к чужим записям | Auth tests | Auth | Medium |
| NFR-007 | Pre-commit проверка качества кода | 100% коммитов проходят pre-commit | `pre-commit run --all-files` | Dev tooling | High |
| NFR-008 | Документация API | Swagger/Redoc доступны и актуальны | manual check | FastAPI docs | Medium |

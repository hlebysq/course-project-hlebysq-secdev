# STRIDE Threat Assessment

| Поток/Элемент | Угроза (STRIDE) | Риск | Контроль | Ссылка на NFR | Проверка/Артефакт |
|---------------|----------------|------|----------|---------------|------------------|
| F1 GET /entries | S: Spoofing — нет проверки пользователя | R1 | Ограничение доступа к изменению данных | NFR-006 | AuthZ tests |
| F1 GET /entries | R: Repudiation — нет лога действий | R2 | Логирование запросов | NFR-005 | Лог проверка в CI |
| F2 POST /entries | T: Tampering — вредоносные данные | R3 | Pydantic валидация входных данных | NFR-002 | Negative tests |
| F2 POST /entries | I: Information Disclosure — подробные ошибки | R4 | Error Envelope Normalization | NFR-001 | API error contract tests |
| DB Storage | T: Tampering — SQL Injection | R5 | ORM + параметризованные запросы | NFR-005 | ZAP baseline |
| F3 PUT /entries/{id} | E: Elevation of Privilege — изменение чужих данных | R6 | Проверка владельца записи | NFR-006 | AuthZ integration tests |
| Сервис | D: DoS — отсутствие лимитов производительности | R7 | Performance SLA | NFR-003 | Load tests |
| Репозиторий | I: Code Disclosure / Quality Gaps | R8 | Pre-commit hooks, линтеры | NFR-007 | Pre-commit CI gate |
| Документация | I: Information Disclosure | R9 | Синхронизация схемы API и Swagger | NFR-008 | Schema diff check |

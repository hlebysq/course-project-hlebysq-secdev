# Acceptance Scenarios (BDD)

## NFR-001 — Error envelope
Scenario: Not found returns proper error JSON
  When GET "/entries/999"
  Then status = 404
  And response.error.code = "not_found"

## NFR-002 — Validation
Scenario: Invalid title rejected
  When POST "/entries" with title=""
  Then status = 422

## NFR-003 — Performance
Scenario: API responds fast
  When load = 50 RPS
  Then 95% requests respond under 200ms

## NFR-004 — Coverage
Scenario: Minimum coverage met
  When running pytest with coverage
  Then coverage >= 80%

## NFR-007 — Pre-commit quality gate
Scenario: Commit with style issues is blocked
  Given code has formatting issues
  When developer tries to commit
  Then commit is rejected by pre-commit hook

## NFR-008 — API docs
Scenario: Documentation is available
  When GET "/docs"
  Then status = 200

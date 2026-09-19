# Q360 Sprints 09/10/11 — Fila de Implementação

## Task 1: Backend — Modelos ORM Outbox/Idempotency/Inbox (managed=False) + Audit Serializer/View/URL + Audit list endpoint
- **Status**: `pending`
- **Priority**: high
- **Depends On**: None
- **Description**:
  - Adicionar a `apps/foundation/infrastructure/models.py` os modelos `OutboxEvent`, `IdempotencyRecord`, `ConsumerInbox` com `managed=False`, campos exactos de ART-012 V025, `db_table` não qualificados (`outbox_event`, `idempotency_record`, `consumer_inbox`) — usando `TenantScopedModel` ou equivalente.
  - Criar `AuditEventSerializer` exactamente por ART-006 schema `AuditEvent` (camelCase via serializer field_names: `id`, `actorId`, `action`, `entityType`, `entityId`, `occurredAt`, `correlationId`, `metadata`).
  - Criar `AuditEventListView` em `apps/foundation/interfaces/views.py` (ou `audit_views.py`) com `IsAuthenticated + require_scope(Scope.AUDIT)`, `Q360PageNumberPagination`, filtros query `entityType`, `entityId`, `correlationId`. A query filtrar sempre por tenant actual.
  - Adicionar URL `audit-events` ao `apps/foundation/interfaces/urls.py`.
- **Acceptance Criteria Addressed**: AC-1, AC-10
- **Test Requirements**:
  - `rule` TR-1.1: Chamada GET sem scope audit responde 403. GET com scope responde 200 e schema de campos exactos. Filtro `entityType=QUOTE` devolve só auditoria dessa entidade. Evidence: `tests/foundation/test_audit_list_endpoint.py` verde.
  - `rule` TR-1.2: Modelos OutboxEvent/IdempotencyRecord/ConsumerInbox criam objectos em memória e cada `.save()` (via fixture de Testcontainers) persiste sem erro de schema mismatch com as migrations V025. Evidence: `tests/foundation/test_outbox_models.py` verde.
- **Notes**: Sem migrations novas; todos os modelos devem usar `managed=False`.

## Task 2: Backend — AuditService calls integrados em todos os módulos S02–S08
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 1
- **Description**:
  - Percorrer cada serviço de aplicação (`product/product_service.py`, `product/use_cases.py`, `client/proposer_service.py`, `client/member_service.py`, `client/import_service.py`, `eligibility/use_cases.py`, `pricing/pricing_engine.py`, `quote/quote_service.py`, `quote/document_service.py`, `foundation/rule_service.py`) e injectar `AuditService` via DI no `__init__` (ou usar padrão já existente de instantiation no app).
  - Em cada operação crítica: `AuditService.record(action="…", entity_type="…", entity_id="…", metadata={"result": "SUCCESS", …})`. Para operações que podem falhar com excepção esperada (ex: pricing config error), rode dentro de um bloco try/except que também grave `FAILURE` com `reason`/`failure_code`.
  - Alargar `_FORBIDDEN_METADATA_KEYS` como em NFR-2.
  - Usar `get_correlation_id()` de middleware e passar para `correlation_id`.
- **Acceptance Criteria Addressed**: AC-2, AC-10
- **Test Requirements**:
  - `rule` TR-2.1: `tests/product/test_products.py::test_audit_product_create_publish` — após create product + publish version, existem exactamente 2 audit_events com `result=SUCCESS`.
  - `rule` TR-2.2: `tests/pricing/test_pricing_engine.py::test_audit_pricing_failure` — pricing com config ausente grava audit com `result=FAILURE, failure_code=PRICING-CONFIG`.
  - `rule` TR-2.3: `tests/quote/test_review_workflow.py::test_audit_approve_records_decision` — quote aprovado grava audit com `decision_id, reason_code` em metadata quando aplicável.
  - `rubric` TR-2.4: Cobertura de ações auditadas por módulo. Scale: 0–100%. Threshold: >= 90% das operações listadas em FR-2. Evidence: contagem por grep de `AuditService.record` vs lista de operações.

## Task 3: Backend — Middleware de Idempotência + IdempotencyRecordService
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 1
- **Description**:
  - Criar `apps/foundation/application/idempotency_service.py` com `IdempotencyService` que implementa:
    - `begin(key, operation_code, request_hash, tenant_id) → tuple[started, record_or_none]` — tenta criar `IN_PROGRESS` com `expires_at = now + 24h`. Se já existir (mesma key+tenant+operation): (a) `COMPLETED` e mesmo request_hash: devolve o mesmo body; (b) hash diferente: levanta `IdempotencyReplayError` (mapeado para 409 `IDEMP-REPLAY` via exception_handler); (c) `IN_PROGRESS` (em curso por outro worker): esperar polling curto ou devolver 409 temporário.
    - `complete(record_id, response_status, response_body_json, resource_id=None)` — marca `COMPLETED + completed_at`.
    - `fail(record_id, response_status=None, response_body_json=None)` — marca `FAILED`.
  - Criar middleware `IdempotencyMiddleware` em `apps/foundation/interfaces/middleware.py`. Determina `operation_code` a partir da view dispatch. Calcula `request_hash` (SHA-256 de `method + path_info + raw_body.decode utf-8 + str(tenant_id)`).
  - A middleware só activa para views que ART-006 declara `IdempotencyKey` required — identificamo-los via um decorator `@requires_idempotency` aplicado em cada view mutante correspondente (ou via whitelist de `request.resolver_match.view_name`).
  - Mapear excepção `IdempotencyReplayError` → ProblemDetail `code=IDEMP-REPLAY` em `exception_handler.py`.
  - Falta de cabeçalho `Idempotency-Key` quando obrigatório → 400 `VALIDATION-400` concreto.
- **Acceptance Criteria Addressed**: AC-3
- **Test Requirements**:
  - `rule` TR-3.1: `tests/foundation/test_idempotency.py::test_same_key_same_body_is_replayed` — replay devolve mesmo status/body, sem duplicar Quote.
  - `rule` TR-3.2: `test_same_key_different_body_returns_409_idemp_replay`.
  - `rule` TR-3.3: `test_missing_idempotency_key_on_required_endpoint_returns_400`.
  - `rule` TR-3.4: O record em `idempotency_record` é criado/actualizado com campos correctos.

## Task 4: Backend — OutboxService (Transactional Append) + Dispatcher command + Publisher adapter (Noop/Rabbit ready hook)
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 1
- **Description**:
  - `apps/foundation/application/ports.py` + `apps/foundation/application/outbox_service.py`: `OutboxService` com `append(*, aggregate_type, aggregate_id, event_type, payload: dict, schema_version=1, correlation_id=None, causation_id=None)` que cria `OutboxEvent.status=PENDING` — deve ser sempre chamado dentro de `transaction.atomic()`; documentar isso. `payload` é o payload interno ART-007; o envelope completo {eventId, eventType, schemaVersion, occurredAt, tenantId, aggregateType, aggregateId, correlationId, causationId, producer, payload} é guardado em `payload_json`.
  - Publisher Port: `class EventPublisher(Protocol)` com método `publish(envelope: dict) -> None`. Implementação default `ValidatingNoopPublisher`: valida envelope obrigatório, faz json roundtrip, verifica que nenhum campo proibido existe. Falha → levanta `PublishError`.
  - `apps/foundation/management/commands/dispatch_outbox.py`: argumentos `--once` (uma passagem) e `--interval SECONDS` (loop com sleep). Por passagem: `transaction.atomic()`, SELECT OutboxEvent `WHERE status in (PENDING, FAILED) AND (next_attempt_at IS NULL OR next_attempt_at <= now()) ORDER BY occurred_at LIMIT 50 FOR UPDATE SKIP LOCKED`. Para cada: `PROCESSING` → chama `publisher.publish(envelope_from_payload_json)` → sucesso: `PUBLISHED + published_at`. Falha: `attempts++`, guarda `last_error_safe` (truncado, sem PII), calcula `next_attempt_at` por backoff 10s/30s/2m/10m/30m. Se attempts >= 5 → FAILED.
- **Acceptance Criteria Addressed**: AC-4, AC-10
- **Test Requirements**:
  - `rule` TR-4.1: `tests/foundation/test_outbox.py::test_rollback_also_rolls_outbox` — `atomic()` rollback, sem row persistida.
  - `rule` TR-4.2: `test_dispatch_marks_published` — dispatcher passa validating publisher → evento PUBLISHED.
  - `rule` TR-4.3: `test_dispatch_backoff_and_fail` — ValidatingNoopPublisher que sempre levanta; após 5 runs → FAILED e attempts=5, last_error_safe presente e não contém conteúdo de payload bruto.

## Task 5: Backend — Cablagem OutboxService para todos os eventos do ART-007 com operações implementadas
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 4
- **Description**:
  - Em cada serviço/use_case já existente, chamar `OutboxService.append` dentro da mesma transacção, com os campos mínimos do payload do ART-007. Cobrir explicitamente:
    - Product: PRODUCT.VERSION.PUBLISHED, PLAN.CREATED, PLAN.UPDATED.
    - Client: PROPOSER.CREATED, PROPOSER.UPDATED, MEMBER.CREATED, MEMBER.UPDATED, MEMBER.IMPORT.COMPLETED.
    - Eligibility: ELIGIBILITY.EVALUATED.
    - Pricing: PRICING.CALCULATED, PRICING.FAILED, PRICING.SCENARIO.CREATED (se existir).
    - Quote: QUOTE.CREATED, QUOTE.POPULATION.UPDATED, QUOTE.PRICE.CALCULATED, QUOTE.SUBMITTED, QUOTE.APPROVED, QUOTE.REJECTED, QUOTE.RETURNED, QUOTE.CANCELLED, QUOTE.EXPIRED (no cmd expire_quotes).
    - Documents: DOCUMENT.GENERATION.REQUESTED, DOCUMENT.GENERATED, DOCUMENT.GENERATION.FAILED.
  - `causation_id` pode None; `correlation_id` do request context.
- **Acceptance Criteria Addressed**: AC-5
- **Test Requirements**:
  - `rule` TR-5.1: `tests/integration/test_outbox_event_catalog.py` com 14 mini-testes (`with pytest.subTest`) cada um executa a operação, faz flush e asserter `event_type` exacto + campos mínimos payload do ART-007 não nulos.

## Task 6: Backend — Testes de Tenant Isolation e Migrations + Golden
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Tasks 1, 2, 3, 4, 5 (parte isolamento); Task 1 + todos os outros (para migrations+golden)
- **Description**:
  - `tests/foundation/test_tenant_isolation.py`: criar 2 tenants e 2 actors correspondentes via fixtures. Criar Quote/Product/Membro em A. Tentar cada operação de leitura/alteração sobre o mesmo UUID a partir de B → 404 NOT-FOUND. Verificar que listagens (audit, products, quotes) filtradas pela página 0 não contêm entidades de tenant B.
  - `tests/integration/test_migrations_and_golden.py`: usar Testcontainers ou base `Q360_TEST_POSTGRES`. Correr `migrate` desde zero. Depois carregar cada GT-*.json. Operacionalizar os GTs: se GT descrever inputs e outputs esperados, executar o caso via REST API client e asserter campos determinísticos (não asserter UUIDs e timestamps generated). Ignorar template `PENDING_OD_*`.
- **Acceptance Criteria Addressed**: AC-8, AC-9
- **Test Requirements**:
  - `rule` TR-6.1: Todos os casos de tenant isolation passam com 404/NOT-FOUND, nunca 200 com cross-tenant data.
  - `rule` TR-6.2: Migrations do zero correm sem erro; golden tests que não PENDING_OD passam todos os asserts determinísticos.

## Task 7: Frontend — AuditPage migrada para API real + paginação + filtros ART-006
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 1 (backend endpoint functional)
- **Description**:
  - Criar `src/domains/audit/services/auditApi.ts` que usa `httpClient.request` para `GET /api/v1/audit-events` com query params `page, size, entityType, entityId, correlationId` e retorna `AuditEventPage`.
  - Actualizar `src/domains/audit/types/index.ts` para alinhar com schema ART-006 `AuditEvent`: `id, actorId, action, entityType, entityId, occurredAt, correlationId, metadata`. Manter compatibilidade de apresentação: derivar um `actorName` a partir de actorId (pode ser só o id, ou o backend retorna metadata com nome se existir). O antigo `type` é calculado no frontend a partir de `action` (ex: `quote.created` → `quote_created`).
  - Actualizar `AuditPage.tsx`: usar `useQuery` ou `useEffect` para ir buscar dados reais com paginação (botões anterior/próximo, página actual e total).
  - Manter filtros de pesquisa client-side só para `summary` derivado; mapear os filtros ART-006 (`entityType`, `entityId`, `correlationId`) directamente para query params enviados ao servidor.
  - Remover importação directa de `Mockdata` de produção; manter só para ambiente dev se quiser, mas nunca no build de teste/prod.
  - Actualizar `filterAuditEvents` para operar sobre os tipos reais ou decompor em server-filter + client-filter.
- **Acceptance Criteria Addressed**: AC-6, AC-10
- **Test Requirements**:
  - `rule` TR-7.1: `src/tests/audit.test.ts` actualizado: mock de httpClient que responde AuditEventPage valida que a página é renderizada com os items e paginação accionada.
  - `rule` TR-7.2: Aplicar filtro `entityType=QUOTE` no UI → request URL contém `entityType=QUOTE`.

## Task 8: Frontend — httpClient Idempotency-Key automático + tratamento IDEMP-REPLAY
- **Status**: `pending`
- **Priority**: high
- **Depends On**: None
- **Description**:
  - Criar `src/api/idempotency.ts` (ou dentro do próprio `httpClient.ts`): gerar `crypto.randomUUID()` como `Idempotency-Key` para todo o pedido mutante (POST/PUT/PATCH/DELETE). Se o mesmo (method, url, bodyHash) falhar por erro de rede e houver retry do utilizador, opcionalmente reutilizar o mesmo key por um TTL de 60s.
  - Enviar cabeçalho `Idempotency-Key` em mutações.
  - `problemDetail.ts` já lida com `ProblemDetail`. Garantir que `code === "IDEMP-REPLAY"` é exibido com mensagem clara (não crash).
  - Não enviar o header em requests de leitura GET/HEAD/OPTIONS.
- **Acceptance Criteria Addressed**: AC-7
- **Test Requirements**:
  - `rule` TR-8.1: `src/tests/httpClient.test.ts` — novo caso: `POST` tem cabeçalho `Idempotency-Key` com UUID válido; `GET` não tem.
  - `rule` TR-8.2: Resposta 409 com `code=IDEMP-REPLAY` é parseada e lança erro com código correcto.

## Task 9: Finalização — Testes de regressão completos + Diagnostics/Typecheck
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Tasks 1–8
- **Description**:
  - Correr todos os testes backend (`pytest backend/tests`) — todos verdes.
  - Correr todos os testes frontend (`npm run test`) — todos verdes.
  - Correr `GetDiagnostics` no backend e frontend para type errors / lint.
- **Acceptance Criteria Addressed**: todos os AC via TRs
- **Test Requirements**:
  - `rule` TR-9.1: pytest passa sem falhas.
  - `rule` TR-9.2: npm test passa sem falhas.
  - `rule` TR-9.3: `GetDiagnostics` sem error level crítico.

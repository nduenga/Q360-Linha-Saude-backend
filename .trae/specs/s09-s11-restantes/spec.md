# Q360 — Conclusão Sprints 09/10/11: Auditoria, Idempotência, Outbox, Integração Frontend Audit, Isolamento e Hardening

## Overview
- **Summary**: Construir a parte acionável por código do que falta dos Sprints 09, 10 e 11 do DOC-002 no backend e frontend já existentes, respeitando integralmente os contratos ART-005 (DDL), ART-006 (OpenAPI), ART-007 (RabbitMQ/Outbox) e ART-012 (Migrations).
- **Purpose**: Fechar os gaps implementáveis que separam o estado actual (S01–S08 funcionais com decisões pragmáticas em DECISIONS_TAKEN.md) de um estado compatível com G4 (end-to-end) e preparado para G5 (só faltando ODs comerciais, testes humanos e UAT formal).
- **Target Users**: Equipa backend + frontend + QA + auditoria técnica que consome a API e valida a integração.

## Goals
1. Disponibilizar `GET /api/v1/audit-events` paginado e filtrado exactamente por ART-006 (`operationId: listAuditEvents`, scope `q360.audit`, filtros `entityType`, `entityId`, `correlationId`).
2. Garantir auditoria real (chamadas a `AuditService.record`) nas operações críticas dos módulos product, client, eligibility, pricing e quote, com `result`/`reason` em `metadata_json` quando DOC-001 §19 o exige.
3. Implementar Idempotência real para endpoints com `Idempotency-Key` obrigatório no ART-006: persistir em `idempotency_record` (ART-012 V025), detectar replay com payload diferente e devolver `IDEMP-REPLAY`, devolver resposta gravada para replay idêntico.
4. Implementar Transactional Outbox completo: modelos Django (`managed=False`) para `outbox_event` e `consumer_inbox` (ART-012 V025), serviço de escrita transaccional, dispatcher (`select_for_update skip locked` + marca PUBLISHED/FAILED), comandos de gestão, e cablagem dos eventos-chave do ART-007 para operações de negócio já implementadas.
5. Ligar `AuditPage` no React ao endpoint real (remover dependência de `Mockdata`), adicionar paginação, suportar os filtros query do ART-006 e refletir exactamente o schema `AuditEvent` da OpenAPI.
6. Adicionar Idempotency-Key automático no `httpClient.ts` do frontend para mutações críticas (ART-006 marca o parâmetro como required).
7. Implementar testes de isolamento de tenant cruzado para endpoints e operações persistentes (hardening S10).
8. Garantir que as migrations ART-012 V001–V026 aplicam do zero numa base limpa e que o golden test runner existente valida o que está no `docs/artifacts/ART-013-golden-tests/golden/`.

## Non-Goals
- Implementar um consumidor RabbitMQ real ou conectar a um broker; ART-007 exige outbox antes de eventos saírem, e a "publicação" aqui é a passagem a PUBLISHED no outbox com envelope serializado correto. (Conexão real ao broker fica fora do âmbito — é deployment/config, não lógica de negócio V1.)
- Resolver qualquer Open Decision comercial (OD-001 tarifas, OD-002 moeda, OD-005 authority, OD-006 template, OD-007/008 numeração, OD-009 IdP real) — cada OD continua bloqueada em produção como antes; só usamos os placeholders de teste já documentados.
- Adicionar endpoints, estados, campos ou erros não presentes no ART-006; excepções já existentes em DECISIONS_TAKEN.md (listagens pragmáticas, `status` no ProductUpdateRequest, `GET /quotes/{id}/members`) não são expandidas e não são aqui duplicadas.
- UAT formal, pen-test, tuning de performance com métricas reais e runbook operacional de produção (são actividades humanas / SRE, não código acionável nesta fase).

## Background & Context
- Estado actual: backend Django modular monolith com apps foundation, product, client, eligibility, pricing, quote — S01–S08 implementados e testados; `AuditService` existe mas só é chamado em foundation; `AuditEvent` ORM existe mas não há endpoint de listagem; tabelas ART-012 V025 (`outbox_event`, `idempotency_record`, `consumer_inbox`) existem no DDL mas sem ORM, sem serviços, sem cablagem; `Idempotency-Key` está listado nos CORS mas não há middleware; frontend `AuditPage` usa `Mockdata` e `filterAuditEvents` local.
- Documentos autoritativos (pela ordem de precedência DOC-000): ART-005 (esquema físico), ART-012 (migrations V001–V026), ART-006 (HTTP OpenAPI), ART-007 (eventos/topologia/outbox), DOC-004 (arquitectura modular/ports), DECISIONS_TAKEN.md (pragmáticas já aceites).
- O stack é Python/Django + DRF backend, React + TypeScript frontend, PostgreSQL. Sem task queue (confirmado em DECISIONS_TAKEN.md S08: `expire_quotes` é management command). Seguimos o mesmo padrão para dispatcher do outbox.

## Functional Requirements
- **FR-1**: Endpoint `GET /api/v1/audit-events` em conformidade ART-006: scope `q360.audit`, pagination `Q360PageNumberPagination`, query filters opcionais `entityType`, `entityId`, `correlationId`, resposta `AuditEventPage` com cada item `AuditEvent` (camelCase exacto: `id, actorId, action, entityType, entityId, occurredAt, correlationId, metadata`).
- **FR-2**: Toda operação crítica de negócio (produto: create/update/version publish; cliente: proposer create/update, member create/update/delete/import commit; eligibility evaluate; pricing calculate/rule publish; quote: create/update population/price/submit/cancel/approve/reject/return/document generate/expire) emite 1 linha `audit_event` com actor/tenant/action/entity/correlation e `metadata.result` SUCCESS|FAILURE mais `metadata.reason` quando aplicável a decisões.
- **FR-3**: Middleware de idempotência activo para endpoints que ART-006 marca com `$ref: '#/components/parameters/IdempotencyKey'`; lê cabeçalho `Idempotency-Key`, calcula `request_hash` (SHA-256 de `(method, path, body, tenant)`), grava `idempotency_record` em `IN_PROGRESS` antes de view; ao concluir, grava `response_status` + `response_body_json` + `resource_id` e marca `COMPLETED`; no replay do mesmo (key, tenant, operation) com mesmo hash devolve resposta gravada sem reexecutar; replay com hash diferente devolve `409 IDEMP-REPLAY`.
- **FR-4**: Transactional Outbox. (a) ORMs `managed=False` para `outbox_event` e `consumer_inbox` (campos/check constraints exactos ART-012 V025). (b) Serviço `OutboxService.append(*, aggregate_type, aggregate_id, event_type, payload, schema_version, correlation_id, causation_id)` — sempre dentro da transacção PostgreSQL da alteração de negócio, usando `atomic()`. (c) Payload do envelope segue o ART-007 `envelope` (inclui `eventId, eventType, schemaVersion, occurredAt, tenantId, aggregateType, aggregateId, correlationId, causationId, producer="q360-core", payload`). (d) Management command `dispatch_outbox` que reclama lote curto com `SELECT … FOR UPDATE SKIP LOCKED WHERE status IN (PENDING, FAILED) AND (next_attempt_at IS NULL OR next_attempt_at <= now())`, tenta publicação (lado "publicação" = valida envelope, serializa, marca `PUBLISHED + published_at`; qualquer falha: `attempts++`, `last_error_safe` truncado, `next_attempt_at` por backoff exponencial curto 10s/30s/2m/10m/30m a 5 tentativas; depois FAILED). (e) Cablagem de eventos: APPEND para os 20+ eventos do ART-007 onde já existe a operação correspondente no código (QUOTE.CREATED, QUOTE.POPULATION.UPDATED, QUOTE.PRICE.CALCULATED, QUOTE.SUBMITTED, QUOTE.APPROVED, QUOTE.REJECTED, QUOTE.RETURNED, QUOTE.CANCELLED, QUOTE.EXPIRED; PRICING.CALCULATED/FAILED/SCENARIO.CREATED; ELIGIBILITY.EVALUATED; PROPOSER.CREATED/UPDATED; MEMBER.CREATED/UPDATED; MEMBER.IMPORT.COMPLETED; PRODUCT.VERSION.PUBLISHED; PLAN.CREATED/UPDATED; DOCUMENT.GENERATION.REQUESTED/GENERATED/FAILED).
- **FR-5**: Frontend `AuditPage` abandona `mockAuditEvents`. Adiciona `auditApi.ts` com `listAuditEvents(query)` usando `httpClient`, controlos de paginação (page/size/totalElements), filtros mapeados directamente aos query params `entityType`, `entityId`, `correlationId` (sem filtros inventados). Os tipos `AuditEvent`/`AuditEventType` alinham-se ao schema do ART-006 (`id, actorId, action, entityType, entityId, occurredAt, correlationId, metadata`).
- **FR-6**: `httpClient.ts` gere `Idempotency-Key`: para mutações (`POST/PUT/PATCH/DELETE`) em endpoints ART-006 cujo schema o declara required, gera um UUID por request se ainda não existir no cliente, persiste opcionalmente numa cache in-memory por (method,urlKey,bodyHash) curta para retry de rede, envia o cabeçalho, e trata `409 IDEMP-REPLAY` como erro tratado.
- **FR-7**: Testes de isolamento por tenant cobrindo: criar produto/cotação/membro em tenant A, autenticar como tenant B, tentar ler/alterar o mesmo recurso por ID, esperar 404/NOT-FOUND; e assegurar que audit_events e outbox_events criados por A não são visíveis via endpoint paginado do tenant B.
- **FR-8**: Teste de integração que executa `migrate` do zero numa base PostgreSQL limpa (Testcontainers), valida que todas as 26 migrations V001–V026 se aplicam sem erro, e depois corre os 4 golden tests JSON existentes em `docs/artifacts/ART-013-golden-tests/golden/` como chamadas HTTP com assert de campos determinísticos.

## Non-Functional Requirements
- **NFR-1 (Determinismo)**: Outbox envelope e audit `occurredAt` usam sempre tempo do servidor (agora), nunca tempo do cliente; `request_hash` de idempotência é SHA-256 hex sempre.
- **NFR-2 (Segurança)**: `AuditService._FORBIDDEN_METADATA_KEYS` alargado para cobrir `authorization,access_token,refresh_token,secret,password,jwt,api_key`; `last_error_safe` do outbox recebe stack trace truncado a 2 KB e passa por sanitização para não conter payload de request.
- **NFR-3 (Isolamento)**: Toda query feita por `listAuditEvents` e dispatcher do outbox filtra `tenant_id` obrigatoriamente via `TenantScopedModel` + middleware do actor.
- **NFR-4 (Performance)**: Dispatcher do outbox usa batch de 50 por passagem; índices ART-012 V025 (`ix_outbox_dispatch`) estão criados e são usados.
- **NFR-5 (Compatibilidade)**: Nenhuma alteração aos modelos Django `managed=False` existentes; nenhuma migration nova é criada (o schema V025 já tem tudo).
- **NFR-6 (Convenções)**: Segue exactamente estrutura de pastas e estilo já existente (apps/<mod>/application | domain | infrastructure | interfaces | tests; camelCase em JSON via `serializers`; `ProblemDetail` para erros; `Q360PageNumberPagination`).

## Constraints
- **Technical**: Sem migrations novas (V001–V026 são a baseline). Sem Django ORM `makemigrations` sobre os modelos `managed=False`. Sem RabbitMQ real no ambiente de teste do CI; dispatcher valida só o percurso "persiste → PUBLISHED local" (a publicação de rede real está fora de âmbito por Non-Goal). Sem task queue — outbox dispatcher é `python manage.py dispatch_outbox --once` ou loop contínuo com `--interval`.
- **Business**: Nenhum valor comercial inventado; todos os placeholders seguem DECISIONS_TAKEN.md. Nenhuma permissão nova fora da matriz DOC-001 §18.
- **Dependencies**: DRF `APIView`/`viewsets` existentes, `django.db.transaction.atomic`, Python stdlib `hashlib` para SHA-256, `uuid` standard. Frontend: `@tanstack/react-query` (já existe via `queryClient.ts`) e `uuid` (verificar package.json; se não existir, não introduzir — usar `crypto.randomUUID()` que é browser API padrão).

## Assumptions
- Como não há broker real, "publicar com sucesso" no dispatcher significa: (1) validar que envelope tem todos os campos obrigatórios ART-007; (2) `json.loads(json.dumps(envelope))` round-trip; (3) assert payload mínimo sem campos proibidos. A implementação prepara um ponto de extensão `publisher = OutboxPublisherAdapter` que em teste/dev é o `NoopPublisher` validante; um adaptador RabbitMQ real pode ser plugado mais tarde sem tocar nas restantes camadas (ports/adapters pattern DOC-004).
- Lista exacta dos endpoints ART-006 que requerem `Idempotency-Key` = todos os paths em ART-006 com `parameters` contendo `$ref: '#/components/parameters/IdempotencyKey'` (±20 operações de mutação: create product, create version, publish version, create plan, create proposer, create member, commit import, evaluate eligibility, calculate pricing, create rule version, publish config, create quote, price quote, submit quote, decide quote, cancel quote, generate proposal, upload import, etc.). Para identificar o operation_code no `idempotency_record`, usamos `view.__module__ + "." + view.__class__.__name__` ou o `operationId` se for acessível — fallback estável.
- Para golden tests: usamos os 4 JSON existentes (`GT-ELIG-002`, `GT-IDEMP-002`, `GT-PRICE-005`, `GT-WF-003`) e o template `PENDING_OD_pricing_template.json` é explicitamente saltado (apenas validamos que não crasha, não fazemos assert de campos porque está PENDING_OD).

## Acceptance Criteria

### AC-1: listAuditEvents responde exactamente por ART-006
- **Type**: `rule`
- **Given**: Actor autenticado com scope `q360.audit` e pelo menos 1 `AuditEvent` existente
- **When**: GET `/api/v1/audit-events?page=0&size=20`
- **Then**: HTTP 200; corpo raiz tem `items:[]` e `page:{page,size,totalElements,totalPages}`; cada item tem campos e formatos exactos `id, actorId, action, entityType, entityId, occurredAt, correlationId, metadata`; nomes em camelCase; `additionalProperties` não esperados; `X-Correlation-Id` ecoado no cabeçalho.
- **Pass Condition**: Resposta schema-validada por contrato + testes unitários que asserter campos exactos e `403` sem scope audit.
- **Evidence**: `tests/foundation/test_audit_list_endpoint.py` verde.

### AC-2: Operações críticas produzem audit_event transaccionalmente
- **Type**: `rule`
- **Given**: Actor autenticado com permissões apropriadas
- **When**: Executar operações create product + publish version + create proposer + create member + evaluate eligibility + calculate pricing + create quote + price quote + submit quote + decide approve + generate proposal
- **Then**: 1 (exactamente 1, não duplica nem omite) `audit_event` por operação, com `action` distinto e `metadata.result == "SUCCESS"` em caso de sucesso; em caso de erro conhecido (ex.: pricing falha por config ausente) também grava 1 `audit_event` com `metadata.result == "FAILURE"` e `metadata.reason/failure_code`.
- **Pass Condition**: Testes por módulo com contagem e assert dos campos críticos de cada evento; não há operação na lista sem audit correspondente.
- **Evidence**: Testes adicionais em `tests/product/test_products.py`, `tests/client/`, `tests/pricing/`, `tests/quote/` todos verdes.

### AC-3: Idempotência previne replay e IDEMP-REPLAY acerta hash diferente
- **Type**: `rule`
- **Given**: Endpoint de mutação com `Idempotency-Key` obrigatório; actor autenticado.
- **When**: (a) Mesmo key + mesmo body duas vezes; (b) Mesma key + body diferente.
- **Then**: (a) Segunda chamada devolve exactamente `response_status` + `response_body_json` gravado na primeira, sem nova linha de negócio; (b) Segunda chamada devolve 409 `{"code": "IDEMP-REPLAY", ...}` ProblemDetail.
- **Pass Condition**: `tests/foundation/test_idempotency.py` com ambos os casos + verificação de linha em `idempotency_record`.
- **Evidence**: O ficheiro de teste verde.

### AC-4: Transactional Outbox grava no mesmo commit e dispatcher marca PUBLISHED
- **Type**: `rule`
- **Given**: Transacção que altera estado de negócio e chama `OutboxService.append`.
- **When**: (i) Fazer commit da transacção; (ii) Correr `python manage.py dispatch_outbox --once`.
- **Then**: (i) Rollback da transacção também remove o outbox_event; (ii) Após dispatcher, eventos válidos estão `status=PUBLISHED` com `published_at` preenchido; envelope JSON desserializa exactamente como ART-007 envelope + payload. Eventos com envelope inválido → FAILED após 5 tentativas.
- **Pass Condition**: Testes transacção rollback + dispatcher batch + `last_error_safe` não contém PII.
- **Evidence**: `tests/foundation/test_outbox.py` + `tests/quote/test_quotes_outbox.py` verdes.

### AC-5: Eventos do ART-007 são emitidos para operações já implementadas
- **Type**: `rule`
- **Given**: Mapeamento evento → operação de código documentado.
- **When**: Executar a operação correspondente (ex: `quote_service.submit_quote`).
- **Then**: `outbox_event` existe com `event_type` exacto do ART-007 (uppercase com pontos), `aggregate_type` correspondente, `payload_json` contendo os campos mínimos do payload do ART-007.
- **Pass Condition**: 1 assert por eventType cobrindo pelo menos QUOTE.CREATED, QUOTE.SUBMITTED, QUOTE.APPROVED, PRICING.CALCULATED, ELIGIBILITY.EVALUATED, PRODUCT.VERSION.PUBLISHED, MEMBER.CREATED, PROPOSER.CREATED.
- **Evidence**: Testes em `tests/integration/test_outbox_event_catalog.py` verde.

### AC-6: Frontend AuditPage usa API real e pagina
- **Type**: `rule`
- **Given**: API `listAuditEvents` a funcionar, fixtures de 30 eventos de auditoria.
- **When**: Abrir página de auditoria, mudar de página, aplicar filtro `entityType=QUOTE`, `correlationId=…`.
- **Then**: Dados chegam via API (chamada `GET /api/v1/audit-events` visível em DevTools Network); paginação funciona (page 0 size 20 → 20 items, next → mais 10); filtro é passado como query param e reflecte resultados; `mockAuditEvents` não é importado em lado nenhum do build produtivo.
- **Pass Condition**: Vitest `src/tests/audit.test.ts` actualizado e verde; assert que `Mockdata.ts` não é importado fora de ambientes de dev se ainda existir.
- **Evidence**: `npm run test` no frontend verde.

### AC-7: httpClient envia Idempotency-Key em mutações e trata IDEMP-REPLAY
- **Type**: `rule`
- **Given**: Mutação via `httpClient.post(url, body)`.
- **When**: Request é enviado.
- **Then**: Cabeçalho `Idempotency-Key` existe e é UUID válido; dois POSTs com mesmo corpo recebidos pelo mesmo interceptador teste reutilizam o mesmo key numa janela de retry; resposta 409 `code=IDEMP-REPLAY` é parseada correctamente pelo `problemDetail.ts`.
- **Pass Condition**: `src/tests/httpClient.test.ts` actualizado com os novos casos e verde.
- **Evidence**: O ficheiro de teste verde.

### AC-8: Isolamento de tenant impede acesso cruzado
- **Type**: `rule`
- **Given**: Tenant A cria Quote #QA. Actor autenticado Tenant B.
- **When**: Actor B tenta `GET /api/v1/quotes/{QA.id}`, `GET /api/v1/audit-events?entityId={QA.id}`, `GET /api/v1/quotes/{QA.id}/members`.
- **Then**: Todas respondem 404 `NOT-FOUND` (não 403 nem 200 com 0 items — é erro do tipo NOT-FOUND por convenção ART-006 quando o recurso não existe no scope do tenant). Linhas de outros tenants não aparecem em listagens paginadas.
- **Pass Condition**: `tests/foundation/test_tenant_isolation.py` verde.
- **Evidence**: O ficheiro de teste verde.

### AC-9: Migrations do zero + golden tests rodam em base limpa
- **Type**: `rule`
- **Given**: Base PostgreSQL vazia, Testcontainers.
- **When**: `migrate` de todas as apps; correr os 4 GT JSON existentes.
- **Then**: Todas as migrations V001–V026 aplicam sem erro. GTs que não PENDING_OD produzem resultados determinísticos (mesmos campos de output, mesmos valores determinísticos que o JSON do artefacto).
- **Pass Condition**: `tests/integration/test_migrations_and_golden.py` verde.
- **Evidence**: O ficheiro de teste verde.

### AC-10: Cobertura e fidelidade a padrões do projecto
- **Type**: `rubric`
- **Dimension**: Fidelidade às convenções já estabelecidas (estrutura, nomenclatura, tratamento de erros, pagination, serializers camelCase, middleware, ports, separação application/domain/infrastructure).
- **Scale**: 1-5
- **Anchors**: 1 = violações claras de padrão (managed=True nos modelos, migração criada fora do ART-012, inventado endpoint fora do ART-006); 3 = funcionalidades implementadas mas com 1-2 pequenos desvios (ex: nome variante inconsistente); 5 = idêntico ao estilo dos módulos S01–S08 entregues, reutiliza Q360PageNumberPagination, ProblemDetail, Scope, TenanScopedModel, PermissionsGate, etc.
- **Pass Threshold**: >= 4
- **Evidence**: Revisão por leitura da árvore de arquivos criados vs arquivos existentes em `apps/*/application|domain|infrastructure|interfaces`.

## Open Questions
- [ ] Em `OutboxService.append` para `QUOTE.*`, qual o `aggregate_version` exacto que devemos usar? (Assumimos: `Quote.row_version`. Se não existir em V1, omitimos o campo que é optional por ART-007.)
- [ ] Na cablagem de audit para erros, todos os erros conhecidos produzem `FAILURE`. Questionamos para S10-Hardening: devemos incluir erros 500 inesperados também? (Resposta: usamos signal do exception_handler para gravar audit com result FAILURE quando a request já tem actor autenticado — isto é uma melhoria automática do middleware, sem inventar novo comportamento.)

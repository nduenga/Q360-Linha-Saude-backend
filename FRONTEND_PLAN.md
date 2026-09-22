# Plano de Frontend — Especificação Completa (2026-09-22)

**Para quem vai construir/actualizar o frontend.** Esta sessão constrói
**só backend**. Este documento substitui por completo as versões
anteriores e é intencionalmente exaustivo: cobre **toda** a API
disponível hoje (não só o que mudou esta semana), o **estado real** de
cada ecrã do frontend actual (`Q360-Linha-Sa-de-frontend`, branch
`main`) verificado directamente no código — não por suposição — e o
contrato exacto das duas features novas desta sessão (Motor de
Elegibilidade Fase A, Portal do Cliente Fase 0).

Complementa `ROADMAP_ANGOLA_CUSTOMIZATION.md`/`ROADMAP_PORTAL_CLIENTE.md`
(racional de negócio, Open Decisions) e `CHECKLIST_CUSTOMIZACAO.md`
(vista rápida de progresso). Este ficheiro é o **contrato técnico**: que
rota chamar, que forma tem o pedido/resposta, que ficheiro editar.

**Repositório frontend:** `Q360-Linha-Sa-de-frontend`, branch `main`.
**Backend:** `Quote - Saúde/backend`, branch `fabio`.

---

## 0. Legenda

- ✅ **Backend pronto** — endpoint existe, testado, pode implementar já.
- ⏳ **Backend por construir** — não existe ainda, não implementar no
  frontend antes disso (evita construir contra uma forma que ainda pode
  mudar).
- 🔒 **Bloqueado** — não existe endpoint nenhum e não há trabalho de
  backend planeado para isto na V1 (ex.: gestão de utilizadores/roles —
  identidade é federada via Auth0/OIDC, não há tabela `user` em
  ART-005). Não construir contra dados inventados a fingir que é real.
- 🟢 **Real** / 🟡 **Misto** / ⚪ **Mock** — estado actual verificado no
  código do frontend (secção 4).

---

## 1. Convenções transversais da API

Aplicam-se a **todos** os endpoints staff (`/api/v1/...`, excepto
`/api/v1/customer-portal/...`, que tem o seu próprio contrato — secção 6).

### 1.1 Autenticação

- Header: `Authorization: Bearer <jwt>` em todos os pedidos, excepto os
  marcados `AllowAny` abaixo (`/api/v1/health/*`, `/api/v1/auth/dev-login`
  — dev-only, `/api/v1/customer-portal/...`).
- **Estado actual real do frontend**: login é feito via **Auth0**
  (`@auth0/auth0-react`), não por email/password contra
  `/api/v1/auth/dev-login`. `src/auth/LoginPage.tsx` só tem um botão
  "Iniciar Sessão" que chama `loginWithRedirect()`. O token é gerido
  inteiramente pelo SDK do Auth0 (`Auth0ProviderWithNavigate.tsx`,
  `cacheLocation="localstorage"`, `useRefreshTokens`) — a app nunca toca
  directamente no token/localStorage. `httpClient.ts` obtém o token via
  `accessTokenProvider()` registado em `app/providers.tsx`
  (`auth0.getAccessTokenSilently()`), com fallback a
  `VITE_DEV_BEARER_TOKEN` só em dev quando não autenticado (usado por
  `/dev/api-console`). Ver `AUTH0_SETUP.md` para a configuração da conta.
- **`roles`/`permissions` nunca vêm do JWT directamente** — depois do
  login, `fetchMe()` (`src/auth/services/authApi.ts`) chama
  `GET /api/v1/me` e o resultado é a única fonte de verdade, combinado
  com `name`/`email` do Auth0 em `CurrentUser` (`CurrentUserContext`).
  **Isto já está correcto e não precisa de alteração.**
- `GET /api/v1/me` — Auth: `IsAuthenticated` + scope `q360.read`.
  Resposta 200:
  ```json
  { "actorId": "string", "tenantId": "uuid", "roles": ["ADMIN"], "permissions": ["audit:read", "product:manage"] }
  ```
- `POST /api/v1/auth/dev-login` — **dev-only**, 404 em produção (a rota
  desaparece se `OIDC_STATIC_VERIFICATION_KEY` não estiver definida, e
  `config/settings/production.py` recusa arrancar com essa variável
  definida). Usado só por `manage.py`/testes/curl, nunca pelo frontend em
  produção. Corpo: `{ "email": string, "password": string }`. Resposta
  200: `{ "accessToken": string, "expiresIn": 3600, "name": string }`.
  Identidades demo: `admin@q360.co.ao`/`Q360admin2026` (ADMIN),
  `aprovador@q360.co.ao`/`Q360aprova2026` (APPROVER),
  `subscritor@q360.co.ao`/`Q360demo2026` (SUBSCRIBER).

### 1.2 Scopes, Roles, Permissions

Duas camadas independentes, **ambas** têm de passar — nenhuma substitui
a outra:

**Scope** (OAuth2, grosseiro, por operação HTTP — vem do JWT):
`q360.read`, `q360.write`, `q360.approve`, `q360.admin`, `q360.audit`.

**Role** (DOC-001 §6): `ADMIN`, `PRODUCT_CONFIGURATOR`, `SUBSCRIBER`,
`APPROVER`, `AUDITOR`.

**Permission** (DOC-001 §18, fine-grained RBAC — usar
`hasPermission()`/`hasAnyPermission()` de `src/auth/permissions.ts` para
mostrar/esconder botões, nunca `hasRole()` excepto onde já é o padrão —
ver nota Administração):

| Permission | ADMIN | PRODUCT_CONFIGURATOR | SUBSCRIBER | APPROVER | AUDITOR |
|---|---|---|---|---|---|
| `quote:create` | ✓ | ✓ | ✓ | | |
| `quote:edit` | ✓ | ✓ | ✓ | | |
| `quote:calculate` | ✓ | ✓ | ✓ | ✓ | |
| `quote:submit` | ✓ | ✓ | ✓ | | |
| `quote:review` | ✓ | ✓ | | ✓ | ✓ |
| `quote:approve` | ✓ | | | ✓ | |
| `quote:reject` | ✓ | | | ✓ | |
| `product:manage` | ✓ | ✓ | | | |
| `pricing-config:manage` | ✓ | ✓ | | | |
| `audit:read` | ✓ | | | ✓ | ✓ |

Não existe permissão DOC-001 para "configuração de regras" (rule-versions)
nem para o domínio client/eligibility genericamente — esses endpoints são
protegidos só por Scope (ver tabela de endpoints). O ecrã de
Administração continua gated por **Role** `ADMIN` (`AdminRoute` no
router), não por Permission — DOC-001 não define uma permissão granular
para essa área ainda; manter assim.

### 1.3 Envelope de erro genérico (`ProblemDetail`)

Content-Type `application/problem+json`. Já implementado em
`src/api/problemDetail.ts`/`httpClient.ts` (`ApiError.problem`) — **nada
a fazer aqui**, só usar.

```json
{ "title": "string", "status": 401, "code": "AUTH-401", "detail": "string", "correlationId": "uuid" }
```

Catálogo completo de `code` (união fechada, já reflectida em
`ProblemErrorCode`):

| Code | Título | Quando |
|---|---|---|
| `AUTH-401` | Não autenticado | Token ausente/inválido/expirado. Também usado pelo Portal do Cliente para credenciais inválidas. |
| `AUTH-403` | Sem autorização | Scope/Permission falhou. |
| `SEC-403` | Violação de segurança/tenant/four-eyes | Ex.: o mesmo actor que submeteu tenta aprovar a própria cotação. |
| `VALIDATION-400` | Pedido inválido | Erros de serializer, entidades referenciadas inexistentes, datas incoerentes. |
| `VERSION-CONFLICT` | Optimistic/version conflict | `rowVersion` desactualizado. |
| `QUOTE-STATE` | Transição inválida | Acção não permitida no estado actual da cotação. |
| `PRICING-CONFIG` | Configuração de pricing ausente/inválida | Sem RatingTable/PricingParameterSet publicada aplicável. |
| `PRICING-FAILED` | Falha de cálculo | Cálculo de preço falhou (ex.: overflow). |
| `IDEMP-REPLAY` | Idempotency key reutilizada com payload diferente | Ver 1.4. |
| `NOT-FOUND` | Recurso não encontrado | 404 genérico. |
| `CONFLICT` | Conflito genérico | Código duplicado, versão imutável, membro duplicado numa cotação. |
| `RATE-LIMIT` | Limite excedido | 429. |
| `PORTAL-LOCKED` | Conta temporariamente bloqueada | 423, só Portal do Cliente (5 falhas de OTP). |

Um 5xx não mapeado não usa este envelope (erro genérico do Django).

### 1.4 Idempotência

- Header `Idempotency-Key` obrigatório em **todas** as operações
  mutantes (`POST`/`PUT`/`PATCH`/`DELETE`) marcadas
  `@requires_idempotency` na tabela de endpoints abaixo. **Já
  implementado**: `httpClient.ts` gera sempre uma UUID nova para
  `POST/PUT/PATCH/DELETE` automaticamente — nada a fazer, só não
  reaproveitar a mesma chave manualmente entre pedidos com corpos
  diferentes.
- Mesma chave + mesmo corpo (dentro de 24h) → devolve a resposta
  persistida anterior sem re-executar. Mesma chave + corpo diferente →
  `409 IDEMP-REPLAY`. Mesma chave em voo (pedido concorrente) → também
  `409 IDEMP-REPLAY`.

### 1.5 Paginação

Todas as listas usam `Q360PageNumberPagination`. Query params: `page`
(0-indexed, omitir para 0), `size` (omitir para 20, máx. 200).

```json
{ "items": [ /* ... */ ], "page": { "page": 0, "size": 20, "totalElements": 42, "totalPages": 3 } }
```

Já modelado em `Page<T>` (`domains/product/types/catalog.ts`) — **usar
sempre este tipo genérico**, não reinventar por domínio.
`PricingConfigPanel.tsx` hoje pede `size=200` fixo e ignora o resto —
ver Épico 5 (secção 4.5) para trocar por paginação real.

### 1.6 Rate limit

429 com o mesmo envelope `ProblemDetail`, `code=RATE-LIMIT`. Global: por
tenant/IP, 120 pedidos/60s por omissão. Não há nada especial a fazer no
frontend além de mostrar `detail`/`title` como qualquer outro erro — mas
ver secção 6.4 para o limite adicional, mais agressivo, específico do
Portal do Cliente.

### 1.7 Formato de valores monetários/decimais

Todo o campo monetário/decimal (`factorValue`, `value` quando
`valueType=DECIMAL`, todos os montantes de pricing) é sempre uma
**string** JSON (`"12.50"`), nunca um número binário — para não perder
precisão. Nunca fazer `Number(valor)` e voltar a enviar sem cuidado com
casas decimais; tratar como string/`Decimal.js` de ponta a ponta.

---

## 2. Referência completa de endpoints por módulo

`rowVersion` = lock optimista; enviar sempre o valor mais recente lido,
senão `409 VERSION-CONFLICT`.

### 2.1 Foundation

| Método/Rota | Auth | Idemp. | Corpo/Query | Resposta |
|---|---|---|---|---|
| `GET /api/v1/health/live` | AllowAny | — | — | `200 {"status":"ok"}` |
| `GET /api/v1/health/ready` | AllowAny | — | — | `200 {"status":"ok"}` ou `503 {"status":"unavailable"}` (JSON simples, não é o envelope ProblemDetail) |
| `GET /api/v1/me` | `q360.read` | — | — | ver 1.1 |
| `POST /api/v1/auth/dev-login` | AllowAny | — | ver 1.1 | ver 1.1 (dev-only) |
| `GET /api/v1/audit-events` | scope `q360.audit` | — | query: `entityType`, `entityId`, `correlationId`, `actorId`, `from`, `to` (ISO datetime), `page`, `size` | página de `{id, actorId, action, entityType, entityId, occurredAt, correlationId, metadata}` |
| `GET /api/v1/rule-versions` | scope `q360.read` | — | query: `ruleDomain` (`ELIGIBILITY\|PRICING\|WORKFLOW\|VALIDATION`), `status` (`DRAFT\|PUBLISHED\|RETIRED`), `page`, `size` | página de `VersionedConfigHeader` |
| `POST /api/v1/rule-versions` | scope `q360.admin` | ✅ | `{code, name, ruleDomain, effectiveFrom, effectiveTo?, artifactType: "DRL"\|"DECISION_TABLE"\|"JSON"\|"INTERNAL", artifactRef?, artifactChecksum?}` | `201 VersionedConfigHeader` |
| `PATCH /api/v1/rule-versions/{id}` | scope `q360.admin` | ✅ | `{name, artifactType, artifactRef?, artifactChecksum?}` (só DRAFT) | `200 VersionedConfigHeader` |
| `DELETE /api/v1/rule-versions/{id}` | scope `q360.admin` | ✅ | — (só DRAFT) | `204` |

`VersionedConfigHeader` = `{id, code, versionNo, effectiveFrom, effectiveTo, status, checksum}` — mesma forma partilhada por rule-versions, rating-tables, pricing-parameter-sets e document-templates.

### 2.2 Product

| Método/Rota | Auth | Idemp. | Corpo/Query | Resposta |
|---|---|---|---|---|
| `GET /api/v1/products` | `q360.read` | — | `page`, `size` | página de `{id, code, name, description, status, rowVersion}` |
| `POST /api/v1/products` | `q360.write` + `product:manage` | ✅ | `{code, name, description?}` | `201` Product. `409 CONFLICT` se `code` duplicado |
| `GET /api/v1/products/{id}` | `q360.read` | — | — | `200` Product |
| `PUT /api/v1/products/{id}` | `q360.write` + `product:manage` | ✅ | `{name, description?, rowVersion, status?}` | `200` Product |
| `GET /api/v1/products/{id}/versions` | `q360.read` | — | — | página de `{id, productId, versionNo, effectiveFrom, effectiveTo, status, checksum}` |
| `POST /api/v1/products/{id}/versions` | `q360.admin` + `product:manage` | — | `{effectiveFrom}` (sem `effectiveTo` — versões nunca expiram por desenho) | `201` ProductVersion. `400` se sobrepuser outra versão não retirada |
| `POST /api/v1/product-versions/{id}/publish` | `q360.admin` + `product:manage` | ✅ | — | `200` ProductVersion (PUBLISHED). `409 CONFLICT` se não DRAFT; `400` se faltar alguma cobertura BASE obrigatória num Plano |
| `GET /api/v1/plans` | `q360.read` | — | query: `productVersionId?` | página de `{id, productVersionId, code, name, description, status, rowVersion}` |
| `POST /api/v1/plans` | `q360.admin` + `product:manage` | — | `{productVersionId, code, name, description?}` | `201` Plan (3 coberturas BASE já anexadas automaticamente pelo backend). `409` código duplicado ou versão não DRAFT |
| `GET /api/v1/plans/{id}` | `q360.read` | — | — | `200` Plan |
| `GET /api/v1/benefits` | `q360.read` | — | query: `category?` | página de `{id, code, name, category, description, status}` — catálogo fixo de 11 coberturas (3 BASE + 8 COMPLEMENTARY) |
| `GET /api/v1/plans/{id}/benefits` | `q360.read` | — | — | **array simples (não paginado)** de `{id, planId, benefit: Benefit, configurationJson}` |
| `POST /api/v1/plans/{id}/benefits` | `q360.admin` + `product:manage` | ✅ | `{benefitId}` (só COMPLEMENTARY — BASE já vêm anexadas) | `201` PlanBenefit |
| `DELETE /api/v1/plans/{id}/benefits/{benefitId}` | `q360.admin` + `product:manage` | — | — | `204`. `400` se for uma cobertura BASE (nunca removível) |
| `GET /api/v1/pricing-parameter-sets` | `q360.read` | — | query: `status?` | página de `VersionedConfigHeader` |
| `POST /api/v1/pricing-parameter-sets` | `q360.admin` + `pricing-config:manage` | ✅ | `{code, effectiveFrom, effectiveTo?, parameters: [{code, valueType: "DECIMAL"\|"INTEGER"\|"BOOLEAN"\|"TEXT"\|"JSON", value}]}` (≥1 parâmetro; `DECIMAL` como string) | `201 VersionedConfigHeader`. `409` código+versão duplicados |
| `PATCH /api/v1/pricing-parameter-sets/{id}` | idem | ✅ | `{parameters: [...]}` (só DRAFT; `code`/datas não editáveis) | `200 VersionedConfigHeader` |
| `DELETE /api/v1/pricing-parameter-sets/{id}` | idem | ✅ | — (só DRAFT) | `204` |
| `POST /api/v1/configuration/{tipo}/{id}/publish` | `q360.admin` | ✅ | `{tipo}` ∈ `pricing-parameter-set\|rule-version\|rating-table` | `200` header dict (status PUBLISHED). `404` tipo/id inválido; `409` se não DRAFT |
| `POST /api/v1/configuration/{tipo}/{id}/retire` | `q360.admin` | ✅ | idem | `200` header dict (status RETIRED — nunca apaga a linha) |

### 2.3 Client

| Método/Rota | Auth | Idemp. | Corpo/Query | Resposta |
|---|---|---|---|---|
| `GET /api/v1/relationship-codes` | `q360.read` | — | — | página de `{id, code, label, category: TITULAR\|SPOUSE\|CHILD\|ASCENDANT\|OTHER}` — **usar sempre este catálogo para o dropdown de "Relação", nunca hardcode** |
| `GET /api/v1/proposers` | `q360.read` | — | — | página de Proposer |
| `POST /api/v1/proposers` | `q360.write` | ✅ | `{proposerType: "INDIVIDUAL"\|"ORGANISATION", externalReference?, displayName, registrationNumber?, attributes?}` | `201 {id, proposerType, externalReference, displayName, registrationNumber, attributes, status, rowVersion}`. `409` externalReference duplicado |
| `GET /api/v1/proposers/{id}` | `q360.read` | — | — | `200` Proposer |
| `PUT /api/v1/proposers/{id}` | `q360.write` | ✅ | `{displayName, registrationNumber?, attributes?, rowVersion}` | `200` Proposer |
| `GET /api/v1/members` | `q360.read` | — | query: `proposerId?` | página de Member |
| `POST /api/v1/members` | `q360.write` | ✅ | `{proposerId, externalReference?, relationshipCode, firstName?, lastName?, dateOfBirth?, sexCode?, attributes?}` | `201 {id, proposerId, externalReference, relationshipCode, firstName, lastName, dateOfBirth, sexCode, attributes, status, rowVersion}`. `400` relationshipCode desconhecido ou data incoerente |
| `GET /api/v1/members/{id}` | `q360.read` | — | — | `200` Member |
| `PUT /api/v1/members/{id}` | `q360.write` | ✅ | `{relationshipCode, firstName?, lastName?, dateOfBirth?, sexCode?, attributes?, rowVersion}` | `200` Member |
| `POST /api/v1/member-imports` | `q360.write` | ✅ | **multipart/form-data**: `file` + `proposerId?` | `202 {id, proposerId, status: ImportJobStatus, totalRows, validRows, invalidRows, createdAt}` |
| `GET /api/v1/member-imports/{id}` | `q360.read` | — | — | `200` ImportJob |
| `POST /api/v1/member-imports/{id}/commit` | `q360.write` | ✅ | `{confirm: true}` | `202` ImportJob. `409` se job não estiver `VALIDATED` |

`ImportJobStatus`: `UPLOADED, VALIDATING, VALIDATED, COMMITTING, COMPLETED, FAILED`.

### 2.4 Pricing

| Método/Rota | Auth | Idemp. | Corpo/Query | Resposta |
|---|---|---|---|---|
| `GET /api/v1/rating-tables` | `q360.read` | — | query: `status?` | página de `VersionedConfigHeader` |
| `POST /api/v1/rating-tables` | `q360.admin` + `pricing-config:manage` | ✅ | `{code, name, effectiveFrom, effectiveTo?, currencyCode? (^[A-Z]{3}$), factors: [{factorCode, dimensions: object, factorValue: string, priority?}]}` (≥1 factor) | `201 VersionedConfigHeader` |
| `PATCH /api/v1/rating-tables/{id}` | idem | ✅ | `{name, currencyCode?, factors: [...]}` (só DRAFT) | `200 VersionedConfigHeader` |
| `DELETE /api/v1/rating-tables/{id}` | idem | ✅ | — (só DRAFT) | `204` |
| `POST /api/v1/pricing/calculate` | `q360.write` + `quote:calculate` | ✅ | `{productVersionId, planId, effectiveDate, memberIds: uuid[] (não vazio), context?}` | `200` ver `PricingResponse` abaixo. `400` referência inexistente; `422 PRICING-CONFIG`/`PRICING-FAILED` |
| `GET /api/v1/pricing/{runId}/explanation` | `q360.read` | — | — | `200 {pricingRunId, steps: [{sequence, stepCode, ruleCode, message, input, output}]}` |
| `POST /api/v1/pricing/scenarios` | `q360.write` + `quote:calculate` | ✅ | `{basePricingRunId, name, overrides: object}` | `201` `PricingResponse` do cenário |

`PricingResponse`:
```json
{
  "pricingRunId": "uuid", "status": "CALCULATED",
  "currencyCode": "AOA", "totalAmount": "123.45",
  "components": [{"order":0,"code":"BASE_PREMIUM","type":"BASE","baseAmount":"100.00","factorValue":"1.05","adjustmentAmount":null,"resultAmount":"105.00","sourceCode":null,"sourceVersion":null}],
  "versions": {"productVersionId":"uuid","ratingTableId":"uuid","parameterSetId":"uuid","ruleVersionId":"uuid","roundingPolicyCode":null,"roundingPolicyVersion":null},
  "calculatedAt": "iso-datetime"
}
```

### 2.5 Quote

| Método/Rota | Auth | Idemp. | Corpo/Query | Resposta |
|---|---|---|---|---|
| `GET /api/v1/quotes` | `q360.read` | — | query: `status?`, `quoteNumber?` | página de `{id, quoteNumber, proposerId, productVersionId, planId, status, effectiveDate, validUntil, currencyCode, latestPricingRunId, rowVersion}` |
| `POST /api/v1/quotes` | `q360.write` + `quote:create` | ✅ | `{proposerId, productVersionId, planId, effectiveDate}` | `201` Quote (DRAFT) |
| `GET /api/v1/quotes/{id}` | `q360.read` | — | — | `200` Quote |
| `PUT /api/v1/quotes/{id}` | `q360.write` + `quote:edit` | ✅ | `{effectiveDate, rowVersion}` | `200` Quote. `409 QUOTE-STATE`/`VERSION-CONFLICT` |
| `GET /api/v1/quotes/{id}/members` | `q360.read` | — | — | página de `{id, memberId, status: "INCLUDED"\|"EXCLUDED"\|"REFERRAL", eligibilityEvaluationId}` |
| `POST /api/v1/quotes/{id}/members` | `q360.write` + `quote:edit` | ✅ | `{memberId}` | **`200` devolve a Quote pai, não o QuoteMember criado**. `409` membro duplicado ou estado inválido |
| `DELETE /api/v1/quotes/{id}/members/{memberId}` | `q360.write` + `quote:edit` | ✅ | — | `204` |
| `POST /api/v1/quotes/{id}/price` | `q360.write` + `quote:calculate` | ✅ | `{recalculate?: boolean}` | `200` `PricingResponse` |
| `POST /api/v1/quotes/{id}/submit` | `q360.write` + `quote:submit` | ✅ | `{rowVersion}` | `200` Quote (READY/IN_REVIEW) |
| `GET /api/v1/quotes/{id}/review` | `q360.read` | — | — | `200 {id, quoteId, status: ReviewTaskStatus, assignedTo, createdAt}`. `404` se não houver tarefa activa |
| `POST /api/v1/quotes/{id}/decision` | scope `q360.approve` + (`quote:approve`/`quote:reject`/`quote:review` conforme `decision`) | ✅ | `{decision: "APPROVE"\|"REJECT"\|"RETURN", reasonCode, reasonText?, rowVersion}` | `200` Quote. `403 SEC-403` se o mesmo actor submeteu e decide (four-eyes) |
| `GET /api/v1/quotes/{id}/history` | `q360.read` | — | — | **array simples** de `{fromStatus, toStatus, reasonCode, reasonText, changedBy, changedAt}` |
| `POST /api/v1/quotes/{id}/cancel` | `q360.write` + `quote:edit` | ✅ | `{reasonCode, reasonText?, rowVersion}` | `200` Quote (CANCELLED) |
| `POST /api/v1/quotes/{id}/proposal` | `q360.write` | ✅ | — | `202 {id, quoteId, documentType:"QUOTE_PROPOSAL", documentNumber, status: "REQUESTED"\|"GENERATED"\|"FAILED", generatedAt}` |
| `GET /api/v1/quotes/{id}/proposal` | `q360.read` | — | — | `200` Document. `404` se nenhum gerado ainda |
| `GET /api/v1/document-templates` | `q360.admin` + `product:manage` | — | query: `templateCode?` | página de `{id, templateCode, versionNo, status, effectiveFrom, effectiveTo, checksum}` |
| `POST /api/v1/document-templates` | idem | ✅ | `{templateCode, storageRef, effectiveFrom, effectiveTo?}` | `201` header |
| `PATCH /api/v1/document-templates/{id}` | idem | ✅ | `{storageRef}` (só DRAFT) | `200` header |
| `DELETE /api/v1/document-templates/{id}` | idem | ✅ | — (só DRAFT) | `204` |
| `POST /api/v1/document-templates/{id}/publish` | idem | ✅ | — | `200` header (PUBLISHED) |
| `POST /api/v1/document-templates/{id}/retire` | idem | ✅ | — | `200` header (RETIRED) |
| `GET /api/v1/reviews` | scope `q360.approve` + `quote:review` | — | query: `status?` | página de ReviewTask |

`QuoteStatus`: `DRAFT, READY, IN_REVIEW, APPROVED, REJECTED, EXPIRED, CANCELLED`.
`ReviewTaskStatus`: `OPEN, IN_PROGRESS, DECIDED, RETURNED`.

### 2.6 Eligibility

| Método/Rota | Auth | Idemp. | Corpo | Resposta |
|---|---|---|---|---|
| `POST /api/v1/eligibility/evaluate` | scope `q360.write` | ✅ | `{proposerId?, memberId?, productVersionId, planId, effectiveDate, context: object}` | `200 {evaluationId, decision, ruleVersionId, messages: [{code, severity: "INFO"\|"WARNING"\|"ERROR", message}], evaluatedAt}` — ver secção 5 para as 3 decisões novas e `context.angola` |

---

## 3. Autenticação/estado real — nada a construir aqui

Confirmado no código: Épico 0 (Auth0) e a ligação de `roles`/`permissions`
via `/api/v1/me` já estão correctos e completos. **Não mexer** — só
usar `hasPermission`/`hasAnyPermission`/`hasRole` já existentes em
`src/auth/permissions.ts`.

---

## 4. Estado actual do frontend, ecrã a ecrã (verificado no código)

### 4.1 Produtos — 🟢 Real, com 2 ajustes pendentes

`src/domains/product/ProductPage.tsx` (lista + criar) e
`ProductDetailPage` (mesma ficheiro): já chamam
`catalogApi.ts`/`benefitApi.ts` reais.

**Pendente (Épico 2+3, backend já pronto):**
- Criar produto hoje faz **3 chamadas encadeadas no frontend**
  (`createProduct` → `createProductVersion` → cria um Plano "Básico" →
  `publish`). Isto continua a funcionar, mas o Épico 2 do backend
  (`create_next_version()`, `PATCH /products/{id}` já herda planos/
  coberturas reais ao editar) torna desnecessário o botão separado
  "Criar versão" em `ProductDetailPage` — **remover esse botão**;
  editar o produto (`PUT /api/v1/products/{id}`) já cria e publica a
  próxima versão sozinho.
- Confirmar que nenhum formulário continua a pedir "Data de término" —
  o backend já não aceita `effectiveTo` em `POST /products/{id}/versions`.

### 4.2 Elegibilidade — 🟢 Real, Épico 4 já feito

`src/domains/eligibility/EligibilityPage.tsx` **já tem** a pesquisa por
número de apólice implementada (não são mais 6 selects manuais) — o
Épico 4 do plano anterior estava desactualizado, isto já está pronto de
ambos os lados. Único trabalho pendente aqui é o da **Fase A do Motor de
Elegibilidade** — ver secção 5.

### 4.3 Configuração (Rating Tables / Pricing Parameter Sets / Rule Versions) — 🟢 Real, Épico 6 já feito

`src/domains/administration/PricingConfigPanel.tsx` **já implementa**
editar/remover/retirar (chama `httpClient` directamente para
`PATCH`/`DELETE`/`.../retire`) — o Épico 6 também estava marcado como
pendente no plano anterior por engano. Ainda vale a pena confirmar
visualmente que os 3 botões só aparecem no estado certo (Editar/Remover
só em DRAFT, Retirar só em PUBLISHED), mas o essencial já está feito.

**Document Templates**: `administration/DocumentTemplatesPanel.tsx`
também já é real (CRUD completo via `httpClient` inline), mas não tem um
`documentTemplateApi.ts` dedicado como os outros domínios — considerar
extrair para consistência, não bloqueante.

### 4.4 Clientes / Membros — 🟢 Real

`CustomerPage.tsx`/`ClientDetailPage` (proponentes),
`MemberImportPage.tsx` (importação em massa, multipart real) — ambos
reais. `BeneficiariesPage.tsx` (passo do wizard de nova cotação) usa
chamadas reais (`createMember`, `POST /quotes/{id}/members`) mas os seus
próprios tipos (`Beneficiary`/`BeneficiaryDraft`) ainda são a forma
antiga da era mock — sem urgência, mas alinhar com `RealMember`
(`domains/customer/types/directory.ts`) evitaria duplicação de forma.

### 4.5 Pricing — 🟡 Real, com o Épico 5 (100% frontend) ainda por fazer

`PricingPage.tsx` já é real. Trabalho pendente, **sem depender de
nenhum endpoint novo**:
- `PricingConfigPanel.tsx`: paginação real (hoje `size=200` fixo,
  ignora `page`/`totalPages`) — usar o `Page<T>` já modelado.
- Reaproveitar o `statusLabel` map já usado em `ProductPage` para
  DRAFT/PUBLISHED/RETIRED em vez de mostrar a string crua.
- Substituir literais mágicos (`priority: -1`, `'BASE_PREMIUM'`,
  `'ADMIN_ADJUSTMENT'`) por constantes nomeadas.
- Vista de histórico das configurações (hoje só lista plana) — usar
  `?status=` para separar DRAFT/PUBLISHED/RETIRED em abas, por exemplo.

### 4.6 Cotação (Nova/Resumo) — 🟡 Real, com uma lacuna concreta

`NewQuotePage.tsx` (wizard) e `QuoteSummaryPage.tsx` já chamam a API
real (`createQuote`, `getQuote`, `priceQuote`, `submitQuote`,
`cancelQuote`). **Lacuna real encontrada**: `QuoteSummaryPage` não chama
`GET /api/v1/quotes/{id}/members` — a lista de membros da cotação viaja
só por `location.state` do router, o que já cai para `EmptyState` se o
utilizador actualizar a página (F5) ou abrir o link directamente.
- **Corrigir**: `QuoteSummaryPage` deve chamar
  `GET /api/v1/quotes/{id}/members` ao montar (a rota já existe e já é
  usada por `Quoteapi.ts` nalgum sítio, mas não aqui), e usar isso como
  fonte de verdade em vez de `location.state`.

### 4.7 Underwriting/Revisão — 🟢 Real

`UnderwritingPage.tsx` (fila) e `QuoteReviewPage.tsx` (decisão) já
cobrem `GET /reviews`, `GET/quotes/{id}`, `/history`, `/decision`,
`/review`, `/pricing/{id}/explanation`, `/proposal` (GET/POST). Nada
pendente identificado.

### 4.8 Auditoria — 🟢 Real

`AuditPage.tsx` já chama `GET /api/v1/audit-events` com filtros e
paginação. Existe um `Mockdata.ts` órfão neste domínio, usado só por
`src/tests/audit.test.ts` — inofensivo, mas pode ser removido quando o
teste for actualizado para não depender dele.

### 4.9 Dashboard — 🔒 Bloqueado (não há endpoint de métricas)

`Dashboardpage.tsx` usa dados 100% mock (`Mockdata.ts`, atraso
artificial de 150ms a simular latência). **Não é um esquecimento do
frontend** — não existe nenhum endpoint de métricas agregadas em
ART-006 nem no roadmap actual. Não construir nada aqui até essa decisão
de produto existir; o comentário TODO já no código está correcto.

### 4.10 Administração — 🟡 Misto, secções de utilizadores/roles ficam 🔒 Bloqueadas

- Abas "Pricing" (embebe `PricingConfigPanel`, real) e "Document
  Templates" (`DocumentTemplatesPanel`, real): sem pendências novas além
  da secção 4.5.
- Abas "Utilizadores", "Roles", "Parâmetros": **100% mock, sem endpoint
  nenhum no backend** — identidade é federada via Auth0/OIDC (DOC-001,
  OD-009), não há tabela `user`/`role` em ART-005 para gerir por CRUD.
  Não ligar a nada real sem uma decisão de produto explícita sobre como
  provisionar utilizadores no Auth0 a partir daqui (fora do âmbito desta
  sessão) — manter como mock e sinalizado como tal, nunca apresentar
  como dado real.

---

## 5. Motor de Elegibilidade — Fase A ✅ Backend pronto (2026-09-22)

`POST /api/v1/eligibility/evaluate` (secção 2.6) agora pode devolver
**3 decisões novas**, além das 5 já existentes — a forma da resposta em
si não mudou, só o conjunto de valores válidos de `decision` e o texto
de `messages[].message`.

| `decision` | Cor no ecrã | Nunca mostrar como |
|---|---|---|
| `ELIGIBLE` | Verde — "Elegível" | — |
| `ELIGIBLE_WITH_LOADING` | Verde, com nota do agravamento | "Rejeitado" |
| `WARNING` | Amarelo | — |
| `REFERRAL` | Amarelo | — |
| `PENDING_DOCUMENT` | Amarelo — "Falta um documento" | "Rejeitado" |
| `PENDING_MEDICAL_BOARD` | Amarelo — "Em análise" | "Rejeitado" |
| `HARD_STOP` | Vermelho — "Não Elegível" | — (o único vermelho) |
| `CONFIG_ERROR` | Nunca mostrado ao cliente final — erro interno | — |

`messages[]` já vem com texto amigável em português para os novos
códigos (`FALTA_CERTIFICADO_MATRICULA`, `FALTA_HOMOLOGACAO_UNIAO_FACTO`,
`FALTA_PROVA_DEPENDENCIA_ASCENDENTE`, `IDADE_ACIMA_LIMITE_DEPENDENTE`,
`ELIGIBLE_COM_AGRAVAMENTO`, `PENDENTE_JUNTA_MEDICA`) — **mostrar sempre
`message`, nunca `code`**. Pode também aparecer um código informativo
`ELIG-WAITING-PERIOD` (severidade `INFO`) junto de um resultado não
bloqueante, com o número de dias de carência aplicável.

### `context.angola` — novo bloco opcional no pedido

```jsonc
{
  "context": {
    "angola": {
      "hasEnrollmentCertificate": false,
      "unionBondType": "UNIAO_DE_FACTO",       // ou "CASAMENTO"
      "hasUnionHomologationDocument": false,
      "hasCohabitationOrFinancialDependencyProof": false,
      "hasPreExistingCondition": false,
      "previousPolicyNumber": null,
      "previousPolicyContinuous": false
    }
  }
}
```

Nenhum destes campos tem upload de ficheiro associado nesta fase (não
existe armazenamento de documentos — Fase B, em aberto); são booleanos
que a equipa de subscrição marca manualmente depois de validar o
documento por fora do sistema. Omitir o bloco inteiro é seguro — o
endpoint continua a funcionar exactamente como hoje.

### O que fazer no frontend

- **Obrigatório**: `EligibilityPage.tsx` (e qualquer resumo de cotação
  que mostre `decision`) — actualizar o mapa de cores/labels para as 8
  decisões da tabela acima. Se hoje só trata as 5 antigas, as 3 novas
  vão cair num `default` genérico — verificar e corrigir.
- **Opcional**, quando fizer sentido no fluxo de subscrição: um pequeno
  formulário/checklist em `BeneficiariesPage.tsx` ou
  `EligibilityPage.tsx` para marcar os campos de `context.angola` antes
  de calcular elegibilidade de um dependente CHILD/SPOUSE/ASCENDANT.

---

## 6. Portal do Cliente — Fase 0 ✅ Backend pronto (2026-09-22)

**Confirmado no código actual: não existe nenhum vestígio de Portal do
Cliente no frontend hoje** (zero ocorrências de "portal" em `src/`) —
isto é uma aplicação/rota **completamente nova, a construir do zero**,
com autenticação, cliente HTTP e RBAC próprios.

### 6.1 Isolamento — regra inegociável

- **Nunca** reaproveitar `httpClient.ts`, `CurrentUserContext`,
  `useCurrentUser`, `Auth0ProviderWithNavigate` ou qualquer coisa de
  `src/auth/` do backoffice.
- Criar um cliente HTTP **novo e separado** (ex.
  `src/portal/api/portalHttpClient.ts`), sem `accessTokenProvider` do
  Auth0, sem injecção automática de `Idempotency-Key` (os 2 endpoints
  não são idempotency-decorated — enviar a header não faz mal mas não é
  necessário), com a sua própria gestão de token (`sessionStorage`
  dedicado, chave diferente da usada pelo Auth0/backoffice).
- O `accessToken` deste portal **nunca** deve ser enviado a
  `/api/v1/quotes`, `/api/v1/products`, etc. — são mecanismos de
  assinatura completamente diferentes (JWT assinado com
  `CUSTOMER_PORTAL_JWT_SECRET`, não o OIDC do Auth0); o backend já
  rejeita/ignora um token errado no sítio errado, mas o frontend não
  deve sequer tentar.
- Layout próprio, **sem** `AppShell.tsx`/menu do backoffice. Rotas fora
  de `RequireAuth`/`AppShell` do router actual — considerar até uma
  entrada Vite/bundle separada se o deployment for um domínio/subdomínio
  próprio (roadmap não fecha isto, ver `ROADMAP_PORTAL_CLIENTE.md`
  OD-PORTAL-004: fica no mesmo backend, mas o frontend pode ser um
  build separado).

### 6.2 `{tenantId}` — de onde vem

`{tenantId}` é um UUID fixo, conhecido do **build/deployment** deste
portal (cada seguradora publica o seu portal com o seu próprio
`tenantId`, tipicamente uma env var tipo `VITE_PORTAL_TENANT_ID`) — não
é algo que o cliente final digite nem algo lido de outro lado em
runtime.

### 6.3 Fluxo de login (2 ecrãs, 2 chamadas)

**Ecrã 1 — pedir acesso:**
```
POST /api/v1/customer-portal/{tenantId}/auth/request-access
Content-Type: application/json

{ "quoteNumber": "AO-2026-000123", "registrationNumber": "123456789LA042", "email": "cliente@example.com" }
```
- Campos: `quoteNumber` (string, ≤100), `registrationNumber` (string,
  ≤100), `email` (email válido, ≤320).
- **Sempre `202 Accepted`, corpo vazio** — mesmo que os dados não
  correspondam a nada real (o backend nunca revela se uma apólice ou
  documento existe, para não dar pistas a um atacante). O ecrã **deve**
  mostrar sempre a mesma mensagem de sucesso ("Se os dados estiverem
  correctos, enviámos um código para o seu email"), com um botão
  "Avançar" que leva sempre ao Ecrã 2 — nunca inferir sucesso/falha a
  partir da resposta, porque não há diferença nenhuma na resposta.
- `429` (`code=RATE-LIMIT`) → "Demasiadas tentativas, tente novamente
  mais tarde".
- `400` (`code=VALIDATION-400`) → erro de formulário normal (campo em
  falta/malformado).

**Ecrã 2 — confirmar o código:**
```
POST /api/v1/customer-portal/{tenantId}/auth/verify-otp
Content-Type: application/json

{ "quoteNumber": "AO-2026-000123", "registrationNumber": "123456789LA042", "email": "cliente@example.com", "otp": "123456" }
```
- Repetir os mesmos 3 campos do Ecrã 1 (guardar em estado do formulário
  entre os 2 ecrãs, não pedir de novo ao utilizador) + `otp` (string,
  exactamente 6 caracteres).
- Sucesso `200`:
  ```json
  { "accessToken": "eyJ...", "tokenType": "Bearer", "expiresIn": 1800 }
  ```
- Erros:

| Status | `code` | Quando | Mensagem sugerida |
|---|---|---|---|
| `401` | `AUTH-401` | Dados/código errados ou expirados (nunca diz qual) | "Código inválido ou expirado" |
| `423` | `PORTAL-LOCKED` | 5 tentativas falhadas seguidas — bloqueado 30 min | "Conta temporariamente bloqueada, tente novamente mais tarde" |
| `429` | `RATE-LIMIT` | Demasiadas tentativas seguidas (por IP+email) | "Demasiadas tentativas, tente novamente mais tarde" |
| `400` | `VALIDATION-400` | Campos em falta/malformados (ex. OTP com menos de 6 dígitos) | erro de formulário normal |

Todos os erros usam o mesmo envelope `ProblemDetail` da secção 1.3.

### 6.4 Rate limit específico deste portal

Mais agressivo que o global: por omissão 10 pedidos/60s, chaveado por
tenant+IP+email — atinge-se rápido em testes manuais repetidos. Não
tratar um 429 aqui como bug, é o desenho (protecção contra força bruta
de número de apólice/documento).

### 6.5 Sessão

- Guardar `accessToken` em `sessionStorage` **próprio deste portal**
  (chave distinta de qualquer coisa do backoffice), com o cliente HTTP
  próprio (6.1) a anexar `Authorization: Bearer <accessToken>`.
- `expiresIn` (1800s por omissão) — **não há refresh token nesta fase**.
  Ao expirar (ou receber `401` nalgum pedido autenticado futuro),
  redireccionar para o Ecrã 1 do login (pedir um novo código), nunca
  tentar renovar silenciosamente.

### 6.6 O que NÃO construir ainda

- **Nenhum ecrã autenticado existe do lado do backend** (`GET /me` do
  portal, coberturas, elegibilidade da própria apólice — tudo isso é
  Fase 1 de `ROADMAP_PORTAL_CLIENTE.md`, ainda não implementada). Depois
  do login bem-sucedido, é aceitável ter só um ecrã "Login efectuado,
  volte em breve" ou similar — não inventar chamadas a endpoints que
  não existem.
- Não desenhar upload de documentos (certificado de matrícula,
  homologação, etc.) — isso depende de uma decisão de armazenamento
  ainda em aberto (Fase B do Motor de Elegibilidade).

### 6.7 Estrutura sugerida (não vinculativa, mas mantém o isolamento)

```
src/portal/
  api/portalHttpClient.ts       # cliente HTTP isolado, sem Auth0
  auth/
    RequestAccessPage.tsx        # Ecrã 1
    VerifyOtpPage.tsx            # Ecrã 2
    portalSession.ts             # sessionStorage próprio + helpers
  PortalRouter.tsx                # rotas próprias, fora de AppShell
```

---

## 7. Transversal (aplica-se a tudo acima)

- **Tipos gerados**: `npm run api:generate:offline` (contra
  `docs/artifacts/ART-006-openapi/...yaml`) ou `npm run api:generate`
  (contra um backend a correr em `localhost:8080`) sempre que um
  endpoint novo do backoffice mudar de forma. **O Portal do Cliente não
  está em ART-006** (contrato novo e isolado, ver
  `ROADMAP_PORTAL_CLIENTE.md`) — os seus tipos ficam manuais
  (`src/portal/api/types.ts`), não gerados.
- **Testes**: cada componente novo (mapas de decisão, ecrãs de login do
  portal, checklist de `context.angola`) precisa de pelo menos um teste
  de comportamento, seguindo o padrão já usado em `src/tests/`.
- **Sessão do backoffice**: inalterada — nada neste documento pede
  alterações à autenticação Auth0 já a funcionar.

# Inventário de endpoints — novos e alterados

Só os endpoints **novos** e os **alterados** desde o commit `1ff1e6a` (15/10/2026). Este trabalho inclui:
- a camada geral do fornecedor;
- as regras por etapa;
- as constantes e tabelas nas fórmulas;
- a tarifa por produto com simulação;
- a fila de aprovações;
- os modelos de partida.

Para cada endpoint: quem pode chamar, o que **recebe** (parâmetros e corpo) e o que **envia** (resposta de sucesso), com o tipo de cada campo.

- As secções 1 e 2 são geradas a partir do contrato (`backend/schema.yml`, OpenAPI 3.1), comparado com o do commit `1ff1e6a`.
- A secção 3 lista as alterações que o contrato não mostra: campos novos dentro de respostas sem tipo, regras e erros novos, rotas obsoletas.
- Os caminhos estão sem o prefixo `/api/v1`.
- Os erros vêm em `application/problem+json` (`code`, `detail`, `correlationId`).
- As rotas `/platform/…` usam o token da conta da plataforma; as restantes, o token do tenant.

**Resumo:** 35 endpoints novos, 5 alterados no contrato e 31 alterados no comportamento (dos quais 8 obsoletos).

| # | Método | Endpoint | operationId | Estado |
|---|---|---|---|---|
| 1 | GET | `/platform/system-parameters` | getPlatformParameterList | Novo |
| 2 | GET | `/platform/system-parameters/{code}` | getPlatformParameterDetail | Novo |
| 3 | POST | `/platform/system-parameters/{code}/rollback` | postPlatformParameterRollback | Novo |
| 4 | GET | `/platform/system-parameters/{code}/versions` | getPlatformParameterVersions | Novo |
| 5 | POST | `/platform/system-parameters/{code}/versions` | postPlatformParameterVersions | Novo |
| 6 | POST | `/platform/system-parameters/{code}/versions/{version_no}/approve` | postPlatformParameterApprove | Novo |
| 7 | POST | `/platform/system-parameters/{code}/versions/{version_no}/reject` | postPlatformParameterReject | Novo |
| 8 | GET | `/platform/reference-tables` | getPlatformReferenceTableList | Novo |
| 9 | POST | `/platform/reference-tables` | postPlatformReferenceTableList | Novo |
| 10 | GET | `/platform/reference-tables/{code}` | getPlatformReferenceTableDetail | Novo |
| 11 | GET | `/platform/reference-tables/{code}/versions` | getPlatformReferenceTableVersions | Novo |
| 12 | POST | `/platform/reference-tables/{code}/versions/{version_no}/approve` | postPlatformReferenceTableApprove | Novo |
| 13 | POST | `/platform/reference-tables/{code}/versions/{version_no}/reject` | postPlatformReferenceTableReject | Novo |
| 14 | GET | `/platform/templates` | getPlatformTemplateList | Novo |
| 15 | POST | `/platform/templates` | postPlatformTemplateList | Novo |
| 16 | GET | `/platform/templates/{code}` | getPlatformTemplateDetail | Novo |
| 17 | GET | `/platform/templates/{code}/versions` | getPlatformTemplateVersions | Novo |
| 18 | POST | `/platform/templates/{code}/versions/{version_no}/approve` | postPlatformTemplateApprove | Novo |
| 19 | POST | `/platform/templates/{code}/versions/{version_no}/reject` | postPlatformTemplateReject | Novo |
| 20 | GET | `/platform/formula-engine` | getPlatformFormulaEngine | Novo |
| 21 | GET | `/reference-tables` | getReferenceTableList | Novo |
| 22 | GET | `/reference-tables/{code}` | getReferenceTableDetail | Novo |
| 23 | GET | `/templates` | listTemplates | Novo |
| 24 | GET | `/templates/{code}` | getTemplate | Novo |
| 25 | POST | `/templates/{code}/adopt` | adoptTemplate | Novo |
| 26 | GET | `/products/{product_id}/tariff` | getProductTariff | Novo |
| 27 | POST | `/products/{product_id}/tariff/simulate` | simulateProductTariff | Novo |
| 28 | GET | `/business-config/formulas/variables` | getFormulaVariables | Novo |
| 29 | GET | `/business-config/approvals/pending` | listPendingApprovals | Novo |
| 30 | GET | `/business-config/approvals/pending/count` | countPendingApprovals | Novo |
| 31 | POST | `/business-config/formulas/test` | testPricingFormula | Alterado (contrato) |
| 32 | GET | `/system-parameters` | getSystemParameterList | Alterado (contrato) |
| 33 | GET | `/system-parameters/{code}` | getSystemParameterDetail | Alterado (contrato) |
| 34 | PUT | `/system-parameters/{code}` | putSystemParameterDetail | Alterado (contrato) |
| 35 | POST | `/system-parameters/{code}/rollback` | postSystemParameterRollback | Alterado (contrato) |
| 36 | GET | `/business-config/catalog` | getBusinessConfigurationCatalog | Alterado (comportamento) |
| 37 | POST | `/business-config/configurations` | createBusinessConfiguration | Alterado (comportamento) |
| 38 | PUT | `/business-config/configurations/{configuration_id}` | updateBusinessConfiguration | Alterado (comportamento) |
| 39 | POST | `/business-config/configurations/{configuration_id}` | changeBusinessConfigurationStatus | Alterado (comportamento) |
| 40 | POST | `/business-config/configurations/{configuration_id}/approve` | approveBusinessConfiguration | Alterado (comportamento) |
| 41 | POST | `/business-config/formulas/{configuration_id}/simulate` | simulateFormulaSet | Alterado (comportamento) |
| 42 | GET | `/business-config/formulas/catalog` | getFormulaCatalog | Alterado (comportamento) |
| 43 | PUT | `/products/{product_id}/pricing-setup` | saveProductPricingSetupDraft | Alterado (comportamento) |
| 44 | POST | `/products/{product_id}/pricing-setup/validate` | validateProductPricingSetup | Alterado (comportamento) |
| 45 | POST | `/products/{product_id}/pricing-setup/test` | testProductPricingSetup | Alterado (comportamento) |
| 46 | GET | `/quotes/{quote_id}/requirements` | getQuoteRequirements | Alterado (comportamento) |
| 47 | POST | `/quotes/{quote_id}/submit` | postQuoteSubmit | Alterado (comportamento) |
| 48 | POST | `/quotes/{quote_id}/decision` | postQuoteDecision | Alterado (comportamento) |
| 49 | POST | `/eligibility/evaluate` | postEligibilityEvaluate | Alterado (comportamento) |
| 50 | POST | `/configuration/{config_type}/{config_id}/publish` | postConfigurationPublish | Alterado (comportamento) |
| 51 | POST | `/quotes/{quote_id}/price` | postQuotePrice | Alterado (comportamento) |
| 52 | POST | `/quotes/{quote_id}/preview` | postQuotePreview | Alterado (comportamento) |
| 53 | POST | `/pricing/calculate` | postPricingCalculate | Alterado (comportamento) |
| 54 | POST | `/pricing/preview` | postPricingPreview | Alterado (comportamento) |
| 55 | GET | `/pricing/{pricing_run_id}/explanation` | getPricingExplanation | Alterado (comportamento) |
| 56 | GET | `/rating-tables` | getRatingTableCreate | Obsoleto |
| 57 | POST | `/rating-tables` | postRatingTableCreate | Obsoleto |
| 58 | PATCH | `/rating-tables/{rating_table_id}` | patchRatingTableDetail | Obsoleto |
| 59 | DELETE | `/rating-tables/{rating_table_id}` | deleteRatingTableDetail | Obsoleto |
| 60 | GET | `/pricing-parameter-sets` | getPricingParameterSetCreate | Obsoleto |
| 61 | POST | `/pricing-parameter-sets` | postPricingParameterSetCreate | Obsoleto |
| 62 | PATCH | `/pricing-parameter-sets/{parameter_set_id}` | patchPricingParameterSetDetail | Obsoleto |
| 63 | DELETE | `/pricing-parameter-sets/{parameter_set_id}` | deletePricingParameterSetDetail | Obsoleto |
| 64 | GET | `/claims/experience-rating` | getClaimsExperienceRating | Novo |
| 65 | POST | `/customer-portal/requests/{request_number}/satisfaction` | postCustomerPortalRequestSatisfaction | Novo |
| 66 | GET | `/portal-requests/metrics` | getPortalRequestMetrics | Novo |
| 67 | GET | `/quote-discount-approvals` | getQuoteDiscountApprovalQueue | Novo |
| 68 | POST | `/quote-discount-approvals/{approval_id}/decision` | postQuoteDiscountApprovalDecision | Novo |
| 69 | POST | `/quotes/{quote_id}/adjustments` | postQuoteAdjustmentListCreate | Alterado (comportamento) |
| 70 | GET | `/quotes/{quote_id}/scenarios/compare` | getQuoteScenarioCompare | Alterado (resposta inclui margem) |
| 71 | GET | `/portal-requests` | getPortalRequestList | Alterado (resposta inclui métricas SLA) |

## 1. Endpoints novos

## 1.1 Fornecedor — parâmetros gerais

### `GET /platform/system-parameters`

**Novo** · `getPlatformParameterList` · Listar platform parameter list

- **Quem pode:** conta da plataforma (super administrador, token `platform`).
- **Parâmetros de pesquisa:** `category` (texto) — OPERATIONAL, STRUCTURAL, LEGAL, LIMIT ou MARKET.; `level` (texto) — PLATFORM_MANDATORY ou PLATFORM_DEFAULT.

**Recebe:** nada (sem corpo).

**Envia** (200, `application/json`, lista de `PlatformParameter`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `[].code` | texto | sim |  |
| `[].valueType` | texto (INTEGER · DECIMAL · TEXT · BOOLEAN) | sim |  |
| `[].category` | texto (OPERATIONAL · STRUCTURAL · LEGAL · LIMIT · MARKET) | sim |  |
| `[].level` | texto (PLATFORM_MANDATORY · PLATFORM_DEFAULT) | sim |  |
| `[].value` | qualquer ou null | sim | Valor geral em vigor. |
| `[].codeDefault` | qualquer ou null | sim |  |
| `[].isCodeDefault` | booleano | sim |  |
| `[].versionNo` | inteiro | sim |  |
| `[].effectiveFrom` | texto (data e hora) ou null | sim |  |
| `[].legalReference` | texto ou null | sim | Fonte da versão em vigor. |
| `[].sourceUrl` | texto ou null | sim |  |
| `[].requiresLegalReference` | booleano | sim | true nos parâmetros LEGAL: propor exige legalReference. |
| `[].description` | texto | sim |  |
| `[].unit` | texto ou null | sim |  |
| `[].usedBy` | texto ou null | sim |  |
| `[].hardLimits` | mapa de qualquer ou null | sim |  |
| `[].tenantLimits` | mapa de qualquer ou null ou null | sim |  |
| `[].allowedValues` | lista de qualquer ou null | sim | Valores que o motor sabe executar. |
| `[].tenantEditable` | booleano | sim |  |
| `[].pendingVersions` | lista de objeto `PlatformParameterVersion` | sim |  |
| `[].pendingVersions[].code` | texto | sim |  |
| `[].pendingVersions[].versionNo` | inteiro | sim |  |
| `[].pendingVersions[].status` | texto (PENDING_APPROVAL · PUBLISHED · REJECTED) | sim |  |
| `[].pendingVersions[].action` | texto | sim | CREATED ou ROLLBACK_TO_<n>. |
| `[].pendingVersions[].value` | qualquer ou null | sim |  |
| `[].pendingVersions[].minimum` | qualquer ou null | sim | Limite mínimo imposto aos tenants (só PLATFORM_DEFAULT). |
| `[].pendingVersions[].maximum` | qualquer ou null | sim | Limite máximo imposto aos tenants (só PLATFORM_DEFAULT). |
| `[].pendingVersions[].effectiveFrom` | texto (data e hora) ou null | sim |  |
| `[].pendingVersions[].inEffect` | booleano | sim |  |
| `[].pendingVersions[].reason` | texto | sim |  |
| `[].pendingVersions[].legalReference` | texto ou null | sim | Fonte legal (parâmetros LEGAL). |
| `[].pendingVersions[].sourceUrl` | texto ou null | sim |  |
| `[].pendingVersions[].createdBy` | texto | sim |  |
| `[].pendingVersions[].createdAt` | texto (data e hora) ou null | sim |  |
| `[].pendingVersions[].decidedBy` | texto ou null | sim |  |
| `[].pendingVersions[].decidedAt` | texto (data e hora) ou null | sim |  |
| `[].pendingVersions[].decisionNote` | texto ou null | sim |  |
| `[].tenantOverrides` | mapa de inteiro | não | count, outOfLimits. |

**Erros:** 400, 401, 403.

### `GET /platform/system-parameters/{code}`

**Novo** · `getPlatformParameterDetail` · Obter platform parameter detail

- **Quem pode:** conta da plataforma (super administrador, token `platform`).
- **Parâmetros no caminho:** `code` (texto)

**Recebe:** nada (sem corpo).

**Envia** (200, `application/json`, `PlatformParameter`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `code` | texto | sim |  |
| `valueType` | texto (INTEGER · DECIMAL · TEXT · BOOLEAN) | sim |  |
| `category` | texto (OPERATIONAL · STRUCTURAL · LEGAL · LIMIT · MARKET) | sim |  |
| `level` | texto (PLATFORM_MANDATORY · PLATFORM_DEFAULT) | sim |  |
| `value` | qualquer ou null | sim | Valor geral em vigor. |
| `codeDefault` | qualquer ou null | sim |  |
| `isCodeDefault` | booleano | sim |  |
| `versionNo` | inteiro | sim |  |
| `effectiveFrom` | texto (data e hora) ou null | sim |  |
| `legalReference` | texto ou null | sim | Fonte da versão em vigor. |
| `sourceUrl` | texto ou null | sim |  |
| `requiresLegalReference` | booleano | sim | true nos parâmetros LEGAL: propor exige legalReference. |
| `description` | texto | sim |  |
| `unit` | texto ou null | sim |  |
| `usedBy` | texto ou null | sim |  |
| `hardLimits` | mapa de qualquer ou null | sim |  |
| `tenantLimits` | mapa de qualquer ou null ou null | sim |  |
| `allowedValues` | lista de qualquer ou null | sim | Valores que o motor sabe executar. |
| `tenantEditable` | booleano | sim |  |
| `pendingVersions` | lista de objeto `PlatformParameterVersion` | sim |  |
| `pendingVersions[].code` | texto | sim |  |
| `pendingVersions[].versionNo` | inteiro | sim |  |
| `pendingVersions[].status` | texto (PENDING_APPROVAL · PUBLISHED · REJECTED) | sim |  |
| `pendingVersions[].action` | texto | sim | CREATED ou ROLLBACK_TO_<n>. |
| `pendingVersions[].value` | qualquer ou null | sim |  |
| `pendingVersions[].minimum` | qualquer ou null | sim | Limite mínimo imposto aos tenants (só PLATFORM_DEFAULT). |
| `pendingVersions[].maximum` | qualquer ou null | sim | Limite máximo imposto aos tenants (só PLATFORM_DEFAULT). |
| `pendingVersions[].effectiveFrom` | texto (data e hora) ou null | sim |  |
| `pendingVersions[].inEffect` | booleano | sim |  |
| `pendingVersions[].reason` | texto | sim |  |
| `pendingVersions[].legalReference` | texto ou null | sim | Fonte legal (parâmetros LEGAL). |
| `pendingVersions[].sourceUrl` | texto ou null | sim |  |
| `pendingVersions[].createdBy` | texto | sim |  |
| `pendingVersions[].createdAt` | texto (data e hora) ou null | sim |  |
| `pendingVersions[].decidedBy` | texto ou null | sim |  |
| `pendingVersions[].decidedAt` | texto (data e hora) ou null | sim |  |
| `pendingVersions[].decisionNote` | texto ou null | sim |  |
| `tenantOverrides` | mapa de inteiro | não | count, outOfLimits. |

**Erros:** 401, 403, 404.

### `POST /platform/system-parameters/{code}/rollback`

**Novo** · `postPlatformParameterRollback` · Criar platform parameter rollback

- **Quem pode:** conta da plataforma (super administrador, token `platform`).
- **Parâmetros no caminho:** `code` (texto)
- **Cabeçalho:** `Idempotency-Key` obrigatório.

**Recebe** (`application/json`, `PlatformParameterRollbackRequest`):

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `versionNo` | inteiro | sim |  |
| `reason` | texto | sim | Motivo obrigatório (mínimo 10 caracteres). |

**Envia** (201, `application/json`, `PlatformParameterVersion`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `code` | texto | sim |  |
| `versionNo` | inteiro | sim |  |
| `status` | texto (PENDING_APPROVAL · PUBLISHED · REJECTED) | sim |  |
| `action` | texto | sim | CREATED ou ROLLBACK_TO_<n>. |
| `value` | qualquer ou null | sim |  |
| `minimum` | qualquer ou null | sim | Limite mínimo imposto aos tenants (só PLATFORM_DEFAULT). |
| `maximum` | qualquer ou null | sim | Limite máximo imposto aos tenants (só PLATFORM_DEFAULT). |
| `effectiveFrom` | texto (data e hora) ou null | sim |  |
| `inEffect` | booleano | sim |  |
| `reason` | texto | sim |  |
| `legalReference` | texto ou null | sim | Fonte legal (parâmetros LEGAL). |
| `sourceUrl` | texto ou null | sim |  |
| `createdBy` | texto | sim |  |
| `createdAt` | texto (data e hora) ou null | sim |  |
| `decidedBy` | texto ou null | sim |  |
| `decidedAt` | texto (data e hora) ou null | sim |  |
| `decisionNote` | texto ou null | sim |  |

**Erros:** 400, 401, 403, 404, 409.

### `GET /platform/system-parameters/{code}/versions`

**Novo** · `getPlatformParameterVersions` · Obter platform parameter versions

- **Quem pode:** conta da plataforma (super administrador, token `platform`).
- **Parâmetros no caminho:** `code` (texto)

**Recebe:** nada (sem corpo).

**Envia** (200, `application/json`, lista de `PlatformParameterVersion`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `[].code` | texto | sim |  |
| `[].versionNo` | inteiro | sim |  |
| `[].status` | texto (PENDING_APPROVAL · PUBLISHED · REJECTED) | sim |  |
| `[].action` | texto | sim | CREATED ou ROLLBACK_TO_<n>. |
| `[].value` | qualquer ou null | sim |  |
| `[].minimum` | qualquer ou null | sim | Limite mínimo imposto aos tenants (só PLATFORM_DEFAULT). |
| `[].maximum` | qualquer ou null | sim | Limite máximo imposto aos tenants (só PLATFORM_DEFAULT). |
| `[].effectiveFrom` | texto (data e hora) ou null | sim |  |
| `[].inEffect` | booleano | sim |  |
| `[].reason` | texto | sim |  |
| `[].legalReference` | texto ou null | sim | Fonte legal (parâmetros LEGAL). |
| `[].sourceUrl` | texto ou null | sim |  |
| `[].createdBy` | texto | sim |  |
| `[].createdAt` | texto (data e hora) ou null | sim |  |
| `[].decidedBy` | texto ou null | sim |  |
| `[].decidedAt` | texto (data e hora) ou null | sim |  |
| `[].decisionNote` | texto ou null | sim |  |

**Erros:** 401, 403, 404.

### `POST /platform/system-parameters/{code}/versions`

**Novo** · `postPlatformParameterVersions` · Criar platform parameter versions

- **Quem pode:** conta da plataforma (super administrador, token `platform`).
- **Parâmetros no caminho:** `code` (texto)
- **Cabeçalho:** `Idempotency-Key` obrigatório.

**Recebe** (`application/json`, `PlatformParameterProposalWithSource`):

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `value` | qualquer | sim |  |
| `minimum` | qualquer ou null | não |  |
| `maximum` | qualquer ou null | não |  |
| `effectiveFrom` | texto (data e hora) ou null | não | Vigência; por omissão, a aprovação. |
| `reason` | texto | sim | Motivo obrigatório (mínimo 10 caracteres). |
| `legalReference` | texto ou null | não | Fonte legal (diploma, artigo). Obrigatória nos parâmetros LEGAL. |
| `sourceUrl` | texto ou null | não | Ligação https para o texto da fonte. |

**Envia** (201, `application/json`, `PlatformParameterVersion`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `code` | texto | sim |  |
| `versionNo` | inteiro | sim |  |
| `status` | texto (PENDING_APPROVAL · PUBLISHED · REJECTED) | sim |  |
| `action` | texto | sim | CREATED ou ROLLBACK_TO_<n>. |
| `value` | qualquer ou null | sim |  |
| `minimum` | qualquer ou null | sim | Limite mínimo imposto aos tenants (só PLATFORM_DEFAULT). |
| `maximum` | qualquer ou null | sim | Limite máximo imposto aos tenants (só PLATFORM_DEFAULT). |
| `effectiveFrom` | texto (data e hora) ou null | sim |  |
| `inEffect` | booleano | sim |  |
| `reason` | texto | sim |  |
| `legalReference` | texto ou null | sim | Fonte legal (parâmetros LEGAL). |
| `sourceUrl` | texto ou null | sim |  |
| `createdBy` | texto | sim |  |
| `createdAt` | texto (data e hora) ou null | sim |  |
| `decidedBy` | texto ou null | sim |  |
| `decidedAt` | texto (data e hora) ou null | sim |  |
| `decisionNote` | texto ou null | sim |  |

**Erros:** 400, 401, 403, 404, 409.

### `POST /platform/system-parameters/{code}/versions/{version_no}/approve`

**Novo** · `postPlatformParameterApprove` · Criar platform parameter approve

- **Quem pode:** conta da plataforma (super administrador, token `platform`).
- **Parâmetros no caminho:** `code` (texto), `version_no` (inteiro)
- **Cabeçalho:** `Idempotency-Key` obrigatório.

**Recebe** (`application/json`, `PlatformParameterDecision`):

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `note` | texto ou null | não | Obrigatória (mínimo 10 caracteres) ao rejeitar. |

**Envia** (200, `application/json`, `PlatformParameterVersion`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `code` | texto | sim |  |
| `versionNo` | inteiro | sim |  |
| `status` | texto (PENDING_APPROVAL · PUBLISHED · REJECTED) | sim |  |
| `action` | texto | sim | CREATED ou ROLLBACK_TO_<n>. |
| `value` | qualquer ou null | sim |  |
| `minimum` | qualquer ou null | sim | Limite mínimo imposto aos tenants (só PLATFORM_DEFAULT). |
| `maximum` | qualquer ou null | sim | Limite máximo imposto aos tenants (só PLATFORM_DEFAULT). |
| `effectiveFrom` | texto (data e hora) ou null | sim |  |
| `inEffect` | booleano | sim |  |
| `reason` | texto | sim |  |
| `legalReference` | texto ou null | sim | Fonte legal (parâmetros LEGAL). |
| `sourceUrl` | texto ou null | sim |  |
| `createdBy` | texto | sim |  |
| `createdAt` | texto (data e hora) ou null | sim |  |
| `decidedBy` | texto ou null | sim |  |
| `decidedAt` | texto (data e hora) ou null | sim |  |
| `decisionNote` | texto ou null | sim |  |

**Erros:** 400, 401, 403, 404, 409.

### `POST /platform/system-parameters/{code}/versions/{version_no}/reject`

**Novo** · `postPlatformParameterReject` · Criar platform parameter reject

- **Quem pode:** conta da plataforma (super administrador, token `platform`).
- **Parâmetros no caminho:** `code` (texto), `version_no` (inteiro)
- **Cabeçalho:** `Idempotency-Key` obrigatório.

**Recebe** (`application/json`, `PlatformParameterDecision`):

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `note` | texto ou null | não | Obrigatória (mínimo 10 caracteres) ao rejeitar. |

**Envia** (200, `application/json`, `PlatformParameterVersion`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `code` | texto | sim |  |
| `versionNo` | inteiro | sim |  |
| `status` | texto (PENDING_APPROVAL · PUBLISHED · REJECTED) | sim |  |
| `action` | texto | sim | CREATED ou ROLLBACK_TO_<n>. |
| `value` | qualquer ou null | sim |  |
| `minimum` | qualquer ou null | sim | Limite mínimo imposto aos tenants (só PLATFORM_DEFAULT). |
| `maximum` | qualquer ou null | sim | Limite máximo imposto aos tenants (só PLATFORM_DEFAULT). |
| `effectiveFrom` | texto (data e hora) ou null | sim |  |
| `inEffect` | booleano | sim |  |
| `reason` | texto | sim |  |
| `legalReference` | texto ou null | sim | Fonte legal (parâmetros LEGAL). |
| `sourceUrl` | texto ou null | sim |  |
| `createdBy` | texto | sim |  |
| `createdAt` | texto (data e hora) ou null | sim |  |
| `decidedBy` | texto ou null | sim |  |
| `decidedAt` | texto (data e hora) ou null | sim |  |
| `decisionNote` | texto ou null | sim |  |

**Erros:** 400, 401, 403, 404, 409.

## 1.2 Fornecedor — tabelas de referência

### `GET /platform/reference-tables`

**Novo** · `getPlatformReferenceTableList` · Listar platform reference table list

- **Quem pode:** conta da plataforma (super administrador, token `platform`).

**Recebe:** nada (sem corpo).

**Envia** (200, `application/json`, lista de `ReferenceTableSummary`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `[].code` | texto | sim |  |
| `[].name` | texto | sim |  |
| `[].inEffect` | objeto `ReferenceTableVersion` ou null | sim |  |
| `[].inEffect.code` | texto | sim |  |
| `[].inEffect.versionNo` | inteiro | sim |  |
| `[].inEffect.status` | texto (PENDING_APPROVAL · PUBLISHED · REJECTED) | sim |  |
| `[].inEffect.name` | texto | sim |  |
| `[].inEffect.description` | texto ou null | sim |  |
| `[].inEffect.keyColumn` | texto | sim |  |
| `[].inEffect.columns` | lista de objeto `ReferenceTableColumn` | sim |  |
| `[].inEffect.rowCount` | inteiro | sim |  |
| `[].inEffect.rows` | lista de objeto | não | Só no detalhe. |
| `[].inEffect.source` | texto ou null | sim |  |
| `[].inEffect.effectiveFrom` | texto (data e hora) ou null | sim |  |
| `[].inEffect.inEffect` | booleano | sim |  |
| `[].inEffect.reason` | texto | sim |  |
| `[].inEffect.createdBy` | texto | sim |  |
| `[].inEffect.createdAt` | texto (data e hora) ou null | sim |  |
| `[].inEffect.decidedBy` | texto ou null | sim |  |
| `[].inEffect.decidedAt` | texto (data e hora) ou null | sim |  |
| `[].inEffect.decisionNote` | texto ou null | sim |  |
| `[].pendingVersions` | lista de objeto `ReferenceTableVersion` | sim |  |
| `[].pendingVersions[].code` | texto | sim |  |
| `[].pendingVersions[].versionNo` | inteiro | sim |  |
| `[].pendingVersions[].status` | texto (PENDING_APPROVAL · PUBLISHED · REJECTED) | sim |  |
| `[].pendingVersions[].name` | texto | sim |  |
| `[].pendingVersions[].description` | texto ou null | sim |  |
| `[].pendingVersions[].keyColumn` | texto | sim |  |
| `[].pendingVersions[].columns` | lista de objeto `ReferenceTableColumn` | sim |  |
| `[].pendingVersions[].rowCount` | inteiro | sim |  |
| `[].pendingVersions[].rows` | lista de objeto | não | Só no detalhe. |
| `[].pendingVersions[].source` | texto ou null | sim |  |
| `[].pendingVersions[].effectiveFrom` | texto (data e hora) ou null | sim |  |
| `[].pendingVersions[].inEffect` | booleano | sim |  |
| `[].pendingVersions[].reason` | texto | sim |  |
| `[].pendingVersions[].createdBy` | texto | sim |  |
| `[].pendingVersions[].createdAt` | texto (data e hora) ou null | sim |  |
| `[].pendingVersions[].decidedBy` | texto ou null | sim |  |
| `[].pendingVersions[].decidedAt` | texto (data e hora) ou null | sim |  |
| `[].pendingVersions[].decisionNote` | texto ou null | sim |  |

**Erros:** 401, 403.

### `POST /platform/reference-tables`

**Novo** · `postPlatformReferenceTableList` · Criar platform reference table list

- **Quem pode:** conta da plataforma (super administrador, token `platform`).
- **Cabeçalho:** `Idempotency-Key` obrigatório.

**Recebe** (`application/json`, `ReferenceTableProposal`):

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `code` | texto | sim | Minúsculas, números e '_' (ex.: provincias). |
| `name` | texto | sim |  |
| `description` | texto ou null | não |  |
| `keyColumn` | texto | sim |  |
| `columns` | lista de objeto `ReferenceTableColumn` | sim |  |
| `columns[].code` | texto | sim |  |
| `columns[].label` | texto | não |  |
| `columns[].type` | texto (NUMBER · TEXT) | sim |  |
| `rows` | lista de objeto | sim | Até 5000 linhas; chaves únicas. |
| `source` | texto ou null | não |  |
| `effectiveFrom` | texto (data e hora) ou null | não |  |
| `reason` | texto | sim | Motivo obrigatório (mínimo 10 caracteres). |

**Envia** (201, `application/json`, `ReferenceTableVersion`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `code` | texto | sim |  |
| `versionNo` | inteiro | sim |  |
| `status` | texto (PENDING_APPROVAL · PUBLISHED · REJECTED) | sim |  |
| `name` | texto | sim |  |
| `description` | texto ou null | sim |  |
| `keyColumn` | texto | sim |  |
| `columns` | lista de objeto `ReferenceTableColumn` | sim |  |
| `columns[].code` | texto | sim |  |
| `columns[].label` | texto | não |  |
| `columns[].type` | texto (NUMBER · TEXT) | sim |  |
| `rowCount` | inteiro | sim |  |
| `rows` | lista de objeto | não | Só no detalhe. |
| `source` | texto ou null | sim |  |
| `effectiveFrom` | texto (data e hora) ou null | sim |  |
| `inEffect` | booleano | sim |  |
| `reason` | texto | sim |  |
| `createdBy` | texto | sim |  |
| `createdAt` | texto (data e hora) ou null | sim |  |
| `decidedBy` | texto ou null | sim |  |
| `decidedAt` | texto (data e hora) ou null | sim |  |
| `decisionNote` | texto ou null | sim |  |

**Erros:** 400, 401, 403, 409.

### `GET /platform/reference-tables/{code}`

**Novo** · `getPlatformReferenceTableDetail` · Obter platform reference table detail

- **Quem pode:** conta da plataforma (super administrador, token `platform`).
- **Parâmetros no caminho:** `code` (texto)

**Recebe:** nada (sem corpo).

**Envia** (200, `application/json`, `ReferenceTableDetail`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `code` | texto | sim |  |
| `inEffect` | objeto `ReferenceTableVersion` ou null | sim | Com as linhas. |
| `inEffect.code` | texto | sim |  |
| `inEffect.versionNo` | inteiro | sim |  |
| `inEffect.status` | texto (PENDING_APPROVAL · PUBLISHED · REJECTED) | sim |  |
| `inEffect.name` | texto | sim |  |
| `inEffect.description` | texto ou null | sim |  |
| `inEffect.keyColumn` | texto | sim |  |
| `inEffect.columns` | lista de objeto `ReferenceTableColumn` | sim |  |
| `inEffect.rowCount` | inteiro | sim |  |
| `inEffect.rows` | lista de objeto | não | Só no detalhe. |
| `inEffect.source` | texto ou null | sim |  |
| `inEffect.effectiveFrom` | texto (data e hora) ou null | sim |  |
| `inEffect.inEffect` | booleano | sim |  |
| `inEffect.reason` | texto | sim |  |
| `inEffect.createdBy` | texto | sim |  |
| `inEffect.createdAt` | texto (data e hora) ou null | sim |  |
| `inEffect.decidedBy` | texto ou null | sim |  |
| `inEffect.decidedAt` | texto (data e hora) ou null | sim |  |
| `inEffect.decisionNote` | texto ou null | sim |  |
| `pendingVersions` | lista de objeto `ReferenceTableVersion` | sim |  |
| `pendingVersions[].code` | texto | sim |  |
| `pendingVersions[].versionNo` | inteiro | sim |  |
| `pendingVersions[].status` | texto (PENDING_APPROVAL · PUBLISHED · REJECTED) | sim |  |
| `pendingVersions[].name` | texto | sim |  |
| `pendingVersions[].description` | texto ou null | sim |  |
| `pendingVersions[].keyColumn` | texto | sim |  |
| `pendingVersions[].columns` | lista de objeto `ReferenceTableColumn` | sim |  |
| `pendingVersions[].rowCount` | inteiro | sim |  |
| `pendingVersions[].rows` | lista de objeto | não | Só no detalhe. |
| `pendingVersions[].source` | texto ou null | sim |  |
| `pendingVersions[].effectiveFrom` | texto (data e hora) ou null | sim |  |
| `pendingVersions[].inEffect` | booleano | sim |  |
| `pendingVersions[].reason` | texto | sim |  |
| `pendingVersions[].createdBy` | texto | sim |  |
| `pendingVersions[].createdAt` | texto (data e hora) ou null | sim |  |
| `pendingVersions[].decidedBy` | texto ou null | sim |  |
| `pendingVersions[].decidedAt` | texto (data e hora) ou null | sim |  |
| `pendingVersions[].decisionNote` | texto ou null | sim |  |

**Erros:** 401, 403, 404.

### `GET /platform/reference-tables/{code}/versions`

**Novo** · `getPlatformReferenceTableVersions` · Obter platform reference table versions

- **Quem pode:** conta da plataforma (super administrador, token `platform`).
- **Parâmetros no caminho:** `code` (texto)

**Recebe:** nada (sem corpo).

**Envia** (200, `application/json`, lista de `ReferenceTableVersion`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `[].code` | texto | sim |  |
| `[].versionNo` | inteiro | sim |  |
| `[].status` | texto (PENDING_APPROVAL · PUBLISHED · REJECTED) | sim |  |
| `[].name` | texto | sim |  |
| `[].description` | texto ou null | sim |  |
| `[].keyColumn` | texto | sim |  |
| `[].columns` | lista de objeto `ReferenceTableColumn` | sim |  |
| `[].columns[].code` | texto | sim |  |
| `[].columns[].label` | texto | não |  |
| `[].columns[].type` | texto (NUMBER · TEXT) | sim |  |
| `[].rowCount` | inteiro | sim |  |
| `[].rows` | lista de objeto | não | Só no detalhe. |
| `[].source` | texto ou null | sim |  |
| `[].effectiveFrom` | texto (data e hora) ou null | sim |  |
| `[].inEffect` | booleano | sim |  |
| `[].reason` | texto | sim |  |
| `[].createdBy` | texto | sim |  |
| `[].createdAt` | texto (data e hora) ou null | sim |  |
| `[].decidedBy` | texto ou null | sim |  |
| `[].decidedAt` | texto (data e hora) ou null | sim |  |
| `[].decisionNote` | texto ou null | sim |  |

**Erros:** 401, 403, 404.

### `POST /platform/reference-tables/{code}/versions/{version_no}/approve`

**Novo** · `postPlatformReferenceTableApprove` · Criar platform reference table approve

- **Quem pode:** conta da plataforma (super administrador, token `platform`).
- **Parâmetros no caminho:** `code` (texto), `version_no` (inteiro)
- **Cabeçalho:** `Idempotency-Key` obrigatório.

**Recebe** (`application/json`, `PlatformParameterDecision`):

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `note` | texto ou null | não | Obrigatória (mínimo 10 caracteres) ao rejeitar. |

**Envia** (200, `application/json`, `ReferenceTableVersion`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `code` | texto | sim |  |
| `versionNo` | inteiro | sim |  |
| `status` | texto (PENDING_APPROVAL · PUBLISHED · REJECTED) | sim |  |
| `name` | texto | sim |  |
| `description` | texto ou null | sim |  |
| `keyColumn` | texto | sim |  |
| `columns` | lista de objeto `ReferenceTableColumn` | sim |  |
| `columns[].code` | texto | sim |  |
| `columns[].label` | texto | não |  |
| `columns[].type` | texto (NUMBER · TEXT) | sim |  |
| `rowCount` | inteiro | sim |  |
| `rows` | lista de objeto | não | Só no detalhe. |
| `source` | texto ou null | sim |  |
| `effectiveFrom` | texto (data e hora) ou null | sim |  |
| `inEffect` | booleano | sim |  |
| `reason` | texto | sim |  |
| `createdBy` | texto | sim |  |
| `createdAt` | texto (data e hora) ou null | sim |  |
| `decidedBy` | texto ou null | sim |  |
| `decidedAt` | texto (data e hora) ou null | sim |  |
| `decisionNote` | texto ou null | sim |  |

**Erros:** 400, 401, 403, 404, 409.

### `POST /platform/reference-tables/{code}/versions/{version_no}/reject`

**Novo** · `postPlatformReferenceTableReject` · Criar platform reference table reject

- **Quem pode:** conta da plataforma (super administrador, token `platform`).
- **Parâmetros no caminho:** `code` (texto), `version_no` (inteiro)
- **Cabeçalho:** `Idempotency-Key` obrigatório.

**Recebe** (`application/json`, `PlatformParameterDecision`):

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `note` | texto ou null | não | Obrigatória (mínimo 10 caracteres) ao rejeitar. |

**Envia** (200, `application/json`, `ReferenceTableVersion`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `code` | texto | sim |  |
| `versionNo` | inteiro | sim |  |
| `status` | texto (PENDING_APPROVAL · PUBLISHED · REJECTED) | sim |  |
| `name` | texto | sim |  |
| `description` | texto ou null | sim |  |
| `keyColumn` | texto | sim |  |
| `columns` | lista de objeto `ReferenceTableColumn` | sim |  |
| `columns[].code` | texto | sim |  |
| `columns[].label` | texto | não |  |
| `columns[].type` | texto (NUMBER · TEXT) | sim |  |
| `rowCount` | inteiro | sim |  |
| `rows` | lista de objeto | não | Só no detalhe. |
| `source` | texto ou null | sim |  |
| `effectiveFrom` | texto (data e hora) ou null | sim |  |
| `inEffect` | booleano | sim |  |
| `reason` | texto | sim |  |
| `createdBy` | texto | sim |  |
| `createdAt` | texto (data e hora) ou null | sim |  |
| `decidedBy` | texto ou null | sim |  |
| `decidedAt` | texto (data e hora) ou null | sim |  |
| `decisionNote` | texto ou null | sim |  |

**Erros:** 400, 401, 403, 404, 409.

## 1.3 Fornecedor — modelos de partida

### `GET /platform/templates`

**Novo** · `getPlatformTemplateList` · Listar platform template list

- **Quem pode:** conta da plataforma (super administrador, token `platform`).

**Recebe:** nada (sem corpo).

**Envia** (200, `application/json`, lista de `TemplateSummary`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `[].code` | texto | sim |  |
| `[].name` | texto | sim |  |
| `[].kind` | texto | sim |  |
| `[].published` | objeto `TemplateVersion` ou null | sim |  |
| `[].published.code` | texto | sim |  |
| `[].published.versionNo` | inteiro | sim |  |
| `[].published.status` | texto (PENDING_APPROVAL · PUBLISHED · REJECTED) | sim |  |
| `[].published.kind` | texto (PRODUCT · ACTUARIAL_MODEL · FORMULA_SET · COVERAGE_LIBRARY) | sim |  |
| `[].published.kindLabel` | texto | sim |  |
| `[].published.name` | texto | sim |  |
| `[].published.description` | texto ou null | sim |  |
| `[].published.segment` | texto ou null | sim |  |
| `[].published.configKeys` | lista de texto | sim |  |
| `[].published.marketProducts` | booleano | sim |  |
| `[].published.content` | objeto | não | configurations {configKey: valor} e marketProducts (só no detalhe). |
| `[].published.source` | texto ou null | sim |  |
| `[].published.isLatestPublished` | booleano | sim |  |
| `[].published.reason` | texto | sim |  |
| `[].published.createdBy` | texto | sim |  |
| `[].published.createdAt` | texto (data e hora) ou null | sim |  |
| `[].published.decidedBy` | texto ou null | sim |  |
| `[].published.decidedAt` | texto (data e hora) ou null | sim |  |
| `[].published.decisionNote` | texto ou null | sim |  |
| `[].pendingVersions` | lista de objeto `TemplateVersion` | sim |  |
| `[].pendingVersions[].code` | texto | sim |  |
| `[].pendingVersions[].versionNo` | inteiro | sim |  |
| `[].pendingVersions[].status` | texto (PENDING_APPROVAL · PUBLISHED · REJECTED) | sim |  |
| `[].pendingVersions[].kind` | texto (PRODUCT · ACTUARIAL_MODEL · FORMULA_SET · COVERAGE_LIBRARY) | sim |  |
| `[].pendingVersions[].kindLabel` | texto | sim |  |
| `[].pendingVersions[].name` | texto | sim |  |
| `[].pendingVersions[].description` | texto ou null | sim |  |
| `[].pendingVersions[].segment` | texto ou null | sim |  |
| `[].pendingVersions[].configKeys` | lista de texto | sim |  |
| `[].pendingVersions[].marketProducts` | booleano | sim |  |
| `[].pendingVersions[].content` | objeto | não | configurations {configKey: valor} e marketProducts (só no detalhe). |
| `[].pendingVersions[].source` | texto ou null | sim |  |
| `[].pendingVersions[].isLatestPublished` | booleano | sim |  |
| `[].pendingVersions[].reason` | texto | sim |  |
| `[].pendingVersions[].createdBy` | texto | sim |  |
| `[].pendingVersions[].createdAt` | texto (data e hora) ou null | sim |  |
| `[].pendingVersions[].decidedBy` | texto ou null | sim |  |
| `[].pendingVersions[].decidedAt` | texto (data e hora) ou null | sim |  |
| `[].pendingVersions[].decisionNote` | texto ou null | sim |  |

**Erros:** 401, 403.

### `POST /platform/templates`

**Novo** · `postPlatformTemplateList` · Criar platform template list

- **Quem pode:** conta da plataforma (super administrador, token `platform`).
- **Cabeçalho:** `Idempotency-Key` obrigatório.

**Recebe** (`application/json`, `TemplateProposal`):

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `code` | texto | sim |  |
| `kind` | texto (PRODUCT · ACTUARIAL_MODEL · FORMULA_SET · COVERAGE_LIBRARY) | sim |  |
| `name` | texto | sim |  |
| `description` | texto ou null | não |  |
| `segment` | qualquer | não |  |
| `content` | objeto | sim | {configurations: {configKey: valor}, marketProducts: bool} |
| `source` | texto ou null | não |  |
| `reason` | texto | sim | Motivo obrigatório (mínimo 10 caracteres). |

**Envia** (201, `application/json`, `TemplateVersion`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `code` | texto | sim |  |
| `versionNo` | inteiro | sim |  |
| `status` | texto (PENDING_APPROVAL · PUBLISHED · REJECTED) | sim |  |
| `kind` | texto (PRODUCT · ACTUARIAL_MODEL · FORMULA_SET · COVERAGE_LIBRARY) | sim |  |
| `kindLabel` | texto | sim |  |
| `name` | texto | sim |  |
| `description` | texto ou null | sim |  |
| `segment` | texto ou null | sim |  |
| `configKeys` | lista de texto | sim |  |
| `marketProducts` | booleano | sim |  |
| `content` | objeto | não | configurations {configKey: valor} e marketProducts (só no detalhe). |
| `source` | texto ou null | sim |  |
| `isLatestPublished` | booleano | sim |  |
| `reason` | texto | sim |  |
| `createdBy` | texto | sim |  |
| `createdAt` | texto (data e hora) ou null | sim |  |
| `decidedBy` | texto ou null | sim |  |
| `decidedAt` | texto (data e hora) ou null | sim |  |
| `decisionNote` | texto ou null | sim |  |

**Erros:** 400, 401, 403, 409.

### `GET /platform/templates/{code}`

**Novo** · `getPlatformTemplateDetail` · Obter platform template detail

- **Quem pode:** conta da plataforma (super administrador, token `platform`).
- **Parâmetros no caminho:** `code` (texto)

**Recebe:** nada (sem corpo).

**Envia** (200, `application/json`, `TemplateDetail`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `code` | texto | sim |  |
| `published` | objeto `TemplateVersion` ou null | sim | Com o conteúdo. |
| `published.code` | texto | sim |  |
| `published.versionNo` | inteiro | sim |  |
| `published.status` | texto (PENDING_APPROVAL · PUBLISHED · REJECTED) | sim |  |
| `published.kind` | texto (PRODUCT · ACTUARIAL_MODEL · FORMULA_SET · COVERAGE_LIBRARY) | sim |  |
| `published.kindLabel` | texto | sim |  |
| `published.name` | texto | sim |  |
| `published.description` | texto ou null | sim |  |
| `published.segment` | texto ou null | sim |  |
| `published.configKeys` | lista de texto | sim |  |
| `published.marketProducts` | booleano | sim |  |
| `published.content` | objeto | não | configurations {configKey: valor} e marketProducts (só no detalhe). |
| `published.source` | texto ou null | sim |  |
| `published.isLatestPublished` | booleano | sim |  |
| `published.reason` | texto | sim |  |
| `published.createdBy` | texto | sim |  |
| `published.createdAt` | texto (data e hora) ou null | sim |  |
| `published.decidedBy` | texto ou null | sim |  |
| `published.decidedAt` | texto (data e hora) ou null | sim |  |
| `published.decisionNote` | texto ou null | sim |  |
| `pendingVersions` | lista de objeto `TemplateVersion` | sim |  |
| `pendingVersions[].code` | texto | sim |  |
| `pendingVersions[].versionNo` | inteiro | sim |  |
| `pendingVersions[].status` | texto (PENDING_APPROVAL · PUBLISHED · REJECTED) | sim |  |
| `pendingVersions[].kind` | texto (PRODUCT · ACTUARIAL_MODEL · FORMULA_SET · COVERAGE_LIBRARY) | sim |  |
| `pendingVersions[].kindLabel` | texto | sim |  |
| `pendingVersions[].name` | texto | sim |  |
| `pendingVersions[].description` | texto ou null | sim |  |
| `pendingVersions[].segment` | texto ou null | sim |  |
| `pendingVersions[].configKeys` | lista de texto | sim |  |
| `pendingVersions[].marketProducts` | booleano | sim |  |
| `pendingVersions[].content` | objeto | não | configurations {configKey: valor} e marketProducts (só no detalhe). |
| `pendingVersions[].source` | texto ou null | sim |  |
| `pendingVersions[].isLatestPublished` | booleano | sim |  |
| `pendingVersions[].reason` | texto | sim |  |
| `pendingVersions[].createdBy` | texto | sim |  |
| `pendingVersions[].createdAt` | texto (data e hora) ou null | sim |  |
| `pendingVersions[].decidedBy` | texto ou null | sim |  |
| `pendingVersions[].decidedAt` | texto (data e hora) ou null | sim |  |
| `pendingVersions[].decisionNote` | texto ou null | sim |  |

**Erros:** 401, 403, 404.

### `GET /platform/templates/{code}/versions`

**Novo** · `getPlatformTemplateVersions` · Obter platform template versions

- **Quem pode:** conta da plataforma (super administrador, token `platform`).
- **Parâmetros no caminho:** `code` (texto)

**Recebe:** nada (sem corpo).

**Envia** (200, `application/json`, lista de `TemplateVersion`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `[].code` | texto | sim |  |
| `[].versionNo` | inteiro | sim |  |
| `[].status` | texto (PENDING_APPROVAL · PUBLISHED · REJECTED) | sim |  |
| `[].kind` | texto (PRODUCT · ACTUARIAL_MODEL · FORMULA_SET · COVERAGE_LIBRARY) | sim |  |
| `[].kindLabel` | texto | sim |  |
| `[].name` | texto | sim |  |
| `[].description` | texto ou null | sim |  |
| `[].segment` | texto ou null | sim |  |
| `[].configKeys` | lista de texto | sim |  |
| `[].marketProducts` | booleano | sim |  |
| `[].content` | objeto | não | configurations {configKey: valor} e marketProducts (só no detalhe). |
| `[].source` | texto ou null | sim |  |
| `[].isLatestPublished` | booleano | sim |  |
| `[].reason` | texto | sim |  |
| `[].createdBy` | texto | sim |  |
| `[].createdAt` | texto (data e hora) ou null | sim |  |
| `[].decidedBy` | texto ou null | sim |  |
| `[].decidedAt` | texto (data e hora) ou null | sim |  |
| `[].decisionNote` | texto ou null | sim |  |

**Erros:** 401, 403, 404.

### `POST /platform/templates/{code}/versions/{version_no}/approve`

**Novo** · `postPlatformTemplateApprove` · Criar platform template approve

- **Quem pode:** conta da plataforma (super administrador, token `platform`).
- **Parâmetros no caminho:** `code` (texto), `version_no` (inteiro)
- **Cabeçalho:** `Idempotency-Key` obrigatório.

**Recebe** (`application/json`, `PlatformParameterDecision`):

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `note` | texto ou null | não | Obrigatória (mínimo 10 caracteres) ao rejeitar. |

**Envia** (200, `application/json`, `TemplateVersion`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `code` | texto | sim |  |
| `versionNo` | inteiro | sim |  |
| `status` | texto (PENDING_APPROVAL · PUBLISHED · REJECTED) | sim |  |
| `kind` | texto (PRODUCT · ACTUARIAL_MODEL · FORMULA_SET · COVERAGE_LIBRARY) | sim |  |
| `kindLabel` | texto | sim |  |
| `name` | texto | sim |  |
| `description` | texto ou null | sim |  |
| `segment` | texto ou null | sim |  |
| `configKeys` | lista de texto | sim |  |
| `marketProducts` | booleano | sim |  |
| `content` | objeto | não | configurations {configKey: valor} e marketProducts (só no detalhe). |
| `source` | texto ou null | sim |  |
| `isLatestPublished` | booleano | sim |  |
| `reason` | texto | sim |  |
| `createdBy` | texto | sim |  |
| `createdAt` | texto (data e hora) ou null | sim |  |
| `decidedBy` | texto ou null | sim |  |
| `decidedAt` | texto (data e hora) ou null | sim |  |
| `decisionNote` | texto ou null | sim |  |

**Erros:** 400, 401, 403, 404, 409.

### `POST /platform/templates/{code}/versions/{version_no}/reject`

**Novo** · `postPlatformTemplateReject` · Criar platform template reject

- **Quem pode:** conta da plataforma (super administrador, token `platform`).
- **Parâmetros no caminho:** `code` (texto), `version_no` (inteiro)
- **Cabeçalho:** `Idempotency-Key` obrigatório.

**Recebe** (`application/json`, `PlatformParameterDecision`):

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `note` | texto ou null | não | Obrigatória (mínimo 10 caracteres) ao rejeitar. |

**Envia** (200, `application/json`, `TemplateVersion`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `code` | texto | sim |  |
| `versionNo` | inteiro | sim |  |
| `status` | texto (PENDING_APPROVAL · PUBLISHED · REJECTED) | sim |  |
| `kind` | texto (PRODUCT · ACTUARIAL_MODEL · FORMULA_SET · COVERAGE_LIBRARY) | sim |  |
| `kindLabel` | texto | sim |  |
| `name` | texto | sim |  |
| `description` | texto ou null | sim |  |
| `segment` | texto ou null | sim |  |
| `configKeys` | lista de texto | sim |  |
| `marketProducts` | booleano | sim |  |
| `content` | objeto | não | configurations {configKey: valor} e marketProducts (só no detalhe). |
| `source` | texto ou null | sim |  |
| `isLatestPublished` | booleano | sim |  |
| `reason` | texto | sim |  |
| `createdBy` | texto | sim |  |
| `createdAt` | texto (data e hora) ou null | sim |  |
| `decidedBy` | texto ou null | sim |  |
| `decidedAt` | texto (data e hora) ou null | sim |  |
| `decisionNote` | texto ou null | sim |  |

**Erros:** 400, 401, 403, 404, 409.

## 1.4 Fornecedor — motor de fórmulas (consulta)

### `GET /platform/formula-engine`

**Novo** · `getPlatformFormulaEngine` · Obter platform formula engine

- **Quem pode:** conta da plataforma (super administrador, token `platform`).

**Recebe:** nada (sem corpo).

**Envia** (200, `application/json`, `PlatformFormulaEngine`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `pricingFormulas` | objeto | sim | Catálogo do motor de fórmulas de tarifação (fases, funções, variáveis…). |
| `productFormulas` | objeto | sim | systemVariables das fórmulas de produto. |
| `rules` | objeto | sim | Campos, operadores, etapas e ações das regras «Quando… então…». |
| `platformConstants` | lista de objeto | sim | name, parameter, unit, description. |
| `limits` | mapa de inteiro | sim |  |

**Erros:** 401, 403.

## 1.5 Tenant — tabelas de referência e modelos

### `GET /reference-tables`

**Novo** · `getReferenceTableList` · Listar reference table list

- **Quem pode:** scope q360.read.

**Recebe:** nada (sem corpo).

**Envia** (200, `application/json`, lista de `ReferenceTableVersion`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `[].code` | texto | sim |  |
| `[].versionNo` | inteiro | sim |  |
| `[].status` | texto (PENDING_APPROVAL · PUBLISHED · REJECTED) | sim |  |
| `[].name` | texto | sim |  |
| `[].description` | texto ou null | sim |  |
| `[].keyColumn` | texto | sim |  |
| `[].columns` | lista de objeto `ReferenceTableColumn` | sim |  |
| `[].columns[].code` | texto | sim |  |
| `[].columns[].label` | texto | não |  |
| `[].columns[].type` | texto (NUMBER · TEXT) | sim |  |
| `[].rowCount` | inteiro | sim |  |
| `[].rows` | lista de objeto | não | Só no detalhe. |
| `[].source` | texto ou null | sim |  |
| `[].effectiveFrom` | texto (data e hora) ou null | sim |  |
| `[].inEffect` | booleano | sim |  |
| `[].reason` | texto | sim |  |
| `[].createdBy` | texto | sim |  |
| `[].createdAt` | texto (data e hora) ou null | sim |  |
| `[].decidedBy` | texto ou null | sim |  |
| `[].decidedAt` | texto (data e hora) ou null | sim |  |
| `[].decisionNote` | texto ou null | sim |  |

**Erros:** 401, 403.

### `GET /reference-tables/{code}`

**Novo** · `getReferenceTableDetail` · Obter reference table detail

- **Quem pode:** scope q360.read.
- **Parâmetros no caminho:** `code` (texto)

**Recebe:** nada (sem corpo).

**Envia** (200, `application/json`, `ReferenceTableVersion`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `code` | texto | sim |  |
| `versionNo` | inteiro | sim |  |
| `status` | texto (PENDING_APPROVAL · PUBLISHED · REJECTED) | sim |  |
| `name` | texto | sim |  |
| `description` | texto ou null | sim |  |
| `keyColumn` | texto | sim |  |
| `columns` | lista de objeto `ReferenceTableColumn` | sim |  |
| `columns[].code` | texto | sim |  |
| `columns[].label` | texto | não |  |
| `columns[].type` | texto (NUMBER · TEXT) | sim |  |
| `rowCount` | inteiro | sim |  |
| `rows` | lista de objeto | não | Só no detalhe. |
| `source` | texto ou null | sim |  |
| `effectiveFrom` | texto (data e hora) ou null | sim |  |
| `inEffect` | booleano | sim |  |
| `reason` | texto | sim |  |
| `createdBy` | texto | sim |  |
| `createdAt` | texto (data e hora) ou null | sim |  |
| `decidedBy` | texto ou null | sim |  |
| `decidedAt` | texto (data e hora) ou null | sim |  |
| `decisionNote` | texto ou null | sim |  |

**Erros:** 401, 403, 404.

### `GET /templates`

**Novo** · `listTemplates` · Modelos de partida publicados pelo fornecedor

- **Quem pode:** scope q360.read.

**Recebe:** nada (sem corpo).

**Envia** (200, `application/json`, lista de `TemplateVersion`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `[].code` | texto | sim |  |
| `[].versionNo` | inteiro | sim |  |
| `[].status` | texto (PENDING_APPROVAL · PUBLISHED · REJECTED) | sim |  |
| `[].kind` | texto (PRODUCT · ACTUARIAL_MODEL · FORMULA_SET · COVERAGE_LIBRARY) | sim |  |
| `[].kindLabel` | texto | sim |  |
| `[].name` | texto | sim |  |
| `[].description` | texto ou null | sim |  |
| `[].segment` | texto ou null | sim |  |
| `[].configKeys` | lista de texto | sim |  |
| `[].marketProducts` | booleano | sim |  |
| `[].content` | objeto | não | configurations {configKey: valor} e marketProducts (só no detalhe). |
| `[].source` | texto ou null | sim |  |
| `[].isLatestPublished` | booleano | sim |  |
| `[].reason` | texto | sim |  |
| `[].createdBy` | texto | sim |  |
| `[].createdAt` | texto (data e hora) ou null | sim |  |
| `[].decidedBy` | texto ou null | sim |  |
| `[].decidedAt` | texto (data e hora) ou null | sim |  |
| `[].decisionNote` | texto ou null | sim |  |

**Erros:** 401, 403.

### `GET /templates/{code}`

**Novo** · `getTemplate` · Conteúdo da versão publicada de um modelo

- **Quem pode:** scope q360.read.
- **Parâmetros no caminho:** `code` (texto)

**Recebe:** nada (sem corpo).

**Envia** (200, `application/json`, `TemplateVersion`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `code` | texto | sim |  |
| `versionNo` | inteiro | sim |  |
| `status` | texto (PENDING_APPROVAL · PUBLISHED · REJECTED) | sim |  |
| `kind` | texto (PRODUCT · ACTUARIAL_MODEL · FORMULA_SET · COVERAGE_LIBRARY) | sim |  |
| `kindLabel` | texto | sim |  |
| `name` | texto | sim |  |
| `description` | texto ou null | sim |  |
| `segment` | texto ou null | sim |  |
| `configKeys` | lista de texto | sim |  |
| `marketProducts` | booleano | sim |  |
| `content` | objeto | não | configurations {configKey: valor} e marketProducts (só no detalhe). |
| `source` | texto ou null | sim |  |
| `isLatestPublished` | booleano | sim |  |
| `reason` | texto | sim |  |
| `createdBy` | texto | sim |  |
| `createdAt` | texto (data e hora) ou null | sim |  |
| `decidedBy` | texto ou null | sim |  |
| `decidedAt` | texto (data e hora) ou null | sim |  |
| `decisionNote` | texto ou null | sim |  |

**Erros:** 401, 403, 404.

### `POST /templates/{code}/adopt`

**Novo** · `adoptTemplate` · Copiar um modelo para rascunhos do tenant (não publica nada)

- **Quem pode:** scope q360.write, permissão pricing-config:manage.
- **Parâmetros no caminho:** `code` (texto)

**Recebe** (`application/json`, `TemplateAdopt`):

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `effectiveFrom` | texto (data) ou null | não |  |

**Envia** (201, `application/json`, `TemplateAdoptResult`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `template` | objeto | sim | code, versionNo, name. |
| `effectiveFrom` | texto (data) | sim |  |
| `createdDrafts` | lista de objeto `TemplateAdoptDraft` | sim |  |
| `createdDrafts[].configKey` | texto | sim |  |
| `createdDrafts[].configurationId` | texto (UUID) | sim |  |
| `createdDrafts[].versionNo` | inteiro | sim |  |
| `createdDrafts[].status` | texto | sim |  |
| `marketProducts` | objeto ou null | sim | Relatório da criação dos produtos de mercado, se pedida. |
| `next` | texto | sim |  |

**Erros:** 400, 401, 403, 404, 409.

## 1.6 Tenant — tarifa por produto e simulação

### `GET /products/{product_id}/tariff`

**Novo** · `getProductTariff` · Tarifa do produto por passo do cálculo

- **Quem pode:** scope q360.read.
- **Parâmetros no caminho:** `product_id` (texto (UUID))

**Recebe:** nada (sem corpo).

**Envia** (200, `application/json`, `ProductTariff`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `productId` | texto (UUID) | sim |  |
| `productCode` | texto | sim |  |
| `productName` | texto | sim |  |
| `plans` | lista de objeto | sim | id, code, name, status. |
| `engine` | objeto | sim | owner=CODE, order, rounding, structure. |
| `stages` | lista de objeto `TariffStage` | sim |  |
| `stages[].order` | inteiro | sim |  |
| `stages[].code` | texto (PURE_PREMIUM · RISK_FACTORS · PERSON_RULES · PERSON_FORMULAS · LOADINGS · ADJUSTMENTS · LEGAL_TAXES · CHARGES · QUOTE_FORMULAS · PRODUCT_SETUP · FRACTIONATION) | sim |  |
| `stages[].label` | texto | sim |  |
| `stages[].owner` | texto (CODE · PLATFORM · TENANT) | sim |  |
| `stages[].editable` | booleano | sim |  |
| `stages[].scope` | texto (TENANT · PRODUCT) | sim | TENANT: a chave vale para todos os produtos. |
| `stages[].configurations` | lista de objeto `TariffConfigState` | sim |  |
| `stages[].platformParameters` | lista de objeto | sim | code, value, versionNo, unit. |
| `stages[].summary` | objeto | sim | Resumo do passo (depende do passo). |
| `openDrafts` | lista de objeto `TariffConfigVersion` | sim |  |
| `openDrafts[].configurationId` | texto (UUID) | sim |  |
| `openDrafts[].versionNo` | inteiro | sim |  |
| `openDrafts[].status` | texto | sim |  |
| `openDrafts[].effectiveFrom` | texto (data) ou null | sim |  |
| `openDrafts[].effectiveTo` | texto (data) ou null | sim |  |
| `openDrafts[].createdBy` | texto ou null | sim |  |
| `openDrafts[].rowVersion` | inteiro | sim |  |
| `platformVersions` | mapa de inteiro | sim |  |

**Erros:** 401, 403, 404.

### `POST /products/{product_id}/tariff/simulate`

**Novo** · `simulateProductTariff` · Simular a tarifa (com rascunhos) numa cotação de exemplo, sem gravar nada

- **Quem pode:** scope q360.write, permissão pricing-config:manage.
- **Parâmetros no caminho:** `product_id` (texto (UUID))

**Recebe** (`application/json`, `TariffSimulation`):

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `planId` | texto (UUID) | sim |  |
| `members` | lista de objeto `TariffMember` | sim |  |
| `members[].age` | inteiro | sim |  |
| `members[].sex` | texto (M · F) | não |  |
| `members[].relationship` | texto ou null | não |  |
| `proposerType` | texto (INDIVIDUAL · ORGANISATION) | não |  |
| `selection` | qualquer | não |  |
| `actuarialProfile` | qualquer | não |  |
| `paymentFrequency` | texto (ANUAL · SEMESTRAL · TRIMESTRAL · MENSAL) | não |  |
| `configurationIds` | lista de texto (UUID) | não |  |
| `includeOpenDrafts` | booleano | não |  |

**Envia** (200, `application/json`, `TariffSimulationResult`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `productId` | texto (UUID) | sim |  |
| `planId` | texto (UUID) | sim |  |
| `referenceDate` | texto (data) | sim |  |
| `currencyCode` | texto | sim |  |
| `totalAmount` | texto | sim |  |
| `installments` | mapa de texto | sim | Prestação por frequência (ANUAL, SEMESTRAL…). |
| `components` | lista de objeto | sim | Componentes do cálculo, cada um com owner. |
| `appliedDrafts` | lista de objeto `TariffConfigVersion` | sim |  |
| `appliedDrafts[].configurationId` | texto (UUID) | sim |  |
| `appliedDrafts[].versionNo` | inteiro | sim |  |
| `appliedDrafts[].status` | texto | sim |  |
| `appliedDrafts[].effectiveFrom` | texto (data) ou null | sim |  |
| `appliedDrafts[].effectiveTo` | texto (data) ou null | sim |  |
| `appliedDrafts[].createdBy` | texto ou null | sim |  |
| `appliedDrafts[].rowVersion` | inteiro | sim |  |
| `versions` | objeto | sim |  |
| `steps` | lista de objeto `TariffSimulationStep` | sim |  |
| `steps[].sequence` | inteiro | sim |  |
| `steps[].stepCode` | texto | sim |  |
| `steps[].ruleCode` | texto ou null | sim |  |
| `steps[].owner` | texto (CODE · PLATFORM · TENANT) | sim |  |
| `steps[].input` | qualquer ou null | sim |  |
| `steps[].output` | qualquer ou null | sim |  |
| `steps[].message` | texto ou null | sim |  |
| `persisted` | booleano | sim | Sempre false: a simulação não grava nada. |

**Erros:** 400, 401, 403, 404, 409.

## 1.7 Tenant — fórmulas

### `GET /business-config/formulas/variables`

**Novo** · `getFormulaVariables` · Catálogo único das variáveis de fórmulas e regras

- **Quem pode:** scope q360.read.
- **Parâmetros de pesquisa:** `productId` (texto) — UUID do produto: junta os grupos, opções, campos e fórmulas dele.; `usableIn` (texto) — PRICING_FORMULAS, PRICING_FORMULAS:PERSON, PRICING_FORMULAS:QUOTE, PRODUCT_FORMULAS ou RULE_CONDITIONS.

**Recebe:** nada (sem corpo).

**Envia** (200, `application/json`, `FormulaVariablesCatalog`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `variables` | lista de objeto `FormulaVariable` | sim |  |
| `variables[].token` | texto | sim | Nome a usar na expressão. |
| `variables[].label` | texto | sim |  |
| `variables[].source` | texto (SYSTEM · PARAMETER · AUXILIARY · PLATFORM_CONSTANT · RULE_FIELD · PRODUCT_GROUP · PRODUCT_OPTION · PRODUCT_FIELD · PRODUCT_FORMULA · PRODUCT_SYSTEM) | sim |  |
| `variables[].usableIn` | lista de texto | sim | PRICING_FORMULAS:PERSON/QUOTE, PRODUCT_FORMULAS, RULE_CONDITIONS. |
| `variables[].unit` | texto ou null | não |  |
| `variables[].value` | texto ou null | não | Parâmetros e constantes do fornecedor. |
| `variables[].parameter` | texto | não | Constantes: código do parâmetro do fornecedor. |
| `variables[].readOnly` | booleano | não |  |
| `variables[].expression` | texto | não | Valores auxiliares. |
| `functions` | lista de mapa de texto | sim |  |
| `operators` | lista de texto | sim |  |
| `referenceTables` | lista de objeto `FormulaReferenceTable` | sim |  |
| `referenceTables[].code` | texto | sim |  |
| `referenceTables[].name` | texto | sim |  |
| `referenceTables[].versionNo` | inteiro | sim |  |
| `referenceTables[].keyColumn` | texto | sim |  |
| `referenceTables[].columns` | lista de objeto | sim |  |
| `referenceTables[].example` | texto | sim |  |
| `sources` | mapa de qualquer ou null | sim | pricingFormulas, pricingFormulasError, productSetup, productSetupError. |

**Erros:** 400, 401, 403.

## 1.8 Tenant — aprovações

### `GET /business-config/approvals/pending`

**Novo** · `listPendingApprovals` · Fila única de aprovações pendentes

- **Quem pode:** scope q360.read.
- **Parâmetros de pesquisa:** `area` (texto) — ORGANIZATION, PRODUCTS, TARIFF, RULES, PARAMETERS ou DOCUMENTS.

**Recebe:** nada (sem corpo).

**Envia** (200, `application/json`, `PendingApprovals`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `total` | inteiro | sim |  |
| `byArea` | mapa de inteiro | sim |  |
| `items` | lista de objeto `PendingApprovalItem` | sim |  |
| `items[].configurationId` | texto (UUID) | sim |  |
| `items[].configKey` | texto | sim |  |
| `items[].label` | texto | sim |  |
| `items[].area` | texto (ORGANIZATION · PRODUCTS · TARIFF · RULES · PARAMETERS · DOCUMENTS) | sim |  |
| `items[].areaLabel` | texto | sim |  |
| `items[].versionNo` | inteiro | sim |  |
| `items[].effectiveFrom` | texto (data) ou null | sim |  |
| `items[].createdBy` | texto ou null | sim |  |
| `items[].submittedAt` | texto (data e hora) ou null | sim |  |
| `items[].againstVersionNo` | inteiro ou null | sim | Versão publicada com que se compara. |
| `items[].changeCount` | inteiro ou null | sim |  |
| `items[].changes` | lista de objeto | sim | path, change (ADDED/REMOVED/CHANGED), before, after; até 50. |
| `items[].isNew` | booleano | sim |  |
| `items[].canApprove` | booleano | sim |  |
| `items[].cannotApproveReason` | texto ou null | sim |  |

**Erros:** 400, 401, 403.

### `GET /business-config/approvals/pending/count`

**Novo** · `countPendingApprovals` · Contagem de aprovações pendentes (para o menu)

- **Quem pode:** scope q360.read.

**Recebe:** nada (sem corpo).

**Envia** (200, `application/json`, `PendingApprovalsCount`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `total` | inteiro | sim |  |
| `canApprove` | inteiro | sim |  |
| `byArea` | mapa de inteiro | sim |  |

**Erros:** 401, 403.

## 1.9 Sinistralidade — experience rating

### `GET /claims/experience-rating`

**Novo** · `getClaimsExperienceRating` · Calcular o fator configurado de experiência

- **Quem pode:** scope `q360.read` e permissão `audit:read`.
- **Parâmetros:** `proposerId` (obrigatório), `policyId` e `currency` (opcionais; AOA por omissão).
- **Envia:** `available`, métrica observada/alvo, período consultado, `factor`, limites e indicação do cálculo; HTTP 409 quando não há dados/configuração suficiente.
- O endpoint é informativo. O fator é aplicado à cotação pelo fluxo de tarifação.

## 1.10 Portal — satisfação e SLA de pedidos

### `POST /customer-portal/requests/{request_number}/satisfaction`

**Novo** · `postCustomerPortalRequestSatisfaction` · Registar avaliação do pedido

- **Quem pode:** cliente autenticado no Portal, dono do pedido.
- **Cabeçalho:** `Idempotency-Key`.
- **Recebe:** `score` e `comment` opcional. Só aceita pedidos resolvidos e uma avaliação por pedido.
- **Envia (201):** `requestNumber`, `score`, `comment` e `createdAt`.

### `GET /portal-requests/metrics`

**Novo** · `getPortalRequestMetrics` · Consultar métricas de satisfação e atendimento

- **Quem pode:** scope `q360.read`.
- **Filtros opcionais:** `status` e `type`, aplicados às métricas temporais.
- **Envia (200):** `satisfaction.enabled`, número de respostas, média, limites configurados e distribuição por pontuação; `serviceTime.items` agrega primeira resposta e resolução por prioridade e relógio SLA (`BUSINESS_HOURS` ou `ELAPSED_TIME`). Só inclui durações medidas; cada duração indica a quantidade de pedidos usada na média.

`GET /portal-requests` também devolve, por pedido, `sla` com metas, minutos de primeira resposta/resolução, relógio usado (`BUSINESS_HOURS` ou `ELAPSED_TIME`) e estado de violação. O calendário e as prioridades vêm da configuração de negócio publicada.

`GET /dashboard` agrega tendência por semana/mês, duração média entre submissão e aprovação e conversão aprovada/total por produto. Conversão por canal está indisponível até o modelo da cotação registar o canal de origem. O tempo médio de aprovação usa timestamps persistidos e não estima valores ausentes.

`GET /claims/projections/{run_id}` inclui, em cada cenário, `timeSeries`: sinistros reais mensais históricos seguidos dos sinistros projetados mensais. `periodStart` é o primeiro dia do mês; `actualClaims` ou `projectedClaims` fica nulo quando o ponto pertence ao outro trecho da série.

**Versões de produto:** o fluxo `ProductVersion` foi retirado; `Plan` está ligado diretamente a `Product`. Não há endpoint de histórico de versões do produto com autor/data/diff. As rotas `configuration/{type}/{id}/versions` versionam configurações e não representam versões do catálogo de produtos.

## 1.11 Cotações — aprovação de descontos

### `GET /quote-discount-approvals`

**Novo** · `getQuoteDiscountApprovalQueue` · Listar pedidos de aprovação de desconto

- **Quem pode:** papel Direcção Técnica, scope `q360.approve` e permissão `quote:discount:approve`.
- **Parâmetro:** `status` — `PENDING` (por omissão), `APPROVED`, `REJECTED` ou `ALL`.
- **Envia (200):** `{items: QuoteDiscountApproval[]}`.

### `POST /quote-discount-approvals/{approval_id}/decision`

**Novo** · `postQuoteDiscountApprovalDecision` · Aprovar ou rejeitar desconto

- **Quem pode:** papel Direcção Técnica, scope `q360.approve` e permissão `quote:discount:approve`; quem pediu não pode aprovar.
- **Cabeçalho:** `Idempotency-Key`.
- **Recebe:** `decision` (`APPROVE` ou `REJECT`) e `note` (mínimo 10 caracteres).
- **Envia (200):** pedido de aprovação atualizado. A decisão aprovada aplica o desconto à cotação.

`POST /quotes/{quote_id}/adjustments` devolve **202** e o pedido pendente quando o desconto excede o limite configurado; `dryRun=true` continua a devolver simulação e descontos abaixo do limite são aplicados imediatamente.

## 1.12 Comparação de cenários — margem

`GET /quotes/{quote_id}/scenarios/compare` e a respetiva exportação incluem margem estimada quando existe projeção de sinistros compatível. Sem projeção ou moeda compatível, a margem vem indisponível com o respetivo motivo.

## 2. Endpoints alterados no contrato

### `POST /business-config/formulas/test`

**Alterado** · `testPricingFormula` · Validar e testar uma expressão

- **Quem pode:** scope q360.write, permissão pricing-config:manage.
- **O que mudou:**
  - Envia: formato passou a estar descrito no contrato.

**Recebe** (`application/json`, `FormulaTest`):

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `expression` | texto | sim |  |
| `variables` | objeto | não |  |

**Envia** (200, `application/json`, `FormulaTestResult`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `valid` | booleano | sim |  |
| `result` | texto | não | Só quando valid=true. |
| `variables` | lista de texto | não |  |
| `steps` | lista de objeto `FormulaExplanationStep` | não | Cálculo passo a passo. |
| `steps[].step` | inteiro | sim |  |
| `steps[].expression` | texto | sim | Subexpressão calculada neste passo. |
| `steps[].operation` | texto | sim | VARIABLE, CONSTANT, tabela, + - * / **, min, max, abs, round. |
| `steps[].operands` | lista de texto | sim |  |
| `steps[].result` | texto | sim |  |
| `error` | texto | não | Só quando valid=false (HTTP 400). |

**Erros:** 400, 401, 403, 409.

### `GET /system-parameters`

**Alterado** · `getSystemParameterList` · Listar system parameter list

- **Quem pode:** scope q360.read.
- **Parâmetros de pesquisa:** `category` (texto) — OPERATIONAL, STRUCTURAL, LEGAL, LIMIT ou MARKET.
- **O que mudou:**
  - Envia — campos novos: `[].level`, `[].platformVersionNo`, `[].source`, `[].tenantValueOutOfLimits`
  - Envia — tipo alterado: `[].category` (texto (OPERATIONAL · STRUCTURAL) → texto (OPERATIONAL · STRUCTURAL · LEGAL · LIMIT · MARKET))

**Recebe:** nada (sem corpo).

**Envia** (200, `application/json`, lista de `SystemParameter`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `[].code` | texto | sim |  |
| `[].valueType` | texto (INTEGER · DECIMAL · TEXT · BOOLEAN) | sim |  |
| `[].category` | texto (OPERATIONAL · STRUCTURAL · LEGAL · LIMIT · MARKET) | sim | OPERATIONAL: o GTE altera; STRUCTURAL: só por evolução do sistema; LEGAL: valor legal; LIMIT: teto do fornecedor; MARKET: dado de mercado (fornecedor). |
| `[].level` | texto (PLATFORM_MANDATORY · PLATFORM_DEFAULT) | sim | PLATFORM_MANDATORY: vale o valor do fornecedor; PLATFORM_DEFAULT: o tenant ajusta dentro dos limites. |
| `[].value` | qualquer ou null | sim |  |
| `[].source` | texto (TENANT · PLATFORM · CODE_DEFAULT) | sim | De onde vem o valor em vigor. |
| `[].default` | qualquer ou null | sim | Valor geral (do fornecedor ou do código) usado sem ajuste do tenant. |
| `[].platformVersionNo` | inteiro | sim | Versão geral em vigor (0 = valor do código). |
| `[].isDefault` | booleano | sim |  |
| `[].tenantValueOutOfLimits` | booleano | sim | O valor do tenant ficou fora dos limites do fornecedor e não se aplica. |
| `[].description` | texto | sim |  |
| `[].unit` | texto ou null | sim |  |
| `[].constraints` | mapa de qualquer ou null | sim |  |
| `[].usedBy` | texto ou null | sim |  |
| `[].editable` | booleano | sim |  |
| `[].rowVersion` | inteiro | sim |  |
| `[].updatedBy` | texto ou null | sim |  |
| `[].updatedAt` | texto (data e hora) ou null | sim |  |

**Erros:** 400, 401, 403.

### `GET /system-parameters/{code}`

**Alterado** · `getSystemParameterDetail` · Obter system parameter detail

- **Quem pode:** scope q360.read.
- **Parâmetros no caminho:** `code` (texto)
- **O que mudou:**
  - Envia — campos novos: `level`, `platformVersionNo`, `source`, `tenantValueOutOfLimits`
  - Envia — tipo alterado: `category` (texto (OPERATIONAL · STRUCTURAL) → texto (OPERATIONAL · STRUCTURAL · LEGAL · LIMIT · MARKET))

**Recebe:** nada (sem corpo).

**Envia** (200, `application/json`, `SystemParameter`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `code` | texto | sim |  |
| `valueType` | texto (INTEGER · DECIMAL · TEXT · BOOLEAN) | sim |  |
| `category` | texto (OPERATIONAL · STRUCTURAL · LEGAL · LIMIT · MARKET) | sim | OPERATIONAL: o GTE altera; STRUCTURAL: só por evolução do sistema; LEGAL: valor legal; LIMIT: teto do fornecedor; MARKET: dado de mercado (fornecedor). |
| `level` | texto (PLATFORM_MANDATORY · PLATFORM_DEFAULT) | sim | PLATFORM_MANDATORY: vale o valor do fornecedor; PLATFORM_DEFAULT: o tenant ajusta dentro dos limites. |
| `value` | qualquer ou null | sim |  |
| `source` | texto (TENANT · PLATFORM · CODE_DEFAULT) | sim | De onde vem o valor em vigor. |
| `default` | qualquer ou null | sim | Valor geral (do fornecedor ou do código) usado sem ajuste do tenant. |
| `platformVersionNo` | inteiro | sim | Versão geral em vigor (0 = valor do código). |
| `isDefault` | booleano | sim |  |
| `tenantValueOutOfLimits` | booleano | sim | O valor do tenant ficou fora dos limites do fornecedor e não se aplica. |
| `description` | texto | sim |  |
| `unit` | texto ou null | sim |  |
| `constraints` | mapa de qualquer ou null | sim |  |
| `usedBy` | texto ou null | sim |  |
| `editable` | booleano | sim |  |
| `rowVersion` | inteiro | sim |  |
| `updatedBy` | texto ou null | sim |  |
| `updatedAt` | texto (data e hora) ou null | sim |  |

**Erros:** 401, 403, 404.

### `PUT /system-parameters/{code}`

**Alterado** · `putSystemParameterDetail` · Substituir system parameter detail

- **Quem pode:** scope q360.admin, permissão pricing-config:manage.
- **Parâmetros no caminho:** `code` (texto)
- **Cabeçalho:** `Idempotency-Key` obrigatório.
- **O que mudou:**
  - Envia — campos novos: `level`, `platformVersionNo`, `source`, `tenantValueOutOfLimits`
  - Envia — tipo alterado: `category` (texto (OPERATIONAL · STRUCTURAL) → texto (OPERATIONAL · STRUCTURAL · LEGAL · LIMIT · MARKET))

**Recebe** (`application/json`, `SystemParameterUpdate`):

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `value` | qualquer | sim |  |
| `rowVersion` | inteiro | sim |  |
| `reason` | texto | sim | Motivo obrigatório (mínimo 10 caracteres). |

**Envia** (200, `application/json`, `SystemParameter`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `code` | texto | sim |  |
| `valueType` | texto (INTEGER · DECIMAL · TEXT · BOOLEAN) | sim |  |
| `category` | texto (OPERATIONAL · STRUCTURAL · LEGAL · LIMIT · MARKET) | sim | OPERATIONAL: o GTE altera; STRUCTURAL: só por evolução do sistema; LEGAL: valor legal; LIMIT: teto do fornecedor; MARKET: dado de mercado (fornecedor). |
| `level` | texto (PLATFORM_MANDATORY · PLATFORM_DEFAULT) | sim | PLATFORM_MANDATORY: vale o valor do fornecedor; PLATFORM_DEFAULT: o tenant ajusta dentro dos limites. |
| `value` | qualquer ou null | sim |  |
| `source` | texto (TENANT · PLATFORM · CODE_DEFAULT) | sim | De onde vem o valor em vigor. |
| `default` | qualquer ou null | sim | Valor geral (do fornecedor ou do código) usado sem ajuste do tenant. |
| `platformVersionNo` | inteiro | sim | Versão geral em vigor (0 = valor do código). |
| `isDefault` | booleano | sim |  |
| `tenantValueOutOfLimits` | booleano | sim | O valor do tenant ficou fora dos limites do fornecedor e não se aplica. |
| `description` | texto | sim |  |
| `unit` | texto ou null | sim |  |
| `constraints` | mapa de qualquer ou null | sim |  |
| `usedBy` | texto ou null | sim |  |
| `editable` | booleano | sim |  |
| `rowVersion` | inteiro | sim |  |
| `updatedBy` | texto ou null | sim |  |
| `updatedAt` | texto (data e hora) ou null | sim |  |

**Erros:** 400, 401, 403, 404, 409.

### `POST /system-parameters/{code}/rollback`

**Alterado** · `postSystemParameterRollback` · Criar system parameter rollback

- **Quem pode:** scope q360.admin, permissão pricing-config:manage.
- **Parâmetros no caminho:** `code` (texto)
- **Cabeçalho:** `Idempotency-Key` obrigatório.
- **O que mudou:**
  - Envia — campos novos: `level`, `platformVersionNo`, `source`, `tenantValueOutOfLimits`
  - Envia — tipo alterado: `category` (texto (OPERATIONAL · STRUCTURAL) → texto (OPERATIONAL · STRUCTURAL · LEGAL · LIMIT · MARKET))

**Recebe** (`application/json`, `SystemParameterRollbackRequest`):

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `revisionNo` | inteiro | sim |  |
| `reason` | texto | sim | Motivo obrigatório (mínimo 10 caracteres). |

**Envia** (200, `application/json`, `SystemParameter`):

| Campo | Tipo | Sempre presente | Descrição |
|---|---|---|---|
| `code` | texto | sim |  |
| `valueType` | texto (INTEGER · DECIMAL · TEXT · BOOLEAN) | sim |  |
| `category` | texto (OPERATIONAL · STRUCTURAL · LEGAL · LIMIT · MARKET) | sim | OPERATIONAL: o GTE altera; STRUCTURAL: só por evolução do sistema; LEGAL: valor legal; LIMIT: teto do fornecedor; MARKET: dado de mercado (fornecedor). |
| `level` | texto (PLATFORM_MANDATORY · PLATFORM_DEFAULT) | sim | PLATFORM_MANDATORY: vale o valor do fornecedor; PLATFORM_DEFAULT: o tenant ajusta dentro dos limites. |
| `value` | qualquer ou null | sim |  |
| `source` | texto (TENANT · PLATFORM · CODE_DEFAULT) | sim | De onde vem o valor em vigor. |
| `default` | qualquer ou null | sim | Valor geral (do fornecedor ou do código) usado sem ajuste do tenant. |
| `platformVersionNo` | inteiro | sim | Versão geral em vigor (0 = valor do código). |
| `isDefault` | booleano | sim |  |
| `tenantValueOutOfLimits` | booleano | sim | O valor do tenant ficou fora dos limites do fornecedor e não se aplica. |
| `description` | texto | sim |  |
| `unit` | texto ou null | sim |  |
| `constraints` | mapa de qualquer ou null | sim |  |
| `usedBy` | texto ou null | sim |  |
| `editable` | booleano | sim |  |
| `rowVersion` | inteiro | sim |  |
| `updatedBy` | texto ou null | sim |  |
| `updatedAt` | texto (data e hora) ou null | sim |  |

**Erros:** 400, 401, 403, 404, 409.

## 3. Endpoints alterados no comportamento

O formato destes endpoints no contrato é o mesmo, ou a resposta não tem tipo no contrato. Mudou o que aceitam, o que devolvem dentro de campos livres (JSON) ou as regras que aplicam.

### `GET /business-config/catalog`

**Alterado** · `getBusinessConfigurationCatalog`

- **Recebe:** nada (sem corpo).
- **Envia (200):** `items[]`, com os campos novos:

| Campo | Tipo | Descrição |
|---|---|---|
| `items[].area` | texto (ORGANIZATION · PRODUCTS · TARIFF · RULES · DOCUMENTS) | Área da Administração onde o tipo é editado |
| `items[].areaLabel` | texto | Nome da área |
| `items[].formSchema.meta.stages[]` | lista de `{key, label}` | Só em `rules.custom`: ELIGIBILITY, PRICING, UNDERWRITING, VALIDATION, WORKFLOW |
| `items[].formSchema.meta.approvalRoles` | lista de texto | Só em `rules.custom`: SUBSCRIPTION_MANAGER, ADMIN |
| `items[].formSchema.meta.actions[].stage` · `needsRole` · `personOnly` | texto · booleano · booleano | Etapa da ação; se pede o perfil; se só vale por pessoa |
| `items[].formSchema.meta.fields[].quoteOnly` · `excludedStages` | booleano · lista de texto | Campo `total_premium`: só para a cotação inteira; não serve para preço nem elegibilidade |

### `POST /business-config/configurations` · `PUT /business-config/configurations/{configuration_id}`

**Alterado** · `createBusinessConfiguration` · `updateBusinessConfiguration`

- **Recebe:** `{configKey, value, effectiveFrom, effectiveTo?, metadata?}`. A forma é a mesma, mas o `value` aceita mais:
  - **`rules.custom`:**
    - `value.rules[]` aceita `stage` (opcional; tem de coincidir com a etapa da ação) e `role` (obrigatório em `REQUIRE_APPROVAL_BY_ROLE`).
    - Ações novas: `NOT_ELIGIBLE` e `REFER_TO_UNDERWRITING` (só «Cada pessoa»), `VALIDATION_ERROR`, `VALIDATION_WARNING` e `REQUIRE_APPROVAL_BY_ROLE`.
    - Campo de condição novo: `total_premium` (só «A cotação inteira»).
  - **`pricing.formulas`:**
    - As expressões podem usar as constantes do fornecedor (`cambio_usd_aoa`, `inflacao_geral_pct`, `taxa_arseg_pct`, `taxa_selo_pct`, `maioridade`) e a função `tabela("codigo", chave, "coluna")`.
    - Esses nomes ficam reservados: um parâmetro com o mesmo código dá 400.
- **Envia:** igual (`BusinessConfiguration`).
- **Erros novos:** 400 `VALIDATION-400` quando a etapa não coincide com a ação, quando falta o perfil, quando `total_premium` é usado no preço ou na elegibilidade, ou quando há um nome reservado.

### `POST /business-config/configurations/{configuration_id}` (ação `submit`) · `POST /business-config/configurations/{configuration_id}/approve`

**Alterado** · `changeBusinessConfigurationStatus` · `approveBusinessConfiguration`

- **Recebe:** igual (`{"action": "submit"}` / sem corpo).
- **Envia:** igual.
- **Erro novo:** 400 `VALIDATION-400` em `pricing.actuarial_model` quando a comissão de mediação de um segmento passa o teto do fornecedor (`limits.max_acquisition_commission_pct`). Verifica-se ao submeter e de novo ao aprovar.

### `POST /business-config/formulas/test`

**Alterado** · `testPricingFormula`

- **Recebe:** igual: `{expression: texto, variables: mapa}`.
- **Envia (200):** `{valid, result, variables, steps[]}`. Campo novo `steps[]`: `{step, expression, operation, operands[], result}`, o cálculo passo a passo; `operation` pode ser `VARIABLE`, `CONSTANT`, `tabela`, um operador ou uma função. Com expressão inválida devolve 400 `{valid: false, error}`.

### `POST /business-config/formulas/{configuration_id}/simulate`

**Alterado** · `simulateFormulaSet`

- **Recebe:** igual: `{totalAmount, membersCount, stage?, age?}`.
- **Envia (200):** em cada `steps[]`, campos novos `explanation[]` (passos do cálculo da fórmula) e `auxiliaryExplanations` (mapa: valor auxiliar → passos). Os `variables` de cada passo mostram também o valor das constantes do fornecedor usadas.

### `GET /business-config/formulas/catalog`

**Alterado** · `getFormulaCatalog`

- **Envia (200):** `functions[]` passa a incluir `tabela`.

### `PUT /products/{product_id}/pricing-setup` · `POST …/pricing-setup/validate` · `POST …/pricing-setup/test`

**Alterado** · `saveProductPricingSetupDraft` e as rotas de validar e testar

- **Recebe:** igual. As fórmulas do produto aceitam as constantes do fornecedor e `tabela()`. Os códigos de grupos, campos e fórmulas não podem usar os nomes das constantes.
- **Envia:** igual.

### `GET /quotes/{quote_id}/requirements`

**Alterado** · `getQuoteRequirements`

- **Envia (200):** os itens de `errors[]`, `warnings[]` e `info[]` que vêm das regras «Quando… então…» ganham:

| Campo | Tipo | Descrição |
|---|---|---|
| `stage` | texto (ELIGIBILITY · UNDERWRITING · VALIDATION · WORKFLOW) | Etapa da regra |
| `requiredRole` | texto (SUBSCRIPTION_MANAGER · ADMIN) | Só nas regras de fluxo |

- **Códigos novos:**
  - `CUSTOM_RULE_NOT_ELIGIBLE` (erro);
  - `CUSTOM_RULE_ELIGIBILITY_REFERRAL` (aviso);
  - `CUSTOM_RULE_VALIDATION_ERROR` (erro);
  - `CUSTOM_RULE_VALIDATION_WARNING` (aviso);
  - `CUSTOM_RULE_APPROVAL_ROLE` (informação).

### `POST /quotes/{quote_id}/submit`

**Alterado** · `postQuoteSubmit`

- **Recebe/Envia:** igual.
- **Erro novo:** a submissão é recusada quando uma regra de validação (`VALIDATION_ERROR`) ou de elegibilidade (`NOT_ELIGIBLE`) se verifica. A mensagem traz o texto da regra.

### `POST /quotes/{quote_id}/decision`

**Alterado** · `postQuoteDecision`

- **Recebe/Envia:** igual (`{decision, reasonCode, reasonText?, rowVersion}`).
- **Erro novo:** 403 `SEC-403` ao aprovar uma cotação em que se verifica uma regra `REQUIRE_APPROVAL_BY_ROLE`, se quem aprova não tem esse perfil. Um ADMIN pode sempre.

### `POST /eligibility/evaluate`

**Alterado** · `postEligibilityEvaluate`

- **Recebe:** igual.
- **Envia (200):** a mesma forma. Mudanças:
  - `decision` pode passar a `HARD_STOP` (regra `NOT_ELIGIBLE`) ou `REFERRAL` (regra `REFER_TO_UNDERWRITING`), com mensagens de código `ELIG-CUSTOM-RULE`;
  - os filhos passam a respeitar a maioridade (`legal.age_of_majority`) e a idade máxima com prova (`limits.dependent_max_age_with_proof`) do fornecedor, mesmo com regras publicadas antes;
  - o registo guarda `customRulesVersion`.

### `POST /configuration/rule-version/{config_id}/publish`

**Alterado** · `postConfigurationPublish` (`config_type = rule-version`)

- **Recebe/Envia:** igual.
- **Erro novo:** 400 `VALIDATION-400` numa regra de elegibilidade cujo `categoryRules.CHILD`, ou o de uma exceção corporativa, passa a maioridade (sem prova) ou a idade máxima com prova.

### `POST /quotes/{quote_id}/price` · `POST /quotes/{quote_id}/preview` · `POST /pricing/calculate` · `POST /pricing/preview`

**Alterado** · `postQuotePrice` · `postQuotePreview` · `postPricingCalculate` · `postPricingPreview`

- **Recebe:** igual.
- **Envia (200):** a mesma forma. Mudanças:
  - os componentes `STAMP_DUTY` e `ARSEG_LEVY` usam a taxa do fornecedor e têm `sourceCode = PLATFORM_PARAMETER:<código>` e `sourceVersion` = versão do valor;
  - um encargo do tenant com código legal passa a usar a taxa do fornecedor;
  - as fórmulas podem usar constantes e tabelas do fornecedor;
  - uma versão nova de um valor, constante ou tabela do fornecedor faz com que o cálculo seguinte de uma cotação aberta seja feito de novo.

### `GET /pricing/{pricing_run_id}/explanation`

**Alterado** · `getPricingExplanation`

- **Envia (200):** no passo `CONTEXT_RESOLVED`, `output` ganha `platformParameterVersions` e `platformReferenceTableVersions` (mapa código → versão). Os passos `ACTUARIAL_TAX_APPLIED` passam a ter em `input` `parameter` e `modelRate`.

### `PUT /system-parameters/{code}`

**Alterado no comportamento** (além dos campos da secção 2)

- **Erros:**
  - 403 `SEC-403` em parâmetros `LEGAL`, `LIMIT`, `MARKET` e `STRUCTURAL`, que são definidos pelo fornecedor;
  - 400 `VALIDATION-400` quando o valor sai dos limites que o fornecedor fixou para os tenants.

### Rotas da tarifa antiga (obsoletas)

`GET`/`POST /rating-tables`, `PATCH`/`DELETE /rating-tables/{rating_table_id}`, `GET`/`POST /pricing-parameter-sets`, `PATCH`/`DELETE /pricing-parameter-sets/{parameter_set_id}`

- **Recebe/Envia:** igual.
- **Mudança:** marcadas `deprecated: true` no contrato. A tarifa antiga converte-se com `manage.py migrate_legacy_tariffs` e deixa de ser usada quando o tenant publica `pricing.reference_premiums`.

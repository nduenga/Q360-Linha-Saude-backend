# Contrato v1.3.0 — Simulador GTE (R1–R8)

Fonte: `docs/artifacts/ART-006-openapi/Q360_MVP_ART_006_OpenAPI_Integral_v1.0.yml` (cópia idêntica no front: `docs/artifacts/ART-006-openapi/*.yaml`; regenerar tipos com `npm run api:generate:offline`). Cobre todas as fases de `CHECKLIST_BACKEND_SIMULADOR.md` e do guia do front.

Alterações **aditivas** (sem breaking changes). Cada operação nova traz `x-q360-readiness`, `x-q360-phase` e `x-q360-permission` (permissão DOC-001 **existente**; não há permissões novas).

- 🟢 contrato firme · 🟡 contrato proposto (depende de migração/acordo de formato) · 🔴 bloqueado por decisão do cliente: contrato **provisório**, front usa mock

## Extensões a operações/schemas existentes

- `Quote`/`QuoteCreateRequest`: `quoteType` (NEW|RENEWAL), `sourcePolicyId`, `isTransfer`, `previousInsurer`, `versionNo`, `selectedScenarioId`; `listQuotes` +filtros `quoteType, sourcePolicyId, proposerId, createdFrom, createdTo`.
- `AuditEvent`: `reason, before, after, impact`; `listAuditEvents` +filtros `action, actorId, from, to`.
- `PricingComponent`: `dimension`, `benefitCode`. `PricingParameterValue`: `classification` (OPERATIONAL|STRUCTURAL).
- `PlanBenefitConfiguration`: `inclusion` (INCLUDED|OPTIONAL), `currencyCode` (AOA|USD), `parentBenefitCode`, `participationBySystem`, além das 7 formas de garantia.
- `Scenario`/`PricingPreviewRequest`: `participationOptionCode` (A–E). `ClaimsImport`: `purpose` (HISTORY|TRANSFER_3Y).
- `Document`: `format, versionNo, templateId, templateVersionNo, scenarioId, checksum, errorCode, errorMessage`; `POST /quotes/{id}/proposal` aceita `ProposalRequest` (inclui `includeSections`: coberturas, capitais, participação, carências, exclusões, condições).
- `ProblemDetail.alerts[]`; `ReviewTask` (+`quoteName, quoteNumber, proposerName, planName, productName`, já usados pelo front); `document-templates` repostos.
- Novos códigos de erro em `x-q360-error-catalog`; mapeamento de permissões em `x-q360-permission-mapping`.

## Operações novas

### Fase 0 — Fundações (versões, rollback, auditoria)

| | Operação | Endpoint | Permissão | Bloqueio |
|---|---|---|---|---|
| 🟢 | `listConfigurationVersions` | `GET /api/v1/configuration/{configType}/{configId}/versions` | pricing-config:manage |  |
| 🟢 | `rollbackConfiguration` | `POST /api/v1/configuration/{configType}/{configId}/rollback` | pricing-config:manage |  |
| 🟢 | `exportAuditEvents` | `GET /api/v1/audit-events/export` | audit:read |  |

### Fase 1 — R6 Biblioteca de coberturas

| | Operação | Endpoint | Permissão | Bloqueio |
|---|---|---|---|---|
| 🟢 | `listBenefits` | `GET /api/v1/benefits` | — |  |
| 🟡 | `createBenefit` | `POST /api/v1/benefits` | product:manage |  |
| 🟢 | `getBenefit` | `GET /api/v1/benefits/{benefitId}` | — |  |
| 🟡 | `updateBenefit` | `PATCH /api/v1/benefits/{benefitId}` | product:manage |  |
| 🟢 | `deactivateBenefit` | `POST /api/v1/benefits/{benefitId}/deactivate` | product:manage |  |
| 🟢 | `reactivateBenefit` | `POST /api/v1/benefits/{benefitId}/reactivate` | product:manage |  |
| 🟢 | `duplicateBenefit` | `POST /api/v1/benefits/{benefitId}/duplicate` | product:manage |  |
| 🟢 | `listBenefitRevisions` | `GET /api/v1/benefits/{benefitId}/revisions` | — |  |
| 🟢 | `rollbackBenefit` | `POST /api/v1/benefits/{benefitId}/rollback` | product:manage |  |
| 🟢 | `getBenefitUsage` | `GET /api/v1/benefits/{benefitId}/usage` | — |  |
| 🟢 | `importBenefits` | `POST /api/v1/benefits/import` | product:manage |  |
| 🟢 | `downloadBenefitImportTemplate` | `GET /api/v1/benefits/import-template` | — |  |
| 🟢 | `exportBenefits` | `GET /api/v1/benefits/export` | — |  |

### Fase 2 — R4 Capitais, participação, plano e modelos

| | Operação | Endpoint | Permissão | Bloqueio |
|---|---|---|---|---|
| 🟢 | `listPlanBenefits` | `GET /api/v1/plans/{planId}/benefits` | — |  |
| 🟡 | `upsertPlanBenefit` | `PUT /api/v1/plans/{planId}/benefits/{benefitId}` | pricing-config:manage |  |
| 🟢 | `removePlanBenefit` | `DELETE /api/v1/plans/{planId}/benefits/{benefitId}` | pricing-config:manage |  |
| 🟢 | `validatePlanBenefits` | `POST /api/v1/plans/{planId}/benefits/validate` | pricing-config:manage |  |
| 🟢 | `listPlanConfigurationVersions` | `GET /api/v1/plans/{planId}/configuration-versions` | — |  |
| 🟢 | `createPlanConfigurationDraft` | `POST /api/v1/plans/{planId}/configuration-versions` | pricing-config:manage |  |
| 🟢 | `publishPlanConfiguration` | `POST /api/v1/plans/{planId}/configuration-versions/{versionId}/publish` | pricing-config:manage |  |
| 🟡 | `previewPricing` | `POST /api/v1/pricing/preview` | quote:calculate |  |
| 🟡 | `listParticipationOptions` | `GET /api/v1/participation-options` | — |  |
| 🟡 | `updateParticipationOption` | `PUT /api/v1/participation-options/{code}` | pricing-config:manage |  |
| 🟡 | `getPlanSettings` | `GET /api/v1/plans/{planId}/settings` | — |  |
| 🟡 | `updatePlanSettings` | `PUT /api/v1/plans/{planId}/settings` | pricing-config:manage |  |
| 🟡 | `getMarketCatalog` | `GET /api/v1/market-catalog` | — |  |
| 🟡 | `listPlanTemplates` | `GET /api/v1/plan-templates` | — |  |
| 🟡 | `createPlanFromTemplate` | `POST /api/v1/plans/from-template` | pricing-config:manage |  |

### Fase 3 — R3 Agravamentos, ajustes e preexistências

| | Operação | Endpoint | Permissão | Bloqueio |
|---|---|---|---|---|
| 🟡 | `createQuoteAdjustment` | `POST /api/v1/quotes/{quoteId}/adjustments` | quote:edit | OD-001/OD-002 (fórmula e ordem); o formato do contrato não depende disto |
| 🟢 | `listQuoteAdjustments` | `GET /api/v1/quotes/{quoteId}/adjustments` | — |  |
| 🟢 | `removeQuoteAdjustment` | `DELETE /api/v1/quotes/{quoteId}/adjustments/{adjustmentId}` | quote:edit |  |
| 🟡 | `listMemberPreexistingConditions` | `GET /api/v1/quotes/{quoteId}/members/{memberId}/preexisting-conditions` | — |  |
| 🟡 | `replaceMemberPreexistingConditions` | `PUT /api/v1/quotes/{quoteId}/members/{memberId}/preexisting-conditions` | quote:edit |  |

### Fase 4 — R5 Cenários

| | Operação | Endpoint | Permissão | Bloqueio |
|---|---|---|---|---|
| 🟢 | `listQuoteScenarios` | `GET /api/v1/quotes/{quoteId}/scenarios` | — |  |
| 🟡 | `createQuoteScenario` | `POST /api/v1/quotes/{quoteId}/scenarios` | quote:edit |  |
| 🟢 | `getScenario` | `GET /api/v1/scenarios/{scenarioId}` | — |  |
| 🟢 | `updateScenario` | `PATCH /api/v1/scenarios/{scenarioId}` | quote:edit |  |
| 🟢 | `deleteScenario` | `DELETE /api/v1/scenarios/{scenarioId}` | quote:edit |  |
| 🟢 | `cloneScenario` | `POST /api/v1/scenarios/{scenarioId}/clone` | quote:edit |  |
| 🟢 | `recalculateScenario` | `POST /api/v1/scenarios/{scenarioId}/recalculate` | quote:edit |  |
| 🟢 | `selectScenario` | `POST /api/v1/scenarios/{scenarioId}/select` | quote:edit |  |
| 🟢 | `compareScenarios` | `GET /api/v1/scenarios/compare` | — |  |
| 🟢 | `exportScenarioComparison` | `GET /api/v1/scenarios/compare/export` | quote:edit |  |

### Fase 5 — R1 Versões, renovação e requisitos de subscrição

| | Operação | Endpoint | Permissão | Bloqueio |
|---|---|---|---|---|
| 🟡 | `listQuoteVersions` | `GET /api/v1/quotes/{quoteId}/versions` | — |  |
| 🟢 | `getQuoteVersion` | `GET /api/v1/quotes/{quoteId}/versions/{versionNo}` | — |  |
| 🟢 | `compareQuoteVersion` | `GET /api/v1/quotes/{quoteId}/versions/{versionNo}/compare` | — |  |
| 🟢 | `restoreQuoteVersion` | `POST /api/v1/quotes/{quoteId}/versions/{versionNo}/restore` | quote:edit |  |
| 🟢 | `cloneQuote` | `POST /api/v1/quotes/{quoteId}/clone` | quote:create |  |
| 🟡 | `listPolicies` | `GET /api/v1/policies` | — |  |
| 🟡 | `getPolicy` | `GET /api/v1/policies/{policyId}` | — |  |
| 🟡 | `getRenewalContext` | `GET /api/v1/policies/{policyId}/renewal-context` | — |  |
| 🟡 | `listQuoteRequirements` | `GET /api/v1/quotes/{quoteId}/requirements` | — |  |
| 🟡 | `acknowledgeQuoteRequirement` | `POST /api/v1/quotes/{quoteId}/requirements/{code}/acknowledge` | quote:edit |  |
| 🟡 | `validateQuotePopulation` | `GET /api/v1/quotes/{quoteId}/population-validation` | — |  |
| 🟡 | `indexQuoteCapitals` | `POST /api/v1/quotes/{quoteId}/capital-indexation` | quote:edit |  |

### Fase 6 — R2 Sinistralidade e participação nos resultados

| | Operação | Endpoint | Permissão | Bloqueio |
|---|---|---|---|---|
| 🔴 | `createClaimsImport` | `POST /api/v1/claims-imports` | pricing-config:manage | Formato dos dados históricos, fórmulas actuariais e indicadores prioritários (cliente). Contrato PROVISÓRIO para permitir mocks. |
| 🔴 | `listClaimsImports` | `GET /api/v1/claims-imports` | quote:calculate | Formato dos dados históricos, fórmulas actuariais e indicadores prioritários (cliente). Contrato PROVISÓRIO para permitir mocks. |
| 🔴 | `getClaimsImport` | `GET /api/v1/claims-imports/{importId}` | quote:calculate | Formato dos dados históricos, fórmulas actuariais e indicadores prioritários (cliente). Contrato PROVISÓRIO para permitir mocks. |
| 🔴 | `setClaimsImportMapping` | `PUT /api/v1/claims-imports/{importId}/mapping` | pricing-config:manage | Formato dos dados históricos, fórmulas actuariais e indicadores prioritários (cliente). Contrato PROVISÓRIO para permitir mocks. |
| 🔴 | `listClaimsImportErrors` | `GET /api/v1/claims-imports/{importId}/errors` | pricing-config:manage | Formato dos dados históricos, fórmulas actuariais e indicadores prioritários (cliente). Contrato PROVISÓRIO para permitir mocks. |
| 🔴 | `commitClaimsImport` | `POST /api/v1/claims-imports/{importId}/commit` | pricing-config:manage | Formato dos dados históricos, fórmulas actuariais e indicadores prioritários (cliente). Contrato PROVISÓRIO para permitir mocks. |
| 🔴 | `getClaimsSummary` | `GET /api/v1/claims/summary` | quote:calculate | Formato dos dados históricos, fórmulas actuariais e indicadores prioritários (cliente). Contrato PROVISÓRIO para permitir mocks. |
| 🔴 | `createClaimsProjection` | `POST /api/v1/claims/projections` | quote:calculate | Formato dos dados históricos, fórmulas actuariais e indicadores prioritários (cliente). Contrato PROVISÓRIO para permitir mocks. |
| 🔴 | `getClaimsProjection` | `GET /api/v1/claims/projections/{projectionId}` | quote:calculate | Formato dos dados históricos, fórmulas actuariais e indicadores prioritários (cliente). Contrato PROVISÓRIO para permitir mocks. |
| 🔴 | `applyClaimsProjection` | `POST /api/v1/claims/projections/{projectionId}/apply` | quote:edit | Formato dos dados históricos, fórmulas actuariais e indicadores prioritários (cliente). Contrato PROVISÓRIO para permitir mocks. |
| 🟡 | `listAssumptionSets` | `GET /api/v1/claims/assumption-sets` | quote:calculate |  |
| 🟡 | `createAssumptionSet` | `POST /api/v1/claims/assumption-sets` | quote:calculate |  |
| 🟡 | `getAssumptionSet` | `GET /api/v1/claims/assumption-sets/{assumptionSetId}` | quote:calculate |  |
| 🟡 | `updateAssumptionSet` | `PUT /api/v1/claims/assumption-sets/{assumptionSetId}` | quote:calculate |  |
| 🔴 | `getProfitSharingTerms` | `GET /api/v1/policies/{policyId}/profit-sharing-terms` | quote:calculate | Formato dos dados e fórmulas (cliente) |
| 🔴 | `updateProfitSharingTerms` | `PUT /api/v1/policies/{policyId}/profit-sharing-terms` | pricing-config:manage | Formato dos dados e fórmulas (cliente) |
| 🔴 | `getProfitSharingResult` | `GET /api/v1/claims/profit-sharing` | quote:calculate | Formato dos dados e fórmulas (cliente) |

### Fase 7 — R7 Parâmetros e autonomia

| | Operação | Endpoint | Permissão | Bloqueio |
|---|---|---|---|---|
| 🟢 | `diffConfigurationVersions` | `GET /api/v1/configuration/{configType}/{configId}/diff` | pricing-config:manage |  |
| 🟢 | `simulateConfigurationImpact` | `POST /api/v1/configuration/{configType}/{configId}/impact-simulation` | pricing-config:manage |  |
| 🟡 | `getSystemParameters` | `GET /api/v1/system-parameters` | — |  |
| 🟡 | `updateSystemParameters` | `PATCH /api/v1/system-parameters` | pricing-config:manage |  |
| 🟢 | `listSystemParameterVersions` | `GET /api/v1/system-parameters/versions` | — |  |
| 🟢 | `listRoles` | `GET /api/v1/admin/roles` | — |  |

### Fase 8 — R8 Propostas e documentos

| | Operação | Endpoint | Permissão | Bloqueio |
|---|---|---|---|---|
| 🟢 | `listQuoteDocuments` | `GET /api/v1/quotes/{quoteId}/documents` | — |  |
| 🟢 | `getDocument` | `GET /api/v1/documents/{documentId}` | — |  |
| 🟡 | `getDocumentDownloadLink` | `GET /api/v1/documents/{documentId}/download` | quote:edit |  |
| 🟢 | `retryDocument` | `POST /api/v1/documents/{documentId}/retry` | quote:edit |  |
| 🟢 | `listTemplateVariables` | `GET /api/v1/document-templates/variables` | — |  |
| 🔴 | `previewDocumentTemplate` | `GET /api/v1/document-templates/{templateId}/preview` | — | OD-006 (template oficial e identidade visual) |
| 🟡 | `customerPortalListProposals` | `GET /api/v1/portal/proposals` | — |  |

## Decisões tomadas no contrato (confirmar)

1. **Benefit**: `kind` (BASE|COMPLEMENTARY) é o filtro BASE/Complementar; `category` é a classificação temática. Só Hospitalização, Cirurgia de ambulatório e Urgências/ambulância são BASE (checklist).
2. **Biblioteca**: histórico em `/benefits/{id}/revisions` e `POST /benefits/{id}/rollback` (alinhado com o código e a checklist). Rollback genérico `/configuration/{type}/{id}/rollback` para os restantes tipos.
3. **Remoção de ajuste**: `DELETE /quotes/{id}/adjustments/{adjId}` com corpo JSON `{reason}`.
4. **Plano**: `PUT /plans/{id}/benefits/{benefitId}` e `PUT /plans/{id}/settings` gravam no DRAFT; publicar em `POST /plans/{id}/configuration-versions/{versionId}/publish`. Criação por modelo: `POST /plans/from-template`.
5. **Validação** de combinações: 422 `PLAN-CONFIG-INVALID` com `alerts[]`; `POST /plans/{id}/benefits/validate` valida sem gravar.
6. **`/pricing/preview`** não exige `Idempotency-Key` (não persiste).
7. **Perfis**: só `GET /admin/roles` (leitura); perfis editáveis dependem do cliente.
8. **Listas fechadas** (grupos, formas de garantia, sistemas de acesso, tratamentos de preexistência, destinos de evacuação) vêm de `GET /market-catalog`; o front não deve hardcodar.
9. **Requisitos de subscrição** em `GET /quotes/{id}/requirements`; os `blocking` pendentes impedem `submit` (409 `REQUIREMENT-PENDING`).
10. **Permissões de sinistralidade**: não existe permissão DOC-001 própria; mapeei `claims:read`→`quote:calculate` e importação→`pricing-config:manage`. A confirmar (privacidade de dados de saúde).
11. **Fase 6** em fluxo upload → mapping → validação → commit; formatos e fórmulas dependem do cliente.
12. **Apólices** (`/policies`, `/renewal-context`) são novos no contrato; o portal usa `GET /portal/proposals` (confirmar prefixo `customer-portal`).

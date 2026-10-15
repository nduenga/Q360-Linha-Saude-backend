# Inventário de endpoints — API v1

Gerado a partir das rotas reais (`django.urls`) cruzadas com o contrato
OpenAPI regenerado (`manage.py build_openapi` →
`docs/artifacts/ART-006-openapi/Q360_MVP_ART_006_OpenAPI_Integral_v1.0.yml` e
`backend/schema.yml`). O teste `tests/integration/test_openapi_contract.py`
garante que **todas** as rotas estão no contrato, que o contrato não tem rotas
inexistentes, que cada operação tem `operationId`, resumo, tags, resposta de
sucesso, parâmetros de caminho e corpo, e que os ficheiros estão em dia.

Estados: **Novo** — criado neste trabalho; **Corrigido** — existia mas foi
alterado; **Já implementado; faltava no contrato** — existia no código mas não
no contrato anterior (`POST /api/v1/quotes/{quote_id}/reopen`);
**Implementado** — sem alterações de rota.

## Em falta / fora do âmbito

- Não há rotas no contrato sem implementação, nem rotas implementadas fora do
  contrato (verificado pelo teste acima).
- O serviço de referência `quote360-products` tem também: comparação de
  versões (**implementada aqui** em `…/configurations/{id}/compare`),
  *sandbox* de fórmulas (coberto por `…/formulas/test` e `…/{id}/simulate`)
  e um resultado esperado no *sandbox* (`expected_result`) — não
  implementado: o teste de referência actuarial cumpre esse papel.
- Fórmulas por pessoa: implementadas (fase `PERSON`, decisão A9).

## Alterações de contrato em rotas existentes

- `GET/POST/PUT /api/v1/members…`: novo campo opcional `nif` (pedido e resposta).
- `GET /api/v1/quotes`, `GET /api/v1/quotes/{id}` e restantes respostas de
  cotação: novo campo `proposerName` (além de `planName`/`productName`).
- `POST /api/v1/business-config/formulas/test`: resposta inclui `variables`.

Alterações de 2026-10-15 (decisões A1–A9, R1–R2):

- Configurações: novo estado `REJECTED` (rejeição; `PUT` volta a DRAFT;
  `submit` aceita DRAFT ou REJECTED); `GET …/configurations?status=REJECTED`.
- `POST …/formulas/{id}/simulate`: novos campos `stage` (`QUOTE`/`PERSON`) e
  `age`; resposta inclui `stage`. Validação/consulta de fórmulas devolvem
  também `evaluationOrderByStage` e `stages`.
- `POST/PUT /api/v1/proposers…`: NIF repetido no tenant → 409 também na
  edição (antes só na criação). `POST/PUT /api/v1/members…`: NIF repetido no
  tenant → 409.
- Novas chaves no catálogo: `pricing.fractionation`; nova gravidade
  `MODERATE_HIGH` em `underwriting.pre_existing_conditions`.
- Novas rotas do modelo actuarial (abaixo).

## Lista completa

Total: **281 operações**. Corrigido (devolve variáveis; agora no contrato): 1 · Implementado: 261 · Já implementado; faltava no contrato: 1 · Novo (código + contrato): 15 · Novo (2026-10-15): 3

| Área | Método | Rota | operationId | Resumo | Estado |
|---|---|---|---|---|---|
| Administration | GET | `/api/v1/admin/staff-accounts` | getStaffAccountListCreate | Listar staff account list create | Implementado |
| Administration | POST | `/api/v1/admin/staff-accounts` | postStaffAccountListCreate | Criar staff account list create | Implementado |
| Administration | POST | `/api/v1/admin/staff-accounts/{account_id}/reset-password` | postStaffAccountResetPassword | Criar staff account reset password | Implementado |
| Administration | PATCH | `/api/v1/admin/staff-accounts/{account_id}/roles` | patchStaffAccountRoles | Alterar staff account roles | Implementado |
| Administration | PATCH | `/api/v1/admin/staff-accounts/{account_id}/status` | patchStaffAccountStatus | Alterar staff account status | Implementado |
| Audit | GET | `/api/v1/audit-events` | getAuditEventList | Listar audit event list | Implementado |
| Benefits | GET | `/api/v1/benefits` | getBenefitList | Listar benefit list | Implementado |
| Benefits | POST | `/api/v1/benefits` | postBenefitList | Criar benefit list | Implementado |
| Benefits | GET | `/api/v1/benefits/export` | getBenefitExport | Obter benefit export | Implementado |
| Benefits | POST | `/api/v1/benefits/import` | postBenefitImport | Criar benefit import | Implementado |
| Benefits | GET | `/api/v1/benefits/{benefit_id}` | getBenefitDetail | Obter benefit detail | Implementado |
| Benefits | PATCH | `/api/v1/benefits/{benefit_id}` | patchBenefitDetail | Alterar benefit detail | Implementado |
| Benefits | POST | `/api/v1/benefits/{benefit_id}/deactivate` | postBenefitDeactivate | Criar benefit deactivate | Implementado |
| Benefits | POST | `/api/v1/benefits/{benefit_id}/reactivate` | postBenefitReactivate | Criar benefit reactivate | Implementado |
| Benefits | GET | `/api/v1/benefits/{benefit_id}/revisions` | getBenefitRevisionList | Listar benefit revision list | Implementado |
| Benefits | POST | `/api/v1/benefits/{benefit_id}/rollback` | postBenefitRollback | Criar benefit rollback | Implementado |
| Benefits | GET | `/api/v1/benefits/{benefit_id}/usage` | getBenefitUsage | Obter benefit usage | Implementado |
| Claims | GET | `/api/v1/claims/assumption-sets` | getAssumptionSetListCreate | Listar assumption set list create | Implementado |
| Claims | POST | `/api/v1/claims/assumption-sets` | postAssumptionSetListCreate | Criar assumption set list create | Implementado |
| Claims | GET | `/api/v1/claims/assumption-sets/{set_id}` | getAssumptionSetDetail | Obter assumption set detail | Implementado |
| Claims | GET | `/api/v1/claims/import-template` | getClaimsImportTemplate | Obter claims import template | Implementado |
| Claims | GET | `/api/v1/claims/imports` | getClaimsImportListCreate | Listar claims import list create | Implementado |
| Claims | POST | `/api/v1/claims/imports` | postClaimsImportListCreate | Criar claims import list create | Implementado |
| Claims | GET | `/api/v1/claims/imports/{import_id}` | getClaimsImportDetail | Obter claims import detail | Implementado |
| Claims | GET | `/api/v1/claims/methodology` | getClaimsMethodology | Obter claims methodology | Implementado |
| Claims | GET | `/api/v1/claims/profit-sharing` | getClaimsProfitSharing | Obter claims profit sharing | Implementado |
| Claims | GET | `/api/v1/claims/profit-sharing/parameters` | getClaimsProfitSharingParameters | Obter claims profit sharing parameters | Implementado |
| Claims | GET | `/api/v1/claims/projections` | getProjectionListCreate | Listar projection list create | Implementado |
| Claims | POST | `/api/v1/claims/projections` | postProjectionListCreate | Criar projection list create | Implementado |
| Claims | GET | `/api/v1/claims/projections/{run_id}` | getProjectionDetail | Obter projection detail | Implementado |
| Claims | GET | `/api/v1/claims/summary` | getClaimsSummary | Obter claims summary | Implementado |
| Clients | GET | `/api/v1/proposers` | getProposerListCreate | Listar proposer list create | Implementado |
| Clients | POST | `/api/v1/proposers` | postProposerListCreate | Criar proposer list create | Implementado |
| Clients | DELETE | `/api/v1/proposers/{proposer_id}` | deleteProposerDetail | Remover proposer detail | Implementado |
| Clients | GET | `/api/v1/proposers/{proposer_id}` | getProposerDetail | Obter proposer detail | Implementado |
| Clients | PUT | `/api/v1/proposers/{proposer_id}` | putProposerDetail | Substituir proposer detail | Implementado |
| Configuration | GET | `/api/v1/business-config/actuarial-model/catalog` | getActuarialModelCatalog | Secções editáveis e opções de cálculo do modelo actuarial | Novo (2026-10-15) |
| Configuration | POST | `/api/v1/business-config/actuarial-model/import` | importActuarialModelWorkbook | Importar o modelo actuarial de um Excel (cria uma versão DRAFT para aprovação) | Novo (2026-10-15) |
| Configuration | GET | `/api/v1/business-config/actuarial-model/template` | downloadActuarialModelTemplate | Descarregar o Excel de referência do modelo actuarial | Novo (2026-10-15) |
| Configuration | GET | `/api/v1/business-config/catalog` | getBusinessConfigurationCatalog | Consultar catálogo de configurações | Implementado |
| Configuration | GET | `/api/v1/business-config/configurations` | listBusinessConfigurations | Listar configurações de negócio | Implementado |
| Configuration | POST | `/api/v1/business-config/configurations` | createBusinessConfiguration | Criar configuração de negócio | Implementado |
| Configuration | GET | `/api/v1/business-config/configurations/{configuration_id}` | getBusinessConfiguration | Consultar configuração de negócio | Implementado |
| Configuration | POST | `/api/v1/business-config/configurations/{configuration_id}` | changeBusinessConfigurationStatus | Submeter ou retirar configuração de negócio | Implementado |
| Configuration | PUT | `/api/v1/business-config/configurations/{configuration_id}` | updateBusinessConfiguration | Actualizar configuração de negócio em rascunho | Implementado |
| Configuration | POST | `/api/v1/business-config/configurations/{configuration_id}/approve` | approveBusinessConfiguration | Aprovar configuração de negócio | Implementado |
| Configuration | GET | `/api/v1/business-config/configurations/{configuration_id}/compare` | compareBusinessConfigurations | Comparar duas versões da mesma configuração | Novo (código + contrato) |
| Configuration | GET | `/api/v1/business-config/configurations/{configuration_id}/documents` | listBusinessConfigurationDocuments | Listar documentos da configuração | Implementado |
| Configuration | POST | `/api/v1/business-config/configurations/{configuration_id}/documents/upload` | uploadBusinessConfigurationDocument | Anexar documento à configuração | Implementado |
| Configuration | GET | `/api/v1/business-config/configurations/{configuration_id}/history` | getBusinessConfigurationHistory | Histórico de uma versão de configuração | Novo (código + contrato) |
| Configuration | POST | `/api/v1/business-config/configurations/{configuration_id}/reject` | rejectBusinessConfiguration | Rejeitar configuração pendente (fica REJECTED com o motivo registado) | Novo (código + contrato) |
| Configuration | GET | `/api/v1/business-config/documents/{document_id}/download` | downloadBusinessConfigurationDocument | Descarregar documento da configuração | Implementado |
| Configuration | GET | `/api/v1/business-config/formulas` | listFormulaSets | Listar versões do conjunto de fórmulas | Novo (código + contrato) |
| Configuration | POST | `/api/v1/business-config/formulas` | createFormulaSet | Criar nova versão (DRAFT) do conjunto de fórmulas | Novo (código + contrato) |
| Configuration | GET | `/api/v1/business-config/formulas/catalog` | getFormulaCatalog | Variáveis, funções e operadores do editor de fórmulas | Novo (código + contrato) |
| Configuration | POST | `/api/v1/business-config/formulas/test` | testPricingFormula | Validar e testar uma expressão | Corrigido (devolve variáveis; agora no contrato) |
| Configuration | POST | `/api/v1/business-config/formulas/validate` | validateFormulaSet | Validar um conjunto de fórmulas sem o gravar | Novo (código + contrato) |
| Configuration | GET | `/api/v1/business-config/formulas/{configuration_id}` | getFormulaSet | Consultar versão do conjunto de fórmulas (com dependências) | Novo (código + contrato) |
| Configuration | PUT | `/api/v1/business-config/formulas/{configuration_id}` | updateFormulaSet | Editar conjunto de fórmulas em DRAFT | Novo (código + contrato) |
| Configuration | POST | `/api/v1/business-config/formulas/{configuration_id}/approve` | approveFormulaSet | Aprovar e publicar conjunto de fórmulas | Novo (código + contrato) |
| Configuration | GET | `/api/v1/business-config/formulas/{configuration_id}/history` | getFormulaSetHistory | Histórico de uma versão do conjunto de fórmulas | Novo (código + contrato) |
| Configuration | POST | `/api/v1/business-config/formulas/{configuration_id}/reject` | rejectFormulaSet | Rejeitar conjunto de fórmulas pendente | Novo (código + contrato) |
| Configuration | POST | `/api/v1/business-config/formulas/{configuration_id}/retire` | retireFormulaSet | Retirar (desativar) conjunto de fórmulas publicado | Novo (código + contrato) |
| Configuration | POST | `/api/v1/business-config/formulas/{configuration_id}/simulate` | simulateFormulaSet | Simular uma versão (qualquer estado) com valores de entrada, sem gravar nada | Novo (código + contrato) |
| Configuration | POST | `/api/v1/business-config/formulas/{configuration_id}/submit` | submitFormulaSet | Submeter conjunto de fórmulas para aprovação | Novo (código + contrato) |
| Configuration | GET | `/api/v1/business-config/rules/custom` | listCustomRules | Consultar regras personalizadas | Implementado |
| Configuration | POST | `/api/v1/business-config/rules/custom` | createCustomRules | Criar nova versão de regras personalizadas | Implementado |
| Configuration | GET | `/api/v1/business-config/rules/custom/catalog` | getCustomRulesCatalog | Consultar catálogo do construtor de regras personalizadas | Implementado |
| Configuration | PUT | `/api/v1/business-config/rules/custom/{configuration_id}` | updateCustomRules | Actualizar regras personalizadas em DRAFT | Implementado |
| Configuration | POST | `/api/v1/business-config/rules/custom/{configuration_id}/approve` | approveCustomRules | Publicar nova versão das regras personalizadas | Implementado |
| Configuration | POST | `/api/v1/business-config/rules/custom/{configuration_id}/submit` | submitCustomRules | Submeter regras personalizadas para aprovação | Implementado |
| Configuration | GET | `/api/v1/configuration/{config_type}/{config_id}/diff` | getConfigurationDiff | Obter configuration diff | Implementado |
| Configuration | POST | `/api/v1/configuration/{config_type}/{config_id}/impact-simulation` | postConfigurationImpactSimulation | Criar configuration impact simulation | Implementado |
| Configuration | POST | `/api/v1/configuration/{config_type}/{config_id}/publish` | postConfigurationPublish | Criar configuration publish | Implementado |
| Configuration | POST | `/api/v1/configuration/{config_type}/{config_id}/retire` | postConfigurationRetire | Criar configuration retire | Implementado |
| Configuration | POST | `/api/v1/configuration/{config_type}/{config_id}/rollback` | postConfigurationRollback | Criar configuration rollback | Implementado |
| Configuration | GET | `/api/v1/configuration/{config_type}/{config_id}/versions` | getConfigurationVersions | Obter configuration versions | Implementado |
| Configuration | GET | `/api/v1/pricing-parameter-sets` | getPricingParameterSetCreate | Listar pricing parameter set create | Implementado |
| Configuration | POST | `/api/v1/pricing-parameter-sets` | postPricingParameterSetCreate | Criar pricing parameter set create | Implementado |
| Configuration | DELETE | `/api/v1/pricing-parameter-sets/{parameter_set_id}` | deletePricingParameterSetDetail | Remover pricing parameter set detail | Implementado |
| Configuration | PATCH | `/api/v1/pricing-parameter-sets/{parameter_set_id}` | patchPricingParameterSetDetail | Alterar pricing parameter set detail | Implementado |
| Configuration | GET | `/api/v1/rating-tables` | getRatingTableCreate | Listar rating table create | Implementado |
| Configuration | POST | `/api/v1/rating-tables` | postRatingTableCreate | Criar rating table create | Implementado |
| Configuration | DELETE | `/api/v1/rating-tables/{rating_table_id}` | deleteRatingTableDetail | Remover rating table detail | Implementado |
| Configuration | PATCH | `/api/v1/rating-tables/{rating_table_id}` | patchRatingTableDetail | Alterar rating table detail | Implementado |
| Configuration | GET | `/api/v1/rule-versions` | getRuleVersionCreate | Listar rule version create | Implementado |
| Configuration | POST | `/api/v1/rule-versions` | postRuleVersionCreate | Criar rule version create | Implementado |
| Configuration | DELETE | `/api/v1/rule-versions/{rule_version_id}` | deleteRuleVersionDetail | Remover rule version detail | Implementado |
| Configuration | PATCH | `/api/v1/rule-versions/{rule_version_id}` | patchRuleVersionDetail | Alterar rule version detail | Implementado |
| Configuration | GET | `/api/v1/system-parameters` | getSystemParameterList | Listar system parameter list | Implementado |
| Configuration | GET | `/api/v1/system-parameters/{code}` | getSystemParameterDetail | Obter system parameter detail | Implementado |
| Configuration | PUT | `/api/v1/system-parameters/{code}` | putSystemParameterDetail | Substituir system parameter detail | Implementado |
| Configuration | GET | `/api/v1/system-parameters/{code}/revisions` | getSystemParameterRevisions | Obter system parameter revisions | Implementado |
| Configuration | POST | `/api/v1/system-parameters/{code}/rollback` | postSystemParameterRollback | Criar system parameter rollback | Implementado |
| Customer Portal | GET | `/api/v1/customer-portal/beneficiaries` | getCustomerPortalBeneficiaries | Obter customer portal beneficiaries | Implementado |
| Customer Portal | GET | `/api/v1/customer-portal/conversations` | getCustomerPortalConversations | Obter customer portal conversations | Implementado |
| Customer Portal | GET | `/api/v1/customer-portal/coverage` | getCustomerPortalCoverage | Obter customer portal coverage | Implementado |
| Customer Portal | GET | `/api/v1/customer-portal/dashboard` | getCustomerPortalDashboard | Obter customer portal dashboard | Implementado |
| Customer Portal | GET | `/api/v1/customer-portal/documents` | getCustomerPortalDocuments | Obter customer portal documents | Implementado |
| Customer Portal | GET | `/api/v1/customer-portal/documents/{document_id}/download` | getCustomerPortalDocumentDownload | Obter customer portal document download | Implementado |
| Customer Portal | POST | `/api/v1/customer-portal/eligibility` | postCustomerPortalEligibility | `POST /customer-portal/eligibility` — same coverage check as `GET /coverage`, as a POST with a body (kept for URL/method backward-compatibility with Fase 1; see module docstring). | Implementado |
| Customer Portal | GET | `/api/v1/customer-portal/me` | customerPortalMe | Obter informações do usuário autenticado no portal do cliente | Implementado |
| Customer Portal | GET | `/api/v1/customer-portal/me/quotes` | getCustomerPortalQuotes | Obter customer portal quotes | Implementado |
| Customer Portal | GET | `/api/v1/customer-portal/me/quotes/{quote_number}` | getCustomerPortalQuoteDetail | Obter customer portal quote detail | Implementado |
| Customer Portal | GET | `/api/v1/customer-portal/members/{member_id}/documents` | getCustomerPortalMemberDocuments | Obter customer portal member documents | Implementado |
| Customer Portal | POST | `/api/v1/customer-portal/members/{member_id}/documents` | postCustomerPortalMemberDocuments | Criar customer portal member documents | Implementado |
| Customer Portal | GET | `/api/v1/customer-portal/messages` | getCustomerPortalMessages | Obter customer portal messages | Implementado |
| Customer Portal | POST | `/api/v1/customer-portal/messages` | postCustomerPortalMessages | Criar customer portal messages | Implementado |
| Customer Portal | GET | `/api/v1/customer-portal/notifications` | getCustomerPortalNotifications | Obter customer portal notifications | Implementado |
| Customer Portal | POST | `/api/v1/customer-portal/notifications/read` | postCustomerPortalNotificationsRead | Criar customer portal notifications read | Implementado |
| Customer Portal | GET | `/api/v1/customer-portal/payments` | getCustomerPortalPayments | Obter customer portal payments | Implementado |
| Customer Portal | GET | `/api/v1/customer-portal/plan-benefits` | getCustomerPortalPlanBenefits | Obter customer portal plan benefits | Implementado |
| Customer Portal | GET | `/api/v1/customer-portal/plans/compare` | getCustomerPortalPlanCompare | Obter customer portal plan compare | Implementado |
| Customer Portal | GET | `/api/v1/customer-portal/policies` | getCustomerPortalPolicyList | Listar customer portal policy list | Implementado |
| Customer Portal | GET | `/api/v1/customer-portal/policies/{policy_number}` | getCustomerPortalPolicyDetail | Obter customer portal policy detail | Implementado |
| Customer Portal | GET | `/api/v1/customer-portal/policies/{policy_number}/document` | getCustomerPortalPolicyDocument | Obter customer portal policy document | Implementado |
| Customer Portal | GET | `/api/v1/customer-portal/policies/{policy_number}/history` | getCustomerPortalPolicyHistory | Obter customer portal policy history | Implementado |
| Customer Portal | GET | `/api/v1/customer-portal/policies/{policy_number}/members/{member_id}/card` | getCustomerPortalCard | Obter customer portal card | Implementado |
| Customer Portal | GET | `/api/v1/customer-portal/policies/{policy_number}/renewal` | getCustomerPortalRenewal | Obter customer portal renewal | Implementado |
| Customer Portal | GET | `/api/v1/customer-portal/policies/{policy_number}/statement` | getCustomerPortalPolicyStatement | Obter customer portal policy statement | Implementado |
| Customer Portal | GET | `/api/v1/customer-portal/profile` | getCustomerPortalProfile | Obter customer portal profile | Implementado |
| Customer Portal | GET | `/api/v1/customer-portal/request-types` | getCustomerPortalRequestTypes | Obter customer portal request types | Implementado |
| Customer Portal | GET | `/api/v1/customer-portal/requests` | getCustomerPortalRequests | Obter customer portal requests | Implementado |
| Customer Portal | POST | `/api/v1/customer-portal/requests` | postCustomerPortalRequests | Criar customer portal requests | Implementado |
| Customer Portal | GET | `/api/v1/customer-portal/requests/{request_number}` | getCustomerPortalRequestDetail | Obter customer portal request detail | Implementado |
| Customer Portal | POST | `/api/v1/customer-portal/{tenant_id}/auth/first-access/confirm` | postFirstAccessConfirm | Criar first access confirm | Implementado |
| Customer Portal | POST | `/api/v1/customer-portal/{tenant_id}/auth/first-access/request` | postFirstAccessRequest | Criar first access request | Implementado |
| Customer Portal | POST | `/api/v1/customer-portal/{tenant_id}/auth/login` | postPasswordLogin | Criar password login | Implementado |
| Customer Portal | POST | `/api/v1/customer-portal/{tenant_id}/auth/password-reset/confirm` | postPasswordResetConfirm | Criar password reset confirm | Implementado |
| Customer Portal | POST | `/api/v1/customer-portal/{tenant_id}/auth/password-reset/request` | postPasswordResetRequest | Criar password reset request | Implementado |
| Customer Portal | POST | `/api/v1/customer-portal/{tenant_id}/auth/request-access` | customerPortalRequestAccess | Solicitar acesso ao portal do cliente | Implementado |
| Customer Portal | POST | `/api/v1/customer-portal/{tenant_id}/auth/verify-otp` | customerPortalVerifyOtp | Verificar OTP para acesso ao portal do cliente | Implementado |
| Customer Portal Support | GET | `/api/v1/portal-conversations` | getPortalConversationList | Listar portal conversation list | Implementado |
| Customer Portal Support | GET | `/api/v1/portal-messages` | getPortalStaffMessages | Obter portal staff messages | Implementado |
| Customer Portal Support | POST | `/api/v1/portal-messages` | postPortalStaffMessages | Criar portal staff messages | Implementado |
| Customer Portal Support | GET | `/api/v1/portal-requests` | getPortalRequestList | Listar portal request list | Implementado |
| Customer Portal Support | GET | `/api/v1/portal-requests/{request_number}` | getPortalRequestDetail | Obter portal request detail | Implementado |
| Customer Portal Support | POST | `/api/v1/portal-requests/{request_number}/transition` | postPortalRequestTransition | Criar portal request transition | Implementado |
| Documents | GET | `/api/v1/document-templates` | getDocumentTemplateListCreate | Listar document template list create | Implementado |
| Documents | POST | `/api/v1/document-templates` | postDocumentTemplateListCreate | Criar document template list create | Implementado |
| Documents | GET | `/api/v1/document-templates/schema` | getDocumentTemplateSchema | Obter document template schema | Implementado |
| Documents | DELETE | `/api/v1/document-templates/{template_id}` | deleteDocumentTemplateDetail | Remover document template detail | Implementado |
| Documents | PATCH | `/api/v1/document-templates/{template_id}` | patchDocumentTemplateDetail | Alterar document template detail | Implementado |
| Documents | DELETE | `/api/v1/document-templates/{template_id}/letterhead` | deleteDocumentTemplateLetterhead | Remover document template letterhead | Implementado |
| Documents | GET | `/api/v1/document-templates/{template_id}/letterhead` | getDocumentTemplateLetterhead | Obter document template letterhead | Implementado |
| Documents | POST | `/api/v1/document-templates/{template_id}/letterhead` | postDocumentTemplateLetterhead | Criar document template letterhead | Implementado |
| Documents | GET | `/api/v1/document-templates/{template_id}/preview` | getDocumentTemplatePreview | Obter document template preview | Implementado |
| Documents | POST | `/api/v1/document-templates/{template_id}/publish` | postDocumentTemplatePublish | Criar document template publish | Implementado |
| Documents | POST | `/api/v1/document-templates/{template_id}/retire` | postDocumentTemplateRetire | Criar document template retire | Implementado |
| Documents | DELETE | `/api/v1/document-templates/{template_id}/word` | deleteDocumentTemplateWord | Remover document template word | Implementado |
| Documents | GET | `/api/v1/document-templates/{template_id}/word` | getDocumentTemplateWord | Obter document template word | Implementado |
| Documents | POST | `/api/v1/document-templates/{template_id}/word` | postDocumentTemplateWord | Criar document template word | Implementado |
| Documents | GET | `/api/v1/documents/signed/{token}` | getDocumentSignedDownload | Obter document signed download | Implementado |
| Documents | GET | `/api/v1/documents/{document_id}/download` | getDocumentDownload | Obter document download | Implementado |
| Documents | POST | `/api/v1/documents/{document_id}/retry` | postDocumentRetry | Criar document retry | Implementado |
| Documents | POST | `/api/v1/documents/{document_id}/signed-url` | postDocumentSignedUrl | Criar document signed url | Implementado |
| Documents | GET | `/api/v1/quotes/{quote_id}/proposal` | getQuoteProposal | Obter quote proposal | Implementado |
| Documents | POST | `/api/v1/quotes/{quote_id}/proposal` | postQuoteProposal | Criar quote proposal | Implementado |
| Documents | GET | `/api/v1/quotes/{quote_id}/proposals` | getQuoteProposalListCreate | Listar quote proposal list create | Implementado |
| Documents | POST | `/api/v1/quotes/{quote_id}/proposals` | postQuoteProposalListCreate | Criar quote proposal list create | Implementado |
| Documents | GET | `/api/v1/quotes/{quote_id}/proposals/preview` | getQuoteProposalPreview | Obter quote proposal preview | Implementado |
| Eligibility | POST | `/api/v1/eligibility/evaluate` | postEligibilityEvaluate | Criar eligibility evaluate | Implementado |
| Eligibility | GET | `/api/v1/eligibility/evaluations` | getEligibilityExecutionList | Listar eligibility execution list | Implementado |
| Eligibility | GET | `/api/v1/eligibility/evaluations/{evaluation_id}` | getEligibilityExecutionDetail | Obter eligibility execution detail | Implementado |
| Health | GET | `/api/v1/health/live` | getLiveHealth | Obter live health | Implementado |
| Health | GET | `/api/v1/health/ready` | getReadyHealth | Obter ready health | Implementado |
| Identity | POST | `/api/v1/auth/dev-login` | postDevLogin | Criar dev login | Implementado |
| Identity | POST | `/api/v1/auth/login` | postLogin | Criar login | Implementado |
| Identity | POST | `/api/v1/auth/logout` | postLogout | Criar logout | Implementado |
| Identity | POST | `/api/v1/auth/refresh` | postRefresh | Criar refresh | Implementado |
| Identity | GET | `/api/v1/me` | getCurrentActor | Obter actor, tenant, roles e permissões | Implementado |
| Identity | GET | `/api/v1/member-documents` | getMemberDocumentQueue | Listar member document queue | Implementado |
| Identity | GET | `/api/v1/member-documents/{document_id}/download` | getMemberDocumentDownload | Obter member document download | Implementado |
| Identity | POST | `/api/v1/member-documents/{document_id}/review` | postMemberDocumentReview | Criar member document review | Implementado |
| Identity | POST | `/api/v1/member-imports` | postMemberImportUpload | Criar member import upload | Implementado |
| Identity | GET | `/api/v1/member-imports/{import_id}` | getMemberImportDetail | Obter member import detail | Implementado |
| Identity | POST | `/api/v1/member-imports/{import_id}/commit` | postMemberImportCommit | Criar member import commit | Implementado |
| Identity | GET | `/api/v1/members` | getMemberListCreate | Listar member list create | Implementado |
| Identity | POST | `/api/v1/members` | postMemberListCreate | Criar member list create | Implementado |
| Identity | DELETE | `/api/v1/members/{member_id}` | deleteMemberDetail | Remover member detail | Implementado |
| Identity | GET | `/api/v1/members/{member_id}` | getMemberDetail | Obter member detail | Implementado |
| Identity | PUT | `/api/v1/members/{member_id}` | putMemberDetail | Substituir member detail | Implementado |
| Identity | GET | `/api/v1/members/{member_id}/documents` | getMemberDocumentListCreate | Listar member document list create | Implementado |
| Identity | POST | `/api/v1/members/{member_id}/documents` | postMemberDocumentListCreate | Criar member document list create | Implementado |
| Other | GET | `/api/v1/installments` | getInstallmentList | Listar installment list | Implementado |
| Other | GET | `/api/v1/platform/admins` | getPlatformAdminListCreate | Listar platform admin list create | Implementado |
| Other | POST | `/api/v1/platform/admins` | postPlatformAdminListCreate | Criar platform admin list create | Implementado |
| Other | PATCH | `/api/v1/platform/admins/{admin_id}` | patchPlatformAdminStatus | Alterar platform admin status | Implementado |
| Other | POST | `/api/v1/platform/admins/{admin_id}/reset-password` | postPlatformAdminResetPassword | Criar platform admin reset password | Implementado |
| Other | GET | `/api/v1/platform/audit` | getPlatformAudit | Obter platform audit | Implementado |
| Other | POST | `/api/v1/platform/auth/login` | postPlatformLogin | Criar platform login | Implementado |
| Other | GET | `/api/v1/platform/me` | getPlatformMe | Obter platform me | Implementado |
| Other | POST | `/api/v1/platform/me/password` | postPlatformChangePassword | Criar platform change password | Implementado |
| Other | GET | `/api/v1/platform/tenants` | getPlatformTenantListCreate | Listar platform tenant list create | Implementado |
| Other | POST | `/api/v1/platform/tenants` | postPlatformTenantListCreate | Criar platform tenant list create | Implementado |
| Other | GET | `/api/v1/platform/tenants/{tenant_id}` | getPlatformTenantDetail | Obter platform tenant detail | Implementado |
| Other | PATCH | `/api/v1/platform/tenants/{tenant_id}` | patchPlatformTenantDetail | Alterar platform tenant detail | Implementado |
| Other | POST | `/api/v1/platform/tenants/{tenant_id}/accounts/{account_id}/reset-password` | postPlatformTenantAccountReset | Criar platform tenant account reset | Implementado |
| Other | POST | `/api/v1/platform/tenants/{tenant_id}/admins` | postPlatformTenantAdmins | Criar platform tenant admins | Implementado |
| Plans | GET | `/api/v1/plans` | getPlanListCreate | Listar plan list create | Implementado |
| Plans | POST | `/api/v1/plans` | postPlanListCreate | Criar plan list create | Implementado |
| Plans | DELETE | `/api/v1/plans/{plan_id}` | deletePlanDetail | Remover plan detail | Implementado |
| Plans | GET | `/api/v1/plans/{plan_id}` | getPlanDetail | Obter plan detail | Implementado |
| Plans | PATCH | `/api/v1/plans/{plan_id}` | patchPlanDetail | Alterar plan detail | Implementado |
| Plans | GET | `/api/v1/plans/{plan_id}/benefits` | getPlanBenefitListCreate | Listar plan benefit list create | Implementado |
| Plans | POST | `/api/v1/plans/{plan_id}/benefits` | postPlanBenefitListCreate | Criar plan benefit list create | Implementado |
| Plans | DELETE | `/api/v1/plans/{plan_id}/benefits/{benefit_id}` | deletePlanBenefitDetail | Remover plan benefit detail | Implementado |
| Plans | GET | `/api/v1/plans/{plan_id}/benefits/{benefit_id}` | getPlanBenefitDetail | Obter plan benefit detail | Implementado |
| Plans | PUT | `/api/v1/plans/{plan_id}/benefits/{benefit_id}` | putPlanBenefitDetail | Substituir plan benefit detail | Implementado |
| Plans | GET | `/api/v1/plans/{plan_id}/validation` | getPlanValidation | Obter plan validation | Implementado |
| Policies | GET | `/api/v1/coverage` | getCoverageLookup | Obter coverage lookup | Implementado |
| Policies | GET | `/api/v1/policies` | getPolicyList | Listar policy list | Implementado |
| Policies | GET | `/api/v1/policies/{policy_id}` | getPolicyDetail | Obter policy detail | Implementado |
| Policies | GET | `/api/v1/policies/{policy_id}/coverage` | getPolicyCoverage | Obter policy coverage | Implementado |
| Policies | GET | `/api/v1/policies/{policy_id}/document` | getPolicyDocument | Obter policy document | Implementado |
| Policies | GET | `/api/v1/policies/{policy_id}/installments` | getPolicyInstallmentList | Listar policy installment list | Implementado |
| Policies | POST | `/api/v1/policies/{policy_id}/installments/{installment_no}/payment` | postRegisterFirstPremiumPayment | Criar register first premium payment | Implementado |
| Policies | GET | `/api/v1/policies/{policy_id}/members` | getPolicyMemberList | Listar policy member list | Implementado |
| Policies | GET | `/api/v1/policies/{policy_id}/signature` | getPolicySignature | Obter policy signature | Implementado |
| Population | GET | `/api/v1/relationship-codes` | getRelationshipCodeList | Listar relationship code list | Implementado |
| Pricing | POST | `/api/v1/pricing/calculate` | postPricingCalculate | Criar pricing calculate | Implementado |
| Pricing | POST | `/api/v1/pricing/preview` | postPricingPreview | Criar pricing preview | Implementado |
| Pricing | GET | `/api/v1/pricing/runs` | getPricingExecutionList | Listar pricing execution list | Implementado |
| Pricing | GET | `/api/v1/pricing/runs/{pricing_run_id}` | getPricingExecutionDetail | Obter pricing execution detail | Implementado |
| Pricing | POST | `/api/v1/pricing/scenarios` | postPricingScenario | Criar pricing scenario | Implementado |
| Pricing | GET | `/api/v1/pricing/{pricing_run_id}/explanation` | getPricingExplanation | Obter pricing explanation | Implementado |
| Products | POST | `/api/v1/product-templates/market` | postMarketTemplates | Criar market templates | Implementado |
| Products | GET | `/api/v1/products` | getProductListCreate | Listar product list create | Implementado |
| Products | POST | `/api/v1/products` | postProductListCreate | Criar product list create | Implementado |
| Products | DELETE | `/api/v1/products/{product_id}` | deleteProductDetail | Remover product detail | Implementado |
| Products | GET | `/api/v1/products/{product_id}` | getProductDetail | Obter product detail | Implementado |
| Products | PUT | `/api/v1/products/{product_id}` | putProductDetail | Substituir product detail | Implementado |
| Quotes | GET | `/api/v1/dashboard` | getDashboard | Obter dashboard agregado de cotações e subscrição | Implementado |
| Quotes | GET | `/api/v1/quotes` | getQuoteListCreate | Listar quote list create | Implementado |
| Quotes | POST | `/api/v1/quotes` | postQuoteListCreate | Criar quote list create | Implementado |
| Quotes | POST | `/api/v1/quotes/renewals` | postQuoteRenewalCreate | Criar quote renewal create | Implementado |
| Quotes | DELETE | `/api/v1/quotes/{quote_id}` | deleteQuoteDetail | Remover quote detail | Implementado |
| Quotes | GET | `/api/v1/quotes/{quote_id}` | getQuoteDetail | Obter quote detail | Implementado |
| Quotes | PUT | `/api/v1/quotes/{quote_id}` | putQuoteDetail | Substituir quote detail | Implementado |
| Quotes | GET | `/api/v1/quotes/{quote_id}/adjustments` | getQuoteAdjustmentListCreate | Listar quote adjustment list create | Implementado |
| Quotes | POST | `/api/v1/quotes/{quote_id}/adjustments` | postQuoteAdjustmentListCreate | Criar quote adjustment list create | Implementado |
| Quotes | DELETE | `/api/v1/quotes/{quote_id}/adjustments/{adjustment_id}` | deleteQuoteAdjustmentDetail | Remover quote adjustment detail | Implementado |
| Quotes | POST | `/api/v1/quotes/{quote_id}/cancel` | postQuoteCancel | Criar quote cancel | Implementado |
| Quotes | GET | `/api/v1/quotes/{quote_id}/claims-context` | getQuoteClaimsContext | Obter quote claims context | Implementado |
| Quotes | POST | `/api/v1/quotes/{quote_id}/clone` | postQuoteClone | Criar quote clone | Implementado |
| Quotes | GET | `/api/v1/quotes/{quote_id}/history` | getQuoteHistory | Obter quote history | Implementado |
| Quotes | GET | `/api/v1/quotes/{quote_id}/members` | getQuoteMemberListCreate | Listar quote member list create | Implementado |
| Quotes | POST | `/api/v1/quotes/{quote_id}/members` | postQuoteMemberListCreate | Criar quote member list create | Implementado |
| Quotes | DELETE | `/api/v1/quotes/{quote_id}/members/{member_id}` | deleteQuoteMemberDetail | Remover quote member detail | Implementado |
| Quotes | DELETE | `/api/v1/quotes/{quote_id}/members/{member_id}/pre-existing` | deleteQuoteMemberPreExisting | Remover quote member pre existing | Implementado |
| Quotes | PUT | `/api/v1/quotes/{quote_id}/members/{member_id}/pre-existing` | putQuoteMemberPreExisting | Substituir quote member pre existing | Implementado |
| Quotes | POST | `/api/v1/quotes/{quote_id}/policy` | postIssuePolicy | Criar issue policy | Implementado |
| Quotes | GET | `/api/v1/quotes/{quote_id}/policy-draft` | getPolicyDraft | Obter policy draft | Implementado |
| Quotes | POST | `/api/v1/quotes/{quote_id}/policy/emit` | postEmitPolicy | Criar emit policy | Implementado |
| Quotes | POST | `/api/v1/quotes/{quote_id}/preview` | postQuotePreview | Criar quote preview | Implementado |
| Quotes | POST | `/api/v1/quotes/{quote_id}/price` | postQuotePrice | Criar quote price | Implementado |
| Quotes | POST | `/api/v1/quotes/{quote_id}/renewal/indexation` | postQuoteIndexation | Criar quote indexation | Implementado |
| Quotes | POST | `/api/v1/quotes/{quote_id}/reopen` | postQuoteReopen | Criar quote reopen | Já implementado; faltava no contrato |
| Quotes | GET | `/api/v1/quotes/{quote_id}/requirements` | getQuoteRequirements | Obter quote requirements | Implementado |
| Quotes | GET | `/api/v1/quotes/{quote_id}/selection` | getQuoteSelection | Obter quote selection | Implementado |
| Quotes | PUT | `/api/v1/quotes/{quote_id}/selection` | putQuoteSelection | Substituir quote selection | Implementado |
| Quotes | POST | `/api/v1/quotes/{quote_id}/submit` | postQuoteSubmit | Criar quote submit | Implementado |
| Quotes | GET | `/api/v1/quotes/{quote_id}/versions` | getQuoteVersionListCreate | Listar quote version list create | Implementado |
| Quotes | POST | `/api/v1/quotes/{quote_id}/versions` | postQuoteVersionListCreate | Criar quote version list create | Implementado |
| Quotes | GET | `/api/v1/quotes/{quote_id}/versions/{version_no}` | getQuoteVersionDetail | Obter quote version detail | Implementado |
| Quotes | GET | `/api/v1/quotes/{quote_id}/versions/{version_no}/diff` | getQuoteVersionDiff | Obter quote version diff | Implementado |
| Quotes | POST | `/api/v1/quotes/{quote_id}/versions/{version_no}/restore` | postQuoteVersionRestore | Criar quote version restore | Implementado |
| Scenarios | GET | `/api/v1/quotes/{quote_id}/scenarios` | getQuoteScenarioListCreate | Listar quote scenario list create | Implementado |
| Scenarios | POST | `/api/v1/quotes/{quote_id}/scenarios` | postQuoteScenarioListCreate | Criar quote scenario list create | Implementado |
| Scenarios | GET | `/api/v1/quotes/{quote_id}/scenarios/compare` | getQuoteScenarioCompare | Obter quote scenario compare | Implementado |
| Scenarios | GET | `/api/v1/quotes/{quote_id}/scenarios/compare/export` | getQuoteScenarioCompareExport | Obter quote scenario compare export | Implementado |
| Scenarios | DELETE | `/api/v1/scenarios/{scenario_id}` | deleteScenarioDetail | Remover scenario detail | Implementado |
| Scenarios | GET | `/api/v1/scenarios/{scenario_id}` | getScenarioDetail | Obter scenario detail | Implementado |
| Scenarios | PATCH | `/api/v1/scenarios/{scenario_id}` | patchScenarioDetail | Alterar scenario detail | Implementado |
| Scenarios | POST | `/api/v1/scenarios/{scenario_id}/apply` | postScenarioApply | Criar scenario apply | Implementado |
| Scenarios | POST | `/api/v1/scenarios/{scenario_id}/clone` | postScenarioClone | Criar scenario clone | Implementado |
| Scenarios | POST | `/api/v1/scenarios/{scenario_id}/recalculate` | postScenarioRecalculate | Criar scenario recalculate | Implementado |
| Scenarios | POST | `/api/v1/scenarios/{scenario_id}/select` | postScenarioSelect | Criar scenario select | Implementado |
| Underwriting | POST | `/api/v1/quotes/{quote_id}/decision` | postQuoteDecision | Criar quote decision | Implementado |
| Underwriting | GET | `/api/v1/quotes/{quote_id}/review` | getQuoteReview | Obter quote review | Implementado |
| Underwriting | GET | `/api/v1/reviews` | getReviewQueue | Listar review queue | Implementado |
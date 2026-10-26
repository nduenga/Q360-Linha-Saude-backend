"""Per-endpoint documentation that static analysis cannot recover.

Key: "<ViewClass>.<method>". Fields (all optional):
  request   serializer class describing the request body
  response  serializer class (or {status: serializer}) describing the success body
  many      response is a list of `response`
  status    success status code (default: 200, or what the view returns)
  media     response media type for non-JSON bodies
  empty     success has no body
  queries   {name: (type, required, description)} for query parameters
  public    no authentication required
  notes     extra text appended to the operation description
"""
from __future__ import annotations

from config.openapi import doc_serializers as d

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
FILE_TYPE = {"fileType": ("string", False, "xlsx (por omissão) ou csv.")}
DRY_RUN = {"dryRun": ("boolean", False, "true: só simula, nada é gravado.")}

REGISTRY: dict[str, dict] = {
    "LiveHealthView.get": {"response": d.StatusOk, "public": True},
    "ReadyHealthView.get": {"response": {200: d.StatusOk, 503: d.StatusOk}, "public": True},
    # ------------------------------------------------------ system parameters
    "SystemParameterListView.get": {
        "response": d.SystemParameter, "many": True,
        "queries": {"category": ("string", False, "OPERATIONAL, STRUCTURAL, LEGAL, LIMIT ou MARKET.")},
    },
    "SystemParameterDetailView.get": {"response": d.SystemParameter},
    "ReferenceTableListView.get": {"response": d.ReferenceTableVersion, "many": True},
    "ReferenceTableDetailView.get": {"response": d.ReferenceTableVersion},
    "TemplateListView.get": {"response": d.TemplateVersion, "many": True},
    "TemplateDetailView.get": {"response": d.TemplateVersion},
    "TemplateAdoptView.post": {
        "request": d.TemplateAdoptRequest, "response": d.TemplateAdoptResult, "status": 201,
        "notes": "Copia cada configuração do modelo para um rascunho do tenant; nada é publicado.",
    },
    "PendingApprovalsCountView.get": {"response": d.PendingApprovalsCount},
    "ProductTariffView.get": {"response": d.ProductTariff},
    "ProductHistoryView.get": {"response": d.ProductHistoryEntry, "many": True, "notes": "Histórico de nome, descrição e estado do produto a partir de eventos de auditoria; não representa versões de tarifa ou configurações."},
    "ProductTariffSimulationView.post": {"response": d.TariffSimulationResult},
    "FormulaTestView.post": {"response": d.FormulaTestResult},
    "PendingApprovalsView.get": {"response": d.PendingApprovals, "queries": {"area": ("string", False, "ORGANIZATION, PRODUCTS, TARIFF, RULES, PARAMETERS ou DOCUMENTS.")}},
    "PolicyInclusionView.post": {
        "request": d.EndorsementInclusionRequest, "response": d.EndorsementState, "status": 201,
        "notes": "Cria a cotação de endosso (ENDORSEMENT) ligada à apólice ativa, com a data de inclusão como data de referência do cálculo, e calcula logo o prémio anual das pessoas indicadas.",
    },
    "PolicyEndorsementListView.get": {"response": d.PolicyEndorsements},
    "QuoteEndorsementView.get": {"response": d.EndorsementState},
    "QuoteEndorsementView.put": {
        "request": d.EndorsementDateRequest, "response": d.EndorsementState,
        "notes": "Só antes de submeter. Reavalia a elegibilidade e recalcula na nova data.",
    },
    "QuoteEndorsementResponseView.post": {
        "request": d.EndorsementClientResponse, "response": d.EndorsementState,
        "notes": "Resposta do cliente registada pelo GTE. ACCEPT aplica o endosso (pessoas, carências, prestações, endosso ADD_MEMBER); REFUSE cancela.",
    },
    "QuoteEndorsementDocumentView.get": {
        "media": "application/pdf", "queries": {"fileType": ("string", False, "pdf (por omissão), html ou docx.")},
        "notes": "Proposta de endosso; depois de aplicado, ata adicional.",
    },
    "CustomerPortalEndorsementListView.get": {"response": d.EndorsementState, "many": True},
    "CustomerPortalEndorsementResponseView.post": {"request": d.EndorsementClientResponse, "response": d.EndorsementState},
    "CustomerPortalEndorsementDocumentView.get": {"media": "application/pdf"},
    "FormulaVariablesView.get": {
        "response": d.FormulaVariablesCatalog,
        "queries": {"productId": ("string", False, "UUID do produto: junta os grupos, opções, campos e fórmulas dele."),
                    "usableIn": ("string", False, "PRICING_FORMULAS, PRICING_FORMULAS:PERSON, PRICING_FORMULAS:QUOTE, "
                                                  "PRODUCT_FORMULAS ou RULE_CONDITIONS.")},
    },
    "SystemParameterDetailView.put": {"request": d.SystemParameterUpdate, "response": d.SystemParameter},
    "SystemParameterRevisionsView.get": {"response": d.SystemParameterRevision, "many": True},
    "SystemParameterRollbackView.post": {"request": d.SystemParameterRollbackRequest, "response": d.SystemParameter},
    # ---------------------------------------------------------------- benefits
    "BenefitExportView.get": {
        "media": XLSX, "queries": {**FILE_TYPE, "category": ("string", False, "BASE ou COMPLEMENTARY."),
                                   "status": ("string", False, "ACTIVE, INACTIVE ou ALL (por omissão ALL)."),
                                   "q": ("string", False, "Pesquisa por nome ou código.")},
        "notes": "Devolve o ficheiro (XLSX ou CSV, conforme fileType).",
    },
    "BenefitImportView.post": {"request": d.BenefitImportRequest, "response": d.BenefitImportResult},
    "BenefitUsageView.get": {"response": d.BenefitUsage},
    "MemberImportUploadView.post": {"request": d.MemberImportRequest, "status": 202},
    "ImportTemplateView.get": {"media": XLSX, "notes": "Modelo Excel .xlsx com cabeçalhos, exemplo e instruções em português. kind: MEMBERS, CLAIMS, PREMIUMS ou BENEFITS."},
    "PlanValidationView.get": {"response": d.PlanValidation},
    "MarketTemplatesView.post": {"request": d.EmptyRequest, "response": d.MarketTemplatesResult},
    # -------------------------------------------------------- configuration
    "ConfigurationPublishView.post": {"request": d.EmptyRequest, "response": d.ConfigurationHeader},
    "ConfigurationRetireView.post": {"request": d.EmptyRequest, "response": d.ConfigurationHeader},
    "ConfigurationVersionsView.get": {"response": d.ConfigurationVersion, "many": True},
    "ConfigurationDiffView.get": {
        "response": d.ConfigurationDiff,
        "queries": {"against": ("string", True, "Id (UUID) de outra versão do mesmo código.")},
    },
    "ConfigurationRollbackView.post": {"response": d.ConfigurationRollbackResult},
    "ConfigurationImpactSimulationView.post": {"request": d.ImpactSimulationRequest, "response": d.ImpactSimulation},
    # ----------------------------------------------------------------- pricing
    "PricingPreviewView.post": {"response": d.PricingPreviewResponse},
    # -------------------------------------------------------------- quote sim.
    "QuotePreviewView.post": {"request": d.QuotePreviewRequest, "response": d.QuotePreviewResponse},
    "QuoteSelectionView.get": {"response": d.QuoteSelectionRead},
    "QuoteAdjustmentListCreateView.post": {
        "queries": DRY_RUN,
        "response": {201: d.AdjustmentApplied, 200: d.AdjustmentDryRun, 202: d.DiscountApprovalRequested},
        "notes": "dryRun=true devolve AdjustmentDryRun (200); aplicação imediata devolve 201; desconto acima do limite cria pedido de aprovação da Direção Técnica (202).",
    },
    "QuoteDiscountApprovalQueueView.get": {
        "response": d.QuoteDiscountApprovalQueue,
        "queries": {"status": ("string", False, "PENDING (por omissão), APPROVED, REJECTED ou ALL.")},
    },
    "QuoteDiscountApprovalDecisionView.post": {
        "request": d.QuoteDiscountApprovalDecision,
        "response": d.QuoteDiscountApproval,
        "notes": "Só Direção Técnica; exige nota de decisão e impede autoaprovação.",
    },
    "QuoteAdjustmentDetailView.delete": {"response": d.AdjustmentRemoved},
    "QuoteSelectionView.put": {"response": d.QuoteWithWarnings},
    "PlanBenefitDetailView.put": {"response": d.PlanBenefitConfigured},
    "QuoteMemberPreExistingView.put": {"response": d.PreExistingResult},
    "QuoteVersionDiffView.get": {
        "response": d.VersionDiff, "queries": {"against": ("integer", False, "N.º da outra versão (por omissão o estado atual).")},
    },
    "QuoteVersionRestoreView.post": {"response": d.VersionRestoreResult},
    "QuoteRequirementsView.get": {"response": d.Requirements},
    "QuoteClaimsContextView.get": {"response": d.ClaimsContext},
    "QuoteIndexationView.post": {"request": d.IndexationRequest, "response": d.IndexationResult, "queries": DRY_RUN},
    "QuoteScenarioCompareView.get": {
        "response": d.ScenarioCompare, "queries": {"ids": ("string", False, "Ids de cenários separados por vírgula (por omissão todos).")},
    },
    "QuoteScenarioCompareExportView.get": {
        "media": XLSX,
        "queries": {**FILE_TYPE, "ids": ("string", False, "Ids de cenários separados por vírgula.")},
    },
    "QuoteProposalPreviewView.get": {
        "media": "text/html", "queries": {"scenarioId": ("string", False, "Cenário (por omissão o selecionado)."),
                                          "templateCode": ("string", False, "Modelo (por omissão QUOTE_PROPOSAL_DEFAULT).")},
    },
    "DocumentDownloadView.get": {"media": "application/octet-stream", "notes": "Ficheiro gerado (PDF, DOCX ou HTML); verifica o checksum."},
    "DocumentRetryView.post": {"request": d.EmptyRequest},
    "DocumentSignedUrlView.post": {"request": d.EmptyRequest, "response": d.SignedUrl, "status": 201},
    "DocumentSignedDownloadView.get": {"media": "application/octet-stream", "public": True, "notes": "O token assinado é a credencial; expira (documents.signed_url_ttl_seconds)."},
    "DocumentTemplateSchemaView.get": {"response": d.TemplateSchema},
    "DocumentTemplatePreviewView.get": {
        "media": "text/html", "queries": {"fileType": ("string", False, "html (por omissão), pdf ou docx.")},
    },
    "DocumentTemplatePublishView.post": {"request": d.EmptyRequest},
    "DocumentTemplateRetireView.post": {"request": d.EmptyRequest},
    "QuoteProposalView.post": {"request": d.EmptyRequest},
    "ScenarioRecalculateView.post": {"request": d.EmptyRequest},
    "ScenarioSelectView.post": {"request": d.EmptyRequest},
    # ------------------------------------------------------------------ policy
    "PolicyCoverageView.get": {
        "response": d.PolicyCoverage,
        "queries": {"memberId": ("string", False, "Omitir verifica todos os membros."),
                    "date": ("string", False, "YYYY-MM-DD (por omissão hoje)."),
                    "benefitCategory": ("string", False, "Código da cobertura a verificar."),
                    "eventType": ("string", False, "ACCIDENT: a carência não se aplica onde o plano o indica; ILLNESS (por omissão).")},
    },
    "CoverageLookupView.get": {
        "response": d.PolicyCoverage,
        "queries": {"policyNumber": ("string", True, "Número da apólice."),
                    "memberId": ("string", False, "Omitir verifica todos os membros."),
                    "date": ("string", False, "YYYY-MM-DD (por omissão hoje)."),
                    "benefitCategory": ("string", False, "Código da cobertura a verificar."),
                    "eventType": ("string", False, "ACCIDENT: a carência não se aplica onde o plano o indica; ILLNESS (por omissão).")},
    },
    "DocumentTemplateLetterheadView.get": {"media": "application/pdf", "notes": "O papel timbrado carregado."},
    "DocumentTemplateWordView.get": {
        "media": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "notes": "O modelo Word carregado.",
    },
    "PolicyDraftView.get": {"response": d.PolicyDraft},
    "MemberDocumentListCreateView.get": {"response": d.MemberDocumentsOverview},
    "MemberDocumentListCreateView.post": {"response": {201: d.MemberDocumentItem}, "status": 201},
    "MemberDocumentQueueView.get": {
        "response": d.MemberDocumentQueueItem,
        "queries": {"status": ("string", False, "SUBMITTED (por omissão, a aguardar análise), APPROVED, REJECTED ou ALL."),
                    "memberId": ("string", False, "Só os documentos desta pessoa segura.")},
        "notes": "Fila de análise do GTE.",
    },
    "MemberDocumentDownloadView.get": {"media": "application/octet-stream", "notes": "Ficheiro original enviado (PDF, JPG ou PNG)."},
    "MemberDocumentReviewView.post": {"response": d.MemberDocumentReviewResult},
    "CustomerPortalMemberDocumentsView.get": {"response": d.MemberDocumentsOverview},
    "CustomerPortalMemberDocumentsView.post": {"response": {201: d.MemberDocumentItem}, "status": 201},
    "InstallmentListView.get": {
        "response": d.CollectionInstallment,
        "queries": {"status": ("string", False, "DUE (por pagar), OVERDUE (atrasadas) ou PAID."),
                    "dueBefore": ("string", False, "AAAA-MM-DD: vencimento até esta data."),
                    "policyNumber": ("string", False, "Número da apólice."),
                    "q": ("string", False, "Nome do tomador (contém).")},
        "notes": "Cobranças: as prestações de todas as apólices, para registar pagamentos.",
    },
    "RegisterFirstPremiumPaymentView.post": {"response": d.PaymentRegistered},
    "EmitPolicyView.post": {"response": {201: d.EmittedPolicy}, "status": 201},
    "PolicyDocumentView.get": {
        "media": "application/pdf", "queries": {"fileType": ("string", False, "pdf (por omissão), html ou docx.")},
        "notes": "Apólice digital. O PDF gravado na emissão é servido tal e qual.",
    },
    # ------------------------------------------------------------------ claims
    "ClaimsImportListCreateView.post": {"request": d.ClaimsImportRequest, "response": {201: d.ClaimsImportResult, 200: d.ClaimsImportResult}},
    "ClaimsMethodologyView.get": {"response": d.ClaimsMethodology},
    "ClaimsImportTemplateView.get": {
        "media": XLSX, "queries": {"kind": ("string", False, "CLAIMS (por omissão) ou PREMIUMS.")},
        "notes": "Excel .xlsx com cabeçalhos, exemplo e instruções em português.",
    },
    "ClaimsSummaryView.get": {
        "response": d.ClaimsSummary,
        "queries": {"proposerId": ("string", True, "Cliente."), "policyId": ("string", False, "Apólice."),
                    "from": ("string", False, "YYYY-MM-DD."), "to": ("string", False, "YYYY-MM-DD."),
                    "currency": ("string", False, "AOA (por omissão) ou USD.")},
    },
    "ClaimsExperienceRatingView.get": {
        "response": {200: d.ExperienceRating, 409: d.ExperienceRating},
        "queries": {"proposerId": ("string", True, "UUID do cliente."),
                    "policyId": ("string", False, "UUID da apólice."),
                    "currency": ("string", False, "AOA (por omissão) ou USD.")},
        "notes": "Fator calculado segundo pricing.experience_rating; é informativo e não altera a cotação por este endpoint.",
    },
    "ClaimsProfitSharingView.get": {
        "response": d.ProfitSharing,
        "queries": {"proposerId": ("string", True, "Cliente."), "policyId": ("string", False, "Apólice."),
                    "thresholdPct": ("string", False, "Limite de sinistralidade acordado (por omissão 65)."),
                    "sharePct": ("string", False, "Quota devolvida (por omissão 100)."),
                    "from": ("string", False, "YYYY-MM-DD."), "to": ("string", False, "YYYY-MM-DD."),
                    "currency": ("string", False, "AOA (por omissão) ou USD.")},
    },
    "DashboardView.get": {
        "response": d.OperationalDashboard,
        "queries": {"page": ("integer", False, "Página, começa em 0."),
                    "size": ("integer", False, "Itens por página, máximo 200."),
                    "proposerId": ("string", False, "Filtra cotações por cliente."),
                    "trendPeriod": ("string", False, "week ou month (por omissão month).")},
    },
    # ------------------------------------------------------------------ portal
    "CustomerPortalPlanBenefitsView.get": {
        "response": d.PortalPlanBenefits, "queries": {"policyNumber": ("string", True, "Número da apólice do cliente.")},
    },
    "CustomerPortalQuotesView.get": {"response": d.PortalQuotes},
    "GlobalSearchView.get": {
        "response": d.GlobalSearchResult,
        "queries": {"q": ("string", False, "Texto a pesquisar (mínimo 2 caracteres).")},
    },
    "FirstAccessRequestView.post": {"response": d.PortalMaskedEmail, "status": 202, "public": True},
    "FirstAccessConfirmView.post": {"response": d.PortalToken, "public": True},
    "PasswordLoginView.post": {"response": d.PortalToken, "public": True},
    "PasswordResetRequestView.post": {"empty": True, "status": 202, "public": True},
    "PasswordResetConfirmView.post": {"response": d.PortalToken, "public": True},
    "CustomerPortalDashboardView.get": {"response": d.PortalDashboard},
    "CustomerPortalQuoteDetailView.get": {"response": d.PortalQuoteDetail},
    "CustomerPortalPolicyListView.get": {
        "response": d.PortalPolicyList,
        "queries": {"phase": ("string", False, "ACTIVE, EXPIRING, RENEWED, EXPIRED, CANCELLED ou OTHER.")},
    },
    "CustomerPortalPolicyDetailView.get": {"response": d.PortalPolicyDetail},
    "CustomerPortalPolicyHistoryView.get": {"response": d.PortalPolicyHistory},
    "CustomerPortalCardView.get": {"response": d.PortalCard},
    "CustomerPortalBeneficiariesView.get": {"response": d.PortalBeneficiaries},
    "CustomerPortalPaymentsView.get": {
        "response": d.PortalPayments,
        "queries": {"status": ("string", False, "DUE, PAID ou OVERDUE.")},
    },
    "CustomerPortalDocumentsView.get": {"response": d.PortalDocuments},
    "CustomerPortalDocumentDownloadView.get": {"media": "application/octet-stream"},
    "CustomerPortalPolicyDocumentView.get": {
        "media": "application/pdf", "queries": {"fileType": ("string", False, "pdf (por omissão), html ou docx.")},
        "notes": "A apólice digital.",
    },
    "CustomerPortalPolicyStatementView.get": {
        "media": "application/pdf",
        "queries": {"kind": ("string", False, "COVERAGE (declaração de cobertura, por omissão) ou PAYMENT (comprovativo)."),
                    "installmentNo": ("string", False, "Só em PAYMENT: n.º da prestação paga (por omissão a última).")},
        "notes": "Gerado na hora; sem pedido ao GTE.",
    },
    "CustomerPortalProfileView.get": {"response": d.PortalProfile},
    "CustomerPortalRequestsView.get": {
        "response": d.PortalRequestList,
        "queries": {"status": ("string", False, "OPEN, IN_REVIEW, AWAITING_CUSTOMER, APPROVED, REJECTED ou COMPLETED.")},
    },
    "CustomerPortalRequestsView.post": {"request": d.PortalRequestCreate, "response": d.PortalRequestDetail, "status": 201},
    "CustomerPortalRequestDetailView.get": {"response": d.PortalRequestDetail},
    "CustomerPortalRequestSatisfactionView.post": {
        "request": d.RequestSatisfactionCreate, "response": d.RequestSatisfactionResult, "status": 201,
        "notes": "Só pedidos resolvidos; uma avaliação por pedido.",
    },
    "CustomerPortalRequestTypesView.get": {"response": d.PortalRequestTypes},
    "CustomerPortalMessagesView.get": {
        "response": d.PortalMessages,
        "queries": {"contextType": ("string", True, "QUOTE, POLICY ou REQUEST."),
                    "contextRef": ("string", True, "Número da cotação, da apólice ou do pedido.")},
    },
    "CustomerPortalMessagesView.post": {"request": d.PortalMessageCreate, "response": d.PortalMessages, "status": 201},
    "CustomerPortalConversationsView.get": {"response": d.PortalConversations},
    "CustomerPortalNotificationsView.get": {
        "response": d.PortalNotifications,
        "queries": {"unread": ("boolean", False, "true devolve só as não lidas.")},
    },
    "CustomerPortalNotificationsReadView.post": {"request": d.PortalMarkRead, "response": d.PortalMarkReadResult},
    "CustomerPortalRenewalView.get": {"response": d.PortalRenewal},
    "CustomerPortalPlanCompareView.get": {
        "response": d.PortalPlanCompare,
        "queries": {"policyNumber": ("string", True, "Número da apólice do cliente.")},
    },
    "PortalRequestListView.get": {
        "response": d.StaffPortalRequestList,
        "queries": {"status": ("string", False, "OPEN, IN_REVIEW, AWAITING_CUSTOMER, APPROVED, REJECTED ou COMPLETED."),
                    "type": ("string", False, "Tipo do pedido.")},
    },
    "PortalRequestMetricsView.get": {"response": d.PortalRequestMetrics},
    "PortalRequestDetailView.get": {"response": d.StaffPortalRequestDetail},
    "PortalRequestTransitionView.post": {"request": d.StaffPortalTransition, "response": d.StaffPortalRequestDetail},
    "PortalConversationListView.get": {
        "response": d.StaffPortalConversations,
        "queries": {"unread": ("boolean", False, "true devolve só conversas com mensagens do cliente por ler.")},
    },
    "PortalStaffMessagesView.get": {
        "response": d.PortalMessages,
        "queries": {"contextType": ("string", True, "QUOTE, POLICY ou REQUEST."),
                    "contextRef": ("string", True, "Número da cotação, da apólice ou do pedido.")},
    },
    "PortalStaffMessagesView.post": {"request": d.PortalMessageCreate, "response": d.PortalMessages, "status": 201},
    "CustomerPortalCoverageView.get": {
        "response": d.PolicyCoverage,
        "queries": {"policyNumber": ("string", True, "Número da apólice do cliente."),
                    "memberId": ("string", False, "Omitir verifica todos os membros."),
                    "date": ("string", False, "YYYY-MM-DD (por omissão hoje)."),
                    "benefitCategory": ("string", False, "Código da cobertura."),
                    "eventType": ("string", False, "ACCIDENT ou ILLNESS (por omissão).")},
    },
}

# Staff authentication/administration (apps.staff_accounts).
from apps.staff_accounts.interfaces import serializers as _staff  # noqa: E402

REGISTRY.update(
    {
        "LoginView.post": {"response": _staff.TokenResponseSerializer, "public": True},
        "RefreshView.post": {"response": _staff.TokenResponseSerializer, "public": True},
        "LogoutView.post": {"empty": True, "status": 204},
        "StaffAccountListCreateView.get": {"response": _staff.StaffAccountSerializer, "many": True},
        "StaffAccountListCreateView.post": {"response": _staff.StaffAccountSerializer, "status": 201},
        "StaffAccountRolesView.patch": {"response": _staff.StaffAccountSerializer},
        "StaffAccountStatusView.patch": {"response": _staff.StaffAccountSerializer},
        "StaffAccountResetPasswordView.post": {"request": d.EmptyRequest, "response": _staff.GeneratedPasswordSerializer},
        "StaffAccountUnlockView.post": {"request": d.EmptyRequest, "empty": True, "status": 204},
    }
)

# Business configuration (apps.business_config).
from apps.business_config.interfaces import serializers as _bc  # noqa: E402

REGISTRY.update(
    {
        "BCCatalogView.get": {"response": _bc.BusinessConfigurationCatalogSerializer},
        "BCConfigurationListCreateView.get": {
            "response": _bc.BusinessConfigurationListSerializer,
            "queries": {"configKey": ("string", False, "Chave do catálogo."),
                        "status": ("string", False, "DRAFT, PENDING_APPROVAL, PUBLISHED ou RETIRED.")},
        },
        "BCConfigurationListCreateView.post": {
            "request": _bc.BusinessConfigurationWriteSerializer,
            "response": _bc.BusinessConfigurationSerializer, "status": 201,
        },
        "BCConfigurationDetailView.get": {"response": _bc.BusinessConfigurationSerializer},
        "BCConfigurationDetailView.put": {
            "request": _bc.BusinessConfigurationUpdateSerializer, "response": _bc.BusinessConfigurationSerializer,
            "notes": "Só versões DRAFT. rowVersion desatualizado devolve VERSION-CONFLICT.",
        },
        "BCConfigurationDetailView.post": {
            "request": _bc.BusinessConfigurationActionSerializer, "response": _bc.BusinessConfigurationSerializer,
            "notes": "action=submit (DRAFT para PENDING_APPROVAL) ou retire (PUBLISHED para RETIRED).",
        },
        "BCConfigurationApproveView.post": {
            "request": d.EmptyRequest, "response": _bc.BusinessConfigurationSerializer,
            "notes": "Publica a versão. O criador não pode aprovar (SEC-403).",
        },
        "BCDocumentListView.get": {"response": _bc.BusinessConfigurationDocumentListSerializer},
        "BCDocumentUploadView.post": {
            "request": _bc.BusinessConfigurationDocumentUploadSerializer,
            "response": _bc.BusinessConfigurationDocumentSerializer, "status": 201,
        },
        "BCDocumentDownloadView.get": {"media": "application/octet-stream"},
    }
)

# Platform administration (apps.platform_admin) - super administrators only.
from apps.platform_admin.interfaces import serializers as _pl  # noqa: E402

REGISTRY.update(
    {
        "PlatformLoginView.post": {"request": _pl.PlatformLoginSerializer, "response": _pl.PlatformLoginResponseSerializer, "public": True},
        "PlatformMeView.get": {"response": _pl.PlatformAdminSerializer},
        "PlatformChangePasswordView.post": {"request": _pl.ChangePasswordSerializer, "empty": True, "status": 204},
        "PlatformTenantListCreateView.get": {
            "response": _pl.TenantResponseSerializer, "many": True,
            "queries": {"status": ("string", False, "ACTIVE, SUSPENDED ou INACTIVE."), "q": ("string", False, "Pesquisa por código ou nome.")},
        },
        "PlatformTenantListCreateView.post": {
            "request": _pl.CreateTenantSerializer, "response": _pl.CreateTenantResponseSerializer, "status": 201,
            "notes": "Cria o tenant, os dados da empresa e o primeiro ADMIN; a palavra-passe temporária só aparece nesta resposta.",
        },
        "PlatformTenantDetailView.get": {"response": _pl.TenantDetailSerializer},
        "PlatformTenantDetailView.patch": {
            "request": _pl.UpdateTenantSerializer, "response": _pl.TenantResponseSerializer,
            "notes": "Suspender (SUSPENDED/INACTIVE) bloqueia de imediato o staff e o portal do tenant.",
        },
        "PlatformTenantAdminsView.post": {"request": _pl.CreatePlatformAdminSerializer, "response": _pl.TemporaryPasswordResponseSerializer, "status": 201},
        "PlatformTenantAccountResetView.post": {"request": d.EmptyRequest, "response": _pl.TemporaryPasswordResponseSerializer},
        "PlatformAdminListCreateView.get": {"response": _pl.PlatformAdminSerializer, "many": True},
        "PlatformAdminListCreateView.post": {"request": _pl.CreatePlatformAdminSerializer, "response": _pl.CreatePlatformAdminResponseSerializer, "status": 201},
        "PlatformAdminStatusView.patch": {"request": _pl.UpdatePlatformAdminStatusSerializer, "response": _pl.PlatformAdminSerializer},
        "PlatformAdminResetPasswordView.post": {"request": d.EmptyRequest, "response": _pl.TemporaryPasswordResponseSerializer},
        "PlatformFormulaEngineView.get": {
            "response": d.PlatformFormulaEngine,
            "notes": "Só leitura: funções, operadores, limites e variáveis do motor de fórmulas e os campos/ações/etapas "
                     "das regras. As fórmulas e regras de negócio são de cada tenant.",
        },
        "PlatformParameterListView.get": {
            "response": d.PlatformParameter, "many": True,
            "queries": {"level": ("string", False, "PLATFORM_MANDATORY ou PLATFORM_DEFAULT."),
                        "category": ("string", False, "OPERATIONAL, STRUCTURAL, LEGAL, LIMIT ou MARKET.")},
        },
        "PlatformParameterDetailView.get": {"response": d.PlatformParameter},
        "PlatformParameterVersionsView.get": {"response": d.PlatformParameterVersion, "many": True},
        "PlatformParameterVersionsView.post": {
            "request": d.PlatformParameterProposalWithSource, "response": d.PlatformParameterVersion, "status": 201,
            "notes": "Fica PENDING_APPROVAL até outra conta da plataforma a aprovar. Uma pendente de cada vez (CONFLICT).",
        },
        "PlatformParameterApproveView.post": {
            "request": d.PlatformParameterDecision, "response": d.PlatformParameterVersion,
            "notes": "Quem propôs não pode aprovar (SEC-403). Vale a partir da vigência indicada ou da aprovação.",
        },
        "PlatformParameterRejectView.post": {"request": d.PlatformParameterDecision, "response": d.PlatformParameterVersion},
        "PlatformParameterRollbackView.post": {
            "request": d.PlatformParameterRollbackRequest, "response": d.PlatformParameterVersion, "status": 201,
            "notes": "Cria uma versão nova (pendente de aprovação) com o valor de uma versão publicada anterior.",
        },
        "PlatformReferenceTableListView.get": {"response": d.ReferenceTableSummary, "many": True,
                                               "notes": "Uma linha por tabela: versão em vigor (sem as linhas) e pendentes."},
        "PlatformReferenceTableListView.post": {
            "request": d.ReferenceTableProposal, "response": d.ReferenceTableVersion, "status": 201,
            "notes": "Versão nova da tabela inteira, PENDING_APPROVAL até outra conta a aprovar.",
        },
        "PlatformReferenceTableImportTemplateView.get": {"media": XLSX, "notes": "Modelo Excel em português para propor uma tabela de referência."},
        "PlatformReferenceTableImportPreviewView.post": {"request": d.PlatformReferenceTableImportPreviewRequest, "response": d.PlatformReferenceTableImportPreviewResult},
        "PlatformReferenceTableDetailView.get": {"response": d.ReferenceTableDetail},
        "PlatformReferenceTableVersionsView.get": {"response": d.ReferenceTableVersion, "many": True},
        "PlatformReferenceTableApproveView.post": {
            "request": d.PlatformParameterDecision, "response": d.ReferenceTableVersion,
            "notes": "Quem propôs não pode aprovar (SEC-403).",
        },
        "PlatformReferenceTableRejectView.post": {"request": d.PlatformParameterDecision, "response": d.ReferenceTableVersion},
        "PlatformTemplateListView.get": {"response": d.TemplateSummary, "many": True},
        "PlatformTemplateDetailView.get": {"response": d.TemplateDetail},
        "PlatformTemplateListView.post": {
            "request": d.TemplateProposal, "response": d.TemplateVersion, "status": 201,
            "notes": "O conteúdo é validado como configuração do tenant; um modelo não muda de tipo.",
        },
        "PlatformTemplateVersionsView.get": {"response": d.TemplateVersion, "many": True},
        "PlatformTemplateApproveView.post": {"request": d.PlatformParameterDecision, "response": d.TemplateVersion},
        "PlatformTemplateRejectView.post": {"request": d.PlatformParameterDecision, "response": d.TemplateVersion},
        "PlatformAuditView.get": {
            "response": _pl.PlatformAuditEventSerializer, "many": True,
            "queries": {"action": ("string", False, "Ação."), "entityType": ("string", False, "Tipo de entidade."),
                        "entityId": ("string", False, "Id da entidade."), "actorId": ("string", False, "Quem fez."),
                        "limit": ("integer", False, "Máximo 500 (por omissão 100).")},
        },
    }
)

# Views kept only while tenants migrate to the business configuration
# (`manage.py migrate_legacy_tariffs`, then `/products/{id}/tariff`):
# marked `deprecated` in the contract.
DEPRECATED_VIEWS = {
    "RatingTableCreateView",
    "RatingTableDetailView",
    "PricingParameterSetCreateView",
    "PricingParameterSetDetailView",
}
DEPRECATION_NOTE = (
    "Obsoleto: tarifa antiga. Converta-a com `manage.py migrate_legacy_tariffs` e use a configuração de negócio "
    "(`/business-config/configurations`, `/products/{id}/tariff`). Deixa de ser usada quando o tenant publica "
    "`pricing.reference_premiums`."
)

# Approved ART-006 component schemas whose operation no longer exists: the
# merge keeps untouched approved schemas, so these are dropped explicitly.
# `QuoteUpdateRequest` only changed the quote's effective date, which quotes
# no longer have (decision of 2026-10-15; `PUT /quotes/{id}` removed).
RETIRED_SCHEMAS = {"QuoteUpdateRequest"}

# Operations documented by the approved ART-006 contract with a richer schema
# than the code exposes through a serializer: keep the contract's version.
KEEP_CONTRACT = {
    ("/api/v1/me", "get"),
    ("/api/v1/customer-portal/{tenant_id}/auth/request-access", "post"),
    ("/api/v1/customer-portal/{tenant_id}/auth/verify-otp", "post"),
    ("/api/v1/customer-portal/me", "get"),
    ("/api/v1/customer-portal/eligibility", "post"),
}

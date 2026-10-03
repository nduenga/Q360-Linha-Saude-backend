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
        "queries": {"category": ("string", False, "OPERATIONAL ou STRUCTURAL.")},
    },
    "SystemParameterDetailView.get": {"response": d.SystemParameter},
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
        "response": {201: d.AdjustmentApplied, 200: d.AdjustmentDryRun},
        "notes": "dryRun=true devolve AdjustmentDryRun (200); caso contrário 201 com {adjustment, quote, impact}.",
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
    # ------------------------------------------------------------------ claims
    "ClaimsImportListCreateView.post": {"request": d.ClaimsImportRequest, "response": {201: d.ClaimsImportResult, 200: d.ClaimsImportResult}},
    "ClaimsMethodologyView.get": {"response": d.ClaimsMethodology},
    "ClaimsImportTemplateView.get": {
        "media": "text/csv", "queries": {"kind": ("string", False, "CLAIMS (por omissão) ou PREMIUMS.")},
        "notes": "CSV com o cabeçalho aceito e uma linha de exemplo fictícia.",
    },
    "ClaimsSummaryView.get": {
        "response": d.ClaimsSummary,
        "queries": {"proposerId": ("string", True, "Cliente."), "policyId": ("string", False, "Apólice."),
                    "from": ("string", False, "YYYY-MM-DD."), "to": ("string", False, "YYYY-MM-DD."),
                    "currency": ("string", False, "AOA (por omissão) ou USD.")},
    },
    "ClaimsProfitSharingView.get": {
        "response": d.ProfitSharing,
        "queries": {"proposerId": ("string", True, "Cliente."), "policyId": ("string", False, "Apólice."),
                    "thresholdPct": ("string", False, "Limite de sinistralidade acordado (por omissão 65)."),
                    "sharePct": ("string", False, "Quota devolvida (por omissão 100)."),
                    "from": ("string", False, "YYYY-MM-DD."), "to": ("string", False, "YYYY-MM-DD."),
                    "currency": ("string", False, "AOA (por omissão) ou USD.")},
    },
    # ------------------------------------------------------------------ portal
    "CustomerPortalPlanBenefitsView.get": {
        "response": d.PortalPlanBenefits, "queries": {"policyNumber": ("string", True, "Número da apólice do cliente.")},
    },
    "CustomerPortalQuotesView.get": {"response": d.PortalQuotes},
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
        "PlatformAuditView.get": {
            "response": _pl.PlatformAuditEventSerializer, "many": True,
            "queries": {"action": ("string", False, "Ação."), "entityType": ("string", False, "Tipo de entidade."),
                        "entityId": ("string", False, "Id da entidade."), "actorId": ("string", False, "Quem fez."),
                        "limit": ("integer", False, "Máximo 500 (por omissão 100).")},
        },
    }
)

# Operations documented by the approved ART-006 contract with a richer schema
# than the code exposes through a serializer: keep the contract's version.
KEEP_CONTRACT = {
    ("/api/v1/me", "get"),
    ("/api/v1/dashboard", "get"),
    ("/api/v1/customer-portal/{tenant_id}/auth/request-access", "post"),
    ("/api/v1/customer-portal/{tenant_id}/auth/verify-otp", "post"),
    ("/api/v1/customer-portal/me", "get"),
    ("/api/v1/customer-portal/eligibility", "post"),
}

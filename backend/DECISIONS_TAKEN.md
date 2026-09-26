# DECISÕES TOMADAS — para destravar o teste fluido dos Sprints 1-5

**Contexto:** este ficheiro regista decisões **técnicas/de teste** tomadas
directamente para que a plataforma seja simples de usar e testar de ponta a
ponta. Não substitui `OPEN_DECISIONS.md` (que continua a existir e a listar
a mesma lista, agora com uma nota "ver DECISIONS_TAKEN.md" em cada entrada
resolvida aqui) — é o registo formal do que foi decidido, quando, e porquê.

**O que este ficheiro NÃO faz:** não inventa valores de negócio reais
(tarifas, prémios, moeda oficial, catálogo regulatório de relações
familiares). Onde a decisão substitui um valor de negócio genuíno (ex.:
OD-001 tarifas, OD-002 moeda/arredondamento oficial), a decisão aqui é
explicitamente **um valor de teste/demonstração**, não uma aprovação de
negócio — continua a precisar de validação do Product Owner/Actuarial antes
de produção. Isto é uma extensão do mesmo princípio "nunca inventar" — só
que agora documentado como decisão explícita, não como bloqueio.

**Autoridade:** decisões tomadas a pedido directo do Product Owner do
projecto (2026-09-12): "resolva todas as decisões do open_decisions, para
que os teste do s1-s5 seja mais fluido".

---

## S01-AUTH-001 — Identity Provider (OD-009)

**Decisão:** para desenvolvimento/teste, usa-se sempre o escape-hatch
`OIDC_STATIC_VERIFICATION_KEY` (HS256, claims `tenant_id`/`roles`/`scope`)
via `manage.py issue_dev_token` — ver `DEV_SETUP.md`. Nenhum IdP real é
necessário para testar S1-S5.
**Ainda em aberto para produção:** qual IdP concreto (Keycloak/Auth0/Azure
AD) — `config/settings/production.py` já recusa arrancar sem isso
configurado, por isso não há risco de isto "escapar" para produção por
engano.

## S02-CONTRACT-001 — Benefit/PlanBenefit sem endpoint

**Decisão:** fora de âmbito para o teste fluido de S1-S5. Planos são
testados/usados sem detalhe de benefícios (o campo não aparece em lado
nenhum da UI). Sem alteração de código.

## S02-PRODUCT-VERSION-OVERLAP

**Decisão:** mantém-se o comportamento actual (verificação à criação,
contra todas as versões DRAFT+PUBLISHED do mesmo produto) como definitivo
para V1. Sem alteração de código.

## S03-RELATIONSHIP-001 — Catálogo de códigos de relação

**Decisão:** adoptado um catálogo de teste/demonstração:

| Código | Rótulo (UI) |
|---|---|
| `TITULAR` | Titular |
| `CONJUGE` | Cônjuge |
| `FILHO` | Filho(a) |
| `OUTRO` | Outro |

Aplicado como `<select>` em `Q360-Linha-Sa-de-frontend/src/domains/customer/CustomerPage.tsx`
(campo "Relação" ao adicionar um membro) — o utilizador escolhe de uma
lista, não escreve texto livre. **Não é enforced no backend** (o campo
`insured_member.relationship_code` continua `varchar(40)` livre, ART-005 —
alterar isso exigiria uma Change Request à DDL, fora de âmbito): a
validação acontece só do lado do frontend. A regra "dependente requer
titular" continua **não implementada** (precisaria de saber qual código é
"titular" com autoridade real, que é exactamente o que este catálogo de
teste não tem).
**Ainda em aberto para produção:** o catálogo oficial/regulatório de
relações familiares deve vir do Product Owner antes de produção.

## S03-IMPORT-001 — Importação de membros (3 escolhas de implementação)

**Decisão:** as três escolhas já documentadas (armazenamento do ficheiro,
mapeamento de colunas CSV, `proposerId` obrigatório no commit) ficam
**aceites como definitivas para V1**. Sem alteração de código.

## S03-ELIGIBILITY-001 — Critérios de referral/warning

**Decisão:** a forma `Criterion` (relationshipCodes/minAge/maxAge, AND
dentro de uma entrada, OR entre entradas) fica **aceite como definitiva
para V1**, incluindo para teste. Não são critérios médicos reais (ART-008 é
explícito: nenhum critério médico é inventado em V1).

## S04-ROUNDING-001 — Moeda e política de arredondamento (OD-002)

**Decisão de teste/demonstração** (não é o valor de negócio aprovado —
OD-002 continua `BLOCKED-SPEC` para produção):
- **Arredondamento:** `ROUND_HALF_UP` a 2 casas decimais, aplicado a cada
  componente do cálculo (já implementado em
  `apps/pricing/domain/money.py`, código `OD-002-PLACEHOLDER-HALF-UP-2DP`).
- **Moeda de demonstração:** AOA (Kwanza) para dados de demonstração
  reais; `TST` continua reservado a fixtures puramente técnicas (golden
  tests ART-013).
**Ainda em aberto para produção:** política oficial de arredondamento e
moeda(s) suportada(s) — decisão do Actuarial/Product Owner.

## S04-PRICING-CONTEXT-001 — Como resolver RatingTable/PricingParameterSet

**Decisão:** mantém-se a convenção `context.ratingTableCode`/
`parameterSetCode`/`ruleVersionCode` (contrato do `POST
/api/v1/pricing/calculate` inalterado). A simplificação para o utilizador
foi feita do lado da UI, não do contrato: `PricingPage.tsx` já não pede
para escrever esses códigos à mão — são `<select>` preenchidos a partir
dos endpoints de listagem novos (ver S04-LISTING-GAPS-001) e
pré-seleccionados automaticamente quando só há uma opção publicada.

## S04-CROSS-MODULE-001 — Leitura directa entre módulos

**Decisão:** aceite como padrão definitivo para V1 (pricing/eligibility
importam modelos de product/client directamente). Um refactor para
ports/adapters fica registado como dívida técnica, não bloqueante.

## S04-LISTING-GAPS-001 — Endpoints de listagem em falta — RESOLVIDO

**Decisão:** adicionados 4 endpoints `GET` de listagem, todos seguindo o
mesmo padrão (paginação `Q360PageNumberPagination`, serializers já
existentes, sem nenhum campo/valor de negócio inventado):

| Endpoint | Filtro opcional |
|---|---|
| `GET /api/v1/products/{productId}/versions` | — |
| `GET /api/v1/rating-tables` | `?status=` |
| `GET /api/v1/pricing-parameter-sets` | `?status=` |
| `GET /api/v1/rule-versions` | `?ruleDomain=`, `?status=` |

Estes endpoints **não estão no ART-006** (que só define `POST` para os
três recursos versionados) — são uma extensão pragmática de V1, puramente
de leitura, sem qualquer decisão de negócio embutida. Testado em
`tests/product/test_products.py::test_list_product_versions`,
`tests/product/test_pricing_parameters.py::test_list_pricing_parameter_sets`,
`tests/pricing/test_rating_tables.py::test_list_rating_tables` e
`tests/eligibility/test_evaluate_api.py::test_list_rule_versions_filters_by_domain`.
**Acção futura recomendada:** Product Owner/Tech Lead deve submeter uma
Change Request ao ART-006 para os incluir formalmente no contrato — até
lá, ficam documentados aqui como extensão V1, não como parte do contrato
aprovado.

## seed-data-from-art-011 — Uso dos dados oficiais de bootstrap (2026-09-12)

**Decisão:** carregado `Q360_MVP_ART_011_Seed_Data_v1.0.sql` (o artefacto
oficial de seed, que este projecto tinha lido mas nunca executado) na base
de dados local, em vez de continuar a inventar tenants/produtos de teste
ad-hoc. Isto cria:
- Tenant `Q360-DEMO` (`00000000-0000-7000-8000-000000000001`).
- 4 RuleSets técnicos (ELIGIBILITY_V1/PRICING_V1/WORKFLOW_V1/VALIDATION_V1)
  com RuleVersions v1 em DRAFT (sem conteúdo de regras — o seed proíbe
  explicitamente valores de negócio, ver PROH-005 no workbook ART-011).
- Produto `HEALTH-DEMO` (DRAFT), versão 1 (DRAFT, `effective_from
  2000-01-01`), plano `DEMO-BASE`, benefício `DEMO-BENEFIT`.
- Shells vazios `DEMO-PARAMS` (parameter set) e `DEMO-RATING` (rating
  table) — o seed tem uma verificação própria (`DO $$ ... RAISE
  EXCEPTION`) que impede a existência de `rating_factor`/`pricing_parameter`
  nestes IDs específicos, precisamente para nunca conter tarifas.
Como esses dois shells ficam propositadamente vazios para sempre (por
desenho do ART-011), os dados de teste reais (factores/parâmetros/membros)
foram acrescentados como uma **v2** dos mesmos códigos
(`DEMO-RATING`/`DEMO-PARAMS`), publicada, com valores não-redondos
(ex.: prémio base `87.35`, factores `0.85`–`2.87`) para se distinguir
claramente de coincidência com números redondos e demonstrar o
arredondamento a funcionar. A versão 1 original do seed nunca é alterada.
**Nota:** o tenant de teste `dev-tenant` criado antes desta sessão
continua a existir e a funcionar — `Q360-DEMO` é agora o tenant
recomendado para testes/demonstração daqui para a frente.

## product-status-transition — Como activar um produto (2026-09-12)

**Decisão:** `ProductUpdateRequest` (ART-006) não tem nenhum campo
`status` — não existe **nenhuma** forma documentada de mover um Product
para fora de `DRAFT`. Isto não é um bug: `Product.status` (ciclo de vida
comercial) e `ProductVersion.status` (ciclo de vida de uma configuração
concreta) são dois campos independentes em ART-005, e o próprio ART-011
mantém o seu produto de demonstração em `DRAFT` propositadamente mesmo
depois de a versão ser publicada (CHK-008 "Draft-only commercial
shells") — publicar uma versão nunca deveria activar o produto
implicitamente.
Adicionado `status` como campo opcional e retrocompatível a
`ProductUpdateRequestSerializer`/`update_product` (pragmático, não em
ART-006 — mesma categoria que S04-LISTING-GAPS-001), exposto no frontend
como um `<select>` na página de detalhe do produto.
**Ainda em aberto para produção:** ART-006 deveria ganhar este campo (ou
um endpoint de transição de estado dedicado) via Change Request.

## age-band-buckets — Faixas etárias calculadas automaticamente (2026-09-12)

**Decisão de teste/demonstração** (não é uma tabela actuarial aprovada):
para que o utilizador da página Pricing nunca precise de escrever
`{"ageBand": "30-39"}` à mão, a dimensão `ageBand` usada para resolver
`RatingFactor` passa a ser **calculada automaticamente** a partir da data
de nascimento real do membro (já existente em `insured_member`) e da data
de referência do cálculo, usando estes escalões:

`0-17`, `18-29`, `30-39`, `40-49`, `50-59`, `60-69`, `70+`

Implementado em `Q360-Linha-Sa-de-frontend/src/domains/pricing/services/ageBand.ts`.
Um membro sem data de nascimento não tem `ageBand` calculado (o factor
correspondente só se aplica se a `RatingTable` tiver uma entrada de
fallback com `dimensions: {}`, comportamento já existente e testado desde
S4-01). Isto não altera o backend nem o contrato `context` — é só o
frontend a deixar de pedir ao utilizador algo que já pode calcular
sozinho.
**Ainda em aberto para produção:** os escalões etários oficiais (se
existirem regras actuariais específicas) são uma decisão do Product
Owner/Actuarial.

## S05-PRICING-RULES-001 — Forma das regras de pricing

**Decisão:** a forma `PricingRuleConfig`/`PricingAdjustment` (lista de
`{code, when, amount}`, aplicada aditivamente) fica **aceite como
definitiva para V1**, incluindo para teste.

## S05-RULE-FOUR-EYES-001 — Four-eyes na publicação de regras

**Decisão:** **não aplicado em V1.** Qualquer actor com scope `q360.admin`
pode publicar uma `RuleVersion` sozinho — `approved_by` fica sempre `NULL`
(a `CHECK` do schema permite isso). Isto é uma simplificação deliberada
para desbloquear o teste fluido de S5-01; não é uma alteração de segurança
para produção.
**Ainda em aberto para produção:** requer Change Request ao ART-006 (novo
campo/endpoint) antes de poder ser aplicado.

---

## S06-QUOTE-001 — Judgment calls made building Quote Core (Sprint 6, 2026-09-14)

ART-006/ART-009/ART-012 fix `Quote`'s schema, endpoints and state values
precisely, but leave several mechanisms unspecified. Decisions taken to
build a complete, working Sprint 6:

1. **Becoming READY is automatic, not a manual command.** ART-006 has no
   `/quotes/{id}/ready` endpoint, and ART-009's QT-001 guard ("valid
   pricing exists") is exactly what a successful `priceQuote` produces.
   `apps/quote/application/quote_service.price_quote` therefore promotes
   DRAFT→READY as a side effect of a successful calculation whose
   population has no `EXCLUDED` member, matching QT-001's stated guard
   ("no HARD_STOP/CONFIG_ERROR"). Any member add/remove or `effectiveDate`
   edit on a READY quote demotes it back to DRAFT (QT-002), per ART-009's
   own "Atomic Side Effects" column.
2. **Eligibility decision → `quote_member.status` mapping** (ART-012 V020
   only has INCLUDED/EXCLUDED/REFERRAL, ART-006 doesn't define the
   mapping): ELIGIBLE/WARNING → INCLUDED, REFERRAL → REFERRAL,
   HARD_STOP/CONFIG_ERROR → EXCLUDED (fail-closed, consistent with
   S03-ELIGIBILITY-001's own fail-closed posture). EXCLUDED members are
   never sent to the pricing engine; REFERRAL members still are (a
   provisional price while manual underwriting decides, not yet built —
   Sprint 7).
3. **Default quote validity** (`Quote.valid_until`, `QuoteCreateRequest`
   has no such field — it's server-computed): `QUOTE_DEFAULT_VALIDITY_DAYS`
   setting (env-configurable, default 30), not a business-approved value.
4. **Quote numbering**: `quote_number` is left `NULL` at creation — no
   numbering convention is invented (matches ART-011 PROH-008's own
   prohibition on inventing one). **Updated 2026-09-19
   (ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 4, OD-ANGOLA-005):** at
   **approval** it is now assigned a sequential number via the same
   `numbering_service.next_value` already used for document numbers —
   still explicitly a test/demo identifier (a simple incrementing string
   per year), never a real ARSEG policy-number format, which PROH-008
   still prohibits inventing. This exists only so "apólice" can mean
   "the quoteNumber of an approved Quote" for the Épico 4 lookup-by-
   number flow, without inventing a new `Policy` entity.
5. **RatingTable/PricingParameterSet auto-resolution for Quote pricing**
   (`QuotePriceRequest` is just `{recalculate: bool}` — no `context` at
   all, so the client can never name a code): resolves the single
   PUBLISHED code effective on the date, exactly mirroring the frontend's
   own `resolveLatestPerCode` — see
   `apps/pricing/application/auto_resolve.py`. Ambiguous/missing
   configuration fails the same way as standalone pricing
   (`PRICING-CONFIG`, 422).
6. **`GET /quotes/{id}/members`** (pragmatic V1 addition, not in ART-006):
   `Quote` itself has no population field, so there is no other way for
   the frontend to show who is on the quote.

## S07-REVIEW-001 — Judgment calls made building the review workflow (Sprint 7, 2026-09-14)

1. **No `START_REVIEW` endpoint.** ART-006 has no way to move a
   `ReviewTask` OPEN→IN_PROGRESS (RV-001) — only `getQuoteReview`,
   `decideQuote` and `listReviews` exist. `ReviewTask.status` therefore
   goes straight OPEN→DECIDED/RETURNED; `assigned_to`/`started_at` remain
   unset in V1. Not invented — genuinely absent from the contract.
2. **Segregation of duties enforced for all three decisions, not just
   APPROVE.** ART-009's "Commands & Authority" sheet marks "Four-eyes: Yes"
   only for APPROVE, but ART-012's `ck_decision_four_eyes` CHECK
   (`submitted_by IS NULL OR decided_by <> submitted_by`) applies
   unconditionally to every `quote_decision` row regardless of `decision`
   value. The stricter, DB-enforced rule was taken as authoritative
   (DOC-000 P-08): the submitter can decide (approve/reject/return)
   nothing about their own submission.
3. **Authority policy (OD-005) absence = unrestricted, not fail-closed.**
   `AuthorityPolicy` (ART-012 V022) has no CRUD/publish endpoint in
   ART-006 at all, unlike RatingTable/PricingParameterSet/RuleVersion — so
   there is no channel to configure a real limit yet. Scope (`q360.approve`)
   + DOC-001 `quote:approve` already gate *who* may decide; absent a
   policy, *how much* is left unrestricted rather than blocking every
   approval on an OD that has no way to be resolved via the API. Once
   OD-005 is closed and a Change Request adds the endpoint, this
   automatically starts enforcing real limits (`_resolve_authority_limit`
   already reads `policy_json.maxApprovalAmount` when a policy exists).
4. **`review_note` (ART-012 V023) has no endpoint** — same posture as
   `Benefit`/`PlanBenefit` (S02-CONTRACT-001): table exists, no API surface
   in this version.
5. **Decision-type → DOC-001 permission mapping** (Commands & Authority
   sheet uses "underwriting:review"/"underwriting:decide", not present in
   DOC-001's own matrix — that matrix already fixes `quote:approve`/
   `quote:reject`/`quote:review`): APPROVE→`quote:approve`,
   REJECT→`quote:reject`, RETURN→`quote:review`, all still gated by the
   single `q360.approve` OAuth2 scope ART-006 attaches to `decideQuote`.

## S08-DOCUMENT-001 — Judgment calls made building documents/finalization (Sprint 8, 2026-09-14)

1. **`DocumentTemplateVersion` gets its own dedicated create/publish
   endpoints** (`POST /api/v1/document-templates`,
   `POST /api/v1/document-templates/{id}/publish`), not the shared
   `/configuration/{configType}/{configId}/publish` dispatcher used by
   RatingTable/PricingParameterSet/RuleVersion — that endpoint's
   `configType` is a **closed enum** in ART-006 (exactly those three
   values); adding a fourth would silently violate the documented schema.
   A dedicated pair is the only way to add this without either inventing
   an enum value or reusing the shared one incorrectly.
2. **"Generation" produces a placeholder JSON artifact, not a real PDF.**
   OD-006 ("template oficial da proposta") is genuinely unresolved — no
   approved template content/branding/legal text exists anywhere. The
   generated file is a labeled JSON summary of the APPROVAL snapshot
   (reproducible, checksummed, satisfies S8-01's own AC), explicitly
   marked as a placeholder. `DEFAULT_TEMPLATE_CODE =
   "QUOTE_PROPOSAL_DEFAULT"` is this module's own fixture convention (same
   posture as pricing's `BASE_PREMIUM` parameter code) — an Admin must
   create and publish one before any proposal can be generated at all
   (fails closed with `NOT-FOUND` otherwise).
3. **Numbering (OD-007/OD-008) mechanism is real, the format is a
   placeholder.** `numbering_service.next_value` guarantees no duplicate
   number under concurrency (proven with real threads, not just
   sequential calls) using `select_for_update`; the actual prefix/suffix
   policy is unset (empty) until a real numbering convention is approved.
4. **`generateQuoteProposal` requires `Quote.status == APPROVED`** and an
   existing APPROVAL `QuoteSnapshot` — neither ART-006 nor ART-009 states
   this explicitly, but `Document` has no other defined trigger, and a
   "proposal" logically reflects the approved snapshot the AC names
   ("Documento reflecte snapshot").
5. **Cancelling an `IN_REVIEW` quote leaves its `ReviewTask` untouched.**
   QT-009's side effect ("Close/void active review task consistently")
   has no matching value in `ck_review_status` (only OPEN/IN_PROGRESS/
   DECIDED/RETURNED — none means "voided") — forcing one of those would
   misrepresent what happened. Left as a known gap rather than invented.
6. **Document template management reuses the `product:manage` DOC-001
   permission** — no dedicated "document:manage" permission exists in
   DOC-001's matrix, and `product:manage` already covers "Admin/Product
   Configurator does config work" for every other versioned config
   resource in this project.
7. **`expire_quotes` is a management command, not a background job.** No
   task queue exists in this stack (DOC-002 s4: "no messaging without a
   real consumer") — an external scheduler (cron/Task Scheduler/CronJob)
   is expected to invoke it periodically in deployment; it is idempotent
   and safe to re-run.

## S09-IDEMPOTENCY-001 — Tenant scoping do middleware de idempotência (2026-09-18)

**Contexto:** `IdempotencyMiddleware` corre antes da autenticação DRF do
`APIView` (é middleware Django puro, não um `authentication_class`), logo
`CurrentTenantProvider` pode ainda não estar vinculado quando
`IdempotencyService.begin/complete/fail` precisam de ler/escrever
`idempotency_record`. Uma tentativa anterior "resolveu" isto enfraquecendo
`TenantScopedManager.get_queryset()` de fail-closed (`CurrentTenantProvider.require()`)
para fail-open (devolver todas as linhas sem tenant vinculado) — isto
quebra o invariante de segurança usado por **todos** os outros modelos de
negócio (DOC-001 s20) e foi revertido.

**Decisão:** `TenantScopedManager` mantém-se fail-closed. `idempotency_service.py`
usa explicitamente `IdempotencyRecord.all_tenants` (o escape-hatch já
documentado em `tenant_scoping.py` para jobs que legitimamente precisam de
funcionar sem contexto de tenant vinculado) e passa `tenant_id` como filtro
explícito em cada query — nunca depende do filtro implícito do manager.

**Known issue resolvido (2026-09-24):** `tests/foundation/test_idempotency.py::test_same_key_different_body_returns_409_idemp_replay`
passava isoladamente mas falhava intermitentemente a seguir a outro teste
na mesma sessão. Causa raiz real (nada a ver com Postgres/Testcontainers,
nem específica de `all_tenants`): `IdempotencyMiddleware` tem dois caminhos
de retorno antecipado (o 409 `IdempotencyReplayError` e o short-circuit de
resposta repetida) que devolvem a resposta **sem chamar
`self.get_response(request)`** — e é só dentro dessa chamada que
`ActorContextCleanupMiddleware` (mais interno na lista `MIDDLEWARE`) corre
e limpa `CurrentActorProvider`. Nesses dois caminhos, o actor que o próprio
`IdempotencyMiddleware` vincula (para resolver o tenant antes da
autenticação DRF, linha ~143) ficava "pendurado" no contextvar e era
reutilizado pelo pedido seguinte tratado pela mesma worker thread — daí o
tenant errado (o do pedido *anterior*) aparecer na segunda chamada deste
teste. Corrigido em `apps/foundation/interfaces/middleware.py`: os dois
caminhos de retorno antecipado agora limpam a vinculação antes de devolver
a resposta. `test_same_key_same_body_is_replayed` também foi corrigido — a
sua asserção final dependia acidentalmente da mesma fuga para conseguir
correr `Product.objects.filter(...)` fora de qualquer pedido HTTP; passou a
usar `Product.all_tenants.filter(tenant_id=tenant.id, ...)` explicitamente,
o padrão já documentado acima para este cenário.

## S09-OUTBOX-EVENT-FIELDS-001 — Gap de campos ART-007 em QUOTE.SUBMITTED/APPROVED (2026-09-18)

**Contexto:** `tests/integration/test_outbox_event_catalog.py` (AC-5) provou
que `QUOTE.SUBMITTED` e `QUOTE.APPROVED`/`REJECTED`/`RETURNED` são emitidos
com `eventType` exacto e `aggregateType` correcto, mas os seus `payload`
não incluem todos os campos que o catálogo ART-007 declara:
- `QUOTE.SUBMITTED` declara `quoteId, snapshotId, reviewTaskId, submittedBy,
  submittedAt, status` — `quote_service.submit_quote` só emite
  `quoteId, submittedBy, submittedAt`.
- `QUOTE.APPROVED`/`REJECTED`/`RETURNED` declaram `quoteId, snapshotId,
  decisionId, decidedBy, decidedAt, status` — `quote_service.decide_quote`
  emite `quoteId, decision, reasonCode, reasonText, decidedBy,
  approvedAt|rejectedAt` (nomes e campos diferentes, `decision`/`reasonCode`/
  `reasonText` não fazem parte do contrato para estes três eventos).

**Decisão:** documentado como gap de fidelidade ao contrato, não corrigido
nesta sessão (implicaria expor `snapshot.id`/`decision.id` até
`quote_service.py`'s outbox call sites, que hoje não os têm à mão sem mais
refactor). O teste de catálogo asserta apenas os campos realmente emitidos,
com uma nota inline apontando para esta entrada. Nenhum consumidor real
existe ainda (ART-007 Non-Goal para V1), pelo que não há impacto funcional
imediato — mas qualquer consumidor futuro que dependa de `snapshotId`/
`decisionId`/`status` nestes dois eventos vai falhar até isto ser corrigido.

## Fora de âmbito desta resolução

**OD-001 (tarifas/prémios reais)** não é resolvido aqui e não pode ser —
não há autoridade actuarial para inventar valores comerciais reais. Todos
os dados usados em testes/demonstração (`BASE_PREMIUM`, `RatingFactor`,
`PricingAdjustment`) continuam a ser fixtures técnicas explícitas, nunca
tarifas Angolanas reais, exactamente como antes desta resolução.

## S09-POLICY-001 — Apólice como contrato separado da cotação; fim das versões de produto (2026-09-26)

**Contexto:** pedido directo do Product Owner (conversa 2026-09-26,
`ROADMAP_APOLICES.md`) para tratar a apólice como um contrato distinto da
cotação, com elegibilidade de subscrição (motor `evaluate()`, inalterado)
separada de elegibilidade de cobertura (nova, `apps.policy`). Um parecer
jurídico externo, recebido na mesma conversa, apontou 3 desconformidades
ao desenho inicial — duas confirmadas contra fonte pública, uma (art.
428.º do Código Comercial) ainda por confirmar pelo jurídico do cliente,
tratada como prática de mercado configurável entretanto.

**Decisões do Product Owner (PO-APO-1..7), ver `ROADMAP_APOLICES.md` para
o detalhe completo:**

1. **PO-APO-1**: o que transforma uma cotação em contrato é a
   **assinatura** do tomador — nunca a aprovação por si só.
2. **PO-APO-2**: um membro com elegibilidade pendente bloqueia **só o seu
   próprio registo** na apólice, nunca a emissão.
3. **PO-APO-3**: a duração do contrato é definida no momento da emissão
   (não vem do produto nem da cotação).
4. **PO-APO-5** (substitui a PO-APO-4 original, "sem suspensão", revogada
   pelo parecer jurídico): o pagamento do prémio é condição de cobertura —
   Decreto n.º 2/02 de 11/02, art. 17.º (a 1.ª fracção paga-se na data da
   celebração) e art. 18.º (falta de pagamento dá lugar a suspensão por
   carta registada com novo prazo, e só depois a resolução — nunca
   suspensão automática e imediata).
5. **PO-APO-6**: deixam de existir "versões" de produto na plataforma —
   só produtos e planos. Ver Fase 1 de `ROADMAP_APOLICES.md` para o
   racional (o snapshot de aprovação da cotação tinha de passar a guardar
   o conteúdo integral do plano antes de este deixar de ser imutável por
   versão, para não abrir uma janela onde editar um plano alterasse
   retroactivamente o que já foi contratado).
6. **PO-APO-7**: o mediador (corretor/agente) é validado contra a licença
   ARSEG antes da emissão — Lei n.º 6/24 de 03/06 (Mediação e Corretagem
   de Seguros). Não existe API pública da ARSEG; a validação é feita
   contra um registo interno mantido pelo compliance a partir da lista
   pública de entidades autorizadas, nunca uma integração inventada
   (mantém DOC-000 s3 P-08).

**Superseded por esta decisão** (histórico mantido, não apagado):
- **OD-ANGOLA-005** ("apólice = `Quote.quoteNumber` de uma cotação
  `APPROVED`", Épico 4 de `ROADMAP_ANGOLA_CUSTOMIZATION.md`): substituída
  por uma entidade `Policy` real (`apps.policy`, Fase 2+ de
  `ROADMAP_APOLICES.md`).
- **Épico 2** (versionamento automático do produto, OD-ANGOLA-003/004) e
  **Épico 3** (produtos sem data de término, `ProductVersion.effective_to`):
  substituídos pela Fase 1 de `ROADMAP_APOLICES.md` — `Plan` liga
  directamente a `Product`, sem `ProductVersion`, com estados
  `ACTIVE`/`INACTIVE` a fazer o papel que a versão fazia.
- **OD-ANGOLA-009** ("versão antiga nunca inicia negócio novo"):
  reformulada como "plano `INACTIVE` nunca inicia negócio novo, mas
  cotações/apólices existentes continuam válidas" — o mesmo princípio,
  aplicado ao novo modelo sem versões.

Nenhum valor de negócio (prazos de tolerância de pagamento, taxas de
comissão, franquias) é inventado nesta decisão — o que a lei angolana
exige mas não quantifica fica registado como Open Decision em
`ROADMAP_APOLICES.md` e implementado como configurável.

## S09-PORTAL-002 — request-access deixa de ser sempre 202 silencioso (2026-09-26)

**Contexto:** o desenho original de `ROADMAP_PORTAL_CLIENTE.md` Fase 0
fazia `POST /customer-portal/{tenant}/auth/request-access` responder
sempre `202`, mesmo quando `quoteNumber`/`registrationNumber` não
correspondiam a nada — para nunca confirmar a um chamador não autenticado
que um número de cotação real existe.

**Decisão do Product Owner (2026-09-26):** passa a responder de forma
explícita:
- `404 PORTAL-QUOTE-NOT-FOUND` quando `quoteNumber` não corresponde a
  nenhuma cotação `APPROVED`;
- `401 PORTAL-REGISTRATION-MISMATCH` quando `quoteNumber` é real mas
  `registrationNumber` não corresponde ao tomador dessa cotação.

**Controlo compensatório:** um limite de pedidos **por IP**
(`apps.customer_portal.interfaces.rate_limit.is_ip_rate_limited`),
independente do limite por email já existente, porque `email` não é
verificado antes deste ponto — um chamador pode variar o email em cada
pedido e contornar um limite só por email. As duas verificações correm
em conjunto; qualquer uma delas bloqueia o pedido com `429`.

**Efeito:** troca deliberada de sigilo anti-enumeração por feedback mais
claro ao cliente final — aceite como troca válida dado o controlo
compensatório acima. Código:
`apps/customer_portal/domain/errors.py` (`PortalQuoteNotFoundError`,
`PortalRegistrationMismatchError`), `apps/customer_portal/application/
auth_service.py` (`_resolve_proposer` levanta em vez de devolver `None`),
`apps/customer_portal/interfaces/rate_limit.py` (`is_ip_rate_limited`),
`apps/foundation/interfaces/exception_handler.py` (títulos PT dos 2 novos
códigos), `config/settings/base.py`
(`CUSTOMER_PORTAL_LOGIN_RATE_LIMIT_PER_IP`/`_WINDOW_SECONDS_PER_IP`).
Testado em `tests/customer_portal/test_portal_auth_api.py`
(`test_request_access_reports_quote_not_found_for_a_nonexistent_quote`,
`test_request_access_reports_registration_mismatch_for_a_real_quote`).

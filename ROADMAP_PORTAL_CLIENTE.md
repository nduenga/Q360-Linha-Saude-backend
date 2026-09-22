# Roadmap — Portal do Cliente (autoatendimento para o segurado final)

**Estado:** Fase 0 (Fundação técnica) **implementada** (2026-09-22) — ver
secção própria abaixo para código/testes. Fase 1+ ainda não iniciadas.

Projecto à parte, de prazo mais longo, pedido explicitamente como um
roadmap separado (não faz parte dos Épicos 0-6 de
`ROADMAP_ANGOLA_CUSTOMIZATION.md`, nem do V1 definido em DOC-002/DOC-003).
Público-alvo: o **cliente final segurado** (titular de uma cotação
`APPROVED`), nunca staff — é um sistema de acesso novo, com o seu próprio
contrato, nunca misturado com o backoffice actual.

**Porquê um roadmap à parte e não mais um épico:** os Épicos 0-6
extendem o backoffice existente (actors staff, roles DOC-001 §18, scopes
OAuth2 internos `q360.*`). O Portal do Cliente introduz um **tipo de
actor novo** que hoje não existe em lado nenhum do sistema — é reflectido
em código real, não só em intenção: o CHECK constraint
`ck_audit_actor_type` em `audit_event` (ver
`apps/foundation/infrastructure/migrations/0001_foundation_baseline.py`)
só permite `'USER'`, `'SYSTEM'`, `'SERVICE'` hoje — um cliente final não
cabe em nenhum destes três sem uma decisão e uma migration explícitas.

---

## Fase 0 — Fundação técnica (pré-requisito das 3 fases seguintes)

### Pedido
Antes de qualquer ecrã de "consultar a minha apólice", precisa de existir
uma forma segura de um cliente final se identificar e de o sistema saber
**exactamente a que cotação/proposer ele tem direito de aceder — e a mais
nenhum outro**.

### Estado actual
- `Actor` (`apps/foundation/domain/actor.py`) já tem um campo
  `actor_type: str = "USER"`, usado hoje só com `"SYSTEM"` (jobs como
  `expire_quotes.py`) e `"USER"` (staff via `JwtActorAdapter`). Isto é
  reaproveitável: um actor-cliente pode ser um `actor_type` novo (ex.
  `"CUSTOMER"`) em vez de inventar uma classe paralela.
- `TenantScopedModel`/`CurrentTenantProvider` já garantem isolamento por
  tenant (seguradora) — mas não isolamento **dentro** do mesmo tenant
  entre clientes diferentes. Isso é uma fronteira de segurança nova, que
  não existe hoje em lado nenhum (staff sempre viu todos os dados do seu
  tenant).
- Não existe nenhuma tabela de credenciais de cliente final. `Proposer`
  (`apps/client/infrastructure/models.py`) tem `registration_number`
  (BI/NIF) e `attributes_json`, mas nenhum campo de password/OTP/telefone
  verificado — e não deve ganhar esses campos directamente (um Proposer
  pode ser referenciado por múltiplas cotações ao longo do tempo; misturar
  credenciais de login no mesmo registo acopla identidade de login a
  dados de subscrição).
- `Role`/`Permission`/`Scope` (DOC-001 §18) são todos desenhados para
  staff — não devem ser estendidos com um "role" de cliente; APENAS o
  módulo de portal deve decidir o que um actor `CUSTOMER` pode fazer,
  fora da matriz DOC-001.

### Objectivo
Um mecanismo de autenticação e autorização **novo e isolado**, que nunca
reaproveita os scopes/roles internos, para não criar uma forma acidental
de um cliente final herdar permissões de staff.

### Tarefas — IMPLEMENTADAS (2026-09-22)
- [x] Nova tabela `customer_account` (schema `q360`, `TenantScopedModel`,
      migration nova, nunca editando as existentes): liga-se a um ou mais
      `Proposer` do mesmo tenant (uma pessoa pode ter mais que uma
      cotação/apólice ao longo do tempo). Guarda apenas o necessário para
      autenticar — não duplica dados já em `Proposer`.
      - `apps/customer_portal/infrastructure/models.py`
        (`CustomerAccount`, `CustomerAccountProposer` — a tabela de junção
        do OD-PORTAL-002, `CustomerLoginChallenge` para o OTP) +
        `apps/customer_portal/infrastructure/migrations/0001_customer_portal_baseline.py`.
- [x] Mecanismo de login **fora** do fluxo OAuth2/OIDC staff: número de
      apólice (`Quote.quoteNumber`) + número de documento de identificação
      (`Proposer.registrationNumber`) + código OTP por email
      (OD-PORTAL-001).
      - `apps/customer_portal/application/auth_service.py`
        (`CustomerPortalAuthService.request_access`/`verify_otp`),
        `apps/customer_portal/infrastructure/otp.py` (hash via
        `django.contrib.auth.hashers`, nunca em texto simples),
        `apps/customer_portal/infrastructure/email_sender.py` (via
        `django.core.mail`, backend configurável por ambiente — console em
        dev, locmem em testes, SMTP/API real a configurar em produção via
        `EMAIL_*`).
      - `apps/customer_portal/infrastructure/portal_token.py`: token de
        sessão próprio (`CUSTOMER_PORTAL_JWT_SECRET`, nunca `SECRET_KEY`
        nem uma chave OIDC), 30 min por omissão
        (`CUSTOMER_PORTAL_TOKEN_TTL_SECONDS`), sem refresh token nesta
        fase.
      - Endpoints: `POST /api/v1/customer-portal/{tenantId}/auth/request-access`
        e `POST /api/v1/customer-portal/{tenantId}/auth/verify-otp`
        (`apps/customer_portal/interfaces/views.py`). `{tenantId}` vem do
        path — decisão de implementação adicional, não coberta por
        OD-PORTAL-001..004: o frontend do portal é publicado por tenant e
        já conhece o seu próprio `tenantId`; o único papel deste valor é
        seleccionar em que tenant a consulta corre, nunca autorizar nada
        por si só — a verificação real continua a ser o par
        quoteNumber+registrationNumber(+OTP).
      - Resposta de `request-access` é sempre `202`, exista ou não uma
        correspondência real, para nunca confirmar a um chamador não
        autenticado que um dado número de apólice/documento existe.
- [x] `actor_type="CUSTOMER"` em `Actor`, com `roles=frozenset()` sempre
      vazio e um novo mecanismo de permissão *específico do portal*, não
      DOC-001 §18.
      - `apps/foundation/domain/actor.py` (`Actor.actor_type="CUSTOMER"`,
        já suportado antes desta fase) +
        `apps/customer_portal/interfaces/authentication.py`
        (`CustomerPortalJwtAuthentication`, isolada de
        `JwtActorAuthentication`) +
        `apps/customer_portal/interfaces/permissions.py`
        (`IsCustomerPortalActor`, não `require_scope`).
- [x] `CurrentActorProvider`/middleware: quando `actor_type="CUSTOMER"`,
      toda a query tem de ser adicionalmente filtrada por
      `proposer_id IN (<os do customer_account autenticado>)`.
      - `Actor.customer_proposer_ids: frozenset[str]` (novo campo,
        `apps/foundation/domain/actor.py`, opaco — sem import de
        `apps.client` em `foundation`, DOC-004 s3.1) preenchido pelo
        `PortalTokenService`/`CustomerPortalJwtAuthentication` a partir do
        token; `apps/customer_portal/infrastructure/scoping.py`
        (`require_customer_proposer_ids`) é o acessor fail-closed que a
        Fase 1 (ainda não construída) deve usar em vez de ler o campo do
        Actor directamente.
- [x] Estender `ck_audit_actor_type` (migration nova) para incluir
      `'CUSTOMER'`.
      - `apps/foundation/infrastructure/migrations/0004_customer_actor_type.py`;
        `CustomerPortalAuthService` audita
        `customer_portal.access_requested`/`otp_failed`/`login_succeeded`
        via o `AuditService` já existente.
- [x] Rate limiting mais agressivo que o actual nos endpoints públicos de
      login do portal.
      - `apps/customer_portal/interfaces/rate_limit.py`
        (`CUSTOMER_PORTAL_LOGIN_RATE_LIMIT`/`_WINDOW_SECONDS`, por omissão
        10/60s por tenant+IP+email) — soma-se ao `RateLimitMiddleware`
        global, não o substitui.
      - Lockout por conta (distinto do rate limit por IP):
        `apps/customer_portal/domain/lockout.py`, política pura testada em
        `backend/tests/customer_portal/test_lockout_domain.py` — ver
        OD-PORTAL-003.
- [x] Namespace de URLs novo e isolado, `/api/v1/customer-portal/...`
      (`apps/customer_portal/interfaces/urls.py`, incluído em
      `config/urls.py`) — nunca reaproveita os paths do backoffice.
- Testes: `backend/tests/customer_portal/` (`test_lockout_domain.py`,
  `test_portal_token.py`, `test_scoping.py` — puros, sem BD, todos
  verdes; `test_portal_auth_api.py` — integração real via
  `@pytest.mark.django_db`, mesmo padrão de
  `tests/eligibility/test_evaluate_api.py`, não corrida neste ambiente por
  falta de Docker/Postgres local, tal como os testes de API já existentes
  do módulo eligibility).
- **Deliberadamente fora desta fase**: nenhum endpoint autenticado de
  leitura (`GET /me`, etc.) foi construído — isso é Fase 1, que depende
  desta fundação estar fechada primeiro, exactamente como este roadmap
  pede.

### Open Decisions — RESOLVIDAS (Product Owner, 2026-09-22)
- **OD-PORTAL-001** — RESOLVIDA: email OTP apenas (não SMS). Razão: evita
  depender de um contrato com gateway SMS angolano ainda por escolher;
  `Proposer`/`CustomerAccount` já não precisam de um campo de telefone
  verificado nesta fase.
- **OD-PORTAL-002** — RESOLVIDA: muitos-para-um via NIF. Um
  `CustomerAccount` pode agregar vários `Proposer` do mesmo tenant ao
  longo do tempo, através da tabela de junção `CustomerAccountProposer`.
- **OD-PORTAL-003** — RESOLVIDA: 5 tentativas falhadas → bloqueio de 30
  minutos, com reset automático. `apps/customer_portal/domain/lockout.py`.
- **OD-PORTAL-004** — RESOLVIDA: novo app Django (`apps.customer_portal`)
  no mesmo backend, reaproveitando os serviços de aplicação já existentes
  em processo (sem chamada de rede interna) — proposta por omissão do
  próprio roadmap, confirmada.

---

## Fase 1 — Consulta de elegibilidade e estado da apólice (MVP) — IMPLEMENTADA (2026-09-22)

### Pedido
Depois de autenticado (Fase 0), o cliente final deve conseguir ver o
estado da sua própria apólice sem ligar para o call center.

### Objectivo
O mínimo útil e seguro: ver que apólice tem, que plano/coberturas
contratou, e se está elegível.

### Tarefas
- [x] `GET /api/v1/customer-portal/me` — devolve o(s)
      `Quote.quoteNumber` associados ao `customer_account` autenticado,
      status (`APPROVED`/etc.), plano e produto (reaproveita
      `QuoteSerializer`/`ProductSerializer`/`ProductVersionSerializer`/
      `PlanSerializer` já existentes, tal como pedido — nenhum serializer
      novo/mais magro nesta fase, isso fica para a Fase 2). Restringido
      via `apps.customer_portal.application.self_service.list_my_quotes`,
      que filtra por `proposer_id IN (<proposers ligados ao
      customer_account>)` (`require_customer_proposer_ids`, Fase 0).
      Sem `{tenantId}` no path — ao contrário dos 2 endpoints de login,
      este já vem autenticado pelo token do portal, que já traz o
      `tenant_id`.
- [x] `GET /api/v1/customer-portal/coverage?quoteNumber=` — coberturas
      contratadas no plano, via `list_plan_benefits` de
      `apps/product/application/benefit_service.py` (Épico 1), sem
      alteração nenhuma a esse serviço.
- [x] `POST /api/v1/customer-portal/eligibility` `{quoteNumber,
      memberId?}` — reaproveita `EvaluateEligibilityUseCase.execute()`
      já existente, chamado com `proposer_id`/`plan_id`/
      `product_version_id`/`effective_date` resolvidos do próprio
      `Quote` (nunca do pedido); se `memberId` for omitido avalia todos
      os membros da apólice, se for dado tem de pertencer a essa mesma
      apólice (verificado via `QuoteMember`) — nunca aceita um
      `memberId` de outra pessoa.
      Código: `apps/customer_portal/application/self_service.py`
      (`list_my_quotes`, `resolve_my_quote` — resolução scoped, nunca
      confia num `quoteNumber` sem verificar que pertence ao chamador) e
      `apps/customer_portal/interfaces/self_service_views.py`.
      `resolve_my_quote`/o `memberId` inexistente na apólice devolvem o
      mesmo `404 NOT-FOUND` (`PortalResourceNotFoundError`) quer o
      recurso não exista quer pertença a outro cliente — nunca confirma
      a existência de uma apólice alheia.
      Testes: `backend/tests/customer_portal/test_self_service_api.py`
      (isolamento entre clientes, 401 sem token, 404 em apólice/membro
      alheios) — mesmo padrão de integração via `@pytest.mark.django_db`
      dos restantes testes de API deste projecto.

### Open Decisions
- Nenhuma nova além das da Fase 0 — esta fase foi mesmo, como previsto,
  só composição de serviços de aplicação já existentes e testados.

---

## Fase 2 — Self-service básico (documentos e dados)

### Pedido
Reduzir mais pedidos ao call center: descarregar a proposta já emitida,
ver os dependentes associados.

### Tarefas
- [ ] `GET /api/v1/customer-portal/documents/proposal` — reaproveitar
      `document_service`/`GET /quotes/{id}/proposal` já existente,
      restrito ao(s) `quote_id` do `customer_account` autenticado.
- [ ] `GET /api/v1/customer-portal/members` — lista de dependentes
      (`QuoteMember`) associados à apólice, reaproveitando
      `QuoteMemberSerializer` já existente.
- [ ] Rever se algum destes dados deve ser mascarado/reduzido para o
      cliente final (ex. o cliente não precisa de ver
      `eligibilityEvaluationId` interno, só o resultado) — provavelmente
      precisa de serializers **novos e mais magros**, não os mesmos do
      backoffice, para não vazar campos internos (`rowVersion`,
      `latestPricingRunId`, etc. não fazem sentido para o cliente final).

### Open Decisions
- **OD-PORTAL-005**: o cliente final pode ver o valor do prémio pago
  (`PricingRun`/breakdown), ou isso é sempre gerido só pela seguradora?
  Afecta se `PricingExplanationView` é reaproveitável ou deve ficar de
  fora do portal.

---

## Fase 3 — Submissão de pedidos pelo próprio cliente (prazo mais longo)

### Pedido
Permitir que o cliente final inicie ele próprio um pedido (nova cotação,
adicionar um dependente, pedir alteração de plano) sem passar por um
subscritor.

### Estado actual
Nenhum trabalho começado — depende inteiramente das Fases 0-2 estarem
estáveis e em produção primeiro.

### Objectivo (alto nível, a detalhar quando a Fase 2 fechar)
- Um cliente final poder despoletar `create_next_version`-style de
  pedido sem ferramentas de staff, mas ainda sujeito a aprovação humana
  (nunca `auto-approve` — a segregação de funções de quatro-olhos do
  Épico 6/Sprint 7 deve continuar a aplicar-se; o "actor" que cria não
  pode ser o mesmo que aprova, e aqui nem sequer teria permissão para
  aprovar).
- Provavelmente precisa de um novo `QuoteStatus` intermédio ou de um
  `origin`/`created_by_actor_type` no `Quote` para o backoffice conseguir
  distinguir "cotação criada por staff" de "cotação criada pelo próprio
  cliente" — a decidir quando esta fase começar a ser desenhada em
  detalhe (não antecipar a solução agora, dado o risco de inventar algo
  que a Fase 0-2 real ainda não valide).

### Open Decisions
- **OD-PORTAL-006**: fica para quando esta fase for desenhada em
  detalhe — não vale a pena fixar agora um esquema de dados para um
  fluxo que ainda não tem as duas fases anteriores validadas em uso
  real.

---

## Como usar este documento

- Segue exactamente a mesma disciplina de `ROADMAP_ANGOLA_CUSTOMIZATION.md`:
  "Open Decisions" bloqueiam o início do código correspondente.
  Nenhuma tarefa da Fase 0 deve começar a ser codificada antes de
  OD-PORTAL-001/002/003/004 terem resposta.
- Este roadmap é vivo — nada aqui é definitivo até à Fase 0 estar
  desenhada em detalhe com o product owner.
- Nenhuma parte deste roadmap reaproveita ou modifica os scopes/roles
  internos (`q360.*`, DOC-001 §18) — é uma fronteira de segurança
  deliberada, não um esquecimento.

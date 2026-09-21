# Roadmap — Portal do Cliente (autoatendimento para o segurado final)

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

### Tarefas
- [ ] Nova tabela `customer_account` (schema `q360`, `TenantScopedModel`,
      migration nova, nunca editando as existentes): liga-se a um ou mais
      `Proposer` do mesmo tenant (uma pessoa pode ter mais que uma
      cotação/apólice ao longo do tempo). Guarda apenas o necessário para
      autenticar — não duplicar dados já em `Proposer`.
- [ ] Mecanismo de login **fora** do fluxo OAuth2/OIDC staff — proposta
      mínima e realista para o mercado angolano: número de apólice
      (`Quote.quoteNumber`, já existe desde o Épico 4) + número de
      documento de identificação (BI/NIF, já em
      `Proposer.registration_number`) + um código OTP enviado por
      SMS/email no momento do primeiro acesso (ver OD-PORTAL-001 — método
      exacto de envio ainda em aberto).
- [ ] `actor_type="CUSTOMER"` em `Actor`, com `roles=frozenset()` sempre
      vazio (um cliente nunca tem `Role` de staff) e um novo mecanismo de
      permissão *específico do portal*, não DOC-001 §18.
- [ ] `CurrentActorProvider`/middleware: quando `actor_type="CUSTOMER"`,
      toda a query tem de ser adicionalmente filtrada por
      `proposer_id IN (<os do customer_account autenticado>)` — não basta
      o filtro de tenant já existente. Isto é uma segunda fronteira de
      segurança, nova, e tem de ser fail-closed tal como o tenant scoping
      (ver `apps/foundation/infrastructure/tenant_scoping.py` como
      referência do padrão a seguir).
- [ ] Estender `ck_audit_actor_type` (migration nova) para incluir
      `'CUSTOMER'`, para que acções de um cliente final continuem
      auditadas como tudo o resto no sistema.
- [ ] Rate limiting mais agressivo que o actual (`RateLimitMiddleware`
      já existe, ver `apps/foundation/interfaces/middleware.py`) nos
      endpoints públicos de login do portal — são o único ponto do
      sistema acessível sem já ter um token válido, logo o alvo natural
      de força bruta (tentar adivinhar números de apólice/documento).
- [ ] Namespace de URLs novo e isolado, ex. `/api/v1/customer-portal/...`
      — nunca reaproveitar os paths `/api/v1/quotes`, `/api/v1/products`,
      etc. já usados pelo backoffice, mesmo que a lógica por baixo
      reaproveite os mesmos serviços de aplicação.

### Open Decisions
- **OD-PORTAL-001**: qual o mecanismo real de verificação de identidade
  no primeiro acesso (SMS OTP via que gateway/operadora angolana? Email?
  Os dois?). Bloqueia o desenho exacto de `customer_account`.
- **OD-PORTAL-002**: um `customer_account` está ligado a **um** `Proposer`
  ou pode agregar vários (ex. o mesmo NIF em duas cotações diferentes ao
  longo dos anos)? Afecta o modelo de dados.
- **OD-PORTAL-003**: política de bloqueio/lockout após N tentativas
  falhadas de login — nenhuma política de lockout existe hoje em lado
  nenhum do sistema (staff usa IdP externo, quando OD-009 for resolvido).
- **OD-PORTAL-004**: este portal corre atrás do mesmo backend Django (novo
  app `customer_portal`) ou é um serviço separado que só lê via API? Dado
  DOC-004 s3.1 (fronteiras entre módulos), a proposta por omissão é um
  novo app Django dentro do mesmo backend, reaproveitando os serviços de
  aplicação já existentes (`quote_service`, `benefit_service`,
  `EvaluateEligibilityUseCase`) — mas nunca os endpoints/views do
  backoffice directamente.

---

## Fase 1 — Consulta de elegibilidade e estado da apólice (MVP)

### Pedido
Depois de autenticado (Fase 0), o cliente final deve conseguir ver o
estado da sua própria apólice sem ligar para o call center.

### Objectivo
O mínimo útil e seguro: ver que apólice tem, que plano/coberturas
contratou, e se está elegível.

### Tarefas
- [ ] `GET /api/v1/customer-portal/me` — devolve o(s)
      `Quote.quoteNumber` associados ao `customer_account` autenticado,
      status (`APPROVED`/etc.), plano e produto (reaproveitar
      `QuoteSerializer`/`ProductVersionSerializer` já existentes, apenas
      restringindo o queryset ao proposer do actor autenticado — nunca
      duplicar serializers).
- [ ] `GET /api/v1/customer-portal/coverage` — coberturas contratadas no
      plano (reaproveitar `list_plan_benefits` de
      `apps/product/application/benefit_service.py`, já construído no
      Épico 1).
- [ ] `POST /api/v1/customer-portal/eligibility` (ou automaticamente
      incluído em `/me`) — reaproveitar
      `EvaluateEligibilityUseCase.execute()` já existente, chamado com o
      `proposer_id`/`plan_id`/`product_version_id` resolvidos do próprio
      `customer_account`, nunca aceitando esses IDs vindos do pedido do
      cliente (evitar que um cliente peça a elegibilidade de outro
      alterando um ID no payload).

### Open Decisions
- Nenhuma nova além das da Fase 0 — esta fase é sobretudo composição de
  serviços de aplicação já existentes e testados.

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

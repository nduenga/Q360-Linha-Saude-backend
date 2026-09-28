# ROADMAP — Apólices (contrato), prémio e elegibilidade de cobertura

**Estado:** plano aprovado para arranque, nenhuma fase implementada.
**Autoridade:** decisões do Product Owner (2026-09-26) e parecer jurídico
recebido na mesma data (ver "Base legal").
**Substitui:** OD-ANGOLA-005 ("apólice = `Quote.quoteNumber` de uma
cotação `APPROVED`") e o versionamento de produto (Épicos 2 e 3,
OD-ANGOLA-003/004/009) — ver Fase 0.

---

## Princípio orientador

Uma **cotação aprovada não é um seguro**: é uma proposta contratual, em
fase pré-contratual. O seguro só existe quando o **tomador assina** — nesse
momento nasce a **apólice**. A apólice, porém, só **cobre riscos depois do
pagamento do prémio** (ou da sua primeira fracção). Assinatura e pagamento
são dois factos distintos, e o sistema regista-os separadamente.

Com isto, o sistema passa a tratar separadamente dois tipos de elegibilidade:

| | Elegibilidade de subscrição | Elegibilidade de cobertura |
|---|---|---|
| Pergunta | "Esta pessoa **pode entrar** neste plano?" | "Esta pessoa **está coberta** nesta data, para este acto?" |
| Quando | Cotação e cada inclusão por acta adicional | A qualquer momento: backoffice, portal, prestador |
| Fonte | `RuleVersion` (motor `evaluate()`, já existe) | `Policy` + `PolicyMember` + estado do prémio (novo) |
| Módulo | `apps/eligibility` | `apps/policy` (novo) |

### Decisões do Product Owner (2026-09-26)

| # | Decisão |
|---|---|
| PO-APO-1 | O que transforma a cotação em contrato é a **assinatura**. Havendo contrato assinado, existe apólice. |
| PO-APO-2 | Um membro com elegibilidade pendente **bloqueia só o seu próprio registo**, nunca a emissão. |
| PO-APO-3 | A **duração do contrato é definida no momento da emissão** da apólice. |
| ~~PO-APO-4~~ | ~~Sem suspensão por falta de pagamento.~~ **Revogada pelo parecer jurídico**: ver PO-APO-5. |
| PO-APO-5 | O pagamento do prémio é condição de cobertura. Existe **suspensão** e **resolução** por falta de pagamento (Decreto n.º 2/02, arts. 17.º e 18.º). |
| PO-APO-6 | **Deixam de existir "versões" de produto** na plataforma: só existem **produtos e planos**. |
| PO-APO-7 | O **mediador** é registado com a licença ARSEG e o direito a comissão fica segregado desde a emissão (Lei n.º 6/24). |

### Base legal

| Diploma | Uso neste roadmap | Verificação |
|---|---|---|
| Código Comercial, art. 426.º | O contrato de seguro reduz-se a escrito num instrumento, a apólice | Citado no parecer |
| Decreto n.º 2/02, de 11 de Fevereiro (Contrato de Seguro) | Art. 17.º: a 1.ª fracção é paga na data da celebração e as seguintes nas datas da apólice. Art. 18.º: em caso de falta de pagamento, a seguradora pode **suspender as garantias por carta registada, concedendo novo prazo**, e depois **resolver** o contrato | Confirmado em fonte pública |
| Lei n.º 18/22, de 7 de Julho (Actividade Seguradora e Resseguradora) | Provisões técnicas e solvência, o que impede manter coberturas sem prémio | Confirmado (diploma existe) |
| Lei n.º 6/24, de 3 de Junho (Mediação e Corretagem de Seguros) | Registo do mediador na ARSEG; revoga o Decreto Executivo n.º 7/03 | Diploma confirmado. **A obrigação de "segregação da comissão desde a emissão" está por confirmar pelo jurídico** |
| Código Comercial, art. 428.º | Início dos efeitos no dia civil seguinte, salvo convenção | **Por confirmar pelo jurídico**. Adoptado como regra por defeito, configurável |
| Lei n.º 5/20 (BCFT), alterada pela Lei n.º 8/26 | Documentos de identificação aceites (BI, Cartão de Residente, Passaporte) | Lei 5/20 confirmada; **a alteração 8/26 está por confirmar** |

**Regra do projecto mantida:** nenhum prazo em dias (tolerância, novo
prazo após carta registada, etc.) é inventado. Todos são **configuráveis**
e têm um valor por decidir (Open Decisions).

### Prática de mercado adoptada

- **Terminologia**: *tomador do seguro* (o `Proposer`), *pessoa segura*
  (`PolicyMember`), *mediador* (corretor, agente ou bancassurance),
  *acta adicional* (alteração ao contrato), *recibo* (cada fracção do
  prémio).
- **Documentos contratuais**: Condições Gerais, Especiais e
  **Particulares**. As Particulares são geradas a partir do snapshot de
  condições contratadas (Fase 1).
- **Início do risco**: por defeito às **00h00 do dia seguinte** ao que
  torna o contrato perfeito, ou seja, a data mais tardia entre a
  assinatura e o pagamento da 1.ª fracção. Uma data diferente só pode ser
  **posterior**, e fica registada nas Condições Particulares. Isto
  protege a seguradora contra sinistros ocorridos no próprio dia.
- **Fim do risco**: às **24h00 do último dia** de vigência.
- **Duração**: livre (PO-APO-3). A UI sugere **12 meses**.
- Nas **apólices de grupo** assina o **representante legal** da empresa.
- **Termos congelados**: a apólice guarda uma cópia integral das
  condições contratadas. Uma alteração posterior ao plano, à tarifa ou às
  regras **nunca** altera uma apólice em vigor. Aplica-se só a novo
  negócio e à renovação.
- **Número da apólice**: sequencial de teste `APO-` (ART-011 PROH-008
  continua a proibir inventar o formato real).
- **Sem efeitos retroactivos**, em nenhuma operação.

---

## Fase 0 — Decisões e documentação

- [x] `backend/DECISIONS_TAKEN.md`: nova entrada `S09-POLICY-001` com
      PO-APO-1..7 e a tabela de base legal.
- [x] Marcar como **substituídos**, sem apagar o histórico:
      OD-ANGOLA-005 (Épico 4), **Épico 2** (versionamento automático),
      **Épico 3** (versões sem data de fim), OD-ANGOLA-009 — em
      `ROADMAP_ANGOLA_CUSTOMIZATION.md` e `CHECKLIST_CUSTOMIZACAO.md`.
- [x] Actualizar os comentários "apólice = quoteNumber" em
      `apps/quote/interfaces/views.py` e
      `apps/customer_portal/application/auth_service.py`.
- [ ] Registar como desvio consciente aos artefactos ART-005/ART-009/
      ART-012: o novo estado `BOUND` da cotação e a remoção de
      `product_version`.
- [ ] Pedir ao jurídico a validação dos 3 pontos marcados "por confirmar"
      na tabela de base legal. **Não bloqueia o arranque**: o que depende
      deles fica configurável.

---

## Fase 1 — Produtos e planos, sem versões (PO-APO-6)

**Tem de vir antes da apólice.** Hoje, a imutabilidade de uma cotação
aprovada depende de a `ProductVersion` ser imutável: o snapshot `APPROVAL`
([quote_service.py](backend/apps/quote/application/quote_service.py),
`_create_snapshot`) guarda **apenas IDs** (`productVersionId`, `planId`,
`latestPricingRunId`), não o conteúdo do plano. Se os planos passarem a
ser editáveis sem versões, e o snapshot não for completado antes, uma
edição ao plano **alteraria retroactivamente o que o cliente contratou**.

### Modelo alvo
```
Product ──< Plan ──< PlanBenefit >── Benefit
               status: DRAFT | ACTIVE | INACTIVE
```
- `Plan.product_id` passa a ser uma FK directa. Desaparece `product_version`.
- `ACTIVE` significa "comercializável" (pode iniciar novas cotações).
  `INACTIVE` significa que deixou de ser vendido, mas continua legível
  para cotações e apólices existentes. Substitui a regra de OD-ANGOLA-009.
- **Editar um plano ACTIVE** (coberturas, limites, nome) só afecta
  cotações **ainda não aprovadas** e novo negócio. As cotações nesse caso
  são marcadas para revalidação (o preço e a elegibilidade voltam a ser
  calculados antes de submeter).
- **Histórico de alterações** do plano via `audit_event` (quem, quando,
  antes e depois). É rastreabilidade interna, nunca apresentada como
  "versão".
- As versões de **configuração** (`RuleVersion`, tabelas de tarifa,
  `PricingParameterSet`) **mantêm-se**. São governação interna (dupla
  aprovação, OD-ANGOLA-015), não "versões de produto", e são o que permite
  saber que regra ou tarifa foi aplicada em cada decisão. Na UI podem ser
  chamadas "Tarifário em vigor" e "Regras em vigor".

### Snapshot de condições contratadas (pré-requisito)
- [x] Os snapshots `PRICING`/`SUBMISSION`/`APPROVAL` passam a guardar o
      **conteúdo integral do plano** (`_plan_content_snapshot`, em
      `apps/quote/application/quote_service.py`): código, nome, estado e a
      lista de coberturas com `configuration_json`. Ainda não inclui
      `ruleVersionId` nem o breakdown do prémio por membro — só o `plan`;
      o `pricingRunId`/`totalAmount`/`currencyCode` já lá estavam. Deixado
      para a Fase 2 (onde o snapshot vira o `contracted_terms_snapshot`
      real da apólice) se se revelar necessário mais detalhe.
- [x] Teste: `tests/product/test_plans.py::test_edit_plan` prova que
      editar o plano não falha nem quebra nada a jusante; a imutabilidade
      do próprio snapshot ainda não tem um teste dedicado
      (`snapshot_json` nunca é reescrito depois de criado, por construção
      — `QuoteSnapshot` só é criado, nunca actualizado).

### Migração (feita em 1 passo aditivo; passo 2 fica para mais tarde)
1. **Aditivo, implementado**: `plan.product_id` (backfill a partir de
   `product_version.product_id` — `apps/product/infrastructure/
   migrations/0002_plan_direct_to_product.py`). As colunas
   `product_version_id` em `plan`, `quote`, `quote_snapshot`,
   `pricing_run` e `eligibility_evaluation` tornaram-se **nullable**
   (migrações `0004_product_version_optional`/`0003_product_version_
   optional` em quote/pricing/eligibility) e **nenhum código novo as
   escreve** — só ficam preenchidas em linhas antigas, pré-migração.
   Não foi feito o backfill `PUBLISHED→ACTIVE`/`RETIRED,DRAFT→INACTIVE`
   por estado de versão: como a base de dados de desenvolvimento não
   tinha dados reais em produção, `Plan.status` manteve o valor que já
   tinha (por omissão `ACTIVE`). **Numa base de dados com dados reais,
   este backfill tem de ser feito explicitamente antes de aplicar esta
   migração.**
2. **Remoção** (não feita nesta sessão): `DROP` das colunas
   `product_version_id` e da tabela `product_version`. Falta como
   trabalho de limpeza depois de este passo estar validado em produção.

### Impacto no código
- [x] `product`: removidos `create_next_version`/`create_product_version`/
      `_versions_overlap`, `PublishProductVersionUseCase` e os endpoints
      `/products/{id}/versions` e `/product-versions/{id}/publish`. O
      CRUD de planos manteve-se em `POST/GET /plans` (plano), filtrável
      por `?productId=` — **não** foi movido para `/products/{id}/plans`
      como este item previa (o padrão flat já existente foi mantido, por
      consistência com o resto do módulo). `Plan.status`
      (`ACTIVE`/`INACTIVE`) faz agora o papel de "comercializável", sem
      gating por DRAFT — um plano pode ser editado ou ter coberturas
      alteradas a qualquer momento.
- [x] `quote`: `QuoteCreateRequest` recebe só `planId`. `create_quote`
      exige `plan.status == PlanStatus.ACTIVE`.
- [x] `pricing`: `pricing_engine.calculate_pricing` resolve só por
      `plan_id`. `PricingRun.product_version` ficou nullable, nunca
      escrito por código novo.
- [x] `eligibility`: `ProductVersionFacts` removida; `evaluate()` já só
      recebe `plan: PlanFacts`. A regra ELIG-006 foi dobrada em ELIG-007
      (plano inactivo), não mantida como regra separada — porque um
      `Plan` já não tem intervalo de datas próprio, só um estado. O golden
      test GT-ELIG-002 foi **retirado** (`pytest.mark.skip`, com a razão
      documentada inline), porque o cenário que testava (intervalo de
      vigência de uma versão) deixou de poder existir no domínio.
- [x] `customer_portal`: `self_service_views.py` resolve o produto via
      `plan.product_id`; a chave `productVersion` mantém-se na resposta,
      sempre `None` (decisão da sessão irmã que integra o frontend do
      portal, que já trata esse campo como opcional).
- [ ] Frontend (`Q360-Linha-Saúde-frontend`): remover os selects e ecrãs
      de versão. **Não feito nesta sessão** — âmbito de backend.
- [x] Testes: `test_auto_versioning.py` removido, `test_concurrency.py`
      perdeu o teste de publish concorrente de versão (o de
      `PricingParameterSet` mantém-se), `test_quote_requires_current_
      version.py` reescrito para "plano `INACTIVE`", mais os testes de
      `product`/`quote`/`pricing`/`eligibility`/`customer_portal`/
      `integration` que criavam produto+versão+plano, todos adaptados
      para produto+plano directo. **Suite completa verde** (`pytest -q`,
      1 skip esperado — GT-ELIG-002).

---

## Fase 2 — Modelo de dados da apólice (`apps/policy`)

A app segue as camadas habituais, com migrações SQL no schema `q360` e
`managed = False`. Tudo é tenant-scoped.

**`policy`**

| Coluna | Notas |
|---|---|
| `policy_number` | `APO-…`, `UNIQUE (tenant_id, policy_number)` |
| `source_quote_id` | `UNIQUE`: uma cotação gera no máximo uma apólice |
| `contracted_terms_snapshot_id` | Snapshot `APPROVAL` integral (Fase 1) |
| `proposer_id` | Tomador |
| `product_id`, `plan_id` | Referência. Os termos vêm do snapshot |
| `intermediary_id` | Obrigatório quando o negócio veio de mediador (Fase 5) |
| `policy_type` | `INDIVIDUAL` \| `GROUP` |
| `term_months` | Duração definida na emissão (PO-APO-3) |
| `start_date`, `end_date` | Preenchidos na activação (ver Fase 3) |
| `status` | ver máquina de estados |
| `payment_frequency` | `ANUAL` \| `SEMESTRAL` \| `TRIMESTRAL` \| `MENSAL` (catálogo configurável) |
| `currency_code` | AOA |
| `termination_*`, `cancellation_*` | motivo, data efectiva, autor |
| `issued_by`, `issued_at`, `row_version`, timestamps | |

**Máquina de estados**
```
                 1.ª fracção paga
PENDING_FIRST_PREMIUM ─────────────► ACTIVE ◄──────────────┐
      │ (prazo configurável                │ carta registada│ pagamento
      │  sem pagamento)                    ▼ (art. 18.º)    │ regulariza
      ▼                                SUSPENDED ───────────┘
  CANCELLED                               │ novo prazo esgotado
  (sem efeitos, nunca                     ▼
   houve cobertura)                   TERMINATED (resolução por falta de pagamento)

ACTIVE ──(fim de vigência)──► EXPIRED        ACTIVE ──(pedido/decisão)──► CANCELLED
```

**`policy_signature`** (1:1): signatário (nome, tipo e número de
documento em `BI`/`CARTAO_RESIDENTE`/`PASSAPORTE`), qualidade
(`TOMADOR`/`REPRESENTANTE_LEGAL`/`PROCURADOR`), `signature_method`
(`PRESENCIAL`; `DIGITAL` fica reservado), `signed_at`,
`signed_document_ref`/`checksum` (nullable até OD-APO-001), e
`registered_by`/`registered_at`.

**`policy_member`**: `status` (`PENDING`/`ACTIVE`/`EXCLUDED`/`REJECTED`),
`pending_reason_code`, `inclusion_date`/`exclusion_date`,
`eligibility_evaluation_id`, `rule_version_id` (congelado),
`waiting_period_ends_json`, `loading_percentage`.

**`premium_installment`** (recibo): `policy_id`, `installment_no`,
`period_from`/`period_to`, `due_date`, `amount`, `status` (`DUE`/`PAID`/
`OVERDUE`/`VOID`), `paid_at`, `payment_reference`, `payment_method`,
`registered_by`. O pagamento é **registado manualmente** pelo backoffice.
Não há integração com gateway nem banco.

**`premium_default_notice`**: registo da carta registada do art. 18.º:
`installment_id`, `sent_at`, `registered_mail_reference`,
`new_deadline`, `suspension_effective_at`, `outcome`.

**`policy_commission`** (**adiada para a Fase 5**, junto com
`intermediary`): `policy_id`, `intermediary_id`, `commission_basis` e
`rate` (do acordo de mediação em vigor à data da emissão, congelado),
`status` (`ACCRUED`/`EARNED`/`VOID`), mais uma linha por recibo quando o
prémio é pago. Fica **apenas registado**: o pagamento de comissões ao
mediador está fora de âmbito. Não entrou na migração da Fase 2 para não
deixar uma FK pendurada para uma tabela `intermediary` que ainda não
existe — ver `DECISIONS_TAKEN.md#S09-POLICY-003`.

**`policy_endorsement`** (acta adicional) e **`policy_state_history`**.

**Alteração à cotação**: `QuoteStatus.BOUND`, terminal, numa migração
nova. `expire_quotes` e o cancelamento nunca lhe tocam.

- [x] App, enums, migração `0001_policy_baseline.py` com os CHECKs de
      estado e de datas — implementado com `policy`, `policy_signature`,
      `policy_member`, `premium_installment`, `premium_default_notice`,
      `policy_endorsement` e `policy_state_history` (7 tabelas; falta só
      `policy_commission`, adiada para a Fase 5 pela razão acima).
      `QuoteStatus.BOUND` implementado (`apps/quote/infrastructure/
      migrations/0005_bound_status.py`).
- [ ] Permissões `POLICY_ISSUE`, `PREMIUM_REGISTER_PAYMENT`,
      `POLICY_ENDORSE`, `POLICY_CANCEL`, `POLICY_SUSPEND` — **não
      criadas**: `apps.foundation.domain.permissions` proíbe explicitamente
      inventar permissões sem entrada aprovada em DOC-001 s18. Fica para a
      Fase 3 decidir qual permissão já aprovada reutilizar (ver
      `DECISIONS_TAKEN.md#S09-POLICY-003`), quando existirem endpoints
      reais para gatear.
- [x] Testes de esquema/constraints (`tests/policy/test_policy_models.py`,
      9 casos: 1:1 Quote→Policy, unicidade de `policy_number`, `ck_policy_
      status`, `ck_policy_dates`, 1:1 `PolicySignature`, unicidade de
      `PolicyMember`, PO-APO-2 (pendente não acopla o resto), isolamento
      por tenant). Suite completa do backend verde (`pytest -q`, 1 skip
      esperado).

---

## Fase 3 — Emissão por assinatura e activação por pagamento

### Emissão (`IssuePolicyFromSignature`)
1. A cotação está `APPROVED`, dentro de `valid_until`, e tem snapshot
   integral.
2. O pedido traz o signatário, `signedAt`, `termMonths`,
   `paymentFrequency`, o mediador (se houver) e, opcionalmente,
   `requestedStartDate` (só pode ser posterior à regra por defeito).
3. Numa única transacção: `Policy` em `PENDING_FIRST_PREMIUM`,
   `PolicySignature`, `PolicyMember` (mapeamento abaixo), o plano de
   recibos (`premium_installment`), a comissão (`ACCRUED`), a cotação
   passa a `BOUND`, e são gerados auditoria e o outbox `POLICY.ISSUED`.
4. Se o pagamento da 1.ª fracção for registado **no mesmo acto** (o
   art. 17.º prevê o pagamento na data da celebração), a apólice activa
   imediatamente.

**Mapeamento de membros (PO-APO-2)**

| Decisão de subscrição | `PolicyMember.status` |
|---|---|
| `ELIGIBLE`, `WARNING`, `ELIGIBLE_WITH_LOADING` | `ACTIVE` (na activação da apólice) |
| `PENDING_DOCUMENT`, `PENDING_MEDICAL_BOARD`, `REFERRAL` | `PENDING` + motivo |
| `HARD_STOP`, `CONFIG_ERROR` | não é copiado |

### Activação (`RegisterPremiumPayment` na 1.ª fracção)
- `start_date` = **dia seguinte** a `max(data da assinatura, data do
  pagamento)`, ou o `requestedStartDate` se for posterior.
  `end_date = start_date + term_months − 1 dia`, com o fim às 24h00.
- Os recibos são recalculados a partir do `start_date` efectivo.
- A carência é calculada a partir da `inclusion_date`, com a
  `RuleVersion` congelada.
- Se não houver pagamento no prazo configurável (OD-APO-009), a apólice
  passa a `CANCELLED` **sem efeitos**, porque nunca houve cobertura.

### API e frontend
- [x] `POST /quotes/{id}/policy` (emissão), `POST
      /policies/{id}/installments/{n}/payment` (só `n=1` implementado —
      `n>1` devolve `VALIDATION-400`, recibos recorrentes ficam para a
      Fase 7), `GET /policies`, `GET /policies/{id}`,
      `GET /policies/{id}/members`, `GET /policies/{id}/installments`,
      `GET /policies/{id}/signature`.
      Implementado sem comissão/mediador (`ACCRUED`) — adiado para a
      Fase 5, tal como as tabelas correspondentes ficaram adiadas na
      Fase 2.
- [ ] Documento `POLICY_SCHEDULE` (Condições Particulares) — **não
      implementado**. Âmbito de geração de documentos fica fora desta
      sessão (mesma decisão de adiamento que o resto do trabalho de
      frontend/documentos).
- [ ] Frontend (`QuoteSummaryPage`, `PoliciesListPage`,
      `PolicyDetailPage`) — **não implementado**, âmbito de backend
      apenas nesta sessão.

### Testes
- [x] Assinatura às 14h de dia D e pagamento em D: o risco começa em
      D+1 00h00 (`test_activation_when_paid_same_day_as_signature_still_
      starts_next_day`).
- [x] Pagamento em D+3: o risco começa em D+4
      (`test_activation_starts_risk_the_day_after_signature_and_payment`).
- [x] `requestedStartDate` anterior à regra: 400
      (`test_requested_start_date_before_signature_is_rejected`).
- [ ] "Sem pagamento: `PENDING_FIRST_PREMIUM` e `NOT_COVERED`" — o estado
      `PENDING_FIRST_PREMIUM` já existe e é testado; o `NOT_COVERED` via
      `check_coverage` é a Fase 4, testado lá.
- [x] Emissão dupla (`test_cannot_issue_policy_twice_for_the_same_quote`),
      só cotação `APPROVED` pode ser assinada
      (`test_only_an_approved_quote_can_be_signed`), membro `HARD_STOP`
      nunca copiado (`test_hard_stop_member_is_not_copied_onto_the_
      policy`), plano mensal gera 12 recibos que somam o total
      (`test_monthly_frequency_creates_12_installments`), procura por
      número de apólice (`test_lookup_by_policy_number`). **Cotação
      expirada e isolamento por tenant explícitos para `apps.policy`
      não testados** — o isolamento por tenant é herdado de
      `TenantScopedManager` (já provado genericamente na Fase 2), e a
      cotação expirada seria um teste de `quote.valid_until`, não
      construído nesta fase.
- [x] Suite completa do backend verde (`pytest -q`, 1 skip esperado),
      18 testes novos em `tests/policy/test_issuance.py`.

---

## Fase 4 — Verificação de cobertura

A verificação é uma função pura, em `apps/policy/domain/coverage.py`.
As regras avaliam-se por esta ordem, e a primeira que falha decide:

```
check_coverage(policy, member, installments, on_date, benefit_category?) →
  NOT_COVERED  POLICY_AWAITING_FIRST_PREMIUM   (status PENDING_FIRST_PREMIUM)
  NOT_COVERED  POLICY_SUSPENDED_NO_PAYMENT     (SUSPENDED em on_date)
  NOT_COVERED  POLICY_NOT_IN_FORCE             (TERMINATED/CANCELLED/EXPIRED ou fora de [start, end])
  NOT_COVERED  MEMBER_PENDING                  (+ motivo, mensagem amigável)
  NOT_COVERED  MEMBER_NOT_IN_FORCE             (fora de [inclusion, exclusion))
  NOT_COVERED  BENEFIT_NOT_IN_PLAN             (segundo o snapshot contratado, não o plano actual)
  IN_WAITING_PERIOD  until=<data>
  COVERED
```

A suspensão avalia-se **por data**: um acto anterior à suspensão
continua coberto (implementado desde já — `SUSPENDED` é verificado
mesmo sem nada ainda o atribuir, ver `DECISIONS_TAKEN.md#S09-POLICY-005`).
As mensagens ficaram directamente em `apps/policy/domain/coverage.py`
(dicionário `_MESSAGES`), não num `messages_pt.py` próprio — o volume não
justificou um módulo à parte como o de `apps.eligibility`.

- [x] Endpoints `GET /policies/{id}/coverage?memberId=&date=&benefitCategory=`
      (`memberId` omitido avalia todos os membros) e
      `GET /coverage?policyNumber=&date=&memberId=&benefitCategory=`.
      Gate só por `Scope.READ`, sem `Permission` (leitura pura).
- [ ] `EligibilityPage.tsx` — **não implementado**, âmbito de frontend
      fora desta sessão.
- [x] Testes: `tests/policy/test_coverage_domain.py` (14 casos puros,
      um por cada ramo da ordem documentada acima, mais determinismo) e
      `tests/policy/test_coverage_api.py` (7 casos via API real —
      incluindo um cenário completo de carência de maternidade a 300
      dias calculada a partir da `inclusion_date` real de uma apólice
      activada). Suite completa do backend verde (`pytest -q`, 1 skip
      esperado).

---

## Fase 5 — Mediadores (PO-APO-7)

Esta fase deixou de ser opcional: o mediador tem de estar registado a
tempo da emissão.

- [ ] Tabela `intermediary`: `name`, `intermediary_type` (`CORRETOR`/
      `AGENTE`/`BANCASSURANCE`/`MEDIADOR_ACESSORIO`, as categorias da Lei
      6/24), `nif`, `arseg_licence_number` (**obrigatório**, `UNIQUE` por
      tenant), `licence_valid_from`/`licence_valid_to`, `status`.
- [ ] `intermediary_agreement`: acordo de mediação com a base e a taxa de
      comissão por produto e plano. É versionado internamente, porque a
      taxa aplicada tem de ser a que estava em vigor à data da emissão.
- [ ] **Validação cruzada na cotação e na emissão**: o mediador tem de
      estar `ACTIVE`, com licença válida na data da emissão e com acordo
      em vigor para o plano. Se falhar, a emissão é bloqueada (422).
- [ ] **Não existe API pública da ARSEG**, e inventar uma integração é
      proibido (DOC-000). A validação é feita contra o **registo interno**,
      mantido pelo compliance a partir da lista pública da ARSEG
      (*Entidades autorizadas*). Ficam registados a data e o autor de cada
      verificação da licença.
- [ ] `quote.intermediary_id` é herdado pela apólice. O mediador é
      **intermediário, não dono**. O acesso às suas apólices é feito por
      âmbito de linha (`intermediary_id`), como no `scoping.py` do portal,
      **nunca com uma base de dados por mediador**.

---

## Fase 6 — Portal do Cliente passa a usar a apólice

- [x] O login passa a usar `policyNumber` + `registrationNumber` + email,
      sobre `Policy.status IN (ACTIVE, EXPIRED)`, em vez de
      `Quote APPROVED`. Mudança de rutura deliberada: o código de erro
      `PORTAL-QUOTE-NOT-FOUND` passou a `PORTAL-POLICY-NOT-FOUND`
      (`PortalPolicyNotFoundError`) — ver `DECISIONS_TAKEN.md#S09-POLICY-006`.
- [x] `/me` lista apólices e o seu estado, incluindo recibos em dívida
      (`outstandingInstallments`: contagem e total das `premium_
      installment` `DUE`/`OVERDUE`, não a lista completa). `/coverage` e
      `/eligibility` passam a usar `check_coverage` (Fase 4), não
      `EvaluateEligibilityUseCase`. O catálogo de coberturas contratadas
      que `/coverage` costumava devolver mudou-se para
      `GET /plan-benefits?policyNumber=`, novo endpoint, para libertar o
      nome `/coverage` para a verificação real.
- [x] `ROADMAP_PORTAL_CLIENTE.md` actualizado (nota no topo da Fase 1
      original) e `tests/customer_portal/` reescritos: 6 casos em
      `test_portal_auth_api.py`, 10 em `test_self_service_api.py`.

---

## Fase 7 — Ciclo de vida

- [ ] **Falta de pagamento (art. 18.º)**: o comando `premium_overdue_scan`
      (padrão `expire_quotes`, actor `SYSTEM`, idempotente) marca os
      recibos `OVERDUE` e cria uma tarefa de envio de carta registada.
      A suspensão **só é aplicada depois de a carta ser registada** no
      sistema (`premium_default_notice`), nunca automaticamente. Quando o
      `new_deadline` se esgota, o comando propõe a resolução, que passa a
      `TERMINATED` com confirmação humana. O pagamento durante a suspensão
      reactiva a apólice, sem efeito retroactivo sobre o período suspenso.
- [ ] **Actas adicionais**: activar um membro pendente (motor com a
      `RuleVersion` congelada, inclusão na data da activação), incluir um
      membro (gera um recibo pro-rata; a cobertura desse membro depende
      do pagamento desse recibo), excluir um membro.
- [ ] **Cancelamento** com catálogo de motivos, sem retroactividade.
- [ ] **Expiração**: o comando `expire_policies` passa a `EXPIRED` as
      apólices com `end_date` ultrapassada. A cobertura já é calculada
      por data, por isso um atraso do cron nunca dá cobertura indevida.

---

## Fase 8 — Renovação

- [ ] Perto do fim da vigência, é gerada uma cotação de renovação com o
      plano **actual** (se estiver `INACTIVE`, é preciso escolher um
      plano substituto), idades actualizadas e a tarifa em vigor.
- [ ] Após assinatura e pagamento, é criado um novo período com o **mesmo
      `policy_number`** (`term_no`, `renewed_from_policy_id`). O período
      anterior passa a `RENEWED`.
- [ ] Os membros com continuidade não voltam a cumprir carência
      (portabilidade interna verificada automaticamente).

---

## Fora de âmbito

- Integração com gateway ou banco para pagamentos (o pagamento é
  registado manualmente).
- Pagamento de comissões ao mediador (só são registadas).
- Assinatura digital qualificada.
- Cartão de beneficiário e rede de prestadores.
- Reporte regulamentar à ARSEG.

---

## Open Decisions

| Código | Pergunta | Recomendação |
|---|---|---|
| OD-APO-001 | Onde se guarda o documento assinado? | Mesma decisão de armazenamento da Fase B do motor. Até lá, `signed_document_ref` fica nullable. |
| OD-APO-002 | Apólice individual com o titular pendente: emite-se? | Sim (PO-APO-2). Os dependentes só ficam cobertos depois de o titular ser activado. |
| OD-APO-003 | O início do risco pode ser anterior ao `effective_date` da cotação? | Não. A tarifa foi calculada para aquela data. |
| OD-APO-004 | Há limites de duração? | Nenhum hardcoded. Se o negócio quiser, `durationRules` na configuração. |
| OD-APO-005 | Recém-nascidos: há prazo de inclusão sem carência? | Configurável (`newbornGraceDays`), sem inventar o valor. |
| OD-APO-006 | Categorias de carência ↔ `Benefit.benefit_type` | Usar `benefit_type`. Confirmar no catálogo do Épico 1. |
| OD-APO-007 | O prémio de um membro pendente conta? | Não. Só a partir da activação, pro-rata. |
| OD-APO-008 | Motivos de cancelamento | `PEDIDO_TOMADOR`, `DECISAO_SEGURADORA`, `ERRO_EMISSAO`, alargável por tenant. |
| OD-APO-009 | Prazo para pagar a 1.ª fracção antes de a emissão caducar | Configurável, com valor a definir pelo negócio e pelo jurídico. |
| OD-APO-010 | Novo prazo concedido na carta registada (art. 18.º) | Configurável, com valor a definir pelo jurídico. |
| OD-APO-011 | Fraccionamentos permitidos e eventual custo de fraccionamento por plano | Configuração do plano ou tarifa, sem valores inventados. |
| OD-APO-012 | Taxas de comissão por tipo de mediador | Vêm do `intermediary_agreement`. Nenhuma taxa por defeito. |
| OD-APO-013 | Validar os pontos "por confirmar" da base legal | Jurídico. |

---

## Ordem recomendada

**0 → 1 → 2 → 3 → 5 → 4 → 6 → 7 → 8**

- **Fase 1 primeiro**: a apólice congela os termos a partir do snapshot,
  e hoje o snapshot só aguenta porque as versões são imutáveis. Remover
  as versões sem completar o snapshot abriria um buraco.
- **Fase 5 antes da 4**: o mediador é validado na emissão (Fase 3), por
  isso tem de existir cedo. A Fase 4 pode avançar em paralelo.
- As Fases 2 a 4 são o mínimo para "apólice = contrato assinado e pago"
  funcionar de ponta a ponta.

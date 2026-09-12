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

## Fora de âmbito desta resolução

**OD-001 (tarifas/prémios reais)** não é resolvido aqui e não pode ser —
não há autoridade actuarial para inventar valores comerciais reais. Todos
os dados usados em testes/demonstração (`BASE_PREMIUM`, `RatingFactor`,
`PricingAdjustment`) continuam a ser fixtures técnicas explícitas, nunca
tarifas Angolanas reais, exactamente como antes desta resolução.

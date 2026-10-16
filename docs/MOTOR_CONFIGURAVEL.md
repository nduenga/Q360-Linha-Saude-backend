# Motor de cálculo configurável — Q360 Linha Saúde

Este documento descreve como fórmulas, taxas, valores, parâmetros e regras são
administrados pela API, validados, aprovados, publicados e usados no cálculo
real do prémio. Toda a configuração comercial/actuarial vive na tabela
`business_configuration`, versionada por chave (`configKey`).

## 1. Chaves de configuração

| `configKey` | O que contém | Onde entra no cálculo |
|---|---|---|
| `pricing.reference_premiums` | Moeda e prémios de referência por plano/idade | Prémio base (quando não há modelo actuarial publicado) |
| `pricing.factors` | Multiplicadores por dimensão (idade, sexo, região…) | Por pessoa, depois do prémio base |
| `pricing.adjustments` | Agravamentos/descontos por condição | Por pessoa ou sobre o total |
| `pricing.taxes_fees` | Impostos e encargos (percentagem ou valor fixo) | Sobre o total |
| `pricing.actuarial_model` | Modelo actuarial SAU/SAG (editável; importável de Excel) e opções de cálculo | Substitui o prémio base e aplica toda a cadeia do `Calculador` (ver `MAPA_MODELO_ACTUARIAL.md` e §7) |
| `pricing.formulas` | Fórmulas matemáticas e parâmetros com nome | Fase `PERSON` por pessoa; fase `QUOTE` no fim, sobre o total |
| `pricing.fractionation` | Encargo de fracionamento por periodicidade | Nas prestações de todas as apólices |
| `rules.custom` | Regras «Quando… então…» | Por pessoa e/ou sobre o total; avisos/encaminhamentos na cotação |
| restantes (`product.*`, `security.*`, `proposal.*`…) | Ver `GET /api/v1/business-config/catalog` | — |

## 2. Ciclo de vida (todas as chaves)

```
DRAFT ──submit──▶ PENDING_APPROVAL ──approve──▶ PUBLISHED ──retire──▶ RETIRED
  ▲                      │
  │                   reject (motivo obrigatório)
  │                      ▼
  └──editar────────── REJECTED ──submit (sem alterar)──▶ PENDING_APPROVAL
```

- **DRAFT**: editável (`PUT`, com `rowVersion` para bloqueio otimista). A
  validação estrutural corre logo ao criar/editar — uma fórmula com sintaxe
  inválida, variável desconhecida ou dependência circular nunca é gravada.
- **submit**: volta a validar e aplica as regras de publicação; aceita
  `changeReason` (motivo da alteração, guardado na auditoria).
- **approve**: só utilizadores com scope de aprovação; o autor não pode
  aprovar a própria versão (*four-eyes*, desligável em
  `security.approval_rules.four_eyes_required`). Publica a versão, fecha a
  vigência da versão anterior na véspera do novo `effectiveFrom`.
- **reject**: a versão fica `REJECTED` (decisão R2, migração
  `business_config/0003`), com o motivo em `metadata.lastRejection` /
  `metadata.rejections` e no evento `BUSINESS_CONFIGURATION_REJECTED`. Não é
  aprovável; editar devolve-a a DRAFT; também pode ser reenviada. A
  rejeição também é *four-eyes*.
- **Imutabilidade**: uma versão publicada não é editável; muda-se criando
  outra versão. Cada versão tem `checksum` SHA-256 do valor.
- **Histórico**: `GET …/configurations/{id}/history` (quem, quando, estado,
  checksum, motivo). **Comparação**: `GET …/configurations/{id}/compare?with={id2}`.

## 3. Reprodutibilidade e rastreabilidade

- Cada `PricingRun` guarda em `business_configuration_snapshot_json` o
  `configurationId`, `versionNo` e `checksum` de **cada** chave usada
  (incluindo `pricing.formulas`, `pricing.actuarial_model` e `rules.custom`).
- Cada componente do prémio (`PricingComponent`) tem `sourceCode` (ex.:
  `BUSINESS_CONFIG:pricing.formulas:com_gestao`,
  `BUSINESS_CONFIG:pricing.actuarial_model:Matriz_SAU!S6`) e `sourceVersion`.
- O trace (`GET /api/v1/pricing/{runId}/explanation`) regista cada passo:
  fórmulas aplicadas (com variáveis e valores auxiliares), fórmulas
  ignoradas (`FORMULA_SKIPPED`, motivo `INACTIVE`), regras aplicadas
  (`CUSTOM_RULE_APPLIED`) e regras ignoradas com os factos avaliados
  (`CUSTOM_RULE_SKIPPED`, motivo `CONDITION_NOT_MET`).
- Publicar uma nova versão **não altera cálculos antigos**: a cotação só é
  recalculada quando se pede o preço e a combinação de versões vigente é
  diferente da registada (`price_quote` compara as versões de todas as
  chaves, incluindo as opcionais). Uma cotação aprovada fica congelada no
  snapshot. Recalcular explicitamente: `POST /quotes/{id}/price` com
  `{"recalculate": true}`.
- Arredondamento: cada componente monetário é arredondado a 2 casas,
  meio-para-cima (decisão OD-006). Cálculos internos em `Decimal`.

## 4. Fórmulas (`pricing.formulas`)

### 4.1 Forma

```json
{
  "parameters": [
    {"code": "taxa_gestao", "label": "Taxa de gestão", "value": "0.05",
     "unit": "RATIO", "min": "0", "max": "1"}
  ],
  "rules": [
    {"code": "gestao", "name": "Encargo de gestão", "target": "VALUE",
     "expression": "base_total * taxa_gestao"},
    {"code": "com_gestao", "name": "Total com gestão", "purpose": "LOADING",
     "stage": "QUOTE", "target": "TOTAL", "order": 10, "active": true,
     "expression": "total_amount + gestao",
     "variables": ["total_amount", "gestao"],
     "output": {"min": "0", "max": null}}
  ]
}
```

- `stage` — `PERSON` (por pessoa) ou `QUOTE` (total; omissão).
- `target: TOTAL` — passo do cálculo; substitui o valor da fase (prémio da
  pessoa ou total). Os passos ativos correm por fase, `order` e código
  (ordem determinística).
- `target: VALUE` — valor auxiliar reutilizável por código, só na mesma
  fase; não arredondado.
- `variables` (opcional) — variáveis declaradas; se presente, a expressão
  não pode usar outras.
- `output.min/max` — intervalo permitido; um passo TOTAL tem mínimo 0.
- `active: false` — a fórmula fica guardada mas não corre (desativação).

### 4.2 Linguagem controlada

Números, variáveis, `+ - * / **` (expoente ≤ 10) e as funções `min`, `max`,
`abs`, `round(x, casas)` (0–6 casas, meio-para-cima). A expressão é analisada
com `ast` e recusada se tiver qualquer outro elemento (atributos, índices,
chamadas não autorizadas, strings, comparações, lambdas…). Não há `eval`,
`exec` nem SQL. Limites: 500 caracteres, 100 nós, 50 fórmulas, 100 parâmetros.

Variáveis do sistema:

| Fase | Variáveis |
|---|---|
| `PERSON` (decisão A9) | `person_amount` (prémio da pessoa antes da fórmula), `person_base` (antes de qualquer fórmula), `age`, `members_count` |
| `QUOTE` | `total_amount` (total antes da fórmula), `base_total` (antes de qualquer fórmula), `members_count` |

### 4.3 Validação (ao criar, editar e submeter)

Sintaxe; códigos válidos e únicos; variáveis conhecidas e declaradas;
parâmetros dentro de `min/max`; nenhum passo TOTAL referenciado por outra
fórmula; nenhuma dependência de uma fórmula desativada; **sem ciclos** entre
fórmulas VALUE (ex.: `a -> b -> a` é recusado com o caminho do ciclo).

### 4.4 API

| Método e rota | Função |
|---|---|
| `GET /business-config/formulas/catalog` | Variáveis, funções, operadores, limites |
| `POST /business-config/formulas/test` | Testar uma expressão isolada |
| `POST /business-config/formulas/validate` | Validar um conjunto sem gravar |
| `GET/POST /business-config/formulas` | Listar versões / criar DRAFT |
| `GET/PUT /business-config/formulas/{id}` | Consultar (com ordem e dependências) / editar DRAFT |
| `POST …/{id}/submit` · `approve` · `reject` · `retire` | Ciclo de vida |
| `POST …/{id}/simulate` | Simular qualquer versão, passo a passo: `totalAmount`, `membersCount`, `stage` (`QUOTE`/`PERSON`) e `age` (fase `PERSON`) |
| `GET …/{id}/history` | Histórico da versão |

## 5. Regras «Quando… então…» (`rules.custom`)

Formulário fechado (sem expressões livres): campo (`age`, `members_count`,
`plan`, `product`, `segment`, `relationship`, `participation_option`),
operador (`EQ NE GT GTE LT LTE BETWEEN`), segunda condição opcional, âmbito
(`PERSON`/`QUOTE`), prioridade (`order`), e ação:

- preço: `INCREASE_PERCENT`, `DISCOUNT_PERCENT`, `MULTIPLY`, `ADD_AMOUNT`,
  `SUBTRACT_AMOUNT`;
- aceitação: `REQUIRE_MEDICAL_REVIEW`, `REQUIRE_TECHNICAL_REVIEW`, `WARN`,
  `DECLINE`;
- elegibilidade (só `PERSON`): `NOT_ELIGIBLE` (a avaliação de elegibilidade
  passa a `HARD_STOP`, a cotação ganha um erro que bloqueia o envio) e
  `REFER_TO_UNDERWRITING` (`REFERRAL`). Só agravam uma decisão `ELIGIBLE`
  ou `WARNING`; nunca desfazem um bloqueio ou pendência do motor;
- validação: `VALIDATION_ERROR` (erro que bloqueia o envio) e
  `VALIDATION_WARNING`;
- fluxo: `REQUIRE_APPROVAL_BY_ROLE` com `role` (`SUBSCRIPTION_MANAGER` ou
  `ADMIN`): a aprovação da cotação só é aceite por esse perfil (um ADMIN
  pode sempre; outro perfil recebe SEC-403).

A etapa (`stage`: `ELIGIBILITY`, `PRICING`, `UNDERWRITING`, `VALIDATION`,
`WORKFLOW`) deduz-se da ação; se vier na linha, tem de coincidir. O campo
`total_premium` (prémio do último cálculo, só `QUOTE`) serve para validação,
aceitação e fluxo, nunca para preço nem elegibilidade. Os itens dos
requisitos trazem `stage` (e `requiredRole` nas regras de fluxo).

São executadas pelo motor de preços existente (não há um segundo motor),
por ordem determinística; o trace regista as aplicadas e as ignoradas.
Catálogo: `GET /business-config/rules/custom/catalog`.

## 5.1 Catálogo único de variáveis

`GET /business-config/formulas/variables[?productId=&usableIn=]` junta numa
resposta tudo o que o tenant pode usar: variáveis do motor por fase
(`SYSTEM`), parâmetros e valores auxiliares do `pricing.formulas` publicado
(`PARAMETER`, `AUXILIARY`), grupos/opções/campos/fórmulas do produto
(`PRODUCT_*`) e os campos das regras (`RULE_FIELD`). Cada entrada diz onde se
usa (`usableIn`: `PRICING_FORMULAS:PERSON|QUOTE`, `PRODUCT_FORMULAS`,
`RULE_CONDITIONS`). O teste de uma expressão (`POST /business-config/formulas/test`)
e a simulação de um conjunto devolvem o cálculo passo a passo (`steps` /
`explanation`: subexpressão, operação, operandos e resultado intermédio).

## 5.2 Camada geral do fornecedor (parâmetros da plataforma)

Os parâmetros de `/system-parameters` têm um nível:

| Nível | Parâmetros | Quem manda |
|---|---|---|
| `PLATFORM_MANDATORY` | estruturais (`pricing.rounding_policy`, `pricing.formula`, `capital.pro_rata_rule`) e legais (`tax.stamp_duty_pct` 0 %, `tax.arseg_levy_pct` 1 %) | o fornecedor; o tenant só consulta (PUT → 403) |
| `PLATFORM_DEFAULT` | operacionais (validade da cotação, beneficiários, validade das ligações, inflação médica) | o fornecedor dá o valor por omissão e pode estreitar os limites; o tenant ajusta dentro deles |

Prioridade: obrigatório → valor do fornecedor; por omissão → valor do tenant
enquanto estiver dentro dos limites do fornecedor (fora deles volta a valer
o geral, `tenantValueOutOfLimits: true`); sem versão do fornecedor → valor
do código. A resposta do tenant diz de onde vem o valor (`source`).

As contas da plataforma gerem a camada em `/platform/system-parameters`:
propor uma versão (motivo obrigatório, vigência opcional), aprovar por
**outra** conta (SEC-403 se for quem propôs), rejeitar, histórico e
reverter (cria uma versão nova, também por aprovar). Uma versão pendente de
cada vez. Tudo fica na auditoria da plataforma. Os estruturais só aceitam
os valores que o motor sabe executar (`allowedValues`): outro valor é uma
nova versão do sistema.

Impostos legais no cálculo: com modelo actuarial, o selo e a ARSEG usam a
taxa geral (o valor do modelo fica só no rasto como `modelRate`); sem modelo,
um encargo do tenant com código legal (`STAMP_DUTY`, `ARSEG_LEVY`, …) mantém
o lugar e o `included_in_premium`, mas a taxa é a geral. O componente TAX
regista `PLATFORM_PARAMETER:<código>` e a versão. Uma nova versão publicada
pelo fornecedor torna desatualizado o último cálculo das cotações abertas.

`GET /platform/formula-engine` mostra ao fornecedor, sem tenant, o catálogo
do motor (funções, operadores, limites, variáveis do sistema, campos, ações e
etapas das regras). As fórmulas e regras de negócio continuam a ser de cada
tenant.

## 5.3 Valores legais, tetos e dados de mercado (plano, fases 1 e 2)

- **Fonte legal:** cada versão de um parâmetro `LEGAL` exige `legalReference`
  (diploma e artigo) e aceita `sourceUrl`. Novos parâmetros:
  `legal.age_of_majority` (18, art. 130.º CC) e os tetos `LIMIT`
  `limits.dependent_max_age_with_proof` (27) e
  `limits.max_acquisition_commission_pct` (100 % = sem teto).
- **Tetos aplicados:** a elegibilidade usa a maioridade como limite «sem
  prova» e o teto de idade com prova (também nas exceções corporativas); a
  publicação de uma regra acima deles é recusada. A comissão do modelo
  actuarial é verificada ao submeter e ao aprovar.
- **Dados de mercado (`MARKET`):** `market.usd_aoa` (931,27) e
  `market.inflation_pct` (10,9 %), valores iniciais do Excel a 30/06/2026.
- **Constantes nas fórmulas:** `cambio_usd_aoa`, `inflacao_geral_pct`,
  `taxa_arseg_pct`, `taxa_selo_pct`, `maioridade` — só leitura, nomes
  reservados, valor e versão registados no rasto do cálculo.
- **Tabelas de referência:** `/platform/reference-tables` (versão inteira,
  duas contas, vigência); os tenants consultam em `/reference-tables` e usam
  `tabela("codigo", chave, "coluna")` nas fórmulas. As versões entram no
  rasto e na impressão digital da cotação.

## 5.4 Tarifa por produto, simulação e migração (fase 3)

- `GET /products/{id}/tariff`: os passos pela ordem do motor, com dono
  (CODE, PLATFORM, TENANT), versão publicada, rascunho e pendente de cada
  configuração, e um resumo por passo.
- `POST /products/{id}/tariff/simulate`: cria uma cotação de exemplo e
  calcula-a pelo caminho normal, com os rascunhos escolhidos
  (`configurationIds` ou `includeOpenDrafts`) a valer só dentro de uma
  transação revertida. Nada fica gravado. Devolve componentes e passos com
  dono e as prestações.
- `manage.py migrate_legacy_tariffs --tenant-code X [--dry-run]`: converte a
  tarifa antiga em rascunhos de `pricing.reference_premiums` e
  `pricing.factors`; o que não dá o mesmo prémio fica no relatório. As rotas
  antigas estão marcadas `deprecated` no contrato.

## 5.5 Aprovações e modelos de partida (fases 4 e 5)

- `GET /business-config/approvals/pending[?area=]` e `/count`: tudo o que
  espera pela segunda pessoa, com as diferenças face à versão publicada e se
  o utilizador atual pode aprovar. O catálogo indica a `area` de cada tipo.
- Modelos de partida do fornecedor em `/platform/templates` (tipos
  PRODUCT, ACTUARIAL_MODEL, FORMULA_SET, COVERAGE_LIBRARY; duas contas). Os
  tenants veem `/templates` e adotam com `POST /templates/{code}/adopt`:
  cópia para rascunhos, nunca ligação. `manage.py seed_platform_templates`
  carrega a configuração de referência de Angola e o modelo actuarial.

## 6. Ordem de cálculo (com modelo actuarial publicado)

Por pessoa: prémio puro por cobertura (LEV recalculado) → agravamento por
idade de adesão (SAU, só nova adesão) → factor de risco combinado (região,
participação nos custos; em SAG também dimensão, adesão e sector) → regras
`PERSON` → sobreprémio de pré-existência → fórmulas `PERSON` → ajustes
comerciais da cotação → σ
(volatilidade) → carregamentos `÷(1−eₐ−e_c−m)` → desconto comercial
limitado. Total: regras `QUOTE` → ajustes `pricing.adjustments` → impostos
(selo + ARSEG somados sobre o prémio líquido) → fórmulas `pricing.formulas`.

Sem modelo actuarial a ordem por pessoa é: prémio de referência → factores →
opção de participação → ajustes → regras `PERSON` → sobreprémio de
pré-existência → fórmulas `PERSON` → ajustes comerciais.

## 7. Modelo actuarial pela interface (decisão A1)

O modelo é a configuração `pricing.actuarial_model` e segue o ciclo da §2.
Ao gravar é validado (`apps/business_config/domain/actuarial_model.py`):
mapeamentos de planos/coberturas, carregamentos em [0, 1) e com encargos +
comissão + margem < 100 %, prestações, relatividades, capitais, parâmetros
dos prémios puros, tabelas de grupo, ajustes, descontos em [−1, 0],
participação nos custos e opções de cálculo. A mensagem indica o caminho do
campo (ex.: `assumptions.loadings.SAU: …`).

| Rota | Função |
|---|---|
| `POST /business-config/actuarial-model/import` | Multipart: `file` (.xlsx, ≤ 10 MB), `effectiveFrom`, `keepPublishedSettings` (omissão `true`), `dryRun`. Cria uma versão DRAFT (ou só devolve o resumo com `dryRun`). O ficheiro fica anexado à versão (`ACTUARIAL_WORKBOOK`, SHA-256) |
| `GET /business-config/actuarial-model/template` | Excel de referência, para preencher e importar |
| `GET /business-config/actuarial-model/catalog` | Secções editáveis, opções de cálculo, valores recomendados e valores válidos do modelo publicado (regiões, sectores, venda cruzada, participação nos custos) |

O Excel tem de ter sido guardado pelo Excel depois de recalculado (o
importador lê os valores calculados; um ficheiro sem eles é recusado).

`calculation_settings`:

```json
{
  "profile_defaults": {
    "SAU": {"region": "Luanda (Grande Luanda)", "crossSell": "Nenhuma", "noClaimsRenewal": false,
            "costSharing": {"copaymentAoa": 0, "reimbursementShare": 1,
                            "outpatientDeductibleAoa": 0, "inpatientDeductibleAoa": 0}},
    "SAG": {"region": "Luanda (Grande Luanda)", "crossSell": "Nenhuma", "noClaimsRenewal": false,
            "costSharing": {"copaymentAoa": 0, "reimbursementShare": 1,
                            "outpatientDeductibleAoa": 0, "inpatientDeductibleAoa": 0},
            "industry": "Comércio e Serviços", "adhesion": "MANDATORY"}
  },
  "entry_age_on_renewal": "ORIGINAL_ENTRY_AGE"
}
```

- `profile_defaults` (A4): completam o `actuarialProfile` do tomador; o que
  o tomador indica prevalece. O trace `ACTUARIAL_PROFILE_RESOLVED` mostra o
  perfil efetivo e os campos que vieram por omissão. Os recomendados são os
  de referência do Excel (não alteram o prémio).
- `entry_age_on_renewal` (A6): `ORIGINAL_ENTRY_AGE` | `CURRENT_AGE` |
  `NOT_APPLIED`. Um modelo publicado antes destas opções mantém o
  comportamento anterior (sem valores por omissão; sem agravamento de
  adesão em renovações).

Fracionamento (A8): `pricing.fractionation` (`installments[]`:
`frequency` ANUAL/SEMESTRAL/TRIMESTRAL/MENSAL, `loading` em fração) vale para
todas as apólices; sem ela usa-se a tabela do modelo usado no cálculo.

Agravamento clínico (A5): percentagem decidida pelo subscritor, com valor
por omissão por gravidade em `underwriting.pre_existing_conditions`
(`LOW` 15 %, `MODERATE` 30 %, `MODERATE_HIGH` 50 %, `HIGH` exclusão).

## 8. Configuração por produto (grupos de opções, campos, valores e fórmulas)

Pedido de 2026-10-15, a partir dos ecrãs de referência do produto
(«Grupo de opções», «Campos», «Formulário», «Valores», «Fórmulas»). Cada
produto tem a sua configuração, guardada como configuração de negócio com a
chave `product.pricing_setup:<id do produto>`: tem rascunho, aprovação por
outra pessoa (quatro olhos), histórico, comparação, reversão e documentos
anexos como as restantes. Código: `apps/business_config/domain/product_setup.py`.

| Separador | Na configuração | Notas |
|---|---|---|
| Grupo de opções | `optionGroups[]` {code, name, listType RADIO/SELECT/CHECKBOX/TOGGLE/AUTOCOMPLETE, required, maxSelected, options[]} | Escolhas da cotação em `selection.productOptions` |
| Campos | `fields[]` {code, label, type NUMBER/INTEGER/TEXT/DATE/BOOLEAN, required, min, max, default, unit} | Valores em `selection.productFields` |
| Formulário | `showInForm`, `order` | `GET /products/{id}/pricing-setup/form` |
| Valores (Taxas e Valores) | `values[]`: Simples, Múltiplas opções, Fixo, Por intervalo de idade, Pelo valor do campo, Condicional de opção | Agregação de várias opções/pessoas: SUM (Somar), PRODUCT, MAX, MIN |
| Fórmulas | `formulas[]` {code, name, expression, flags, frequency, unit, minResult, order, active, scope} | Editor por blocos: grupos, `<grupo>__<opção>` (1/0), campos numéricos, outras fórmulas, `premio_tecnico`, `pessoas`; operadores + − × ÷ ( ) e min/max/abs/round |

Indicadores das fórmulas: **Prémio** (o resultado passa a ser o prémio anual
da cotação; no máximo uma por cotação), **Capital** (registado, não altera o
prémio), **Ocultar** (não se mostra ao cliente), **Fracionamento** (valor da
prestação na frequência indicada, usado na emissão em vez do encargo de
`pricing.fractionation`), **Conversão** (guardado; ver lacuna abaixo).
`minResult` é o resultado mínimo. Âmbito (`scope`): categorias do plano,
planos (subprodutos) e tipos de apólice (INDIVIDUAL/GROUP); vazio = todos.

No cálculo, as fórmulas do produto correm no fim, depois das fórmulas gerais
(`pricing.formulas`), com o prémio do motor como `premio_tecnico`. Uma fórmula
de prémio que se aplique substitui o total. A versão usada fica em
`businessConfigurationVersions` e os resultados no componente
`PRODUCT_FORMULAS` e no passo `PRODUCT_FORMULAS_EVALUATED` da explicação.

Lacunas (não inventadas): o indicador **Conversão** não tem regra definida
(moeda/unidade de conversão) e não altera o cálculo; o campo **Upload** do
ecrã não tem semântica descrita — os ficheiros anexam-se à versão da
configuração (documentos da configuração de negócio). Os separadores PDFs,
Regras de Subscrição, Regras por Produto, Limites Operacionais e Workflow
aparecem nas imagens sem detalhe; o backend já tem modelos de documentos,
regras «Quando… então…», limites de autoridade e fluxo de aprovação, mas
não por produto.


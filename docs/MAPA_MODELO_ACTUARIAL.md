# Mapa do modelo actuarial (Excel → backend)

Fonte: `Modelo_Actuarial_Saude_SAU_SAG_Angola.xlsx` (cópia idêntica em
`backend/apps/business_config/seed/`, SHA-256 `0e6b2142…511d1c`).
Importação: `apps/business_config/seed/actuarial_model.py`
(`build_actuarial_model`). Publicação: `manage.py publish_actuarial_model`
ou pela API (`configKey = pricing.actuarial_model`, ciclo DRAFT → aprovação).
O modelo é marcado `DRAFT_REQUIRES_ACTUARIAL_APPROVAL`: os valores vêm do
Excel e precisam de validação do actuário responsável antes de produção.

## Folhas

| Folha | Fórmulas | Papel | Importado para |
|---|---|---|---|
| `Dashboard_Premissas` | 277 | Câmbio, inflação, carregamentos (σ, eₐ, e_c, m), impostos, fraccionamento, exposição etária, pressupostos por cobertura (λ, custo, CV, rede), relatividades idade×sexo, factores de plano | `assumptions`, `coverage_assumptions`, `age_gender_relativities`, `plan_factors` |
| `Matriz_SAU` | 1 689 | Prémio puro por plano×cobertura (SAU), capitais, estatuto B/O/— | `plan_coverages.SAU`, `reference_pure_premiums` (λ, custo ajustado, tendência, μ, σ, LEV, célula `S`) |
| `Matriz_SAG` | 1 827 | Idem SAG; dimensão do grupo, adesão, sector | `plan_coverages.SAG`, `reference_pure_premiums`, `group_size_factors`, `group_participation_factors`, `industry_factors` |
| `Regras_Ajustes` | 90 | Co-pagamento, comparticipação, franquias, gravidade clínica, idade de adesão, descontos, factor regional | `adjustment_assumptions` (incl. `cost_sharing` com os **valores adoptados** das colunas H/F) |
| `Calculador` | 213 | Cotação de referência (cadeia completa) | — (reproduzido pelo motor; teste de referência) |
| `Listas` | 0 | Listas de validação e mapa plano SAU→categoria SAG | `plan_code_mapping` |

## Cadeia do `Calculador` e correspondência

| Excel | Significado | Backend | Estado |
|---|---|---|---|
| `F25:G25` | Escalão etário e chave sexo\|escalão | `resolve_actuarial_coverage_premiums` (`age_band`, `sex`) | ✔ |
| `H35:H51`, `G35:G51` | Prémio puro de referência por cobertura incluída | idem; `coverage_code_mapping` liga coberturas do plano a códigos actuariais | ✔ (LEV recalculado a partir do capital) |
| `K25` = SUMPRODUCT(incl., PP, relatividade) | Prémio puro base por pessoa | componentes `ACTUARIAL_<COD>` (BASE) | ✔ coincide ao cêntimo por cobertura |
| `I25` agravamento clínico | Gravidade da pré-existência | decisão de pré-existência `ACCEPTED_WITH_LOADING` (`loadingPct` pelo subscritor; tabela `pre_existing_severity` como referência) | ✔ (percentagem escolhida pelo subscritor) |
| `J25` agravamento idade de adesão (SAU) | `Regras_Ajustes!C79:C83` | `ACTUARIAL_ENTRY_AGE_LOADING`; em renovações conforme `calculation_settings.entry_age_on_renewal` (A6) | ✔ |
| `C55:C59` participação nos custos | Co-pag., comparticipação, franquias | `actuarialProfile.costSharing` → factor no `ACTUARIAL_RISK_FACTOR` | ✔ **novo** |
| `C60` factor regional | `Regras_Ajustes!C104:C108` | `actuarialProfile.region`, SAU e SAG | ✔ (antes só SAG) |
| `C61:C63` dimensão, adesão, sector (SAG) | `Matriz_SAG!B100:D121` | `resolve_actuarial_group_adjustment` | ✔ |
| `C64` factor de risco combinado | produto dos anteriores | `ACTUARIAL_RISK_FACTOR` | ✔ (igual ao Excel a 10⁻⁷) |
| `C65` σ | `sig_SAU` / tabela por dimensão (SAG) | `ACTUARIAL_VOLATILITY_LOADING` | ✔ |
| `C66`, `C79` | Carregamentos eₐ+e_c+m, prémio comercial bruto `÷(1−carreg.)` | `ACTUARIAL_COMMERCIAL_LOADINGS` | ✔ |
| `C67:C70` | Desconto agregado (SAU), venda cruzada, renovação sem sinistros, limite `desc_max` | `ACTUARIAL_COMMERCIAL_DISCOUNT` (`actuarialProfile.crossSell`, `noClaimsRenewal`) | ✔ **novo** |
| `C71`, `C85` | Imposto do selo + ARSEG somados × prémio líquido | `STAMP_DUTY`, `ARSEG_LEVY` | ✔ **corrigido** (antes em cascata) |
| `C86` | Prémio total anual | `PricingRun.totalAmount` | ✔ diferença medida: **+0,02 Kz** em 2 303 121,49 |
| `C87` | SAG: prémio por colaborador-tipo × n.º de colaboradores | o backend soma as pessoas reais da cotação | ✔ método decidido (A3: soma das pessoas reais) |
| `E91:E94` | Prestação com encargo de fraccionamento | `issuance_service.installment_amount`: `pricing.fractionation` (todas as apólices, A8) ou a tabela da versão do modelo usada no cálculo | ✔ |
| `M25` decisão de subscrição | Texto da decisão | decisão de elegibilidade/aceitação (motor de elegibilidade) | parcial |

## Entradas do cálculo

`proposer.attributes.actuarialProfile` (SAU e SAG):

```jsonc
{
  "region": "Luanda (Grande Luanda)",
  "costSharing": {"copaymentAoa": 5000, "reimbursementShare": "0.8",
                  "outpatientDeductibleAoa": 0, "inpatientDeductibleAoa": 0},
  "crossSell": "Nenhuma",
  "noClaimsRenewal": false,
  "industry": "Comércio e Serviços",        // só SAG (obrigatório)
  "adhesion": "MANDATORY",                    // só SAG: MANDATORY | VOLUNTARY
  "participationRate": "0.6",                 // só SAG voluntária
  "groupHeadcount": 40                        // opcional; por omissão conta os titulares
}
```

Os valores têm de existir nas tabelas do modelo (o Excel usa `MATCH`
exacto); um valor desconhecido é um erro de configuração explícito (HTTP 422).
Campos ausentes são completados pelos valores por omissão configurados no
modelo (`calculation_settings.profile_defaults`, decisão A4; os
recomendados são os de referência do Excel, factor 1). Um modelo publicado
sem essas opções mantém o comportamento estrito: campos ausentes não são
aplicados e o SAG exige sector, região e adesão.

## Teste de referência

`backend/tests/quote/test_actuarial_excel_reference.py` lê as células
calculadas do próprio Excel e compara, pela API real (plano de mercado,
modelo publicado, proponente, 4 pessoas, opcionais escolhidos):
`K25:K28` (±0,10 Kz), `C64` (10⁻⁷), `C70` (exacto), `C85` (±0,05 Kz),
`C86` (±0,10 Kz) e `E91:E94` (±0,10 Kz). As diferenças vêm apenas do
arredondamento por componente (OD-006).

`backend/tests/quote/test_actuarial_excel_reference_sag.py` faz o mesmo com
`Calculador!C5 = SAG` (plano `GRP-QUADROS`, 40 colaboradores, adesão
obrigatória, Comércio e Serviços; as restantes entradas do ficheiro). Como o
Excel só guarda os valores do cenário em que foi gravado, os valores
esperados (`tests/quote/fixtures/calculador_sag_expected.json`) vêm do
recálculo das fórmulas do próprio livro com `backend/tools/recalc_calculador.py`
(pycel). O script valida o método antes de o usar: recalculado com `C5 = SAU`,
reproduz os valores guardados pelo Excel com diferença ≤ 5×10⁻⁹. Compara
`K25:K28`, `C64`, ausência de desconto (`C70 = 0`), `C85`, `C86` e `E91:E94`;
`C87` (× 40) não se aplica (A3).

## Edição e importação pela interface

Ver `MOTOR_CONFIGURAVEL.md` §7: o modelo edita-se como qualquer configuração
(com validação ao gravar) e importa-se de um `.xlsx` com
`POST /api/v1/business-config/actuarial-model/import`.

# Especificação — Fechar Integração Completa do Modelo Actuarial SAU/SAG

## 1. Objetivo

Concluir as 8 frentes de trabalho indicadas no estado atual do projeto, **aproveitando tudo o que já está feito e corrigindo apenas o que está incompleto**:
1. Corrigir arranque (OpenAPI / business_config views import).
2. Ligar o modelo actuarial SAU/SAG 94 prémios do workbook **ao pricing em produção** (não só rascunho).
3. Tornar **todas as tarifas operacionais 100% configuráveis** pelo GTE via `BusinessConfig` (sem intervenção do fornecedor).
4. **Completar renovação por experiência** usando histórico de claims/premiums já importados.
5. Ligar cenários de cotação (R5) à análise actuarial: indicadores LR/freq/custo médio.
6. Confirmar permissões + 4-eyes + autonomia GTE.
7. **Testar fluxos completos** ponta-a-ponta sem Testcontainers se preciso.
8. **Documentar** parâmetros + fórmulas para autonomia diária GTE.

## 2. Pressupostos de Partida (confirmado pelo utilizador)

- ✅ **(Frente 1 — FECHADA PARCIAL)**: OpenAPI build passa (`7 passed`). Django check OK. Importações de views em business_config corrigidas.
- ✅ **(Frente 2 — 70%)**: Importador do Excel actuarial recolheu 94 prémios puros, mapeou planos/coberturas e guardou dados de relatividade idade/sexo + LEV. Caminho condicional no motor existe (usa o modelo quando está publicado + aprovado). Headcount SAG por titulares. Perfis SAG por atributos do Proposer. A configuração **ainda não foi publicada / activada**.
- ❌ **(Frente 3 — 0%)**: Parametrização operacional via BusinessConfig — ainda não ligada.
- ❌ **(Frentes 4 a 8 — 0%)**: Por fazer.

## 3. Requisitos Funcionais (por frente)

### Frente 1 — Corrigir Arranque e OpenAPI Sync

| ID | Descrição |
|---|---|
| R-01 | `manage.py check` devolve 0 erros (incl. apps `business_config`, `claims`, `platform_admin`). |
| R-02 | `manage.py build_openapi --check` devolve `OK` (sem diff do contrato). |
| R-03 | Suite de testes OpenAPI: 7 testes passam (como está hoje). |
| R-04 | Todas as views importadas em `business_config/interfaces/urls.py` existem nos módulos de views correspondentes. |

### Frente 2 — Ligar Modelo SAU/SAG ao Pricing Ativo

| ID | Descrição |
|---|---|
| R-10 | Seed `actuarial_model.py` produz `PricingConfiguration` **PUBLICADA** (não só DRAFT) + `RatingTable` completas (94 células mapeadas por cobertura, idade, sexo, plano, segmento IND/GRUPO). |
| R-11 | `PricingEngine.resolve_rating_context(...)` escolhe **automaticamente** o modelo actuarial publicado, quando existe, em detrimento de quaisquer tabelas placeholder antigas. |
| R-12 | **Mapeamento exato dimensões**: (plan_code, age, sex, benefit_code, segment INDIVIDUAL/GROUP) → prémio puro por vida/ano. |
| R-13 | **Factores de grupo**: headcount (≥ 50 vidas → desconto grupo %), idade média do grupo, sexo-ratio do grupo aplicados como ajuste multiplicativo ao prémio puro (antes de impostos e loadings comerciais). |
| R-14 | **Headcount SAG**: cálculo por contagem de `QuoteMembers` com `relationship_code = TITULAR` (como está em comentário hoje). |
| R-15 | **Carregamentos do workbook**: loadings técnicos, margem comercial (ex.: 15% + 10%) aplicados via 2 configurações publicadas do modelo (podem ser publicadas separadamente). |
| R-16 | `price_quote()` → `pricing_engine.calculate()` devolve, para o **mesmo conjunto de vidas**, valores **iguais (± 0.01%)** ao cálculo manual no Excel do modelo SAU/SAG de referência. |
| R-17 | Perfil SAG (seguro por grupos/tipo contrato) detetado por atributo `proposer.attributes.contract_type = "SAG"` ou `plan.plan_settings.segment = "SAG"`. |
| R-18 | Calculo do LEV (Limiar de Esperança de Vida / Relatividade por idade) incluído no pricing output detalhado por membro (`member_line_items`), para auditoria posterior GTE. |

### Frente 3 — Tornar Tarifas Operacionais Parametrizáveis

| ID | Descrição |
|---|---|
| R-30 | **Impostos**: Chave `pricing.taxes_fees` no catálogo BusinessConfig tem `form_schema` publicado, 4-eyes, e valida `imposto_selo_pct (0..100)`, `outros_impostos_pct (0..100)`, `imposto_prestacoes_sociais_pct (0..100)`. O pricing engine **aplica** esses valores quando publicados. |
| R-31 | **Agravamentos / Descontos comerciais**: Chave `pricing.adjustments` → `age_load_pct`, `pre_existing_load_pct`, `group_discount_headcount` (tabela: `>=50 → 5%, >=100 → 8%, >=500 → 12%`). Aplicados no engine. |
| R-32 | **Carregamentos técnicos**: `pricing.actuarial_loads` → `technical_margin_pct`, `commercial_margin_pct`, `inflation_loading_pct`. Separados para auditoria. |
| R-33 | **Capitais e Copagamentos**: `product.capitals_sublimits` e `product.member_participation` — as matrizes de capitais de `market_templates.py` são **lidas via BusinessSnapshot** no pricing_engine (hardcoded matriz é fallback se não houver versão publicada). |
| R-34 | Todas as chaves novas/atualizadas aparecem no `catalog.py` com `form_schema` + `validators.py`. A alteração no PricingConfigPanel do frontend aparece sem JS adicional (formSchema-driven). |
| R-35 | **Four-eyes**: Publicação de cada ajuste requer aprovador ≠ criador. |

### Frente 4 — Renovação por Experiência (Claims Histórico → Prémio Renovação)

| ID | Descrição |
|---|---|
| R-40 | Quote `quote_type=RENEWAL` + `source_policy_id` ativa o cálculo por experiência automaticamente após `price_quote()`. |
| R-41 | **Dados usados**: histórico de `ClaimRecord` + `PremiumRecord` de `policy_id = source_policy_id` nos últimos 24 meses. |
| R-42 | **Fórmula (indicativa; parametrizável em R-31)**: `prémio renovação = prémio_técnico_base × credibility_factor × LR_bonus_penalty × trend_loading`. |
| R-43 | **Bonus-malus por LR**: `LR < 50%` → bónus -10%; 50-65% → neutro (0); 65-85% → +5%; > 85% → +15%. (Valores por omissão parametrizáveis). |
| R-44 | **Credibilidade**: `n_sinistros >= 20` → 100% credibilidade; `n < 5` → 20% credibilidade. (Parametrizado no BusinessConfig `renewal.experience_factors`). |
| R-45 | **Output renovação**: `renewal_breakdown_json` anexado ao `PricingRun` com `historical_summary`, `credibility`, `bonus_malus_pct`, `trend_pct`, `base_premium`, `final_premium`, auditoria. |
| R-46 | Jornada cliente no portal: 7-step renovação mostra indicador R-44 ao cliente em "Sua proposta de renovação" (sem revelar tabelas técnicas). |

### Frente 5 — Ligar Cenários de Cotação (R5) à Análise Actuarial

| ID | Descrição |
|---|---|
| R-50 | Criar 1+ cenários de cotação (ScenarioService) e, quando histórico de claims do cliente existe, `scenario_service.projection` é acrescentado automaticamente ao `scenario.parameters.projection`. |
| R-51 | Endpoint `compare_scenarios()` acrescenta 3 novas colunas ao diff tabela: `lossRatioExpectedPct`, `frequencyPerLifeYear`, `averageClaimCost` (todos indicativos) para cada cenário. |
| R-52 | Frontend `ScenariosPanel.compareQuery.data` renderiza as novas colunas (caso existam; hidden se histórico claims não existir). |
| R-53 | **Não quebra a comparação existente**: cenários que não têm projections mostram apenas o que existia antes (prémios, coberturas). |

### Frente 6 — Permissões + Autonomia GTE

| ID | Descrição |
|---|---|
| R-60 | Roles existentes são suficientes: `ADMIN`, `SUBSCRIPTION_MANAGER`, `SUBSCRIBER`, `PLATFORM_ADMIN`. **NÃO criar roles novos nesta frente.** (Conforme nota do cliente: "sem criar perfis novos sem acordo"). |
| R-61 | `ROLE_PERMISSIONS` validadas: `SUBSCRIPTION_MANAGER` tem `pricing-config:manage`, `quote:calculate`, `product:manage`, `audit:read` — parametrização diária GTE autónoma 100%. |
| R-62 | 4-eyes check mantido para publicação BusinessConfig. Nenhuma role consegue publicar a própria alteração. |
| R-63 | Parametrização de impostos/capitais por GTE: `AuthorityPolicy.published.pricing_config_scope = ALL` para permitir editar todas as chaves (hoje default). |

### Frente 7 — Testar Fluxos Completos

| ID | Descrição |
|---|---|
| R-70 | **Fluxo SAU Individual**: criar proponente INDIVIDUAL, 1 titular (idade 40 sexo M, sem agrav.), plano Base IM, price → prémio igual ao Excel de referência ±0.01. |
| R-71 | **Fluxo SAG Grupo**: proponente GRUPO com 60 titulares + agregados (75 vidas), plano Grupo ADMIN → cálculo aplica desconto headcount ≥ 50; compara com Excel. |
| R-72 | **Renovação por experiência**: aplicar seed `claims_historical_renewal_test` (24 meses claims, LR ~ 75%) → `price_quote()` de renovação devolve `+5%` por bonus-malus. |
| R-73 | **Parametrização GTE**: alterar `pricing.taxes_fees.imposto_selo_pct` de 10 → 12 via BusinessConfig (DRAFT→PEND→APPROVE→PUBLIC), recalcular 1 cotação → variação +1.8% (só imposto) comparado. |
| R-74 | **Isolamento multi-tenant**: criar tenant B, subscritor B, apólice 1; subscritor A (tenant A) **não vê** apólice de B em `/policies`. |
| R-75 | **4-eyes**: X cria BusinessConfig draft; X tenta aprovar → 403 FourEyes; Y aprova → 200. |
| R-76 | **Sem Testcontainers?** Se não existir Docker/Postgres, suite corre com `DATABASE_URL=sqlite://:memory:` para 95% dos testes; reservar 1 teste end-to-end real com connection string local do desenvolvedor (env var `Q360_TEST_REAL_PG`). |
| R-77 | Todos os testes do módulo pricing (`pytest tests/pricing tests/apps/claims tests/business_config`) passam. Sem regressões. |

### Frente 8 — Documentação Parâmetros + Fórmulas

| ID | Descrição |
|---|---|
| R-80 | Criar documento português `docs/Parametros_E_Formulas_GTE.md` (apenas se ficheiro já existir na pasta docs; senão usar Markdown file em backend/README de operação): lista **cada uma das 26 chaves BusinessConfig** + descrição, valores por omissão, fórmulas, 4-eyes. |
| R-81 | Descrição do modelo actuarial SAU/SAG: 94 células, fórmulas `prémio_puro × grupo_factors × loads × impostos × agrav`. |
| R-82 | Explicação passo-a-passo renovação por experiência. |
| R-83 | Como publicar uma alteração de preço (DRAFT→PENDING→APPROVED→PUBLIC, 4-eyes, effective_from). |
| R-84 | Como validar que o preço foi aplicado (comparar cotação vs Excel). |
| R-85 | Glossário de termos actuariais (LEV, LR, freq, custo médio, credibility, bonus-malus, segmento SAU vs SAG). |
| R-86 | O documento é **em Português de Angola** (pt-AO). |

## 4. Requisitos Não Funcionais

| ID | Descrição |
|---|---|
| NF-01 | **Zero regressões.** Os preços de cotações DRAFT/READY existentes no ambiente de staging (com configuração placeholder antiga) continuam a ser calculáveis sem erro 5xx, mesmo que os valores mudem. Nota no changelog explicando a migração para o modelo SAU/SAG. |
| NF-02 | **Performance.** `price_quote` para grupo 100 vidas com modelo SAU/SAG completo: ≤ 3s p95. |
| NF-03 | **Backward compatibility de APIs.** Nenhuma view existente muda path ou contracto. Apenas acrescentar campos opcionais (indicativos) aos JSON responses. |
| NF-04 | **Auditoria total.** Toda a publicação de configuração (impostos, capitais, modelo actuarial) é registada em `AuditEvent` com `before`/`after`. Toda a renovação regista `correlation_id`. |
| NF-05 | **Isolamento de dados.** O modelo actuarial é publicado **por tenant**. A seguradora A pode ter configuração SAU 2026-Q3 publicada; corretora B pode ainda estar em versão 2025-Q4. Sem impacto cruzado. |

## 5. Critérios de Aceitação

### Regras

| AC-ID | Tipo | Enunciado |
|---|---|---|
| AC-01 | rule | `manage.py check` + `manage.py build_openapi --check` passam sem erros em ambiente local. |
| AC-02 | rule | Cotação SAU Individual Benchmark (40M IM Base) tem `prémio_liquido = referência_excel(tol ±0.5%)`. |
| AC-03 | rule | Cotação SAG Grupo (75 vidas ≥ 50 headcount) aplica desconto grupo esperado na comparação com Excel. |
| AC-04 | rule | Publicar `pricing.taxes_fees` como GTE (SUBSCRIPTION_MANAGER) via 4-eyes → 200. Publicar sem 4-eyes (self-approve) → 403. |
| AC-05 | rule | `price_quote(quote_type=RENEWAL, source_policy_id=...)` com claims seed LR 75% → `final_premium = base × (1 + 0.05 ± 0.0001)`. |
| AC-06 | rule | `compare_scenarios(2_ids_com_histórico_claims)` tem colunas novas no JSON `lossRatioExpectedPct`. |
| AC-07 | rule | `pytest tests/pricing tests/claims tests/business_config tests/quote` passam (sem ignorar todos os failures). |
| AC-08 | rule | Documento pt-AO parâmetros e fórmulas existe com pelo menos 1 tópico para cada frente (R-30..R-45). |

### Rubricas

| AC-ID | Tipo | Enunciado | Escala | Limite Passagem |
|---|---|---|---|---|
| AC-09 | rubric | Autonomia GTE: % de parâmetros operacionais hoje editáveis sem código. | 2 = ≥ 95% dos operacionais; 1 = 75-94%; 0 = < 75%. | ≥ 1.5 |
| AC-10 | rubric | Mapeamento Excel→motor (94 células). | 2 = match ±0.01% em ≥ 90/94 células; 1 = ≥ 75; 0 = < 75. | ≥ 2 (exigido para conformidade do modelo) |
| AC-11 | rubric | Qualidade suite testes sem Docker. | 2 = ≥ 40 testes isolados passam em sqlite; 1 = ≥ 25; 0 = < 25. | ≥ 1.5 |

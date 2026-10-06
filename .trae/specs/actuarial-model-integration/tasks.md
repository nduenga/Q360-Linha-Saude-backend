# Plano de Implementação — Integração Modelo Actuarial SAU/SAG (8 Frentes)

## Tarefa 1: Validar Arranque + OpenAPI Sync (Frente 1)

**Prioridade**: HIGH  
**Dependências**: Nenhuma  
**Cobertura AC**: AC-01  
**Estimativa**: 30-60 minutos

### Objetivo
Garantir que `manage.py check` e `manage.py build_openapi --check` passam. Este passo é verificação, não implementação — corrige apenas importações quebradas se for encontrado.

### Passos
1. **Executar**: `manage.py check` no backend. Se houver erros (missing views no business_config urls.py etc.): corrigir.
2. **Executar**: `manage.py build_openapi --check` → garantia sem alterações acidentais de contrato.
3. **Executar se possível**: `pytest tests/openapi_test.py` ou equivalente para confirmar os 7 testes passam.
4. **Não mexer** em lógica de negócio nesta tarefa.

### TR (Test Requirements)
| Tipo | Texto |
|---|---|
| **rule** | `manage.py check` → exit code 0. |
| **rule** | `manage.py build_openapi --check` → exit code 0 + mensagem `OK | no changes`. |
| **rule** | 7 testes OpenAPI → pass todos. |

---

## Tarefa 2: Ligar Modelo Actuarial SAU/SAG ao Pricing Ativo (Frente 2)

**Prioridade**: HIGHEST  
**Dependências**: Task 1 (ambiente tem de arrancar)  
**Cobertura AC**: AC-02, AC-03, AC-10  
**Estimativa**: 4-6 horas

### Objetivo
Passar de **"dados do Excel em rascunho" → "modelo publicado e usado no pricing real"**. Tudo isto deve manter a estrutura existente em `pricing_engine.py`, `pricing.py` (business_config), e `actuarial_model.py`.

### Passos
1. **Passo 2.1**: Ler `apps/business_config/seed/actuarial_model.py` (hoje `seed`). Garantir que o output do seed é **PUBLICADO** (não DRAFT) no tenant de teste.
   - Função `apply_default_pricing_configuration` hoje cria DRAFT. Adicionar variante `force_publish = True` quando `Q360_ENVIRONMENT = dev|test|staging` (production continua manual).
   - Garantir `RatingTable`/`PricingParameterSet` geradas no DB têm 94 células preenchidas (verificar COUNT por cobertura/plano).

2. **Passo 2.2**: Em `pricing_engine.py`, método `_resolve_rating_table(plan_id, effective_date, ...)` — **garantir escolha auto**:
   - Se existe `Published PricingParameterSet + RatingTable` de actuarial_model publicado → **usar estes em PRIORIDADE** (dar override a quaisquer placeholders antigos).
   - Senão, cair para placeholder antigo (compatibilidade).

3. **Passo 2.3**: **Mapa dimensões** (hoje parcial no código): confirmar que a lookup `(plan.code, age, sex, benefit_code, segment IND/GRUPO) → prémio puro → calcula LEV relatividade idade` funciona para as 94 células de referência do seed. Criar lookup indexado no motor para performance.

4. **Passo 2.4**: **Aplicar fatores de grupo** e **headcount SAG**:
   - `headcount = Count(QuoteMembers where relationship_code = TITULAR)`
   - Buscar `group_discount_headcount` table a `pricing.adjustments` (criar no catálogo se não existir, fallback padrão: <50=0%, 50-99=5%, 100-499=8%, ≥500=12%).
   - Multiplicar `prémio puro médio` × `1 - group_discount_pct`.
   - SAG segment detetado por `proposer.attributes.contract_type = SAG` OU `plan.settings.segment = SAG` (prioridade 1: proposer).

5. **Passo 2.5**: Aplicar **loads técnicos e comerciais** (15% + 10% = 26.5% compostos) via valores padrão do `pricing.actuarial_loads` BusinessConfig (ainda não publicado → fallback hardcoded 15% tech + 10% commercial = 26.5% compostos; se publicado → usar publicado).

6. **Passo 2.6**: Output `member_line_items` por membro no `PricingRun.total_detail_json` → acrescentar campos: `pure_premium`, `lev_factor_pct`, `age_sex_relativity_pct`, `group_load_applied_pct`; para auditoria manual GTE.

7. **Passo 2.7**: **Teste de validação 94 células**: Criar `tests/pricing/test_actuarial_model_94.py` (isolado, sqlite se preciso) que corre cada uma das 94 células e compara `prémio_calculado / prémio_excel → diff ≤ 0.01%`. Reportar diffs por célula.

### TR
| Tipo | Texto |
|---|---|
| **rule** | Seed `actuarial_model.py` → `PricingConfiguration.status = PUBLISHED` no tenant default. |
| **rule** | `price_quote(SAU_IND_40_BASE)`: valor corresponde a Excel ± 0.5% (AC-02). |
| **rule** | `price_quote(SAG_GRP_75_ADMIN)`: desconto headcount aplicado (AC-03). |
| **rubric** Match 94 células. ≥ 90/94 células (±0.01%) → PASS. (AC-10) ≥ 2. |

---

## Tarefa 3: Parametrizar Tarifas Operacionais por GTE (Frente 3)

**Prioridade**: HIGH  
**Dependências**: Task 2 (publicar modelo actuarial) e Task 1  
**Cobertura AC**: AC-04, AC-09  
**Estimativa**: 3-4h

### Objetivo
Hoje muitos valores estão hardcoded (imposto selo 10%, margens etc.). O GTE deve mudá-los via **PricingConfigPanel** sem escrever código.

### Passos
1. **Catalog.py**: Adicionar / validar estas chaves **existem** em BusinessConfig `catalog.CATALOG` (não é preciso adicionar todas novas; muitas já existem como placeholder):
   - ✅ Existentes: `pricing.factors`, `pricing.adjustments`, `pricing.taxes_fees`, `pricing.actuarial_model`
   - Adicionar ou completar:
     - `pricing.actuarial_loads` (tech_margin_pct, commercial_margin_pct, inflation_loading_pct, commission_pct)
     - `pricing.group_discounts` (tabela headcount: min/max + pct)
     - `product.member_participation` + `product.capitals_sublimits` (tornar BusinessConfig fonte oficial)

2. **FormSchema**: Criar/atualizar `form_schema` para cada chave em `catalog.form_schemas`. Exemplos:
   - `pricing.taxes_fees`: `imposto_selo_pct (range 0-100, step 0.1)`, `outros_impostos_pct`, `seguradora_social_pct`
   - `pricing.adjustments`: `agravamento_idade_pct_slider`, `pre_existing_load_pct`, `smoker_load_pct`
   - `pricing.group_discounts`: array de objetos `{min_headcount, max_headcount, discount_pct}` (5%, 8%, 12% defaults)

3. **Validators.py**: acrescentar regras (ex.: sum of loads ≤ 100%; group_discounts não overlap min/max).

4. **Resolver no Motor**: `pricing_engine.py` + `BusinessSnapshot.load()` têm de **ler estas chaves PUBLICADAS** (não hardcoded).
   - Fallback para valores default documentados se NÃO publicado.
   - Chamar `validate_for_publication` do BConf para validar intervalos 4-eyes.

5. **Teste 4-eyes**: Criar teste integration que X=SUBSCRIPTION_MANAGER cria draft → X aprova → deve 403; Y=ADMIN aprova → 200. (AC-04)

### TR
| Tipo | Texto |
|---|---|
| **rule** | Todas as 5 novas/alvo keys estão em `catalog.py` + `form_schema`. |
| **rule** | 4-eyes self-approve → 403; outros aprovam → 200. (AC-04) |
| **rubric** Autonomia GTE (% operacionais editáveis). ≥ 95% → (AC-09) ≥ 1.5. |
| **rule** | Publicar `imposto_selo_pct = 12%`, recalcular cotação → prémio variou ≈ +1.8% (como no AC-04 passo lógico). |

---

## Tarefa 4: Completar Renovação por Experiência (Frente 4)

**Prioridade**: HIGH  
**Dependências**: Task 2 (act modelo publicado) + Apps Claims existentes  
**Cobertura AC**: AC-05  
**Estimativa**: 3-5h

### Objetivo
Hoje `renewal_service.py` só mostra jornada 7-step no cliente. Falta ligar o motor de PRICING à **experiência histórica** no renewal.

### Passos
1. **Renewal Pricing Trigger**: `quote_service.price_quote(quote)` → se `quote.quote_type = RENEWAL` e `quote.source_policy_id ≠ None` → **chamar novo serviço** `renewal.experience_pricing_adjustment(quote, params_businessconfig)`.

2. **Novo módulo `apps.policy.domain.experience_rating.py`**: Implementar fórmula:
   ```
   claims_hist = claims.summary_service.summary(policy_id = source_policy_id, window_months=24)
   n_claims = claims_hist.n_claims
   credibility = linear_interp(n_claims, [0, 5, 20], [0.20, 0.20, 1.00])
   bonus_malus = lookup(claims_hist.loss_ratio_pct)
     <50% → -10%; 50-65% → 0%; 65-85% → +5%; >85% → +15%
   trend = 1 + (inflacao_medica_pct/100)  # de actuarial_loads
   prémio_renovação = prémio_base_modelo * (1 + credibility*(bonus_malus) + trend_adjustment)
   ```
   Todos os parâmetros de `renewal.experience_factors` BusinessConfig.

3. **Output**: Guardar `pricing_run.renewal_breakdown_json = { historical_summary, credibility_pct, bonus_malus_pct, trend_pct, base_premium, final_premium, formula_version }`.

4. **Portal Cliente**: No `renewal_service.get_renewal()` se o breakdown existe → passo "PROPOSAL" mostra `premiumVariationPct` com `±X%` e `motivo = sinistralidade dos últimos 2 anos` (sem revelar fórmulas).

5. **Teste AC-05**: Fixture claims `LR=75%`, prémio base 1.000 → esperado `final = 1.050 ±0.01` (±1 currency).

### TR
| Tipo | Texto |
|---|---|
| **rule** | R-40..R-45: `price_quote` renewal invoca experiência. |
| **rule** | `RenewalBreakdownJSON` tem 6 campos obrigatórios. |
| **rule** | Teste AC-05 (LR 75% → +5% final premium). diff ≤ 0.01AOA → PASS. |
| **rule** | Portal `get_renewal()` tem `premiumVariationPct` no JSON. |

---

## Tarefa 5: Ligar Cenários de Cotação (R5) a Análise Actuarial

**Prioridade**: MEDIUM  
**Dependências**: Tasks 2 e 4 + claims module  
**Cobertura AC**: AC-06  
**Estimativa**: 1.5-2h

### Objetivo
Cenários hoje comparam prémios e coberturas. Acrescentar **indicadores LR / freq / custo médio** (R5, R2) ao diff, se existir histórico.

### Passos
1. **`scenario_service.compare_scenarios(ids)`**: Adicionar passo opcional:
   - Se `proposer_id` tem claims importados → para CADA cenário, calcular `{lrExpectedPct, frequencyPerYear, averageCost}` usando `claims.summary_service` (mesmo motor).
   - Guardar em `scenario_diff["actuarialIndicators"][id_cenario] = { ... }`.
   - Senão → empty (não quebra diff existente).

2. **`parameters.projection`**: Na criação de um cenário, se o GTE quiser → permitir input manual (UI `SimulatorService`) destes indicadores para testar "e se LR = 110%". Hoje defaults vêm do histórico.

3. **Frontend (ScenariosPanel.tsx)**: Na section `compareQuery.data` → nova coluna `Indicadores` com badge colorido por LR (verde <65%, amarelo 65-85%, vermelho >85%).

### TR
| Tipo | Texto |
|---|---|
| **rule** | JSON `compare_scenarios` tem chave `actuarialIndicators` quando claims existem. (AC-06) |
| **rule** | Sem claims → chave omitida ou empty, não quebra. |
| **rule** | Compare 2 cenários de um cliente com 2 anos de claims → output tem 2 indicadores preenchidos. |

---

## Tarefa 6: Confirmar Permissões + Autonomia GTE

**Prioridade**: MEDIUM  
**Dependências**: Tasks 3 e 1  
**Cobertura AC**: R-60..R-63  
**Estimativa**: 1h (verificação, quase 0 código)

### Objetivo
Validar roles e permissões existentes são suficientes (confirmar e documentar, não criar roles novos sem acordo).

### Passos
1. **Validar matrix** em `permissions.py.ROLE_PERMISSIONS` + `ROLE_SCOPES`:
   - `SUBSCRIPTION_MANAGER`: `{ product:manage, pricing_config:manage, quote:calculate, audit:read, quote:review, quote:edit }`
   - Se algo estiver em falta → acrescentar (ex.: `pricing_config:manage` no SUBSCRIPTION_MANAGER tem de estar para a Tarefa 3).

2. **Teste (já existe ou novo)**: `SUBSCRIPTION_MANAGER` tem de conseguir:
   - Criar draft BusinessConfig `pricing.adjustments`
   - Criar draft de impostos
   - Submeter para aprovação
   - Não consegue aprovar o seu próprio draft (4-eyes bloqueado)

3. **PLATFORM_ADMIN**: Confirmar tem `SUPER_ADMIN equivalente` no módulo `platform_admin`. Consegue publicar modelos actuarial de qualquer tenant.

4. **4-eyes confirmado no serviço**: rever o `publish_approved_config` do `business_config/application/service.py` → confirma `created_by != approved_by` (4-eyes).

### TR
| Tipo | Texto |
|---|---|
| **rule** | Matrix roles contém permissões corretas para SUBSCRIPTION_MANAGER e ADMIN. |
| **rule** | 4-eyes check active no service.py e bloqueia self. |
| **rule** | NENHUM role novo é criado nesta tarefa (R-60). |

---

## Tarefa 7: Testar Fluxos Completos + Regressões

**Prioridade**: HIGHEST  
**Dependências**: Tasks 1 a 6 (todas)  
**Cobertura AC**: AC-07, AC-11, R-70 a R-77  
**Estimativa**: 4-6h (inclui corrigir falhas encontradas)

### Objetivo
Correr todos os fluxos ponta-a-ponta, com e sem PostgreSQL local. Sem Docker → fallback sqlite.

### Passos
1. **Setup tests em sqlite (fallback local)**: `conftest.py` permitir `DATABASE_URL=sqlite:///tmp/test.db` se `Q360_TEST_PG_URL` não existir. Ajustar testes que usem PG-specific features.

2. **Testes E2E por frente**:
   - **R-70**: Fixtures fluxo SAU_IND Benchmark (40M Base IM).
   - **R-71**: Fixtures fluxo SAG_GRUPO_75_ADMIN (60 titulares + 15 agregados = 75 vidas; headcount ≥ 50 → desconto).
   - **R-72**: Renovação experiência claims LR=75% → +5%.
   - **R-73**: Parametrização GTE (impostos 10→12%).
   - **R-74**: Isolamento 2 tenants (A vs B) — list policies.
   - **R-75**: 4-eyes bloqueio; desbloqueio com outro user.

3. **Correr suite pricing completa**: `pytest tests/pricing tests/business_config tests/claims tests/quote` → todos passam.
4. **Correr smoke testes portal cliente**: `pytest tests/customer_portal/` para garantir não regressão de renovação no cliente.

### TR
| Tipo | Texto |
|---|---|
| **rule** | `pytest tests/pricing tests/business_config tests/claims tests/quote` passa AC-07. |
| **rule** | 6 fluxos R-70..R-75 implementados e PASS. |
| **rubric** AC-11: ≥ 40 testes isolados PASS sqlite. → ≥ 1.5. |
| **rule** | `python manage.py check` final no último passo → 0 erros. |

---

## Tarefa 8: Documentar Parâmetros + Fórmulas GTE

**Prioridade**: MEDIUM  
**Dependências**: Tasks 2..6 (tudo implementado)  
**Cobertura AC**: AC-08  
**Estimativa**: 1.5-2.5h

### Objetivo
Documento em Português (pt-AO) **para o GTE operar diariamente, sem depender do fornecedor.**

### Passos
1. **Criar ficheiro**: `backend/docs/Parametros_E_Formulas_GTE.md` (se pasta não existe → criar pasta `backend/docs/`). Estrutura:
   1. Visão geral + papéis (ADMIN vs SUBSCRIPTION_MANAGER vs SUBSCRIBER + GTE = SUBSCRIPTION_MANAGER)
   2. Lista das 26 chaves do catálogo (catalog.py) → para cada: descrição PT, valores default, formato JSON/formSchema exemplo
   3. Passo-a-passo publicação config (DRAFT → PEND → APPROVE → PUBLISH + 4-eyes)
   4. Modelo actuarial SAU/SAG: 94 células, dimensões, fórmula `prémio_puro × (1 + loads) × (1 + impostos) × agrav × grupo`
   5. Renovação por experiência (bonus-malus LR table, credibilidade)
   6. Como validar 1 cotação manualmente (vs Excel referência)
   7. Glossário PT: LEV / LR / credibilidade / freq / etc.
   8. Troubleshooting: erros comuns (config não publicada → pricing placeholder; 4-eyes falta aprovador)

2. **Referenciar no Project**: Atualizar ou criar link no `README.md` backend → apontar para `docs/Parametros_E_Formulas_GTE.md`.

3. **Qualidade**:
   - Língua: Português de Angola (pt-AO)
   - Sem jargão técnico excessivo onde não for preciso.
   - Exemplos reais para cada passo.

### TR
| Tipo | Texto |
|---|---|
| **rule** | Existe 8 capítulos no documento. Cada frente R-30..R-45 descrita (AC-08). |
| **rule** | 1 exemplo passo-a-passo: publicar `imposto_selo` 10%→12% (como Tarefa 3). |
| **rule** | Documento está em PT (confirmar palavras chave: prémio, carência, sinistralidade, etc., não em inglês). |

---

## Ordem Recomendada de Execução

```
Dia 1 (Hoje):
  15h   T1  ─── (arranque + OpenAPI)
  15h45 T2 ────── publicar modelo + ligar ao pricing engine + validar 94 células

Dia 2:
  Manhã T3 ─────── parametrizar BusinessConfig + testar 4-eyes
  Tarde T4 ─────── renovação por experiência (apps policy domain experience_rating)

Dia 3:
  Manhã T5 ─────── ligar cenários R5 + actuarialIndicators
  12h   T6 ─────── confirmar roles e 4-eyes
  Tarde T7 ─────── suite testes completa (corrigir falhas se aparecer)

Dia 4:
  Manhã T8 ─────── documentação PT-AO + validação final + entrega.
```

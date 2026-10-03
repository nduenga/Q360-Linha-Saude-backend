# Checklist — Backend do simulador GTE (Saúde)

Único ficheiro de acompanhamento do backend do simulador. Substitui os antigos
`CHECKLIST_CUSTOMIZACAO`, `ROADMAP_ANGOLA_CUSTOMIZATION`, `FRONTEND_PLAN`,
`GUIA_TESTES` e `AUTH0_SETUP` (apagados: épicos fechados / Auth0 abandonado).
Decisões de desenho continuam em `backend/DECISIONS_TAKEN.md` e
`backend/OPEN_DECISIONS.md`.

**Fonte das regras de negócio:** `Seguro de Saúde — Coberturas e Capitais.pdf`
(1-Out-2026). O PDF diz que os valores em Kz são **indicativos**: entram como
dados-modelo (`indicative: true`), editáveis pelo GTE, nunca como tarifa real.

Legenda: `[x]` feito e testado · `[ ]` por fazer / parcial (com a razão) · 🔴 depende de decisão do cliente.

Testes: `cd backend && Q360_TEST_POSTGRES=true ./.venv/Scripts/python.exe -m pytest tests` — toda a suite passa.
Integridade: `tests/policy/test_end_to_end.py` (ciclo completo até ao portal do cliente e à renovação),
`tests/integration/test_api_surface.py` (autenticação e ausência de erros 5xx em todas as rotas) e
`tests/integration/test_openapi_contract.py` (contrato OpenAPI completo e em dia).
Contrato: `python manage.py build_openapi` regenera `backend/schema.yml` e o ART-006 v1.4.0 a partir do código.
Questões para a área de negócio: `docs/Questionario_Decisoes_Negocio_Simulador_GTE.docx`.

---

## Fase 0 — Fundações
- [x] Auditoria com `before`/`after`/`reason`/`impact` (`change_audit.py`) e motivo obrigatório (≥10 car.) em ajustes, rollbacks, desativações, restauros
- [x] Reutilizadas as permissões existentes (`product:manage`, `pricing-config:manage`, `quote:*`); **nenhuma permissão nova** (regra de `permissions.py`)
- [x] `GET /audit-events` com filtro por `action` (já havia entidade, ator, datas)
- [x] Bug latente corrigido: numeração `COT-`/`APO-`/documentos reiniciava por ano mas o índice é único por tenant → colisão na 1.ª cotação/renovação do ano seguinte (`next_continuous_value`)

## Fase 1 — R6 Biblioteca de coberturas
- [x] Catálogo do PDF (24 coberturas); só Hospitalização, Cirurgia de ambulatório e Urgências são `BASE` (B em todas as colunas); Ambulatório passa a opcional
- [x] Migração: `OUTPATIENT` deixa de ser `BASE`; `definition_json`; `benefit_revision`
- [x] CRUD `POST/GET/PATCH /benefits`, `deactivate`/`reactivate`, pesquisa `q`/`category`/`status`
- [x] `GET /benefits/{id}/revisions`, `POST …/rollback`, `GET …/usage`
- [x] Importação/exportação XLSX/CSV com relatório por linha e `dryRun`
- [x] Invariante: coberturas `BASE` não se desativam nem se removem de um plano

## Fase 2 — R4 Capitais, participação, carências, opções A–E
- [x] `plan.settings_json` validado (segmento, escalão, sistema de acesso, idades, agregado, grupo, A–E, preexistências, rede, pré-autorização, indexação)
- [x] `PlanBenefit.configuration_json` validado: inclusão B/O, formas de garantia, participação rede/reembolso, franquias, carências, moeda Kz/USD
- [x] `GET /plans/{id}/validation` (erros + avisos) e `PUT /plans/{id}/benefits/{benefitId}`
- [x] Opções de participação A–E com regra "mais participação ⇒ menor prémio"
- [x] Motor: dimensões do plano/capitais, fator da opção A–E, custo de opcionais (`COVERAGE_LOADING_<COD>`), "e se..." de capitais
- [x] `POST /pricing/preview` e `POST /quotes/{id}/preview` (nada gravado)
- [x] `POST /product-templates/market` + `manage.py seed_health_market_templates` (Individual Base/Médio/Superior e Grupo Colaboradores/Quadros/Administração)

## Fase 3 — R3 Agravamentos e ajustes
- [x] `QuoteAdjustment` (agravamento/desconto, % ou valor, por cotação ou pessoa), motivo, autor, remoção sem apagar
- [x] `POST /quotes/{id}/adjustments[?dryRun=true]`, `GET`, `DELETE` — recalcula e devolve impacto
- [x] Limite de autoridade (`AuthorityPolicy.maxAdjustmentPct/Amount`): acima exige `quote:approve`
- [x] Doenças preexistentes por pessoa: 6 tratamentos do PDF com as regras de aplicação (`PUT/DELETE /quotes/{id}/members/{memberId}/pre-existing`)
- [x] `PUT /quotes/{id}/selection` (opcionais, opção A–E, "e se...")

## Fase 4 — R5 Cenários
- [x] `GET/POST /quotes/{id}/scenarios`, `GET/PATCH/DELETE /scenarios/{id}`, `clone`, `recalculate`, `select`, `apply`
- [x] `GET /quotes/{id}/scenarios/compare` (+ `/export` XLSX/CSV): prémios, coberturas que diferem, componentes, ajustes, opção A–E, projeção
- [x] Deteção de cenário desatualizado (`stale`)

## Fase 5 — R1 Versões, clonagem, renovação, requisitos
- [x] Versões da cotação (automáticas ao recalcular com estado novo, manuais, `diff`, `restore` incl. população)
- [x] `POST /quotes/{id}/clone`
- [x] `POST /quotes/renewals`: população da apólice (sem quem excede a idade de permanência), escolhas e preexistências, prémio/período anterior
- [x] `POST /quotes/{id}/renewal/indexation[?dryRun]`: capitais × inflação médica (percentagem do plano ou parâmetro global)
- [x] `GET /quotes/{id}/requirements`: questionário clínico, exames (idade/capital), idades, agregado, dimensão mínima do grupo, rede, pré-autorização, evacuação, carências, exclusões, histórico de 3 anos; erros bloqueiam o envio para revisão
- [ ] Ao emitir a apólice de uma renovação, marcar a de origem como `RENEWED` (módulo `policy`, fora deste âmbito)
- [ ] Cotação de Grupo com 2–3 categorias numa só cotação: hoje é **uma cotação por categoria/plano** (`settings.category`); consolidar numa proposta única fica por fazer

## Fase 6 — R2 Sinistralidade (novo módulo `apps/claims`)
- [x] Importação CSV/XLSX de sinistros e prémios (formato documentado), histórico de outra seguradora (`source=OTHER_INSURER`)
- [x] `GET /claims/summary`: loss ratio, frequência, custo médio, por cobertura e mês, meses de histórico (só agregados, leitura auditada)
- [x] `GET /claims/profit-sharing` (participação nos resultados, limite ex. 65 %)
- [x] Projeção otimista/base/pessimista (`SIMPLE_TREND_V1`) + conjuntos de premissas; ligação a cenários; `GET /quotes/{id}/claims-context`
- [ ] 🔴 Formato real dos dados do cliente e **fórmulas atuariais** por confirmar (o método é simples e rotulado como tal)

## Fase 7 — R7 Autonomia do GTE
- [x] Rollback de tabelas de tarifação, conjuntos de parâmetros e regras (nova versão publicada + retirar as mais recentes), motivo e auditoria
- [x] `GET …/versions`, `GET …/diff?against=`, `POST …/impact-simulation` (reprecia cotações recentes antes de publicar)
- [x] Parâmetros globais (`/system-parameters`) operacionais vs estruturais, com histórico e rollback; `quote.validity_days` e `renewal.default_medical_inflation_pct` em uso
- [ ] 🔴 Perfis/permissões editáveis pelo GTE (decisão do cliente; hoje fixos por `permissions.py`)

## Fase 8 — R8 Propostas
- [x] `POST /quotes/{id}/proposals` (PDF/DOCX/HTML) a partir do cenário selecionado, de um cenário indicado ou da cotação; `GET` histórico; `download`; `retry`; `preview`
- [x] Modelos configuráveis (`document-templates`): título, textos com `{{variáveis}}`, secções por ordem; `schema`, `preview`, validação
- [x] Conteúdo: capitais por forma de garantia, participação rede/reembolso, carências, opção A–E, exclusões, preexistências por pessoa, pré-autorização, evacuação (destinos/moeda/risco cambial), idades, regras de Grupo, aviso de valores indicativos
- [ ] 🔴 Template oficial / identidade visual (OD-006): existe um desenho por omissão editável, não o oficial
- [ ] URLs assinadas com expiração (hoje o download é autenticado e verifica o checksum)

---

## Fase 9 — Configuração de negócio pela interface (`apps/business_config`)
- [x] Catálogo de 24 chaves (`product.*`, `pricing.*`, `underwriting.*`, `group.rules`, `renewal.*`, `proposal.*`, `network.rules`, `foreign_coverage.rules`, `security.approval_rules`) com esquema de formulário por chave (`GET /business-config/catalog`)
- [x] Versões `BusinessConfiguration` (DRAFT → PENDING_APPROVAL → PUBLISHED → RETIRED), checksum, `rowVersion`, auditoria; publicar encerra a versão anterior na véspera da nova vigência
- [x] Four-eyes: o criador não aprova (`SEC-403`); aprovar exige `q360.approve` + `pricing-config:manage`; escrita exige `q360.write` + `pricing-config:manage`
- [x] Documentos anexos por versão (upload só em DRAFT, download com checksum)
- [x] Resolver por inquilino, chave e vigência; motor de tarifação usa `pricing.reference_premiums/factors/adjustments/taxes_fees` e regista as versões no `PricingRun` (`versions.businessConfigurationVersions`)
- [x] Sem configuração publicada mantém-se o caminho legado (RatingTable/PricingParameterSet); nenhum valor comercial é inventado
- [x] Cotação com tarifação desatualizada é recalculada quando uma versão nova é publicada (`price_quote`)
- [x] Teste ponta a ponta `test_business_config_e2e.py` (tarifa → aprovação → cotação → nova versão → reprecificação)
- [x] Contrato OpenAPI regenerado e copiado para o frontend (`schema.d.ts` regenerado, `tsc -b` sem erros)
- [x] Todas as chaves são lidas pelos motores (`business_config/application/overlays.py`, `readers.py`): `product.*` (planos ativos, coberturas, capitais/sublimites, participação, carências, idades, exclusões) sobrepõem-se à configuração do plano; `underwriting.*` (aceitação, preexistências por gravidade, análise médica) → requisitos e decisões; `group.rules` → dimensão mínima e quota de resultados; `renewal.*` → inflação, prazos, continuidade de carências; `network.rules`/`foreign_coverage.rules` → rede, evacuação; `proposal.documents/texts/branding` → proposta; `security.*` → quem edita/aprova e permissões por perfil
- [x] Validação estrutural de cada chave (tipos, obrigatórios, opções) ao gravar; regras reforçadas ao submeter
- [x] Renovação: a apólice de origem passa a RENEWED quando a cotação de renovação se converte em apólice. Por omissão na ativação (1.º prémio pago, garante a continuidade); configurável em `renewal.deadlines.previous_policy_close` (ON_RENEWAL_ACTIVATION, ON_RENEWAL_ISSUANCE, ON_EFFECTIVE_DATE com `manage.py close_renewed_policies`, MANUAL)
- [x] Permissões por perfil editáveis (`security.role_permissions`): redistribui as permissões existentes, ADMIN nunca perde `product:manage`/`pricing-config:manage`; os escopos do token seguem as permissões no próximo login
- [x] Identidade visual dos documentos (`proposal.branding`: empresa, cor, lema, rodapé, logótipo anexado) em HTML, PDF e DOCX
- [x] Ligações assinadas com expiração (`POST /documents/{id}/signed-url`, `GET /documents/signed/{token}`; prazo no parâmetro `documents.signed_url_ttl_seconds`)
- [x] Sinistralidade: `GET /claims/methodology` (método rotulado como indicativo, fórmulas, formatos) e `GET /claims/import-template`; limite e quota de resultados por omissão vêm de `group.rules`
- [ ] 🔴 Template oficial do cliente (OD-006) e fórmulas atuariais reais: aguardam o material do negócio (a identidade e o método já são configuráveis/substituíveis)
- [x] Regras "Quando… então…" (`rules.custom`): o GTE preenche linhas de formulário (condição por idade/plano/nº de pessoas/tipo de seguro/relação/opção A–E, 2.ª condição opcional, ação em linguagem de negócio) em vez de escrever fórmulas. Ações de prémio (aumentar/desconto %, multiplicar, somar/subtrair) aplicam-se por pessoa ou ao total da cotação, por ordem; ações de aceitação (análise médica/técnica, recusar, aviso) geram requisitos. Mesmo ciclo DRAFT→aprovação→PUBLISHED, versão registada no `PricingRun`, recálculo ao publicar. Esquema com `optionLabels`/`help` para o frontend. Testes: `test_custom_rules_domain.py`, `test_business_config_e2e.py`
- [ ] Ecrãs de administração no frontend (formulários a partir de `formSchema`; usar `optionLabels` como texto das opções e `help` como ajuda)

---

## Fase 10 — Plataforma: super admins e tenants (`apps/platform_admin`)
- [x] Login próprio dos super admins (token separado, bloqueio após falhas) e gestão de vários super admins pela interface
- [x] Criar/listar/ver/alterar/suspender tenants com dados da empresa e primeiro ADMIN com palavra-passe temporária única
- [x] Acrescentar ADMIN a um tenant e repor a palavra-passe de qualquer conta do tenant
- [x] Tenant suspenso bloqueia staff e portal de imediato; tokens de plataforma não entram nas rotas de tenant
- [x] Auditoria de plataforma consultável; testes em `tests/platform_admin`
- [ ] Ecrãs de plataforma no frontend; troca obrigatória da palavra-passe temporária no primeiro login

---

## Rastreabilidade — regras do PDF → onde estão e que teste as cobre

| Regra do PDF | Implementação | Teste |
|---|---|---|
| Só a hospitalização é a base obrigatória; matriz B/O/— por plano | `market_catalog.py`, `market_templates.MATRIX` | `test_benefits`, `test_plan_rules_domain::test_template_matrix_matches_the_pdf_comparison_table` |
| Base do plano vs opcionais | `PlanBenefit.configuration_json.inclusion` | `test_plan_configuration`, `test_plan_pricing` |
| Sistemas de acesso (rede / reembolso / misto) | `plan_settings.accessSystem`, participação por bloco | `test_access_system_mismatch_warnings` |
| Formas de garantia dos capitais | `coverage_config` (`limits[].kind`) | `test_capital_forms_and_sublimit_inside_capital`, `test_quantity_limit…`, `test_single_main_capital…` |
| Sem regra de rateio | `settings.noProRata`, parâmetro estrutural `capital.pro_rata_rule`, texto da proposta | `test_no_pro_rata_rule_cannot_be_disabled`, `test_parameters_separate_operational_from_structural` |
| Capital em Kz ou USD (evacuação), risco cambial | `currency` por cobertura | `test_evacuation_rules_prior_approval_currency_destinations` |
| Individual/Familiar: agregado (cônjuge/união de facto, filhos ≤25 estudantes) | `settings.household`, requisitos | `test_household_rules_spouse_and_dependent_child_age` |
| Idade de entrada 60–65, renovação até 70–75 | `entryAge`/`permanenceAge`, requisitos, renovação | `test_age_outside_entry_range_blocks_submission`, `test_people_above_the_permanence_age_are_not_renewed` |
| Questionário clínico obrigatório (individual); dispensado no grupo obrigatório >~20 | `requirements_service` | `test_individual_requirements_…`, `test_group_questionnaire_…` |
| Exames acima de 55 anos ou de um capital | `clinicalQuestionnaire.medicalExamAboveAge/Capital` | `test_exam_required_above_a_capital` |
| Grupo: mínimo 5–10, categorias, adesão, pagador, base do prémio, movimentos mensais | `settings.group`, `GROUP_MIN_SIZE` | `test_group_minimum_size_blocks_submission`, `test_group_proposal_shows_group_conditions` |
| Participação nos resultados (ex. 65 %) | `profitSharing` + `/claims/profit-sharing` | `test_profit_sharing_when_loss_ratio_is_below_the_agreed_limit` |
| Capitais Base/Médio/Superior e por categoria de grupo | `market_templates.CAPITALS` | `test_template_capitals_match_the_pdf_tables` |
| Franquia anual/por evento, copagamento fixo, coparticipação, com máximo, sem participação | `coverage_config.participation` | `test_participation_types_and_where_they_apply`, `test_no_participation_coverage_assistance_24h` |
| Carências por cobertura (individual/grupo), acidente dispensa, anti-seleção (parto/estomatologia) | `waitingDays`, aviso `ANTI_SELECTION` | `test_waiting_periods_and_anti_selection`, `test_group_mandatory_adhesion_waiting_hint` |
| Opções A–E, ajuste ao prémio, "mais participação ⇒ menor prémio" | `participationOptions`, motor | `test_participation_options_follow_higher_participation_lower_premium`, `test_higher_participation_option_means_lower_premium` |
| 6 tratamentos das doenças preexistentes e onde se aplicam | `pre_existing.py`, `plan_settings` | `test_pre_existing_decision_rules_per_the_pdf`, `test_group_pre_existing_full_acceptance_and_sublimit` |
| Exclusões habituais (13) | `STANDARD_EXCLUSIONS`, requisitos, proposta | `test_individual_requirements_…`, `test_proposal_content_follows_the_pdf_rules` |
| Rede: cobertura geográfica Luanda/províncias | `settings.network`, aviso `NETWORK_COVERAGE` | `test_network_geographic_coverage_warning_and_regions` |
| Evacuação: destinos, aprovação prévia obrigatória | `definition.requiresPriorApproval`, `destinations` | `test_evacuation_rules_…` |
| Histórico de sinistralidade de 3 anos na transferência | `claims` + `CLAIMS_HISTORY_ON_TRANSFER` | `test_quote_claims_context_and_three_year_history_requirement` |
| Atualização de capitais pela inflação médica na renovação | `apply_indexation`, `CAPITAL_INDEXATION_PENDING` | `test_capital_indexation_dry_run_apply_and_rules` |
| Pré-autorização (internamentos, exames de alto custo, cirurgias programadas) | `settings.priorAuthorization` | `test_prior_authorization_and_capital_indexation_settings` |
| Doenças graves (lista fechada, capital fixo), subsídio (30/60 dias, franquia temporal 2–3), assistência 24h, segunda opinião… | `market_catalog`, `coverage_config` | `test_critical_illness_closed_list_and_fixed_capital`, `test_hospital_daily_allowance_days_and_time_deductible` |
| Valores indicativos a confirmar nas Condições Gerais | `indicative: true` + aviso na proposta | `test_proposal_content_follows_the_pdf_rules` |

**Discrepâncias do próprio PDF (seguiu-se a matriz comparativa):** Medicamentos no plano Base (150.000 Kz na tabela p.3 vs "—" na matriz p.6/p.9); Parto (capital por evento p.3 vs normal/cesariana p.9).

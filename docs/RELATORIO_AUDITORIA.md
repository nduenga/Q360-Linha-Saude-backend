# Relatório de auditoria e correcções — Q360 Linha Saúde (backend)

Data: 2026-10-14. Base: ramo `fabio` (último commit `b026a25`) com as
alterações ainda não commitadas da sessão anterior. Documentos relacionados:
`MOTOR_CONFIGURAVEL.md`, `MAPA_MODELO_ACTUARIAL.md`, `INVENTARIO_ENDPOINTS.md`,
`INSTALACAO_E_EXECUCAO.md`, `DECISOES_PENDENTES.md`.

## 1. Resumo

- A arquitectura (Django + DRF, módulos por domínio, isolamento por tenant
  com `TenantScopedModel`, auditoria, outbox, versões publicadas) já existia e
  foi preservada. O motor de preços já integrava configuração publicada,
  modelo actuarial e regras «Quando… então…».
- Faltava: gestão completa de fórmulas (só havia um endpoint de teste e as
  fórmulas publicadas não eram validadas), rejeição com motivo, histórico e
  comparação de versões, parte da cadeia actuarial do Excel, e cobertura de
  testes do caminho actuarial.
- Resultado: o cálculo pela API reproduz o `Calculador` do Excel (diferença
  de 0,02 Kz em 2 303 121,49 Kz) e as fórmulas configuráveis são criadas,
  validadas, aprovadas, publicadas e usadas no cálculo real, com trace.

## 2. Falhas encontradas, causa e correcção

### 2.1 Testes e regras de domínio

| # | Sintoma | Causa raiz | Correcção |
|---|---|---|---|
| F1 | Execução de 13/10 (`backend/relatorio-testes.xml`): 278 falhas em 697 testes, a maioria `KeyError: 'id'` após HTTP 400 em `POST /proposers` | Regra já commitada: proponente `INDIVIDUAL` exige `dateOfBirth`; os *fixtures* de vários módulos não a enviavam | Fixtures actualizados (enviam a data). A regra de domínio não foi alterada |
| F2 | `DuplicateTitularError` no seeder de demonstração | `seed_demo_data.py` criava «António» (1940) como **segundo `TITULAR`** da proponente individual Ana; a regra R5 só admite um titular | Passa a `ASCENDENTE`; o cenário de idade-limite mantém-se |
| F3 | Simulador: prémios a metade (100 vs 200) | Edição anterior do teste deixou o `attach` do membro fora do ciclo `for` (indentação) | Corrigida a indentação no teste |
| F4 | `test_quote_lifecycle`: membros extra recusados | Helper criava todos os membros como `TITULAR` | Membros extra como `OUTRO` (sem regras de agregado) |
| F5 | Filho de 1999 recusado com titular de 1990 | Regra já commitada: filho ≥13 anos mais novo que o titular | Dados do teste ajustados mantendo a regra testada (idade máxima do dependente) |
| F6 | Asserção de conflito de versão enfraquecida para `in (400, 409)` | O pedido «obsoleto» violava outra regra (400) e escondia o 409 | Pedido válido excepto na versão; asserção estrita `409 VERSION-CONFLICT` reposta |
| F7 | `KeyboardInterrupt` / suite >25 min | PBKDF2 em cada conta criada nos testes | *Hasher* rápido só em `config/settings/testing.py` |
| F8 | Tracebacks com `???` | `__pycache__` com caminhos de uma localização antiga do projecto | Caches limpos (são regenerados) |

Testes alterados apenas para os alinhar com regras de domínio já em vigor
ou para corrigir erros do próprio teste; nenhum resultado esperado de
negócio foi alterado para fazer um teste passar.

### 2.2 Motor de preços e configuração

| # | Defeito | Impacto | Correcção |
|---|---|---|---|
| M1 | `pricing.formulas` não era validada ao criar/submeter (o esquema genérico JSON saía antes de qualquer verificação) | Uma fórmula inválida só falhava ao cotar, partindo todas as cotações | Validação completa no DRAFT e na submissão (sintaxe, variáveis, ciclos…) |
| M2 | `price_quote` comparava só 4 chaves + `rules.custom` com o snapshot, que também guarda `pricing.formulas` e `pricing.actuarial_model` | Com fórmulas ou modelo actuarial publicados, cada pedido de preço criava um cálculo novo (nunca reutilizava) | Comparação inclui todas as chaves opcionais |
| M3 | `InvalidOperation` usado em `pricing_engine.py` sem import (no código commitado) | `NameError` latente com dados actuariais inválidos | Import reposto |
| M4 | Regras personalizadas ignoradas não ficavam registadas | Requisito «registar regras ignoradas e porquê» | Trace `CUSTOM_RULE_SKIPPED` com os factos avaliados |
| M5 | Impostos actuariais aplicados em cascata | Excel soma selo + ARSEG sobre o mesmo prémio líquido (`C85`) | Taxas somadas sobre o prémio comercial líquido |
| M6 | Factor regional só em SAG | Excel `C60` aplica-o a SAU e SAG | Aplicado aos dois quando o perfil indica a região |
| M7 | Faltavam participação nos custos (`C55:C59`), idade de adesão (`J25`), descontos comerciais limitados (`C67:C70`) e encargo de fraccionamento (`E91:E94`) | Prémio diferente do modelo | Implementados a partir das tabelas do Excel, com trace e origem (`sourceCode`) |
| M8 | Perfil actuarial só passado a cotações de grupo | SAU não recebia região/participação | Passado a SAU e SAG |
| M9 | `build_actuarial_model` abria o Excel em `read_only` com milhares de acessos aleatórios | Minutos por importação | Carregamento normal: ~2 s, mesmo resultado |

### 2.3 API e contrato

| # | Situação | Correcção |
|---|---|---|
| C1 | `POST /api/v1/quotes/{quote_id}/reopen` implementado mas ausente do contrato | Contrato regenerado a partir do código |
| C2 | Sem gestão de fórmulas, rejeição, histórico, comparação de versões | 15 operações novas (ver inventário) |
| C3 | Cotação sem `proposerName` | Campo acrescentado; `select_related` evita N+1 na listagem |
| C4 | Membros sem NIF (requisito: NIF do beneficiário opcional) | Campo opcional + migração `client/0009_member_nif` |
| C5 | Import duplicado em `eligibility/interfaces/urls.py` | Removido |

### 2.4 Requisitos da secção 13 verificados

| Requisito | Estado |
|---|---|
| NIF do beneficiário opcional | ✔ (C4) |
| `GET /relationship-codes` sem `TITULAR` | ✔ (já implementado; coberto por testes) |
| Relação proponente individual / titular / beneficiários | ✔ regras R2/R4/R5 e idades (titular único, filho ≥13 anos mais novo…) |
| Elegibilidade com nomes de proponente, membro, produto e plano | ✔ `proposerName`, `memberName`, `planName`, `productName` |
| Motivo concreto da inelegibilidade | ✔ `reasons` com código e mensagem |
| Data de inclusão dos beneficiários | ✔ `inclusionDate` no portal |
| Nomes legíveis em cotação/subscrição | ✔ (C3) |

## 3. Segurança

| Verificação | Resultado |
|---|---|
| Segredos no repositório | `.env` nunca commitado; só `.env.example` com valores de exemplo. Nenhuma credencial hardcoded encontrada no código de aplicação |
| Execução de expressões | Fórmulas via `ast` com lista branca; sem `eval`/`exec`/SQL; testes com tentativas de injecção (`__import__`, atributos, índices, `eval`, `open`…) |
| Permissões | Ler exige scope de leitura; escrever exige scope de escrita + `PRICING_CONFIG_MANAGE`; aprovar/rejeitar exige scope de aprovação; *four-eyes* na aprovação e na rejeição |
| Isolamento por tenant | Modelos `TenantScopedModel`; consultas fora de contexto falham (`LookupError`); suite `test_tenant_isolation` passa |
| Integridade das configurações | Versões publicadas imutáveis com checksum SHA-256; cada cálculo regista versão e checksum usados |
| Transacções | Criação/edição/publicação em `transaction.atomic` com `select_for_update` na numeração de versões; bloqueio optimista (`rowVersion`) |
| Produção | `production.py` recusa `OIDC_STATIC_VERIFICATION_KEY`; *hasher* rápido só nos testes |
| Dados pessoais no seed | E-mail com aspecto pessoal no seed de demonstração (ver `DECISOES_PENDENTES.md`) |

## 4. Análise estática e migrações

- `pyflakes`: sem nomes indefinidos no código de aplicação (excepto ficheiros
  com `import *`, não analisáveis); 21 imports não usados (registados, não
  alterados).
- `makemigrations --check`: modelos coerentes com as migrações.
- `migrate --check` na BD de desenvolvimento: sem migrações por aplicar
  (antes da nova `0009_member_nif`).
- `requirements.txt` estava em UTF-16 (PowerShell): convertido para UTF-8,
  mesmo conteúdo; `pip install --dry-run` validado.

## 5. Resultados dos testes (execução real)

Ambiente: macOS, Python 3.13.13, PostgreSQL 16 (Postgres.app),
`Q360_TEST_POSTGRES=true`. Ficheiros: `docs/resultados-testes/junit-2026-10-14.xml`
e `pytest-2026-10-14.txt`.

| | Antes (13/10, `relatorio-testes.xml`) | Depois (14/10) |
|---|---|---|
| Testes | 697 | 743 (+46 novos) |
| Passaram | 418 | **742** |
| Falharam | 278 | **0** |
| Erros | 0 | 0 |
| Ignorados | 1 | 1 — `test_golden_tests.py:65`, ELIG-006 retirado por decisão (S09-POLICY-001) |
| Duração | 486 s | 288 s |

Por módulo (depois): client 77 · customer_portal 65 · eligibility 43 ·
foundation 46 · integration 40 · platform_admin 11 · policy 69 · pricing 37 ·
product 117 · quote 166 · fórmulas (unitários) 44 · regras personalizadas 21 ·
modelo actuarial 3 · resolvedor de pricing 3 · configuração 1.

Testes novos neste trabalho:

- `tests/test_formula_engine.py` (44): avaliador seguro, injecções recusadas,
  Decimal/arredondamento, ordem determinística, desativação, ciclos,
  variáveis não declaradas, intervalos, dependências.
- `tests/quote/test_formula_config_e2e.py` (4): catálogo e teste isolado;
  validação antes de gravar (incl. endpoint genérico); ciclo completo
  DRAFT → rejeição com motivo → correcção → aprovação por outro utilizador →
  cálculo real → reutilização → trace (aplicadas/ignoradas) → cálculo antigo
  intacto → histórico; comparação de versões.
- `tests/quote/test_actuarial_excel_reference.py` (1): backend vs `Calculador`.
- `tests/client/test_member_nif.py` (3): NIF opcional, validado, preservado.
- Regressão em `tests/quote/test_quotes.py`: `proposerName` em detalhe e lista.

## 6. Decisões de 2026-10-14 implementadas (execução de 2026-10-15)

Detalhe em `DECISOES_PENDENTES.md`. Resumo:

| # | Alteração |
|---|---|
| Ambiente | `migrate` falhava com `No module named 'django'`: o `.venv` tinha o caminho da pasta antiga do projecto. Venv recriado; migrações aplicadas (`client/0009`, `client/0010`, `client/0011`, `business_config/0003`) |
| A1 | Modelo actuarial validado ao gravar; importação de Excel (`…/actuarial-model/import`, com `dryRun`, ficheiro anexado com SHA-256), modelo de referência (`…/template`) e catálogo de opções (`…/catalog`) |
| A4 | Valores por omissão do perfil actuarial configuráveis (`calculation_settings.profile_defaults`), registados no trace; teste de referência SAG contra o `Calculador` recalculado (`C5 = SAG`) |
| A5 | Gravidade `MODERATE_HIGH` (+50 %) nas regras de pré-existência |
| A6 | Idade de adesão em renovações configurável (`ORIGINAL_ENTRY_AGE` recomendado) |
| A8 | `pricing.fractionation` para todas as apólices |
| A9 | Fórmulas por pessoa (fase `PERSON`) |
| R1 | NIF obrigatório por tipo e único por tenant (proponente); único no tomador quando indicado (pessoa segura; a mesma pessoa pode ter o NIF em tomadores diferentes). Corrigido: NIF repetido não era detectado ao **editar** um proponente |
| R2 | Estado `REJECTED` (migração da CHECK) |
| Seed | Ana → `fabiongila@gmail.com`; Empresa Kilamba → `empresa.kilamba@demo.q360.local` |

Testes alterados por mudança de requisito (não para esconder falhas):
`test_formula_config_e2e` (rejeição passa a `REJECTED`), `test_formula_engine`
(a fase `PERSON` deixou de ser inválida; o caso usa agora uma fase
inexistente), `test_seed_portal_demo` (e-mails), dois testes que inserem
proponentes directamente na BD (passam a ter NIF, agora obrigatório).

Testes novos: `test_actuarial_model_config.py` (9), `test_actuarial_excel_reference_sag.py` (1),
`test_nif_uniqueness.py` (3), `test_configuration_rejected_state.py` (1) e 4
casos em `test_formula_engine.py`.

Resultado (execução real, `docs/resultados-testes/junit-2026-10-15.xml` e
`pytest-2026-10-15.txt`): **761 testes — 760 passaram, 0 falharam, 1
ignorado** (o mesmo ELIG-006), 262 s. `makemigrations --check` e
`migrate --check` limpos; contrato OpenAPI regenerado (281 operações).

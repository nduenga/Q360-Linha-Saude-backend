# ROADMAP — Customização Q360 para o Mercado Angolano

**Estado:** vivo / em aberto. **Autoridade:** pedido directo do Product Owner (2026-09-18).

## Princípio orientador — mudança de fase do projecto

Até agora, quase todos os valores de negócio no sistema eram **placeholders de
teste explicitamente marcados** (ver `backend/DECISIONS_TAKEN.md`): tarifas,
moeda, catálogo de relações familiares, template de proposta, etc. eram
fixtures técnicas para destravar o teste de ponta a ponta, nunca decisões de
produto reais.

Este roadmap marca uma mudança de fase: os itens abaixo **são decisões de
produto reais** para o mercado Angolano, vindas directamente do Product
Owner. Mantém-se, no entanto, a mesma disciplina de sempre — **nunca
inventar** um detalhe que não foi especificado. Onde falta uma decisão
concreta (um código exacto, um schema de configuração, um comportamento de
fronteira), fica registado como **Open Decision** dentro do épico
correspondente, e o código correspondente não avança sem resposta.

**Nota explícita do Product Owner:** este roadmap está sujeito a aumento,
diminuição ou substituição de funcionalidades a qualquer momento — não é um
contrato fechado.

---

## Épico 1 — Catálogo de coberturas do mercado angolano (base + complementares)

**Fonte:** `Guia_Coberturas_Seguro_Saude_Angola.pdf` (mercado angolano,
regulação ARSEG), fornecido pelo Product Owner em 2026-09-19. Esta fonte
**resolve** a antiga OD-ANGOLA-001 (codes/lista fechada) — deixa de ser uma
decisão em aberto.

### Matriz integral de coberturas

**Base (obrigatórias em todas as apólices — sempre presentes em todo o
produto/plano, não removíveis na UI):**

| # | Código proposto | Nome | Âmbito |
|---|---|---|---|
| 1 | `HOSPITALIZATION` | Internamento Hospitalar e Cirurgia | Honorários médicos (cirurgia/anestesia), bloco operatório, estadia hospitalar, tratamentos oncológicos, hemodiálise em internamento |
| 2 | `OUTPATIENT` | Ambulatório | Consultas clínica geral/especialidade, meios auxiliares de diagnóstico (análises, ecografias, radiografias, TAC, ressonâncias), pequenas cirurgias de consultório |
| 3 | `EMERGENCY` | Urgência Médica | Atendimento imediato a episódios agudos/acidentes em território nacional, transporte de emergência pré-hospitalar |

**Complementares (facultativas — apresentadas como cards seleccionáveis na
UI, nunca pré-marcadas):**

| # | Código proposto | Nome | Âmbito |
|---|---|---|---|
| 4 | `PHARMACY` | Medicamentos / Farmácia | Comparticipação/reembolso de fármacos prescritos, rede convencionada |
| 5 | `MATERNITY` | Maternidade e Parto | Pré-natal, parto (normal/cesariana/IVG), cuidados ao recém-nascido |
| 6 | `DENTAL` | Estomatologia (Medicina Dentária) | Consultas, higiene oral, restaurações, extrações, cirurgia maxilofacial por sinistro |
| 7 | `OPTICAL` | Oftalmologia e Óptica | Consultas de refração/especialidade, comparticipação de lentes/armações com limite anual |
| 8 | `PROSTHESIS` | Próteses e Ortóteses | Muletas, cadeiras de rodas, talas, coletes, pacemakers |
| 9 | `PHYSIOTHERAPY` | Fisioterapia e Reabilitação | Sessões de reabilitação motora, pós-cirúrgica ou livre com limite anual |
| 10 | `MEDICAL_EVACUATION` | Evacuação Médica Internacional | Transferência aérea + assistência hospitalar no estrangeiro quando inexequível em Angola |
| 11 | `TRAVEL_ASSISTANCE` | Assistência em Viagem | Assistência médica urgente em deslocações temporárias ao estrangeiro (tipicamente ≤60 dias) |

**Exclusões-padrão de mercado** (a registar como metadado/nota do produto,
não como lógica de pricing nesta fase): cirurgias estéticas, patologias
pré-existentes não declaradas, tratamentos de fertilidade, lesões por
desportos radicais, acidentes de trabalho (imputáveis à apólice de
Acidentes de Trabalho).

### Estado actual

`Benefit`/`PlanBenefit` **já existem** na base de dados e no ORM
(`apps/product/infrastructure/models.py`, ART-012 V006) — mas **sem
endpoint API e sem UI** (`DECISIONS_TAKEN.md#S02-CONTRACT-001`,
`OPEN_DECISIONS.md`). Hoje não há nenhum caminho documentado para associar
uma cobertura a um plano. Este épico completa esse trabalho já identificado,
em vez de partir do zero.

### Objectivo

- Tabela `benefit` na BD com **todas as 11** coberturas acima (id, code,
  name, category `BASE`/`COMPLEMENTARY`, description, status).
- Um endpoint por operação: `GET /benefits` (catálogo completo, para o
  frontend construir a lista de cards), e associação por plano via
  `PlanBenefit`.
- Um Plano nunca existe (ou nunca publica) sem as 3 coberturas **BASE**
  associadas automaticamente. As 8 **COMPLEMENTARY** aparecem na UI como
  **cards seleccionáveis** (multi-select), nunca pré-marcados.

### Tarefas

**Backend**
- [x] Confirmado: `benefit.benefit_type` (ART-012 V006, `varchar(60)`, sem
      CHECK) já serve como o campo de categoria — usa-se `BASE`/
      `COMPLEMENTARY` directamente, **sem migration nova**.
- [ ] Seed das 11 coberturas (3 BASE + 8 COMPLEMENTARY) com os codes acima.
- [ ] `GET /api/v1/benefits` (catálogo, paginável, filtrável por
      `category`) — pragmático, documentar como tal (Change Request ART-006).
- [ ] `POST /api/v1/plans/{id}/benefits` (ou incluído no `PlanCreateRequest`)
      para associar coberturas a um plano.
- [ ] Ao criar um plano: associar as 3 `BASE` automaticamente no backend
      (nunca confiar só na UI para garantir isto).
- [ ] Validação: publicar uma versão de produto falha se algum plano não
      tiver as 3 `BASE`.

**Frontend**
- [ ] Ecrã de plano: secção "Coberturas base" (3, sempre presentes,
      bloqueadas) + secção "Coberturas complementares" em **cards
      seleccionáveis** (grid, toggle on/off por card, sem pré-selecção).

### Open Decisions (o que o PDF NÃO resolve)

- **OD-ANGOLA-002** (mantém-se, mais restrita agora): que campos de
  `configuration_json` por cobertura complementar são precisos já
  (limites monetários anuais, franquias, percentagens de comparticipação,
  nº de sessões/ano)? O PDF descreve o *âmbito* de cada cobertura, não os
  *limites numéricos* — esses são decisões comerciais/actuariais reais que
  continuam a precisar de confirmação explícita antes de virarem schema.
- **OD-ANGOLA-007** (nova): os `code` propostos na tabela acima
  (`HOSPITALIZATION`, `OUTPATIENT`, etc.) são uma proposta técnica minha,
  não vêm do PDF — confirmar antes de os fixar em seed/migration (fácil de
  mudar agora, caro depois de haver dados reais a referenciá-los).

---

## Épico 2 — Versionamento automático do produto ✅ Backend concluído (2026-09-19)

**Pedido:** qualquer alteração ao produto (mesmo a mais básica) cria
automaticamente uma nova versão; deixa de existir a opção "criar versão" —
passa a ser sempre "editar produto".

### Estado actual (antes desta implementação)

Coexistiam **dois caminhos inconsistentes**:
- Editar nome/descrição no `ProductPage.tsx` cria e publica
  **silenciosamente** uma nova versão com um plano "Básico" hardcoded.
- Um botão explícito "Criar versão", separado, com datas manuais, sem
  criação automática de plano.

### Implementado

- `product_service.update_product()` chama agora `create_next_version()`
  sempre que o produto já tem pelo menos uma versão não-retirada. Um
  produto sem nenhuma versão ainda não tem nada para "avançar" — a
  primeira versão continua a ser criada explicitamente (endpoint
  `POST /products/{id}/versions`), só passa a acontecer uma vez.
- `create_next_version()`: retira a versão actual, cria a próxima
  (`effective_from=hoje`, `effective_to=None` — Épico 3), copia todos os
  Planos e as suas coberturas (`PlanBenefit`) sem alteração, e publica-a
  de imediato.
- Testado com 5 casos novos (`tests/product/test_auto_versioning.py`):
  retirada da versão antiga, herança de planos/coberturas, cotações
  antigas continuam legíveis após a retirada, produto sem versão não
  dispara nada, e edições sucessivas incrementam a versão de cada vez.

### Open Decisions — resolvidas

- **OD-ANGOLA-003** (resolvida): a nova versão fica **PUBLISHED
  automaticamente**, não DRAFT. Racional: o pedido original ("já não deve
  aparecer opção de criar versão mas sim de editar produto") implica uma
  única acção sem passo de publicação manual separado — inventar um passo
  extra de "publicar alterações" contradiria o pedido de simplicidade.
  Reversível se o Product Owner preferir DRAFT+publish explícito.
- **OD-ANGOLA-004** (resolvida, confirmado por teste): retirar a versão
  anterior nunca quebra nada que já a referencie — Quotes/PricingRuns
  apontam para um `productVersionId` específico e imutável, e retirar uma
  versão não apaga a linha nem os Planos/PlanBenefits associados.

---

## Épico 3 — Produtos sem data de término de vigência ✅ Backend concluído (2026-09-19)

### Estado actual (antes desta implementação)

`ProductVersion.effective_to` já era opcional (nullable) na BD e no
schema — tecnicamente já era possível deixar em branco. Faltava impedir
activamente que alguém a preenchesse.

### Implementado

- `ProductVersionCreateRequestSerializer` já não aceita `effectiveTo` —
  o campo foi removido do serializer (não apenas tornado opcional).
- `create_product_version()` já não recebe `effective_to` como parâmetro;
  cria sempre com `effective_to=None`.
- `create_next_version()` (Épico 2) também nunca define `effective_to` na
  versão nova — só na antiga, ao retirá-la (para reporting/histórico, não
  afecta a lógica: versões `RETIRED` ficam sempre excluídas da verificação
  de sobreposição de datas).
- `RETIRED` continua a ser o único mecanismo real de "fim de vida" de uma
  versão.
- **Efeito colateral tratado**: o golden test GT-ELIG-002 (ART-013)
  assume um `ProductVersion` com `effectiveTo` real — deixou de ser
  reproduzível via API real. Em vez de o descartar, passou a exercitar a
  mesma função de domínio (`evaluate()`) directamente, provando que a
  regra ELIG-006 continua implementada e correcta mesmo sem caminho HTTP
  para a construir (ver `tests/integration/test_golden_tests.py`).

### Open Decisions

Nenhuma.

---

## Épico 4 — Elegibilidade por número de apólice

**Pedido:** em vez de pedir os dados um a um, pedir o ID da apólice e
preencher tudo automaticamente.

### Estado actual (antes desta implementação)

Não existia um conceito de "Apólice" separado de `Quote`, e
`Quote.quote_number` nunca era realmente atribuído em código nenhum
(campo sempre `NULL`, ver `DECISIONS_TAKEN.md#S06-QUOTE-001` item 4) —
apesar de a coluna e o índice único já existirem desde o Sprint 6.
`EligibilityRequest` exigia `productVersionId`+`planId`+`effectiveDate`+
`proposerId`+`memberId` escolhidos manualmente, um a um (6 selects
sequenciais na UI).

### Implementado (backend)

- **OD-ANGOLA-005 resolvida — opção (a)**: "apólice" = `Quote.quoteNumber`
  de uma cotação `APPROVED`. Não inventa uma entidade `Policy` nova.
- `decide_quote()` atribui agora um `quote_number` real (sequencial, via
  `numbering_service.next_value`, mesmo mecanismo já usado para os
  números de documento) **só na aprovação** — nunca em REJECT/RETURN,
  nunca na criação. Continua a ser um número de teste/demonstração
  (sequencial simples), nunca um formato ARSEG real — ART-011 PROH-008
  continua a proibir inventar esse formato (ver `DECISIONS_TAKEN.md`).
- `GET /api/v1/quotes?quoteNumber=...` (pragmático, novo filtro) resolve
  a cotação completa (productVersionId/planId/proposerId/effectiveDate) a
  partir do número — falta só o frontend chamar isto e depois
  `GET /quotes/{id}/members` (já existente) para os beneficiários.
- Testado (`tests/quote/test_quote_number_lookup.py`): número atribuído
  só em APPROVE, lookup resolve o contexto completo, número desconhecido
  devolve lista vazia, sequências independentes por tenant.

### Tarefas

**Frontend**
- [ ] `EligibilityPage.tsx`: substituir os 6 selects por um único campo
      "Número da apólice/cotação" + botão "Procurar" (chama
      `GET /quotes?quoteNumber=` e depois `GET /quotes/{id}/members`),
      com possibilidade de correcção manual se necessário.

### Open Decisions

Nenhuma bloqueante — ver nota acima sobre o formato do número não ser
uma decisão real de negócio, só um identificador de teste.

---

## Épico 6 — CRUD completo de configurações (Rating Tables, Parameter Sets, Rule Versions, Document Templates)

**Pedido:** hoje não é possível editar nem remover Rating Tables,
Pricing Parameter Sets, Rule Versions nem Document Templates — só criar
(POST) e publicar. Isto bloqueia correcções normais de configuração.

### Estado actual

Confirmado em código (`apps/pricing/interfaces/views.py`,
`apps/product/interfaces/views.py`, `apps/foundation/interfaces/rule_views.py`,
`apps/quote/interfaces/views.py`): todos os quatro recursos só têm
`GET` (listar) e `POST` (criar) + um endpoint de `publish` dedicado.
**Não existe `PUT`/`PATCH`/`DELETE` em nenhum dos quatro.** Isto não é um
esquecimento aleatório — reflecte o desenho "versão imediável" usado em
todo o sistema (DRAFT → PUBLISHED → RETIRED), pensado para o invariante
dos golden tests (`docs/artifacts/ART-013-golden-tests/golden/README.md`:
"mesmo input + mesma versão exacta = mesmo resultado sempre"). Editar uma
versão já **PUBLISHED** in-place quebraria esse invariante para qualquer
cotação/pricing run que já a referencia.

### Objectivo

Dar capacidade real de manutenção sem quebrar a reprodutibilidade de
cotações/pricing runs já existentes:

- **Editar (PATCH/PUT)** — permitido **apenas enquanto o recurso está em
  `DRAFT`** (antes de publicar). Depois de `PUBLISHED`, a única forma de
  "corrigir" é criar uma nova versão (o fluxo de criação já suporta isto).
- **Remover (DELETE)** — permitido **apenas em `DRAFT`** (uma versão nunca
  usada por nenhuma cotação/pricing run pode ser apagada em segurança).
  Para uma versão `PUBLISHED`, "remover" na prática é **retirar**
  (`status=RETIRED`), nunca apagar a linha — para não quebrar histórico
  nem os golden tests.

### Tarefas

**Backend** (mesmo padrão nos 4 recursos: Rating Table, Pricing Parameter
Set, Rule Version, Document Template Version) — ✅ concluído
- [x] `PATCH /api/v1/rating-tables/{id}`,
      `/api/v1/pricing-parameter-sets/{id}`, `/api/v1/rule-versions/{id}`,
      `/api/v1/document-templates/{id}` — só aceite quando `status=DRAFT`;
      `409` reaproveitando o código de erro já existente de cada recurso
      (`CONFLICT` para Rating Table/Pricing Parameter Set/Rule Version,
      `CONFLICT` também para Document Template via `TemplateImmutableError`)
      se já publicado.
- [x] `DELETE` nos mesmos 4 endpoints — só aceite quando `status=DRAFT`.
      Corrigido um bug real encontrado pelos testes: apagar directamente a
      linha-pai (`RatingTable`/`PricingParameterSet`) falhava com
      `IntegrityError` de FK porque `rating_factor`/`pricing_parameter` não
      têm `ON DELETE CASCADE` — agora as linhas-filho são apagadas primeiro,
      na mesma transacção.
- [x] `POST /api/v1/configuration/{configType}/{configId}/retire`
      (dispatcher partilhado, mesmos 3 `configType` do publish:
      `pricing-parameter-set`/`rule-version`/`rating-table`) +
      `POST /api/v1/document-templates/{id}/retire` (endpoint dedicado,
      Document Template nunca fez parte desse dispatcher) — marcam
      `RETIRED` uma versão `PUBLISHED`.
- [ ] Change Request ao ART-006 para os novos verbos (hoje nenhum está
      documentado no contrato) — pendente, não bloqueia o uso real.

**Frontend** (fica para outra pessoa construir)
- [ ] `PricingConfigPanel.tsx` e o ecrã de Document Templates: acções
      "Editar" e "Remover" visíveis apenas em itens `DRAFT`; acção
      "Retirar" visível em itens `PUBLISHED`. Ver `FRONTEND_PLAN.md`.

### Open Decisions

- **OD-ANGOLA-006 — resolvida**: "remover" para um recurso já `PUBLISHED`
  significa **retirar** (soft, `RETIRED`) e nunca apagar a linha — dado o
  impacto directo nos golden tests e na reprodutibilidade de cotações
  antigas. Implementado exactamente assim nos 4 recursos, com testes
  (`tests/pricing/test_rating_table_crud.py`,
  `tests/product/test_pricing_parameter_crud.py`,
  `tests/foundation/test_rule_version_crud.py`,
  `tests/quote/test_document_template_crud.py`) a confirmar que retirar
  uma versão `DRAFT` é rejeitado (só faz sentido em `PUBLISHED`).

---

## Roadmap à parte — Portal do Cliente (autoatendimento de elegibilidade)

Pedido explicitamente como um roadmap separado, de prazo mais longo — **não**
é trabalho imediato dos épicos acima. Desenvolvido em detalhe (fases,
tarefas, decisões em aberto) em **`ROADMAP_PORTAL_CLIENTE.md`** — resumo:

- **Fase 0 — Fundação técnica**: mecanismo de autenticação/autorização
  novo e isolado para o cliente final (nunca reaproveitando scopes/roles
  internos DOC-001 §18); nova tabela `customer_account`; segunda
  fronteira de segurança (isolamento por proposer, além do isolamento por
  tenant já existente).
- **Fase 1 — Consulta de elegibilidade e estado da apólice (MVP)**:
  reaproveita `EvaluateEligibilityUseCase`, `benefit_service`, `Quote`
  já construídos.
- **Fase 2 — Self-service básico**: descarregar proposta, ver
  dependentes (reaproveita `document_service`, `QuoteMember`).
- **Fase 3 — Submissão de pedidos pelo próprio cliente** (prazo mais
  longo, desenho adiado até as Fases 0-2 estarem validadas em uso real).

**Nota:** isto é uma extensão de âmbito significativa (fora do V1 definido
em DOC-002/DOC-003) e deve ser tratada como um projecto à parte, com o seu
próprio contrato ART-006 (conjunto novo de endpoints públicos, tenant-
scoped por cliente final, nunca por staff) — não deve ser misturado com o
backoffice actual.

---

## Épico 5 — Simplificação adicional da configuração de Pricing

Itens concretos já identificados em `PricingConfigPanel.tsx` (que já tem
simplificação real: códigos auto-gerados, selects nomeados, acções
"criar e publicar" combinadas):

- [ ] Localizar/traduzir os estados `DRAFT`/`PUBLISHED` (reaproveitar o
      padrão `statusLabel` já usado no `ProductPage`).
- [ ] Extrair valores mágicos do código (`priority: -1`, `'BASE_PREMIUM'`,
      `'ADMIN_ADJUSTMENT'`) para constantes nomeadas e comentadas, com
      rótulos amigáveis onde aparecem na UI.
- [ ] Vista de histórico/edição das configurações existentes (hoje só há
      uma lista plana, sem editar nem ver histórico).
- [ ] Paginação real em vez do `size=200` fixo.

---

## Epico 7 - Resolucao das 8 decisoes do Product Owner (2026-09-21)

**Nota de numeracao:** o Product Owner numerou estas 8 decisoes OD-001 a
OD-008 na propria mensagem - para nao colidir com o OD-001/OD-002 que ja
existiam antes desta customizacao (tarifas reais / moeda-arredondamento,
ver `backend/DECISIONS_TAKEN.md`, seccao final "Fora de ambito desta
resolucao"), ficam registadas aqui como **OD-ANGOLA-008 a OD-ANGOLA-015**,
continuando a sequencia ja usada neste roadmap.

### OD-ANGOLA-008 (pedido "OD-001") - Auth0 como fornecedor de login

**Pedido:** construir a infra-estrutura para usar o Auth0 como IdP real.
**Estado:** backend ja pronto (nao precisou de codigo novo); guia de
configuracao escrito; ligacao do frontend ainda por fazer - falta o
Product Owner criar a conta Auth0.
Ver detalhe completo em `AUTH0_SETUP.md`.

### OD-ANGOLA-009 (pedido "OD-002") - versao antiga nunca inicia negocio novo

**Pedido (resumido):** quando existe uma versao nova de um produto, a
versao anterior deixa de poder ser usada para **novas** cotacoes - mas
cotacoes/contratos ja feitos com a versao anterior continuam validos ate
a renovacao ou fim do contrato.
**Resposta a pergunta "faz sentido?": sim** - e exactamente a pratica
correcta do mercado segurador (nao vender negocio novo sobre uma
tarifa/desenho descontinuado, mas nunca invalidar apolices em vigor).
**Estado:** concluido e testado.
- `apps/quote/application/quote_service.py::create_quote` agora rejeita
  (`400 VALIDATION-400`) sempre que `productVersion.status != PUBLISHED`.
- Uma cotacao ja criada contra uma versao que e retirada depois continua
  perfeitamente legivel e utilizavel (OD-ANGOLA-004 ja garantia isto).
- Testes: `backend/tests/quote/test_quote_requires_current_version.py`.

### OD-ANGOLA-010 (pedido "OD-003") - catalogo de relacoes familiares real, com pais/avos

**Pedido:** adicionar pais e avos ao catalogo, ligado desde a BD ate as
interfaces (nao hardcoded no frontend).
**Ambito confirmado com o Product Owner:** so o catalogo, aplicado ao
produto de Saude ja existente - a mencao a Acidentes Pessoais/Funeral era
so contexto de mercado, nao pedido para construir essas linhas de
produto novas.
**Estado:** concluido e testado (backend).
- Nova tabela `relationship_code` (tenant-scoped, migration
  `apps/client/infrastructure/migrations/0002_relationship_catalog.py`),
  com 5 valores: `TITULAR`, `CONJUGE` (conjuge ou equiparado),
  `FILHO` (descendente directo), **`ASCENDENTE`** (pai/mae/avo/avo - o
  valor novo pedido aqui), `OUTRO`.
- Cada codigo tem uma `category` (TITULAR/SPOUSE/CHILD/ASCENDANT/OTHER) -
  pensada para o motor de elegibilidade (OD-ANGOLA-012) poder aplicar
  regras por categoria (ex. "descendentes perdem elegibilidade aos
  18/25 anos") sem repetir a logica por cada codigo individual.
- `GET /api/v1/relationship-codes` - endpoint novo, e a partir daqui que
  o frontend deve construir o `<select>` de "Relacao", nunca de um array
  hardcoded.
- `POST/PUT /api/v1/members` agora rejeita (`400 VALIDATION-400`) um
  `relationshipCode` que nao esteja no catalogo do tenant.
- Testes: `backend/tests/client/test_relationship_codes.py`.
- **Ainda nao implementado (fica para o motor de elegibilidade,
  OD-ANGOLA-012):** os proprios limites de idade/documentos por
  categoria (ex. filho ate 18, ou ate 25 com comprovativo de
  matricula) - o catalogo so guarda o *codigo*, nao a *regra*.

### OD-ANGOLA-011 (pedido "OD-004") - importacao em massa: Excel primeiro, com validacao ETL

**Pedido:** suportar Excel (preferencial) e CSV, com um ETL que apanhe
campos vazios/valores nulos antes de importar.
**Estado:** concluido e testado.
- `.xlsx`/`.xlsm` e agora detectado automaticamente pela extensao do
  ficheiro e lido directamente (biblioteca `openpyxl`, ja declarada em
  `pyproject.toml`); `.csv` continua a funcionar como alternativa.
- Linhas completamente em branco numa folha Excel sao ignoradas (nao
  contam como erro).
- Novo passo de ETL: qualquer coluna esperada com um valor "parece vazio
  mas nao e" (`null`, `n/a`, `nan`, `none`, `-`, `--`, sem distinguir
  maiusculas/minusculas) e rejeitado explicitamente, em vez de ser aceite
  como texto valido.
- `relationshipCode` passou a ser validado contra o catalogo real
  (OD-ANGOLA-010) ja no momento do upload, nao so no commit.
- Testes: `backend/tests/client/test_imports_excel_etl.py`.

### OD-ANGOLA-012 (pedido "OD-005") - motor de elegibilidade inteligente e configuravel

**Pedido:** motor completo (compliance legal + regras dinamicas) descrito
em detalhe, com UX "Elegivel/Nao Elegivel" simples e mensagens humanas.
**Estado:** desenho entregue na integra; implementacao faseada - ver
`MOTOR_ELEGIBILIDADE.md` para a arvore de decisao, os exemplos de
mensagens amigaveis e o esquema JSON pedidos explicitamente pelo Product
Owner. Este e o maior dos 8 pedidos - tratado como o seu proprio roadmap
de implementacao dentro deste Epico, com fases proprias (ver esse
documento).

### OD-ANGOLA-013 (pedido "OD-006") - Kwanza (AOA) como moeda oficial, arredondamento oficial

**Pedido:** usar sempre AOA, arredondar para cima ao chegar a 3 casas
decimais.
**Estado:** ja era exactamente isto que o sistema fazia como valor de
teste (`ROUND_HALF_UP` a 2 casas decimais, aplicado a cada componente) -
promovido de "placeholder pendente de aprovacao" para **politica oficial
aprovada**. `apps/pricing/domain/money.py` actualizado (constante
renomeada de `PLACEHOLDER_ROUNDING_POLICY_*` para `ROUNDING_POLICY_*`,
codigo `OD-006-OFFICIAL-HALF-UP-2DP`). Nenhuma mudanca de comportamento -
so deixa de ser um placeholder.

### OD-ANGOLA-014 (pedido "OD-007") - regras de ajuste de preco configuraveis pela interface

**Pedido:** as regras de ajuste de preco devem ser configuraveis pela
interface, nunca hardcoded.
**Estado:** ja resolvido antes desta conversa, confirmado agora como
suficiente. `PricingRuleConfig`/`PricingAdjustment`
(`apps/pricing/domain/pricing_rules.py`) ja le os ajustes de um
`RuleVersion` publicado (rule_domain=PRICING, artifact_type=JSON) - nunca
hardcoded no codigo. O Epico 6 ja deu a esse `RuleVersion` o ciclo de
vida completo (criar/editar em DRAFT/publicar/retirar).
**Limitacao conhecida, aceite como esta:** um JSON de ajuste mal-formado
nao e rejeitado no momento de configurar - e silenciosamente ignorado no
momento de calcular o preco. Corrigir isto exigiria o modulo `foundation`
(dono do `RuleVersion` generico) depender do modulo `pricing` (dono do
formato especifico dos ajustes), o que DOC-004 s3.1 proibe
explicitamente. Fica documentado como opcao conhecida, nao como bug.

### OD-ANGOLA-015 (pedido "OD-008") - dupla aprovacao na publicacao de regras

**Pedido:** manter como esta - quem tem o perfil autorizado publica
sozinho.
**Estado:** confirmado, sem alteracao de codigo. E exactamente o
comportamento ja implementado desde S05-RULE-FOUR-EYES-001: publicar uma
`RuleVersion`/`RatingTable`/`PricingParameterSet` exige apenas o scope
`q360.admin` (o "perfil autorizado a configurar"), sem exigir um segundo
aprovador - ao contrario da aprovacao de cotacoes, que continua a exigir
sempre um actor diferente.

---

## Como usar este documento

- Cada épico tem "Open Decisions" que **bloqueiam** o início do código
  correspondente — não se avança sem resposta a essas perguntas.
- Este roadmap é vivo: itens podem ser adicionados, removidos ou
  substituídos a qualquer momento.
- À medida que cada épico avança, o trabalho real (migrations, decisões
  técnicas tomadas) continua a ser registado em `backend/DECISIONS_TAKEN.md`
  e `backend/OPEN_DECISIONS.md`, como sempre.

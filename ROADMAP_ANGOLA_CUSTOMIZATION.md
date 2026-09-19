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

## Épico 1 — Coberturas básicas obrigatórias

**Pedido:** todo o produto tem de ter sempre estas 3 coberturas, da BD à UI:

1. **Internamento Hospitalar** — cirurgias, sala operatória, honorários
   médicos, estadia em quarto hospitalar.
2. **Ambulatório (Consultas e Exames)** — consultas de clínica geral/
   especialidade e exames de diagnóstico fora do internamento.
3. **Urgências Médicas** — assistência imediata a episódios agudos/acidentes
   em território nacional.

### Estado actual

`Benefit`/`PlanBenefit` **já existem** na base de dados e no ORM
(`apps/product/infrastructure/models.py`, ART-012 V006) — mas **sem
endpoint API e sem UI** (`DECISIONS_TAKEN.md#S02-CONTRACT-001`,
`OPEN_DECISIONS.md`). Hoje não há nenhum caminho documentado para associar
uma cobertura a um plano. Este épico completa esse trabalho já identificado,
em vez de partir do zero.

### Objectivo

Um Plano nunca existe (ou nunca publica) sem as 3 coberturas core
associadas. A UI mostra-as sempre pré-preenchidas e não-removíveis;
coberturas adicionais continuam a ser opcionais.

### Tarefas

**Backend**
- [ ] Change Request ao ART-006 (ou decisão pragmática documentada, no
      padrão já usado neste projecto) para expor `Benefit`/`PlanBenefit`:
      catálogo de coberturas + associação por plano.
- [ ] Seed fixo das 3 coberturas core (code/name).
- [ ] Validação de domínio: publicar uma versão de produto falha
      (código de erro reaproveitado do catálogo fechado, ex.
      `PRICING-CONFIG` ou `VALIDATION-400` consoante o caso) se algum plano
      não tiver as 3 coberturas.
- [ ] Se precisar de schema adicional (ex. uma flag `is_core`), **migration
      nova** — nunca editar uma migration já aplicada (ver incidente
      corrigido nesta sessão: `0003_outbox_idempotency_consumer_inbox.py`).

**Frontend**
- [ ] Ecrã de plano passa a ter sempre uma secção "Coberturas", com as 3
      core pré-marcadas e bloqueadas para remoção.

### Open Decisions

- **OD-ANGOLA-001**: os `code` exactos das 3 coberturas (ex.
  `HOSPITALIZATION` / `OUTPATIENT` / `EMERGENCY`) e se são globais
  (partilhadas entre tenants) ou definidas por tenant.
- **OD-ANGOLA-002**: que campos de `configuration_json` por cobertura são
  realmente precisos agora (limites monetários? franquias? sub-limites?) —
  não inventar um schema de configuração sem confirmação de negócio.

---

## Épico 2 — Versionamento automático do produto

**Pedido:** qualquer alteração ao produto (mesmo a mais básica) cria
automaticamente uma nova versão; deixa de existir a opção "criar versão" —
passa a ser sempre "editar produto".

### Estado actual

Hoje coexistem **dois caminhos inconsistentes**:
- Editar nome/descrição no `ProductPage.tsx` cria e publica
  **silenciosamente** uma nova versão com um plano "Básico" hardcoded.
- Um botão explícito "Criar versão", separado, com datas manuais, sem
  criação automática de plano.

### Objectivo

Uma única acção "Editar Produto": qualquer alteração cria a próxima versão,
**herdando** os planos/coberturas reais da versão anterior (nunca um
"Básico" inventado). O botão "Criar versão" desaparece da UI.

### Tarefas

**Backend**
- [ ] Serviço único que, a cada edição, cria a próxima `ProductVersion`
      copiando planos/benefícios da versão anterior.
- [ ] Rever a regra de não-sobreposição de datas de
      `create_product_version` à luz do Épico 3 (datas deixam de ser
      escolhidas manualmente).

**Frontend**
- [ ] Remover o botão "Criar versão" da página de detalhe do produto.
- [ ] "Editar Produto" passa a ser o único ponto de entrada, sem hardcode
      de plano.

### Open Decisions

- **OD-ANGOLA-003**: a nova versão fica **PUBLISHED automaticamente**, ou
  fica **DRAFT** à espera de uma acção explícita "Publicar alterações"?
  (Recomendação: DRAFT + publish explícito, para não publicar a meio de uma
  edição composta por vários campos — mas é uma decisão de produto, não
  técnica.)
- **OD-ANGOLA-004**: o que acontece às cotações já em curso na versão
  anterior quando uma nova versão é criada? Confirmar que não quebra
  cotações existentes (o motor de pricing/elegibilidade já resolve por
  `productVersionId` explícito, por isso o impacto deve ser nulo — mas
  precisa de confirmação explícita antes de se mudar o comportamento por
  omissão de publicação).

---

## Épico 3 — Produtos sem data de término de vigência

### Estado actual

`ProductVersion.effective_to` já é opcional (nullable) na BD e no schema —
tecnicamente já é possível hoje deixar em branco. O que falta é impedir
activamente que alguém a preencha.

### Objectivo

Nenhum produto/versão pode ter `effective_to`. Um produto fica aberto
indefinidamente até ser substituído por nova versão ou marcado `RETIRED`.

### Tarefas

**Backend**
- [ ] `ProductVersionCreateRequestSerializer`: remover/ignorar
      `effectiveTo` do payload aceite (ou validar que é sempre `null`).
- [ ] Confirmar que `RETIRED` continua a ser o único mecanismo real de
      "fim de vida" de um produto.

**Frontend**
- [ ] Remover o campo "Data de término" de todos os formulários de
      produto/versão.

### Open Decisions

Nenhuma — mudança directa, sem ambiguidade.

---

## Épico 4 — Elegibilidade por número de apólice

**Pedido:** em vez de pedir os dados um a um, pedir o ID da apólice e
preencher tudo automaticamente.

### Estado actual

Não existe um conceito de "Apólice" separado de `Quote` — o mais próximo é
uma cotação já `APPROVED`. `EligibilityRequest` hoje exige
`productVersionId`+`planId`+`effectiveDate`+`proposerId`+`memberId`
escolhidos manualmente, um a um (6 selects sequenciais na UI).

### Objectivo

Utilizador introduz um único número (apólice/cotação) e o sistema
pré-preenche produto, versão, plano, proponente e membro automaticamente.

### Tarefas

**Backend**
- [ ] **Decisão de produto necessária primeiro** (ver Open Decision
      abaixo) antes de desenhar o endpoint.
- [ ] Endpoint pragmático de lookup (ex. `GET /quotes?quoteNumber=...` ou
      dedicado) que devolve tudo o necessário para pré-preencher o pedido
      de elegibilidade.

**Frontend**
- [ ] `EligibilityPage.tsx`: substituir os 6 selects por um único campo
      "Número da apólice/cotação" + botão "Procurar", com possibilidade de
      correcção manual se necessário.

### Open Decisions

- **OD-ANGOLA-005** (bloqueante): "apólice" mapeia para quê no domínio
  actual?
  - **(a)** Usar `Quote.quoteNumber` de uma cotação `APPROVED` como
    "número de apólice" — reaproveita o que já existe, não inventa
    entidade nova. **Recomendação para V1.**
  - **(b)** Criar uma entidade `Policy` nova, gerada a partir de uma Quote
    aprovada — mais fiel à realidade seguradora (uma apólice pode
    sobreviver a renovações/cotações futuras), mas implica schema novo,
    migration nova e Change Request a ART-005/ART-006. Só avançar para
    (b) se houver um requisito real que (a) não cubra.

---

## Roadmap à parte — Portal do Cliente (autoatendimento de elegibilidade)

Pedido explicitamente como um roadmap separado, de prazo mais longo — **não**
é trabalho imediato dos épicos acima.

- **Fase 1 — Consulta de elegibilidade própria**: endpoint autenticado por
  credenciais de cliente final (não staff) para consultar apenas o estado
  de elegibilidade da sua própria apólice. Requer:
  - Um mecanismo de autenticação novo para clientes finais (hoje só existem
    actors staff via scopes OAuth2/OIDC internos — `q360.read/write/admin/
    approve/audit`).
  - Um RBAC novo: o cliente só pode ver os *seus* dados, nunca dados de
    outro cliente ou de outro tenant.
- **Fase 2 — Self-service básico**: ver cobertura contratada, descarregar o
  documento de proposta já existente (reaproveitando
  `GET /quotes/{id}/proposal`).
- **Fase 3 — Submissão de pedidos pelo próprio cliente** (mais longo prazo).

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

## Como usar este documento

- Cada épico tem "Open Decisions" que **bloqueiam** o início do código
  correspondente — não se avança sem resposta a essas perguntas.
- Este roadmap é vivo: itens podem ser adicionados, removidos ou
  substituídos a qualquer momento.
- À medida que cada épico avança, o trabalho real (migrations, decisões
  técnicas tomadas) continua a ser registado em `backend/DECISIONS_TAKEN.md`
  e `backend/OPEN_DECISIONS.md`, como sempre.

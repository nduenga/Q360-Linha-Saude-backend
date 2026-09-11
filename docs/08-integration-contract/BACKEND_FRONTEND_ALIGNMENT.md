# Q360 — Alinhamento Backend ↔ Frontend (V1)

**Estado:** vivo — actualizar a cada Sprint fechado.
**Regra de ouro (herdada de DOC-000):** nenhuma das duas equipas inventa
campos, endpoints, estados, regras ou erros que não estejam nos documentos
abaixo. Se falta informação, marca-se `BLOCKED-SPEC` e pergunta-se — não se
adivinha.

## 0. Proveniência (não é opinião, é o que os documentos dizem)

| Assunto | Fonte única e final | Não é autoridade para isto |
|---|---|---|
| Contrato HTTP (paths, verbos, schemas JSON, erros) | **ART-006** — `Q360_MVP_ART_006_OpenAPI_Integral_v1.0.yml` | DOC-004 (é só descritivo/arquitectura) |
| Estados e transições de cotação/revisão/documento | **ART-009** — State Machines | Nenhum outro documento decide isto |
| Regras de negócio/pricing configuráveis | **ART-008** — Matriz Drools | Frontend nunca reimplementa isto |
| Papéis, permissões funcionais, casos de uso | **DOC-001** §6, §18 | — |
| Arquitectura backend (módulos, camadas) | **DOC-004** §3 | — |
| Estrutura de pastas/rotas/componentes React | **ART-010** — Estrutura React | Backend não dita isto, só o consome |
| Ordem de construção (o que existe em cada Sprint) | **DOC-002** — Roadmap 11 Sprints | — |

⚠️ Nota de governança: no Master Index (DOC-000), o ART-006 está marcado
`REVIEW`, não `APPROVED`. Estamos a implementar contra ele por decisão
prática do Product Owner (tu), mas se um campo mudar quando for aprovado
formalmente, isso é uma alteração de contrato, não um bug nosso — avisa-se
a outra equipa antes de mudar.

Há também dois ficheiros "parecidos" que **não são fonte de nada**, ficam só
como referência histórica (`docs/artifacts/_excluded-full-model/`):
`Q360_DDL_v1.0.sql` (523 tabelas, modelo completo V2) e
`Q360_OpenAPI_v1.0.yml` (99 paths, não referenciado no Master Index). Se
alguém dos dois lados olhar para esses ficheiros por engano, o que constrói
a partir deles está fora do contrato da V1.

---

## 1. Fronteira Backend ↔ Frontend

Fonte: DOC-004 §3.

- **Backend é dono de toda a regra de negócio.** Pricing, elegibilidade,
  transições de estado, permissões — tudo corre e é validado no backend.
  Frontend nunca decide se uma acção é permitida; só esconde/mostra UI com
  base no que a API devolveu (`roles`, `permissions` de `/me`, e nos corpos
  de resposta de cada recurso).
- **Frontend é dono de toda a apresentação.** Layout, validação de
  formulário *client-side* (UX, não substitui a validação do servidor),
  navegação, estado de UI local.
- **O contrato entre os dois é só o ART-006.** Nada de "o backend disse no
  Slack que ia devolver X" — se não está no OpenAPI, não existe.
- **DOC-004 §2:** "ART-006 será autoridade final do HTTP." Se o
  comportamento real do backend divergir do ART-006, corrige-se o ART-006
  primeiro (Change Request, DOC-000 §12) e só depois o código dos dois
  lados — nunca ao contrário.

---

## 2. O que já existe hoje (Sprints 1-3, validado)

Isto é 100% real e testado — não é plano, é o que está implementado e a
correr contra Postgres real.

### 2.1 Autenticação (ART-006 `securitySchemes.oauth2`)

- Fluxo: **OAuth2 Authorization Code** contra um Identity Provider externo
  (o backend é só *Resource Server* — não emite tokens, não tem
  login/password próprios, não existe endpoint `/login` ou `/token` nesta
  API).
- O frontend obtém um **access token JWT** do IdP e envia-o em todos os
  pedidos: `Authorization: Bearer <token>`.
- **Qual é o IdP concreto, e o nome exacto das claims dentro do token —
  ainda não está decidido** (OD-009, `backend/OPEN_DECISIONS.md#S01-AUTH-001`).
  O que está fixo e não muda com essa decisão:
  - Os **scopes OAuth2** que cada endpoint exige — `q360.read`,
    `q360.write`, `q360.approve`, `q360.admin`, `q360.audit` — vêm do
    ART-006 e não vão mudar.
  - Os **nomes dos campos JSON** que o backend devolve (ex.: `/me`) — vêm
    do ART-006 e não vão mudar.
  - O que pode mudar é só o nome interno da claim dentro do JWT — isso é
    invisível para o frontend, que nunca lê o JWT directamente.

### 2.2 `GET /api/v1/me` (ART-006 `operationId: getCurrentActor`)

Único endpoint que existe hoje. Requer scope `q360.read`.

Resposta `200`:

```json
{
  "actorId": "string",
  "tenantId": "uuid",
  "roles": ["ADMIN" | "PRODUCT_CONFIGURATOR" | "SUBSCRIBER" | "APPROVER" | "AUDITOR"],
  "permissions": ["quote:create", "quote:edit", "quote:calculate", "quote:submit",
                  "quote:review", "quote:approve", "quote:reject",
                  "product:manage", "pricing-config:manage", "audit:read"]
}
```

- Campos são **exactamente estes quatro, camelCase** (`ActorContext` no
  ART-006 tem `additionalProperties: false` — não aparece nem vai aparecer
  mais nenhum campo aqui).
- `permissions` é a matriz funcional do **DOC-001 §18**, já resolvida por
  role — o frontend usa isto directamente para mostrar/esconder acções, não
  precisa de re-calcular nada.
- **Nota:** as concessões marcadas "Opc." na matriz do DOC-001 §18 (ex.:
  `quote:create` para Aprovador) não aparecem em `permissions` até existir
  o motor de Authority Policy (Sprint 7) — não é bug, é âmbito.

### 2.3 Erros — formato único para toda a API (ART-006 `ProblemDetail`)

Todo o erro (agora e em qualquer sprint futuro) vem assim, com
`Content-Type: application/problem+json`:

```json
{
  "title": "Não autenticado",
  "status": 401,
  "code": "AUTH-401",
  "detail": "mensagem específica do erro",
  "correlationId": "uuid"
}
```

`code` só pode ser um destes valores (catálogo fechado, `x-q360-error-catalog`
do ART-006 — o frontend pode fazer `switch`/i18n em cima disto com
confiança, a lista não vai crescer sem passar por CR):

| code | Situação |
|---|---|
| `AUTH-401` | Não autenticado (token ausente/inválido/expirado) |
| `AUTH-403` | Autenticado mas sem autorização (scope ou permissão em falta) |
| `SEC-403` | Violação de fronteira de segurança/tenant/four-eyes |
| `VALIDATION-400` | Pedido inválido |
| `VERSION-CONFLICT` | Conflito de optimistic locking/versão |
| `QUOTE-STATE` | Transição de estado inválida |
| `PRICING-CONFIG` | Configuração de pricing ausente/inválida |
| `PRICING-FAILED` | Falha no cálculo |
| `IDEMP-REPLAY` | `Idempotency-Key` reutilizada com payload diferente |
| `NOT-FOUND` | Recurso não encontrado (âmbito do tenant) |
| `CONFLICT` | Conflito genérico |
| `RATE-LIMIT` | Limite de pedidos excedido |

O frontend **nunca** deve fazer parsing de `detail` para decidir lógica —
`detail` é só para mostrar/logar, a decisão programática é sempre por
`code`.

### 2.4 Cabeçalhos

| Cabeçalho | Direcção | Obrigatório | Nota |
|---|---|---|---|
| `Authorization: Bearer <jwt>` | Cliente → API | Sim, em todos os endpoints | — |
| `X-Correlation-Id` | Cliente → API (opcional) / API → Cliente (sempre) | Não (cliente pode omitir) | Se o cliente enviar, a API ecoa o mesmo valor; se não enviar, a API gera um. Útil para o frontend anexar a relatórios de bug. |
| `Idempotency-Key` | Cliente → API | Sim, só nas operações que o ART-006 marcar como exigindo (mutações críticas, ex. submissão de cotação) | Ver `IDEMP-REPLAY` acima |

### 2.5 URLs não têm barra final

`/api/v1/me`, `/api/v1/products`, etc. — **sem `/` no fim**, exactamente
como o ART-006 escreve os paths. O backend tem `APPEND_SLASH=False`
explicitamente por causa disto: um pedido `POST /api/v1/products/` (com
barra) dá 404, não um redirect. Configura o cliente HTTP do frontend
(axios/fetch/gerador do ART-006) para nunca acrescentar barra final.

### 2.6 Sprint 2 — Produtos, Versões, Planos, Parâmetros de Pricing

Scopes OAuth2 por operação (copiados do `security` de cada operação no
ART-006 — reparem que não seguem um padrão simples "GET=read,
POST=write"):

| Operação | Método/Path | Scope | Permissão DOC-001 §18 |
|---|---|---|---|
| `listProducts` | GET `/api/v1/products` | `q360.read` | — |
| `createProduct` | POST `/api/v1/products` | `q360.write` | `product:manage` |
| `getProduct` | GET `/api/v1/products/{id}` | `q360.read` | — |
| `updateProduct` | PUT `/api/v1/products/{id}` | `q360.write` | `product:manage` |
| `createProductVersion` | POST `/api/v1/products/{id}/versions` | `q360.admin` | `product:manage` |
| `publishProductVersion` | POST `/api/v1/product-versions/{id}/publish` | `q360.admin` | `product:manage` |
| `listPlans` | GET `/api/v1/plans?productVersionId=` | `q360.read` | — |
| `createPlan` | POST `/api/v1/plans` | `q360.admin` | `product:manage` |
| `getPlan` | GET `/api/v1/plans/{id}` | `q360.read` | — |
| `createPricingParameterSet` | POST `/api/v1/pricing-parameter-sets` | `q360.admin` | `pricing-config:manage` |
| `publishConfiguration` | POST `/api/v1/configuration/{type}/{id}/publish` | `q360.admin` | `pricing-config:manage` |

Notas importantes para o frontend:

- **`Product` não tem versão; `ProductVersion` sim.** Um produto é criado
  "vazio" (`status: DRAFT`, sem vigência); só a versão tem
  `effectiveFrom`/`effectiveTo`/`status: DRAFT|PUBLISHED|RETIRED`. Um plano
  pertence sempre a uma versão (`productVersionId`), nunca ao produto
  directamente.
- **`Plan` não tem endpoint de update.** Uma vez criado, um plano só muda
  criando uma nova versão do produto e um novo plano lá dentro. Não
  construir um formulário de "editar plano".
- **Publicar é definitivo.** `publishProductVersion` e `publishConfiguration`
  não podem ser repetidos (2ª tentativa → 409 `CONFLICT`) nem revertidos por
  esta API. A UI deve pedir confirmação explícita antes de chamar publish.
- **`rowVersion` é obrigatório no update.** `PUT /products/{id}` exige o
  `rowVersion` que a UI recebeu no último GET; se outro utilizador tiver
  alterado entretanto, vem 409 `VERSION-CONFLICT` — a UI deve recarregar e
  pedir para o utilizador reaplicar a alteração, nunca reenviar
  automaticamente.
- **`PricingParameterValue.value` para `DECIMAL` é sempre string**, nunca
  número JSON (ex. `"125.50"`, não `125.50`) — evita erros de
  arredondamento binário. Para `INTEGER`/`BOOLEAN`/`TEXT` usar o tipo JSON
  nativo correspondente; para `JSON` qualquer valor.
- ⚠️ **Não existe gestão de Benefícios/`Benefit` na API.** O backend tem a
  tabela mas o ART-006 não tem nenhum endpoint nem campo para isso — não é
  omissão de implementação, é um buraco no próprio contrato (ver
  `backend/OPEN_DECISIONS.md#S02-CONTRACT-001`). Não construir UI de
  benefícios até isto ser resolvido com uma CR ao ART-006.

### 2.7 Sprint 3 — Proponente, Membros, Importação, Elegibilidade

| Operação | Método/Path | Scope | Permissão DOC-001 §18 |
|---|---|---|---|
| `listProposers` | GET `/api/v1/proposers` | `q360.read` | — |
| `createProposer` | POST `/api/v1/proposers` | `q360.write` | — |
| `getProposer` | GET `/api/v1/proposers/{id}` | `q360.read` | — |
| `updateProposer` | PUT `/api/v1/proposers/{id}` | `q360.write` | — |
| `listMembers` | GET `/api/v1/members?proposerId=` | `q360.read` | — |
| `createMember` | POST `/api/v1/members` | `q360.write` | — |
| `getMember` | GET `/api/v1/members/{id}` | `q360.read` | — |
| `updateMember` | PUT `/api/v1/members/{id}` | `q360.write` | — |
| `uploadMemberImport` | POST `/api/v1/member-imports` (multipart!) | `q360.write` | — |
| `getMemberImport` | GET `/api/v1/member-imports/{id}` | `q360.read` | — |
| `commitMemberImport` | POST `/api/v1/member-imports/{id}/commit` | `q360.write` | — |
| `evaluateEligibility` | POST `/api/v1/eligibility/evaluate` | `q360.write` | — |
| `createRuleVersion` | POST `/api/v1/rule-versions` | `q360.admin` | — |
| `publishConfiguration` | POST `/api/v1/configuration/rule-version/{id}/publish` | `q360.admin` | — |

Nenhuma destas operações tem uma permissão DOC-001 §18 associada (a matriz
não cobre este domínio) — só o scope OAuth2 é verificado.

Notas importantes para o frontend:

- **`uploadMemberImport` é o único endpoint `multipart/form-data` de toda a
  API** — todo o resto é `application/json`. Não usar o mesmo cliente
  HTTP/interceptor genérico sem verificar o `Content-Type` aqui.
- **Não existe formulário de "editar plano/benefício" na importação** — o
  ficheiro CSV esperado tem cabeçalho
  `relationshipCode,firstName,lastName,dateOfBirth,sexCode,externalReference`
  (mesmos nomes de campo do `MemberCreateRequest`). Isto **não vem de
  nenhum documento aprovado** — é a interpretação mais simples possível na
  ausência de um template oficial (`backend/OPEN_DECISIONS.md#S03-IMPORT-001`).
  Se um "template de importação" vier a ser definido formalmente, este
  formato muda.
- **`uploadMemberImport` devolve 202, não 201.** O job fica `VALIDATED` (ou
  `FAILED`) de imediato nesta implementação (processamento síncrono), mas a
  UI deve tratar a resposta como "aceite para processamento", não como
  "membros já criados" — só `commitMemberImport` cria membros de facto.
- **`evaluateEligibility` devolve sempre HTTP 200** quando os dados de
  entrada são válidos, incluindo quando a decisão é `HARD_STOP` ou
  `CONFIG_ERROR` — estes são valores de negócio no corpo da resposta
  (`decision`), não erros HTTP. Só um pedido estruturalmente inválido
  (campos em falta, `productVersionId`/`planId` inexistentes) dá 400.
- **`EligibilityResponse.messages[].code`** (ex. `ELIG-AGE-MIN`,
  `ELIG-PLAN-INACTIVE`) é um catálogo **diferente e separado** do `code` de
  erro HTTP (`ProblemDetail.code`, secção 2.3) — não confundir os dois. A
  lista completa destes códigos está na Rule Matrix do ART-008, não no
  ART-006.
- ⚠️ **"Dependente requer titular" não está implementado.** Não existe
  nenhum catálogo aprovado de `relationshipCode` (nem "TITULAR" está
  confirmado como a string oficial) — ver
  `backend/OPEN_DECISIONS.md#S03-RELATIONSHIP-001`. A UI pode aceitar
  qualquer string até 40 caracteres em `relationshipCode`.
- ⚠️ **Os critérios de `REFERRAL`/`WARNING` na elegibilidade são um
  placeholder técnico**, não regras médicas reais (ART-008 é explícito:
  "No medical criteria invented in V1") — ver
  `backend/OPEN_DECISIONS.md#S03-ELIGIBILITY-001`. Não construir UI que
  assuma um significado clínico específico para estes dois estados ainda.

---

## 3. O que ainda NÃO existe (não construir contra isto ainda)

Por Sprint (DOC-002 §6/§7 — só se desbloqueia quando o Sprint anterior
fecha o respectivo Gate):

| Sprint | Área desbloqueada | Gate |
|---|---|---|
| S4–S5 | Pricing determinístico + regras | G3 |
| S6 | Cotação (`/api/v1/quotes/...`) | — |
| S7 | Workflow de subscrição (review/approve/reject) | — |
| S8 | Documentos/proposta | G4 |
| S9 | Eventos RabbitMQ, auditoria completa (`/api/v1/audit-events`) | — |

O ART-006 já tem **todos** os paths destes sprints escritos (é um contrato
"integral"), mas isso não significa que estão implementados — significa
que, quando chegarmos lá, o schema já está congelado e não se inventa nada
nessa altura também. Antes de um endpoint estar referido como "feito" numa
conversa entre as duas equipas, confirma-se aqui.

---

## 4. Regras que vinculam os dois lados (DOC-000 §3, princípios P-01 a P-10)

1. **Sem invenção (P-01):** um campo, endpoint, estado ou permissão só
   existe se estiver no documento autorizador. Dúvida → perguntar, não
   assumir.
2. **API-first (P-07):** o frontend consome o contrato, não o contrário.
   Se o frontend "precisa" de um campo que não existe no ART-006, isso é
   uma proposta de Change Request ao ART-006 — não um workaround local de
   nenhum dos dois lados.
3. **Determinismo (P-02):** nenhum valor de pricing, regra ou cálculo pode
   ser "temporário"/hardcoded em nenhum dos dois lados. Valores comerciais
   (prémios base, factores) vêm sempre de configuração versionada no
   backend.
4. **Tenant é fronteira de segurança (DOC-001 §20), não filtro de UI.** O
   frontend nunca envia `tenantId` num pedido para "escolher" o tenant — o
   tenant vem sempre do token validado do lado do backend. Se o frontend
   precisar de mostrar multi-tenant (ex. um admin com acesso a vários), isso
   é uma funcionalidade a especificar, não a inferir.
5. **Versão de documento vence versão de memória.** Se este ficheiro
   divergir do ART-006/DOC-001 actuais, o ART-006/DOC-001 é que estão
   certos — este documento é um resumo de trabalho, não a fonte.

---

## 5. Onde encontrar cada coisa

```
docs/
├── 00-index/        Master Documentation Index (DOC-000) — regras de precedência e gates
├── 01-functional/   DOC-001 — casos de uso, actores, permissões, fórmulas funcionais
├── 02-roadmap/      DOC-002 — 11 Sprints, dependências, gates
├── 03-backlog/      DOC-003 — tarefas técnicas por Sprint
├── 04-engineering-spec/  DOC-004 — arquitectura, módulos, camadas
├── 05-actuarial/    Manual de tarifação, briefing técnico, modelo de referência
└── artifacts/
    ├── ART-005-ddl/          schema físico PostgreSQL (backend apenas)
    ├── ART-006-openapi/      *** contrato HTTP — a fonte deste documento ***
    ├── ART-008-rules/        matriz de regras de pricing/elegibilidade
    ├── ART-009-state-machines/  estados e transições
    ├── ART-010-react/        estrutura de pastas/rotas do frontend
    ├── ART-011-seed-data/    catálogos de códigos (não tem relationshipCode!)
    └── ART-013-golden-tests/ casos de teste determinísticos
```

Este ficheiro (`docs/08-integration-contract/BACKEND_FRONTEND_ALIGNMENT.md`)
é o único sítio pensado para ser lido pelos dois lados ao mesmo tempo — os
restantes são por audiência (funcional, backend, frontend, actuarial).

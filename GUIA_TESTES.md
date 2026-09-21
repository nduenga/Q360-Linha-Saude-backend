# Guia prático de testes — Q360 (estado actual)

Este guia cobre tudo o que já está construído e verificado no backend
(Sprints 1-11 + Épicos 0, 1, 2+3, 4, 6 da customização Angola), com
credenciais reais e passos `curl` reproduzíveis. Não cobre o que ainda só
existe como roadmap (Épico 5, Portal do Cliente — ver
`ROADMAP_PORTAL_CLIENTE.md`).

---

## 1. Credenciais

### 1.1 Base de dados (PostgreSQL local, `backend/.env`)

| Variável | Valor |
|---|---|
| `POSTGRES_DB` | `q360` |
| `POSTGRES_USER` | `q360` |
| `POSTGRES_PASSWORD` | `fabiongila0123` |
| `POSTGRES_HOST` | `localhost` |
| `POSTGRES_PORT` | `5432` |

Ligar directamente: `psql --username q360 --dbname q360 --host localhost`
(pede a password acima). Schema real usado: `q360`.

### 1.2 Chave de assinatura de tokens dev (`backend/.env`)

| Variável | Valor |
|---|---|
| `OIDC_STATIC_VERIFICATION_KEY` | `dev-local-static-signing-key-change-me` |

Isto é o que torna possível emitir tokens JWT localmente sem um IdP OIDC
real (OD-009 ainda em aberto). **Nunca existe em produção** —
`config/settings/production.py` recusa arrancar se esta variável estiver
definida.

### 1.3 Utilizadores de login (via `POST /api/v1/auth/dev-login`)

Estes são os dois utilizadores que o ecrã de login do frontend já
apresenta (mirror de `mockAuth.ts`), agora reais:

| Email | Password | Role | Scopes |
|---|---|---|---|
| `admin@q360.co.ao` | `Q360admin2026` | `ADMIN` | `q360.read q360.write q360.admin q360.approve q360.audit` |
| `aprovador@q360.co.ao` | `Q360aprova2026` | `APPROVER` | `q360.read q360.write q360.approve q360.audit` |
| `subscritor@q360.co.ao` | `Q360demo2026` | `SUBSCRIBER` | `q360.read q360.write` |

Tenant usado pelos três: sempre `dev-tenant` (criado automaticamente no
primeiro login, se ainda não existir).

O `aprovador@q360.co.ao` existe especificamente para testar o fluxo de
aprovação de cotações pela interface: a regra de "four-eyes" (ART-012)
exige um actor diferente de quem submeteu — inicia sessão com este
utilizador (num separador diferente, ou depois de sair do admin) para
aprovar/rejeitar uma cotação submetida por `admin@q360.co.ao`.

### 1.4 Emitir tokens extra (qualquer role) — `manage.py issue_dev_token`

Útil para: testar `APPROVER`, `PRODUCT_CONFIGURATOR`, `AUDITOR`, ou
simular um segundo actor no mesmo tenant `dev-tenant` (obrigatório para o
fluxo de decisão — o mesmo actor nunca pode aprovar a sua própria
submissão).

```bash
cd backend
./.venv/Scripts/python.exe manage.py issue_dev_token \
  --tenant-code dev-tenant \
  --actor-id approver-1 \
  --roles APPROVER \
  --scopes "q360.read q360.write q360.approve"
```

Roles disponíveis: `ADMIN`, `PRODUCT_CONFIGURATOR`, `SUBSCRIBER`,
`APPROVER`, `AUDITOR`. Scopes disponíveis: `q360.read`, `q360.write`,
`q360.approve`, `q360.admin`, `q360.audit`.

> Requer que o tenant `dev-tenant` já exista — já vai existir depois do
> primeiro `dev-login` (secção 1.3), ou corre
> `manage.py seed_dev_tenant --code dev-tenant` primeiro.

### 1.5 Frontend — bearer estático de fallback (`Q360-Linha-Sa-de-frontend/.env.local`)

| Variável | Valor |
|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000` |
| `VITE_DEV_BEARER_TOKEN` | token JWT longo, já presente no `.env.local` (tenant diferente, `ADMIN`) |

Desde a ligação real da autenticação (Épico 0), este token só é usado
como **fallback** se não existir uma sessão de login real
(`src/dev/devAuth.ts`) — na prática, fazer login em `/login` sobrepõe-se
sempre a isto.

---

## 2. Arrancar tudo

### 2.1 Backend

```bash
cd backend
./.venv/Scripts/python.exe manage.py migrate          # só 1ª vez / após nova migration
./.venv/Scripts/python.exe manage.py seed_dev_tenant   # só 1ª vez
./.venv/Scripts/python.exe manage.py runserver 8000
```

Detalhe completo em `backend/DEV_SETUP.md`.

### 2.2 Frontend

```bash
cd Q360-Linha-Sa-de-frontend
npm run dev
```

Abre em `http://localhost:5173` (ou a porta seguinte livre — CORS já
aceita qualquer porta localhost em dev).

### 2.3 Correr a suite de testes automatizados do backend

```bash
cd backend
python -m pytest tests/ -q --deselect tests/foundation/test_idempotency.py::test_same_key_different_body_returns_409_idemp_replay
```

O `--deselect` evita um flake intermitente já documentado e não
relacionado com o trabalho actual (`DECISIONS_TAKEN.md#S09-IDEMPOTENCY-001`).
Se a suite completa falhar com `TimeoutError` a ligar ao Postgres do
Testcontainers, é instabilidade do Docker local, não do código — corre de
novo ou testa o módulo isolado (`pytest tests/product/ -q`).

---

## 3. Login e sessão

```bash
# 1. Login como admin
curl -s -X POST http://localhost:8000/api/v1/auth/dev-login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@q360.co.ao","password":"Q360admin2026"}'
# -> {"accessToken": "...", "expiresIn": 3600, "name": "Administrador Q360"}

export TOKEN="<accessToken acima>"

# 2. Confirmar identidade/permissões reais
curl -s http://localhost:8000/api/v1/me -H "Authorization: Bearer $TOKEN"
```

Todos os exemplos abaixo assumem `$TOKEN` exportado como acima (role
`ADMIN`, que tem todas as permissões usadas neste guia excepto aprovar a
sua própria submissão — ver secção 6).

---

## 4. Épico 1 — Catálogo de coberturas (Angola/ARSEG)

```bash
# Listar as 11 coberturas reais (3 obrigatórias + 8 facultativas)
curl -s http://localhost:8000/api/v1/benefits -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

Deve devolver `HOSPITALIZATION`, `OUTPATIENT`, `EMERGENCY` com
`benefitType=BASE`, e as 8 restantes com `benefitType=COMPLEMENTARY`.

Depois de criar um Plano (secção 5), as 3 obrigatórias já vêm
automaticamente associadas (`attach_core_benefits`) — confirmar:

```bash
curl -s http://localhost:8000/api/v1/plans/<planId>/benefits -H "Authorization: Bearer $TOKEN"

# Adicionar uma cobertura facultativa
curl -s -X POST http://localhost:8000/api/v1/plans/<planId>/benefits \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"benefitId":"<id de PHARMACY, por exemplo>"}'
```

Remover uma cobertura **obrigatória** deve ser sempre rejeitado — e
publicar um produto com um plano ao qual falte alguma das 3 obrigatórias
também (`MissingCoreBenefitsError`, `VALIDATION-400`).

---

## 5. Produto → Plano → Versão (auto-versionamento, sem data de fim — Épicos 2+3)

```bash
# Criar produto (cria logo a v1, PUBLISHED, sem data de fim)
curl -s -X POST http://localhost:8000/api/v1/products \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"code":"SAUDE-FAMILIA","name":"Saude Familia"}'

export PRODUCT_ID="<id acima>"

# Criar um plano (só é possível numa versão DRAFT — ver nota abaixo)
curl -s -X POST http://localhost:8000/api/v1/products/$PRODUCT_ID/versions \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"effectiveFrom":"2026-01-01"}'
export VERSION_ID="<id acima>"

curl -s -X POST http://localhost:8000/api/v1/plans \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"productVersionId\":\"$VERSION_ID\",\"code\":\"BASICO\",\"name\":\"Basico\"}"

curl -s -X POST http://localhost:8000/api/v1/product-versions/$VERSION_ID/publish \
  -H "Authorization: Bearer $TOKEN"

# Editar o produto -> cria e publica AUTOMATICAMENTE a próxima versão,
# herdando planos + coberturas (Épico 2+3, sem passo DRAFT manual)
curl -s -X PATCH http://localhost:8000/api/v1/products/$PRODUCT_ID \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"Saude Familia Plus","rowVersion":0}'

curl -s http://localhost:8000/api/v1/products/$PRODUCT_ID/versions -H "Authorization: Bearer $TOKEN"
# -> deve mostrar 2 versões: v1 RETIRED (effectiveTo=hoje), v2 PUBLISHED (effectiveTo=null)
```

Nenhuma versão criada por este fluxo tem alguma vez `effectiveTo`
diferente de `null` excepto quando é retirada automaticamente por uma
edição seguinte — nunca é pedido ao utilizador.

---

## 6. Cotação completa: criar → preçário → submeter → aprovar → número de apólice

Pré-requisito de preçário: uma `PricingParameterSet` e uma `RatingTable`
**publicadas**. Pré-requisito de elegibilidade (para incluir membros):
uma `RuleVersion` de domínio `ELIGIBILITY` **publicada**.

```bash
# Parametrização de preço
curl -s -X POST http://localhost:8000/api/v1/pricing-parameter-sets \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"code":"BASE-2026","effectiveFrom":"2026-01-01","parameters":[{"code":"BASE_PREMIUM","valueType":"DECIMAL","value":"100.00"}]}'
export PS_ID="<id>"
curl -s -X POST http://localhost:8000/api/v1/configuration/pricing-parameter-set/$PS_ID/publish -H "Authorization: Bearer $TOKEN"

# Tabela de tarifação
curl -s -X POST http://localhost:8000/api/v1/rating-tables \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"code":"AGE-2026","name":"Age 2026","effectiveFrom":"2026-01-01","currencyCode":"AOA","factors":[{"factorCode":"AGE_FACTOR","dimensions":{},"factorValue":"1.00"}]}'
export RT_ID="<id>"
curl -s -X POST http://localhost:8000/api/v1/configuration/rating-table/$RT_ID/publish -H "Authorization: Bearer $TOKEN"

# Regra de elegibilidade (mínima, sem lógica real associada — apenas para não cair em CONFIG_ERROR)
curl -s -X POST http://localhost:8000/api/v1/rule-versions \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"code":"ELIG-2026","name":"Elig 2026","ruleDomain":"ELIGIBILITY","effectiveFrom":"2026-01-01","artifactType":"JSON","artifactRef":"{}"}'
export RV_ID="<id>"
curl -s -X POST http://localhost:8000/api/v1/configuration/rule-version/$RV_ID/publish -H "Authorization: Bearer $TOKEN"

# Proponente + membro
curl -s -X POST http://localhost:8000/api/v1/proposers \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"proposerType":"INDIVIDUAL","displayName":"Joao Manuel"}'
export PROPOSER_ID="<id>"
curl -s -X POST http://localhost:8000/api/v1/members \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"proposerId\":\"$PROPOSER_ID\",\"relationshipCode\":\"TITULAR\",\"dateOfBirth\":\"1990-01-01\"}"
export MEMBER_ID="<id>"

# Cotação
curl -s -X POST http://localhost:8000/api/v1/quotes \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"proposerId\":\"$PROPOSER_ID\",\"productVersionId\":\"$VERSION_ID\",\"planId\":\"<planId>\",\"effectiveDate\":\"2026-06-01\"}"
export QUOTE_ID="<id>"

curl -s -X POST http://localhost:8000/api/v1/quotes/$QUOTE_ID/members \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"memberId\":\"$MEMBER_ID\"}"

curl -s -X POST http://localhost:8000/api/v1/quotes/$QUOTE_ID/price -H "Authorization: Bearer $TOKEN"

curl -s http://localhost:8000/api/v1/quotes/$QUOTE_ID -H "Authorization: Bearer $TOKEN"
# -> status deve ser READY, com rowVersion actualizado

# Submeter para revisão (usa o rowVersion devolvido acima)
curl -s -X POST http://localhost:8000/api/v1/quotes/$QUOTE_ID/submit \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"rowVersion":1}'
```

**Aprovar exige um actor diferente** (regra de segregação de funções,
CHECK constraint na BD). Usa o login `aprovador@q360.co.ao` (secção 1.3)
para obter um segundo token — ou, alternativamente, `issue_dev_token`
(secção 1.4) com qualquer role:

```bash
export APPROVER_TOKEN="<accessToken do login como aprovador@q360.co.ao>"

curl -s -X POST http://localhost:8000/api/v1/quotes/$QUOTE_ID/decision \
  -H "Authorization: Bearer $APPROVER_TOKEN" -H "Content-Type: application/json" \
  -d '{"decision":"APPROVE","reasonCode":"MEETS_CRITERIA","rowVersion":2}'
```

Ao aprovar, a cotação recebe `quoteNumber` automaticamente (Épico 4 —
`numbering_service`, sequência `QUOTE_NUMBER` por ano). Confirmar:

```bash
curl -s http://localhost:8000/api/v1/quotes/$QUOTE_ID -H "Authorization: Bearer $TOKEN"
# -> quoteNumber preenchido, status=APPROVED

# Elegibilidade por número de apólice (Épico 4) — em vez de pedir todos
# os dados um por um, um único parâmetro devolve o contexto completo
curl -s "http://localhost:8000/api/v1/quotes?quoteNumber=<quoteNumber acima>" -H "Authorization: Bearer $TOKEN"
```

---

## 7. Documento de proposta

```bash
curl -s -X POST http://localhost:8000/api/v1/document-templates \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"templateCode":"QUOTE_PROPOSAL_DEFAULT","storageRef":"internal://placeholder","effectiveFrom":"2026-01-01"}'
export TEMPLATE_ID="<id>"
curl -s -X POST http://localhost:8000/api/v1/document-templates/$TEMPLATE_ID/publish -H "Authorization: Bearer $TOKEN"

curl -s -X POST http://localhost:8000/api/v1/quotes/$QUOTE_ID/proposal -H "Authorization: Bearer $TOKEN"
# -> status=GENERATED, documentNumber atribuído

curl -s http://localhost:8000/api/v1/quotes/$QUOTE_ID/proposal -H "Authorization: Bearer $TOKEN"
```

---

## 8. Épico 6 — Editar / remover / retirar configurações

Válido para os 4 recursos: Rating Table, Pricing Parameter Set, Rule
Version, Document Template. Regra igual nos 4: só se edita/apaga em
`DRAFT`; uma vez `PUBLISHED`, só se pode **retirar** (nunca apagar).

```bash
# Editar uma Rating Table ainda em DRAFT
curl -s -X PATCH http://localhost:8000/api/v1/rating-tables/<id> \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"Novo nome","currencyCode":"AOA","factors":[{"factorCode":"AGE_FACTOR","dimensions":{},"factorValue":"1.10"}]}'

# Apagar (só DRAFT)
curl -s -X DELETE http://localhost:8000/api/v1/rating-tables/<id> -H "Authorization: Bearer $TOKEN"

# Retirar uma versão já PUBLISHED (dispatcher partilhado)
curl -s -X POST http://localhost:8000/api/v1/configuration/rating-table/<id>/retire -H "Authorization: Bearer $TOKEN"
curl -s -X POST http://localhost:8000/api/v1/configuration/pricing-parameter-set/<id>/retire -H "Authorization: Bearer $TOKEN"
curl -s -X POST http://localhost:8000/api/v1/configuration/rule-version/<id>/retire -H "Authorization: Bearer $TOKEN"

# Pricing Parameter Set e Rule Version seguem o mesmo padrão de PATCH/DELETE:
curl -s -X PATCH http://localhost:8000/api/v1/pricing-parameter-sets/<id> \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"parameters":[{"code":"BASE_PREMIUM","valueType":"DECIMAL","value":"120.00"}]}'
curl -s -X DELETE http://localhost:8000/api/v1/pricing-parameter-sets/<id> -H "Authorization: Bearer $TOKEN"

curl -s -X PATCH http://localhost:8000/api/v1/rule-versions/<id> \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"Novo nome","artifactType":"JSON","artifactRef":"{}"}'
curl -s -X DELETE http://localhost:8000/api/v1/rule-versions/<id> -H "Authorization: Bearer $TOKEN"

# Document Template usa endpoint dedicado (não está no dispatcher partilhado)
curl -s -X PATCH http://localhost:8000/api/v1/document-templates/<id> \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"storageRef":"internal://novo"}'
curl -s -X DELETE http://localhost:8000/api/v1/document-templates/<id> -H "Authorization: Bearer $TOKEN"
curl -s -X POST http://localhost:8000/api/v1/document-templates/<id>/retire -H "Authorization: Bearer $TOKEN"
```

Qualquer tentativa de `PATCH`/`DELETE`/`retire` fora do estado certo
devolve `409` com `code` `CONFLICT` (ou `QUOTE-STATE` no caso específico
de Document Template, que reaproveita o catálogo de erros de `quote`).

Testes automatizados equivalentes:
`backend/tests/pricing/test_rating_table_crud.py`,
`backend/tests/product/test_pricing_parameter_crud.py`,
`backend/tests/foundation/test_rule_version_crud.py`,
`backend/tests/quote/test_document_template_crud.py`.

---

## 9. Avaliação de elegibilidade (isolada, sem cotação)

```bash
curl -s -X POST http://localhost:8000/api/v1/eligibility/evaluate \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"proposerId\":\"$PROPOSER_ID\",\"memberId\":\"$MEMBER_ID\",\"productVersionId\":\"$VERSION_ID\",\"planId\":\"<planId>\",\"effectiveDate\":\"2026-06-01\",\"context\":{}}"
```

`decision` pode ser `ELIGIBLE`/`WARNING`/`REFERRAL`/`HARD_STOP`/
`CONFIG_ERROR` (este último se não houver `RuleVersion` `ELIGIBILITY`
publicada para o tenant — fail-closed, nunca assume elegível por omissão).

---

## 10. Roteiro de teste pela plataforma visual (frontend)

**Correcção a uma nota anterior deste guia:** a maior parte das páginas
principais **já está ligada ao backend real** — não só o login e as
coberturas. Confirmado directamente no código de cada página (nenhuma
lê de `Mockdata.ts`):

| Página / menu | Estado | O que já dá para testar visualmente |
|---|---|---|
| Login | Real | Épico 0 — já testado, a funcionar |
| Produtos | Real | Criar produto/plano, coberturas (Épico 1), **editar o produto e confirmar que gera uma nova versão sozinho, sem data de fim (Épico 2+3)** — o botão "Criar versão" ainda aparece, mas passou a ser opcional (roadmap pede para o remover) |
| Proponentes / Membros | Real | Criar proponente, adicionar membros |
| Pricing | Real | Criar/publicar Rating Table e Pricing Parameter Set, calcular preço |
| Nova Cotação / Resumo da Cotação | Real | Criar cotação, ver preçário, submeter, cancelar — o `quoteNumber` (Épico 4) já aparece no resumo assim que a cotação é aprovada |
| Underwriting / Revisão | Real | Rever, aprovar, rejeitar, devolver uma cotação submetida (precisa de um segundo utilizador — ver `aprovador@q360.co.ao` na secção 1.3) |
| Auditoria | Real | Consultar o registo de eventos |
| Dashboard | **Mock** | Métricas e fila de prioridade ainda são dados inventados no browser — não reflectem a BD real |
| Administração | **Mock** | Gestão de utilizadores/roles ainda são dados inventados no browser |

**O que ainda não tem ecrã nenhum (só testável via `curl`, secção 8):**
Épico 6 — editar/remover/retirar Rating Tables, Pricing Parameter Sets,
Rule Versions e Document Templates. O `PricingConfigPanel.tsx` ainda só
tem "criar e publicar"; os botões "Editar"/"Remover"/"Retirar" são o
único item de frontend que falta desse épico (ver `FRONTEND_PLAN.md`).

**Roteiro sugerido, de ponta a ponta, tudo pela interface:**
1. Login como `admin@q360.co.ao`.
2. Produtos → criar um produto → criar/publicar uma versão → criar um
   plano (as 3 coberturas obrigatórias já vêm associadas automaticamente)
   → adicionar uma cobertura facultativa.
3. Editar o nome do produto → confirmar na lista de versões que apareceu
   uma versão nova, publicada, sem data de fim, e que a anterior ficou
   retirada.
4. Pricing → criar e publicar um Pricing Parameter Set e uma Rating
   Table.
5. Proponentes → criar um proponente e um membro.
6. Nova Cotação → escolher o plano, o proponente, adicionar o membro,
   calcular o preço.
7. Submeter a cotação para revisão.
8. Sair e voltar a entrar como `aprovador@q360.co.ao` (secção 1.3) →
   aprovar a cotação em Underwriting.
9. Voltar ao resumo da cotação como admin → confirmar que o número da
   apólice apareceu.
10. Auditoria → confirmar que todas as acções acima ficaram registadas.

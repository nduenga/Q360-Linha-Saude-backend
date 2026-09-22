# Plano de Frontend — handoff (actualizado 2026-09-22)

**Para quem vai construir/actualizar o frontend.** Esta sessão constrói
**só backend**. Este documento substitui por completo a versão anterior
(estava desactualizada em vários pontos — Épicos 4 e 6 já tinham o
backend concluído há dias e continuavam marcados "por construir"). Usa
`ROADMAP_ANGOLA_CUSTOMIZATION.md`/`ROADMAP_PORTAL_CLIENTE.md` para o
racional de negócio e `CHECKLIST_CUSTOMIZACAO.md` para o estado
consolidado de todos os épicos; este ficheiro é só o **contrato exacto**
que o frontend precisa para implementar contra o que já existe.

**Repositório frontend:** `Q360-Linha-Sa-de-frontend`, branch `main`.
**Backend:** `Quote - Saúde/backend`, branch `fabio`.

Cada secção indica: **✅ Backend pronto** (endpoint já existe e testado —
pode implementar já) ou **⏳ Backend por construir** (aguarda outra sessão
fechar isso primeiro).

---

## Épico 2 — Versionamento automático do produto ✅ Backend pronto

Editar um produto (`PATCH /api/v1/products/{id}`) já cria e publica
sozinho a próxima versão, herdando os planos/coberturas reais da versão
anterior — nunca inventa um plano "Básico". Resposta inclui a nova versão
já `PUBLISHED`.

### O que fazer no frontend
- Remover o botão "Criar versão" (`ProductDetailPage`, `createProductVersion`)
  — deixa de haver essa acção manual separada.
- `EditProductForm`/`updateMutation`: confirmar que já não constrói um
  plano "Básico" localmente — o backend trata disso.
- Depois de `PATCH`, a versão anterior aparece `RETIRED` (com
  `effectiveTo` preenchido automaticamente) e a nova aparece `PUBLISHED`
  sem `effectiveTo` — refrescar a lista de versões do produto.

---

## Épico 3 — Produtos sem data de término ✅ Backend pronto

`effectiveTo` foi removido do payload de criação de versão.

### O que fazer no frontend
- Remover o campo "Data de término" de todos os formulários de
  produto/versão em `ProductPage.tsx`.

---

## Épico 4 — Elegibilidade/apólice por número de apólice ✅ Backend pronto

`Quote.quoteNumber` é atribuído automaticamente no momento da aprovação
(`POST /quotes/{id}/decision` com `decision=APPROVE`).

```
GET /api/v1/quotes?quoteNumber=<numero>
Authorization: Bearer <token staff>
```
Devolve a lista de `Quote` (normalmente 1 resultado) já com
`proposerId`, `productVersionId`, `planId`, `status`, `quoteNumber` —
tudo o que os 6 selects manuais de `EligibilityPage.tsx` pediam um a um.

### O que fazer no frontend
- Substituir os 6 selects sequenciais (Produto → Versão → Plano → Data →
  Proponente → Membro) por: campo "Número da apólice" + botão "Procurar",
  chamando o endpoint acima.
- Ao encontrar, pré-preencher tudo em modo leitura, com opção "Alterar"
  para cair de volta ao fluxo manual (fallback se o lookup falhar ou o
  utilizador precisar de corrigir algo).
- Nenhum resultado → mostrar "Nenhuma apólice encontrada com este
  número", nunca um erro genérico.

---

## Épico 5 — Pricing mais simples ✅ Backend não bloqueia (100% frontend)

Em `PricingConfigPanel.tsx`:
- Reaproveitar o `statusLabel` map já usado em `ProductPage` para
  DRAFT/PUBLISHED/RETIRED (hoje mostra a string crua).
- Substituir os literais mágicos (`priority: -1`, `'BASE_PREMIUM'`,
  `'ADMIN_ADJUSTMENT'`) por constantes nomeadas no topo do ficheiro.
- Paginação real — o backend já pagina (`?page=`/`?size=`); hoje o
  frontend pede `size=200` fixo e ignora o resto.
- Vista de histórico das configurações existentes (hoje só há uma lista
  plana) — usar o novo `GET` com filtro de `status`/`ruleDomain` onde
  aplicável (ver Épico 6 abaixo).

---

## Épico 6 — Editar / Remover / Retirar (Rating Tables, Pricing Parameter Sets, Rule Versions, Document Templates) ✅ Backend pronto

Regra igual para os 4 recursos: só se edita/apaga em `DRAFT`; uma vez
`PUBLISHED`, só se pode **retirar** (nunca apagar a linha).

| Acção | Método/rota | Quando mostrar o botão |
|---|---|---|
| Editar | `PATCH /api/v1/rating-tables/{id}`, `/pricing-parameter-sets/{id}`, `/rule-versions/{id}`, `/document-templates/{id}` | `status=DRAFT` |
| Remover | `DELETE` nas mesmas rotas | `status=DRAFT` |
| Retirar | `POST /api/v1/configuration/{rating-table\|pricing-parameter-set\|rule-version}/{id}/retire` (dispatcher partilhado) ou `POST /api/v1/document-templates/{id}/retire` (rota dedicada) | `status=PUBLISHED` |

Qualquer tentativa fora do estado certo devolve `409` (`code=CONFLICT`,
ou `QUOTE-STATE` no caso de Document Template).

### O que fazer no frontend
- Em `PricingConfigPanel.tsx` e no ecrã de Document Templates: botão
  "Editar" (abre o formulário de criação pré-preenchido, `PATCH` em vez
  de `POST`), "Remover" e "Retirar", cada um só visível no estado
  correspondente da tabela acima.

---

## Motor de Elegibilidade — Fase A ✅ Backend pronto (2026-09-22)

`POST /api/v1/eligibility/evaluate` (e o resultado embutido em qualquer
fluxo de cotação que chame `EvaluateEligibilityUseCase`) agora pode
devolver **3 decisões novas**, além das 5 já existentes:

| `decision` | Cor no ecrã | Nunca mostrar como |
|---|---|---|
| `ELIGIBLE` | Verde — "Elegível" | — |
| `ELIGIBLE_WITH_LOADING` | Verde, com nota do agravamento | "Rejeitado" |
| `WARNING` | Amarelo | — |
| `REFERRAL` | Amarelo | — |
| `PENDING_DOCUMENT` | Amarelo — "Falta um documento" | "Rejeitado" |
| `PENDING_MEDICAL_BOARD` | Amarelo — "Em análise" | "Rejeitado" |
| `HARD_STOP` | Vermelho — "Não Elegível" | — (o único vermelho) |
| `CONFIG_ERROR` | Nunca mostrado ao cliente final — erro interno | — |

`messages[]` (mesma forma de sempre — `{code, severity, message}`) já
vem com **texto amigável em português** para os novos códigos
(`FALTA_CERTIFICADO_MATRICULA`, `FALTA_HOMOLOGACAO_UNIAO_FACTO`,
`FALTA_PROVA_DEPENDENCIA_ASCENDENTE`, `IDADE_ACIMA_LIMITE_DEPENDENTE`,
`ELIGIBLE_COM_AGRAVAMENTO`, `PENDENTE_JUNTA_MEDICA`) — mostrar
`message` directamente, nunca `code`, a um utilizador final. Um novo
código informativo `ELIG-WAITING-PERIOD` (severidade `INFO`) pode
aparecer junto de um resultado não bloqueante, com o número de dias de
carência aplicável — mostrar como nota, nunca como aviso.

### `context.angola` — novo bloco opcional no pedido

O `context` do pedido (`POST /eligibility/evaluate`, campo já existente)
aceita agora um sub-objecto `angola` com as provas/evidências que o
motor usa para decidir `PENDING_DOCUMENT`/`ELIGIBLE_WITH_LOADING`/etc.
Nenhum destes campos tem upload de ficheiro associado nesta fase (não
existe ainda armazenamento de documentos — Fase B, em aberto); são
booleanos que a equipa de subscrição marca manualmente depois de
validar o documento por fora do sistema:

```jsonc
{
  "context": {
    "angola": {
      "hasEnrollmentCertificate": false,       // dependente CHILD acima da idade sem prova
      "unionBondType": "UNIAO_DE_FACTO",        // ou "CASAMENTO", para SPOUSE
      "hasUnionHomologationDocument": false,
      "hasCohabitationOrFinancialDependencyProof": false,  // ASCENDANT
      "hasPreExistingCondition": false,
      "previousPolicyNumber": null,             // portabilidade — carência
      "previousPolicyContinuous": false
    }
  }
}
```

### O que fazer no frontend
- Actualizar o mapa de cores/labels de `decision` no ecrã de
  elegibilidade (e em qualquer resumo de cotação que mostre o resultado)
  para as 8 decisões da tabela acima — nunca hardcoded para as 5
  antigas.
- Mostrar sempre `messages[].message` (já traduzido/amigável), nunca
  `messages[].code`.
- Opcional, quando fizer sentido no fluxo de subscrição: um pequeno
  formulário/checklist para marcar os campos de `context.angola` antes
  de calcular elegibilidade de um dependente CHILD/SPOUSE/ASCENDANT —
  não é bloqueante, o endpoint já funciona sem este bloco (fica tudo
  como hoje se omitido).

---

## Portal do Cliente — Fase 0 (Fundação técnica) ✅ Backend pronto (2026-09-22)

Aplicação/rota **completamente nova e isolada** do backoffice actual —
autenticação, RBAC e cliente HTTP próprios. **Nunca reaproveitar**
`CurrentUserContext`, `httpClient` autenticado, `session.ts` ou qualquer
token de staff para estes ecrãs, e vice-versa: um token deste portal
nunca deve ser aceite por nenhum endpoint `/api/v1/quotes`,
`/api/v1/products`, etc. (são mecanismos de assinatura diferentes, por
desenho).

Esta fase é só a fundação de autenticação — **não há ainda nenhum
ecrã de consulta** (isso é a Fase 1, ainda não construída). O que já
existe são os 2 endpoints públicos de login.

### Fluxo de login (2 passos)

`{tenantId}` é um UUID fixo, conhecido do build/deployment do portal
(cada seguradora publica o seu portal com o seu próprio `tenantId` — não
é algo que o utilizador digite).

**Passo 1 — pedir acesso:**
```
POST /api/v1/customer-portal/{tenantId}/auth/request-access
Content-Type: application/json

{
  "quoteNumber": "AO-2026-000123",
  "registrationNumber": "123456789LA042",
  "email": "cliente@example.com"
}
```
- **Sempre** `202 Accepted`, corpo vazio — mesmo que os dados não
  correspondam a nada real (o backend nunca revela se uma apólice ou
  documento existe). O ecrã deve mostrar sempre a mesma mensagem de
  sucesso ("Se os dados estiverem correctos, enviámos um código para o
  seu email"), nunca um erro específico.
- `429` (`code=RATE-LIMIT`) se houver demasiadas tentativas seguidas —
  mostrar "Demasiadas tentativas, tente novamente mais tarde".
- `400` (`code=VALIDATION-400`) só por campos em falta/malformados no
  próprio formulário.

**Passo 2 — confirmar o código:**
```
POST /api/v1/customer-portal/{tenantId}/auth/verify-otp
Content-Type: application/json

{
  "quoteNumber": "AO-2026-000123",
  "registrationNumber": "123456789LA042",
  "email": "cliente@example.com",
  "otp": "123456"
}
```
Resposta de sucesso (`200`):
```json
{ "accessToken": "<jwt>", "tokenType": "Bearer", "expiresIn": 1800 }
```
Erros possíveis:
| Status | `code` | Quando | UI |
|---|---|---|---|
| `401` | `AUTH-401` | Dados/código errados ou expirados (nunca diz qual) | "Código inválido ou expirado" |
| `423` | `PORTAL-LOCKED` | 5 tentativas falhadas seguidas — bloqueado 30 min | "Conta temporariamente bloqueada, tente novamente mais tarde" |
| `429` | `RATE-LIMIT` | Demasiadas tentativas seguidas (por IP) | "Demasiadas tentativas, tente novamente mais tarde" |
| `400` | `VALIDATION-400` | Campos em falta/malformados | erro de formulário normal |

Todos os erros usam o mesmo envelope já conhecido do backoffice:
```json
{ "title": "...", "status": 401, "code": "AUTH-401", "detail": "...", "correlationId": "..." }
```

### O que fazer no frontend
- Novo ecrã/app "Portal do Cliente", rota própria (ex.
  `portal.q360.co.ao` ou `/portal/*`, a decidir pelo deployment),
  **sem** o layout/menu do backoffice.
- Formulário 1: número de apólice + documento + email → chama
  `request-access` → avança sempre para o ecrã 2 com a mensagem de
  sucesso genérica.
- Formulário 2: código de 6 dígitos → chama `verify-otp` → guarda
  `accessToken` (ex. `sessionStorage`, cliente HTTP próprio deste
  portal, nunca o `httpClient` do backoffice) → redirecciona para a
  área autenticada.
- `accessToken` expira em `expiresIn` segundos (1800 por omissão) e
  **não há refresh token nesta fase** — ao expirar, devolver ao login
  (pedir um novo código).
- Nenhum ecrã autenticado (`/me`, coberturas, etc.) existe ainda para
  consumir depois do login — construir só quando a Fase 1 do backend
  estiver pronta (ver `ROADMAP_PORTAL_CLIENTE.md`).

---

## Transversal (aplica-se a todos os épicos acima)

- **Tipos gerados**: `npm run api:generate:offline` (ART-006) e
  `api:generate:backend` devem correr sempre que um endpoint novo for
  adicionado no backend — nunca escrever tipos TypeScript à mão para um
  endpoint que o gerador já cobre. O Portal do Cliente não está em
  ART-006 (é um contrato novo e isolado, ver `ROADMAP_PORTAL_CLIENTE.md`)
  — os seus tipos ficam manuais ou num schema próprio, a definir por
  quem construir o Portal.
- **Testes**: cada componente novo precisa de pelo menos um teste de
  comportamento (mostrar/esconder por estado/decisão), seguindo o
  padrão já usado em `src/tests/`.
- **Sessão do backoffice**: inalterada — todos os ecrãs de staff
  continuam a usar o mesmo `httpClient` autenticado de sempre; nada
  neste documento pede alterações de autenticação ao backoffice.

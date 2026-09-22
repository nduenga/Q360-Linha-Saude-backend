# Plano de Frontend — o que falta construir (2026-09-22)

**Só isto: uma lista do que fazer.** Para o contrato completo de cada
endpoint (campos, tipos, erros), usa o OpenAPI já existente
(`npm run api:generate:offline`/`api:generate`) — não repetido aqui.
Racional de negócio e Open Decisions ficam em
`ROADMAP_ANGOLA_CUSTOMIZATION.md`/`ROADMAP_PORTAL_CLIENTE.md`.

---

## Já feito — não mexer

Confirmado directamente no código do frontend (`Q360-Linha-Sa-de-frontend`):
- Login (Auth0), `roles`/`permissions` via `GET /api/v1/me`.
- Produtos, Planos, Coberturas, Proponentes/Membros, Pricing, Nova
  Cotação, Underwriting/Revisão, Auditoria.
- Busca de elegibilidade por número de apólice (Épico 4).
- Editar/Remover/Retirar Rating Tables, Pricing Parameter Sets, Rule
  Versions, Document Templates (Épico 6).

---

## 1. Produtos — remover acção obsoleta

O backend já cria e publica sozinho a próxima versão do produto quando
se edita o produto (herda planos/coberturas reais). Isto torna
desnecessário:
- [ ] Remover o botão "Criar versão" (`ProductDetailPage`, função
      `createProductVersion`) — deixa de haver essa acção manual.
- [ ] Confirmar que nenhum formulário de produto/versão continua a pedir
      "Data de término" (o backend já não aceita esse campo).

## 2. QuoteSummaryPage — corrigir bug real

- [ ] A lista de membros da cotação só sobrevive via `location.state` do
      router — perde-se com F5 ou link directo. Chamar
      `GET /api/v1/quotes/{id}/members` ao montar a página e usar isso
      como fonte de verdade.

## 3. Pricing — Épico 5 (100% frontend, sem depender de backend novo)

Em `PricingConfigPanel.tsx`:
- [ ] Paginação real (hoje pede `size=200` fixo e ignora `page`).
- [ ] Reaproveitar o `statusLabel` map já usado em `ProductPage` para
      DRAFT/PUBLISHED/RETIRED.
- [ ] Substituir literais mágicos (`priority: -1`, `'BASE_PREMIUM'`,
      `'ADMIN_ADJUSTMENT'`) por constantes nomeadas.
- [ ] Vista de histórico das configurações (hoje só lista plana).

## 4. Motor de Elegibilidade — Fase A (novo, backend pronto)

`POST /api/v1/eligibility/evaluate` devolve agora 3 decisões novas.
- [ ] Actualizar o mapa de cores/labels de `decision` para as 8 opções:

  | `decision` | Cor | Nunca mostrar como |
  |---|---|---|
  | `ELIGIBLE` | Verde — "Elegível" | — |
  | `ELIGIBLE_WITH_LOADING` | Verde, com nota do agravamento | "Rejeitado" |
  | `WARNING` / `REFERRAL` | Amarelo | — |
  | `PENDING_DOCUMENT` | Amarelo — "Falta um documento" | "Rejeitado" |
  | `PENDING_MEDICAL_BOARD` | Amarelo — "Em análise" | "Rejeitado" |
  | `HARD_STOP` | Vermelho — "Não Elegível" | — (o único vermelho) |
  | `CONFIG_ERROR` | Nunca mostrado ao cliente final | — |

- [ ] Mostrar sempre `messages[].message` (já vem em português,
      amigável), nunca `messages[].code`.
- [ ] Opcional: um checklist para marcar `context.angola` (booleanos —
      certificado de matrícula, homologação de união de facto, prova de
      coabitação/dependência, doença preexistente, portabilidade) antes
      de calcular elegibilidade de um CHILD/SPOUSE/ASCENDANT. Sem isto o
      endpoint continua a funcionar como hoje — não bloqueante.

## 5. Portal do Cliente — Fase 0 (aplicação nova, do zero)

Não existe **nada** disto no frontend hoje. Novo módulo/rota,
completamente isolado do backoffice.

- [ ] Cliente HTTP novo e separado (nunca o `httpClient.ts`/Auth0 do
      backoffice) — este portal usa um token diferente, assinado com
      outra chave, para outro tipo de utilizador.
- [ ] Sessão própria (`sessionStorage` com chave distinta), sem
      `CurrentUserContext`/`AppShell` do backoffice.
- [ ] Ecrã 1 — pedir acesso: formulário com número de apólice, número de
      documento (BI/NIF) e email → `POST /api/v1/customer-portal/{tenantId}/auth/request-access`.
      Responde sempre `202` vazio, exista ou não correspondência — o
      ecrã mostra sempre a mesma mensagem de sucesso e avança sempre
      para o Ecrã 2, nunca inferir erro a partir da resposta.
- [ ] Ecrã 2 — confirmar código: os mesmos 3 campos + código de 6
      dígitos → `POST /api/v1/customer-portal/{tenantId}/auth/verify-otp`.
      Sucesso devolve `{accessToken, tokenType, expiresIn}` — guardar e
      usar no cliente HTTP próprio. Erros: `401` código/dados errados,
      `423` conta bloqueada (5 tentativas falhadas), `429` demasiadas
      tentativas — mostrar mensagem de erro correspondente.
- [ ] `{tenantId}` vem de configuração do build/deployment do portal
      (env var), nunca digitado pelo utilizador.
- [ ] Token expira em `expiresIn` segundos (1800 por omissão), sem
      refresh — ao expirar, voltar ao Ecrã 1.
Estes 2 endpoints são novos e isolados (não estão no OpenAPI do
backoffice) — é este o único contrato que precisa de ser lido aqui em
vez de gerado.

## 6. Portal do Cliente — Fase 1 (novo, backend pronto — os ecrãs depois do login)

Autenticado com o `accessToken` da Fase 0 (mesmo cliente HTTP isolado).
Nenhum destes 3 aceita nem precisa de `proposerId`/`planId`/etc. no
pedido — tudo resolvido no servidor a partir do token.

- [ ] Ecrã "A minha apólice": `GET /api/v1/customer-portal/me` → lista
      de apólices do cliente, cada uma já com `quote` (status,
      quoteNumber, datas), `product`, `productVersion`, `plan`
      embutidos. Se vazia, mostrar estado vazio (cliente ainda sem
      apólice associada).
- [ ] Secção "Coberturas": `GET /api/v1/customer-portal/coverage?quoteNumber=<numero>`
      → `{quoteNumber, benefits: [{id, planId, benefit: {code, name,
      category, description}, configurationJson}]}`. `404` se o
      `quoteNumber` não pertencer ao cliente autenticado.
- [ ] Secção/acção "Ver elegibilidade": `POST /api/v1/customer-portal/eligibility`
      `{quoteNumber, memberId?}` → `{quoteNumber, results: [{memberId,
      relationshipCode, decision, messages}]}`. Sem `memberId` avalia
      todos os membros da apólice; `decision`/`messages` seguem
      exactamente a mesma tabela de cores da secção 4 (Motor de
      Elegibilidade). `404` se `quoteNumber`/`memberId` não pertencerem
      ao cliente.
- [ ] Qualquer resposta `401` de um destes 3 (token expirado) →
      redireccionar ao Ecrã 1 do login (Fase 0), pedir novo código.

---

## Bloqueado — não construir

- **Dashboard**: métricas/fila continuam mock — não existe endpoint de
  métricas agregadas no backend.
- **Administração → Utilizadores/Roles/Parâmetros**: continuam mock —
  identidade é federada via Auth0, não há tabela de utilizadores para
  gerir por CRUD.

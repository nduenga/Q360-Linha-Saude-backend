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
- [ ] Não construir nenhum ecrã depois do login (coberturas, "a minha
      apólice", etc.) — isso é a Fase 1, o backend ainda não a tem.

Estes 2 endpoints são novos e isolados (não estão no OpenAPI do
backoffice) — é este o único contrato que precisa de ser lido aqui em
vez de gerado.

---

## Bloqueado — não construir

- **Dashboard**: métricas/fila continuam mock — não existe endpoint de
  métricas agregadas no backend.
- **Administração → Utilizadores/Roles/Parâmetros**: continuam mock —
  identidade é federada via Auth0, não há tabela de utilizadores para
  gerir por CRUD.

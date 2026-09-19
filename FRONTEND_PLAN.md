# Plano de Frontend — Customização Angola

Complementa `ROADMAP_ANGOLA_CUSTOMIZATION.md` (que cobre backend+frontend a
alto nível) com o detalhe **específico do frontend**: que ficheiros/
componentes mudam, por que ordem, e o que cada um precisa do backend.
Repositório: `Q360-Linha-Sa-de-frontend` (separado do backend).

---

## 0 — Ligação à autenticação real (bloqueia tudo o resto)

Estado actual confirmado em código:
- `src/auth/LoginPage.tsx` — UI de login real e completa, mas chama
  `authenticateWithMock()` (`src/auth/services/mockAuth.ts`), 100% cliente,
  sem contactar o backend.
- `src/app/providers.tsx` — `CurrentUserProvider` é só `useState` em
  memória; `login(user)` aceita directamente o objecto que `LoginPage`
  lhe dá. Sem persistência, sem chamada ao backend.
- `src/dev/devAuth.ts` — bridge de teste manual que injecta um token
  estático de `VITE_DEV_BEARER_TOKEN` (gerado à mão via
  `manage.py issue_dev_token`); não é um login, é um atalho de developer.
- Backend já expõe `GET /api/v1/me` (retorna `actorId`, `tenantId`,
  `roles`, `permissions` reais resolvidos da matriz DOC-001 §18) — mas
  **não existe nenhum endpoint de login** (o backend é um Resource Server
  OAuth2/OIDC puro; validar um JWT já emitido, nunca emitir um a partir de
  email/password). OD-009 (IdP real) continua por resolver.

### Plano

1. **Backend**: endpoint pragmático de login para desenvolvimento/demo —
   `POST /api/v1/auth/dev-login` (nome sujeito a confirmação), aceita
   `email`+`password`, valida contra os mesmos dois utilizadores demo já
   codificados no frontend (`admin@q360.co.ao` / `subscritor@q360.co.ao`),
   emite um JWT real assinado com `OIDC_STATIC_VERIFICATION_KEY` (mesmo
   mecanismo de `issue_dev_token`, só que servido por HTTP em vez de CLI).
   Documentado explicitamente como **não sendo a resolução de OD-009** —
   um IdP real substituirá isto por um fluxo de redirect (Authorization
   Code), não por um POST directo de password.
2. **Frontend**: `LoginPage.tsx` passa a chamar esse endpoint via
   `httpClient` em vez de `authenticateWithMock`.
3. **Frontend**: após o login, chamar `GET /api/v1/me` e usar a resposta
   real (roles/permissions) para preencher `CurrentUserContext` — deixa de
   haver arrays `ADMIN_PERMISSIONS`/`SUBSCRIBER_PERMISSIONS` hardcoded em
   `mockAuth.ts`.
4. **Frontend**: guardar o token em `sessionStorage` (limpo ao fechar o
   separador — mais seguro que `localStorage` para uma demo, e evita
   reconstruir infra de cookies/sessão no Django, que hoje nem tem
   `SessionMiddleware` instalado) e ligá-lo a
   `setAccessTokenProvider` (já existe em `httpClient.ts`).
5. **Frontend**: `logout()` limpa o token e o `sessionStorage`.
6. Manter `devAuth.ts` intocado (continua útil para debugging manual via
   `.env`), mas deixa de ser o único caminho — o login real passa a
   funcionar no browser sem configuração de `.env`.

### Depois disto

Todos os ecrãs já construídos (Produtos, Pricing, Elegibilidade,
Subscrição, Auditoria, Clientes) continuam a usar o mesmo `httpClient` —
não precisam de nenhuma alteração própria, ficam automaticamente ligados
à sessão real assim que o token real está a ser enviado.

---

## Épico 1 — Coberturas (frontend)

Novos ficheiros:
- `src/domains/product/services/benefitApi.ts` — `listBenefits()`
  (`GET /benefits`), `setPlanBenefits(planId, benefitIds)`.
- `src/domains/product/types/benefit.ts` — `Benefit { id, code, name,
  category: 'BASE' | 'COMPLEMENTARY', description, status }`.

Alterações:
- `ProductPage.tsx` / ecrã de plano: nova secção "Coberturas":
  - Bloco fixo, não removível, com as 3 `BASE` (buscar via `listBenefits`
    filtrado por `category=BASE`, mostrar sempre, sem checkbox).
  - Grid de **cards seleccionáveis** para as 8 `COMPLEMENTARY` (toggle
    on/off por card — sem pré-selecção), reaproveitando o padrão visual
    de cards já usado nesta plataforma (ex. `SectionPanel`/componentes
    existentes) em vez de inventar um novo componente do zero.

---

## Épico 2 — Versionamento automático (frontend)

- Remover o botão "Criar versão" de `ProductDetailPage`
  (`c:\...\ProductPage.tsx` — o botão actual em torno da linha ~327).
- `EditProductForm`/`updateMutation` já dispara `createPublishedVersionWithBasicPlan`
  hoje — substituir por uma chamada que herda os planos/coberturas reais
  da versão anterior (o backend passa a devolver isso pronto; o frontend
  só precisa de deixar de inventar o "Básico" hardcoded).

---

## Épico 3 — Sem data de término (frontend)

- Remover o campo "Data de término" de todos os formulários de produto/
  versão (`ProductPage.tsx`, ecrã de "Criar versão" — que desaparece de
  qualquer forma no Épico 2).

---

## Épico 4 — Elegibilidade por apólice (frontend)

- `EligibilityPage.tsx`: substituir os 6 selects sequenciais (Produto →
  Versão → Plano → Data → Proponente → Membro) por:
  - Um campo "Número da apólice/cotação" + botão "Procurar".
  - Ao encontrar, pré-preencher tudo (mostrar os campos preenchidos,
    read-only, com opção "Alterar" para o fluxo manual antigo como
    fallback).

---

## Épico 5 — Pricing mais simples (frontend)

Em `PricingConfigPanel.tsx`:
- Reaproveitar o `statusLabel` map já usado no `ProductPage` para
  DRAFT/PUBLISHED.
- Substituir os literais mágicos (`priority: -1`, `'BASE_PREMIUM'`,
  `'ADMIN_ADJUSTMENT'`) por constantes nomeadas no topo do ficheiro.
- Adicionar paginação real (o backend já pagina; hoje o frontend pede
  `size=200` fixo e ignora o resto).

---

## Épico 6 — CRUD de configurações (frontend)

Em `PricingConfigPanel.tsx` e no ecrã de Document Templates:
- Botão "Editar" por item — só visível quando `status=DRAFT`, abre o
  mesmo formulário de criação pré-preenchido, `PATCH` em vez de `POST`.
- Botão "Remover" — só visível quando `status=DRAFT`.
- Botão "Retirar" — só visível quando `status=PUBLISHED`.

---

## Portal do Cliente (frontend, roadmap à parte)

Aplicação/rota nova, separada do backoffice actual (autenticação e RBAC
próprios — nunca reaproveitar o `CurrentUserContext` de staff):
- Fase 1: ecrã único "Consultar a minha elegibilidade" (login de cliente
  + número de apólice).
- Fase 2: ecrã de "A minha cobertura" + download da proposta.
- Fase 3: formulário de pedido de adesão.

---

## Transversal

- **Tipos gerados**: `npm run api:generate:offline` (ART-006) e
  `api:generate:backend` (schema.yml, já configurado) devem correr sempre
  que um endpoint novo destes épicos for adicionado no backend — nunca
  escrever tipos TypeScript à mão para um endpoint novo se o gerador já
  cobre o schema.
- **Testes**: cada componente novo (cards de cobertura, lookup de
  apólice, botões CRUD condicionais por estado) precisa de pelo menos um
  teste de comportamento (mostrar/esconder por estado/categoria), seguindo
  o padrão já usado em `src/tests/`.

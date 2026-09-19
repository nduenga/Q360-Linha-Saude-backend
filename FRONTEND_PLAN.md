# Plano de Frontend — Customização Angola (documento de handoff)

**Para quem vai construir o frontend destes épicos.** A partir de
2026-09-19, a construção feita por este agente/sessão é **só backend** —
o frontend de cada épico fica para outra pessoa implementar, usando este
documento como plano. Complementa `ROADMAP_ANGOLA_CUSTOMIZATION.md`
(estado actual, racional de negócio, Open Decisions) e
`CHECKLIST_CUSTOMIZACAO.md` (vista rápida de progresso) com o detalhe
**específico do frontend**: que ficheiros/componentes mudam, por que
ordem, e o que cada um precisa do backend.

**Repositório:** `Q360-Linha-Sa-de-frontend` (separado do backend, branch
`main`). **Backend:** repositório raiz `Quote - Saúde/backend`, branch
`fabio`.

Cada secção abaixo indica o estado: **✅ Backend pronto** (endpoints já
existem e estão testados — o frontend pode implementar já) ou
**⏳ Backend por construir** (aguarda esta sessão terminar esse épico antes
de a UI fazer sentido).

---

## Épico 0 — Autenticação real ✅ Backend pronto — ✅ Frontend também já feito

Este foi implementado nos dois lados antes da directiva "só backend" —
não há nada para o frontend fazer aqui, é só contexto para quem for mexer
no código de autenticação a seguir:

- `POST /api/v1/auth/dev-login` (backend, pragmático — nunca a resolução
  de OD-009/IdP real) aceita `email`+`password` dos dois utilizadores demo
  (`admin@q360.co.ao` / `subscritor@q360.co.ao`) e devolve um JWT real.
- `src/auth/LoginPage.tsx` chama esse endpoint (`src/auth/services/authApi.ts`)
  em vez do antigo `authenticateWithMock`.
- `src/auth/session.ts` guarda o token em `sessionStorage` e liga-o a
  `setAccessTokenProvider` (`httpClient.ts`).
- `src/app/providers.tsx` reidrata a sessão a partir de `GET /api/v1/me`
  ao montar a app, nunca de dados cacheados.
- `UserRole` (`src/types/index.ts`) foi corrigido para os valores reais do
  backend (`ADMIN`/`PRODUCT_CONFIGURATOR`/`SUBSCRIBER`/`APPROVER`/
  `AUDITOR`) — os antigos `CONFIG`/`SUBSCRITOR`/`SUPERVISOR` não existiam
  no backend.

---

## Épico 1 — Coberturas ✅ Backend pronto — ✅ Frontend também já feito

Também implementado nos dois lados antes da directiva. Referência para
quem for estender isto (ex.: editar `configuration_json` por cobertura):

- `GET /api/v1/benefits?category=BASE|COMPLEMENTARY` — catálogo das 11
  coberturas reais (ver ROADMAP Épico 1 para a lista completa).
- `GET/POST /api/v1/plans/{planId}/benefits`, `DELETE
  /api/v1/plans/{planId}/benefits/{benefitId}` (recusa remover uma BASE).
- `src/domains/product/services/benefitApi.ts`,
  `src/domains/product/types/benefit.ts`,
  `src/domains/product/components/PlanBenefitsSection.tsx` — secção no
  ecrã de plano com as 3 BASE fixas + grid de cards seleccionáveis para as
  8 COMPLEMENTARY.

**Por fazer (não bloqueante):** UI para editar `configuration_json` por
cobertura (limites, franquias) quando OD-ANGOLA-002 for respondida.

---

## Épico 2 — Versionamento automático do produto ⏳ Backend por construir

Estado actual do frontend (antes desta mudança):
- `ProductPage.tsx`: editar nome/descrição do produto
  (`EditProductForm`/`updateMutation`) dispara, hoje,
  `createPublishedVersionWithBasicPlan` — cria e publica uma versão nova
  com um plano "Básico" **inventado no frontend**, ignorando os planos
  reais já existentes.
- Existe também um botão separado "Criar versão" (`ProductDetailPage`,
  função `createProductVersion`) com formulário manual de datas.

### O que fazer quando o backend estiver pronto
- Remover o botão "Criar versão" — deixa de haver essa acção distinta.
- `EditProductForm`/`updateMutation`: já não inventa um "Básico" — chama
  o novo endpoint/fluxo do backend que cria a próxima versão herdando os
  planos/coberturas reais da versão anterior.
- Confirmar com o backend (OD-ANGOLA-003) se a nova versão fica
  `PUBLISHED` de imediato ou `DRAFT` à espera de uma acção "Publicar
  alterações" — isso muda se a UI precisa de um botão extra de publicar
  depois de editar.

---

## Épico 3 — Produtos sem data de término ⏳ Backend por construir

- Remover o campo "Data de término" de todos os formulários de produto/
  versão em `ProductPage.tsx` (o formulário de "Criar versão" desaparece
  de qualquer forma no Épico 2, mas confirmar que nenhum outro sítio pede
  `effectiveTo`).

---

## Épico 4 — Elegibilidade por número de apólice ⏳ Backend por construir

Estado actual: `EligibilityPage.tsx` tem 6 selects sequenciais (Produto →
Versão → Plano → Data → Proponente → Membro), todos preenchidos à mão.

### O que fazer quando o backend estiver pronto
- Substituir os 6 selects por: campo "Número da apólice/cotação" + botão
  "Procurar".
- Ao encontrar, pré-preencher tudo (mostrar os campos preenchidos,
  read-only, com opção "Alterar" para o fluxo manual antigo como
  fallback caso o lookup falhe ou o utilizador precise de corrigir algo).
- Depende de OD-ANGOLA-005 (apólice = `Quote.quoteNumber` ou entidade nova)
  estar resolvida no backend antes de desenhar o pedido exacto.

---

## Épico 5 — Pricing mais simples ⏳ Backend não bloqueia (é só frontend)

Este épico é 100% frontend — não depende de nenhum endpoint novo. Em
`PricingConfigPanel.tsx`:
- Reaproveitar o `statusLabel` map já usado no `ProductPage` para
  DRAFT/PUBLISHED (hoje mostra a string crua).
- Substituir os literais mágicos (`priority: -1`, `'BASE_PREMIUM'`,
  `'ADMIN_ADJUSTMENT'`) por constantes nomeadas no topo do ficheiro.
- Adicionar paginação real (o backend já pagina; hoje o frontend pede
  `size=200` fixo e ignora o resto).
- Vista de histórico das configurações existentes (hoje só há uma lista
  plana).

---

## Épico 6 — CRUD de Rating Tables / Parameter Sets / Rule Versions / Document Templates ⏳ Backend por construir

Em `PricingConfigPanel.tsx` e no ecrã de Document Templates, quando os
novos verbos `PATCH`/`DELETE`/`retire` existirem no backend:
- Botão "Editar" por item — só visível quando `status=DRAFT`, abre o
  mesmo formulário de criação pré-preenchido, `PATCH` em vez de `POST`.
- Botão "Remover" — só visível quando `status=DRAFT`.
- Botão "Retirar" — só visível quando `status=PUBLISHED` (nunca apaga a
  linha, só marca `RETIRED` — ver OD-ANGOLA-006 no roadmap).

---

## Portal do Cliente (frontend, roadmap à parte, prazo mais longo)

Aplicação/rota nova, separada do backoffice actual (autenticação e RBAC
próprios — nunca reaproveitar o `CurrentUserContext` de staff):
- Fase 1: ecrã único "Consultar a minha elegibilidade" (login de cliente
  + número de apólice).
- Fase 2: ecrã de "A minha cobertura" + download da proposta.
- Fase 3: formulário de pedido de adesão.

---

## Transversal (aplica-se a todos os épicos acima)

- **Tipos gerados**: `npm run api:generate:offline` (ART-006) e
  `api:generate:backend` (schema.yml, já configurado) devem correr sempre
  que um endpoint novo destes épicos for adicionado no backend — nunca
  escrever tipos TypeScript à mão para um endpoint novo se o gerador já
  cobre o schema.
- **Testes**: cada componente novo (cards, lookup de apólice, botões CRUD
  condicionais por estado) precisa de pelo menos um teste de
  comportamento (mostrar/esconder por estado/categoria), seguindo o
  padrão já usado em `src/tests/`.
- **Sessão real**: desde o Épico 0, todos os ecrãs já usam o mesmo
  `httpClient` autenticado — nenhuma alteração de autenticação é
  necessária ecrã a ecrã, só o consumo dos endpoints novos de cada épico.

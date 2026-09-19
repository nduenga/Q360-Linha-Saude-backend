# Checklist — Customização Q360 para Angola

Ver `ROADMAP_ANGOLA_CUSTOMIZATION.md` para o detalhe/racional de cada item
(estado actual, tarefas backend/frontend, Open Decisions). Este ficheiro é
só a vista rápida de progresso — actualizado à medida que cada item fecha.

**Ordem de trabalho acordada (2026-09-19):** ligar autenticação → Épico 1.

---

## 0 — Ligação Backend ↔ Autenticação do frontend existente
- [ ] Endpoint de login pragmático (email/password → JWT real, mesmo
      mecanismo de `manage.py issue_dev_token`, nunca a resolução final de
      OD-009/IdP real)
- [ ] Frontend: `LoginPage.tsx` chama o backend real em vez de
      `authenticateWithMock`
- [ ] Frontend: `AuthProvider`/`useCurrentUser` populado a partir de
      `GET /api/v1/me` (já existe no backend), não de arrays hardcoded
- [ ] Token guardado e enviado pelo `httpClient` em todos os pedidos
      (via `setAccessTokenProvider`, já existe)
- [ ] Confirmar que todos os ecrãs já construídos (Produtos, Pricing,
      Elegibilidade, Subscrição, Auditoria) continuam a funcionar com a
      sessão real

## 1 — Catálogo de coberturas do mercado angolano
- [ ] Seed das 11 coberturas (3 BASE + 8 COMPLEMENTARY) — dados reais do
      guia ARSEG, ver roadmap
- [ ] `GET /api/v1/benefits` (catálogo)
- [ ] Associação de coberturas a planos (BASE automático, COMPLEMENTARY
      opcional)
- [ ] Validação: plano não publica sem as 3 BASE
- [ ] UI: 3 BASE sempre presentes e bloqueadas + COMPLEMENTARY como cards
      seleccionáveis (nunca pré-marcados)
- [ ] Confirmar OD-ANGOLA-002 (limites/franquias por cobertura) e
      OD-ANGOLA-007 (codes propostos) antes de fixar em produção

## 2 — Versionamento automático do produto
- [ ] OD-ANGOLA-003: nova versão publica automaticamente ou fica DRAFT?
- [ ] OD-ANGOLA-004: confirmar que não quebra cotações em curso
- [ ] Backend: editar produto cria sempre a próxima versão (herda planos/
      coberturas reais, nunca hardcoded)
- [ ] Frontend: remover botão "Criar versão"

## 3 — Produtos sem data de término
- [ ] Remover `effectiveTo` do serializer de criação de versão
- [ ] Remover campo "Data de término" da UI

## 4 — Elegibilidade por número de apólice
- [ ] OD-ANGOLA-005: apólice = `Quote.quoteNumber` aprovado, ou entidade
      `Policy` nova?
- [ ] Endpoint de lookup por número
- [ ] UI: campo único + "Procurar" substitui os 6 selects

## 5 — Simplificação do Pricing
- [ ] Traduzir estados DRAFT/PUBLISHED
- [ ] Extrair valores mágicos (`priority: -1`, `BASE_PREMIUM`,
      `ADMIN_ADJUSTMENT`)
- [ ] Vista de histórico das configurações
- [ ] Paginação real

## 6 — CRUD de Rating Tables / Parameter Sets / Rule Versions / Templates
- [ ] OD-ANGOLA-006: confirmar "remover" em PUBLISHED = retirar, nunca
      apagar
- [ ] `PATCH` (só DRAFT) nos 4 recursos
- [ ] `DELETE` (só DRAFT) nos 4 recursos
- [ ] Acção "Retirar" para PUBLISHED
- [ ] UI: Editar/Remover (DRAFT), Retirar (PUBLISHED)

## Portal do Cliente (roadmap à parte, prazo mais longo)
- [ ] Fase 1: autenticação de cliente final + consulta da própria
      elegibilidade
- [ ] Fase 2: self-service (ver cobertura, descarregar proposta)
- [ ] Fase 3: submissão de pedidos pelo cliente

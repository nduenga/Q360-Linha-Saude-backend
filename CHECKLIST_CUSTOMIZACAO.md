# Checklist — Customização Q360 para Angola

Ver `ROADMAP_ANGOLA_CUSTOMIZATION.md` para o detalhe/racional de cada item
e `FRONTEND_PLAN.md` para o plano detalhado de handoff do frontend. Este
ficheiro é a vista rápida de progresso de **todos os épicos** —
actualizado à medida que cada item fecha.

**Divisão de responsabilidade (a partir de 2026-09-19):** esta sessão
constrói **só o backend** de cada épico. O frontend fica para outra
pessoa, usando `FRONTEND_PLAN.md` como plano — os itens de frontend abaixo
ficam marcados `(frontend — outra pessoa)` e não são construídos aqui.

---

## 0 — Autenticação real ✅ concluído (2026-09-19)
- [x] Backend: `POST /api/v1/auth/dev-login`
- [x] *(frontend — outra pessoa, já feito antes desta divisão)* `LoginPage`,
      `session.ts`, `providers.tsx`, `UserRole` corrigido
- [x] Verificado E2E contra o servidor real

## 1 — Catálogo de coberturas do mercado angolano ✅ concluído (2026-09-19)
- [x] Backend: seed das 11 coberturas, `GET /benefits`,
      `GET/POST/DELETE /plans/{id}/benefits`, validação de publicação
- [x] *(frontend — outra pessoa, já feito antes desta divisão)*
      `PlanBenefitsSection`, cards seleccionáveis
- [x] Verificado E2E contra o servidor real
- [ ] Em aberto: OD-ANGOLA-002 (limites/franquias), OD-ANGOLA-007 (codes)

## 2 — Versionamento automático do produto ✅ backend concluído (2026-09-19)
- [x] OD-ANGOLA-003 resolvida: auto-publica (sem passo DRAFT manual)
- [x] OD-ANGOLA-004 resolvida e testada: não quebra cotações em curso
- [x] **Backend**: editar produto cria sempre a próxima versão (herda
      planos/coberturas reais, nunca hardcoded) — `create_next_version()`
- [ ] *(frontend — outra pessoa)* remover botão "Criar versão"

## 3 — Produtos sem data de término ✅ backend concluído (2026-09-19)
- [x] **Backend**: `effectiveTo` removido do serializer de criação de versão
- [x] Efeito colateral tratado: GT-ELIG-002 (golden test) adaptado —
      exercita `evaluate()` directamente, já não via API (ver roadmap)
- [ ] *(frontend — outra pessoa)* remover campo "Data de término" da UI

## 4 — Elegibilidade por número de apólice ✅ backend concluído (2026-09-19)
- [x] OD-ANGOLA-005 resolvida: apólice = `Quote.quoteNumber` (aprovação)
- [x] **Backend**: `quote_number` atribuído em APPROVE (numbering_service)
- [x] **Backend**: `GET /quotes?quoteNumber=` resolve o contexto completo
- [ ] *(frontend — outra pessoa)* campo único + "Procurar" substitui os
      6 selects

## 5 — Simplificação do Pricing
- [ ] *(100% frontend — outra pessoa)* traduzir estados, extrair valores
      mágicos, histórico de configurações, paginação real — sem trabalho
      de backend associado

## 6 — CRUD de Rating Tables / Parameter Sets / Rule Versions / Templates ✅ backend concluído (2026-09-21)
- [x] OD-ANGOLA-006 resolvida: "remover" em PUBLISHED = retirar, nunca
      apagar
- [x] **Backend**: `PATCH` (só DRAFT) nos 4 recursos
- [x] **Backend**: `DELETE` (só DRAFT) nos 4 recursos — corrigido bug real
      de FK (`rating_factor`/`pricing_parameter` sem `ON DELETE CASCADE`)
      apanhado pelos próprios testes novos
- [x] **Backend**: acção "Retirar" para PUBLISHED (dispatcher partilhado
      para 3 recursos + endpoint dedicado para Document Template)
- [x] Testes dedicados (24 casos): PATCH/DELETE em DRAFT, rejeição em
      PUBLISHED, retire válido e retire de DRAFT rejeitado — para os 4
      recursos
- [ ] *(frontend — outra pessoa)* botões Editar/Remover (DRAFT), Retirar
      (PUBLISHED)

## Portal do Cliente (roadmap à parte, prazo mais longo)
- [ ] Fase 1: autenticação de cliente final + consulta da própria
      elegibilidade
- [ ] Fase 2: self-service (ver cobertura, descarregar proposta)
- [ ] Fase 3: submissão de pedidos pelo cliente

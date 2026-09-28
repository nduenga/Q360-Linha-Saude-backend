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

## 2 — Versionamento automático do produto ⚠️ substituído (2026-09-26, ver `ROADMAP_APOLICES.md` Fase 1)
- [x] OD-ANGOLA-003 resolvida: auto-publica (sem passo DRAFT manual)
- [x] OD-ANGOLA-004 resolvida e testada: não quebra cotações em curso
- [x] **Backend**: editar produto cria sempre a próxima versão (herda
      planos/coberturas reais, nunca hardcoded) — `create_next_version()`
- [ ] *(frontend — outra pessoa)* remover botão "Criar versão"

## 3 — Produtos sem data de término ⚠️ substituído (2026-09-26, sem `ProductVersion`, ver `ROADMAP_APOLICES.md` Fase 1)
- [x] **Backend**: `effectiveTo` removido do serializer de criação de versão
- [x] Efeito colateral tratado: GT-ELIG-002 (golden test) adaptado —
      exercita `evaluate()` directamente, já não via API (ver roadmap)
- [ ] *(frontend — outra pessoa)* remover campo "Data de término" da UI

## 4 — Elegibilidade por número de apólice ⚠️ substituído (2026-09-26, apólice = `Policy` real, ver `ROADMAP_APOLICES.md`)
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

## 7 — Resolução das 8 decisões do Product Owner (2026-09-21)
- [ ] OD-ANGOLA-008 (Auth0): backend pronto, guia escrito (`AUTH0_SETUP.md`),
      falta o Product Owner criar a conta Auth0 + ligar o frontend
- [x] OD-ANGOLA-009: nova cotação exige versão PUBLISHED do produto
- [x] OD-ANGOLA-010: catálogo real de relações (+ pais/avós), endpoint
      `GET /relationship-codes`, validação em criar/editar membro
- [x] OD-ANGOLA-011: importação em massa aceita Excel (preferencial) e
      CSV, com ETL de valores nulos/vazios
- [x] OD-ANGOLA-012 (motor de elegibilidade): desenho entregue
      (`MOTOR_ELEGIBILIDADE.md`) e **Fase A implementada (2026-09-22)** —
      regras por categoria (CHILD/SPOUSE/ASCENDANT), overrides
      corporativos, carência informativa, preexistências
      (agravamento/junta médica), 3 novas decisões + mensagens amigãveis.
      Fases B (armazenamento de documentos) e C (validação NIF/vínculo
      laboral) continuam bloqueadas por decisão de produto/integração
      externa inexistente — ver `MOTOR_ELEGIBILIDADE.md`.
- [x] OD-ANGOLA-013: AOA + arredondamento promovidos a política oficial
- [x] OD-ANGOLA-014: regras de preço configuráveis — confirmado já
      resolvido, limitação conhecida documentada
- [x] OD-ANGOLA-015: dupla aprovação em regras — confirmado manter como
      está

## Portal do Cliente (roadmap à parte, prazo mais longo) — ver `ROADMAP_PORTAL_CLIENTE.md`
- [x] Fase 0 (Fundação técnica) ✅ backend concluído (2026-09-22) —
      OD-PORTAL-001..004 resolvidas (email OTP; `customer_account`
      muitos-para-um via NIF; lockout 5/30min; novo app Django
      `apps.customer_portal` no mesmo backend). Novo `actor_type=CUSTOMER`,
      token de sessão isolado do OIDC staff, scoping por proposer
      fail-closed, `ck_audit_actor_type` alargado, rate limiting dedicado,
      namespace `/api/v1/customer-portal/...`.
      *(frontend — outra pessoa)* ver `FRONTEND_PLAN.md` secção Portal do
      Cliente para o contrato exacto dos 2 endpoints já disponíveis.
- [x] Fase 1 ✅ backend concluído (2026-09-22) — `GET /customer-portal/me`,
      `GET /customer-portal/coverage`, `POST /customer-portal/eligibility`,
      todos scoped ao proposer do `customer_account` autenticado, nunca a
      IDs vindos do pedido. *(frontend — outra pessoa)* ver
      `FRONTEND_PLAN.md`.
- [ ] Fase 2: self-service (ver cobertura, descarregar proposta)
- [ ] Fase 3: submissão de pedidos pelo cliente

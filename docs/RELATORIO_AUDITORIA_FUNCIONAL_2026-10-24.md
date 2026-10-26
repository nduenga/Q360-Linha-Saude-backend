# Auditoria funcional e de UX — Q360 Linha Saúde (24/10/2026) — FINALIZADO

**Como foi feito.** Base de dados à parte (`q360_audit`), migrada e preenchida com `seed_full_database --allow-demo`. Backend em `:8077` e frontend (ramo `seth`) em `:5199`. Um robô Playwright entrou com cada perfil e percorreu todos os ecrãs (texto, pedidos HTTP com erro, erros de consola). Os fluxos de negócio foram executados pela API real: cotação → preço → submissão → quatro olhos → aprovação → emissão → pagamento → endosso de inclusão.

**Perfis testados:** administrador do tenant, gestor de subscrição, subscritor (2 contas), super-administrador da plataforma e cliente do portal (Ana Silva).

**Regra seguida:** só entra aqui o que foi visto a acontecer ou lido no código. Cada ponto diz como foi verificado: **[exec]** = visto a correr; **[código]** = lido no código, com ficheiro e linha.

---

## 1. Falhas reais (corrigir)

| # | Gravidade | Onde | O que acontece | Evidência |
|---|---|---|---|---|
| F1 | **Alta** | Dashboard (`GET /dashboard`) | As contagens por estado e a tendência estão erradas. O queryset tem `.order_by("-created_at")` e o Django junta o `created_at` ao `GROUP BY`. Resultado: aparece uma linha por cotação, cada uma com contagem 1, e o dicionário guarda só a última. O ecrã mostra «1 aprovada», «1 rejeitada/expirada» e «Conversão aprovada 40 %». Na base há 4 rejeitadas, e a conversão real é 35/47 = 74,47 % (é o número que a própria tabela «Conversão por canal» mostra no mesmo ecrã). A tendência mostra «1 criada em outubro» quando foram criadas 47. O mesmo erro afecta `subscriptions.byStatus` (apólices ordenadas por `-issued_at`). | [exec] `byStatus` = 5 estados × 1. A base tem DRAFT 4, BOUND 34, REJECTED 4, APPROVED 1, IN_REVIEW 4 · [código] `backend/apps/foundation/interfaces/views.py:91` (`_status_counts`), `:300`, `:302-305`, `:613`. Correcção: `queryset.order_by()` antes de `.values()` |
| F2 | **Alta** | Subscrição → fila de decisão | O ecrã só carrega a 1.ª página (20 de 43 tarefas) e calcula os indicadores sobre essas 20. Mostra «1 aberta» quando há 4: COT-5, COT-8 e COT-24 ficam **invisíveis** para quem decide. O comentário no código diz «Carrega TODA a fila», mas não carrega. | [exec] `GET /reviews` → `totalElements: 43`, `size: 20`; `?status=OPEN` → 4 · [código] `src/domains/underwriting/UnderwritingPage.tsx:47-60`, `services/underwritingApi.ts:11-13` |
| F3 | Média | Cotações (`updatedAt`) | O `updatedAt` não muda quando a cotação é submetida ou aprovada: fica sempre igual ao `createdAt`. Ordenações e filtros por «actualizado em» ficam enganadores. | [exec] COT-48: `updatedAt 10:29:30.519` depois de `submittedAt 10:29:31` e `approvedAt 10:29:32` |
| F4 | Média | Carência por cobertura | Se uma cobertura tiver `waitingDays = 0` (por exemplo urgências sem carência), o 0 é descartado e a cobertura recebe a carência genérica da regra (30 dias na demo). Não há forma de dizer «sem carência» só para uma cobertura. | [código] `backend/apps/policy/application/issuance_service.py:382` (`days > 0`) e `:416-419` (fallback) · [exec] na demo, `EMERGENCY` ficou com 30 dias de carência |
| F5 | Média | Seed (`seed_full_database`) | Termina com erro: gera o histórico de sinistralidade em `.csv`, mas a importação já só aceita `.xlsx`. O tenant de isolamento e o relatório final ficam por criar, e o ecrã de Sinistralidade fica sem dados. | [exec] `ClaimsImportError: Formato não suportado. Carregue o modelo Excel .xlsx.` · [código] `seed_full_database.py:731-749` vs `claims/application/import_service.py:56-82` |
| F6 | Média | Seed → dados contraditórios no portal | Para simular atrasos, o seed muda o vencimento mas deixa o período como está. O cliente vê a prestação n.º 2 (período 24/01/2027–23/04/2027) «em atraso» desde 14/10/2026, antes de a apólice começar (24/10/2026). Também vê a 1.ª prestação «paga em 23/10/2026», antes do início. | [exec] portal → APO-1 → Prestações · [código] `seed_full_database.py:663-666` |
| F7 | Média | Seed → emails reais | Os clientes de demonstração usam caixas de correio reais (`fabiongila@…`, `sethlussueki@…`). Os códigos de acesso e as notificações da demo podem chegar a pessoas reais. | [exec] saída do seed, linhas «CLIENTES COM/SEM CONTA» |
| F8 | Baixa | Seed → instrução errada | A saída manda configurar `NEXT_PUBLIC_CUSTOMER_PORTAL_TENANT_ID`, mas o frontend lê `VITE_CUSTOMER_PORTAL_TENANT_ID`. | [exec] saída do seed · [código] `src/vite-env.d.ts` |
| F9 | Baixa | Elegibilidade (staff) | O texto «Só cotações aprovadas têm número de cotação atribuído» é falso: o número é atribuído na criação (há rascunhos COT-36 e COT-37). | [código] `src/domains/eligibility/EligibilityPage.tsx:171` vs `quote/application/quote_service.py:330` |
| F10 | Baixa | Dados de pessoas seguras | `POST /members` aceita uma pessoa sem nome (201, `firstName`/`lastName` nulos) e ignora em silêncio campos desconhecidos (`fullName`, `gender`). O endosso e o PDF ficam com «name: null». | [exec] |

## 2. Contradições e coisas sem sentido

1. **Três números de conversão diferentes no mesmo dashboard**: 40 % (cartão), 63,64 %/77,78 % (por produto) e 74,47 % (por canal). A causa é a F1; corrigida a F1, os números batem certo. [exec]
2. **«Cotações na fila: 20»** soma tarefas já decididas (19). «Na fila» devia contar só as abertas e as em análise. [exec]
3. **Subscrição → «Pendentes de subscrição 4» (dashboard) vs «Abertas 1» (fila)**: dois ecrãs dizem coisas diferentes ao mesmo utilizador (efeito da F2). [exec]
4. **Cotações emitidas continuam com «Válida até»** na lista. Para uma cotação já emitida, a validade deixa de interessar e confunde. [exec]
5. **Utilizador «Conta Bloqueada»** aparece como **ATIVO** e nada indica bloqueio. [exec] (não confirmei se o seed chega a bloquear a conta)
6. **Parâmetros da plataforma: «Comissão de mediação máxima 100 %»**: um tecto de 100 % na prática não limita nada. [exec]
7. **Parâmetros legais sem base legal**: a coluna «Base legal» está vazia em «Imposto do selo», «Taxa de supervisão ARSEG» e «Maioridade». O ecrã tem a coluna, mas nenhum parâmetro legal a preenche. Convém também confirmar com a área jurídica se «Imposto do selo 0 %» é intencional. [exec]
8. **Endosso com prestações pré-pagas**: na APO-35, com a prestação n.º 2 paga antecipadamente, o pro-rata do bebé (cobertura desde 31/10/2026) só é cobrado a partir de 25/04/2027 (prestações 5 e 6, com os mesmos períodos das 3 e 4). O total está certo, mas o cliente tem cobertura 6 meses antes de pagar, e a Cobrança passa a ter duas linhas para o mesmo período. Sugestão: cobrar no vencimento mais próximo a parte já decorrida, ou juntar o valor às prestações existentes. [exec]
9. **Pagar de novo a prestação n.º 1** devolve «A apólice <uuid> está em ACTIVE; só uma apólice PENDING_FIRST_PREMIUM…». Devia dizer «Esta prestação já está paga». [exec]

## 3. UI/UX e terminologia, por tipo de utilizador

### Cliente final (portal)
- Aparecem **códigos técnicos**: «AMBULATORY_SURGERY», «EMERGENCY»… nas coberturas; «Tipo INDIVIDUAL» na apólice e no perfil; «Miguel Silva · CONJUGE» na elegibilidade; «POLICY APO-1» nas mensagens. [exec]
- **Valores e datas com formatos diferentes**: o alerta mostra «17625.00 AOA» e o resto mostra «17 625,00 Kz»; as notificações dizem «vence em 2026-10-29» (data ISO). [exec]
- **«Q360» é o nome do software, não da seguradora**: «Nova mensagem da Q360», «Contacte o seu mediador Q360 ou um balcão Q360». Num produto white-label o cliente devia ver o nome da seguradora. [exec]
- **NIF e «N.º de registo»** mostram o mesmo valor, repetido, no perfil. [exec]
- **Não há ecrã para responder a um endosso.** O backend tem `/customer-portal/endorsements` (listar, aceitar/recusar, PDF), mas o portal não o usa. O cliente não consegue aceitar a inclusão de um beneficiário. [código: nenhuma referência em `src/domains/customer-portal`]
- Para aceitar uma cotação aprovada é preciso «criar um pedido». Funciona, mas um botão «Aceitar» directo seria mais simples.
- Mistura «Activa»/«ATIVAS» e «Enviamos»/«Enviámos» (`CustomerPortalApp.tsx:272` vs `:283`). [exec/código]

### Subscritor e gestor de subscrição
- A F2 é a mais grave para estes perfis: há trabalho pendente que não aparece.
- **Mensagens de erro com UUID e em português do Brasil**: «O utilizador a876eb78-… submeteu esta cotação…» (devia mostrar o nome); «Você não tem permissão para executar essa ação» (PT-BR). [exec]
- Entrar em `/auditoria` pelo URL, sem permissão, mostra «Erro ao carregar auditoria… Tente novamente», como se fosse uma falha técnica. Devia dizer «Não tem acesso a esta área». [exec]
- **Proponentes com o mesmo nome não se distinguem** nas listas de escolha (Tarifação, Importar membros): há duas «Benguela Agro-Indústria, Lda.», com NIF diferente. Mostrar o NIF ao lado do nome resolve. [exec]
- **Valores sem separador de milhares** na lista de cotações («138000 AOA»), quando a Cobrança mostra «Kz 15 375,00». Mesmo dentro da Cobrança, «Kz 3000,00» aparece sem espaço e «Kz 15 375,00» com espaço (efeito do `Intl` em pt-PT com 4 dígitos). [exec · código `QuotesListPage` linha 151]
- «Tempo médio de aprovação 0 h» e «Criado há 0 h» vêm dos dados de seed instantâneos, não do produto. Só se nota em demonstração.
- Na auditoria, eventos como «Operação staff_account.login_succeeded concluída.» e «Pricing calculado com a tarifa vigente» aparecem como «Outro evento». [exec]

### Administrador do tenant
- **Textos de programador nos ecrãs de negócio**:
  - Parâmetros: «Utilização: Cotações: \`valid_until\`…», «POST /members», «Documentos: POST /documents/{id}/signed-url», «parâmetros do GTE».
  - Fórmulas: «(pricing.formulas)».
  - Tarifação legado: «Peça ao backend para migrar… com migrate_legacy_tariffs».
  - Configuração avançada: «Q360 Health Quotation Core».
  [exec]
- **Categorias em inglês** na configuração avançada: «Security ·», «Approvals ·», «Service ·», «Tarifação · Experience rating». E ainda «Rating Tables», «Document Templates», «Contas de staff», «Repor password» (no resto do produto diz-se «palavra-passe»). [exec]
- **A Consola API aparece no menu do administrador**, com textos de sprint («Sprint 1 — /me…») e instruções de `.env.local`. É ferramenta de programador e não devia estar no menu de um cliente. [exec]
- O «Meu perfil» mostra papéis e permissões em código (`ADMIN`, `quote:approve`…) e diz «Edição ainda não disponível». [exec]
- **Tratamento misturado (tu/você)**: «Escolhe um produto…», «Abre uma para ver…», «que precises» ao lado de «Selecione», «Consulte». [exec]
- **Ortografia misturada**: «ACTIVOS»/«ATIVO», «actuarial»/«atuariais», «seleccionada»/«selecionada», muitas vezes no mesmo ecrã. Convém escolher uma norma (AO90 ou pré-AO) e aplicá-la em todo o produto. [exec]
- «Inflação médica padrão para renovação» não tem valor («—»), nem no tenant nem na plataforma. As renovações sem percentagem no plano ficam sem indexação. [exec]

### Super-administrador (plataforma)
- **Auditoria meio traduzida**: «Fornecedor tenants listed», «Fornecedor início de sessão succeeded». [exec]
- **Cada listagem gera um evento de auditoria** (3 eventos «tenants listed» em 8 segundos). O trilho enche-se de ruído e os eventos que importam perdem-se. [exec]
- «Seguradora» na plataforma vs «tenant» nos ecrãs do administrador («cópias… para este tenant»). [exec]
- Na mesma área, «Activo» no dashboard e «ATIVO» na lista de seguradoras; a conta usa «tua conta» (tu) e o resto usa você. [exec]
- Os números usam ponto decimal («931.27 Kz por USD», «10.9 %») em vez de vírgula. [exec]
- O ecrã «Motor de fórmulas» mostra jargão interno: «(OD-006)», «Cada passo TOTAL», «Sem eval». [exec]

### Programador
- O dashboard chama `_status_counts` sobre querysets ordenados em três sítios (F1). Convém rever outros `values().annotate()` com `order_by` herdado.
- Há 31 testes que já falhavam no HEAD (verificado na sessão anterior com um worktree limpo). Não vêm desta auditoria, mas escondem regressões novas.
- O login demora 2,5–3,7 s por pedido no servidor de desenvolvimento, e quatro logins em simultâneo deram timeout ao frontend. Não identifiquei a causa (não a investiguei). Fica como observação.

## 4. O que foi testado e funciona

- **Quatro olhos**: quem submete não pode decidir (403 SEC-403). Outro subscritor aprova. [exec]
- **Cotação → preço → requisitos → submissão → aprovação → minuta → emissão**: APO-35 em `PENDING_FIRST_PREMIUM` → pagamento da 1.ª prestação → `ACTIVE`, com início no dia seguinte e as restantes prestações geradas. PDF da apólice disponível. [exec]
- **Endosso de inclusão**: criação, cálculo pro-rata (359/365), submissão, aprovação pelo gestor, prazo de aceitação = data de inclusão, aceitação, novas prestações e endosso n.º 1 registado. Com a configuração por omissão (`newborn_auto_inclusion_days = 0`), o recém-nascido vai para revisão manual, como previsto. [exec]
- **Rotas protegidas por perfil**: o subscritor é enviado para o dashboard em Administração e na Consola API; o gestor não entra em Utilizadores nem em Configuração avançada. [exec]
- Não houve nenhum erro de consola nem resposta 5xx nas 97 visitas de ecrã (5 perfis). A única resposta 4xx foi a 403 esperada (subscritor em `/auditoria`). [exec]

## 5. Ordem sugerida

1. F1 e F2 (números errados e trabalho invisível para a subscrição).
2. Ecrã de resposta a endossos no portal, e F4 (carência 0).
3. F5–F8 (seed fiável e sem emails reais).
4. Limpeza de terminologia: escolher norma ortográfica e tratamento (você), tirar códigos e jargão de programador, tirar a Consola API do menu, formatar valores e datas com uma única função.

---

## 6. Correções — FINALIZADO (24/10/2026)

Feitas pela ordem pedida. Nada foi enviado para o Git (sem commits).

### 1. F1 e F2 — números certos e fila completa
- **F1 ✅** `_status_counts`, tendência e conversões limpam a ordenação antes de agrupar (`backend/apps/foundation/interfaces/views.py`). Verificado na base de auditoria: DRAFT 4 · BOUND 36 · REJECTED 4 · APPROVED 1 · IN_REVIEW 4; conversão 75,51 %; tendência «49 criadas / 37 aprovadas» em outubro; apólices ACTIVE 28 / PENDING 7. Teste novo: `tests/quote/test_quotes.py::test_dashboard_counts_group_by_status_not_by_quote`.
- **F2 ✅** A fila de subscrição percorre todas as páginas do servidor (`src/domains/underwriting/services/underwritingApi.ts`). O cartão «Cotações na fila» passa a «Por decidir» e conta só abertas e em análise (contradição 2 da secção 2).

### 2. Endossos no portal e F4
- **Ecrã «Inclusões propostas» ✅** (`/portal-cliente/inclusoes`, entrada no menu e aviso no Resumo). Mostra as pessoas, o valor, como é cobrado e o novo prémio anual. Tem «Aceitar inclusão», «Recusar» (com motivo, mínimo 10 caracteres) e «Ver proposta (PDF)». Testado no browser com a Ana: proposta da APO-1 → aceitar → mensagem de confirmação, proposta retirada da lista, sem erros de consola.
- **F4 ✅** `waitingDays = 0` numa cobertura passa a significar «sem carência» e prevalece sobre a carência genérica da regra (`issuance_service._coverage_waiting_days`). Testes novos: `tests/policy/test_waiting_period_zero.py`.

### 3. Seed fiável e sem emails reais
- **F5 ✅** O histórico de sinistralidade passa a ser gerado em `.xlsx`, com a função nova `claims.application.import_service.xlsx_from_rows`. O `seed_full_database --allow-demo` corre até ao fim numa base nova: 54 importações de sinistralidade, tenant de isolamento criado. O teste de ponta a ponta `tests/policy/test_end_to_end.py`, que enviava CSV, também passa.
- **F6 ✅** Para criar prestações em atraso ou a vencer, os seeds recuam a apólice inteira: vigência, prestações, pagamentos, inclusões e carências (`apps/policy/application/demo_dates.py`). A janela de renovação da Empresa Kilamba também recua a vigência em vez de a encurtar. Verificado numa base nova: 0 prestações fora da vigência, 0 atrasos de períodos futuros, 0 vigências curtas.
- **F7 ✅** Por omissão os clientes de demonstração usam `ana.silva@demo.q360.local` e `carlos.mendes@demo.q360.local`. Quem quiser receber os códigos na sua caixa define `Q360_DEMO_EMAIL_ANA` / `Q360_DEMO_EMAIL_CARLOS` antes de correr o seed. O comando de produção `prepare_portal_test_accounts` não foi alterado.
- **F8 ✅** A saída do seed indica `VITE_CUSTOMER_PORTAL_TENANT_ID`.

### 4. Terminologia, formatação e Consola API
- **Norma ortográfica: AO90** (já era a dominante: cerca de 1 680 ocorrências contra 280 da antiga). Aplicada aos textos do frontend e aos textos em português do backend: mensagens, catálogo, parâmetros e documentos. Os identificadores, os caminhos da API e os docstrings em inglês ficaram como estavam.
- **Tratamento: «você».** As formas com «tu» passaram a «você» («Escolha», «Ajuste», «Tente novamente», «sua conta», «Não pode decidir uma cotação que foi você a submeter»).
- **Formatação única de valores e datas.**
  - Frontend: `src/shared/format.ts` (`money`, `number`, `percent`, `quantity`, `date`, `dateTime`), com o formato «Kz 15.375,00» (também com 4 dígitos: «Kz 3.000,00») e datas dd/mm/aaaa. Usada em mais de 50 ecrãs; `formatAOA` e `formatDateTime` antigos delegam nela. Testes: `src/tests/format.test.ts`.
  - Backend: `shared/formatting.py`, com a mesma regra. Usada nos alertas e notificações do portal, nas mensagens de erro do endosso e nos documentos (propostas e apólices passam a mostrar «Kz 15.000.000,00»).
- **Consola API:** só aparece (menu e rota) no ambiente de desenvolvimento (`npm run dev`).
- **Códigos e jargão retirados:**
  - **Parâmetros:** os textos de «Utilização» deixam de mostrar endpoints, `valid_until`, GTE e OD-006. «Valor do código» passa a «valor inicial do sistema». Os números aparecem com vírgula decimal («931,27 Kz por USD», «10,9 %») e as unidades no singular quando o valor é 1 («1 dia a 60 dias»).
  - **Administração:** sem «Q360 Health Quotation Core», «(pricing.formulas)», `migrate_legacy_tariffs`, «Rating Tables», «Document Templates», «Contas de staff» nem «password». As categorias da configuração avançada estão em português («Segurança e permissões», «Aprovações», «Atendimento», «Tarifação pela experiência de sinistralidade»). «Pricing» visível passou a «Tarifação» ou «Prémio».
  - **Perfil:** perfis e permissões aparecem por extenso. Saiu o `console.log` e o aviso «Edição ainda não disponível».
  - **Auditoria do tenant:** as ações do backend aparecem em frases portuguesas («Início de sessão», «Apólice ativada (1.º prémio pago)»…). Sem permissão, o ecrã diz «Sem acesso à auditoria» em vez de «Erro ao carregar».
  - **Auditoria da plataforma:** ações traduzidas. A consulta da lista de seguradoras deixa de ser registada (era ruído).
  - **Motor de fórmulas:** sem «(OD-006)», «Cada passo TOTAL» e «Sem eval».
  - **Portal:**
    - sem códigos de cobertura;
    - «Tipo» por extenso;
    - parentesco por extenso nas listas;
    - «Apólice/Cotação/Pedido» nas mensagens;
    - NIF sem repetição;
    - «Q360» substituído por «a seguradora» / «o seu mediador»;
    - «Enviámos»;
    - valores e datas formatados também nos alertas e notificações que vêm do backend.
  - **Erros do backend:**
    - as mensagens por omissão do DRF passam a PT-PT («Não tem permissão para fazer esta operação.»);
    - a regra dos quatro olhos deixa de mostrar o UUID;
    - registar de novo o 1.º prémio responde «A 1.ª prestação da apólice APO-35 já está paga.».
- **F9 ✅** Os textos da Elegibilidade deixam de dizer que só as cotações aprovadas têm número.
- **Outros pontos da secção 3 resolvidos:**
  - «Válida até» só aparece nas cotações em curso;
  - as listas de proponentes mostram o NIF ao lado do nome;
  - a lista de cotações e os totais da tarifação usam a formatação única.

### Pontos que ficaram pendentes — resolvidos (26/10/2026)
- **F3 ✅** `QuerySet.update()` não corre o `auto_now`, por isso as transições de estado (submeter, aprovar, emitir…) deixavam o `updatedAt` igual ao `createdAt`. O QuerySet base dos modelos por tenant (`apps/foundation/infrastructure/tenant_scoping.py`) passa a atualizar `updated_at` em todos os `update()`. Teste: `test_updated_at_moves_on_queryset_updates`.
- **F10 ✅** `POST/PUT /members` exigem `firstName`, e um nome só com espaços também é recusado. Campos desconhecidos dão 400 e a mensagem indica o nome certo (`fullName` → «Use firstName e lastName», `gender` → «Use sexCode»). No frontend, o nome passou a ser obrigatório no formulário de membro da ficha do cliente (os outros formulários já o exigiam). Os testes que criavam pessoas sem nome (39 chamadas) foram atualizados. Teste: `test_member_requires_name_and_rejects_unknown_fields`.
- **«Conta Bloqueada» ATIVO ✅ (era defeito):** a conta estava mesmo bloqueada (5 tentativas falhadas, `locked_until` daqui a 10 anos), mas a API não o dizia e o ecrã só mostrava o estado ATIVO.
  - A lista de utilizadores tem agora o campo `lockedUntil` e o ecrã mostra «Bloqueado».
  - Nova ação «Desbloquear» (`POST /admin/staff-accounts/{id}/unlock`), que levanta o bloqueio sem mudar a palavra-passe e fica registada na auditoria.
  - Teste: `tests/platform_admin/test_staff_unlock.py`.
- **Comissão de 100 % ✅** O valor mantém-se (não há norma que fixe o teto), mas o ecrã da plataforma mostra «Sem teto» em vez de «100 %».
- **Base legal vazia ✅ (sem inventar):** a plataforma assinala «Por indicar» em cada parâmetro legal sem diploma registado e mostra um aviso no topo com a lista. O registo faz-se pelo «Propor alteração», que já exige a referência e aceita o mesmo valor, com aprovação por outro super administrador. **Falta o diploma de cada um** (imposto do selo, taxa ARSEG, maioridade), que tem de vir da área jurídica.
- **Endosso com prestações pré-pagas ✅** Nova opção em `policy.endorsements` → «Período já pago pelas prestações anteriores»:
  - **IMEDIATO (por omissão):** a parte entre a data de inclusão e o início da próxima prestação por pagar vence logo na data de inclusão, e o resto reparte-se pelas prestações futuras.
  - **REPARTIR:** o comportamento anterior.
  - O cálculo devolve `prepaidPeriodCharge`. Teste: `test_prepaid_period_is_charged_immediately_by_default`.
  - É uma regra de negócio: se a seguradora preferir a anterior, basta escolher REPARTIR na configuração.
- Mantém-se só a observação sobre o tempo de login, que não foi investigada.

### Verificação
- Frontend: `tsc` sem erros; `vitest` 35 ficheiros / 142 testes a passar. Os 2 testes que já falhavam antes, com textos antigos, foram alinhados. ESLint nos ficheiros alterados: os mesmos 11 erros que já existiam no HEAD, nenhum novo.
- Backend: `build_openapi` regenerado (só mudam descrições, para a nova ortografia); contrato copiado para o frontend e tipos regenerados. Suite completa: ver a linha seguinte.
- Suite do backend (26/10, depois dos pendentes): 795 passam, 30 falham, 1 ignorado — as mesmas 30 que já falhavam no HEAD; nenhuma nova. Na ronda de 24/10: 784 passam, 30 falham, 1 ignorado. As 30 falhas foram corridas num worktree limpo do HEAD e falham lá também (já existiam: importações, sinistralidade em CSV antigo, regras de grupo, simulador…), não vêm destas correções. As 4 que eram novas (`tests/quote/test_proposals.py`) resultavam da mudança intencional do formato de valores nos documentos e foram atualizadas. Antes destas correções falhavam 31.
- Browser (Playwright), depois das correções: dashboard com conversão de 76 % e 4 rejeitadas; fila com 4 por decidir, de 46; valores «Kz 15.375,00»; parâmetros «931,27 Kz por USD» e «10,9 %»; portal sem códigos técnicos e com o alerta «Prestação de Kz 17.625,00 em atraso». Nenhum erro de consola nem resposta 4xx/5xx. Num build de produção (`vite build`), a Consola API não está incluída.
- Nota: as notificações do portal gravadas antes desta correção mantêm a data no formato antigo («2026-10-29»); as novas já saem como dd/mm/aaaa.

---
Ambiente usado: base `q360_audit` (pode ser apagada com `DROP DATABASE q360_audit;`), conta de super-admin de teste `audit.super@q360.local` (só nessa base).

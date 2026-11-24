Roadmap — App móvel do Portal do Cliente Q360 (React Native / Expo)
Contexto
O Portal do Cliente existe hoje só na web (React, módulo src/domains/customer-portal do frontend). O objetivo é uma app móvel nativa (iOS e Android) única, com a marca Q360, onde o cliente de qualquer seguradora entra e vê a app com o logótipo e as cores da sua seguradora.
Decisões tomadas:
* Tecnologia: React Native com Expo (app nova, partilha a API e os tipos com a web).
* Marca: uma só app Q360 nas lojas, com a seguradora aplicada depois de entrar.
O backend já tem quase tudo o que a app precisa. São 49 rotas em /api/v1/customer-portal, que cobrem:
* painel, cotações e aceitação, apólices, cartão, verificar cobertura;
* pagamentos, documentos (incluindo envio de documentos);
* pedidos, mensagens, notificações, questionários, endossos e renovação.
O trabalho principal está em quatro coisas que a web não precisava:
1. Descobrir a seguradora. Hoje a seguradora é fixada na compilação (VITE_CUSTOMER_PORTAL_TENANT_ID).
2. Sessão longa e segura. Hoje o token dura 30 minutos (CUSTOMER_PORTAL_TOKEN_TTL_SECONDS=1800), não há renovação e fica em sessionStorage.
3. Notificações push. Hoje as notificações só aparecem quando a página as vai buscar.
4. Ligações dos emails (convite e código) a abrir diretamente na app.

Fase 0 — Preparação (1–2 semanas)
* Contas de programador: Apple Developer (99 USD/ano) e Google Play (25 USD, uma vez), em nome da entidade dona do Q360.
* Identidade da app: nome, ícone, ecrã de arranque, bundleId/applicationId (ex.: ao.quote360.cliente) e domínio para as ligações (app.quote360.ao).
* Repositório: projeto Expo novo (Q360-Cliente-Mobile) com TypeScript, Expo Router, TanStack Query (o mesmo da web) e EAS Build/Submit.
* Tipos da API:
    * gerados do mesmo contrato OpenAPI com openapi-typescript, como na web (npm run api:generate:offline);
    * a cópia do .yml faz-se como hoje (ver memória «frontend-contract-sync»).
* Política de privacidade e termos: obrigatórios nas lojas. É preciso rever a lei angolana de proteção de dados (Lei 22/11), porque a app trata dados de saúde.
Fase 1 — Backend pronto para a app (2–3 semanas, em paralelo com a Fase 2)
Todas as alterações são aditivas: a web continua a funcionar igual.
1. Descobrir a seguradora.
    * Rota nova POST /api/v1/customer-portal/discover {email}. Devolve as seguradoras onde o email tem conta (nome, id, marca), sem revelar se o email existe: resposta genérica e envio por email quando há várias.
    * Alternativa: escolher a seguradora numa lista pública com pesquisa.
    * Reutilizar CustomerAccount e as ligações CustomerAccountProposer (apps/customer_portal/infrastructure/models.py).
2. Marca pública da seguradora.
    * Rota GET /api/v1/customer-portal/{tenant_id}/branding: nome, cores, URL do logótipo e se o Portal do Cliente está ativo.
    * Reutilizar tenant_settings.settings_of e logo_bytes (apps/platform_admin/application/tenant_settings.py) e o módulo customerPortal.
3. Sessão móvel (renovação).
    * Token de renovação por dispositivo, em tabela nova customer_device_session: hash, dispositivo, data de criação, último uso, revogado.
    * Rotas POST …/auth/refresh e POST …/auth/logout.
    * O access token continua curto (30 minutos); o de renovação dura até 90 dias, roda a cada uso e é revogado quando a palavra-passe muda.
    * Base existente: PortalTokenService (apps/customer_portal/infrastructure/portal_token.py) e password_auth_service.py.
4. Notificações push.
    * Tabela customer_push_device (conta, token Expo, plataforma, ativo).
    * Rotas POST/DELETE …/devices.
    * Envio pelo Expo Push Service quando se cria uma notificação do portal.
    * Base: notifications_service.py (onde as notificações são criadas hoje). O envio é feito depois do commit, como já se faz com os emails.
    * Eventos prioritários: prestação em atraso, cotação aprovada ou proposta disponível, pedido atualizado, mensagem nova, endosso para aceitar e renovação.
    * O cliente pode desligar as notificações por tipo (preferências no perfil).
5. Ligações universais.
    * Os emails de convite, código e notificação passam a usar https://app.quote360.ao/..., que abre a app se estiver instalada e a web se não estiver.
    * Publicar apple-app-site-association e assetlinks.json nesse domínio.
    * Base: email_sender.py e CUSTOMER_PORTAL_URL.
6. Segurança.
    * Limites de pedidos por dispositivo, além dos atuais por IP e por email.
    * Auditoria de entradas por dispositivo.
    * Lista «Dispositivos ligados» no perfil, com a opção de terminar a sessão.
7. Testes e contrato: testes em tests/customer_portal/ e as rotas novas registadas em config/openapi/registry.py.
Fase 2 — App MVP (6–8 semanas)
Ecrãs, pela ordem de valor para o cliente:
Sprint	Ecrãs	API existente
1	Arranque, escolher a seguradora, entrar (email e palavra-passe), primeiro acesso com código, recuperar palavra-passe, aplicar a marca	auth/login, first-access/*, password-reset/* + rotas novas da Fase 1
2	Início (painel e alertas), Apólices (lista e detalhe), Cartão digital	dashboard, policies, card
3	Pagamentos (prestações, instruções de pagamento), Documentos (ver e partilhar PDF)	payments, documents
4	Pedidos (criar, acompanhar, avaliar), Mensagens, Notificações (lista e marcar como lidas)	requests, conversations, notifications
5	Cotações (ver e aceitar em 2 passos), Questionários de saúde, Endossos	me/quotes, questionnaires, endorsements
Comportamento móvel no MVP:
* Sessão: token de renovação no expo-secure-store (Keychain/Keystore) e renovação automática quando o access token expira.
* Desbloqueio por biometria: Face ID ou impressão digital, com expo-local-authentication, para reabrir a sessão guardada.
* Push: expo-notifications; tocar na notificação abre o ecrã certo.
* Cartão digital offline: a última versão fica guardada no dispositivo, para mostrar no hospital sem rede.
* Erros e falta de rede: mensagens em português e «tentar de novo», reutilizando os textos de portalErrorMessage da web.
* Acessibilidade: tamanhos de letra do sistema, leitores de ecrã e modo escuro.
Fase 3 — Funcionalidades móveis (4–6 semanas)
* Fotografar e enviar documentos com a câmara: receitas, faturas para reembolso, documentos de identificação. Usa uploadMemberDocument e o envio já existente.
* Verificar cobertura antes de uma consulta, a partir do cartão (checkCoverage/evaluateMyCoverage).
* Rede convencionada: mapa e lista de prestadores, com a localização do telemóvel. Precisa de uma rota nova de prestadores, se ainda não existir.
* Renovação e comparação de planos (getRenewal, comparePlans).
* Partilhar o cartão (imagem ou PDF) e acrescentá-lo à Wallet, se houver procura.
* Preferências de notificações e idioma.
Fase 4 — Publicação e operação (2–3 semanas, mais contínuo)
* Testes fechados:
    * TestFlight (iOS) e teste interno no Google Play;
    * piloto com uma seguradora e 20 a 50 clientes reais.
* Revisão das lojas:
    * conta de demonstração para os revisores;
    * formulários de privacidade (dados de saúde);
    * opção de apagar a conta na app (exigida pela Apple).
* Atualizações sem nova revisão: EAS Update para correções em JavaScript; versões nativas por EAS Build/Submit.
* Monitorização:
    * relatório de falhas (Sentry);
    * métricas de uso: ativações, entradas, ecrãs mais usados e push abertos.
* Suporte: a versão mínima suportada é imposta pelo backend (cabeçalho X-App-Version), para obrigar a atualizar quando houver mudanças incompatíveis.

Calendário indicativo (1 programador móvel + apoio de backend)
Semanas	Fase
1–2	Fase 0
2–5	Fase 1 (backend)
3–10	Fase 2 (MVP)
11–12	Piloto (TestFlight / teste interno)
13–14	Publicação nas lojas
15–20	Fase 3
MVP nas lojas em cerca de 3 meses e meio.
Riscos e decisões a confirmar
* Escolha da seguradora: pela descoberta por email (melhor experiência) ou por uma lista pública de seguradoras (mais simples, mas expõe a lista).
* Dados de saúde no dispositivo: guardar em cache só o cartão e os dados mínimos, nunca questionários ou documentos clínicos.
* Prazos de revisão da Apple (1 a 7 dias por versão) e exigências sobre apps de seguros e saúde.
* Duas bases de código (web e app) com regras de negócio duplicadas no ecrã: a regra deve ficar sempre no backend, e a app só apresenta.
* Custos: contas das lojas, EAS (plano gratuito no início; pago com mais builds), Sentry e envio de push (o Expo Push é gratuito).
Verificação
* Backend:
    * testes pytest das rotas novas: descoberta, marca, renovação e revogação de sessão, registo de dispositivo e envio de push simulado;
    * manage.py build_openapi e test_openapi_contract verdes;
    * a suite completa continua verde.
* App:
    * testes unitários (Jest) dos serviços de sessão e da renovação de token;
    * testes E2E com Maestro: entrar, ver o cartão, criar um pedido e receber um push no Expo Go ou num build de desenvolvimento;
    * testes manuais num iPhone e num Android de gama baixa (o mais comum em Angola) com rede 3G simulada.
* Antes de publicar: piloto com uma seguradora, e o cartão offline confirmado em modo avião.

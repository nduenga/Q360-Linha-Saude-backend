# Guia prático de testes — Plataforma e Portal Cliente

Tudo o que precisa para pôr o sistema a funcionar com dados de demonstração e testar cada parte, passo a passo.

## 1. Como o sistema funciona (em 1 minuto)

**Plataforma (backoffice)** — usada pelos colaboradores da seguradora.
- O subscritor cria uma **cotação**, escolhe o produto/plano, associa o cliente e os membros e calcula o prémio.
- A cotação segue para **subscrição**. O aprovador analisa-a e aprova ou recusa; só uma cotação aprovada pode ser contratada.
- Depois de o cliente assinar presencialmente, um utilizador autorizado regista quem assinou, o documento, a qualidade em que assinou e a data/hora. Esse registo transforma a cotação aprovada numa **apólice**.
- A apólice começa **a aguardar o primeiro pagamento**. Só depois de o pagamento ser registado fica activa; a data de início respeita a assinatura e o pagamento.
- A equipa passa então a consultar os dados da apólice, pessoas seguradas, prestações e renovação no mesmo backend que alimenta o Portal.

**Portal Cliente** — usado pelo cliente final, só para consultar e pedir.
- Mostra as cotações (com estado), as apólices, coberturas, pessoas seguradas, pagamentos e documentos.
- O cliente **pede** coisas (alterações, renovação, nova cotação, aceitar uma cotação) e **fala** com a Q360 por mensagens. Quem decide continua a ser a plataforma.
- Entra com **email + palavra-passe**. Na primeira vez, recebe um código no email que a Q360 tem no registo e define a palavra-passe.

```
 Mediador ─► PLATAFORMA ◄──── mesmos dados ────► PORTAL ◄─ Cliente
 (cotação, apólice)   backend Django :8000   (consulta, pedidos, mensagens)
```

Há **um só backend** (`:8000`) e **um só frontend**: `Q360-Linha-Sa-de-frontend` (React/Vite, `:5173`). A Plataforma e o Portal Cliente são áreas desse mesmo frontend.

## 2. Preparar

### Estado actual da interface

O Portal Cliente está integrado no projecto `Q360-Linha-Sa-de-frontend`.
Arranque apenas este frontend na porta `5173`; o projecto autónomo
`Q360-Saude-Portal-Cliente` e a porta `3000` são referências legadas deste
guia e não fazem parte do fluxo actual. Plataforma e portal usam o mesmo
backend e os mesmos dados.

### 2.1 Base de dados e dados de demonstração
Na pasta `backend`, com o ambiente virtual activo:

```powershell
python manage.py migrate
python manage.py seed_demo_data      # plataforma + portal (cria o tenant "demo-saude")
```

Pode repetir à vontade **apenas em desenvolvimento**: repõe as palavras-passe e o estado dos clientes demo.
Para recriar só a parte do portal: `python manage.py seed_portal_demo`.

No fim, o comando imprime o **id do tenant** — anote-o.

### 2.2 Email local: ver os códigos sem usar caixas de correio reais
O `backend/.env` usa SMTP real (Gmail). Para testar sem enviar emails, mude **temporariamente** para:

```
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

Os códigos passam a aparecer **no terminal do backend** («O código ... é: 123456»).
Se preferir receber os códigos nas caixas de correio, mantenha o SMTP configurado. Os três registos de demonstração para primeiro acesso estão associados a:

### 2.3 Apontar o Portal Cliente para o tenant demo
Em `Q360-Linha-Sa-de-frontend/.env.local`:

```
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_CUSTOMER_PORTAL_TENANT_ID=<id do tenant demo-saude impresso pelo seeder>
```

Reinicie o Vite depois de alterar estas variáveis.

### 2.4 Arrancar (2 terminais)

| O quê | Pasta | Comando | Endereço |
|---|---|---|---|
| Backend | `Quote - Saúde/backend` | `python manage.py runserver` | http://127.0.0.1:8000 (docs da API: `/api/docs`) |
| Plataforma e Portal Cliente | `Q360-Linha-Sa-de-frontend` | `npm run dev` | http://localhost:5173 |

## 3. Credenciais

### Plataforma — colaboradores (palavra-passe `Q360Demo!2026`)

Os únicos perfis demo actuais são Administrador, Gestor de Subscrição e
Subscritor. Não use as credenciais antigas de Configurador, Aprovador,
Auditor ou Super administrador: esses perfis não são criados pelo seeder
actual.

| Perfil | Email | Para quê |
|---|---|---|
| Administrador | `admin.demo@q360.local` | tudo, incluindo administração |
| Gestor de Subscrição | `gestor.demo@q360.local` | analisar, aprovar ou recusar cotações |
| Subscritor | `subscritor.demo@q360.local` | criar, calcular e submeter cotações |

Entrada: http://localhost:5173/login (utilizador ou email + palavra-passe).

### Portal Cliente — clientes

**Dados de demonstração** (palavra-passe inicial `Cliente!Demo2026` para as contas pré-configuradas):

| Cliente | Email | O que tem |
|---|---|---|
| Ana Silva | `helibrando@gmail.com` | apólice activa, prestação em atraso e outra a vencer, cotação aprovada por aceitar, 2 pedidos, 1 mensagem |
| Diana Lopes | `diana.lopes@demo.q360.local` | só cotações (em análise e recusada; o rascunho não aparece) |

**Teste de primeiro acesso por email** — use o número exato da apólice (`APO-n`) impresso pelo seeder e o documento correspondente:

| Cliente | Referência | Documento | Cenário |
|---|---|---|---|
| Ana Silva | apólice impressa pelo seeder | `000000001LA001` | apólice activa e cenário completo do Portal; código para `helibrando@gmail.com` |
| Empresa Kilamba | apólice impressa pelo seeder | `541000003LA003` | apólice a terminar em 45 dias; código para `fabiongila@gmail.com` |
| Carlos Mendes | apólice impressa pelo seeder | `000000002LA002` | apólice a aguardar o 1.º pagamento; código para `sethlussueki@gmail.com` |
| Mariana Costa | cotação impressa pelo seeder | `000000005LA005` | sem email no registo → erro esperado |

Portal: abra-o a partir do mesmo frontend em http://localhost:5173. O Portal Cliente já está integrado no frontend; não arranque o projecto legado separado na porta `3000`.

## 4. Testes do Portal Cliente

Cada teste diz o que fazer e o que deve acontecer.

### 4.1 Entrar e primeiro acesso
1. **Entrar com conta.** `/portal-cliente/acesso` → `helibrando@gmail.com` + `Cliente!Demo2026` → entra no **Resumo**.
2. **Palavra-passe errada.** Escreva uma errada → «Email ou palavra-passe incorretos». À 5.ª tentativa → conta bloqueada 30 minutos.
3. **Primeiro acesso.** No login, clique em «Criar palavra-passe» (ou abra `/portal-cliente/primeiro`). Use a referência impressa pelo seeder e o documento da Ana, Carlos ou Empresa Kilamba conforme a tabela acima. Confirme o email mascarado, copie o código do terminal do backend (email de consola) ou da caixa de correio (SMTP), introduza o código e escolha uma palavra-passe com 10+ caracteres. «Guardar e entrar» deve abrir o Resumo. Saia e volte a entrar com o email e a nova palavra-passe.
4. **Palavra-passe fraca.** No passo anterior, tente `1234567890` → recusada com explicação, e o código **continua válido**.
5. **Sem email.** Primeiro acesso com a cotação da **Mariana** + `000000005LA005` → «Ainda não temos um email registado… contacte o seu mediador».
6. **Documento errado.** Qualquer referência com documento errado → «O número de documento não corresponde».
7. **Esqueci-me.** `/portal-cliente/acesso` → «Esqueci-me» → email da Ana → código → nova palavra-passe → entra. Com um email inexistente, o ecrã responde igual e não chega código.
8. **Sessão.** Passados 30 minutos pede nova entrada.

> Para repetir o teste com Carlos ou Empresa Kilamba, volte a correr `python manage.py seed_portal_demo` em desenvolvimento: repõe esses clientes sem palavra-passe. A Ana já tem uma palavra-passe demo, mas o fluxo de primeiro acesso também envia um código para ela e permite defini-la novamente.

### 4.2 Dentro do portal (entrar como **Ana**)
| Onde | O que deve ver |
|---|---|
| **Resumo** | alertas «pagamento em atraso» e cotação a expirar; contagens por estado; próximos eventos; totais pagos, por pagar e em atraso |
| **Cotações** | uma «Aprovada — aguarda assinatura» e as contratadas; abrir uma mostra a **linha temporal** |
| **Apólices** | 1 apólice activa; abrir mostra condições, pessoas seguradas e prestações |
| **Coberturas / Elegibilidade** | coberturas contratadas e se cada pessoa está coberta hoje (algumas em carência) |
| **Beneficiários** | as 4 pessoas; o ícone abre o **cartão digital** |
| **Pagamentos** | 1 prestação «Em atraso», 1 «Por pagar», e as pagas |
| **Notificações** (sino) | pagamento em atraso, cotação aprovada, pedido actualizado, nova mensagem; marcar como lida |
| **Pedidos** | 2 pedidos: um «A aguardar o cliente» (com a nota do backoffice), outro «Aberto» |
| **Mensagens** | 1 conversa da apólice com resposta da Q360 por ler |
| **Perfil** | dados da Ana e o email de acesso |
| **Comparar planos** | os planos do produto da Ana, com coberturas e limites, **sem preços** |
| **Ajuda** | perguntas frequentes |

Como **Diana**: 2 cotações (Em análise, Recusada), sem apólices, e o rascunho **não** aparece.

### 4.3 Pedidos e mensagens
1. Como Ana → **Pedidos** → «Novo pedido» → *Alteração de dados* → enviar → aparece «Aberto».
2. Abra o pedido que está «A aguardar o cliente», leia a nota e **responda nas mensagens** → o estado passa a «Em análise».
3. Tente criar um **2.º pedido de renovação** para a mesma apólice → recusado (só um aberto).
4. **Inclusão de beneficiário** com a data em falta → recusado com a mensagem do que falta.
5. Na cotação **aprovada**: «Aceitar a cotação» → cria o pedido de aceitação (o mediador regista depois a assinatura).

### 4.4 Renovação
1. Entre com a **Empresa Kilamba** (faça primeiro o primeiro acesso, §4.1).
2. **Renovações** → a apólice → o botão **«Pedir renovação»** está activo (faltam 45 dias) → carregue → vai para o pedido.
3. Na Ana, a apólice só termina daqui a muito mais de 90 dias → o botão não aparece e diz quando abre.

## 5. Atender os pedidos do portal (lado do backoffice)

Ainda **não há ecrã** no backoffice para isto; usa-se a API. Abra http://127.0.0.1:8000/api/docs ou use `curl`.

```powershell
# 1. Entrar como administrador e guardar o token
$login = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/auth/login `
  -ContentType 'application/json' -Body '{"email":"admin.demo@q360.local","password":"Q360Demo!2026"}'
$h = @{ Authorization = "Bearer $($login.accessToken)"; 'Idempotency-Key' = [guid]::NewGuid().ToString() }

# 2. Ver pedidos abertos
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/portal-requests?status=OPEN' -Headers $h

# 3. Passar um pedido a «Em análise» (troque PED-1 pelo número real)
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/portal-requests/PED-1/transition `
  -Headers $h -ContentType 'application/json' -Body '{"toStatus":"IN_REVIEW"}'

# 4. Pedir um documento ao cliente (a nota é obrigatória) e aprovar/rejeitar depois
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/portal-requests/PED-1/transition `
  -Headers $h -ContentType 'application/json' -Body '{"toStatus":"AWAITING_CUSTOMER","note":"Envie o seu BI."}'

# 5. Responder a uma conversa
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/portal-messages `
  -Headers $h -ContentType 'application/json' `
  -Body '{"contextType":"REQUEST","contextRef":"PED-1","body":"Recebemos o seu pedido."}'
```

Estados e passagens permitidas: `OPEN → IN_REVIEW → AWAITING_CUSTOMER / APPROVED / REJECTED → COMPLETED`. Mover para «Rejeitado» ou «A aguardar o cliente» exige nota.
Depois de cada passo, volte ao portal (como Ana): o **sino** mostra a notificação e o pedido muda de estado.

## 6. Testes da Plataforma

Entrar em http://localhost:5173/login.

### 6.1 Fluxo completo de uma cotação
1. **Subscritor** → **Cotações → Nova** → cliente *Diana Lopes* → plano *Família Plus* → data de início → adicionar pessoas → calcular o prémio.
2. Submeter para revisão.
3. **Gestor de Subscrição** → **Subscrição** → abrir a cotação → **Aprovar** (ou recusar com motivo).
4. A cotação aprovada **aparece de imediato no portal da Diana** como «Aprovada — aguarda assinatura».
5. **Emitir a apólice e registar o 1.º pagamento.** O ecrã da plataforma **ainda não tem** estes dois passos; fazem-se pela API (com o Aprovador ou o Administrador):

```powershell
# Entrar como gestor de subscrição
$login = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/auth/login -ContentType 'application/json' `
  -Body '{"email":"gestor.demo@q360.local","password":"Q360Demo!2026"}'
$h = @{ Authorization = "Bearer $($login.accessToken)"; 'Idempotency-Key' = [guid]::NewGuid().ToString() }

# Id da cotação aprovada: copie-o do endereço no ecrã (…/cotacoes/<id>/…) e veja a versão
$quoteId = '<id da cotação>'
$quote = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/quotes/$quoteId" -Headers $h

# Emitir a apólice (o cliente assinou)
$body = @{ signatoryName='Diana Lopes'; signatoryDocumentType='BI'; signatoryDocumentNumber='000000004LA004';
  signatoryCapacity='TOMADOR'; signatureMethod='PRESENCIAL'; signedAt=(Get-Date).ToUniversalTime().ToString('o');
  termMonths=12; paymentFrequency='ANUAL'; rowVersion=$quote.rowVersion } | ConvertTo-Json
$policy = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/quotes/$quoteId/policy" -Headers $h -ContentType 'application/json' -Body $body
$policy.policyNumber   # a apólice nasce «A aguardar 1.º pagamento»

# Registar o 1.º pagamento -> a apólice passa a Activa
$h['Idempotency-Key'] = [guid]::NewGuid().ToString()
$pay = @{ paidAt=(Get-Date).ToUniversalTime().ToString('o'); paymentReference='TESTE-1'; paymentMethod='TRANSFERENCIA'; rowVersion=$policy.rowVersion } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/policies/$($policy.id)/installments/1/payment" -Headers $h -ContentType 'application/json' -Body $pay
```

**Como a assinatura presencial fica registada:** no pedido que emite a apólice, `signatureMethod='PRESENCIAL'` identifica que o cliente assinou fisicamente. O utilizador da plataforma preenche também o nome, tipo/número do documento, qualidade de representação (`TOMADOR`, `REPRESENTANTE_LEGAL` ou `PROCURADOR`) e a data/hora real da assinatura. Não se deve marcar uma cotação como assinada antes de o documento físico ter sido assinado.

> **Limite actual da interface:** ainda não existe um formulário/botão de emissão da apólice no ecrã da plataforma. Por isso, neste momento, o utilizador autorizado regista a assinatura presencial através do pedido API acima (`POST /api/v1/quotes/{quoteId}/policy`). A plataforma não tem actualmente um campo visual para carregar/arquivar o documento físico assinado. O registo do método e dos dados do signatário fica na API; a emissão e o primeiro pagamento são operações separadas.

A Diana passa a ver a apólice no Portal depois de emitida; para a tornar activa, registe também o primeiro pagamento. A conta demo dela já está associada ao registo e pode entrar com a palavra-passe demo.

### Gestão de uma apólice, em termos simples

1. **Preparar:** o subscritor cria uma cotação, escolhe o plano, inclui as pessoas e calcula o prémio.
2. **Decidir:** a equipa de subscrição avalia e aprova ou recusa a cotação.
3. **Formalizar:** se o cliente aceitar e assinar presencialmente, o utilizador autorizado regista os dados do signatário e a data/hora. No sistema actual, faz este passo no endpoint de emissão da apólice; o método é `PRESENCIAL`.
4. **Emitir:** a cotação aprovada passa a apólice e fica **Pendente do primeiro pagamento**. A assinatura, por si só, não activa a cobertura.
5. **Activar:** o utilizador regista o recebimento da primeira prestação. A apólice passa a **Activa**; a data de início é calculada para respeitar a data mais tardia entre assinatura e pagamento.
6. **Acompanhar:** a equipa consulta estado, condições contratadas, membros e prestações; pode acompanhar renovações. O cliente vê a mesma apólice no Portal e pode consultar/pedir alterações, mas não altera directamente o contrato.

No fluxo do §6.1, teste os passos 1–2 na plataforma, o passo 3–4 pelo endpoint documentado e o passo 5 pela API de pagamento. Depois, confirme a apólice do cliente no Portal. Para o primeiro acesso de Ana, Carlos ou Empresa Kilamba, use o email e a referência da tabela do §3.

### 6.2 Outras áreas (rápido)
| Área | O que testar |
|---|---|
| **Dashboard** | números por estado |
| **Cotações** | listas por estado; no seed há cotações em *DRAFT*, *IN_REVIEW* e *REJECTED* (Diana) |
| **Subscrição** | fila de revisão; decisão com motivo |
| **Clientes** | Ana, Carlos, Empresa Kilamba, Diana, Mariana |
| **Produtos / Planos / Coberturas** | Família Plus e Empresa Essencial; abrir a configuração de um plano |
| **Elegibilidade** | avaliações das pessoas (há uma «sem elegibilidade» por idade e uma com agravamento) |
| **Sinistralidade** | importar sinistros por ficheiro |
| **Auditoria** | eventos das acções que fez (Administrador) |
| **Administração** (Administrador) | contas de colaboradores, parâmetros do sistema |

## 7. Se algo não funcionar

| Sintoma | Causa provável |
|---|---|
| Portal: «Tenant…» / 404 ao entrar | `VITE_CUSTOMER_PORTAL_TENANT_ID` não é o UUID do tenant `demo-saude`, ou o Vite não foi reiniciado |
| 500 em `/auth/login` com «column … does not exist» | falta `python manage.py migrate` |
| Não chega o código | está a usar SMTP real: veja o terminal se mudou para o backend de consola (§2.2), ou veja o spam |
| «Conta temporariamente bloqueada» | 5 tentativas falhadas: espere 30 minutos ou volte a correr `seed_portal_demo` |
| `seed_demo_data` queixa-se de «pricing ambíguo» | o tenant já tem outra tabela de tarifas publicada; use um tenant novo (`--tenant-code outro`) |
| Cotação do portal não aparece | rascunhos (`DRAFT`) nunca aparecem; só depois de submetida |

## 8. Antes de produção

O deploy do frontend publica a Plataforma e o Portal Cliente juntos. Não há
um segundo deploy nem uma segunda aplicação web para o portal.

- Desligar o login antigo: `CUSTOMER_PORTAL_LEGACY_LOGIN_ENABLED=false`.
- Não correr `seed_demo_data` nem `seed_portal_demo` (criam cenários fictícios e palavras-passe fixas; os comandos também recusam execução com `DEBUG=False`).
- Para preparar teste real de email no tenant, usar apenas `prepare_portal_test_accounts --tenant-id <UUID> --confirm-production`, depois de confirmar que os três clientes e suas apólices/cotações já existem nesse ambiente.
- Configurar SMTP de produção e verificar que as três caixas autorizadas recebem email. Nunca usar o backend de email de consola em produção e nunca copiar códigos OTP para logs ou documentação.
- Antes de usar o Portal no ambiente, aplicar todas as migrações pendentes com `python manage.py migrate`. Isso inclui as migrações do `customer_portal` (0001 a 0004, incluindo as contas do Portal).

# Q360 Linha Saúde — Manual de utilização e testes

Data: 31/10/2026

## 1. Contextualização

O Q360 Linha Saúde é uma plataforma web para seguradoras gerirem seguros de saúde do princípio ao fim: configurar produtos e planos, registar clientes, cotar, subscrever, emitir a apólice e acompanhar pagamentos e sinistralidade. Este manual explica cada área na ótica de quem a usa e, em cada uma, indica o que testar e o resultado esperado.

O sistema tem duas áreas no mesmo endereço, que partilham os mesmos dados:

- **Plataforma (backoffice)** — usada pela equipa da seguradora: administradores, gestores de subscrição e subscritores.
- **Portal Cliente** — usado pelo cliente final para consultar cotações, apólices, pagamentos e coberturas, fazer pedidos e trocar mensagens. O cliente pede; quem decide é sempre a plataforma.

O percurso de um seguro no Q360 segue esta ordem:

1. O **subscritor** cria a cotação: escolhe o cliente, o produto/plano, a data de início e as pessoas a segurar, e calcula o prémio.
2. A cotação é submetida para **subscrição**. O gestor analisa e aprova ou recusa com motivo.
3. Uma cotação aprovada aparece no Portal Cliente como «Aprovada — aguarda assinatura».
4. Depois da assinatura presencial, regista-se quem assinou, em que qualidade e quando; a cotação passa a **apólice**.
5. A apólice fica a aguardar o 1.º pagamento e só fica **ativa** depois de ele ser registado.
6. A partir daí acompanham-se prestações, inclusões de beneficiários, renovação e sinistralidade.

### Perfis de utilizador

| Perfil | O que faz no sistema |
| --- | --- |
| Administrador | Tudo, incluindo utilizadores, aprovações, modelos de documentos e configuração |
| Gestor de Subscrição | Analisa, aprova ou recusa cotações; configura produtos, tarifação, fórmulas, regras e parâmetros |
| Subscritor | Regista clientes, cria, calcula e submete cotações |
| Cliente (Portal) | Consulta os seus dados, faz pedidos e envia mensagens |

## 2. Acesso e preparação do ambiente de testes

Todos os testes são feitos no ambiente local/QA, com dados fictícios, a partir de um navegador. A preparação técnica (feita uma vez pela equipa de desenvolvimento) está em [GUIA_TESTES.md](../GUIA_TESTES.md); quem testa só precisa do endereço e das credenciais abaixo.

### 2.1 Pré-requisitos (equipa técnica)

1. Base de dados atualizada e dados de demonstração carregados: `python manage.py migrate` e `python manage.py seed_demo_data`. O comando cria o tenant «demo-saude» e imprime o seu identificador e os números das apólices/cotações de demonstração — guarde-os.
2. Para ver os códigos de acesso sem usar caixas de correio reais, configure o envio de email para a consola (`EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend`).
3. Backend a correr em http://127.0.0.1:8000 e frontend em http://localhost:5173.

### 2.2 Entrar na Plataforma

1. Abra o navegador e escreva `http://localhost:5173/login`.
2. Preencha o email e a palavra-passe e carregue em **Entrar**.
3. Abre o **Dashboard** com o menu lateral.

Contas de demonstração (palavra-passe `Q360Demo!2026`):

| Perfil | Email | Usar para |
| --- | --- | --- |
| Administrador | admin.demo@q360.local | Administração e consulta geral |
| Gestor de Subscrição | gestor.demo@q360.local | Analisar, aprovar ou recusar cotações |
| Subscritor | subscritor.demo@q360.local | Criar, calcular e submeter cotações |

### 2.3 Entrar no Portal Cliente

1. Abra `http://localhost:5173/portal-cliente/acesso`.
2. Entre com uma conta de cliente de demonstração (palavra-passe inicial `Cliente!Demo2026`). Por exemplo, diana.lopes@demo.q360.local tem só cotações; a cliente Ana Silva tem o cenário completo (apólice ativa, prestações, pedidos e mensagens) — o email está no GUIA_TESTES.md.
3. Para testar o **primeiro acesso**, use «Criar palavra-passe» com a referência da apólice impressa pelo comando de demonstração e o documento correspondente (por exemplo, 541000003LA003 para a Empresa Kilamba).

### 2.4 Ficheiros de teste

Os ficheiros fictícios para carregamentos estão em `docs/ficheiros_teste_modulos` e `docs/modelos_importacao`.

| Ficheiro | Onde usar |
| --- | --- |
| [01_Colaboradores_QA.xlsx](ficheiros_teste_modulos/01_Colaboradores_QA.xlsx) | Importação de colaboradores de uma organização (30 registos) |
| [02_Evidencia_QA_FICTICIA.pdf](ficheiros_teste_modulos/02_Evidencia_QA_FICTICIA.pdf) | Envio de documento/evidência de um membro |
| [03_Papel_Timbrado_QA.pdf](ficheiros_teste_modulos/03_Papel_Timbrado_QA.pdf) | Papel timbrado em Documentos e marca |
| [04_Modelo_Proposta_QA.docx](ficheiros_teste_modulos/04_Modelo_Proposta_QA.docx) | Modelo Word de proposta em Documentos e marca |
| [01_Modelo_Actuarial_Referencia_SAU_SAG.xlsx](modelos_importacao/01_Modelo_Actuarial_Referencia_SAU_SAG.xlsx) | Importar modelo atuarial em Tarifação |
| [08_Exemplo_Coberturas_TESTE.xlsx](modelos_importacao/08_Exemplo_Coberturas_TESTE.xlsx) | Importação de coberturas |
| [10_Exemplo_Tabela_Referencia_TESTE.xlsx](modelos_importacao/10_Exemplo_Tabela_Referencia_TESTE.xlsx) | Tabelas de referência |
| [04_Exemplo_Historico_Sinistros_36_Meses_TESTE.xlsx](modelos_importacao/04_Exemplo_Historico_Sinistros_36_Meses_TESTE.xlsx) | Importação de sinistros |
| [06_Exemplo_Historico_Premios_36_Meses_TESTE.xlsx](modelos_importacao/06_Exemplo_Historico_Premios_36_Meses_TESTE.xlsx) | Importação de prémios |

## 3. Navegação geral

O menu lateral da Plataforma mostra apenas as áreas a que o seu perfil tem acesso. No canto superior direito ficam o sino de notificações, a pesquisa e o seu perfil (com a opção de sair).

### 3.1 Menu da Plataforma

| Item | Para que serve | Quem vê |
| --- | --- | --- |
| Dashboard | Indicadores, evolução semanal/mensal e funil de cotações | Todos |
| Notificações | Lista completa das notificações (o sino mostra só as recentes) | Todos |
| Produtos | Catálogo de produtos e planos, com comparação lado a lado | Todos |
| Cotações | Lista de cotações e assistente de nova cotação | Quem pode criar cotações |
| Clientes | Proponentes (particulares e organizações), agregados e importações | Todos |
| Atendimento | Pedidos e mensagens vindos do Portal Cliente | Todos |
| Tarifação | Cálculo de prémio avulso | Quem pode calcular |
| Elegibilidade | Avaliar se uma pessoa pode aderir a um plano | Quem pode calcular |
| Subscrição | Fila de cotações submetidas para decisão e emissão de apólice | Gestor e Administrador |
| Sinistralidade | Importação de sinistros/prémios e indicadores | Quem pode consultar auditoria |
| Apólices | Apólices emitidas, pessoas seguradas, inclusões e ciclo de vida | Todos |
| Cobranças | Prestações por pagar, em atraso e registo de pagamentos | Todos (registar exige aprovação) |
| Auditoria | Registo das ações feitas no sistema | Quem pode consultar auditoria |

### 3.2 Administração

A área **Administração** está disponível para o Administrador e, em parte, para o Gestor de Subscrição.

| Grupo | Área | Para que serve | Quem vê |
| --- | --- | --- | --- |
| Organização | Utilizadores e perfis | Contas de colaboradores, perfis e permissões | Administrador |
| Organização | Aprovações pendentes | Fila única de configurações a aguardar decisão | Administrador |
| Negócio | Produtos e planos | Coberturas, capitais, co-participações, carências, exclusões e rede | Administrador e Gestor |
| Negócio | Tarifação | Tarifa de cada produto, passo a passo, com simulador e importação atuarial | Administrador e Gestor |
| Negócio | Fórmulas | Editor de fórmulas de tarifação, com teste e simulação | Administrador e Gestor |
| Negócio | Regras de negócio | Regras de elegibilidade, aceitação, validação e fluxo | Administrador e Gestor |
| Negócio | Parâmetros | Valores globais usados na cotação e renovação | Administrador e Gestor |
| Negócio | Modelos de partida | Adotar modelos do fornecedor como ponto de partida | Administrador |
| Comunicação | Documentos e marca | Modelos de documento, textos, cláusulas e identidade visual | Administrador |

### 3.3 Menu do Portal Cliente

Resumo, Cotações, Apólices, Comparar planos, Coberturas e elegibilidade, Verificar elegibilidade, Beneficiários, Inclusões propostas, Pagamentos, Documentos, Pedidos, Mensagens, Notificações, Renovações e Ajuda.

### Teste rápido de acesso

1. Entre como Administrador e confirme que vê o Dashboard e o menu completo, incluindo Administração.
2. Saia e entre como Subscritor: deve ver **Cotações**, mas não **Subscrição** nem **Administração**.
3. Saia e entre como Gestor de Subscrição: deve ver **Subscrição** e, em Administração, só as áreas do grupo Negócio permitidas.
4. Escreva um email ou palavra-passe errados: deve aparecer uma mensagem de erro clara e a sessão não abre.

**Esperado:** cada perfil vê apenas o que pode usar. Se abrir pelo endereço uma área que não lhe pertence (por exemplo `/administracao/utilizadores` como Gestor), deve ser redirecionado.

## 4. Módulos do sistema

Cada módulo explica o que a área faz e traz uma tabela de testes. Preencha a coluna **Estado** com Passou, Falhou ou Sem ecrã, e guarde uma captura de ecrã sempre que algo falhar.

### 4.1 Produtos, planos e coberturas

Um **produto** é o seguro de saúde vendido pela seguradora (por exemplo, saúde individual ou de grupo). Cada produto tem **planos** (por exemplo, Família Plus), e cada plano tem **coberturas** com capitais, limites, co-participações, períodos de carência, exclusões e rede de prestadores. Os estados possíveis são Ativo, Rascunho, Inativo e Arquivado.

No menu **Produtos** consulta-se o catálogo e compara-se até três produtos lado a lado. A configuração faz-se em **Administração → Produtos e planos**.

| # | Passo | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Em Produtos, abra um produto de demonstração | Vê nome, estado, descrição e planos | |
| 2 | Abra um plano | Vê as coberturas com capitais, limites e carências | |
| 3 | Em Comparar produtos e planos, escolha dois produtos e um plano de cada | Aparece uma matriz com coberturas, inclusão, carência e limites; sem dados inventados | |
| 4 | Em Administração → Produtos e planos, filtre por Rascunhos | A lista mostra só rascunhos | |
| 5 | Crie um produto de teste (nome claramente identificável) e guarde como rascunho | O produto aparece na lista com estado Rascunho | |
| 6 | Tente validar/publicar o rascunho incompleto | O ecrã indica os campos em falta e não publica | |
| 7 | Importe 08_Exemplo_Coberturas_TESTE.xlsx | Aparece uma pré-visualização com linhas válidas e erros antes de confirmar | |
| 8 | Abra uma cobertura e edite um limite | Os detalhes abrem e a alteração fica guardada | |

### 4.2 Clientes, agregados e beneficiários

Um **cliente** (proponente) pode ser um particular ou uma organização. Num particular, o agregado tem um **titular** e os seus familiares (cônjuge, filhos, ascendentes). Numa organização, a pessoa responsável/tomadora é importada como um único membro **TITULAR**, com nome, data de nascimento, sexo, e-mail e telefone. Os colaboradores são registados como **COLABORADOR** e cada um pode ter familiares opcionais no seu próprio agregado; o titular da organização não é associado automaticamente a esses agregados. O detalhe do cliente mostra também o histórico de cotações.

| # | Passo | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Em Clientes, crie um proponente particular com dados fictícios | O cliente aparece na lista | |
| 2 | No cliente, adicione o titular, um cônjuge, um filho e um ascendente | Cada pessoa aparece com parentesco e data de nascimento | |
| 3 | Tente adicionar um segundo titular ou um dependente sem titular | O ecrã explica a regra e não guarda | |
| 4 | Crie um proponente organização e adicione um colaborador | A relação é Colaborador, sem pedir parentesco | |
| 5 | Abra o agregado desse colaborador e adicione familiares | O colaborador é o titular; cada familiar tem o seu parentesco | |
| 6 | Registe um filho mais velho do que o pai | O ecrã rejeita ou sinaliza o caso | |
| 7 | Na organização, use Importar com 01_Colaboradores_QA.xlsx | A pré-visualização mostra 30 linhas e os erros; após confirmar, os registos aparecem na lista | |
| 8 | Abra um cliente com cotações | O Histórico de cotações mostra número, plano, estado, data e prémio | |

Nota: criar uma organização exige setor e região atuariais. Se as listas vierem vazias, o modelo atuarial ainda não está publicado (ver 4.9).

### 4.3 Elegibilidade e documentos

A **elegibilidade** verifica se uma pessoa pode aderir a um plano, de acordo com as regras configuradas (idade, parentesco, carências, documentos). O resultado indica a decisão, os motivos e os requisitos pendentes. Os documentos enviados são analisados em **Atendimento → Documentos**.

| # | Passo | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Em Elegibilidade, escolha um membro e um plano e carregue em Avaliar | Aparece a decisão, os motivos e os requisitos | |
| 2 | Repita com uma pessoa fora do limite de idade | O resultado é negativo e explica a restrição | |
| 3 | Se for pedido documento, envie 02_Evidencia_QA_FICTICIA.pdf | O documento fica com nome, estado e data de envio | |
| 4 | Em Atendimento → Documentos, aprove o documento | A pendência fica resolvida | |
| 5 | Noutro teste, recuse um documento sem motivo e depois com motivo | Sem motivo não deixa recusar; com motivo regista a recusa | |

### 4.4 Cotações

A cotação é a proposta de preço para um cliente. Cria-se em **Cotações → Nova**, num assistente por passos: cliente e plano, pessoas a segurar e cálculo do prémio. A lista filtra por estado: Rascunhos, Calculadas, Em revisão, Aprovadas, Convertidas, Rejeitadas, Expiradas e Canceladas, e mostra o prémio anual.

| # | Passo | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Como Subscritor, abra Cotações → Nova e escolha cliente, plano e data de início | Avança para o passo das pessoas | |
| 2 | Adicione o titular e os membros elegíveis | Os membros aparecem com idade e parentesco | |
| 3 | Saia a meio e volte a abrir a cotação em Continuar | Retoma no passo onde ficou | |
| 4 | Calcule o prémio | Aparece o total, os componentes do preço e eventuais avisos | |
| 5 | Confirme na lista | A cotação aparece como Calculada, com o prémio anual | |
| 6 | Tente submeter com um requisito pendente | O ecrã explica o que falta e não submete | |
| 7 | Resolva o requisito e submeta | A cotação passa a Em revisão | |

### 4.5 Subscrição e emissão da apólice

Em **Subscrição**, o Gestor vê a fila das cotações submetidas, abre cada uma, confere cliente, membros e preço, e aprova ou recusa. Descontos acima do permitido também são aprovados aqui. Numa cotação aprovada aparece o painel **Emitir apólice**, onde se regista a assinatura (nome, tipo e número de documento, qualidade do assinante, data/hora), o prazo em meses, a periodicidade de pagamento e, opcionalmente, o pagamento da 1.ª prestação.

| # | Passo | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Como Gestor, abra Subscrição e localize a cotação submetida | A cotação aparece na fila | |
| 2 | Abra-a e aprove | Fica Aprovada e aparece no Portal Cliente como «Aprovada — aguarda assinatura» | |
| 3 | Noutra cotação, recuse com motivo | Fica Rejeitada; o motivo é visível para o Subscritor | |
| 4 | Numa cotação com desconto pendente, aprove ou rejeite o desconto | A decisão fica registada | |
| 5 | Na cotação aprovada, preencha Emitir apólice sem pagamento | A apólice é criada a aguardar o 1.º pagamento | |
| 6 | Repita noutra cotação marcando Registar já o pagamento da 1.ª prestação | A apólice fica ativa | |
| 7 | Tente emitir com um campo obrigatório vazio | O formulário indica o campo e não emite | |

### 4.6 Apólices

Em **Apólices** consultam-se as apólices emitidas, com condições, pessoas seguradas e prestações. No detalhe gerem-se as inclusões de beneficiários (com aceitação ou recusa fundamentada), a remoção de pessoas, o cancelamento e o ciclo de incumprimento: aviso formal, suspensão e terminação.

| # | Passo | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Abra a apólice emitida em 4.5 | Vê estado, datas, pessoas seguradas e prestações | |
| 2 | Proponha a inclusão de um beneficiário e registe a aceitação | A pessoa passa a constar da apólice | |
| 3 | Noutra inclusão, registe a recusa com motivo curto (menos de 10 caracteres) | O botão fica inativo até o motivo ter 10 ou mais caracteres | |
| 4 | Numa prestação em atraso, registe aviso formal com referência e novo prazo | O aviso fica registado | |
| 5 | Suspenda por incumprimento uma apólice ativa | O estado passa a Suspensa | |
| 6 | Tente terminar antes de decorrer o prazo formal | O sistema recusa e explica a condição | |

### 4.7 Cobranças

Em **Cobranças** vêem-se todas as prestações: pagas, por pagar e em atraso. Registar um pagamento exige permissão de aprovação.

| # | Passo | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Abra Cobranças | Lista as prestações com estado, vencimento e valor em Kz | |
| 2 | Registe o 1.º pagamento da apólice que aguardava pagamento | A prestação fica paga e a apólice fica ativa | |
| 3 | Entre como Subscritor e tente registar um pagamento | A ação não está disponível | |

### 4.8 Atendimento

**Atendimento** é o lado da Plataforma que responde ao Portal Cliente, com três separadores: **Pedidos**, **Conversas** e **Documentos**. Os pedidos seguem o percurso Aberto → Em análise → A aguardar o cliente / Aprovado / Rejeitado → Concluído; passar a Rejeitado ou A aguardar o cliente exige nota. O ecrã mostra pedidos abertos, tempo médio em aberto e o pedido mais antigo.

| # | Passo | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Abra Atendimento → Pedidos | Vê os pedidos e a coluna Criado há | |
| 2 | Abra um pedido Aberto e passe-o a Em análise | O estado muda; o cliente recebe notificação no Portal | |
| 3 | Passe-o a A aguardar o cliente sem nota | O sistema exige a nota | |
| 4 | Em Conversas, responda a uma mensagem | A resposta aparece no Portal do cliente | |

### 4.9 Tarifação e simulação de preço

A **Tarifação** define como se calcula o prémio de cada produto. Em **Administração → Tarifação** há a importação do modelo atuarial (prémios base, premissas por cobertura, fatores por idade/sexo, regiões e setores) e a configuração por produto, passo a passo, com simulador. O item **Tarifação** do menu principal calcula um prémio avulso. Uma configuração importada entra como rascunho e só fica ativa depois de submetida e aprovada por outra pessoa.

| # | Passo | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Em Importar modelo atuarial, carregue 01_Modelo_Actuarial_Referencia_SAU_SAG.xlsx com data de início e escolha Importar como rascunho | Aparece a versão criada e um resumo (cerca de 94 linhas de prémios, 17 premissas, 17 fatores) | |
| 2 | Submeta o rascunho para aprovação | Aparece em Aprovações pendentes | |
| 3 | Tente aprovar com o mesmo utilizador que o criou | O sistema recusa | |
| 4 | Aprove com outro Administrador | A versão fica ativa; setores e regiões ficam disponíveis ao criar organizações | |
| 5 | Em Tarifação por produto, escolha um produto e use o simulador | Aparecem os componentes do preço | |

### 4.10 Fórmulas, regras e parâmetros

**Fórmulas** compõem o cálculo com valores, taxas e campos, e podem ser testadas antes de guardar. **Regras de negócio** definem elegibilidade, aceitação, validação e fluxo. **Parâmetros** guardam valores globais (por exemplo, prazos e limites) usados na cotação e renovação. As alterações seguem a mesma lógica de rascunho, aprovação e histórico de versões.

| # | Passo | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Em Fórmulas, crie uma fórmula simples e use Testar/Simular | Mostra o resultado com os valores de teste | |
| 2 | Escreva uma fórmula inválida (parêntese por fechar) | O editor indica o erro e não guarda | |
| 3 | Em Regras de negócio, crie uma regra com uma condição e valide-a | A validação mostra o resultado antes de submeter | |
| 4 | Em Parâmetros, altere um valor dentro dos limites num rascunho | Fica nova versão no histórico | |
| 5 | Tente um valor fora dos limites | O ecrã recusa e indica os limites | |

### 4.11 Utilizadores, documentos e marca

| # | Passo | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Em Utilizadores e perfis, crie um utilizador de teste com perfil Subscritor | Aparece na lista e consegue entrar | |
| 2 | Altere o perfil e depois desative a conta | A conta desativada deixa de conseguir entrar | |
| 3 | Em Documentos e marca, carregue 03_Papel_Timbrado_QA.pdf e 04_Modelo_Proposta_QA.docx | Os ficheiros ficam associados ao modelo de proposta | |
| 4 | Gere a proposta de uma cotação de teste | O documento sai com a marca e os dados da cotação | |

Não altere as contas de demonstração principais.

### 4.12 Sinistralidade

A **Sinistralidade** mostra a experiência de sinistros e prémios de uma organização, a partir de históricos importados de 36 meses.

| # | Passo | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Importe 04_Exemplo_Historico_Sinistros_36_Meses_TESTE.xlsx para a organização de teste | A pré-validação mostra linhas válidas e erros antes de confirmar | |
| 2 | Importe 06_Exemplo_Historico_Premios_36_Meses_TESTE.xlsx | Os prémios ficam associados à mesma organização | |
| 3 | Abra o resumo da organização | Aparecem os indicadores (por exemplo, rácio de sinistralidade) | |

### 4.13 Dashboard, notificações, pesquisa e auditoria

| # | Passo | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | No Dashboard, alterne Semanal/Mensal | O gráfico e o funil atualizam; o funil bate com os estados das cotações | |
| 2 | Abra o sino e depois Notificações | As notificações recentes aparecem e podem ser marcadas como lidas | |
| 3 | Pesquise pelo número de uma cotação de teste | Aparece nos resultados e abre o detalhe | |
| 4 | Em Auditoria, filtre as ações de hoje | Vê utilizador, entidade, data e descrição das ações feitas nos testes | |

### 4.14 Portal Cliente

| # | Passo | Resultado esperado | Estado |
| --- | --- | --- | --- |
| 1 | Entre com a conta da Ana Silva | Abre o Resumo com alertas de pagamento em atraso e cotação a expirar | |
| 2 | Erre a palavra-passe 5 vezes | A conta fica bloqueada 30 minutos | |
| 3 | Faça o primeiro acesso da Empresa Kilamba com o código recebido | Define a palavra-passe (10+ caracteres) e entra | |
| 4 | Tente a palavra-passe 1234567890 | É recusada com explicação; o código continua válido | |
| 5 | Percorra Cotações, Apólices, Beneficiários, Pagamentos e Documentos | Os dados batem com a Plataforma; o rascunho não aparece | |
| 6 | Em Pedidos, crie um pedido de Alteração de dados | Aparece como Aberto e surge em Atendimento na Plataforma | |
| 7 | Crie um 2.º pedido de renovação para a mesma apólice | É recusado (só um aberto) | |
| 8 | Como Empresa Kilamba, em Renovações, carregue em Pedir renovação | O pedido é criado (a apólice termina em 45 dias) | |
| 9 | Numa cotação aprovada, carregue em Aceitar a cotação | É criado o pedido de aceitação | |

## 5. Cenário de teste ponta a ponta

Este cenário percorre o ciclo completo de um seguro, passando por três perfis e pelo Portal Cliente. Execute-o depois de os módulos individuais passarem; cada passo depende do anterior.

| # | Perfil | Onde | Ação | Resultado esperado | Estado |
| --- | --- | --- | --- | --- | --- |
| 1 | Subscritor | Clientes | Criar o particular «Teste E2E» com titular, cônjuge e um filho | Agregado com 3 pessoas | |
| 2 | Subscritor | Elegibilidade | Avaliar o filho no plano Família Plus | Elegível ou requisitos indicados | |
| 3 | Subscritor | Cotações → Nova | Cotar o plano Família Plus para o agregado e calcular | Prémio anual em Kz com componentes | |
| 4 | Subscritor | Cotações | Submeter | Estado Em revisão | |
| 5 | Gestor | Subscrição | Abrir e aprovar | Estado Aprovada | |
| 6 | Cliente | Portal → Cotações | Ver a cotação | «Aprovada — aguarda assinatura» | |
| 7 | Gestor | Subscrição → Emitir apólice | Registar assinatura, prazo 12 meses, periodicidade, sem pagamento | Apólice a aguardar 1.º pagamento | |
| 8 | Administrador | Cobranças | Registar o 1.º pagamento | Apólice ativa | |
| 9 | Cliente | Portal → Apólices e Pagamentos | Consultar | Apólice ativa e prestação paga | |
| 10 | Cliente | Portal → Pedidos | Pedir inclusão de um beneficiário | Pedido Aberto | |
| 11 | Administrador | Atendimento | Analisar e aprovar o pedido | Cliente notificado; estado atualizado | |
| 12 | Administrador | Auditoria | Filtrar as ações de hoje | Todos os passos acima aparecem registados | |

Use dados fictícios (por exemplo, emails terminados em @demo.q360.local) para não enviar mensagens a pessoas reais.

## 6. Como reportar um problema

Quando um passo falhar, pare nesse módulo, preencha a ficha abaixo e envie-a à equipa com uma captura de ecrã sem dados sensíveis. Copie o texto exato da mensagem de erro.

```text
Módulo e n.º do passo:
Perfil usado:
Ecrã/menu aberto:
O que fiz:
Resultado esperado:
Resultado obtido:
Estado: PASSOU / FALHOU / SEM ECRÃ
Mensagem de erro (texto exato):
Captura de ecrã:
Data e hora:
```

Marque **Sem ecrã** quando a função não existir na interface; não a substitua por outra via (consola, API ou ferramentas técnicas).

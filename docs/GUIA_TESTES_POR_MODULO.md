# Guia de testes pela interface — Q360 Linha Saúde

Este guia é para testar **nos ecrãs da aplicação**, com rato e teclado. Não precisas de abrir documentação técnica, consola do navegador, comandos de API ou ferramentas como Postman. Se uma funcionalidade não tiver ecrã, fica registada como **Sem ecrã identificado** e avançamos para a próxima que possas testar visualmente.

Fazemos um módulo de cada vez. Em cada passo, anota o resultado e tira uma captura de ecrã quando houver sucesso, erro ou bloqueio. Usa apenas o ambiente local/QA e dados fictícios. Preparação do ambiente e credenciais estão em [GUIA_TESTES.md](../GUIA_TESTES.md); essa preparação técnica serve apenas para iniciar a aplicação. A execução dos testes descritos aqui é pela interface.

## Como vamos trabalhar

1. Abre a aplicação em `http://localhost:5173` e entra com o perfil indicado no passo.
2. Usa o menu visível. Os nomes abaixo são os que constam no guia atual; se o teu menu mostrar outro nome, segue o equivalente e anota-o.
3. Faz apenas os passos do módulo atual. Não avances se o resultado esperado falhar.
4. Regista o estado como **Passou**, **Falhou** ou **Sem ecrã**. Envia-me o resultado e o texto exato de qualquer erro; eu guio o passo seguinte.

Perfis de demonstração (palavra-passe `Q360Demo!2026`):

| Perfil | Utilizador | Usar para |
|---|---|---|
| Administrador | `admin.demo@q360.local` | Administração e consulta geral |
| Gestor de Subscrição | `gestor.demo@q360.local` | Analisar, aprovar ou recusar cotações |
| Subscritor | `subscritor.demo@q360.local` | Criar e submeter cotações |

## Ficheiros fictícios para os passos de upload

Usa estes ficheiros apenas no ambiente de QA. São exemplos de teste, não documentos válidos de clientes.

| Ficheiro | Usar no ecrã de |
|---|---|
| [01_Colaboradores_QA.xlsx](ficheiros_teste_modulos/01_Colaboradores_QA.xlsx) | Importação de colaboradores/população de uma organização; contém 30 registos fictícios |
| [02_Evidencia_QA_FICTICIA.pdf](ficheiros_teste_modulos/02_Evidencia_QA_FICTICIA.pdf) | Upload de evidência documental de um membro fictício |
| [03_Papel_Timbrado_QA.pdf](ficheiros_teste_modulos/03_Papel_Timbrado_QA.pdf) | Fundo/papel timbrado de proposta, se o ecrã permitir configurar modelos |
| [04_Modelo_Proposta_QA.docx](ficheiros_teste_modulos/04_Modelo_Proposta_QA.docx) | Modelo Word de proposta, se o ecrã permitir gerir modelos |
| [01_Modelo_Actuarial_Referencia_SAU_SAG.xlsx](modelos_importacao/01_Modelo_Actuarial_Referencia_SAU_SAG.xlsx) | Importação atuarial, caso exista opção visível no módulo de tarifação |
| [08_Exemplo_Coberturas_TESTE.xlsx](modelos_importacao/08_Exemplo_Coberturas_TESTE.xlsx) | Importação de coberturas, caso exista opção visível |
| [10_Exemplo_Tabela_Referencia_TESTE.xlsx](modelos_importacao/10_Exemplo_Tabela_Referencia_TESTE.xlsx) | Tabelas de referência, caso exista opção visível |
| [04_Exemplo_Historico_Sinistros_36_Meses_TESTE.xlsx](modelos_importacao/04_Exemplo_Historico_Sinistros_36_Meses_TESTE.xlsx) | Importação de sinistros |
| [06_Exemplo_Historico_Premios_36_Meses_TESTE.xlsx](modelos_importacao/06_Exemplo_Historico_Premios_36_Meses_TESTE.xlsx) | Importação de prémios |

## Módulo 0 — Entrada e confirmação do ambiente

1. Abre `http://localhost:5173/login`.
2. Entra como Administrador com as credenciais da tabela.
3. Confirma que aparece o ecrã inicial e que o menu lateral/superior está disponível.
4. Sai da sessão e entra como Subscritor; confirma que consegues abrir **Cotações**.
5. Sai e entra como Gestor de Subscrição; confirma que consegues abrir **Subscrição**.

**Esperado:** cada perfil entra e vê as áreas necessárias ao seu trabalho. Se não conseguires entrar, para aqui e envia o texto do erro e uma captura sem dados sensíveis.

Regista: `Ambiente: ____ | Administrador: ____ | Subscritor: ____ | Gestor: ____`.

## Módulo 1 — Produtos, coberturas e planos

Entra como Administrador e abre **Produtos / Planos / Coberturas** (ou as entradas equivalentes que apareçam no menu).

1. Abre um produto existente de demonstração e confirma nome, estado e detalhes.
2. Abre as coberturas do produto. Confirma que consegues consultar uma cobertura e os seus limites/condições.
3. Abre um plano associado. Confirma coberturas, capitais/limites e estado do plano.
4. Se existir botão **Novo/Criar**, cria um registo com nome/código de teste claramente identificável, preenche os campos obrigatórios e guarda como rascunho.
5. Se existir validação/publicação, tenta validar o rascunho. Lê a lista de erros; corrige apenas o que for necessário para confirmar que a validação muda.
6. Se existir importação de coberturas, carrega `08_Exemplo_Coberturas_TESTE.xlsx`, confere o preview e cancela ou confirma apenas no tenant de QA.

**Esperado:** consegues abrir e compreender a configuração do plano; validações apontam campos em falta. Não publiques alterações comerciais partilhadas sem estarmos a testar num tenant isolado.

**Regista:** produto/plano escolhido, estado e campos que a interface permite editar. Se não existir criação/edição, anota **consulta apenas**.

## Módulo 2 — Clientes, proponentes e beneficiários

Entra como Subscritor ou Administrador e abre **Clientes**.

### 2.1 Proponente individual

1. Abre **Novo cliente/proponente** e escolhe o tipo individual.
2. Preenche os dados com valores fictícios, válidos e únicos; guarda.
3. Dentro do cliente, abre **Beneficiários/Membros** e adiciona o titular.
4. Adiciona um cônjuge, um filho e um ascendente, se os campos estiverem disponíveis.
5. Tenta guardar um dependente sem titular ou um segundo titular, se o formulário permitir. A interface deve explicar a regra e impedir a inconsistência.
6. Confirma que o parentesco e a data de nascimento ficam visíveis no agregado.

### 2.2 Proponente organização

1. Em **Novo cliente/proponente**, escolhe organização/empresa e guarda uma organização fictícia.
2. Abre a organização e escolhe **Adicionar colaborador**.
3. Confirma que a relação do colaborador é **Colaborador**. Não deve ser necessário classificá-lo como titular ou filho para o registar na empresa.
4. Abre/cria o agregado desse colaborador e confirma que **o colaborador é o titular daquele agregado**.
5. Adiciona familiares do agregado usando as opções disponíveis, por exemplo pai, mãe, filho, ascendente, descendente ou cônjuge. A relação familiar pertence ao agregado do colaborador, não à relação do colaborador com a empresa.
6. Cria um segundo colaborador e um segundo agregado. Confirma que cada agregado tem o seu próprio colaborador titular.
7. Verifica idades de pais/filhos e tenta um caso claramente incompatível. A interface deve rejeitar ou sinalizar o caso conforme a regra configurada.

**Esperado:** todos os colaboradores da organização têm relação laboral **Colaborador**; dentro de cada agregado, o titular é o colaborador e os familiares têm o seu parentesco próprio. Guarda captura dos formulários e da lista final.

### 2.3 Importação de colaboradores

1. Na organização de QA, abre **Importar membros/colaboradores** (se existir no ecrã de Clientes).
2. Seleciona `01_Colaboradores_QA.xlsx`.
3. Analisa a pré-visualização: total de linhas, erros e relação dos registos.
4. Confirma a importação apenas depois de a prévia estar correta.
5. Volta à lista e confirma os registos importados.

Se não existir botão de importação, anota **Sem ecrã de importação** e seguimos sem carregar o ficheiro.

## Módulo 3 — Elegibilidade e documentos

Abre **Elegibilidade** e escolhe um cliente/membro fictício e um produto/plano de demonstração.

1. Faz uma avaliação com dados dentro das regras e carrega em **Avaliar/Verificar**.
2. Regista o resultado, os motivos e os requisitos que aparecem no ecrã.
3. Repete com uma pessoa que falhe uma condição evidente (por exemplo, idade fora do limite mostrado). Confirma que o resultado explica a restrição.
4. Se o resultado pedir documento, abre o perfil do membro e procura **Documentos/Enviar evidência**.
5. Carrega `02_Evidencia_QA_FICTICIA.pdf` como documento de teste. Confirma nome, estado e data de submissão.
6. Se existir fila de análise, abre como perfil autorizado e aprova; repete com rejeição e motivo num segundo teste fictício.

**Esperado:** a decisão e os motivos são apresentados no ecrã; o documento só resolve a pendência depois de analisado/aprovado. Se não houver ação de avaliação ou análise documental na interface, regista essa etapa como **Sem ecrã**.

## Módulo 4 — Cotações, cálculo e decisão

### Criar e submeter

1. Entra como Subscritor e abre **Cotações → Nova**.
2. Escolhe o proponente de teste, produto/plano e data de início.
3. Adiciona o titular (no caso organização, o colaborador titular do agregado) e os membros elegíveis.
4. Guarda a cotação e confirma que aparece na lista com estado de rascunho.
5. Carrega em **Calcular preço**. Regista total, componentes, avisos e eventuais documentos/requisitos.
6. Abre a explicação do preço se houver essa ação e confirma que os valores aparecem associados à cotação.
7. Tenta submeter com uma pendência. Confirma se o ecrã explica o que falta. Resolve os requisitos e submete.

### Aprovar e rejeitar

8. Sai e entra como Gestor de Subscrição. Abre **Subscrição** e localiza a cotação submetida.
9. Abre os detalhes, confere proponente, membros e preço; aprova uma cotação de teste.
10. Para outro rascunho submetido, escolhe **Rejeitar/Recusar** e escreve um motivo de teste.
11. Volta ao Subscritor e confirma os estados e o motivo visíveis no histórico/detalhe.
12. Se existirem ações de duplicar, comparar cenários, ajustar preço ou gerar proposta, testa cada ação em cotação fictícia e confirma o resultado no ecrã.

**Esperado:** o rascunho pode ser calculado; a cotação com bloqueios não é submetida sem os requisitos; gestor consegue aprovar e rejeitar com motivo; a decisão fica visível no histórico.

## Módulo 5 — Administração e configuração de negócio

Entra como Administrador. Abre **Administração** e percorre apenas opções que estejam visíveis. Os nomes abaixo são áreas a procurar, não uma garantia de que cada ecrã já esteja implementado.

Para cada área encontrada, primeiro abre e consulta. Faz alterações apenas num rascunho de QA, com valores simples e reversíveis.

### Utilizadores e permissões

1. Abre a gestão de utilizadores.
2. Confirma lista, perfil e estado de uma conta demo.
3. Se existir formulário, cria utilizador de QA, atribui um perfil, guarda e confirma que aparece na lista.
4. Confirma se o ecrã permite desativar/reativar ou alterar perfil. Não alteres as contas demo principais.

### Parâmetros e regras

1. Procura **Parâmetros**, **Regras de negócio** ou **Configurações**.
2. Abre um parâmetro e regista valor atual, descrição e limites apresentados.
3. Se houver edição, muda um valor num rascunho de QA dentro dos limites; guarda e verifica histórico/versão.
4. Se existir aprovação, tenta aprovar com utilizador diferente do criador.
5. Se houver editor de regras, cria uma regra de teste com condição simples, usa a opção **Validar/Simular** e observa o resultado antes de submeter.

### Fórmulas, tabelas e tarifação

1. Procura ecrãs de **Fórmulas**, **Tabelas de referência**, **Tarifação/Modelo atuarial** ou **Parâmetros do produto**.
2. Se existirem, abre primeiro em modo de consulta e identifica variáveis, campos obrigatórios e ação de pré-visualização/simulação.
3. Só faz upload de `10_Exemplo_Tabela_Referencia_TESTE.xlsx` ou `01_Modelo_Actuarial_Referencia_SAU_SAG.xlsx` se o ecrã mostrar explicitamente esse tipo de importação.
4. Revê a pré-visualização/validação. Não publiques alterações tarifárias sem um tenant de QA isolado e aprovador disponível.

**Regra para este módulo:** se a área não aparecer no menu ou não houver ação visual para editar/testar, anota **Sem ecrã**. Não substituas o passo por comandos nem por chamadas técnicas; avançamos para a área seguinte.

## Módulo 6 — Sinistralidade e importações

Abre **Sinistralidade**.

1. Procura **Importações** e confirma se o ecrã permite escolher cliente e tipo de ficheiro.
2. Se existir modelo para descarregar, usa-o; em alternativa, escolhe o ficheiro de teste correspondente na lista de ficheiros acima.
3. Seleciona o ficheiro de sinistros e observa a pré-validação/preview antes de confirmar.
4. Se a validação estiver correta, importa para a organização fictícia usada no módulo de clientes.
5. Repete para prémios, se o ecrã aceitar esse tipo.
6. Abre **Resumo/Experiência** e regista os indicadores que a interface mostrar.

**Esperado:** a prévia mostra linhas válidas e erros antes da confirmação; o resumo apresenta os dados da organização de teste. Se só houver consulta ou não houver importação visível, regista isso sem tentar outro método.

## Módulo 7 — Portal do cliente

O Portal Cliente abre no mesmo frontend, em `http://localhost:5173`. Usa a conta e palavra-passe de demonstração indicadas em [GUIA_TESTES.md](../GUIA_TESTES.md), sem partilhar palavras-passe reais.

1. No ecrã de acesso do Portal, entra com uma conta de demonstração.
2. Abre **Resumo**, **Cotações**, **Apólices**, **Beneficiários**, **Pagamentos**, **Notificações**, **Pedidos**, **Mensagens** e **Perfil**; confirma que os dados e estados aparecem.
3. Em **Pedidos**, cria um pedido de teste e confirma que aparece com estado aberto.
4. Em **Mensagens**, envia uma mensagem de teste se a ação estiver disponível.
5. Confirma notificações e detalhes da cotação/apólice no portal.

O guia atual indica que o atendimento dos pedidos do portal pelo backoffice ainda não tem ecrã próprio. Se continua assim, podemos testar a criação e visualização pelo portal, mas marcar a transição/decisão interna como **Sem ecrã**.

## Módulo 8 — Apólices e pagamentos

Procura no menu da Plataforma uma área **Apólices** e uma ação de emissão/pagamento.

- Se houver ecrã, abre uma cotação aprovada de teste e segue as instruções visíveis para emitir e registar pagamento; confirma o estado resultante.
- Se o ecrã não existir, regista **Sem ecrã para emissão/pagamento**. O guia atual assinala que emissão de apólice e primeiro pagamento ainda não têm formulário na interface. Neste roteiro não executamos essas operações por outra via.

## Módulo 9 — Auditoria, pesquisa e relatórios

Entra como Administrador e procura **Auditoria**, **Pesquisa** e **Relatórios**.

1. Em **Auditoria**, filtra ou consulta as ações da sessão; confirma utilizador, entidade, data e descrição, se apresentados.
2. Em pesquisa/listagens, procura a cotação pelo nome ou número mostrado na interface.
3. Em **Relatórios**, abre um relatório operacional disponível e verifica se inclui os registos de teste criados.
4. Se alguma área não aparecer ou não permitir pesquisa visual, anota **Sem ecrã**.

## Ficha curta para me reportares cada módulo

```text
Módulo:
Perfil usado:
Ecrã/menu que abri:
Passos concluídos:
Resultado esperado:
Resultado que apareceu:
Estado: PASSOU / FALHOU / SEM ECRÃ
Mensagem de erro (se houver):
Captura de ecrã (se possível):
```

## Começamos agora — Módulo 0

Abre `http://localhost:5173/login`, entra como Administrador e confirma se vês o ecrã inicial. Depois diz-me **quais opções aparecem no menu** e se o login funcionou. A partir do teu ecrã real, guio-te pelo próximo clique e seguimos juntos, um módulo de cada vez.


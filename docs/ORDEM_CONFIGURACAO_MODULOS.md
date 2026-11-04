# Q360 Saúde — Ordem de configuração dos módulos

3 de novembro de 2026

## Objetivo e regras

Uma seguradora fica pronta a cotar seguindo 11 módulos por esta ordem: cada um usa o que o anterior deixou publicado. Hoje os ecrãs são independentes e as dependências só aparecem como erros (ex.: o cliente organização exige setor e região, que só existem depois do modelo atuarial).

Regras que valem para todos os módulos:

- **Cascata de âmbito:** fornecedor → seguradora → produto → plano. A versão de um produto substitui por inteiro a da seguradora nesse produto; as linhas com plano prevalecem sobre as linhas sem plano.
- **Quatro olhos:** quase tudo é rascunho → submeter → outra pessoa aprova → publicado. Quem propõe nunca aprova.
- **Uma só fonte por assunto:** cada coisa configura-se num único sítio (secção «Duplicações excluídas»).
- **Por produto (P):** marca as configurações que aceitam versão própria de um produto; sem marca, só existem ao nível da seguradora ou da plataforma.

## Ordem geral

A plataforma vem sempre primeiro; dentro da seguradora, organização e ponto de partida antes do negócio, e documentos no fim.

| # | Módulo | Quem configura | Depende de | Desbloqueia |
| --- | --- | --- | --- | --- |
| 0 | Plataforma (fornecedor) | Super-administrador + 2.º super-administrador | — | Impostos, câmbio, tabelas e modelos para todas as seguradoras |
| 1 | Organização | Administrador da seguradora | Seguradora criada (0) | Um 2.º administrador para aprovar tudo o resto |
| 2 | Ponto de partida | Administrador | 0, 1 | Produtos, planos e coberturas de base |
| 3 | Coberturas | Administrador | 2 | O que cada plano pode incluir |
| 4 | Produtos e planos | Administrador | 3 | A tarifa e as regras por plano |
| 5 | Tarifação | Administrador (atuário) | 4 | Prémio calculado; setor e região dos clientes organização |
| 6 | Fórmulas | Administrador (atuário) | 5 | Cálculos que tabelas e fatores não cobrem |
| 7 | Regras de negócio | Administrador / gestor de subscrição | 4, 5 | Elegibilidade, aceitação e fluxo das cotações |
| 8 | Parâmetros e serviço | Administrador | 0 (limites) | Validade, limites, atendimento, sinistralidade |
| 9 | Documentos e marca | Administrador | 4–7 | Proposta, textos e identidade visual |
| 10 | Validação final | Subscritor + gestor | 0–9 publicados | Abrir à operação |

## Passos de cada módulo

Dentro de cada módulo, os passos seguem a ordem indicada; cada passo só entra em vigor depois de aprovado por outra pessoa.

### 0. Plataforma (fornecedor)

1. Seguradoras e super-administradores: criar a seguradora e um 2.º super-administrador (aprova o que o 1.º propõe).
2. Parâmetros legais: imposto do selo, taxa ARSEG, maioridade — com a base legal (diploma).
3. Parâmetros de mercado e tetos: câmbio USD/AOA, inflação geral, idade máxima do filho com prova de estudos, comissão de mediação máxima.
4. Valores por omissão e limites: validade da cotação, máximo de beneficiários, validade das ligações, inflação médica, arredondamento.
5. Tabelas de referência (Excel), usadas nas fórmulas.
6. Modelos do fornecedor: produtos, fórmulas, modelo atuarial, bibliotecas de coberturas.

### 1. Organização

1. Utilizadores: pelo menos 2 administradores, gestores de subscrição e subscritores.
2. Permissões por perfil.
3. Aprovação e autonomia: dupla aprovação, quem edita, quem aprova.
4. Aprovação de descontos: a partir de que % e por quem.

### 2. Ponto de partida

1. Adotar um modelo do fornecedor ou «Carregar modelos de mercado»: cria produtos, planos e coberturas de base que depois se ajustam.

### 3. Coberturas

1. Biblioteca de coberturas: base e complementares (Excel ou uma a uma).

### 4. Produtos e planos

1. Produto e planos: segmento (individual/familiar ou grupo), nível, sistema de acesso, opções de participação, agregado, questionário clínico.
2. Coberturas por plano (P): quais, opcionais, disponíveis.
3. Capitais e sublimites (P).
4. Co-participações (P): copagamento, comparticipação, franquias, teto.
5. Períodos de carência (P).
6. Limites de idade (P): entrada mínima e máxima, renovação máxima.
7. Exclusões (P).
8. Rede convencionada (P) e cobertura no estrangeiro (P).

### 5. Tarifação

1. Modelo atuarial SAU/SAG (P), importado por Excel — desbloqueia setor e região dos clientes.
2. Tarifa do produto: prémios de referência (P), fatores (P), agravamentos e descontos (P), ou o modo simples (prémio fixo).
3. Impostos, taxas e encargos.
4. Fracionamento (P) e prémio mínimo (P).
5. Tarifação pela experiência de sinistralidade e comparação de cenários.
6. Simular o produto e confirmar o prémio antes de seguir.

### 6. Fórmulas

1. Fórmulas (P), só onde tabelas e fatores não chegam: parâmetros, valores auxiliares e passos por pessoa ou por cotação; testar e simular antes de submeter.

### 7. Regras de negócio

1. Regras de aceitação (P), por condição e relação.
2. Doenças pré-existentes (P) e análise médica reforçada (P).
3. Regras de grupo (P).
4. Regras «Quando… então…» (P).
5. Renovação e prazos de renovação.
6. Endossos de inclusão.

### 8. Parâmetros e serviço

1. Parâmetros da seguradora, dentro dos limites do fornecedor.
2. Atendimento: metas (SLA) e avaliação de satisfação.
3. Projeções de sinistralidade.

### 9. Documentos e marca

1. Identidade visual: nome, cor, lema, rodapé.
2. Textos e cláusulas.
3. Documentos exigidos ao cliente.
4. Modelos de documento da proposta (pré-visualizar com uma cotação).

## Duplicações excluídas

Quatro assuntos configuram-se hoje em mais de um sítio; esta ordem usa só a fonte indicada e retira as restantes.

| Assunto | Configura-se só em | Sai da ordem (e deve ser retirado ou passar a só consulta) |
| --- | --- | --- |
| Planos | Módulo 4 · Produto e planos | Configuração «Planos de saúde» (product.plans) |
| Idades de entrada e de permanência | Módulo 4 · Limites de idade | Idades nas definições do plano, nas Regras de aceitação e nas regras de elegibilidade antigas |
| Tarifa | Módulo 5 · Modelo atuarial + Tarifação por produto | Ecrã «Tarifação-legado» (tabelas de tarifação e conjuntos de parâmetros antigos) |
| Configurações sem ecrã próprio (SLA, satisfação, endossos, projeções, cenários) | No módulo a que pertencem (7 e 8) | «Configuração avançada» como caminho normal (fica só para suporte) |

Não são duplicações e ficam ambas: a **biblioteca de coberturas** (módulo 3, todas as coberturas da seguradora) e as **coberturas por plano** (módulo 4, quais entram em cada plano); o **prémio mínimo** da apólice (módulo 5) e o do **endosso** (módulo 7), que têm significados diferentes.

## 10. Validação final

A seguradora só abre à operação depois de uma cotação de ensaio percorrer o ciclo completo sem erros.

- [ ] Nada pendente em «Aprovações pendentes».
- [ ] Criar um cliente de ensaio (individual e organização, com setor e região).
- [ ] Verificar a elegibilidade de um titular, de um dependente e de um colaborador.
- [ ] Subscritor cria a cotação, calcula e envia para subscrição; o prémio bate com o simulador do módulo 5.
- [ ] Gestor aprova (outra pessoa), gera a proposta e emite a apólice.
- [ ] Registar o 1.º pagamento; a apólice fica ativa.
- [ ] O cliente entra no portal e vê apólice, coberturas e pagamentos.

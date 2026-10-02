Add-Type -AssemblyName System.IO.Compression.FileSystem

$repoRoot = Split-Path -Parent $PSScriptRoot
$source = Join-Path $repoRoot 'docs\Questionario_Decisoes_Negocio_Simulador_GTE.docx'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('q360-questionnaire-' + [guid]::NewGuid())
$tempDocx = Join-Path ([System.IO.Path]::GetTempPath()) ('Questionario-' + [guid]::NewGuid() + '.docx')
$content = @'
QUESTIONÁRIO DE VALIDAÇÃO COM A ÁREA DE NEGÓCIO
Simulador de Cotações e Análises Técnicas de Saúde (GTE)
Versão revista | 1 de outubro de 2026

1. FINALIDADE E REGRA DE AUTONOMIA
Este documento classifica cada decisão de negócio em quatro dimensões: (1) o que o GTE pode alterar pela interface; (2) o que o sistema mantém como regra estrutural no código; (3) o que ainda não está implementado ou depende de integração; e (4) o que deve ser confirmado antes de usar o simulador com clientes reais.

CONFIGURÁVEL significa que o valor deve ser guardado em parâmetros, tabelas, regras, planos ou templates versionados e editáveis pelo GTE, com auditoria e rollback. Não significa que a interface possa alterar o código do motor.

ESTRUTURAL significa que a interface pode fornecer dados à regra, mas a forma de cálculo, os estados, as validações, os limites de segurança e as integrações permanecem implementados pelo fornecedor.

PENDENTE significa que existe suporte parcial, API ou modelo de dados, mas ainda falta uma tela, uma decisão oficial, uma integração ou uma implementação funcional.

As decisões de prioridade Alta bloqueiam o uso com clientes reais até haver confirmação escrita e configuração dos valores definitivos. Valores de teste, indicativos ou provisórios não são tarifas nem condições comerciais aprovadas.

2. MATRIZ DE DECISÕES DE NEGÓCIO

1.1 FÓRMULA TARIFÁRIA
Decisão: confirmar prémio base, factores por idade, escalão, capital, sistema de acesso e participação.
Classificação: PARCIALMENTE CONFIGURÁVEL.
GTE pela interface: pode alterar prémio base e factores em tabelas e parâmetros versionados.
Hardcoded/fornecedor: a estrutura base x factores + ajustes aditivos, a sequência e o motor de cálculo permanecem no código. Alterar o modelo actuarial exige fornecedor.
Estado/risco: valores actuais são testes; tarifas reais são prioridade Alta.

1.2 VARIÁVEIS QUE DETERMINAM O PRÉMIO
Decisão: confirmar se entram idade, sexo, escalão, capital, acesso, região, profissão, dimensão do grupo e outras variáveis.
Classificação: CONFIGURÁVEL APENAS DENTRO DAS DIMENSÕES SUPORTADAS.
GTE pela interface: pode preencher valores para idade, escalão, categoria, acesso, participação e capitais.
Hardcoded/fornecedor: adicionar uma nova dimensão tarifária, como sexo ou região, exige alteração do motor, do modelo e da interface.
Estado/risco: variáveis actualmente não suportadas não podem ser tarifadas sem desenvolvimento.

1.3 CUSTO DAS COBERTURAS OPCIONAIS
Decisão: confirmar se o custo é percentagem, valor fixo ou função do capital.
Classificação: CONFIGURÁVEL.
GTE pela interface: pode definir o custo por cobertura nos parâmetros do plano/tarifário.
Hardcoded/fornecedor: os tipos de cálculo aceites e a validação do custo pertencem ao motor. Sem parâmetro, a cobertura pode ficar sem custo e gerar aviso.
Estado/risco: prioridade Alta; confirmar comportamento antes de emitir propostas.

1.4 OPÇÕES DE PARTICIPAÇÃO A A E
Decisão: confirmar agravamentos/descontos e se variam por plano.
Classificação: CONFIGURÁVEL COM INVARIANTE ESTRUTURAL.
GTE pela interface: pode alterar os factores A-E por plano ou configuração.
Hardcoded/fornecedor: o código garante que maior participação não pode aumentar o prémio; a validação da ordem económica permanece fixa.
Estado/risco: valores actuais são de partida e precisam de confirmação.

1.5 MOEDA, CÂMBIO E ARREDONDAMENTO
Decisão: confirmar AOA, capital de evacuação em USD, câmbio e arredondamento.
Classificação: MOEDA CONFIGURÁVEL; ARREDONDAMENTO E CÂMBIO PARCIALMENTE ESTRUTURAIS.
GTE pela interface: pode configurar moeda/capital quando suportado e parâmetros de moeda do produto.
Hardcoded/fornecedor: alterar a política de arredondamento ou introduzir conversão cambial exige desenvolvimento; a taxa de câmbio e a sua origem ainda não estão integradas.
Estado/risco: prioridade Alta; AOA e ROUND_HALF_UP a duas casas são provisórios.

1.6 IMPOSTOS, TAXAS E ENCARGOS
Decisão: confirmar imposto de selo, taxas e comissões incluídos no prémio.
Classificação: NÃO IMPLEMENTADO; FUTURAMENTE CONFIGURÁVEL SE O MOTOR FOR EXTENDIDO.
GTE pela interface: actualmente não pode configurar nem calcular estes encargos.
Hardcoded/fornecedor: será necessário desenvolver componentes de imposto/comissão, regras, permissões e apresentação.
Estado/risco: o sistema calcula apenas prémio técnico; prioridade Alta.

1.7 PRÉMIO POR EXPERIÊNCIA DE GRUPOS
Decisão: definir dimensão mínima, fórmula e credibilidade.
Classificação: NÃO IMPLEMENTADO; PREMISSA FUTURA CONFIGURÁVEL.
GTE pela interface: pode registar o tipo de prémio, mas não executar a tarifa por experiência.
Hardcoded/fornecedor: a fórmula actuarial e a lógica de credibilidade exigem desenvolvimento.
Estado/risco: grupos grandes ficam sem esta tarifação; prioridade Média.

2.1 AGRAVAMENTOS E DESCONTOS
Decisão: confirmar percentagem, valor fixo, ordem e limites.
Classificação: TIPOS CONFIGURÁVEIS; ORDEM/LIMITES PARCIALMENTE ESTRUTURAIS.
GTE pela interface: pode aplicar agravamentos/descontos à cotação, indicar motivo e simular o impacto.
Hardcoded/fornecedor: os quatro tipos aceites, a ordem de aplicação e as validações são comportamento do código; limites precisam de política e configuração exposta.
Estado/risco: hoje a ordem é a de registo e não há limite máximo; prioridade Alta.

2.2 MATRIZ DE AUTORIDADE
Decisão: definir quem aplica ajustes e aprova cotações por limite e perfil.
Classificação: LIMITES CONFIGURÁVEIS; PERFIS PARCIALMENTE FIXOS.
GTE pela interface: pode configurar limites de percentagem/valor quando a Authority Policy estiver exposta.
Hardcoded/fornecedor: papéis, permissões e regras de autorização continuam no código; a matriz editável ainda não está concluída.
Estado/risco: sem política, qualquer subscritor pode aplicar qualquer ajuste; prioridade Alta.

2.3 DUPLA APROVAÇÃO DE CONFIGURAÇÕES
Decisão: exigir segunda pessoa para publicar tarifas, regras e parâmetros.
Classificação: NÃO CONFIGURÁVEL ACTUALMENTE.
GTE pela interface: pode publicar com as permissões existentes e deixar auditoria.
Hardcoded/fornecedor: implementar quatro olhos exige novo workflow, estado e permissões.
Estado/risco: administrador publica sozinho; prioridade Média.

2.4 DOENÇAS PREEXISTENTES
Decisão: escolher, por produto/segmento, exclusão, carência, sobreprémio, sublimite ou aceitação integral e respectivos valores.
Classificação: CONFIGURÁVEL.
GTE pela interface: pode seleccionar tratamentos, percentagens, sublimites e carências por plano/pessoa/cotação, dentro do modelo suportado.
Hardcoded/fornecedor: os seis tratamentos aceites e as validações são definidos pelo código; novos tratamentos exigem desenvolvimento.
Estado/risco: valores podem ser decididos caso a caso; prioridade Alta.

2.5 CRITÉRIOS MÉDICOS DE ELEGIBILIDADE
Decisão: definir idades e condições para aceitação, aviso ou análise médica.
Classificação: REGRAS CONFIGURÁVEIS; CATÁLOGO/FLUXO CLÍNICO PENDENTE.
GTE pela interface: pode publicar configurações de regras e critérios no formato suportado.
Hardcoded/fornecedor: novos tipos de decisão, novos dados médicos ou integrações externas exigem código; sem configuração o sistema não bloqueia por critério médico.
Estado/risco: nenhum critério médico real está confirmado; prioridade Alta.

2.6 QUESTIONÁRIO CLÍNICO E EXAMES
Decisão: definir conteúdo, sistema de recolha, idade e capital que exigem exames.
Classificação: LIMITES CONFIGURÁVEIS; RECOLHA CLÍNICA NÃO IMPLEMENTADA.
GTE pela interface: pode configurar quando questionário/exame é exigido.
Hardcoded/fornecedor: criar formulários clínicos, anexos, workflow médico e armazenamento seguro exige desenvolvimento.
Estado/risco: o sistema apenas indica requisitos; prioridade Média.

2.7 PRÉ-AUTORIZAÇÃO E CONTROLO DE SINISTROS
Decisão: decidir se a pré-autorização será gerida neste sistema.
Classificação: NÃO IMPLEMENTADO; APENAS CONDIÇÃO CONFIGURÁVEL.
GTE pela interface: pode registar a condição e apresentá-la na proposta.
Hardcoded/fornecedor: pedidos, aprovação, prestadores, sinistros e workflow exigem novo módulo.
Estado/risco: gestão ocorre fora do simulador; prioridade Baixa.

2.8 RELAÇÕES FAMILIARES E DEPENDENTES
Decisão: aprovar catálogo e comprovativos para titular, cônjuge, filho, ascendente e outros.
Classificação: CATÁLOGO E LIMITES CONFIGURÁVEIS; INVARIANTES DE SEGURANÇA NO CÓDIGO.
GTE pela interface: pode seleccionar relações e configurar limites de idade por plano.
Hardcoded/fornecedor: novos tipos, documentos e relações de dependência exigem extensão do catálogo e validações.
Estado/risco: catálogo actual é demonstração; prioridade Alta.

3.1 ESCALÕES E MATRIZ DE COBERTURAS
Decisão: confirmar Base, Médio, Superior e matriz incluída/opcional/indisponível.
Classificação: CONFIGURÁVEL.
GTE pela interface: pode criar planos, associar coberturas e definir inclusão/optionalidade.
Hardcoded/fornecedor: coberturas base obrigatórias não podem ser desactivadas; essa protecção é estrutural.
Estado/risco: matriz carregada é modelo editável e pode não ser a oferta final; prioridade Alta.

3.2 CAPITAIS E SUBLIMITES
Decisão: confirmar capitais anuais, por acto, por dia e limites de quantidade.
Classificação: CONFIGURÁVEL.
GTE pela interface: pode alterar limites e formas de garantia na configuração do plano.
Hardcoded/fornecedor: formatos de capital válidos, moeda permitida e validações permanecem no código.
Estado/risco: valores são indicativos e há divergências no documento de referência; prioridade Alta.

3.3 PARTICIPAÇÃO DO SEGURADO
Decisão: confirmar copagamentos, percentagens, franquias e tectos por sistema de acesso.
Classificação: CONFIGURÁVEL.
GTE pela interface: pode definir participação por cobertura, rede/reembolso e plano.
Hardcoded/fornecedor: tipos válidos, limites máximos e combinações incompatíveis são validações do código.
Estado/risco: valores actuais são indicativos; prioridade Alta.

3.4 PERÍODOS DE CARÊNCIA
Decisão: confirmar carências por cobertura, individual/grupo e dispensa por acidente.
Classificação: CONFIGURÁVEL.
GTE pela interface: pode configurar dias e regras por plano/cobertura.
Hardcoded/fornecedor: a interpretação da carência, a verificação por data e os estados de cobertura são código.
Estado/risco: valores actuais são indicativos; prioridade Alta.

3.5 CATÁLOGO DE COBERTURAS
Decisão: definir se o catálogo é fechado e se Assistência em Viagem permanece.
Classificação: CONFIGURÁVEL COM COBERTURAS BASE PROTEGIDAS.
GTE pela interface: pode criar, editar, pesquisar, importar, exportar e desactivar coberturas complementares.
Hardcoded/fornecedor: coberturas base não podem ser removidas; novos comportamentos especiais exigem código.
Estado/risco: prioridade Média.

3.6 REDE CONVENCIONADA
Decisão: decidir se haverá prestadores, regiões e tabelas de preços.
Classificação: PARCIALMENTE IMPLEMENTADO.
GTE pela interface: pode registar regiões e obter avisos de rede.
Hardcoded/fornecedor: modelar prestadores, preços acordados e validação geográfica exige novo desenvolvimento.
Estado/risco: actualmente não valida prestador a prestador; prioridade Média.

3.7 EVACUAÇÃO E TRATAMENTO NO ESTRANGEIRO
Decisão: confirmar destinos, moeda, aprovação prévia e câmbio.
Classificação: PARÂMETROS CONFIGURÁVEIS; CÂMBIO ESTRUTURAL/PENDENTE.
GTE pela interface: pode definir destinos, moeda do capital e exigência de aprovação prévia.
Hardcoded/fornecedor: conversão cambial e integração de taxa exigem desenvolvimento.
Estado/risco: destinos actuais são exemplos; prioridade Média.

3.8 IDADES DE ENTRADA E PERMANÊNCIA
Decisão: confirmar limites por plano.
Classificação: CONFIGURÁVEL.
GTE pela interface: pode definir entrada e permanência por plano.
Hardcoded/fornecedor: cálculo de idade, bloqueio e exclusão na renovação são regras do motor.
Estado/risco: valores 60/65 e 70/75 são provisórios; prioridade Alta.

3.9 EXCLUSÕES E DOENÇAS ESPECIAIS
Decisão: aprovar lista oficial e tratamento por produto.
Classificação: LISTA/CONDIÇÕES CONFIGURÁVEIS; CATÁLOGOS FECHADOS NO CÓDIGO.
GTE pela interface: pode configurar exclusões e textos de condições suportados pelo modelo.
Hardcoded/fornecedor: novos tipos de tratamento ou lógica especial exigem desenvolvimento.
Estado/risco: lista actual é indicativa; prioridade Alta.

3.10 DOENÇAS GRAVES E SUBSÍDIO DE INTERNAMENTO
Decisão: confirmar lista, dias máximos e franquia temporal.
Classificação: PARÂMETROS CONFIGURÁVEIS.
GTE pela interface: pode definir dias, franquia e lista dentro do catálogo existente.
Hardcoded/fornecedor: novas modalidades de benefício ou cálculo diferente exigem código.
Estado/risco: dias e franquia ainda não estão definidos; prioridade Média.

4.1 DIMENSÃO MÍNIMA DO GRUPO
Decisão: definir mínimo e tratamento de grupos abaixo do mínimo.
Classificação: CONFIGURÁVEL.
GTE pela interface: pode configurar o mínimo por plano.
Hardcoded/fornecedor: o bloqueio de submissão abaixo do mínimo é regra estrutural.
Estado/risco: prioridade Alta.

4.2 CATEGORIAS PROFISSIONAIS
Decisão: decidir proposta consolidada ou uma cotação por categoria.
Classificação: DECISÃO DE WORKFLOW; PARCIALMENTE IMPLEMENTADO.
GTE pela interface: pode criar uma cotação por categoria.
Hardcoded/fornecedor: proposta consolidada exige novo fluxo, modelo e agregação; não é apenas um parâmetro.
Estado/risco: hoje cada categoria tem cotação própria; prioridade Média.

4.3 ADESÃO E QUESTIONÁRIO CLÍNICO DE GRUPO
Decisão: confirmar adesão e limiar de dispensa.
Classificação: CONFIGURÁVEL.
GTE pela interface: pode definir adesão, limiar e requisitos por plano.
Hardcoded/fornecedor: a avaliação automática dos requisitos e o workflow clínico são código.
Estado/risco: limiar provisório de 20 pessoas; prioridade Média.

4.4 PARTICIPAÇÃO NOS RESULTADOS
Decisão: confirmar limite, quota, fórmula e periodicidade.
Classificação: PARÂMETROS CONFIGURÁVEIS; FÓRMULA ACTUARIAL LIMITADA.
GTE pela interface: pode guardar premissas e calcular a fórmula suportada.
Hardcoded/fornecedor: mudar a metodologia, periodicidade ou modelo actuarial exige desenvolvimento.
Estado/risco: 65% e fórmula actual são indicativos; prioridade Média.

4.5 MOVIMENTOS MENSAIS E ACERTO DE PRÉMIO
Decisão: decidir se inclusões/exclusões e acerto fazem parte do sistema.
Classificação: NÃO IMPLEMENTADO; CONDIÇÃO CONFIGURÁVEL.
GTE pela interface: pode registar a condição contratual.
Hardcoded/fornecedor: gerir movimentos, recibos e acertos exige módulo de apólices/pagamentos.
Estado/risco: processo fica fora do simulador; prioridade Baixa.

4.6 CONTINUIDADE E FAMILIARES
Decisão: confirmar continuidade, reformados e pagamento de familiares.
Classificação: TEXTO/CONDIÇÃO CONFIGURÁVEL; PROCESSO OPERACIONAL PENDENTE.
GTE pela interface: pode registar e apresentar as condições no plano/proposta.
Hardcoded/fornecedor: automatizar movimentos e cobrança exige desenvolvimento.
Estado/risco: regras comerciais ainda precisam de confirmação; prioridade Baixa.

5.1 DADOS HISTÓRICOS EXISTENTES
Decisão: confirmar formato e periodicidade dos dados.
Classificação: FORMATO ACTUAL FIXO; ADAPTAÇÃO FUTURA EXIGE DESENVOLVIMENTO.
GTE pela interface: pode importar CSV/XLSX no formato documentado e corrigir linhas inválidas.
Hardcoded/fornecedor: novos nomes de colunas, fontes ou integrações exigem alteração do importador.
Estado/risco: prioridade Alta; é necessária amostra anonimizada real.

5.2 FÓRMULAS ACTUARIAIS DE PROJECÇÃO
Decisão: aprovar metodologia, inflação, tendência, mix e sazonalidade.
Classificação: PREMISSAS CONFIGURÁVEIS; MODELO ESTRUTURAL.
GTE pela interface: pode introduzir premissas dos cenários optimista/base/pessimista e guardar conjuntos.
Hardcoded/fornecedor: o método actual SIMPLE_TREND_V1 e a fórmula da projecção estão no código; novo modelo actuarial exige fornecedor.
Estado/risco: prioridade Alta; projecção actual não está validada actuarialmente.

5.3 INDICADORES PRIORITÁRIOS
Decisão: confirmar indicadores necessários.
Classificação: INDICADORES SUPORTADOS PELO CÓDIGO.
GTE pela interface: pode consultar loss ratio, frequência, custo médio e distribuições actualmente disponíveis.
Hardcoded/fornecedor: novos indicadores, dimensões ou gráficos exigem desenvolvimento.
Estado/risco: prioridade Média.

5.4 HISTÓRICO DE OUTRA SEGURADORA
Decisão: confirmar formato e garantia dos três anos de histórico.
Classificação: ORIGEM CONFIGURÁVEL; FORMATO E VALIDAÇÃO ESTRUTURAIS.
GTE pela interface: pode importar dados como OTHER_INSURER e verificar meses disponíveis.
Hardcoded/fornecedor: novo formato, integração ou validação de autenticidade exige desenvolvimento.
Estado/risco: prioridade Média.

5.5 PROTECÇÃO DE DADOS DE SAÚDE
Decisão: aprovar retenção, acesso, consentimento e requisitos legais.
Classificação: CONTROLOS ESTRUTURAIS; ALGUNS PARÂMETROS DE RETENÇÃO PENDENTES.
GTE pela interface: pode consultar dados agregados segundo as permissões e deixar auditoria.
Hardcoded/fornecedor: isolamento, pseudonimização, autenticação e autorização são controlos do sistema; requisitos legais novos exigem implementação.
Estado/risco: prioridade Alta.

6.1 REGRAS DE RENOVAÇÃO
Decisão: definir agravamentos, indexação e inflação médica.
Classificação: CONFIGURÁVEL.
GTE pela interface: pode definir inflação por plano/parâmetro global e simular o impacto.
Hardcoded/fornecedor: cálculo de renovação, snapshot e validação de idade são regras do código.
Estado/risco: política comercial ainda precisa de confirmação; prioridade Média.

6.2 FECHO DA APÓLICE ANTERIOR
Decisão: definir quando marcar a apólice anterior como renovada.
Classificação: NÃO IMPLEMENTADO; WORKFLOW ESTRUTURAL.
GTE pela interface: actualmente não pode activar esta transição.
Hardcoded/fornecedor: requer endpoint e transacção de emissão/renovação.
Estado/risco: apólice anterior mantém estado; prioridade Média.

6.3 PRAZOS DE RENOVAÇÃO
Decisão: definir antecedência e validade para aceitar renovação.
Classificação: PRAZOS CONFIGURÁVEIS; WORKFLOW ESTRUTURAL.
GTE pela interface: pode configurar validade da cotação.
Hardcoded/fornecedor: automatizar alertas, janelas e tarefas exige desenvolvimento.
Estado/risco: prioridade Baixa.

7.1 MODELO OFICIAL DA PROPOSTA
Decisão: fornecer identidade visual, textos legais, cláusulas e estrutura.
Classificação: TEMPLATE CONFIGURÁVEL; CONTEÚDO LEGAL DEPENDENTE DO CLIENTE.
GTE pela interface: pode editar título, textos e secções do template.
Hardcoded/fornecedor: novos formatos de documento, renderizadores ou regras legais especiais exigem desenvolvimento.
Estado/risco: template actual é por omissão e não oficial; prioridade Alta.

7.2 FORMATOS E ASSINATURA
Decisão: confirmar formatos obrigatórios e assinatura aceite.
Classificação: FORMATOS PARCIALMENTE SUPORTADOS; ASSINATURA DIGITAL NÃO IMPLEMENTADA.
GTE pela interface: pode escolher PDF, DOCX ou HTML nos formatos disponíveis.
Hardcoded/fornecedor: assinatura digital qualificada, validação e integração externa exigem desenvolvimento.
Estado/risco: assinatura presencial é o comportamento actual; prioridade Média.

7.3 NUMERAÇÃO OFICIAL
Decisão: confirmar formato e reinício ou continuidade anual.
Classificação: REGRA ESTRUTURAL COM PARÂMETRO LIMITADO.
GTE pela interface: pode usar a sequência configurada e consultar histórico.
Hardcoded/fornecedor: alterar formato oficial, unicidade, reinício anual ou integração regulamentar exige desenvolvimento e decisão técnica.
Estado/risco: COT/APO contínuos são identificadores de teste; prioridade Média.

7.4 VALIDADE DAS COTAÇÕES
Decisão: confirmar validade padrão.
Classificação: CONFIGURÁVEL.
GTE pela interface: pode alterar o parâmetro de dias de validade.
Hardcoded/fornecedor: a aplicação do vencimento e transição de estado permanece no código.
Estado/risco: 30 dias é provisório; prioridade Baixa.

7.5 AVISO DE VALORES INDICATIVOS
Decisão: aprovar texto legal do aviso.
Classificação: TEXTO CONFIGURÁVEL; OBRIGAÇÃO DE APRESENTAR É ESTRUTURAL.
GTE pela interface: pode editar o texto do template depois de aprovado.
Hardcoded/fornecedor: garantir que o aviso aparece nos documentos aplicáveis é regra do gerador.
Estado/risco: texto jurídico por validar; prioridade Alta.

8.1 PERFIS E PERMISSÕES DO GTE
Decisão: aprovar perfis, permissões e se podem ser editados.
Classificação: PERFIS ACTUAIS FIXOS; PERMISSÕES DE NEGÓCIO CONFIGURÁVEIS APENAS SE EXTENDIDAS.
GTE pela interface: pode usar os perfis existentes: administrador, configurador, subscritor, aprovador e auditor.
Hardcoded/fornecedor: criar/editar perfis, permissões e matriz por utilizador exige desenvolvimento e decisão de segurança.
Estado/risco: prioridade Alta.

8.2 LIMITE DA AUTONOMIA
Decisão: aprovar fronteira entre operacional e estrutural.
Classificação: DECISÃO DE GOVERNANÇA, NÃO UM CAMPO ÚNICO.
GTE pela interface: deve controlar tarifas, capitais, participação, carências, coberturas, ajustes, templates e parâmetros globais.
Hardcoded/fornecedor: fórmulas, motor, arredondamento, integrações e novos módulos continuam dependentes do fornecedor.
Estado/risco: deve ser aprovado para alinhar expectativas.

8.3 SISTEMA DE AUTENTICAÇÃO
Decisão: escolher fornecedor definitivo ou autenticação interna.
Classificação: INFRAESTRUTURAL.
GTE pela interface: não deve alterar este mecanismo numa tela de negócio.
Hardcoded/fornecedor: configuração de IdP, emissão/validação de tokens, MFA e políticas de segurança exigem administração técnica.
Estado/risco: solução actual é provisória ou dependente do ambiente; prioridade Alta.

8.4 REQUISITOS REGULATÓRIOS
Decisão: confirmar ARSEG, AGT, conservação, documentos e reportes obrigatórios.
Classificação: PARÂMETROS QUANDO SUPORTADOS; COMPLIANCE ESTRUTURAL.
GTE pela interface: pode configurar textos, avisos, campos e prazos que o sistema já suporte.
Hardcoded/fornecedor: novas validações, reportes ou integrações regulatórias exigem desenvolvimento.
Estado/risco: nada está configurado; prioridade Alta.

8.5 INTEGRAÇÕES
Decisão: definir sistemas e formatos a integrar.
Classificação: NÃO IMPLEMENTADO; IMPORTAÇÃO POR FICHEIRO.
GTE pela interface: pode importar ficheiros no formato disponível.
Hardcoded/fornecedor: APIs com cadastro, sinistros, cobranças ou contabilidade exigem desenvolvimento e credenciais técnicas.
Estado/risco: prioridade Média.

8.6 VALIDAÇÃO DO NIF
Decisão: decidir se basta formato ou se é necessária validação AGT.
Classificação: FORMATO VALIDADO NO CÓDIGO; VALIDAÇÃO AGT NÃO IMPLEMENTADA.
GTE pela interface: pode preencher o NIF e receber validação de formato.
Hardcoded/fornecedor: consulta AGT, certificados, disponibilidade e tratamento de erros exigem integração.
Estado/risco: NIF inexistente pode ser aceite; prioridade Baixa.

8.7 VOLUME E UTILIZADORES
Decisão: confirmar volumes, concorrência e desempenho esperado.
Classificação: REQUISITO DE INFRAESTRUTURA/TESTE.
GTE pela interface: não configura capacidade de carga de produção.
Hardcoded/fornecedor: escalabilidade, índices, workers, filas, cache e testes de carga exigem trabalho técnico.
Estado/risco: dimensionado apenas para uso interno; prioridade Média.

8.8 CONSERVAÇÃO E AUDITORIA
Decisão: aprovar período de retenção de auditoria, versões e documentos.
Classificação: AUDITORIA ESTRUTURAL; RETENÇÃO A CONFIGURAR OU IMPLEMENTAR.
GTE pela interface: pode consultar e exportar auditoria e manter histórico.
Hardcoded/fornecedor: eliminação automática, retenção legal, arquivo e anonimização exigem política e implementação técnica.
Estado/risco: conservação sem limite é provisória; prioridade Baixa.

3. MATRIZ FINAL: QUEM PODE FAZER O QUÊ
O GTE pode alterar valores operacionais através da interface quando o item estiver classificado como CONFIGURÁVEL: tarifas e factores suportados, capitais, coberturas, participações, carências, idades, preexistências, regras de grupo, premissas, templates, validade, publicação e rollback.

O código deve continuar a controlar: fórmula e sequência de cálculo, invariantes de segurança, permissões, isolamento por tenant, auditoria, idempotência, transições de estado, formato dos dados aceites, validação de integridade, geração de documentos e protecção de dados.

O fornecedor continua necessário para: novas fórmulas actuariais, novas dimensões do pricing, impostos e comissões, integrações externas, assinatura digital, gestão de pré-autorização, proposta consolidada de grupos, movimentos mensais, novos módulos, perfis editáveis e alterações regulatórias que não sejam cobertas pelos parâmetros existentes.

4. CRITÉRIO DE ACEITAÇÃO DA AUTONOMIA
Considera-se cumprida a autonomia do GTE somente quando cada item marcado CONFIGURÁVEL tiver uma tela autorizada, validação, pré-visualização quando aplicável, publicação versionada, auditoria antes/depois, rollback e testes. Uma API ou estrutura de dados existente sem ecrã não deve ser apresentada como autonomia operacional completa.

5. APROVAÇÃO
Responsável da área de negócio: ________________________________  Data: __________
Responsável técnico-atuarial: _________________________________  Data: __________
Responsável técnico do fornecedor: ____________________________  Data: __________
'@

New-Item -ItemType Directory -Path $tempRoot | Out-Null
[System.IO.Compression.ZipFile]::ExtractToDirectory($source, $tempRoot)
$xmlPath = Join-Path $tempRoot 'word\document.xml'
$escaped = [System.Security.SecurityElement]::Escape($content)
$paragraphs = ($escaped -split "`r?`n") | ForEach-Object {
    if ($_.Length -eq 0) { '<w:p/>' } else { '<w:p><w:r><w:t xml:space="preserve">' + $_ + '</w:t></w:r></w:p>' }
}
$document = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + ($paragraphs -join '') + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/></w:sectPr></w:body></w:document>'
[System.IO.File]::WriteAllText($xmlPath, $document, [System.Text.UTF8Encoding]::new($false))
[System.IO.Compression.ZipFile]::CreateFromDirectory($tempRoot, $tempDocx)
Copy-Item $tempDocx $source -Force
Remove-Item $tempRoot -Recurse -Force
Remove-Item $tempDocx -Force
Write-Output $source
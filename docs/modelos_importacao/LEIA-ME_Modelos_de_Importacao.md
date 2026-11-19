PACOTE DE MODELOS DE IMPORTAÇÃO Q360

01 Modelo actuarial de referência SAU/SAG (dados indicativos do projecto).
02 Exemplo sintético de membros para testes: 30 pessoas de uma empresa (12 titulares e dependentes).
03 Modelo vazio de membros para produção.
04 Exemplo sintético de 36 meses de sinistros (2023–2025): 177 sinistros pagos, rejeitados, em aberto e um em USD.
05 Modelo vazio de sinistros para produção.
06 Exemplo sintético de 36 meses de prémios (2023–2025): 36 períodos mensais; sinistralidade paga perto de 73%.
07 Modelo vazio de prémios para produção.
08 Exemplo sintético de 10 coberturas complementares.
09 Modelo vazio de coberturas para produção.
10 Exemplo de tabela de referência: fator fictício para as 18 províncias.
11 Modelo vazio de tabela de referência para produção.
12 Exemplo sintético de importação organizacional: 1 titular, 10 colaboradores e 19 familiares (30 pessoas no total), incluindo colaboradores sem agregado.

UTILIZAÇÃO
- Modelo actuarial: Administração > Tarifação/Modelo actuarial > Importar Excel actuarial. Use um único livro Excel com as folhas Dashboard_Premissas, Matriz_SAU, Matriz_SAG e Regras_Ajustes, com os valores calculados guardados. A importação cria rascunho; publicação depende de aprovação actuarial. Não usar o importador genérico de configuração em três colunas.
- Novos ficheiros (com erros propositados, modelo do fornecedor, JPG): ver docs/ficheiros_teste_modulos e o índice em docs/GUIA_TESTES_POR_MODULO.md.
- Membros individuais: descarregue o modelo MEMBERS na página de importação de membros.
- Organizações: o responsável/tomador é importado como uma linha TITULAR no Excel ORGANISATION_MEMBERS, com nome, apelido opcional, data de nascimento, sexo, e-mail e telefone. O e-mail do titular tem de ser diferente do e-mail de contacto da organização; os dois contactos ficam separados. Ao confirmar a importação, o convite do Portal do Cliente é enviado para o e-mail do titular. Só pode existir um titular ativo por organização; nas importações seguintes, pode omitir essa linha. Cada linha COLABORADOR representa um trabalhador e pode ter linhas DEPENDENTE opcionais. Na linha do dependente, indique a referência externa do colaborador na coluna «Referência do colaborador titular». Um colaborador sem dependentes não recebe agregado familiar; o titular da organização também não é associado automaticamente a um agregado. Os cabeçalhos e a folha «Instruções» estão em português; os códigos de relação familiar são os códigos configurados no tenant.
- Teste de colaboradores e familiares numa organização: use 12_Exemplo_Colaboradores_e_Familiares_TESTE.xlsx. Tem 30 pessoas fictícias no formato ORGANISATION_MEMBERS: 1 titular, 10 colaboradores e 19 familiares; dois colaboradores não têm dependentes e, por isso, não devem receber agregado. Os códigos CONJUGE e FILHO têm de estar permitidos no tenant.
- Sinistros/prémios: Sinistralidade > Importações; para análise de experiência, usar períodos correspondentes.
- Coberturas: Administração > Produtos/Coberturas > Importar.
- Tabela de referência: Plataforma > Tabelas de referência; seleccionar coluna-chave e submeter para aprovação.

PRODUÇÃO
Os ficheiros TESTE/EXEMPLO têm dados inventados: não os carregue num tenant de produção. Os modelos VAZIO_PRODUCAO contêm cabeçalhos e instruções, sem registos de teste; preencha-os com dados reais, autorizados e validados. O modelo actuarial de referência contém pressupostos indicativos, não dados reais nem aprovação actuarial; deve ser calibrado pelo atuário antes de publicação. Este pacote não contém dados reais de pessoas ou seguradoras.

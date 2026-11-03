# Guia de testes pela interface — Q360 Linha Saúde

Roteiro para testar **todas as funcionalidades com ecrã**, módulo a módulo, usando apenas a aplicação (rato e teclado). Não é preciso consola do navegador, API nem Postman. Quando uma funcionalidade não tem ecrã, o guia diz **Sem ecrã** e passa à seguinte.

Revisto a 31/10/2026 a partir das rotas, menus e botões reais do frontend (`Q360-Linha-Sa-de-frontend`) e das regras do backend. A preparação técnica (base de dados, seed, arranque) está em [GUIA_TESTES.md](../GUIA_TESTES.md) e serve só para pôr a aplicação a funcionar.

## Como trabalhamos

1. Fazemos **um módulo de cada vez**, pela ordem abaixo. A ordem não é arbitrária: a configuração (produtos, tarifação, fórmulas, regras) vem antes da operação (clientes, cotações, apólices), porque a operação depende dela. Exemplo real: o formulário de organização exige setor e região atuariais, que só existem depois de publicar o modelo atuarial (Módulo 5).
2. Em cada passo há uma ação e o **Esperado**. Se o resultado for diferente, pare, tire uma captura e envie-me o texto exato da mensagem.
3. Marque cada passo como **Passou**, **Falhou** ou **Sem ecrã**.
4. Use só o ambiente local e dados fictícios. Os nomes de teste começam por **QA** para os encontrar e limpar depois.

### Regra dos quatro olhos (importante)

Quase toda a configuração é versionada: cria-se um **rascunho**, **submete-se para aprovação** e **outra pessoa aprova**. Quem criou não pode aprovar. Por isso, nos módulos 1 e 2 criamos uma segunda conta de cada nível:

| Nível | Quem cria/propõe | Quem aprova |
|---|---|---|
| Plataforma (parâmetros do sistema, tabelas de referência, modelos do fornecedor) | `superadmin.demo@q360.local` | Super administrador QA 2 (criado no Módulo 1) |
| Seguradora (produtos, tarifação, fórmulas, regras, parâmetros, perfis) | `admin.demo@q360.local` | Administrador QA 2 (criado no Módulo 2) |
| Cotações | Subscritor | Gestor de Subscrição (quem submete não decide) |

### Contas

Palavra-passe de todas as contas demo: `Q360Demo!2026`.

| Perfil | Email | Onde entra |
|---|---|---|
| Super administrador da plataforma | `superadmin.demo@q360.local` | `http://localhost:5173/login` (abre a área `/platform`) |
| Administrador da seguradora | `admin.demo@q360.local` | `http://localhost:5173/login` |
| Gestor de Subscrição | `gestor.demo@q360.local` | `http://localhost:5173/login` |
| Subscritor | `subscritor.demo@q360.local` | `http://localhost:5173/login` |
| Cliente do portal (Ana Silva) | ver [GUIA_TESTES.md §3](../GUIA_TESTES.md) — palavra-passe `Cliente!Demo2026` | `http://localhost:5173/portal-cliente/acesso` |

Dica: use uma janela normal e uma janela privada do navegador para ter duas contas abertas ao mesmo tempo (quem cria e quem aprova).

## Ficheiros para upload

Todos os ficheiros são fictícios. Os que têm **COM_ERROS** servem para confirmar que o sistema recusa dados inválidos e explica porquê; cada um traz uma folha «Leia-me» com o erro propositado de cada linha.

| Ficheiro | Módulo / ecrã | Para quê |
|---|---|---|
| [05_Modelo_Fornecedor_Produto_TESTE.xlsx](ficheiros_teste_modulos/05_Modelo_Fornecedor_Produto_TESTE.xlsx) | 1 · Plataforma → Modelos do fornecedor | 3 planos, regras de grupo e de renovação |
| [10_Exemplo_Tabela_Referencia_TESTE.xlsx](modelos_importacao/10_Exemplo_Tabela_Referencia_TESTE.xlsx) | 1 · Plataforma → Tabelas de referência | Fator regional das 18 províncias |
| [09_Tabela_Referencia_COM_ERROS_TESTE.xlsx](ficheiros_teste_modulos/09_Tabela_Referencia_COM_ERROS_TESTE.xlsx) | 1 · Plataforma → Tabelas de referência | Cabeçalhos repetidos (deve ser recusado) |
| [08_Exemplo_Coberturas_TESTE.xlsx](modelos_importacao/08_Exemplo_Coberturas_TESTE.xlsx) | 4 · Coberturas → Importar | 10 coberturas complementares |
| [07_Coberturas_COM_ERROS_TESTE.xlsx](ficheiros_teste_modulos/07_Coberturas_COM_ERROS_TESTE.xlsx) | 4 · Coberturas → Importar | 1 linha válida + 4 erros |
| [01_Modelo_Actuarial_Referencia_SAU_SAG.xlsx](modelos_importacao/01_Modelo_Actuarial_Referencia_SAU_SAG.xlsx) | 5 · Tarifação → Importar modelo atuarial | Prémios, fatores idade/sexo, setores e regiões |
| [03_Papel_Timbrado_QA.pdf](ficheiros_teste_modulos/03_Papel_Timbrado_QA.pdf) | 10 · Configuração avançada → Documentos | Documento associado a uma configuração |
| [01_Colaboradores_QA.xlsx](ficheiros_teste_modulos/01_Colaboradores_QA.xlsx) | 11 · Clientes → Importar membros | 30 colaboradores (referências DEMO-PESS-001 a 030) |
| [06_Colaboradores_COM_ERROS_QA.xlsx](ficheiros_teste_modulos/06_Colaboradores_COM_ERROS_QA.xlsx) | 11 · Clientes → Importar membros | 2 linhas válidas + 6 erros |
| [04_Exemplo_Historico_Sinistros_36_Meses_TESTE.xlsx](modelos_importacao/04_Exemplo_Historico_Sinistros_36_Meses_TESTE.xlsx) | 18 · Sinistralidade → Importações | 177 sinistros de 36 meses |
| [06_Exemplo_Historico_Premios_36_Meses_TESTE.xlsx](modelos_importacao/06_Exemplo_Historico_Premios_36_Meses_TESTE.xlsx) | 18 · Sinistralidade → Importações | 36 períodos mensais de prémios |
| [08_Sinistros_COM_ERROS_TESTE.xlsx](ficheiros_teste_modulos/08_Sinistros_COM_ERROS_TESTE.xlsx) | 18 · Sinistralidade → Importações | 1 linha válida + 5 erros |
| [02_Evidencia_QA_FICTICIA.pdf](ficheiros_teste_modulos/02_Evidencia_QA_FICTICIA.pdf) | 19 · Portal → Documentos | Documento PDF aceite |
| [11_Comprovativo_Estudante_QA_FICTICIO.jpg](ficheiros_teste_modulos/11_Comprovativo_Estudante_QA_FICTICIO.jpg) | 19 · Portal → Documentos | Documento JPG aceite |
| [10_Formato_Invalido_QA.txt](ficheiros_teste_modulos/10_Formato_Invalido_QA.txt) | 19 · Portal → Documentos | Formato não suportado (deve ser recusado) |

Sem ecrã para upload: o **papel timbrado da proposta** e o **modelo Word de proposta** ([04_Modelo_Proposta_QA.docx](ficheiros_teste_modulos/04_Modelo_Proposta_QA.docx)). O backend aceita papel timbrado por modelo de documento, mas a interface ainda não tem esse campo; os modelos de documento são editados em JSON (Módulo 10).

## Índice

| # | Módulo | Perfil |
|---|---|---|
| 0 | Acesso, menus por perfil e perfil pessoal | Todos |
| 1 | Plataforma (gestão global) | Super administrador |
| 2 | Utilizadores, perfis e permissões | Administrador |
| 3 | Modelos de partida | Administrador |
| 4 | Produtos, coberturas e planos | Administrador |
| 5 | Tarifação e modelo atuarial | Administrador + Admin QA 2 |
| 6 | Fórmulas | Administrador + Admin QA 2 |
| 7 | Regras de negócio | Administrador + Admin QA 2 |
| 8 | Parâmetros globais | Administrador |
| 9 | Aprovações pendentes | Admin QA 2 |
| 10 | Documentos e marca; configuração avançada | Administrador |
| 11 | Clientes, núcleos familiares e importação | Subscritor / Administrador |
| 12 | Elegibilidade | Subscritor |
| 13 | Tarifação operacional (simulação) | Subscritor |
| 14 | Cotações | Subscritor |
| 15 | Subscrição (análise e decisão) | Gestor de Subscrição |
| 16 | Apólices: emissão e ciclo de vida | Gestor / Administrador |
| 17 | Cobranças | Gestor / Administrador |
| 18 | Sinistralidade | Gestor / Administrador |
| 19 | Portal do cliente | Cliente |
| 20 | Atendimento (backoffice do portal) | Administrador |
| 21 | Dashboard, notificações, pesquisa e auditoria | Administrador |

---

## Módulo 0 — Acesso, menus por perfil e perfil pessoal

1. Abra `http://localhost:5173/login` e entre como **Administrador**. **Esperado:** abre o **Dashboard**; o menu lateral mostra Dashboard, Notificações, Produtos, Cotações, Clientes, Atendimento, Tarifação, Elegibilidade, Subscrição, Sinistralidade, Apólices, Cobranças, Auditoria e a entrada **Administração**.
2. Abra **O meu perfil** (menu do utilizador, `/perfil`). **Esperado:** nome, email, perfis e a lista «O que pode fazer».
3. Saia e entre como **Gestor de Subscrição**. **Esperado:** vê Subscrição, Sinistralidade e Auditoria; na Administração vê só Produtos e planos, Tarifação, Fórmulas, Regras e Parâmetros (sem Utilizadores, Aprovações, Modelos de partida, Documentos).
4. Saia e entre como **Subscritor**. **Esperado:** vê Cotações, Tarifação, Elegibilidade e Subscrição; **não** vê Sinistralidade, Auditoria nem Administração.
5. Como Subscritor, escreva na barra de endereço `http://localhost:5173/administracao/utilizadores`. **Esperado:** é redirecionado; não consegue abrir a página por URL.
6. Saia e tente entrar com a palavra-passe errada. **Esperado:** mensagem de credenciais inválidas, sem dizer se o email existe. Não insista mais de 4 vezes nesta conta (à 5.ª tentativa a conta é bloqueada; o desbloqueio testa-se no Módulo 2).

Regista: `Admin ___ | Gestor ___ | Subscritor ___ | Bloqueio por URL ___ | Palavra-passe errada ___`

---

## Módulo 1 — Plataforma (gestão global)

Entre em `http://localhost:5173/login` como **Super administrador**. **Esperado:** abre a área da plataforma (`/platform`), diferente da área da seguradora.

### 1.1 Visão geral e conta
1. **Esperado:** «Olá, Super», contagens de seguradoras (total, ativas, suspensas), seguradoras recentes e auditoria recente.
2. Abra **A minha conta**. Confirme nome, email e estado. Não altere a palavra-passe da conta demo.

### 1.2 Super administradores
1. Abra **Super administradores → Novo super administrador**. Nome `Super Admin QA 2`, email `superadmin2.qa@demo.q360.local` → **Criar administrador**. **Esperado:** aparece na lista; a palavra-passe temporária é mostrada **uma única vez** — anote-a.
2. Tente **Desativar** a sua própria conta. **Esperado:** «Não é possível desativar a própria conta».
3. Numa janela privada, entre em `/login` com a conta QA 2 e a palavra-passe temporária. Se pedir para mudar a palavra-passe, defina uma nova e anote-a.

### 1.3 Seguradoras
1. Abra **Seguradoras**; pesquise por `demo` e filtre por estado. **Esperado:** aparece a seguradora demo.
2. **Nova seguradora:** código `qa-saude`, nome `Seguradora QA`, nome legal, país, nome e email do administrador (`admin.qa-saude@demo.q360.local`) → **Criar seguradora**. **Esperado:** é criada com o primeiro administrador.
3. Abra a seguradora QA: edite o perfil (telefone, notas) → **Guardar perfil**. Veja **Contas de utilizadores**; use **Repor palavra-passe** no administrador. **Esperado:** nova palavra-passe temporária mostrada uma vez.
4. **Suspender** a seguradora QA e confirme o aviso. Numa janela privada, tente entrar em `/login` com o administrador dela. **Esperado:** acesso recusado. Volte a **Ativar**.
5. **Não** suspenda a seguradora demo.

### 1.4 Parâmetros do sistema
1. Abra **Parâmetros do sistema**. **Esperado:** parâmetros agrupados (Operacional, Estrutural, Legal, Teto, Mercado), cada um com valor, limites e estado.
2. Num parâmetro **Operacional**, carregue em **Propor alteração**. Altere o valor dentro dos limites, preencha **Referência legal** e **Motivo** (mínimo indicado no ecrã) → **Enviar para aprovação**. **Esperado:** fica «Pendente de aprovação».
3. Tente propor um valor fora do «Limite do sistema». **Esperado:** recusado com explicação.
4. Com a conta **Super Admin QA 2**, abra o mesmo parâmetro e aprove. **Esperado:** passa a «Publicada»; o **Histórico** mostra as versões. Repita com outra proposta e **rejeite-a**.
5. Com a conta que propôs, confirme que **não** consegue aprovar a sua própria proposta.

### 1.5 Tabelas de referência
1. Abra **Tabelas de referência → Propor tabela**. Código `qa_fator_regional`, nome `QA Fator regional`.
2. Em «Ficheiro Excel (.xlsx)» carregue `10_Exemplo_Tabela_Referencia_TESTE.xlsx`. **Esperado:** colunas e linhas preenchidas automaticamente (Província, Fator regional; 18 linhas); coluna-chave = Província.
3. Escreva um motivo com 10+ caracteres → **Enviar para aprovação**. **Esperado:** «Pendente».
4. Repita com `09_Tabela_Referencia_COM_ERROS_TESTE.xlsx`. **Esperado:** «Dois ou mais cabeçalhos geram o mesmo código…»; nada é enviado.
5. Com a conta QA 2, aprove a tabela. **Esperado:** «Publicada». Esta tabela aparece depois em Fórmulas → Referência (Módulo 6).

### 1.6 Modelos do fornecedor
1. Abra **Modelos do fornecedor → Propor modelo**. Use **Descarregar modelo Excel** para ver o formato (3 colunas: chave, caminho, valor).
2. Código `qa_produto_saude`, tipo **Produto de mercado**, segmento SAU, nome `QA Produto de partida`.
3. Em «Importar de Excel» carregue `05_Modelo_Fornecedor_Produto_TESTE.xlsx`. **Esperado:** «Conteúdo importado — reveja…» e o JSON preenchido com 3 planos (Básico, Standard, Premium), regras de grupo e de renovação.
4. Motivo → **Enviar para aprovação**; aprove com a conta QA 2. **Esperado:** «Publicada». Fica disponível para as seguradoras no Módulo 3.
5. Negativo: mude o tipo para **Conjunto de fórmulas** com o mesmo conteúdo e envie. **Esperado:** recusa (este tipo só aceita fórmulas).

### 1.7 Motor de fórmulas e auditoria
1. Abra **Motor de fórmulas e regras**. **Esperado:** limites de segurança, funções/operadores permitidos, variáveis do sistema, fases (por pessoa / cotação) e campos das regras «Quando… então…». Só consulta.
2. Abra **Auditoria**; filtre por ação e tipo de registo. **Esperado:** os eventos deste módulo (criação de super admin, seguradora, propostas e decisões) com autor e data; **Ver detalhe** abre o evento.

---

## Módulo 2 — Utilizadores, perfis e permissões

Entre em `/login` como **Administrador** → **Administração → Utilizadores e perfis**.

### 2.1 Contas
1. **Criar utilizador:** `Administrador QA 2`, `admin2.qa@demo.q360.local`, perfil **Administrador**. **Esperado:** «Utilizador criado. Password temporária: …» — anote-a. **Esta conta é o aprovador dos módulos 3 a 10.**
2. Crie também `Subscritor QA` (`subscritor.qa@demo.q360.local`, perfil Subscritor).
3. Tente criar um utilizador sem perfil. **Esperado:** «Escolha pelo menos um perfil».
4. **Editar perfis** do Subscritor QA: acrescente Gestor de Subscrição → **Guardar perfis**. Remova de seguida.
5. **Desativar** o Subscritor QA e tente entrar com ele numa janela privada. **Esperado:** acesso recusado. **Ativar** de novo.
6. **Repor palavra-passe** do Subscritor QA. **Esperado:** nova palavra-passe temporária; a anterior deixa de funcionar.
7. Numa janela privada, erre 5 vezes a palavra-passe do Subscritor QA. **Esperado:** na lista aparece «Bloqueada por tentativas falhadas até …»; **Desbloquear** volta a permitir entrar.
8. Entre com o **Administrador QA 2** numa janela privada (defina a palavra-passe se pedido) e mantenha essa janela aberta.

### 2.2 Perfis e permissões
1. Na mesma página, secção **Perfis e permissões**. **Esperado:** matriz dos 3 perfis × permissões (criar, editar, calcular, submeter, rever, aprovar, rejeitar cotações; gerir produtos; gerir tarifação; consultar auditoria).
2. Retire «Consultar auditoria» ao Subscritor (já não tem) ou dê-lhe essa permissão → **Guardar e submeter permissões**. **Esperado:** «Versão vX aguarda aprovação»; com a mesma conta o botão de aprovar não funciona (quatro olhos).
3. Na janela do **Administrador QA 2**, **Aprovar e publicar permissões**. **Esperado:** publicada; o Subscritor tem de voltar a entrar para ver a alteração.
4. Tente tirar ao Administrador «Gerir produtos» ou «Gerir a tarifação». **Esperado:** impedido, para não bloquear a administração.
5. Reponha a permissão original (mesmo ciclo: submeter + aprovar).

---

## Módulo 3 — Modelos de partida

**Administração → Modelos de partida** (Administrador).

1. **Esperado:** lista «Modelos publicados pelo fornecedor», incluindo `QA Produto de partida` do Módulo 1.
2. **Detalhes** → veja o conteúdo. Indique uma data de vigência (opcional) → **Adotar como rascunho**. **Esperado:** «Modelo adotado»; as configurações ficam em **rascunho** na seguradora (não ficam ativas).
3. Abra **Aprovações pendentes** (Módulo 9) ou **Configuração avançada** (Módulo 10) e confirme que os rascunhos existem. Não os publique se não quiser alterar o produto demo.

---

## Módulo 4 — Produtos, coberturas e planos

**Administração → Produtos e planos** (Administrador).

### 4.1 Catálogo de produtos
1. **Esperado:** «Gestão de Produtos» com lista, pesquisa e filtro (Todos, Ativos, Rascunhos, Inativos, Arquivados).
2. **Criar produto:** nome `QA Saúde Empresa` (o código é gerado), descrição. Em **Configuração inicial** escolha **Copiar a configuração geral para este produto** → criar. **Esperado:** «Produto criado…»; as cópias ficam em rascunho.
3. Crie outro, `QA Saúde Individual`, com **Usar a configuração geral (sem cópia)**.
4. **Editar** o primeiro: mude a descrição e o estado → **Guardar**. **Esperado:** «Produto atualizado».
5. **Apagar** o segundo produto e confirme. **Esperado:** «Produto apagado».
6. **Carregar modelos de mercado**. **Esperado:** «Valores indicativos importados» ou mensagem clara de erro.

### 4.2 Biblioteca de coberturas
Botão **Ver Coberturas** (ou `/coberturas`).
1. **Esperado:** lista com filtros Base / Complementares e Ativas / Inativas, pesquisa.
2. **Descarregar modelo Excel** e **Exportar**. **Esperado:** dois ficheiros .xlsx descarregados.
3. **Importar** → `08_Exemplo_Coberturas_TESTE.xlsx`. **Esperado:** «Importação concluída: N criada(s), N atualizada(s), 0 erro(s)»; as coberturas `DEMO_…` aparecem. Atenção: esta importação grava logo, sem pré-visualização.
4. **Importar** → `07_Coberturas_COM_ERROS_TESTE.xlsx`. **Esperado:** 1 criada e 4 erros listados (código que começa por dígito, JSON inválido, categoria BASE, nome em falta).
5. **Nova cobertura** complementar `QA Fisioterapia ao domicílio` → **Guardar**.
6. **Abrir** a cobertura: **Editar** nome/descrição → **Guardar**. Veja **Planos que usam esta cobertura** e **Histórico de revisões**; **Restaurar** uma revisão anterior. **Esperado:** «Nova revisão criada a partir do histórico» (nada é apagado).
7. **Desativar** e **Reativar**. **Esperado:** desativada deixa de poder ser associada a novos planos.

### 4.3 Planos
Volte ao produto `QA Saúde Empresa` (abrir o produto na lista).
1. **+ Adicionar plano**: nome `QA Plano Ouro`, escolha 2 coberturas complementares → **Criar plano**. **Esperado:** «Plano criado».
2. Crie um segundo plano com **as mesmas** coberturas. **Esperado:** «Já existe um plano neste produto com este mesmo conjunto de coberturas».
3. Abra o plano (detalhe, `/plans/…`). Em **Dados do plano** altere a descrição → **Guardar**. **Esperado:** as 3 coberturas base aparecem e não podem ser removidas.
4. Em **Configurações do plano** preencha e guarde (**Guardar configurações**), testando cada secção:
   - **Idades:** entrada 0–65; permanência máx. 75.
   - **Agregado familiar:** cônjuge incluído; filho a cargo até 21; estudante até 25 com comprovativo.
   - **Questionário clínico e exames:** obrigatório; exame acima de 55 anos.
   - **Regras de grupo:** dimensão mínima 5; categorias profissionais (1 a 3, separadas por vírgula); participação nos resultados 70%.
   - **Opções de participação A–E:** mude o modelo de comparticipação para «Com copagamento/franquia», acrescente opções A e B (franquia anual, copagamento, reembolso %, ajuste %) e escolha a opção por omissão. Depois volte a «Integral». **Esperado:** aviso de que um plano Integral não pode ter opções.
   - **Doença pré-existente:** carência 12 meses ou sobreprémio.
   - **Carências, rede e pré-autorização** e **Indexação de capitais** (inflação médica 8%).
   - Negativo: idade mínima maior do que a máxima. **Esperado:** erro de validação.
5. Volte ao produto e carregue em **Parametrizar** no plano (`/administracao/planos/…/config`). Para cada cobertura → **Editar**:
   - Estado, inclusão, moeda; carências individual/grupo/cirurgia programada; «Em acidente, a carência não se aplica».
   - **Capitais e limites → + Adicionar limite** (valor anual, por evento, percentagem).
   - **Participação do segurado:** rede convencionada vs reembolso, copagamento, teto anual, franquia anual e por evento → **Guardar cobertura**. **Esperado:** «Cobertura atualizada»; a tabela mostra capital, copagamento e carência.
   - **Remover cobertura do plano** numa complementar. **Esperado:** «Cobertura removida».
   - Se aparecer «O plano precisa de correções», registe os avisos listados.
6. **Apagar plano** num plano de teste. **Esperado:** pede confirmação e remove.

### 4.4 Configuração do produto
No detalhe do produto `QA Saúde Empresa`, secção **Configuração do produto**.
1. **Esperado:** cada área com origem «Própria do produto», «Herdada da configuração geral» ou «Sem configuração».
2. Numa área herdada: **Personalizar para este produto** → altere um valor → **Guardar rascunho** → **Submeter para aprovação**. **Esperado:** «Outra pessoa tem de o aprovar…». Aprovação no Módulo 9.
3. Numa área que já tem «Rascunho do produto (versão N…)», carregue em **Editar rascunho**. **Esperado:** o formulário abre logo abaixo dessa linha (ex.: em Planos de Saúde, uma linha por plano com código, nome, descrição, ativo e copagamento; use **Adicionar** para mais linhas) → **Guardar rascunho** → **Submeter para aprovação**. Se a etiqueta disser «Sem configuração», não existe versão publicada, nem geral nem do produto: o rascunho vem vazio e é preciso preencher os campos.
4. **Ou copiar do produto** (outro produto) e **Voltar a usar a geral** (confirmar). **Esperado:** volta a «Herdada».

### 4.5 Catálogo operacional
Menu **Produtos** (fora da Administração).
1. **Esperado:** «Catálogo de produtos» só de consulta, com **Gerir em Administração**.
2. Marque **Comparar** em 2 ou 3 produtos. **Esperado:** comparação lado a lado; ao 4.º, «Máximo de 3 produtos».
3. **Ver detalhes** de um produto: planos e **Histórico de alterações** (criação, nome, descrição, estado).

---

## Módulo 5 — Tarifação e modelo atuarial

**Administração → Tarifação** (Administrador). Mantenha a janela do **Admin QA 2** aberta para aprovar.

### 5.1 Modelo atuarial (desbloqueia setor e região dos clientes)
1. Em **Importar modelo atuarial**, **Descarregar modelo Excel** para ver o formato.
2. Carregue `01_Modelo_Actuarial_Referencia_SAU_SAG.xlsx`, data de início = hoje, «Aplica-se a» = **Todos os produtos (modelo geral)** → **Importar como rascunho**. **Esperado:** «Importação criada como rascunho» com resumo (≈94 linhas de prémios, 17 premissas de cobertura, 17 fatores idade/sexo, regiões e setores).
3. A página de Tarifação não tem botão para submeter este rascunho. Abra `http://localhost:5173/administracao/configuracao-avancada`, em **Configurações existentes** localize o modelo atuarial (estado Rascunho) → **Abrir** → **Submeter para aprovação**. **Esperado:** «Configuração submetida para aprovação».
4. Na janela do **Admin QA 2**, **Administração → Aprovações pendentes** → **Ver diferenças** → **Aprovar**. **Esperado:** desaparece da fila; o modelo fica ativo.
5. Confirmação: **Clientes → Novo proponente → Organização**. **Esperado:** «Sector de atividade» e «Região atuarial» têm opções. (Não guarde ainda; o cliente faz-se no Módulo 11.)

### 5.2 Tarifação por produto
1. Escolha o produto `QA Saúde Empresa`. **Esperado:** «Configuração do produto» com **Modo simples** e **Modo avançado**.
2. **Modo simples:** «Valor do prémio anual (Kz)» = `150000` → **Guardar rascunho**. **Esperado:** «Rascunho guardado». Se a configuração for complexa, aparece «Esta configuração é mais complexa…» — use o modo avançado.
3. **Modo avançado:** veja o JSON (grupos de opções, campos, valores, fórmulas) → **Validar configuração**. **Esperado:** «Configuração válida» e a «Ordem de avaliação». Apague uma chaveta e valide de novo. **Esperado:** «JSON inválido». Reponha.
4. **Teste de fórmula:** deixe vazio → **Testar configuração**; depois escreva `base_premium * 1.05` → testar. **Esperado:** prémio e resultados.
5. **Simular perfil:** plano, idade (ex.: 35 e depois 62), sexo, fracionamento (Anual/Semestral/Trimestral/Mensal), rede ou reembolso, «Incluir rascunhos abertos na simulação» → **Simular agora**. **Esperado:** «Decomposição do prémio» (base, fator, ajuste, resultado) e gráfico; a simulação não grava nada. Ative a atualização automática e mude a idade: o resultado muda sozinho.
6. **Submeter para aprovação**. **Esperado:** «Versão pendente de aprovação» e bloqueio de novos rascunhos até decisão. Aprove no Módulo 9 com o Admin QA 2 e repita a simulação sem rascunhos.

---

## Módulo 6 — Fórmulas

**Administração → Fórmulas** (Administrador).

1. **Esperado:** lista de versões (Rascunho, Pendente de aprovação, Rejeitada, Publicada, Retirada) com vigência e autor. Seletor «Fórmulas de»: gerais ou de um produto.
2. Escolha `QA Saúde Empresa` → **Nova versão** → **Abrir**.
3. **Parâmetros → Adicionar:** rótulo `Desconto de grupo QA`, tipo Percentagem, valor 5, mín. 0, máx. 20.
4. **Regras → adicionar:** nome `QA Desconto por adesão em grupo`, etapa **Cotação**, alvo Total, ordem 1, ativa. Construa a expressão clicando nas variáveis/operadores (ex.: total × (1 − desconto)).
5. **Validar**. **Esperado:** «Configuração válida». Crie um erro (variável inexistente ou ciclo) e valide. **Esperado:** «Configuração inválida» com o motivo. Corrija → **Guardar**.
6. **Testar expressão** com valores em JSON, ex.: `{"total_amount": 1000}`. **Esperado:** «Resultado: …» e o cálculo passo a passo.
7. **Simular:** prémio inicial da pessoa, total, nº de membros, idade. **Esperado:** tabela Regra/Antes/Ajuste/Depois e o detalhe da avaliação.
8. **Referência:** confirme variáveis, funções, constantes do fornecedor e **Tabelas publicadas** (deve aparecer `QA Fator regional` do Módulo 1).
9. **Submeter** (motivo opcional). Com a mesma conta, tente **Aprovar**. **Esperado:** bloqueado. Com o **Admin QA 2**: **Aprovar**. **Esperado:** «Publicada» com vigência.
10. Crie outra versão, submeta e **Rejeitar** com motivo de menos de 5 caracteres. **Esperado:** recusa; com 5+ caracteres fica «Rejeitada».
11. Numa versão publicada de teste, **Retirar** e confirme. **Esperado:** «Retirada»; as fórmulas gerais voltam a valer nesse produto. **Histórico** mostra todos os eventos.

---

## Módulo 7 — Regras de negócio

**Administração → Regras de negócio** (Administrador).

1. **Nova regra:** nome `QA Agravamento maiores de 60`, produtos = `QA Saúde Empresa`, «A regra calcula sobre» pessoa. **Quando** idade **maior que** 60 → **Então: Alterar o prémio**, Percentagem +15, mensagem «Agravamento por idade (teste QA)» → **Guardar regra**.
2. **Nova regra:** `QA Revisão médica ascendentes`, **Quando** relação = Ascendente **e** (Adicionar outra condição) idade > 70 → **Então: Aceitação / avisos**, perfil que aprova = Gestor de subscrição.
3. Use **Subir/Descer** para ordenar. **Esperado:** a ordem conta para as regras de prémio.
4. **Guardar e publicar regras**. **Esperado:** «Regras enviadas. Falta a aprovação de outro administrador» (dupla aprovação ativa).
5. Na janela do **Admin QA 2**: **Aprovar e publicar**. **Esperado:** «Regras aprovadas e publicadas».
6. Faça uma alteração e use **Descartar alterações**. **Esperado:** volta à versão publicada.
7. O efeito real confirma-se no Módulo 14: uma pessoa com 62 anos deve ter +15% e um ascendente com 72 deve gerar requisito de aprovação.

---

## Módulo 8 — Parâmetros globais

**Administração → Parâmetros** (Administrador).

1. **Esperado:** «Parâmetros globais» com descrição em linguagem de negócio (validade das cotações, clientes, ligações de documentos, renovações, arredondamento do motor).
2. **Editar** «validade das cotações»: valor novo dentro do intervalo «Entre X e Y» → **Guardar**. **Esperado:** valor atual atualizado e revisão no histórico.
3. Tente um valor fora do intervalo. **Esperado:** recusa.
4. No histórico, **Restaurar** a versão anterior. **Esperado:** «Aplica de novo este valor, com uma nova revisão» — nada é apagado.
5. Confirmação no Módulo 14: o «Válida até» de uma cotação nova segue o valor configurado.

---

## Módulo 9 — Aprovações pendentes

**Administração → Aprovações pendentes**, com o **Administrador QA 2**.

1. **Esperado:** fila com contagens «Pendentes» e «Pode aprovar», com os itens submetidos nos módulos 4.4 e 5.2 (e outros que tenha submetido).
2. **Ver diferenças** num item. **Esperado:** tabela campo a campo antes/depois.
3. **Aprovar** um item. **Esperado:** sai da fila e passa a valer.
4. **Rejeitar** outro com motivo. **Esperado:** sai da fila; o autor vê a rejeição.
5. Com o **Administrador** (autor), abra a fila. **Esperado:** «Aprovar» desativado nos itens criados por si.
6. Se a página ficar em «A carregar a fila…» por mais de 30 segundos, registe **Falhou** com captura (foi observado numa sessão anterior).

---

## Módulo 10 — Documentos e marca; configuração avançada

### 10.1 Modelos de documento
**Administração → Documentos e marca** (Administrador).
1. **Ver variáveis disponíveis**. **Esperado:** lista de variáveis, secções permitidas e formatos suportados.
2. **Novo modelo:** código `QA-PROPOSTA`; o conteúdo JSON vem pré-preenchido com um exemplo — altere o título e o rodapé; vigência de hoje → **Criar modelo (rascunho)**.
3. Escreva JSON inválido e guarde. **Esperado:** «O conteúdo do modelo não é JSON válido…».
4. **Pré-visualizar** em PDF e em **Word (DOCX)**. **Esperado:** abre/descarrega o documento (permita pop-ups se o navegador bloquear).
5. **Publicar**; depois **Nova versão**, edite e **Remover** essa versão rascunho; por fim **Retirar** o modelo QA.
6. Papel timbrado e upload de modelo Word: **Sem ecrã**.

### 10.2 Configuração avançada (só por URL)
`http://localhost:5173/administracao/configuracao-avancada` (Administrador).
1. **Esperado:** «Configuração de negócio» com todas as configurações versionadas (geral e por produto), estado e vigência.
2. **Abrir** uma configuração → **Carregar no formulário**; veja os campos.
3. Em **Documentos**, escolha tipo e carregue `03_Papel_Timbrado_QA.pdf` → **Carregar documento**. **Esperado:** «Documento carregado» e **Descarregar** devolve o mesmo ficheiro.
4. **Nova configuração** de um tipo à escolha, vigente desde hoje → **Criar configuração** → **Submeter para aprovação** → aprovar com o Admin QA 2 → **Retirar**.

---

## Módulo 11 — Clientes, núcleos familiares e importação

Menu **Clientes** (Subscritor ou Administrador).

### 11.1 Proponente individual
1. **Novo proponente → Individual:** nome `QA Maria Teste`, data de nascimento, sexo, NIF `000000011LA011` (formato 9 dígitos + 2 letras + 3 dígitos), email `maria.qa@demo.q360.local`, telefone, morada, província, município → **Guardar**. **Esperado:** proponente criado com o titular.
2. Negativo: NIF com tamanho errado. **Esperado:** «O Nif deve ter 14 caracteres…». Repita o mesmo NIF noutro proponente. **Esperado:** «Número de registo já existe».
3. Abra o cliente → **Membros**: acrescente cônjuge, filho de 10 anos, filho de 23 anos e ascendente de 72 anos.
4. **Editar** um membro e **Inativar** outro. **Esperado:** atualizado / estado Inativo.

### 11.2 Proponente organização
1. **Novo proponente → Organização:** `QA Empresa Kilamba Lda`, NIF de 10 dígitos `5400000011`, **Sector de atividade** e **Região atuarial** (disponíveis depois do Módulo 5) → **Guardar**.
2. Na ficha da organização, secção **Membros**, carregue em «ou adicionar um membro individualmente» (ou importe o Excel, 11.3). O formulário não pede a relação: numa organização, todo o membro fica como **Colaborador**. **Esperado:** o colaborador aparece na lista com a relação COLABORADOR.
3. O titular escolhe-se **por colaborador**: na linha do colaborador → **Editar** → separador **Núcleo familiar** → **Criar o primeiro núcleo familiar**. O titular já vem preenchido com esse colaborador → **Criar núcleo familiar**. Não existe um titular da organização, só um titular por núcleo.
4. No núcleo: **Registar pessoa nova** (cônjuge e filho com parentesco) e **Associar pessoa já registada** (pesquisa por nome ou NIF).
5. Tente criar um segundo núcleo para o mesmo colaborador. **Esperado:** impedido («Cada colaborador pode ter apenas um núcleo familiar»).
6. **Remover do núcleo** um familiar.

### 11.3 Importação de membros
`Clientes → Importar` (ou `/clientes/importar`).
1. **Descarregar modelo Excel** e confirme os cabeçalhos.
2. Proponente = `QA Empresa Kilamba Lda`; ficheiro `06_Colaboradores_COM_ERROS_QA.xlsx`. **Esperado:** «Resultado da validação» com 8 linhas, 2 válidas e 6 inválidas, cada erro com o motivo. Não confirme.
3. Ficheiro `01_Colaboradores_QA.xlsx`. **Esperado:** 30 linhas válidas → **Confirmar importação (30 membros)** → «Importação concluída». A lista de membros mostra as 30 pessoas (DEMO-PESS-001 a 030).

---

## Módulo 12 — Elegibilidade

Menu **Elegibilidade** (Subscritor).

1. Modo **Manual:** produto, plano, data de vigência, proponente `QA Maria Teste`, membro titular → **Verificar elegibilidade**. **Esperado:** elegível, com os motivos (idade, relação permitida).
2. Membro filho de 23 anos sem comprovativo. **Esperado:** pede comprovativo de estudante ou recusa, conforme o plano (Módulo 4.3).
3. Membro ascendente de 72 anos com idade máxima de entrada 65. **Esperado:** recusa «Idade fora do intervalo de entrada».
4. Colaborador da `QA Empresa Kilamba Lda`. **Esperado:** elegível (o colaborador é aceite como titular).
5. Modo **Cotação:** escreva o número de uma cotação (ex.: `COT-12`) → **Procurar**. **Esperado:** carrega plano e proponente da cotação. Com número inexistente: «Cotação não encontrada».
6. Abra o detalhe de uma avaliação (`/elegibilidade/avaliacoes/…`). **Esperado:** pessoa, proponente, decisão e mensagens.

---

## Módulo 13 — Tarifação operacional (simulação)

Menu **Tarifação** (`/pricing`, Subscritor).

1. Produto, plano, proponente `QA Maria Teste`, marque os membros → **Pré-visualizar sem gravar**. **Esperado:** «Pré-visualização — este cálculo não foi guardado», prémio estimado e componentes (base, ajuste, taxa, imposto, total).
2. **Calcular tarifação**. **Esperado:** resultado com data/hora do cálculo. Com um membro inelegível: «Pelo menos um membro foi considerado inelegível» e ligação para a avaliação.
3. Confirme os efeitos dos módulos 5–7: o membro de 62 anos tem o agravamento de 15%.

---

## Módulo 14 — Cotações

Menu **Cotações** (Subscritor).

### 14.1 Criar
1. **Nova cotação → Produto e plano** → Continuar. **Proponente:** escolha `QA Maria Teste` (preenche os dados) → **Rever dados** → **Avançar para beneficiários**.
2. **Selecionar beneficiários:** marque titular, cônjuge, filhos e ascendente; teste **Adicionar membro novo** e, num proponente organização, **Familiares dos núcleos**. **Esperado:** contagens de titulares e dependentes selecionados.
3. Avance para o cálculo. **Esperado:** prémio total anual (inclui imposto de selo e encargo de serviço), vidas incluídas, «Válida até» conforme Módulo 8.
4. Negativo: avance sem produto ou sem NIF. **Esperado:** «Corrija os campos indicados…».

### 14.2 Lista e resumo
1. Lista: filtros (Rascunhos, Calculadas, Em Revisão, Aprovadas, Convertidas, Rejeitadas, Expiradas, Canceladas) e pesquisa por número.
2. **Ver resumo:** identificação, proponente, população, prémio e estado. **Usar dados para nova cotação**: cria cópia com o mesmo proponente e plano.
3. **Continuar** um rascunho: retoma o assistente onde ficou.
4. **Eliminar cotação** num rascunho de teste e confirme.
5. Submeta a cotação para análise. **Esperado:** estado «Em análise»; o prémio fica oculto até à decisão.

### 14.3 Renovação
1. **Renovar** → número de uma apólice existente (ex.: impressa pelo seed) → **Criar renovação**. **Esperado:** nova proposta com a população e as condições anteriores. Número inexistente: «Apólice não encontrada».

---

## Módulo 15 — Subscrição (análise e decisão)

Menu **Subscrição** com **Gestor de Subscrição**.

1. Fila: localize a cotação do Módulo 14 → abrir (`/subscricao/…`). **Esperado:** estado da revisão/tarefa/cotação, atribuição, histórico.
2. Percorra os painéis e registe o que mostram: **População**, **Prémio**, **Requisitos** (ex.: revisão médica do ascendente do Módulo 7), **Alertas**, **Documentos**, **Versões**, **Sinistralidade**.
3. **Ajustes de prémio:** Desconto 5% → **Simular impacto** → **Aplicar**. **Esperado:** prémio e delta atualizados. Um desconto acima do limite do perfil (ex.: 40%) mostra «excede o limite de autoridade…» e vai para **Aprovações de desconto** (decisão com nota de 10+ caracteres). **Remover** o ajuste.
4. **Cenários → Novo cenário** `QA Cenário B` → **Criar e calcular**; **Duplicar**, **Editar nome**, selecione 2 e **Comparar** (lado a lado, Δ vs 1.º), **Exportar**, **Aplicar à cotação**, **Eliminar**.
5. **Indexação de capitais:** inflação 8% → **Indexar**. **Esperado:** capitais indexados e cotação reprecificada.
6. **Proposta → Gerar proposta**. **Esperado:** «Geração em curso» e depois estado Gerado com número; descarregue.
7. **Decisão:** **Devolver** com motivo (volta ao Subscritor), resubmeta e **Aprovar**. Noutra cotação, **Rejeitar** sem motivo (**Esperado:** «O motivo da rejeição é obrigatório») e depois com motivo.
8. Quatro olhos: com uma conta que tenha submetido a cotação, tente decidir. **Esperado:** «Não pode decidir uma cotação que foi você a submeter».
9. Como Subscritor, confirme no resumo o estado e o motivo de rejeição.

---

## Módulo 16 — Apólices: emissão e ciclo de vida

### 16.1 Emissão
No resumo de uma cotação **Aprovada** (Gestor ou Administrador), painel **Emissão da apólice**.
1. **Assinatura presencial:** nome do assinante, tipo de documento (BI, cartão de residente, passaporte + visto), número, qualidade (tomador, representante legal, procurador), data/hora.
2. **Condições:** prazo 12 meses, periodicidade Trimestral, data de início (opcional).
3. Primeiro teste **sem** «Registar já o pagamento da 1.ª prestação» → **Emitir apólice**. **Esperado:** «Apólice … emitida», estado **Pendente do primeiro prémio**.
4. Com o Subscritor (sem permissão de aprovação). **Esperado:** «Precisa da permissão de aprovação de cotações para emitir».

### 16.2 Detalhe e ciclo de vida
Menu **Apólices** → abrir a apólice.
1. Separadores **Resumo, Coberturas, Beneficiários, Movimentações, Cobranças, Histórico**. **Esperado:** aviso «A cobertura só começa depois de o primeiro pagamento ser registado».
2. **Descarregar apólice**. **Esperado:** documento da apólice.
3. Depois do pagamento (Módulo 17), a apólice fica **Ativa**. Então teste:
   - **Inclusão de beneficiário** (no resumo da cotação ou na apólice) com data pretendida.
   - **Excluir pessoa segura** com data e motivo (10+ caracteres). **Esperado:** «Excluído», histórico preservado.
   - **Registar aviso formal** numa prestação em atraso (referência da carta, novo prazo); **Suspender por incumprimento**; **Terminar por incumprimento** antes do prazo. **Esperado:** recusa «A transição não é permitida neste momento».
   - **Cancelar apólice** (numa apólice de teste) com motivo e data de efeito.

---

## Módulo 17 — Cobranças

Menu **Cobranças** (Gestor ou Administrador).
1. **Esperado:** totais (cobrado, recebido, por receber), filtros (estado, nº da apólice, tomador, vencimento desde/até), paginação.
2. **Detalhes** de uma prestação. **Registar pagamento** da 1.ª prestação da apólice do Módulo 16: data/hora, método (Numerário, Transferência, Multicaixa), referência → **Confirmar pagamento**. **Esperado:** prestação **Paga**; a apólice passa a **Ativa**.
3. **Exportar lista**. **Esperado:** ficheiro com as colunas Apólice; Tomador; Prestação; Vencimento; Valor; Estado; Pago em; Método; Referência.
4. Com o Subscritor, confirme que **Registar pagamento** não aparece.
5. Pagamentos parciais: **Sem ecrã** (o sistema não os regista).

---

## Módulo 18 — Sinistralidade

Menu **Sinistralidade** (Gestor ou Administrador; o Subscritor vê «Acesso não autorizado»).
1. **Escolher cliente** `QA Empresa Kilamba Lda` (com os 30 membros importados no Módulo 11).
2. Separador **Importações:** tipo Sinistros → `08_Sinistros_COM_ERROS_TESTE.xlsx`. **Esperado:** validação com 1 linha válida e 5 erros explicados; não confirme.
3. Sinistros → `04_Exemplo_Historico_Sinistros_36_Meses_TESTE.xlsx`. **Esperado:** 177 linhas válidas (inclui um sinistro em USD); confirme.
4. Prémios → `06_Exemplo_Historico_Premios_36_Meses_TESTE.xlsx`. **Esperado:** 36 períodos; confirme.
5. **Resumo:** sinistralidade desde, moeda, **Fator de experiência** (fator, métrica observada vs alvo). **Esperado:** sinistralidade paga próxima de 73%.
6. **Participação nos resultados** e **Projeções**: registe os valores.
7. Crie uma cotação para esta empresa (Módulo 14) e confirme no painel **Sinistralidade** da subscrição que o fator é usado.

---

## Módulo 19 — Portal do cliente

`http://localhost:5173/portal-cliente/acesso`. Testes detalhados de acesso, pedidos, mensagens e renovação: [GUIA_TESTES.md §4](../GUIA_TESTES.md).

1. Entre como **Ana Silva**. Percorra Resumo, Cotações, Apólices, Coberturas/Elegibilidade, Beneficiários (cartão digital), Pagamentos, Notificações, Pedidos, Mensagens, Perfil, Comparar planos (sem preços) e Ajuda.
2. **Primeiro acesso** (`/portal-cliente/primeiro`) e **Esqueci-me** (`/portal-cliente/recuperar`): siga GUIA_TESTES §4.1.
3. Menu **Documentos** do portal: veja «O que falta enviar» e, em **Enviar documento**, escolha a pessoa e o tipo:
   - `02_Evidencia_QA_FICTICIA.pdf`. **Esperado:** aceite, estado «a aguardar análise».
   - `11_Comprovativo_Estudante_QA_FICTICIO.jpg`. **Esperado:** aceite.
   - `10_Formato_Invalido_QA.txt`. **Esperado:** recusado («PDF, JPG ou PNG, até 10 MB»).
4. **Pedidos → Novo pedido** (alteração de dados, inclusão de beneficiário sem data → recusa, 2.º pedido de renovação → recusa).
5. **Mensagens:** envie uma mensagem de teste.
6. Numa cotação aprovada: **Aceitar a cotação**. **Esperado:** cria pedido de aceitação.

---

## Módulo 20 — Atendimento (backoffice do portal)

Menu **Atendimento** (Administrador). Separadores **Pedidos**, **Conversas**, **Documentos**.
1. **Pedidos:** abra o pedido criado no Módulo 19 (`/atendimento/pedidos/PED-…`). Mude o estado: Aberto → Em análise → A aguardar o cliente (nota obrigatória) → Aprovado/Rejeitado (nota obrigatória ao rejeitar) → Concluído. **Esperado:** o cliente vê a notificação e o novo estado no portal.
2. **Conversas:** responda à mensagem da Ana. **Esperado:** aparece no portal como resposta por ler.
3. **Documentos:** filtre por estado/tipo, **Analisar** o PDF do Módulo 19 → **Descarregar ficheiro** → **Aprovar**. **Esperado:** «Documento aceite» e reavaliação («a pessoa ficou ativa (coberta) em N apólice(s)» ou «nenhuma apólice passou a ativa»).
4. **Recusar** o JPG sem nota. **Esperado:** nota obrigatória. Com nota: o cliente vê o motivo no portal.

---

## Módulo 21 — Dashboard, notificações, pesquisa e auditoria

Administrador.
1. **Dashboard:** indicadores refletem as cotações, apólices e pagamentos criados nos testes.
2. **Notificações** (sino e `/notificacoes`): lista completa; marcar como lida.
3. **Pesquisa** (barra superior): procure `QA Maria`, o número da cotação e o número da apólice. **Esperado:** resultados agrupados que abrem o registo.
4. **Auditoria:** filtre por tipo de registo (Cotação, Apólice, Proponente, Pessoa segura, Elegibilidade, Cálculo de prémio, Produto, Plano, Pedido do portal, Utilizador, Configuração de negócio), período e texto. **Esperado:** linha temporal com utilizador, entidade, data e descrição das ações dos módulos anteriores. Pesquisa por identificador técnico: cole o identificador de correlação de uma mensagem de erro, se tiver tido alguma.

---

## Ocorrências conhecidas de sessões anteriores

| Data | Módulo | Ocorrência | Estado nesta revisão |
|---|---|---|---|
| 31/10/2026 | 4 | Limites, franquias e edição de coberturas/planos não acessíveis | A interface tem agora **Parametrizar** (por cobertura do plano) e **Configurações do plano**. Volte a testar no 4.3. |
| 31/10/2026 | 5 | Sem botão para submeter o rascunho do modelo atuarial | Continua sem botão na Tarifação; usar **Configuração avançada** (5.1, passo 3). |
| 31/10/2026 | 9 | Aprovações pendentes ficou em «A carregar a fila…» | Por confirmar no Módulo 9. |
| 31/10/2026 | 11 | Organização exige setor/região sem valores disponíveis | Resolvido ao publicar o modelo atuarial (5.1). |

## Ficha para me reportar cada módulo

```text
Módulo:
Perfil usado:
Passos concluídos:
Passos com falha (nº do passo + o que apareceu):
Mensagem de erro exata:
Estado: PASSOU / FALHOU / SEM ECRÃ
Captura de ecrã:
```

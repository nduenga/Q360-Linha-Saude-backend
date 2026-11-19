# Guia para preparar os modelos de proposta DOCX do Q360

Este guia aplica-se aos oito ficheiros Word desta pasta. Os ficheiros originais devem ser preservados. As cópias preparadas estão em `Q360_PREPARADOS_FINAL/`; o inventário de campos não fornecidos está em `CAMPOS_NAO_FORNECIDOS_PELO_GERADOR_Q360.md`.

## Modelos incluídos

| Plano | Versão individual | Versão de grupo |
| --- | --- | --- |
| Business | `Protteja_Saude_Business_Individual.docx` | `Protteja_Saude_Business_Grupo.docx` |
| Business Plus | `Protteja_Saude_Business_Plus_Individual.docx` | `Protteja_Saude_Business_Plus_Grupo.docx` |
| Premium | `Protteja_Saude_Premium_Individual.docx` | `Protteja_Saude_Premium_Grupo.docx` |
| Premium Plus | `Protteja_Saude_Premium_Plus_Individual.docx` | `Protteja_Saude_Premium_Plus_Grupo.docx` |

Na geração da proposta, a interface mostra nomes legíveis como **Protteja Saúde · Business Plus · Individual e Familiar** e **Protteja Saúde · Business Plus · Grupo**. Os códigos internos continuam estáveis para o backend.

Os PDFs correspondentes são referências visuais. O PDF só deve ser carregado como fundo/papel timbrado se estiver sem dados do exemplo e sem conteúdo que se sobreponha ao texto gerado.

## O que é substituído automaticamente

Escreva cada marcador exatamente como aparece abaixo, incluindo `{{` e `}}`. No Word, aplique o mesmo formato ao marcador inteiro; não altere a fonte ou o estilo a meio dele.

### Dados da proposta

| Marcador | Valor preenchido pelo Q360 |
| --- | --- |
| `{{quote.number}}` | Número da cotação |
| `{{quote.date}}` | Data da cotação |
| `{{quote.validUntil}}` | Validade da proposta |
| `{{quote.type}}` | Novo negócio ou renovação |
| `{{document.number}}` | Número do documento gerado |
| `{{document.date}}` | Data de emissão |
| `{{client.name}}` | Nome do proponente/tomador |
| `{{client.nif}}` | NIF ou identificação |
| `{{client.email}}` | Email, se disponível |
| `{{client.phone}}` | Telefone, se disponível |
| `{{plan.name}}` | Nome do plano |
| `{{plan.product}}` | Produto |
| `{{plan.segment}}` | Segmento |
| `{{plan.accessSystem}}` | Sistema de acesso |
| `{{premium.total}}` | Prémio total calculado |
| `{{premium.currency}}` | Moeda |
| `{{scenario.name}}` | Nome do cenário de tarifação |
| `{{insured.count}}` | Número de pessoas seguras |

Exemplo de texto: `Proposta {{quote.number}} para {{client.name}}, válida até {{quote.validUntil}}.`

### Tabelas de conteúdo variável

Para cada lista vertical, mantenha uma linha-modelo com os marcadores. O Q360 duplica a linha para cada item; linhas-modelo consecutivas podem definir as faixas alternadas do modelo. Nas quatro células do fracionamento e nas duas colunas de exclusões, os itens são distribuídos horizontalmente para preservar a disposição original:

| Lista | Marcadores disponíveis |
| --- | --- |
| Pessoas seguras | `{{insured.name}}`, `{{insured.relationship}}`, `{{insured.age}}`, `{{insured.status}}` |
| Coberturas contratadas | `{{coverage.name}}`, `{{coverage.capital}}`, `{{coverage.coinsurance}}`, `{{coverage.copay}}`, `{{coverage.regime}}` |
| Prémios individuais/familiares | `{{premiumMember.name}}`, `{{premiumMember.relationship}}`, `{{premiumMember.age}}`, `{{premiumMember.ageBand}}`, `{{premiumMember.total}}` |
| Prémios de grupo | `{{premiumCategory.relationship}}`, `{{premiumCategory.profile}}`, `{{premiumCategory.count}}`, `{{premiumCategory.perCapita}}`, `{{premiumCategory.total}}` |
| Fracionamento | `{{paymentOption.frequency}}`, `{{paymentOption.amount}}`, `{{paymentOption.paymentSummary}}` |
| Carências | `{{waiting.coverage}}`, `{{waiting.text}}` |
| Exclusões | `{{exclusion.text}}` |
| Condições | `{{condition.text}}` |

Exemplo: numa tabela com cabeçalhos “Pessoa”, “Relação” e “Idade”, crie uma linha com `{{insured.name}}`, `{{insured.relationship}}` e `{{insured.age}}`. Não copie essa linha para cada beneficiário: o sistema repete-a.

As listas de coberturas, carências, exclusões e condições refletem o conteúdo que o Q360 tem para a cotação. A lista de coberturas inclui apenas as contratadas.

## O que retirar ou rever nos modelos de referência

Os documentos atuais são simulações preenchidas. Antes de os usar como modelos:

1. Substitua os dados do exemplo nos campos variáveis pelos marcadores acima: empresa/tomador, NIF, referência, datas, prémio total, número de pessoas seguras e dados da cotação.
2. Remova os valores de exemplo que o Q360 não fornece como variável, em especial prémios per capita, quantidades por categoria, descontos de grupo e médias de idade. Não os mantenha como se fossem calculados para a cotação atual.
3. Converta a tabela de pessoas seguras para uma linha-modelo com os marcadores da lista “Pessoas seguras”.
4. Reveja a tabela de coberturas. Use os marcadores disponíveis para nome, capital/limite, participação/franquia e carência. Descrições comerciais, regime detalhado e composição tarifária por cobertura não são campos substituíveis no gerador atual; mantenha-os apenas se forem verdadeiros para todos os contratos daquele modelo.
5. Remova ou atualize nomes, números, datas, NIFs, assinaturas, referências, condições particulares e qualquer outra informação específica da simulação original.
6. Guarde em formato `.docx` (não `.doc`) e faça uma revisão visual após a geração.

O Q360 preenche marcadores em parágrafos, cabeçalhos, rodapés, tabelas, caixas de texto, notas e comentários. As linhas repetíveis devem permanecer numa tabela normal: uma caixa de texto tem posição fixa e não deve ser usada para repetir linhas. Um marcador dividido por estilos diferentes também pode não ser reconhecido. Não deixe `{{marcadores}}` que não estejam nesta lista: o sistema recusa marcas desconhecidas.

## Como escolher e carregar os oito modelos

Cada variante deve ter uma versão própria preparada e um código de modelo inequívoco (por exemplo, `PROTTEJA_BUSINESS_INDIVIDUAL` e `PROTTEJA_BUSINESS_GRUPO`). Carregue cada DOCX num rascunho do tipo **Proposta de cotação** na Administração de modelos de documentos, associe o código correspondente e use a pré-visualização antes de publicar.

O nome do ficheiro não faz o Q360 selecionar automaticamente o modelo. Depois de publicados, os oito modelos aparecem na lista **Modelo de documento** ao gerar a proposta; escolha Individual e Familiar ou Grupo e o nível correspondente. A geração envia o código interno do modelo escolhido.

## Carga conjunta no tenant Protteja

O seeder de referência aceita carregar produtos, planos e oito DOCX no mesmo tenant. É necessário indicar uma conta ADMIN Protteja diferente da conta técnica que executa o seed, para respeitar a aprovação por duas pessoas. Exemplo:

```sh
python3 manage.py seed_full_database --profile reference \
  --prod-tenant-code protteja --prod-tenant-name 'Protteja Seguros' \
  --include-protteja --protteja-approver-email admin@protteja.ao \
  --publish-protteja-example-tariff --admin-email admin@protteja.ao
```

O ADMIN é criado antes da carga Protteja e aprova as configurações numa identidade distinta da conta técnica que executa o seeder. `--publish-protteja-example-tariff` é uma confirmação explícita: os prémios nos ficheiros de proposta são indicativos e não substituem a tarifa oficial. O comando não apaga nem altera produtos/planos existentes; cria os novos, publica as configurações de teste com a aprovação indicada e deixa os DOCX disponíveis na cotação. A tarifa Individual fornecida pelas propostas não cobre 51–65 anos; o motor continuará a recusar cálculos nessa faixa em vez de inventar um prémio.

Para acrescentar produtos ou planos de teste, edite a lista declarativa e as funções de configuração em `backend/apps/product/seed/protteja_saude.py`, usando códigos únicos. O seed preserva os registos existentes e permite reexecutar a carga sem duplicar produtos, planos ou modelos.

## Verificação antes de publicar cada modelo

- Pré-visualize o DOCX no Q360 e confirme que todos os marcadores foram substituídos.
- Confira nome/NIF, produto/plano, datas e prémio contra a cotação usada no teste.
- Teste com mais de uma pessoa segura para confirmar que a linha da tabela se repete corretamente.
- Confira as coberturas contratadas e confirme que nenhum dado fixo do exemplo ficou no documento.
- Gere PDF e confira paginação, margens, cabeçalhos, rodapés e assinatura.
- Só publique depois da revisão; use uma nova versão do modelo para alterações posteriores.

## Limites do gerador atual

O gerador não recalcula dados que estejam escritos diretamente no Word. Também não substitui tabelas arbitrárias nem dados sem marcador. Se for necessário mostrar preço por pessoa, contagens por parentesco, descontos, assinatura dinâmica ou detalhes de cobertura além dos marcadores disponíveis, é preciso ampliar o contrato e o gerador antes de incluir esses campos nos modelos.

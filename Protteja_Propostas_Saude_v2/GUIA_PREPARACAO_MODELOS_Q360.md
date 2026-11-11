# Guia para preparar os modelos de proposta DOCX do Q360

Este guia aplica-se aos oito ficheiros Word desta pasta. Os ficheiros originais devem ser preservados. As cópias preparadas estão em `Q360_PREPARADOS_FINAL/`; o inventário de campos não fornecidos está em `CAMPOS_NAO_FORNECIDOS_PELO_GERADOR_Q360.md`.

## Modelos incluídos

| Plano | Versão individual | Versão de grupo |
| --- | --- | --- |
| Business | `Protteja_Saude_Business_Individual.docx` | `Protteja_Saude_Business_Grupo.docx` |
| Business Plus | `Protteja_Saude_Business_Plus_Individual.docx` | `Protteja_Saude_Business_Plus_Grupo.docx` |
| Premium | `Protteja_Saude_Premium_Individual.docx` | `Protteja_Saude_Premium_Grupo.docx` |
| Premium Plus | `Protteja_Saude_Premium_Plus_Individual.docx` | `Protteja_Saude_Premium_Plus_Grupo.docx` |

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

Para cada lista, mantenha no documento uma única linha-modelo com os marcadores. O Q360 duplica essa linha para cada item e preenche os campos:

| Lista | Marcadores disponíveis |
| --- | --- |
| Pessoas seguras | `{{insured.name}}`, `{{insured.relationship}}`, `{{insured.age}}`, `{{insured.status}}` |
| Coberturas contratadas | `{{coverage.name}}`, `{{coverage.limits}}`, `{{coverage.participation}}`, `{{coverage.waiting}}`, `{{coverage.priorApproval}}` |
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

O Q360 preenche marcadores em parágrafos, cabeçalhos, rodapés e tabelas. Marcadores em caixas de texto/formas não são suportados. Um marcador dividido por estilos diferentes também pode não ser reconhecido. Não deixe `{{marcadores}}` que não estejam nesta lista: o sistema recusa marcas desconhecidas.

## Como escolher e carregar os oito modelos

Cada variante deve ter uma versão própria preparada e um código de modelo inequívoco (por exemplo, `PROTTEJA_BUSINESS_INDIVIDUAL` e `PROTTEJA_BUSINESS_GRUPO`). Carregue cada DOCX num rascunho do tipo **Proposta de cotação** na Administração de modelos de documentos, associe o código correspondente e use a pré-visualização antes de publicar.

O nome do ficheiro não faz o Q360 selecionar automaticamente o modelo. A cotação tem de pedir o código de modelo correspondente. A seleção automática por produto/plano exige uma associação explícita entre os produtos do catálogo e os códigos dos modelos.

## Verificação antes de publicar cada modelo

- Pré-visualize o DOCX no Q360 e confirme que todos os marcadores foram substituídos.
- Confira nome/NIF, produto/plano, datas e prémio contra a cotação usada no teste.
- Teste com mais de uma pessoa segura para confirmar que a linha da tabela se repete corretamente.
- Confira as coberturas contratadas e confirme que nenhum dado fixo do exemplo ficou no documento.
- Gere PDF e confira paginação, margens, cabeçalhos, rodapés e assinatura.
- Só publique depois da revisão; use uma nova versão do modelo para alterações posteriores.

## Limites do gerador atual

O gerador não recalcula dados que estejam escritos diretamente no Word. Também não substitui tabelas arbitrárias nem dados sem marcador. Se for necessário mostrar preço por pessoa, contagens por parentesco, descontos, assinatura dinâmica ou detalhes de cobertura além dos marcadores disponíveis, é preciso ampliar o contrato e o gerador antes de incluir esses campos nos modelos.

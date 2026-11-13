# Guia técnico: criação e edição de modelos DOCX no Q360

Este guia destina-se a **todas as seguradoras/tenants** que precisem de criar ou editar modelos DOCX no Q360. Explica como preservar o design, escolher marcadores suportados, carregar um modelo, pré-visualizar, testar e publicar. Os nomes, logótipos, textos comerciais e legais são próprios de cada seguradora; o catálogo de variáveis é o disponibilizado pelo Q360 para o tipo de documento escolhido.

Atualmente, os tipos de modelo Word são `QUOTE_PROPOSAL` (proposta de cotação) e `POLICY` (apólice). Consulte `GET /api/v1/document-templates/schema`: os catálogos estão em `word.QUOTE_PROPOSAL` e `word.POLICY`. Não se passa `documentType` como parâmetro nessa consulta. Marcadores personalizados da seguradora não são criados automaticamente: use apenas os campos do catálogo ou solicite uma alteração ao produto Q360. A implementação está em [word_template.py](../backend/apps/quote/application/word_template.py).

## 1. Princípios comuns a qualquer seguradora

- Cada modelo pertence ao tenant autenticado. Crie e carregue o modelo no contexto da seguradora correta.
- Escolha o `documentType` e um `templateCode` identificável para seguradora, produto e segmento. Por exemplo: `ALFA_SAUDE_PROPOSTA_GRUPO`. O código deve ser usado depois na geração; o nome do ficheiro ou o plano não escolhe o modelo automaticamente.
- O design e os textos fixos podem variar por seguradora. Os marcadores e os dados que o Q360 preenche dependem do `documentType` e do catálogo publicado pelo endpoint de esquema.
- Para uma atualização, crie uma nova versão do modelo. Não altere um modelo publicado; as propostas/documentos já gerados são snapshots e não mudam quando uma nova versão é publicada.
- A seguradora deve aprovar os textos contratuais, comerciais, logótipos e assinaturas antes da publicação.

## 2. Exemplo: modelos Protteja e respetivos códigos

Os modelos Protteja abaixo são apenas um exemplo de organização por produto e segmento. Cada seguradora define os seus próprios códigos e ficheiros. Use uma variante compatível com o risco/produto da cotação; o código do modelo é enviado explicitamente no pedido de geração.

| Produto | Segmento | Ficheiro em `Q360_PREPARADOS_FORMATADOS` | `templateCode` |
|---|---|---|---|
| Business | Individual | `Protteja_Saude_Business_Individual.docx` | `PROTTEJA_BUSINESS_INDIVIDUAL` |
| Business | Grupo | `Protteja_Saude_Business_Grupo.docx` | `PROTTEJA_BUSINESS_GRUPO` |
| Business Plus | Individual | `Protteja_Saude_Business_Plus_Individual.docx` | `PROTTEJA_BUSINESS_PLUS_INDIVIDUAL` |
| Business Plus | Grupo | `Protteja_Saude_Business_Plus_Grupo.docx` | `PROTTEJA_BUSINESS_PLUS_GRUPO` |
| Premium | Individual | `Protteja_Saude_Premium_Individual.docx` | `PROTTEJA_PREMIUM_INDIVIDUAL` |
| Premium | Grupo | `Protteja_Saude_Premium_Grupo.docx` | `PROTTEJA_PREMIUM_GRUPO` |
| Premium Plus | Individual | `Protteja_Saude_Premium_Plus_Individual.docx` | `PROTTEJA_PREMIUM_PLUS_INDIVIDUAL` |
| Premium Plus | Grupo | `Protteja_Saude_Premium_Plus_Grupo.docx` | `PROTTEJA_PREMIUM_PLUS_GRUPO` |

Os oito DOCX de `Q360_PREPARADOS_FORMATADOS` foram verificados: todos usam o mesmo conjunto de **32 marcadores**, resumido na secção 7. As versões individuais e de grupo diferem no texto/design comercial, não no contrato dos marcadores. Preserve os ficheiros originais e edite cópias da pasta preparada/formatada.

## 3. Como o preenchimento preserva o Word

O gerador parte do DOCX carregado e substitui apenas os textos `{{marcador}}`. Não reconstrói o documento. Estrutura, tabelas, imagens, logótipos, cores, estilos, fontes, tamanhos, cabeçalhos, rodapés e texto fixo permanecem no ficheiro.

O texto substituído herda a formatação do trecho do marcador no Word. Para controlar fonte, tamanho, cor, negrito, itálico ou alinhamento:

1. Selecione o marcador completo no Word.
2. Aplique ao marcador o estilo pretendido para o valor final.
3. Mantenha todo o marcador com o mesmo estilo. Se o Word o dividir em vários trechos com formatações diferentes, o valor recebe a formatação do primeiro trecho.
4. Gere uma pré-visualização e confirme o resultado real. Valores mais longos podem ocupar mais linhas ou páginas; o gerador não reduz a fonte nem corta o texto automaticamente.

Os marcadores podem ser usados no corpo, em tabelas, cabeçalhos, rodapés, caixas de texto, notas de rodapé/fim e comentários do Word. Para conteúdo visível ao cliente, use o corpo, cabeçalho, rodapé ou uma tabela; comentários e notas não são substitutos de texto contratual.

## 4. Mover, remover e repetir variáveis

### Mover uma variável

- Pode mover um marcador simples, por exemplo `{{client.name}}`, para outro parágrafo, célula, cabeçalho ou rodapé.
- No Word, corte e cole **o marcador completo**, incluindo `{{` e `}}`; não altere o nome nem deixe uma das chavetas para trás.
- Volte a aplicar ao marcador o estilo pretendido na posição de destino.
- As variáveis simples não controlam a posição de outros elementos. O espaço que ocupam depende do tamanho do valor e da largura disponível.

### Remover uma variável

- Apague o marcador completo, não apenas o nome dentro das chavetas. O texto fixo adjacente (rótulo, pontuação ou unidade) não é apagado automaticamente.
- Não é obrigatório usar todos os marcadores disponíveis. A validação exige apenas que reste pelo menos um marcador conhecido no DOCX.
- Se deixar o marcador e a fonte de dados não tiver valor, o gerador imprime `—`. Para não mostrar nada, remova o marcador do modelo.
- Se remover todos os marcadores de uma linha-modelo repetível, o Q360 deixa de reconhecer a linha como repetível. Apague a linha manualmente se já não quiser essa linha fixa.

### Linhas e parágrafos repetíveis

Os marcadores de lista usam uma linha de tabela ou um parágrafo como modelo. O gerador duplica essa linha/parágrafo uma vez por elemento:

```text
| {{insured.name}} | {{insured.relationship}} | {{insured.age}} |
```

Mantenha na mesma linha apenas marcadores da **mesma lista** (por exemplo, `insured.*` juntos). Não misture `insured.*` e `coverage.*` na mesma linha. Para uma tabela de coberturas, use outra linha-modelo com apenas `coverage.*`.

- O sistema duplica a linha/parágrafo que contém o marcador da lista; não duplica automaticamente a tabela inteira nem cria cabeçalhos.
- Coloque os cabeçalhos como texto fixo numa linha separada.
- Se a lista não tiver elementos, a linha/parágrafo-modelo é removido do resultado.
- Para retirar um campo de uma lista, remova apenas esse marcador da célula; os restantes campos da mesma lista continuam a repetir.
- Não use uma caixa de texto como linha-modelo de tabela. Para dados tabulares, use uma tabela normal do Word.

## 5. Catálogo de variáveis de proposta

Escreva os nomes exatamente como abaixo, incluindo maiúsculas/minúsculas. A forma reconhecida é `{{nome.da.variavel}}`; não use espaços, acentos ou nomes inventados. Marcadores desconhecidos fazem a validação do modelo falhar.

### Valores simples

| Marcador | Valor fornecido |
|---|---|
| `{{quote.number}}` | Número da cotação. |
| `{{quote.date}}` | Data da cotação formatada. |
| `{{quote.validUntil}}` | Data de validade da proposta. |
| `{{quote.type}}` | Tipo de cotação (novo negócio ou renovação). |
| `{{document.number}}` | Número do documento; na pré-visualização pode aparecer como “(a atribuir)”. |
| `{{document.date}}` | Data de emissão formatada. |
| `{{client.name}}` | Nome do cliente/tomador. |
| `{{client.nif}}` | NIF ou identificação. |
| `{{client.email}}` | Email, se registado. |
| `{{client.phone}}` | Telefone, se registado. |
| `{{plan.name}}` | Nome do plano. |
| `{{plan.product}}` | Nome do produto. |
| `{{plan.segment}}` | Segmento do plano. |
| `{{plan.tier}}` | Nível do plano, se configurado. |
| `{{plan.category}}` | Categoria do plano, se configurada. |
| `{{plan.accessSystem}}` | Sistema de acesso configurado. |
| `{{plan.networkRegions}}` | Regiões da rede configurada, se disponíveis. |
| `{{premium.total}}` | Prémio total já formatado com a moeda. |
| `{{premium.totalText}}` | Prémio total por extenso/formatado, conforme o conteúdo devolvido pelo backend; atualmente tem o mesmo valor formatado de `premium.total`. |
| `{{premium.currency}}` | Código da moeda. |
| `{{scenario.name}}` | Nome do cenário selecionado, se houver. |
| `{{insured.count}}` | Número de pessoas seguras incluídas na proposta. |

Email, telefone, nível/categoria, regiões da rede e cenário podem estar vazios consoante os dados da cotação. Um marcador mantido no modelo sem valor é substituído por `—`.

### Listas repetíveis

Cada grupo abaixo representa os nomes válidos da lista. Na linha-modelo, use apenas os campos do mesmo grupo.

| Grupo e uso | Marcadores disponíveis |
|---|---|
| **Pessoas seguras** — um elemento por pessoa | `{{insured.name}}`, `{{insured.relationship}}`, `{{insured.age}}`, `{{insured.status}}`, `{{insured.eligibility}}`, `{{insured.eligibilityDecisionText}}`, `{{insured.eligibilityEvidence}}`, `{{insured.clinicalQuestionnaireRequired}}`, `{{insured.medicalExamRequired}}`, `{{insured.preExistingMode}}`, `{{insured.preExistingText}}`, `{{insured.preExistingCondition}}`, `{{insured.preExistingWaitingMonths}}`, `{{insured.preExistingLoadingPct}}`, `{{insured.preExistingSublimit}}` |
| **Coberturas contratadas** — uma linha por cobertura contratada | `{{coverage.name}}`, `{{coverage.limits}}`, `{{coverage.participation}}`, `{{coverage.waiting}}`, `{{coverage.priorApproval}}`, `{{coverage.category}}`, `{{coverage.inclusion}}`, `{{coverage.regime}}`, `{{coverage.networkCopay}}`, `{{coverage.reimbursementCopay}}`, `{{coverage.networkCoinsurancePct}}`, `{{coverage.reimbursementCoinsurancePct}}`, `{{coverage.networkAnnualDeductible}}`, `{{coverage.reimbursementAnnualDeductible}}`, `{{coverage.destinations}}`, `{{coverage.closedDiseaseList}}`, `{{coverage.maxDaysPerYear}}`, `{{coverage.timeDeductibleDays}}`, `{{coverage.currency}}`, `{{coverage.notes}}`, `{{coverage.excludedItems}}`, `{{coverage.indicative}}` |
| **Disponibilidade das coberturas** — uma linha por cobertura oferecida | `{{coverageOption.name}}`, `{{coverageOption.category}}`, `{{coverageOption.inclusion}}`, `{{coverageOption.contracted}}` |
| **Prémio por pessoa** | `{{premiumMember.name}}`, `{{premiumMember.relationship}}`, `{{premiumMember.total}}` |
| **Prémio agregado por parentesco** | `{{premiumCategory.relationship}}`, `{{premiumCategory.count}}`, `{{premiumCategory.total}}` |
| **Linhas do cálculo do prémio** — linhas por pessoa e/ou cotação | `{{pricingLine.member}}`, `{{pricingLine.code}}`, `{{pricingLine.type}}`, `{{pricingLine.base}}`, `{{pricingLine.factor}}`, `{{pricingLine.adjustment}}`, `{{pricingLine.result}}`, `{{pricingLine.ageBand}}`, `{{pricingLine.source}}`, `{{pricingLine.sourceVersion}}` |
| **Opções indicativas de pagamento** | `{{paymentOption.frequency}}`, `{{paymentOption.count}}`, `{{paymentOption.amount}}`, `{{paymentOption.total}}`, `{{paymentOption.loadingPct}}`, `{{paymentOption.indicative}}` |
| **Ajustes do prémio** | `{{adjustment.text}}` |
| **Opção de participação** | `{{participationOption.code}}`, `{{participationOption.name}}`, `{{participationOption.annualDeductible}}`, `{{participationOption.copayPerConsultation}}`, `{{participationOption.reimbursementPct}}`, `{{participationOption.premiumAdjustmentPct}}`, `{{participationOption.hospitalOnly}}` |
| **Documentos necessários** | `{{requiredDocument.documentType}}`, `{{requiredDocument.description}}` |
| **Informações do produto** | `{{businessText.title}}`, `{{businessText.text}}` |
| **Exclusões** | `{{exclusion.text}}` |
| **Condições** | `{{condition.text}}` |
| **Carências** | `{{waiting.coverage}}`, `{{waiting.text}}` |

As opções de pagamento são indicativas, não uma frequência já escolhida pelo cliente. `coverage.*` lista apenas coberturas contratadas; use `coverageOption.*` para mostrar disponibilidade e estado contratado/não contratado.

`installment.*` representa prestações efetivas de apólice e não deve ser usado numa proposta de cotação. Consulte o endpoint de esquema antes de acrescentar marcadores.

## 6. Catálogo de variáveis de apólice

Os seguintes marcadores simples específicos de apólice constam do catálogo `word.POLICY`:

| Marcador | Valor fornecido |
|---|---|
| `{{quote.number}}` | Número da cotação de origem. |
| `{{policy.number}}` | Número da apólice. |
| `{{policy.status}}` | Estado da apólice. |
| `{{policy.type}}` | Tipo (individual ou grupo). |
| `{{policy.issueDate}}` | Data de emissão da apólice. |
| `{{policy.startDate}}` | Início de vigência. |
| `{{policy.endDate}}` | Fim de vigência. |
| `{{policy.termMonths}}` | Duração em meses. |
| `{{policy.paymentFrequency}}` | Fracionamento do prémio. |
| `{{policy.totalPremium}}` | Prémio total anual. |
| `{{signature.name}}` | Nome de quem assinou. |
| `{{signature.document}}` | Documento de identificação de quem assinou. |
| `{{signature.capacity}}` | Qualidade de quem assinou. |
| `{{signature.date}}` | Data da assinatura. |
| `{{payment.firstDate}}` | Data do primeiro pagamento. |
| `{{payment.firstMethod}}` | Meio do primeiro pagamento. |
| `{{payment.firstReference}}` | Referência do primeiro pagamento. |

O tipo `POLICY` também disponibiliza os campos comuns e os grupos repetíveis apresentados pelo endpoint de esquema. O grupo `installment.*` é específico das prestações da apólice:

| Marcador | Valor fornecido |
|---|---|
| `{{installment.no}}` | Número da prestação. |
| `{{installment.period}}` | Período da prestação. |
| `{{installment.dueDate}}` | Data de vencimento. |
| `{{installment.amount}}` | Valor da prestação. |
| `{{installment.status}}` | Estado da prestação. |

Confirme no esquema e numa pré-visualização que cada campo tem dados no contexto real antes de o incluir no documento.

## 7. Exemplo: marcadores usados nos oito modelos Protteja

Os oito modelos Protteja preparados/formatados contêm o seguinte conjunto. Esta lista é apenas uma referência; outras seguradoras podem escolher outros marcadores do catálogo aplicável. Só inclua dados fornecidos pelo Q360 e pertinentes para o produto:

- **Cotação:** `{{quote.number}}`, `{{quote.date}}`, `{{quote.validUntil}}`, `{{quote.type}}`.
- **Cliente:** `{{client.name}}`, `{{client.nif}}`.
- **Plano:** `{{plan.name}}`, `{{plan.product}}`, `{{plan.segment}}`, `{{plan.accessSystem}}`.
- **Prémio e população:** `{{premium.total}}`, `{{premium.currency}}`, `{{insured.count}}`.
- **Pessoas seguras:** `{{insured.name}}`, `{{insured.relationship}}`, `{{insured.age}}`, `{{insured.status}}`, `{{insured.preExistingText}}`.
- **Coberturas:** `{{coverage.name}}`, `{{coverage.limits}}`, `{{coverage.participation}}`, `{{coverage.waiting}}`, `{{coverage.priorApproval}}`.
- **Outras listas:** `{{paymentOption.frequency}}`, `{{paymentOption.count}}`, `{{paymentOption.amount}}`, `{{paymentOption.total}}`, `{{paymentOption.indicative}}`, `{{adjustment.text}}`, `{{waiting.text}}`, `{{exclusion.text}}`, `{{condition.text}}`.

## 8. Criar, carregar e testar um modelo

1. **Defina o tipo de documento**, produto, segmento, `templateCode` e período de vigência. Use um código claro e consistente para a seguradora; cada código identifica o modelo selecionável na geração.
2. **Prepare o DOCX** com o design aprovado pela seguradora. Pode começar por um documento novo ou por uma cópia de um modelo existente; remova os exemplos e os dados fictícios.
3. **Edite no Microsoft Word** o texto fixo, a posição dos marcadores e a formatação dos próprios marcadores. Não substitua conteúdo contratual aprovado sem validação do responsável do produto/seguradora.
4. **Use apenas marcadores do esquema** do `documentType` e confirme que existe pelo menos um marcador conhecido. A validação acontece ao carregar o DOCX.
5. **Crie um rascunho e carregue o DOCX** na Administração de modelos ou pela API. A criação pela API usa `POST /api/v1/document-templates`:

   ```json
   {
     "documentType": "QUOTE_PROPOSAL",
     "templateCode": "ALFA_SAUDE_PROPOSTA_GRUPO",
     "effectiveFrom": "2026-11-13"
   }
   ```

   Carregue o ficheiro `.docx` como multipart no `POST /api/v1/document-templates/{id}/word`, no campo `file` (limite atual: 10 MB). A API requer permissões de administração/gestão de produtos e usa o tenant autenticado. Uma alteração ao conteúdo deve ser carregada numa nova versão, não sobre um modelo publicado.

6. **Pré-visualize o DOCX** através da Administração ou de `GET /api/v1/document-templates/{id}/preview` e confirme os valores, estilos, paginação, cabeçalhos, rodapés e linhas repetidas. O preview usa dados de exemplo; faça também um teste com dados reais representativos.
7. **Gere um documento de teste** do tipo e formato pretendidos, enviando o código explícito do modelo. Para propostas, teste cenários individual e de grupo, várias pessoas seguras e dados opcionais em falta. Para apólices, teste os dados de vigência, assinatura e prestações disponíveis.
8. **Publique apenas depois de validar** conteúdo fixo, variáveis e resultado visual. Pela API, a publicação é feita com `POST /api/v1/document-templates/{id}/publish`; após publicar, use uma nova versão para alterações.

Para modelos Protteja já preparados, existe ainda o comando específico `install_protteja_quote_templates`. Esse instalador e os ficheiros `Q360_PREPARADOS_FORMATADOS` são exclusivos desse exemplo e não são necessários para outras seguradoras.

### Exemplo de seleção

O pedido de geração usa o identificador da cotação e o modelo:

```json
{
  "format": "DOCX",
  "templateCode": "ALFA_SAUDE_PROPOSTA_GRUPO"
}
```

Os documentos já gerados são snapshots e não mudam quando o modelo é atualizado. Gere outro documento para testar uma nova versão.

## 9. Lista de verificação de publicação

- [ ] Ficheiro `.docx` correto para produto e segmento; não usar `.doc`.
- [ ] Todas as variáveis têm nome válido e chavetas completas.
- [ ] Marcadores têm a mesma fonte, tamanho e estilo que os valores finais devem ter.
- [ ] Cada linha repetível usa apenas uma lista (`insured.*`, `coverage.*`, etc.).
- [ ] Não ficaram dados de exemplo, prémios fictícios, nomes, NIFs, datas ou assinaturas da simulação de origem.
- [ ] Valores longos, listas vazias e múltiplas pessoas foram testados.
- [ ] Textos fixos comerciais/legais foram confirmados pela seguradora.
- [ ] Pré-visualização DOCX e proposta DOCX foram abertas no Word e revistas visualmente.
- [ ] O modelo só foi publicado depois da aprovação.

O esquema devolvido por `GET /api/v1/document-templates/schema` é a referência para os marcadores disponíveis. Os guias [CAMPOS_NAO_FORNECIDOS_PELO_GERADOR_Q360.md](../Protteja_Propostas_Saude_v2/CAMPOS_NAO_FORNECIDOS_PELO_GERADOR_Q360.md), [GUIA_PREPARACAO_MODELOS_Q360.md](../Protteja_Propostas_Saude_v2/GUIA_PREPARACAO_MODELOS_Q360.md) e [GERADOR_PROPOSTAS_PROTTEJA.md](./GERADOR_PROPOSTAS_PROTTEJA.md) descrevem os modelos Protteja e servem apenas como material de exemplo.

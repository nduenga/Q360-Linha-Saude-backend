# Campos das propostas: cobertura do gerador Q360

> Atualizado após a ampliação do conteúdo da proposta e dos marcadores Word. A lista abaixo deixa de significar que todos os campos estão indisponíveis: identifica o que agora tem fonte real no backend e o que continua sem fonte no fluxo de cotação.

Este inventário compara os oito modelos Protteja preparados com os marcadores de **proposta de cotação** reconhecidos pelo Q360. Os DOCX preparados estão em `Q360_PREPARADOS/`; os originais não foram alterados.

## Campos dinâmicos disponíveis

Os modelos preparados usam os seguintes dados:

- Cotação e documento: `quote.number`, `quote.date`, `quote.validUntil`, `quote.type`, `document.number` e `document.date`.
- Tomador e plano: `client.name`, `client.nif`, `client.email`, `client.phone`, `plan.name`, `plan.product`, `plan.segment` e `plan.accessSystem`.
- Prémio: `premium.total` e `premium.currency`.
- Pessoas seguras: `insured.count`, `insured.name`, `insured.relationship`, `insured.age` e `insured.status`.
- Coberturas: `coverage.name`, `coverage.limits`, `coverage.participation`, `coverage.waiting` e `coverage.priorApproval`.
- Conteúdo contratual: `waiting.coverage`, `waiting.text`, `exclusion.text` e `condition.text`.

## Campos das referências agora fornecidos por fontes reais

O conteúdo da proposta e o esquema `GET /document-templates/schema` passam a disponibilizar:

- **Tarifação por pessoa e parentesco:** montantes por pessoa e agregados por relação, obtidos das linhas do cálculo. A faixa etária só aparece quando o próprio motor a gravou na linha de tarifação. Cada linha também expõe código, tipo, base, fator, ajuste, resultado acumulado, origem e versão.
- **Ajustes:** ajustes manuais incluem o motivo registado na cotação. Componentes do cálculo mantêm os valores e a origem gravados pelo motor; não se tenta classificar ou recompor um prémio comercial a partir deles.
- **Periodicidades:** opções anual, semestral, trimestral e mensal calculadas pelas mesmas regras de emissão e fracionamento. São sempre marcadas como indicativas, pois a cotação não contém uma frequência escolhida. Fórmulas do produto são lidas da execução de tarifação correspondente.
- **Coberturas:** regime configurado, copagamento, comparticipação, franquias, limites, carências, destinos, lista fechada de doenças, dias máximos, moeda, notas e caráter indicativo. As opções disponíveis também podem ser listadas com o estado contratado/não contratado.
- **Elegibilidade e subscrição por pessoa:** decisão e evidências da avaliação associada à cotação, requisitos de questionário/exame e decisão de condição preexistente, com os seus campos separados.
- **Contacto do tomador:** email e telefone quando estiverem preenchidos no cadastro.
- **Regiões da rede:** regiões configuradas no plano; destinos de assistência/evacuação continuam a vir da configuração da cobertura.

Os marcadores repetíveis adicionados incluem `{{premiumMember.name}}`, `{{premiumMember.total}}`, `{{premiumCategory.relationship}}`, `{{pricingLine.ageBand}}`, `{{paymentOption.frequency}}`, `{{coverage.networkCopay}}`, `{{coverage.reimbursementCopay}}`, `{{coverage.destinations}}`, `{{insured.eligibilityDecisionText}}` e `{{insured.preExistingText}}`. O esquema completo é a fonte autoritativa dos nomes e campos aceites.

## Campos sem fonte: separar cotação, apólice e dados partilhados

### Pertencem à cotação ou à proposta comercial

Estes campos fazem sentido antes da emissão e poderiam ser associados à própria cotação, mas o backend ainda não guarda a respetiva fonte:

- **Mediador/corretor da cotação** e respetiva licença. Não existe atualmente uma associação do mediador à cotação nem cadastro usado pelo gerador.
- **Motivo para não contratar uma cobertura opcional.** A disponibilidade e o estado contratado/não contratado vêm do plano e da seleção; não há um motivo comercial registado por cotação.
- **Declaração de aceitação da proposta e comprovativo.** É um passo de aceitação da cotação, distinto da assinatura do contrato/apólice. O fluxo atual não guarda essa declaração como documento/decisão de aceitação do cliente.
- **Prémio comercial consolidado antes dos descontos automáticos.** As linhas exatas do motor são fornecidas; não há uma regra aprovada que defina quais componentes compõem esse subtotal. Os ajustes manuais já incluem o motivo registado. Não se deve reconstruir o subtotal somando ou subtraindo linhas.

### Pertencem à emissão ou à apólice no backend atual

Estes dados só são fixados quando a cotação aprovada é convertida em apólice, ou durante o pagamento:

- **Frequência de pagamento escolhida.** Atualmente é guardada em `Policy.payment_frequency` durante a emissão. A cotação pode apresentar as periodicidades como simulações indicativas; para mostrar uma escolha na proposta, o fluxo precisa passar a guardar essa opção na cotação antes da emissão.
- **Prazo contratual e vigência definitiva:** duração, início e fim efetivos. A cotação guarda validade e data de referência do cálculo, não a vigência definitiva. A emissão recebe o prazo e a data de início solicitada; o início efetivo também depende das regras de assinatura e primeiro pagamento.
- **Assinatura contratual:** nome, documento, qualidade/capacidade, data e comprovativo. O modelo `PolicySignature` pertence à apólice.
- **Primeiro pagamento:** método, referência, data, estado e recibo pertencem à prestação/pagamento da apólice. Não devem aparecer numa proposta de cotação como se já tivessem ocorrido.

### Dados institucionais partilhados por cotação e apólice

- **Dados legais da seguradora** (denominação oficial, registo/licença e contactos legais) não estão configurados como fonte dinâmica. São necessários nos dois documentos, mas devem vir de um cadastro/configuração oficial e versionada da seguradora.
- **Dados do mediador** também podem ser impressos na cotação e na apólice, mas primeiro é necessário criar o cadastro e associá-lo à cotação; a apólice poderá herdar esse vínculo na emissão.

Os contactos do tomador não são uma lacuna de contrato: email e telefone são lidos do cadastro quando preenchidos e podem estar vazios quando não foram registados.

## Tratamento aplicado nas cópias preparadas

- Os dados de exemplo do tomador, número de referência, datas, número de pessoas e prémio total foram substituídos por marcadores.
- As tabelas de pessoas e coberturas foram convertidas para linhas-modelo repetíveis pelo Q360.
- A tabela de exclusões e a linha de carências passaram a usar as listas dinâmicas disponíveis.
- As tabelas de prémio per capita, desconto e fracionamento com valores de exemplo, bem como a estimativa mensal, foram removidas para não apresentar valores fictícios como se fossem resultado da cotação.
- As restantes descrições de produto, capitais de destaque, território, mediador, condições legais e contactos Protteja continuam como texto fixo nas cópias. Devem ser validados pela seguradora e pelo responsável do produto antes de publicação, pois o gerador atual não os personaliza.

## Trabalho ainda necessário para preencher os campos sem fonte

Para preencher as lacunas sem distorcer as regras, criar primeiro as fontes de cotação indicadas acima; depois, manter assinatura, vigência efetiva e pagamentos no fluxo de emissão/apólice. A periodicidade só deve ser movida para a cotação se a regra comercial determinar que o cliente a escolhe antes de aceitar a proposta.

Não publique os DOCX preparados como propostas finais enquanto os textos fixos de cobertura e condições não forem confirmados contra o catálogo e as condições contratuais válidas. As opções de pagamento geradas são indicativas; não indicam uma periodicidade contratada.

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

Os marcadores repetíveis incluem `{{premiumMember.name}}`, `{{premiumMember.relationship}}`, `{{premiumMember.age}}`, `{{premiumMember.ageBand}}`, `{{premiumMember.total}}`, `{{premiumCategory.relationship}}`, `{{premiumCategory.profile}}`, `{{premiumCategory.count}}`, `{{premiumCategory.perCapita}}`, `{{premiumCategory.total}}`, `{{paymentOption.frequency}}`, `{{paymentOption.amount}}`, `{{paymentOption.paymentSummary}}`, `{{coverage.capital}}`, `{{coverage.coinsurance}}`, `{{coverage.copay}}`, `{{coverage.regime}}`, `{{insured.eligibilityDecisionText}}` e `{{insured.preExistingText}}`. O esquema completo é a fonte autoritativa dos nomes e campos aceites.

## Campos sem fonte: separar cotação, apólice e dados partilhados

### Pertencem à cotação ou à proposta comercial

Estes campos fazem sentido antes da emissão e poderiam ser associados à própria cotação:

- **Motivo para não contratar uma cobertura opcional.** A disponibilidade e o estado contratado/não contratado vêm do plano e da seleção. O motivo comercial pode ser registado opcionalmente por cobertura na cotação e aparece na proposta.
- **Declaração de aceitação da proposta e comprovativo.** É diferente da assinatura do contrato/apólice. Não é obrigatório preencher este campo na proposta; pode ficar em branco.
- **Prémio comercial antes dos descontos automáticos.** A fórmula depende de dados que ainda faltam: o prémio puro e os carregamentos em valor, ou o índice de despesas percentual e a confirmação de que é uma percentagem do prémio comercial. Também falta definir que custos entram nos carregamentos e em que ordem os descontos automáticos são aplicados. Até esses dados e a regra estarem configurados no motor, o subtotal não deve ser inferido das linhas de cálculo.

  - Se os carregamentos forem valores: `Prémio comercial = prémio puro + soma dos carregamentos`.
  - Se o índice `c` for uma fração do próprio prémio comercial: `Prémio comercial = prémio puro / (1 − c)`, com `0 ≤ c < 1`.

### Cenário fictício para testar a fórmula (não é tarifa Protteja)

Use estes valores apenas numa configuração/tenant de desenvolvimento, identificada como **DEMO — não publicar como tarifa oficial**:

| Campo de teste | Valor |
|---|---:|
| Prémio puro/técnico antes dos carregamentos | 100.000 Kz |
| Despesa administrativa (% do prémio comercial) | 10% |
| Comissão de aquisição (% do prémio comercial) | 5% |
| Margem da seguradora (% do prémio comercial) | 5% |
| Desconto comercial automático aplicado depois dos carregamentos | 10% |

Os carregamentos somam 20% do prémio comercial. Logo, o prémio comercial antes do desconto é `100.000 / (1 − 0,20) = 125.000 Kz`. Aplicando o desconto de 10% depois, o resultado antes de impostos é `112.500 Kz`. Se o desconto for aplicado noutra fase, o resultado muda; a ordem acima faz parte deste cenário de teste.

Este cenário serve para confirmar que a proposta distingue o prémio antes e depois do desconto. Não deve ser carregado como valor por omissão nem publicado para uso comercial. Na tarifa real, o atuário/seguradora deve substituir cada percentagem pelos valores aprovados e confirmar a base e a ordem de aplicação.

### Pertencem à emissão ou à apólice no backend atual

Estes dados só são fixados quando a cotação aprovada é convertida em apólice, ou durante o pagamento:

- **Frequência de pagamento escolhida.** Atualmente é guardada em `Policy.payment_frequency` durante a emissão. A cotação pode apresentar as periodicidades como simulações indicativas; para mostrar uma escolha na proposta, o fluxo precisa passar a guardar essa opção na cotação antes da emissão.
- **Prazo contratual e vigência definitiva:** duração, início e fim efetivos. A cotação guarda validade e data de referência do cálculo, não a vigência definitiva. A emissão recebe o prazo e a data de início solicitada; o início efetivo também depende das regras de assinatura e primeiro pagamento.
- **Assinatura contratual:** nome, documento, qualidade/capacidade, data e comprovativo. O modelo `PolicySignature` pertence à apólice.
- **Primeiro pagamento:** método, referência, data, estado e recibo pertencem à prestação/pagamento da apólice. Não devem aparecer numa proposta de cotação como se já tivessem ocorrido.

### Dados institucionais fixos nos modelos Protteja

Os DOCX Protteja preparados já incluem os elementos institucionais. Devem permanecer como texto fixo do modelo: **Protteja Seguros, S.A.**, **Certificado de Licença Nº 13/ISS/MF/12**, `geral@prottejaseguros.co.ao`, `prottejaseguros.co.ao`, a referência ao **Provedor do Cliente** e à **ARSEG**. O campo de mediador também fica fixo como consta do modelo: **«A indicar na proposta de seguro.»** Não é necessário pedir esses dados na cotação Protteja.

Os contactos do tomador não são uma lacuna de contrato: email e telefone são lidos do cadastro quando preenchidos e podem estar vazios quando não foram registados.

## Tratamento aplicado nas cópias preparadas

- Os dados de exemplo do tomador, número de referência, datas, número de pessoas e prémio total foram substituídos por marcadores.
- As tabelas de coberturas mantêm a grelha, larguras, cabeçalhos e estilos do modelo oficial; o sistema repete as linhas sem perder as faixas de cor alternadas.
- A tabela de prémios mantém a composição oficial: por pessoa nos modelos individuais/familiares e por categoria nos modelos de grupo. Os valores por pessoa/categoria e o total anual vêm da cotação.
- O fracionamento mantém os quatro blocos horizontais do modelo (anual, semestral, trimestral e mensal), preenchidos com os valores calculados para a cotação.
- A tabela de exclusões e a linha de carências passaram a usar as listas dinâmicas disponíveis.
- As linhas de prémio comercial e desconto de exemplo foram removidas porque o gerador não tem uma fonte aprovada para esses subtotais; o total anual continua a ser preenchido. A estimativa mensal fixa também foi removida, pois o quadro de fracionamento já mostra a opção mensal calculada.
- As restantes descrições de produto, capitais de destaque, território, mediador, condições legais e contactos Protteja continuam como texto fixo nas cópias. Devem ser validados pela seguradora e pelo responsável do produto antes de publicação, pois o gerador atual não os personaliza.

## Trabalho ainda necessário para preencher os campos sem fonte

Para preencher as lacunas sem distorcer as regras, criar primeiro as fontes de cotação indicadas acima; depois, manter assinatura, vigência efetiva e pagamentos no fluxo de emissão/apólice. A periodicidade só deve ser movida para a cotação se a regra comercial determinar que o cliente a escolhe antes de aceitar a proposta.

Não publique os DOCX preparados como propostas finais enquanto os textos fixos de cobertura e condições não forem confirmados contra o catálogo e as condições contratuais válidas. As opções de pagamento geradas são indicativas; não indicam uma periodicidade contratada.

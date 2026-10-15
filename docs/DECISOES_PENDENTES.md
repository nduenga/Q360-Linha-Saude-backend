# Decisões e limitações

As decisões A1–A9 e R1–R2 foram tomadas pelo responsável do produto em
2026-10-14 e estão implementadas. Fica registado o que se decidiu, como foi
aplicado e o que continua em aberto.

## Decisões actuariais / de negócio

| # | Tema | Decisão | Implementação |
|---|---|---|---|
| A1 | Modelo actuarial temporário | Dados, fórmulas, variáveis e valores configuráveis pela interface, com importação de Excel | O modelo (`pricing.actuarial_model`) edita-se pela API de configurações (DRAFT → aprovação → PUBLISHED) e é validado ao gravar (tabelas, taxas, intervalos, valores por omissão). `POST /business-config/actuarial-model/import` cria uma versão DRAFT a partir de um `.xlsx` (com `dryRun`; o ficheiro fica anexado com SHA-256); `GET …/template` dá o Excel de referência; `GET …/catalog` lista as secções e opções editáveis. A importação mantém, por omissão, as partes que não vêm do Excel (opções de cálculo e mapeamentos de planos/coberturas) da versão publicada. Continua a exigir aprovação de um segundo utilizador antes de entrar no cálculo |
| A2 | Coberturas PDF vs Excel | Prevalece o PDF e as suas notas de subscrição | Os planos de mercado (`market_templates.py`) não mudam. Os testes de referência só escolhem as coberturas do cenário do Excel (p.ex. doenças endémicas) para reproduzir o `Calculador`, sem alterar o produto |
| A3 | SAG: colaborador-tipo × n.º | Soma das pessoas reais | Mantido. O teste de referência SAG compara o prémio de um colaborador com o seu agregado (`C86`); `C87` (× 40) é só o método do Excel |
| A4 | Referência SAG / dados recomendados | Preencher com dados recomendados, configuráveis | `calculation_settings.profile_defaults` por segmento: valores de referência do Excel (Luanda, sem participação nos custos, sem venda cruzada; SAG: Comércio e Serviços, adesão obrigatória), que não alteram o prémio; o trace `ACTUARIAL_PROFILE_RESOLVED` indica os campos usados por omissão. Teste de referência SAG: `tests/quote/test_actuarial_excel_reference_sag.py`, com valores esperados do recálculo das fórmulas do próprio Excel (`tools/recalc_calculador.py`; o mesmo método reproduz o cenário SAU guardado com diferença ≤ 5×10⁻⁹) |
| A5 | Agravamento clínico | Configurável; forma recomendada | Mantém-se a decisão do subscritor, com a percentagem por omissão da tabela configurável `underwriting.pre_existing_conditions` (15 % / 30 % / **50 %** — acrescentada a gravidade `MODERATE_HIGH` do Excel). Em grupo o sobreprémio continua impedido (o Excel dá 0 % em SAG obrigatório). A percentagem do prémio é a mesma que aparece na proposta |
| A6 | Idade de adesão em renovações | Configurável; forma recomendada | `calculation_settings.entry_age_on_renewal`: `ORIGINAL_ENTRY_AGE` (recomendado: mantém o agravamento da idade na 1.ª adesão, calculada pela inclusão mais antiga da pessoa numa apólice), `CURRENT_AGE` ou `NOT_APPLIED`. Sem histórico, não aplica e regista `ENTRY_AGE_UNKNOWN` no trace |
| A7 | Arredondamento | Duas casas (0,041 → 0,04) | Já era a regra: cada componente a 2 casas, meio-para-cima (OD-006). Diferença medida no cenário SAU do Excel: +0,02 Kz |
| A8 | Fracionamento | Configurável; forma recomendada | Nova configuração `pricing.fractionation` (Anual 0 %, Semestral 1,5 %, Trimestral 2,5 %, Mensal 4 %, do Excel) aplicada a todas as apólices; sem ela usa-se a tabela do modelo do cálculo; sem nenhuma, partes iguais |
| A9 | Fórmulas por pessoa | Configurável; forma recomendada | Fase `PERSON` em `pricing.formulas` (variáveis `person_amount`, `person_base`, `age`, `members_count`), aplicada depois das regras de risco e antes dos ajustes comerciais e carregamentos |
| R1 | NIF | Único por tenant; obrigatório para todo o cliente conforme o tipo | Proponente: obrigatório, formato do tipo e único (serviço + CHECK `NOT VALID` + índice único). Pessoa segura: opcional; quando indicado, único **no tomador** — a mesma pessoa pode ter ficha com o NIF em tomadores diferentes (p.ex. colaborador de uma empresa e titular de uma apólice individual), revisto em 2026-10-15. Migrações `client/0010` e `client/0011` |
| R2 | Estado REJECTED | Migrar a CHECK | Migração `business_config/0003`; a rejeição deixa a versão `REJECTED`; editar volta a DRAFT; pode ser reenviada |
| C1 | Datas da cotação (2026-10-15) | A cotação tem data de criação e validade (configurável na interface); não tem data de efeito, porque ainda não se sabe se será apólice | Migração `quote/0013` remove a coluna. Validade = dia de criação + `quote.validity_days` (parâmetro editável em `/system-parameters`); ao reabrir uma cotação caducada conta a partir do dia da reabertura. A data de referência do cálculo (idades, configurações, tarifas, fórmulas e regras em vigor) é o **dia do cálculo** enquanto a cotação está aberta (DRAFT/READY): o que se publica na interface vale no próximo cálculo, também em cotações criadas antes. Depois de submetida, o prémio fica congelado e vale o dia do último cálculo (`Quote.reference_date`). O último cálculo só é reaproveitado se nada do que entrou nele mudou (todas as configurações publicadas em vigor, tabelas/parâmetros legados, plano e coberturas, pessoas, escolhas e ajustes). O início da vigência escolhe-se na emissão; nas renovações o formulário propõe o dia a seguir ao fim do período actual (`renewal.proposedStartDate`). `PUT /quotes/{id}` removido (só alterava a data de efeito); clonar e renovar deixam de aceitar a data |

Seed de demonstração: a cliente «Ana» passa a `fabiongila@gmail.com`; a
Empresa Kilamba (que usava esse endereço) passa a
`empresa.kilamba@demo.q360.local`, porque o seeder do portal repõe a conta da
Empresa e apagaria a da Ana se partilhassem o endereço.

## Em aberto

| Tema | Situação |
|---|---|
| Validação actuarial | O modelo continua marcado `DRAFT_REQUIRES_ACTUARIAL_APPROVAL`; os valores são do Excel temporário e têm de ser validados pelo actuário antes de produção |
| Registos antigos sem NIF | A CHECK é `NOT VALID`: os proponentes antigos sem NIF continuam a existir e terão de o indicar na próxima edição |
| SAG com menos de 5 colaboradores | A tabela de dimensão do Excel começa nos 5 («abaixo de 5 → SAU individual»); o cálculo recusa grupos menores com erro explícito |

## Limitações técnicas conhecidas

- Os testes exigem PostgreSQL (não há fallback SQLite): Docker para
  Testcontainers ou `Q360_TEST_POSTGRES=true` com uma instância local.
- `apps/business_config/interfaces/views.py` usa `import *`, o que impede a
  análise estática de nomes indefinidos nesse ficheiro.
- Imports não usados reportados pelo `pyflakes` (sem impacto funcional).
- `tools/recalc_calculador.py` precisa do `pycel` e de `openpyxl<3.1` num
  ambiente à parte (não são dependências do backend).

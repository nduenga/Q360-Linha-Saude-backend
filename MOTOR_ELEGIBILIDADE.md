# Motor de Elegibilidade Inteligente — Desenho (OD-ANGOLA-012)

**Estado:** desenho completo, entregue conforme pedido. Implementação
faseada — ver "Fases de implementação" no final. Este documento cobre
exactamente os 3 entregáveis pedidos: (1) árvore de decisão, (2)
mensagens amigáveis, (3) esquema JSON de configuração.

**Princípio herdado do motor já existente** (`apps/eligibility/domain/
evaluation.py`, construído no Sprint 3): a função `evaluate()` é pura,
determinística e nunca lê nenhum limite de negócio hardcoded — tudo vem
de `EligibilityRuleConfig`, lida de um `RuleVersion` publicado
(`rule_domain=ELIGIBILITY`). Este desenho **estende** essa mesma
arquitectura em vez de a substituir: já é exactamente a "tabela de regras
desacoplada da tabela de apólices" pedida, só que já implementada com
outros nomes:

| Pedido | Já existe como |
|---|---|
| Tabela "Apólices" | `Quote` + `Proposer` + `InsuredMember` (schema já existente) |
| Tabela "Regras_Elegibilidade" | `RuleVersion` (rule_domain=ELIGIBILITY), conteúdo em `artifact_ref` (JSON) |
| Interface de gestão para o gestor de produto alterar limites sem tocar código | `POST/PATCH/DELETE/retire` em `/api/v1/rule-versions` (já construído no Épico 6) |
| Excepções por empresa | Ver secção "Excepções corporativas" abaixo — extensão nova ao JSON |

---

## 1. Árvore de decisão

Pseudocódigo da extensão ao `evaluate()` já existente. As regras
ELIG-001 a ELIG-010 já implementadas mantêm-se exactamente como estão
(completude, produto/plano válidos, idade, relação permitida, referral,
warning — ver o ficheiro real para o código actual). As novas regras
entram como um **novo bloco**, executado depois de ELIG-005 (relação
permitida) e antes de ELIG-008/009 (referral/warning genéricos):

```
FUNCTION evaluate_angola_rules(member, proposer, plan, config, apolice_anterior):

    # --- MÓDULO DE COMPLIANCE (executa primeiro, é um hard-stop de sempre) ---

    SE proposer.tipo_documento NÃO EM ("BI", "CARTAO_RESIDENTE", "PASSAPORTE_VISTO_TRABALHO"):
        RETORNA HARD_STOP, mensagem="DOCUMENTO_INVALIDO"

    SE proposer.documento_identificacao É VAZIO:
        # Lei 11/24 — nunca aceitar proposta anónima
        RETORNA HARD_STOP, mensagem="PROPOSTA_ANONIMA"

    SE config.exige_nif_activo E proposer.nif_activo == FALSO:
        RETORNA HARD_STOP, mensagem="NIF_INATIVO"

    # --- MÓDULO DE REGRAS DINÂMICAS ---

    categoria = relationship_code.category   # TITULAR | SPOUSE | CHILD | ASCENDANT | OTHER
    regra = config.regra_para_categoria(categoria, empresa=proposer.empresa_id)
                                            # ↑ overrides corporativos entram aqui — ver secção 3

    SE categoria == CHILD:
        idade_limite = regra.idade_maxima_sem_prova            # ex.: 18
        idade_limite_com_prova = regra.idade_maxima_com_prova  # ex.: 25 (ou 27 se excepção corporativa)

        SE idade_do_membro <= idade_limite:
            CONTINUA (sem condição extra)
        SENÃO SE idade_do_membro <= idade_limite_com_prova:
            SE NÃO TEM certificado_matricula_valido:
                RETORNA PENDENTE_DOCUMENTO, mensagem="FALTA_CERTIFICADO_MATRICULA"
            SENÃO:
                CONTINUA
        SENÃO:
            RETORNA HARD_STOP, mensagem="IDADE_ACIMA_LIMITE_DEPENDENTE"

    SE categoria == SPOUSE:
        SE regra.exige_prova_uniao_facto E tipo_vinculo == "UNIAO_DE_FACTO":
            SE NÃO TEM documento_homologacao:
                RETORNA PENDENTE_DOCUMENTO, mensagem="FALTA_HOMOLOGACAO_UNIAO_FACTO"

    SE categoria == ASCENDANT:
        SE regra.exige_coabitacao_ou_dependencia:
            SE NÃO TEM (prova_coabitacao OU prova_dependencia_financeira):
                RETORNA PENDENTE_DOCUMENTO, mensagem="FALTA_PROVA_DEPENDENCIA_ASCENDENTE"

    SE apolice.tipo == "GRUPO" (B2B):
        SE trabalhador.estado_folha_pessoal != "ATIVO":
            RETORNA HARD_STOP, mensagem="VINCULO_LABORAL_INATIVO"

    # --- CARÊNCIA / PORTABILIDADE ---

    SE apolice_anterior.numero_apolice É FORNECIDO:
        SE validar_continuidade_sem_interrupcao(apolice_anterior):
            aplica_isencao_carencia = VERDADEIRO
        SENÃO:
            aplica_isencao_carencia = FALSO
    SENÃO:
        aplica_isencao_carencia = FALSO

    SE NÃO aplica_isencao_carencia:
        dias_carencia = regra.dias_carencia_padrao   # ex.: 300 para partos
    SENÃO:
        dias_carencia = 0

    # --- PREEXISTÊNCIAS (NUNCA hard-stop definitivo) ---

    SE membro.tem_doenca_preexistente_declarada:
        SE regra.modo_preexistencia == "AGRAVAMENTO":
            RETORNA ELIGIVEL_COM_AGRAVAMENTO, percentual=regra.percentual_agravamento
        SENÃO SE regra.modo_preexistencia == "JUNTA_MEDICA":
            RETORNA PENDENTE_JUNTA_MEDICA
        # nunca existe um terceiro ramo que rejeite definitivamente aqui

    RETORNA ELIGIVEL (segue para ELIG-008/009 já existentes: referral/warning genéricos)
```

**Decisões finais possíveis** (estende o `EligibilityDecision` já
existente — `ELIGIBLE/WARNING/REFERRAL/HARD_STOP/CONFIG_ERROR` — com 3
novos valores que o frontend mapeia para o mesmo "Não Elegível (ainda)"
visual, nunca para "Rejeitado" definitivo):

| Decisão | Visual no frontend |
|---|---|
| `ELIGIBLE` | Verde — "Elegível" |
| `ELIGIBLE_COM_AGRAVAMENTO` | Verde, com nota do agravamento — nunca vermelho |
| `PENDENTE_DOCUMENTO` | Amarelo — "Falta um documento" (nunca vermelho) |
| `PENDENTE_JUNTA_MEDICA` | Amarelo — "Em análise" |
| `HARD_STOP` | Vermelho — "Não Elegível", com o motivo exacto |
| `CONFIG_ERROR` | Nunca mostrado ao cliente final — erro interno, fail-closed |

---

## 2. Mensagens amigáveis (exemplos por motivo)

| Código interno | Nunca mostrar isto | Mostrar isto |
|---|---|---|
| `IDADE_ACIMA_LIMITE_DEPENDENTE` | "Erro: violação do Art. 130º do Código Civil" | "O seu seguro está quase pronto! O seu dependente já celebrou {idade} anos, que é o limite para esta cobertura." |
| `FALTA_CERTIFICADO_MATRICULA` | "Erro: documento MESCTI em falta" | "Só falta mais uma coisa: envie uma foto do certificado de matrícula do seu filho(a), porque ele(a) já celebrou 18 anos." |
| `FALTA_HOMOLOGACAO_UNIAO_FACTO` | "Erro: união de facto não homologada" | "Para incluir o seu cônjuge/parceiro(a), precisamos de um documento que comprove a vossa união — pode ser da conservatória ou do tribunal." |
| `FALTA_PROVA_DEPENDENCIA_ASCENDENTE` | "Erro: dependência económica não comprovada" | "Para incluir os seus pais/avós, envie um documento que mostre que vivem consigo ou que dependem de si financeiramente." |
| `VINCULO_LABORAL_INATIVO` | "Erro: trabalhador inactivo na folha de pessoal" | "Não conseguimos confirmar o seu vínculo actual com a empresa. Fale com o departamento de Recursos Humanos para actualizar o seu registo." |
| `DOCUMENTO_INVALIDO` | "Erro: documento de identificação não reconhecido" | "Precisamos de um Bilhete de Identidade válido (ou Cartão de Residente/Passaporte com Visto de Trabalho, se for estrangeiro)." |
| `PROPOSTA_ANONIMA` | "Erro: violação da Lei 11/24" | "Por razões de segurança, todas as propostas de seguro precisam de identificação completa." |
| `NIF_INATIVO` | "Erro: NIF inactivo no sistema tributário" | "O seu NIF parece estar inactivo. Contacte a Administração Geral Tributária para regularizar antes de continuar." |
| `ELIGIBLE_COM_AGRAVAMENTO` | "Erro: doença preexistente detectada" | "Está tudo pronto! Devido a uma condição de saúde já existente, o prémio tem um pequeno acréscimo de {percentual}%." |
| `PENDENTE_JUNTA_MEDICA` | "Rejeitado: preexistência não avaliável" | "Precisamos de uma avaliação médica adicional antes de confirmar a sua cobertura completa — a nossa equipa entra em contacto em breve." |
| `IDADE_ACIMA_LIMITE_DEPENDENTE` (sem hipótese de prova) | — | "Infelizmente, {nome} já não se enquadra na idade máxima permitida para esta cobertura (25 anos)." |

**Regra de tom, aplicada a todas:** nunca citar artigos de lei, nunca
usar a palavra "rejeitado" quando existe hipótese de correcção (usar
"falta", "ainda não", "precisamos de"), sempre dizer exactamente qual é o
próximo passo.

---

## 3. Esquema JSON (payload que a API lê da interface de gestão)

Isto é o conteúdo de `RuleVersion.artifact_ref` quando
`rule_domain=ELIGIBILITY`, `artifact_type=JSON` — criado/editado via os
endpoints já existentes (`POST /api/v1/rule-versions`,
`PATCH /api/v1/rule-versions/{id}`, Épico 6), sem precisar de nenhum
endpoint novo. Estende o `EligibilityRuleConfig` actual
(`apps/eligibility/domain/evaluation.py`) sem quebrar os campos que já
existem (`minEntryAge`, `maxEntryAge`, `allowedRelationshipCodes`,
`referralCriteria`, `warningCriteria` continuam a funcionar tal como
estão).

```jsonc
{
  // Campos já existentes (Sprint 3), inalterados:
  "minEntryAge": null,
  "maxEntryAge": null,
  "allowedRelationshipCodes": null,
  "referralCriteria": [],
  "warningCriteria": [],

  // NOVO — regras por categoria de relação (RelationshipCode.category,
  // OD-ANGOLA-010). A chave é a categoria, não o código individual, para
  // não repetir a regra por cada relationshipCode.
  "categoryRules": {
    "CHILD": {
      "maxAgeWithoutProof": 18,
      "maxAgeWithProof": 25,
      "proofDocumentType": "CERTIFICADO_MATRICULA",
      "proofIssuerAuthority": "MESCTI"
    },
    "SPOUSE": {
      "requiresUnionProofFor": ["UNIAO_DE_FACTO"],
      "proofDocumentType": "HOMOLOGACAO_UNIAO_FACTO"
    },
    "ASCENDANT": {
      "requiresCohabitationOrFinancialDependency": true,
      "proofDocumentType": "PROVA_COABITACAO_OU_DEPENDENCIA"
    }
  },

  // NOVO — excepções por empresa (Tratamento de Exceções Corporativas).
  // A chave é o identificador da empresa (Proposer.id quando
  // proposerType=ORGANISATION); qualquer campo aqui presente SOBREPÕE
  // o valor geral de "categoryRules" só para essa empresa.
  "corporateOverrides": {
    "<proposerId-da-empresa-X>": {
      "categoryRules": {
        "CHILD": { "maxAgeWithProof": 27 }
      }
    }
  },

  // NOVO — vínculo laboral (apólices de Grupo / B2B).
  "groupPolicyRules": {
    "requiresActivePayrollStatus": true
  },

  // NOVO — carência e portabilidade.
  "waitingPeriod": {
    "defaultDays": 300,
    "defaultDaysByBenefitCategory": { "MATERNITY": 300 },
    "waivedOnVerifiedPortability": true
  },

  // NOVO — preexistências: nunca um terceiro modo que rejeite definitivamente.
  "preExistingConditionPolicy": {
    "mode": "LOADING",              // "LOADING" | "PENDING_MEDICAL_BOARD"
    "loadingPercentage": "15.00"    // só usado quando mode = "LOADING"
  },

  // NOVO — compliance (documento/NIF/AML), aplicado antes de tudo o resto.
  "compliance": {
    "acceptedDocumentTypes": ["BI", "CARTAO_RESIDENTE", "PASSAPORTE_VISTO_TRABALHO"],
    "requireActiveNif": true,
    "rejectAnonymousProposals": true
  }
}
```

**Porque não uma tabela SQL separada por regra:** o padrão já
estabelecido neste projecto (`RuleVersion` genérico + JSON) já dá
exactamente o que foi pedido — "um gestor de produto altera os valores
sem precisar de alterar código" — através dos endpoints do Épico 6,
sem precisar de uma tabela nova por tipo de regra. Uma tabela SQL rígida
exigiria uma migration cada vez que uma seguradora quisesse um campo
novo; o JSON não.

---

## Fases de implementação

Dado o tamanho, a implementação real fica dividida (nenhuma parte
depende de inventar uma integração externa que não existe):

- **Fase A (segura para construir já):** extensão do parser
  `EligibilityRuleConfig`/`Criterion` para ler `categoryRules`,
  `corporateOverrides`, `preExistingConditionPolicy`, `waitingPeriod` —
  tudo dados fornecidos pela própria configuração, sem chamar nenhum
  serviço externo. Mensagens amigáveis (secção 2) devolvidas em vez das
  actuais genéricas.
- **Fase B (precisa de decisão de produto, não técnica):** onde ficam
  guardados os documentos comprovativos (certificado de matrícula,
  homologação, etc.) — hoje não existe nenhum campo de upload de
  documento em `InsuredMember`/`Proposer`. Precisa de uma decisão sobre
  armazenamento (mesma pergunta já registada em
  OPEN_DECISIONS.md#S03-IMPORT-001 para outro contexto).
- **Fase C (precisa de integração externa real, fora de âmbito até
  existir):** validação do NIF junto da Administração Geral Tributária e
  validação de vínculo laboral — nenhuma API pública angolana para isto
  está disponível/aprovada; construir uma "simulação" seria inventar uma
  integração que o projecto proíbe explicitamente (DOC-000 regra de
  ouro). Fica registado como dependência externa, não como trabalho em
  falta deste roadmap.

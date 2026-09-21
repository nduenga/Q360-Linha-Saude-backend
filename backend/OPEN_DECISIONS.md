# Decisões em aberto (explicado de forma simples)

Esta é a lista de tudo o que a documentação oficial do projecto (os
"artefactos" ART-XXX/DOC-XXX que a equipa técnica segue) **não diz com
clareza**. Sempre que o código precisava de fazer alguma coisa e a regra
de negócio real não estava definida em lado nenhum, a regra desta equipa é
simples: **nunca inventar um valor de negócio real** (uma tarifa, uma
moeda oficial, um catálogo regulatório) — em vez disso, ou se bloqueia e
regista-se aqui a pergunta exacta que falta responder, ou usa-se um valor
de teste claramente identificado como tal, nunca disfarçado de definitivo.

**Como ler este documento:** cada item tem um **Estado**, uma explicação
em português simples do que está por decidir, e — quando aplicável — o
que foi feito só para não bloquear os testes enquanto a decisão real não
chega. O ficheiro `DECISIONS_TAKEN.md` tem o detalhe técnico de cada
decisão de teste, para quem precisar dele.

**Os três estados possíveis:**
- **Resolvido** — já há uma resposta definitiva, não precisa de mais nada.
- **Decisão de teste (não é valor de negócio real)** — para não bloquear o
  trabalho, usámos um valor combinado só para testar/demonstrar. Continua
  a precisar de uma decisão real tua (ou do actuário/regulador) antes de
  ir para clientes reais.
- **Em aberto** — ainda não há nem sequer um valor de teste; falta uma
  resposta tua para o código avançar nessa parte.

---

## S01-PERSISTENCE-001 — Base de dados

**Estado:** Resolvido.

Usamos sempre PostgreSQL a sério, nunca uma base de dados "leve" de
mentira só para testes rápidos. Isto porque o desenho oficial dos dados
(schemas, regras de validação) só existe e só funciona em PostgreSQL —
usar outra coisa daria uma falsa sensação de que tudo está correcto
quando podia não estar.

---

## S01-AUTH-001 — Quem confirma a identidade de quem usa o sistema (login)

**Estado:** Decisão de teste (não é valor de negócio real).

Nenhum documento diz ainda **qual** vai ser o sistema real de login da
empresa (ex.: um serviço como o Keycloak, o Auth0, ou o login da Microsoft/
Azure). O código já está pronto para ligar a qualquer um destes — só falta
escolher qual.

**O que fizemos para testar sem esperar:** um mecanismo interno de "login
de desenvolvimento" (o que já usaste para entrar na plataforma). Só
funciona em ambiente de teste — o sistema **recusa-se a arrancar** em
produção se este atalho estiver ligado, por segurança.

**O que falta:** escolher o fornecedor real de login antes de ir para
clientes reais a sério.

---

## S02-CONTRACT-001 — Coberturas de um plano ("Benefit") sem endpoint próprio

**Estado:** Resolvido (superado pelo trabalho de customização Angola).

Este item já não se aplica: as coberturas de saúde (Internamento,
Ambulatório, etc.) já têm agora o seu próprio catálogo real, endpoints
próprios e ligação aos planos — ver `ROADMAP_ANGOLA_CUSTOMIZATION.md`,
Épico 1. Fica registado aqui só por historial.

---

## S02-PRODUCT-VERSION-OVERLAP — Quando é que duas versões de um produto "colidem"

**Estado:** Decisão de teste, aceite como definitiva por agora.

Um produto pode ter várias versões ao longo do tempo (cada uma com o seu
período de validade). A documentação não diz claramente em que momento
exacto o sistema deve verificar se duas versões se sobrepõem no tempo.
Decidimos verificar **assim que uma nova versão é criada**, comparando com
todas as versões existentes desse produto que ainda não foram retiradas.

**Nota:** desde a customização para Angola (Épico 2/3), um produto nunca
mais tem data de fim — este ponto perdeu grande parte da relevância
prática, mas fica registado pelo histórico da decisão.

---

## S03-RELATIONSHIP-001 — Que "relações familiares" existem (titular, cônjuge, filho...)

**Estado:** Decisão de teste (não é o catálogo oficial).

Não existe ainda um catálogo oficial e aprovado dos tipos de relação
familiar aceites numa apólice (ex.: quem conta como "titular", "cônjuge",
"filho").

**O que fizemos para testar sem esperar:** um catálogo simples de
demonstração (Titular / Cônjuge / Filho(a) / Outro), disponível como lista
de escolha no ecrã de adicionar membros — nunca texto livre.

**O que falta:** o catálogo oficial (angolano/regulatório) deve vir de ti
ou do actuário antes de produção — sem ele, o sistema não consegue impor
sozinho a regra "um dependente tem sempre de ter um titular associado".

---

## S03-IMPORT-001 — Como funciona a importação de membros em massa (ficheiro CSV)

**Estado:** Resolvido (decisões técnicas aceites como definitivas).

Três detalhes técnicos sem resposta oficial foram decididos e já
funcionam: onde o ficheiro fica guardado, que colunas o CSV deve ter, e a
obrigatoriedade de indicar o proponente antes de confirmar a importação.
Nada disto tem impacto de negócio — são só decisões de engenharia.

---

## S03-ELIGIBILITY-001 — Critérios médicos de elegibilidade

**Estado:** Decisão de teste (nenhum critério médico real existe ainda).

A avaliação de elegibilidade (se uma pessoa pode ou não ser aceite/tem
avisos/precisa de análise extra) já funciona de ponta a ponta, mas os
**critérios médicos concretos** (idades limite, condições que geram aviso
ou análise extra) não estão definidos em nenhum documento oficial — e a
própria documentação diz explicitamente que nenhum critério médico deve
ser inventado nesta fase.

**O que fizemos para testar sem esperar:** o sistema lê os critérios de
uma configuração publicável (nunca hardcoded); enquanto não houver
nenhuma configurada, simplesmente não bloqueia nem avisa ninguém por esse
critério (nunca assume o pior nem o melhor sozinho).

**O que falta:** os critérios médicos/etários reais devem vir do actuário
antes de estes resultados serem usados a sério com clientes.

---

## S04-ROUNDING-001 — Moeda e arredondamento de valores monetários

**Estado:** Decisão de teste (não é a política oficial).

Não há uma política aprovada de que moeda usar oficialmente nem como
arredondar valores (ex.: para cima, para baixo, a que casa decimal).

**O que fizemos para testar sem esperar:** arredondamento simples (2 casas
decimais, sempre para cima a partir do 5) aplicado de forma consistente
em todo o cálculo, e Kwanza (AOA) como moeda de demonstração.

**O que falta:** a política oficial de arredondamento e moeda deve ser
aprovada pelo actuário/Product Owner antes de qualquer valor calculado
ser usado a sério.

---

## S04-PRICING-CONTEXT-001 — Como o sistema escolhe que tabela de preços usar

**Estado:** Resolvido (decisão técnica aceite como definitiva).

Quando se calcula o preço de uma cotação, o sistema precisa de saber que
tabela de tarifas e que conjunto de parâmetros usar. Como nenhum
documento define isso, o sistema resolve isto automaticamente
(seleccionando a única configuração publicada e válida na data), sem
nunca pedir ao utilizador para escrever códigos técnicos à mão.

---

## S04-CROSS-MODULE-001 — Organização interna do código (só relevante para a equipa técnica)

**Estado:** Resolvido (decisão de arquitectura, sem impacto de negócio).

Detalhe puramente técnico de como os módulos internos do sistema
partilham dados entre si. Não tem qualquer impacto visível para quem usa
a plataforma.

---

## S04-LISTING-GAPS-001 — Falta de ecrãs para listar configurações já criadas

**Estado:** Resolvido.

No início, depois de criar uma tabela de preços ou um conjunto de
parâmetros, não havia forma de voltar a vê-los mais tarde (só apareciam
uma vez, no momento da criação). Foram acrescentados os ecrãs/listas em
falta — hoje já é possível consultar tudo o que já foi criado a qualquer
momento.

---

## S05-PRICING-RULES-001 — Forma das "regras" de ajuste de preço

**Estado:** Decisão de teste (não são regras de negócio reais), aceite
como definitiva para esta fase.

Ajustes de preço automáticos (ex.: um desconto ou agravamento por
determinada condição) seguem hoje um formato simples e genérico
(condição → valor a somar/subtrair). Nenhuma regra real de precificação
angolana foi ainda configurada — é só a mecânica que já está pronta a
recebê-las.

---

## S05-RULE-FOUR-EYES-001 — Dupla aprovação ao publicar uma regra de configuração

**Estado:** Em aberto — decisão consciente de simplificar por agora.

O ideal seria que, ao publicar uma nova regra de pricing/elegibilidade,
fosse sempre uma pessoa diferente a aprovar em relação a quem a criou (o
mesmo princípio de "quatro olhos" que já existe, por exemplo, na
aprovação de cotações). Isto ainda não está implementado para regras de
configuração — qualquer administrador pode publicar sozinho.

**O que falta:** decisão de negócio sobre se isto é mesmo necessário para
regras de configuração (é diferente de aprovar uma cotação de cliente) e,
se sim, priorizar a construção.

---

## Perguntas concretas que precisam de resposta tua (resumo rápido)

1. **Login real** — qual vai ser o fornecedor de autenticação da empresa?
2. **Catálogo oficial de relações familiares** — quais os códigos e regras
   exactas (ex.: quem conta como titular)?
3. **Critérios médicos de elegibilidade** — idades/condições reais de
   aceitação, aviso e análise extra.
4. **Moeda e arredondamento oficiais** — confirmar Kwanza + a regra exacta
   de arredondamento a aplicar em produção.
5. **Regras reais de ajuste de preço** — quais existem, quando se aplicam,
   e quanto valem.
6. **Dupla aprovação em regras de configuração** — é necessária ou não?

Nenhuma destas seis perguntas bloqueia continuar a construir ou a testar
a plataforma — todas têm hoje um valor de teste claramente marcado como
tal, exactamente para isso.

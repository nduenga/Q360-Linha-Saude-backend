# Instalação, migração, execução e testes

Complementa `backend/DEV_SETUP.md` (modos dev/produção) e `GUIA_TESTES.md`
(testes manuais com dados de demonstração). Comandos a partir de `backend/`.

## 1. Requisitos

- Python 3.12+ (testado com 3.13).
- PostgreSQL 16+ (obrigatório também nos testes — não há SQLite).
  - macOS: Postgres.app; Windows: instalador nativo; ou Docker
    (`docker compose up db`).

## 2. Dependências

```bash
python -m venv ../.venv          # a partir de backend/: o venv fica na raiz do repositório
../.venv/bin/python -m pip install -r requirements.txt          # dev + testes (versões fixas)
# produção (Render / Dockerfile.prod): requirements.render.txt
```

`requirements.txt` foi convertido de UTF-16 para UTF-8 (era gerado pelo
PowerShell); o conteúdo não mudou.

**Se o projeto mudar de pasta, recrie o venv.** O `activate` e os scripts do
venv guardam o caminho absoluto de quando foi criado; noutra pasta o
`python3` passa a ser o do sistema e surge `ModuleNotFoundError: No module
named 'django'` (foi a causa do erro no `migrate` de 2026-10-14):

```bash
rm -rf ../.venv && python3 -m venv ../.venv && ../.venv/bin/python -m pip install -r requirements.txt
```

## 3. Variáveis de ambiente

Copiar `backend/.env.example` para `backend/.env` e preencher. Sem segredos
reais no repositório (o `.env` está no `.gitignore` e nunca foi commitado).
Essenciais:

| Variável | Uso |
|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.development` / `production` |
| `DJANGO_SECRET_KEY` | segredo do Django (obrigatório em produção) |
| `POSTGRES_DB/USER/PASSWORD/HOST/PORT` | ligação à BD |
| `Q360_JWT_SIGNING_KEY` | assinatura dos tokens dos colaboradores (≥32 caracteres) |
| `PLATFORM_ADMIN_JWT_SIGNING_KEY` | tokens dos super-admins |
| `OIDC_STATIC_VERIFICATION_KEY` | **só dev**; a produção recusa arrancar com ela definida |
| `EMAIL_*`, `DEFAULT_FROM_EMAIL` | envio de OTP do portal |

## 4. Base de dados

```bash
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py migrate --check          # confirma que não há migrações por aplicar
../.venv/bin/python manage.py makemigrations --check --dry-run   # modelos = migrações
```

Migrações novas neste trabalho:

| Migração | O quê |
|---|---|
| `client/0009_member_nif` | Coluna opcional `insured_member.nif` |
| `client/0010_nif_unique_required` | NIF do proponente obrigatório no formato do tipo (CHECK `NOT VALID`) e único por tenant; NIF da pessoa segura único por tenant. Pára, sem alterar dados, se já houver NIF repetidos |
| `client/0011_member_nif_unique_per_proposer` | NIF da pessoa segura passa a ser único por tomador (a mesma pessoa pode ter o NIF em fichas de tomadores diferentes) |
| `quote/0013_drop_quote_effective_date` | Remove a data de efeito da cotação (e a CHECK `ck_quote_dates`). O reverso recria-a com o dia de criação de cada cotação |
| `business_config/0003_rejected_status` | Estado `REJECTED` na CHECK `ck_business_configuration_status` |

Dados:

```bash
../.venv/bin/python manage.py seed_full_database --profile reference --admin-email admin@exemplo.ao
../.venv/bin/python manage.py publish_actuarial_model --tenant-code q360-saude --validate-only   # valida as 94 células
../.venv/bin/python manage.py publish_actuarial_model --tenant-code q360-saude                  # publica (rever aviso A1)
```

O modelo actuarial também pode ser publicado pela API com o ciclo normal de
aprovação (`POST /api/v1/business-config/configurations`, `configKey =
pricing.actuarial_model`) ou importado de um Excel
(`POST /api/v1/business-config/actuarial-model/import`, ver
`MOTOR_CONFIGURAVEL.md` §7). Uma versão publicada antes deste trabalho não tem
as tabelas de participação nos custos: para usar `actuarialProfile.costSharing`
publique uma versão nova gerada pelo seed actual.

## 5. Executar

```bash
../.venv/bin/python manage.py runserver 8000
../.venv/bin/python manage.py build_openapi    # regenera schema.yml e o contrato ART-006
```

## 6. Testes

```bash
# com uma instância local (variáveis POSTGRES_* do .env):
Q360_TEST_POSTGRES=true ../.venv/bin/python -m pytest tests -q
# ou, com Docker a correr, sem variáveis: o conftest arranca um PostgreSQL com Testcontainers
../.venv/bin/python -m pytest tests -q
```

Conjuntos úteis:

| Comando | O quê |
|---|---|
| `pytest tests/test_formula_engine.py` | avaliador e conjunto de fórmulas (sem BD) |
| `pytest tests/quote/test_formula_config_e2e.py` | fórmulas: criar → rejeitar → aprovar → cálculo real → trace → histórico → comparação |
| `pytest tests/quote/test_actuarial_excel_reference.py` | backend vs `Calculador` do Excel (SAU) |
| `pytest tests/quote/test_actuarial_excel_reference_sag.py` | backend vs `Calculador` recalculado com `C5 = SAG` |
| `pytest tests/quote/test_actuarial_model_config.py` | importação de Excel, validação, valores por omissão, renovações, fracionamento, fórmulas por pessoa |
| `pytest tests/integration/test_openapi_contract.py` | contrato OpenAPI = API |
| `pytest tests/integration/test_tenant_isolation.py` | isolamento por tenant |

Nos testes usa-se um *hasher* de palavras-passe rápido
(`config/settings/testing.py`); a suite completa passou de >25 min para
~5 min. A produção mantém o PBKDF2 do Django.

Para correr dois conjuntos ao mesmo tempo sem colidir na BD de teste, use
outro nome: `POSTGRES_DB=q360_alt pytest …` (cria `test_q360_alt`).

## 7. Regenerar os valores esperados do teste SAG

Só é preciso se o Excel do modelo mudar. Num ambiente à parte (o `pycel` não
é dependência do backend):

```bash
python3 -m venv /tmp/xl && /tmp/xl/bin/pip install pycel "openpyxl<3.1"
/tmp/xl/bin/python tools/recalc_calculador.py SAG > tests/quote/fixtures/calculador_sag_expected.json
```

O script recusa-se a gerar valores se o mesmo recálculo com `SAU` não
coincidir com os valores guardados pelo Excel.

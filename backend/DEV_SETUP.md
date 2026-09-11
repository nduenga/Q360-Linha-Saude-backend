# Correr o backend — dev (rápido, sem Docker) vs produção (Docker)

O schema é sempre PostgreSQL real (S01-PERSISTENCE-001, ver
`OPEN_DECISIONS.md`) — a única coisa que muda entre os dois modos é onde
o Postgres está a correr. O código Django é idêntico nos dois casos.

## Modo dev (recomendado no dia a dia — sem Docker)

Pré-requisito único: um PostgreSQL 16+ nativo instalado no Windows, a
correr em `localhost:5432` (não precisa de Docker Desktop nem WSL2).

1. `backend/.env` já vem configurado para este modo (`POSTGRES_HOST=localhost`,
   `POSTGRES_PORT=5432`). É carregado automaticamente por
   `config/settings/base.py` (via `python-dotenv`) — não é preciso `export`
   manual de variáveis.
2. `./.venv/Scripts/python.exe manage.py migrate` (só da primeira vez / após
   nova migração).
3. `./.venv/Scripts/python.exe manage.py seed_dev_tenant` (só da primeira
   vez) — cria um tenant local para testar contra.
4. `./.venv/Scripts/python.exe manage.py runserver 8000`

Sem um Identity Provider OIDC real (OD-009 ainda em aberto), usa o token
estático de desenvolvimento para chamar endpoints protegidos:

```
./.venv/Scripts/python.exe manage.py issue_dev_token
```

Isto só funciona porque `.env` define `OIDC_STATIC_VERIFICATION_KEY`
(dev-only — `config/settings/production.py` recusa arrancar se isto
estiver definido em produção).

## Modo produção (Docker — configuração já existente, inalterada)

```
docker compose up --build
```

Continua a subir `db` (Postgres em container) + `web` (Django), com
`DJANGO_SETTINGS_MODULE=config.settings.production`. Nada neste modo foi
alterado — `docker-compose.yml` continua a ser a topologia de referência
para produção/CI. Também pode ser usado em dev se preferires um Postgres
descartável em vez de uma instalação nativa: `docker compose up db` sobe
só a base de dados, mapeada em `localhost:5433` (ver comentários no
`docker-compose.yml`), e corres `manage.py` normalmente no host apontando
`POSTGRES_PORT=5433`.

## Ligar o frontend (React/Vite, repo separado)

O frontend já tem CORS liberado por omissão em dev para
`http://localhost:5173` (`config/settings/development.py`). Do lado do
frontend, cria um `.env.local` com:

```
VITE_API_BASE_URL=http://localhost:8000
VITE_DEV_BEARER_TOKEN=<output de manage.py issue_dev_token>
```

`src/dev/devAuth.ts` (frontend) injeta esse token em todos os pedidos do
`httpClient` só em modo dev — ver comentário nesse ficheiro. Isto é só uma
ponte de teste manual, não substitui OD-009 (IdP real) nem o fluxo de
login mock existente.

**Importante:** a maioria das páginas do frontend ainda lê de `Mockdata.ts`
por domínio (é o padrão documentado pelo próprio frontend — trocar para o
endpoint real é uma troca isolada por domínio, quando o respectivo sprint
desbloqueia). Ligar o backend não troca isso automaticamente em nenhuma
página; testa os endpoints já implementados directamente (curl/Postman, ou
a consola do browser com `fetch`) até que cada domínio seja religado do
lado do frontend.

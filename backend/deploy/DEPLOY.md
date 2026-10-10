# Guia de Deploy — Q360 Saúde (Backend)

Guia para hospedar a API Django num servidor Linux (Ubuntu) com PostgreSQL, gunicorn e Nginx.

## Resumo

- **Não existe nenhum ficheiro de base de dados nem backup para restaurar.** A base de dados de produção começa **vazia**.
- As tabelas são criadas pelo Django (`manage.py migrate`) e os dados iniciais pelos comandos `seed_*` (passos 6 e 7).
- Os ficheiros `.sql` em `docs/artifacts/` são só documentação do desenho original. **Não os execute em produção.**
- Todos os comandos `python manage.py ...` são executados **no servidor**, ligados à base de produção.

## Ficheiros desta pasta (`backend/deploy/`)

| Ficheiro | Para quê |
|---|---|
| `q360.env.example` | Modelo das variáveis de ambiente. Copiar para `/etc/q360.env` e preencher. |
| `q360.service` | Serviço systemd que mantém o gunicorn sempre ligado. |
| `nginx-q360.conf` | Configuração do Nginx (proxy + cabeçalho HTTPS). |
| `bootstrap.sh` | Executa os passos 6 e 7 de uma vez (migrate + dados iniciais). |
| `../Dockerfile.prod` | Alternativa com Docker (gunicorn). O `Dockerfile` original usa `runserver` e é só para desenvolvimento. |

Os caminhos `/opt/q360/backend` e o domínio `api.seudominio.com` são exemplos. Ajuste-os ao seu servidor.

---

## 1. Preparar o servidor (Ubuntu)

```bash
sudo apt update && sudo apt install -y python3.12 python3.12-venv postgresql nginx git
```

## 2. Criar a base de dados vazia

```bash
sudo -u postgres psql -c "CREATE USER q360 WITH PASSWORD 'SENHA_FORTE';"
sudo -u postgres psql -c "CREATE DATABASE q360 OWNER q360;"
```

Isto cria só uma base vazia. Não restaura nenhum ficheiro, e não existe nenhum para restaurar.

## 3. Obter o código e instalar

```bash
git clone <url-do-repo> /opt/q360
cd /opt/q360/backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.render.txt
```

O `requirements.render.txt` é a lista de dependências de produção, apesar do nome.

## 4. Definir as variáveis de ambiente

Crie `/etc/q360.env` a partir de `deploy/q360.env.example`:

```bash
sudo cp deploy/q360.env.example /etc/q360.env
sudo chmod 600 /etc/q360.env
sudo nano /etc/q360.env
```

Gere cada chave secreta com:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Conteúdo:

```
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=<chave gerada>
Q360_JWT_SIGNING_KEY=<outra chave, mínimo 32 caracteres>
CUSTOMER_PORTAL_JWT_SECRET=<outra chave>
DJANGO_ALLOWED_HOSTS=api.seudominio.com
CORS_ALLOWED_ORIGINS=https://app.seudominio.com
DATABASE_URL=postgres://q360:SENHA_FORTE@localhost:5432/q360
EMAIL_HOST_USER=<email>
EMAIL_HOST_PASSWORD=<senha de app>
DEFAULT_FROM_EMAIL=<email>
CUSTOMER_PORTAL_EMAIL_FROM=<email>
```

| Variável | Notas |
|---|---|
| `DJANGO_SECRET_KEY`, `Q360_JWT_SIGNING_KEY`, `CUSTOMER_PORTAL_JWT_SECRET` | **Obrigatórias.** O servidor não arranca sem elas (o `production.py` aborta de propósito). Use três chaves diferentes. |
| `DJANGO_ALLOWED_HOSTS` | Domínio da API. |
| `CORS_ALLOWED_ORIGINS` | Origem(ns) do frontend, separadas por vírgula. Vazio = nenhum frontend consegue chamar a API. |
| `DATABASE_URL` | Ligação ao PostgreSQL do passo 2. |
| `EMAIL_*`, `DEFAULT_FROM_EMAIL`, `CUSTOMER_PORTAL_EMAIL_FROM` | Usadas para enviar o código OTP do portal do cliente. |

## 5. Criar as tabelas

```bash
set -a; source /etc/q360.env; set +a
python manage.py migrate --noinput
```

Este é o passo que cria **todas** as tabelas, incluindo as da configuração de fórmulas e tarifas (`business_config`).

## 6. Criar os dados iniciais

```bash
python manage.py seed_dev_tenant --code q360 --name "Q360 Saúde"
python manage.py create_staff_account --email admin@seudominio.com --name "Admin" --tenant-code q360 --password 'SENHA_ADMIN'
python manage.py seed_default_pricing_config --tenant-code q360
python manage.py seed_health_market_templates --tenant-code q360
```

| Comando | O que faz |
|---|---|
| `seed_dev_tenant` | Cria o tenant (a empresa). Tudo o resto depende dele. |
| `create_staff_account` | Cria o primeiro utilizador ADMIN. Sem ele não é possível entrar. |
| `seed_default_pricing_config` | Cria e publica tabela de preços, parâmetros, regra de elegibilidade, modelo de documento e o modelo atuarial. |
| `seed_health_market_templates` | Cria os produtos e planos Individual/Familiar e Grupo (valores indicativos). |

Todos são repetíveis (idempotentes). Só o `create_staff_account` falha se o email já existir.
Use sempre o mesmo `--tenant-code` (aqui `q360`) em todos os comandos.

**Atalho:** o `bootstrap.sh` faz os passos 5 e 6 de uma vez:

```bash
cd /opt/q360/backend
TENANT=q360 ADMIN_EMAIL=admin@seudominio.com ADMIN_PASSWORD='SENHA_ADMIN' bash deploy/bootstrap.sh
```

## 7. Arrancar a API (gunicorn + systemd)

Teste manual:

```bash
gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 2
```

Para ficar sempre ligado, use o serviço systemd:

```bash
sudo cp deploy/q360.service /etc/systemd/system/q360.service
sudo systemctl daemon-reload
sudo systemctl enable --now q360
sudo systemctl status q360
```

O serviço usa `EnvironmentFile=/etc/q360.env` e `WorkingDirectory=/opt/q360/backend`. Ajuste `User` e os caminhos se necessário.

## 8. HTTPS com Nginx

```bash
sudo cp deploy/nginx-q360.conf /etc/nginx/sites-available/q360
sudo ln -s /etc/nginx/sites-available/q360 /etc/nginx/sites-enabled/q360
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d api.seudominio.com
```

O bloco do Nginx tem de incluir:

```
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header Host $host;
```

O `production.py` redireciona para HTTPS e confia nesse cabeçalho. **Sem ele a API entra num ciclo infinito de redirecionamentos.**

## 9. Verificar

Abra `https://api.seudominio.com/api/v1/health/ready`. Deve responder OK.

---

## Tarefas agendadas (cron)

A API não tem fila de tarefas: dois comandos têm de ser agendados no servidor. Ambos são repetíveis sem efeitos secundários.

| Comando | Para quê | Frequência |
|---|---|---|
| `python manage.py expire_quotes` | Marca como expiradas as cotações fora de validade. | 1 vez por dia |
| `python manage.py close_renewed_policies` | Passa a `RENEWED` a apólice antiga quando a renovação já está em vigor. | 1 vez por dia |

Exemplo (`sudo crontab -u www-data -e`; ajuste os caminhos):

```
15 2 * * * cd /opt/q360/backend && set -a && . /etc/q360.env && set +a && .venv/bin/python manage.py expire_quotes
30 2 * * * cd /opt/q360/backend && set -a && . /etc/q360.env && set +a && .venv/bin/python manage.py close_renewed_policies
```

O `dispatch_outbox` só é preciso se ligar um broker de mensagens real; por omissão não envia nada para fora.

## Ficheiros gerados e carregados (pasta `media/`)

A API guarda ficheiros em `backend/media/`. **Esta pasta tem de ser persistente e entrar no backup**, ao lado da base de dados:

| Subpasta | O que tem | Se se perder |
|---|---|---|
| `policies/` | PDF de cada apólice emitida | É gerado de novo a partir dos dados, mas deixa de ser o documento original da emissão. |
| `documents/` | Propostas geradas | Regeneram-se. |
| `document-templates/` | Papel timbrado (PDF) e modelos Word carregados pelo GTE | **Perdem-se**: o GTE tem de os carregar outra vez. |
| `member-documents/` | Documentos enviados pelos clientes (matrícula, prova de união…) | **Perdem-se** e não há como os regenerar. |

`member-documents/` guarda documentos pessoais (e possivelmente de saúde): restrinja o acesso à pasta (só o utilizador do serviço), inclua-a no backup cifrado e nunca a sirva diretamente pelo Nginx.

- Num servidor normal, basta não a apagar ao atualizar o código (o `git pull` não toca nela).
- Em Docker, monte um volume: `-v /var/lib/q360/media:/app/media`.

## Atualizar uma nova versão

```bash
cd /opt/q360 && git pull
cd backend && source .venv/bin/activate
pip install -r requirements.render.txt
set -a; source /etc/q360.env; set +a
python manage.py migrate --noinput
sudo systemctl restart q360
```

## Alternativa com Docker

```bash
cd backend
docker build -f Dockerfile.prod -t q360-api .
docker run --rm --env-file /etc/q360.env q360-api python manage.py migrate --noinput
docker run -d --restart always --env-file /etc/q360.env -p 127.0.0.1:8000:8000 q360-api
```

Os comandos `seed_*` do passo 6 também se executam com `docker run --rm --env-file /etc/q360.env q360-api python manage.py ...`.
Neste caso o `DATABASE_URL` não pode usar `localhost`, porque dentro do contentor isso não é o servidor. Use o IP ou o nome do host do PostgreSQL.

---

## O que NÃO fazer

- Não envie o `db.sqlite3` (é só a base local de desenvolvimento).
- Não execute os ficheiros `.sql` de `docs/artifacts/` em produção. As tabelas vêm das migrações do Django.
- Não use `seed_demo_data` em produção (cria dados de demonstração com palavra-passe fixa).
- Não use `seed_portal_demo` em produção (corre com `seed_demo_data` e cria clientes com palavra-passe fixa).
- Não mude `DJANGO_SETTINGS_MODULE` para `development`.
- Não faça commit do `/etc/q360.env` nem do `backend/.env`.

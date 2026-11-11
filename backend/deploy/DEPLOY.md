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
| `LIBREOFFICE_PDF.md` | Como instalar e verificar o LibreOffice e as fontes, para o PDF dos modelos Word sair igual ao Word. |

Os caminhos `/opt/q360/backend` e o domínio `api.seudominio.com` são exemplos. Ajuste-os ao seu servidor.

---

## 1. Preparar o servidor (Ubuntu)

```bash
sudo apt update && sudo apt install -y python3.12 python3.12-venv postgresql nginx git
```

### LibreOffice e fontes (PDF dos modelos Word)

Guia completo, incluindo Docker, Render, verificação e resolução de problemas: [`LIBREOFFICE_PDF.md`](LIBREOFFICE_PDF.md).

Para o PDF de uma proposta ou apólice com modelo Word sair igual ao Word (por exemplo o modelo Protteja), o servidor precisa do LibreOffice e das fontes usadas no modelo. Sem o LibreOffice, a plataforma continua a gerar o PDF, mas com o seu próprio layout, e regista um aviso no log.

```bash
# 1. LibreOffice só com o processador de texto e sem interface gráfica (~250 MB)
sudo apt install -y --no-install-recommends libreoffice-writer-nogui fonts-dejavu-core fontconfig unzip

# 2. Fontes Inter e Inter Display, versão oficial (o pacote fonts-inter não traz a Inter Display)
curl -fsSL -o /tmp/inter.zip https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip
sudo mkdir -p /usr/local/share/fonts/inter
sudo unzip -j -o /tmp/inter.zip 'extras/ttf/*.ttf' -d /usr/local/share/fonts/inter
sudo fc-cache -f && rm /tmp/inter.zip

# 3. Confirmar
soffice --version
fc-list | grep -c "Inter Display"     # deve ser maior que 0
```

Se o modelo de outra seguradora usar outras fontes, instale-as da mesma forma em `/usr/local/share/fonts` e corra `sudo fc-cache -f`. Se o executável não estiver no PATH, indique-o na variável `Q360_SOFFICE_PATH`. Depois de instalar, reinicie a API: `sudo systemctl restart q360`.

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

A API não tem fila de tarefas. O comando `python manage.py run_daily_jobs` corre uma vez por dia, às 02:45 de Luanda, estas tarefas por ordem:

| Tarefa | Para quê |
|---|---|
| `expire_quotes` | Marca como expiradas as cotações fora de validade. |
| `expire_endorsement_offers` | Expira as propostas de endosso fora do prazo de aceitação. |
| `premium_overdue_scan` | Marca prestações vencidas e resolve apólices elegíveis por falta de pagamento. |
| `close_renewed_policies` | Passa a `RENEWED` a apólice antiga quando a renovação já está em vigor. |
| `expire_policies` | Marca como `EXPIRED` as apólices cuja vigência terminou. |

São repetíveis sem efeitos secundários. Se uma falhar, as seguintes correm na mesma e o comando termina com erro.

**Atenção:** não ative antes da confirmação jurídica. A partir da primeira execução, uma apólice com prestação vencida é resolvida sem intervenção humana, sem tolerância e sem esperar pela carta registada do art. 18.º do Decreto n.º 2/02. Estes prazos não são configuráveis.

**No Render:** o `render.yaml` já declara o serviço `q360-daily-jobs`. Os serviços cron do Render não têm plano gratuito.

**Em servidor próprio (systemd):**

```bash
sudo cp deploy/q360-daily.service deploy/q360-daily.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now q360-daily.timer
systemctl list-timers q360-daily.timer       # próxima execução
sudo systemctl start q360-daily.service      # correr já, para testar
journalctl -u q360-daily.service -n 50       # resultado
```

Ajuste `User` e os caminhos nos dois ficheiros, como no `q360.service`.

O `dispatch_outbox` só é preciso se ligar um broker de mensagens real; por omissão não envia nada para fora.

## Email (convites e códigos do Portal do Cliente)

Preencha `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`, `CUSTOMER_PORTAL_EMAIL_FROM` e `CUSTOMER_PORTAL_URL`. Sem `CUSTOMER_PORTAL_URL`, o link do convite aponta para `localhost`. No Render, preencha estes valores no painel do serviço `q360-health-api`.

```bash
python manage.py check_email                         # valida a configuração e a autenticação, sem enviar
python manage.py check_email --to voce@seudominio.com # envia uma mensagem real
```

Só a chegada da mensagem à caixa de entrada comprova a entrega. O comando apenas confirma que o servidor de email a aceitou. Use um remetente de um domínio próprio com SPF e DKIM configurados; uma caixa pessoal de Gmail serve para testes, não para produção.

Na ficha do cliente, «Portal do Cliente» mostra se o último convite foi aceite ou falhou e permite reenviá-lo. As falhas ficam também na auditoria.

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

# LibreOffice no servidor: PDF igual ao modelo Word

Este guia explica como pôr o LibreOffice a funcionar no servidor da API Q360. Com ele, os PDFs das propostas e das apólices saem iguais ao modelo Word da seguradora, como o modelo Protteja.

## 1. O que faz e quando é preciso

Uma seguradora pode ter um modelo Word com marcas `{{variável}}`, por exemplo o modelo `PROTTEJA-PROPOSTA-SAUDE`. Quando alguém gera uma proposta ou uma apólice nesse modelo:

| Formato pedido | LibreOffice instalado | Resultado |
|---|---|---|
| DOCX | Não é preciso | O Word preenchido |
| PDF | Sim | O Word preenchido, convertido em PDF: **igual ao modelo** |
| PDF | Não | PDF com o layout da plataforma (genérico), e um aviso no log |

O código está em `apps/quote/application/docx_to_pdf.py`. É chamado pela proposta (`proposal_service._render`) e pela apólice (`policy_document`).

Em cada conversão, a plataforma:
1. procura o executável: primeiro a variável `Q360_SOFFICE_PATH`, depois `soffice` ou `libreoffice` no PATH;
2. corre `soffice --headless --convert-to pdf` numa pasta temporária, com um perfil próprio, para que duas conversões ao mesmo tempo não se atropelem;
3. desiste ao fim de **90 segundos** e usa o layout da plataforma;
4. apaga a pasta temporária no fim.

A falta do LibreOffice nunca impede a geração do documento: só muda o aspeto do PDF.

## 2. Requisitos

- **LibreOffice Writer sem interface gráfica.** Pacote `libreoffice-writer-nogui`, cerca de 250 MB instalado. Não é preciso o LibreOffice completo.
- **As fontes usadas no modelo Word.** O modelo Protteja usa **Inter** e **Inter Display**. Sem a fonte certa, o LibreOffice troca-a por outra e o PDF muda de aspeto.
- **Memória.** Cada conversão abre um processo do LibreOffice com cerca de 150–250 MB durante 1 a 3 segundos. Para 2 workers do gunicorn, conte com pelo menos **1 GB de RAM** no servidor.

## 3. Instalar num servidor Ubuntu/Debian (VPS)

```bash
# 3.1 LibreOffice só com o processador de texto, sem interface gráfica
sudo apt update
sudo apt install -y --no-install-recommends libreoffice-writer-nogui fonts-dejavu-core fontconfig unzip curl

# 3.2 Fontes Inter e Inter Display (versão oficial; o pacote fonts-inter não traz a Inter Display)
curl -fsSL -o /tmp/inter.zip https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip
sudo mkdir -p /usr/local/share/fonts/inter
sudo unzip -j -o /tmp/inter.zip 'extras/ttf/*.ttf' -d /usr/local/share/fonts/inter
sudo fc-cache -f
rm /tmp/inter.zip

# 3.3 Reiniciar a API para ela encontrar o LibreOffice
sudo systemctl restart q360
```

O serviço `q360` corre como `www-data`, e isso não exige configuração extra: o perfil do LibreOffice é criado numa pasta temporária em cada conversão. Se aparecer um erro de permissões relacionado com a pasta pessoal, acrescente `Environment=HOME=/tmp` na secção `[Service]` de `/etc/systemd/system/q360.service` e depois corra `sudo systemctl daemon-reload && sudo systemctl restart q360`.

Se o LibreOffice estiver instalado fora do PATH, indique o caminho em `/etc/q360.env`:

```bash
Q360_SOFFICE_PATH=/opt/libreoffice/program/soffice
```

## 4. Com Docker

O `Dockerfile.prod` já instala o LibreOffice e as fontes Inter. Basta construir a imagem e correr:

```bash
cd backend
docker build -f Dockerfile.prod -t q360-api .
docker run --env-file /etc/q360.env -p 8000:8000 q360-api
```

Para mudar a versão das fontes: `docker build --build-arg INTER_VERSION=4.1 ...`.

## 5. No Render

O serviço está configurado com `runtime: python`. Esse runtime **não permite instalar pacotes do sistema**, por isso o LibreOffice não pode ser instalado lá. Há duas opções:

1. **Passar a Docker** (recomendado). Em `render.yaml`, no serviço `q360-health-api`, troque:
   ```yaml
   runtime: python
   buildCommand: pip install --no-cache-dir -r requirements.render.txt && python manage.py migrate --noinput
   ```
   por:
   ```yaml
   runtime: docker
   dockerfilePath: ./Dockerfile.prod
   dockerContext: .
   preDeployCommand: python manage.py migrate --noinput
   ```
   Mantenha `rootDir: backend` e as variáveis de ambiente. O plano `free` tem 512 MB de memória, o que é pouco para a API mais o LibreOffice: use pelo menos o plano `starter`.
2. **Manter `runtime: python`.** Os PDFs usam o layout da plataforma; o formato Protteja fica disponível em DOCX.

## 6. Confirmar que está a funcionar

No servidor:

```bash
soffice --version                       # mostra a versão do LibreOffice
fc-list | grep -c "Inter Display"       # tem de ser maior que 0
```

Teste de conversão com o modelo Protteja do repositório:

```bash
cd /opt/q360/backend
mkdir -p /tmp/teste-pdf
cp apps/quote/seed/protteja_proposta_saude.docx /tmp/teste-pdf/
soffice --headless --convert-to pdf --outdir /tmp/teste-pdf /tmp/teste-pdf/protteja_proposta_saude.docx
ls -la /tmp/teste-pdf/protteja_proposta_saude.pdf
```

Abra o PDF e compare-o com as propostas Protteja: mesmo grafismo e mesmas fontes, com as marcas `{{…}}` por preencher.

Teste automático, que só corre quando o LibreOffice existe:

```bash
.venv/bin/python -m pytest tests/quote/test_word_pdf.py
```

Na plataforma:
1. Carregar a gama Protteja, se ainda não estiver carregada: `python manage.py seed_protteja_products --tenant-code <código>`. Depois, um administrador aprova e publica (ver o próprio comando).
2. Numa cotação de um plano Protteja, escolher o modelo `PROTTEJA-PROPOSTA-SAUDE` e gerar em **PDF**.
3. O PDF deve sair com o grafismo Protteja e os dados da cotação.

## 7. Resolução de problemas

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| O PDF sai com o layout da plataforma | LibreOffice não encontrado | Procurar no log da API `LibreOffice não encontrado`. Instalar (secção 3) ou definir `Q360_SOFFICE_PATH`, e reiniciar a API |
| O PDF sai com o layout da plataforma e o log diz `A conversão do Word para PDF falhou` | Conversão com erro ou acima de 90 s | Correr o teste manual da secção 6 para ver o erro; confirmar a memória livre (`free -m`) |
| O PDF tem outra letra | Fonte do modelo em falta | `fc-list \| grep -i inter`; instalar as fontes em falta e correr `sudo fc-cache -f` |
| A conversão é lenta na primeira vez | O LibreOffice cria o perfil e a cache de fontes | É normal na 1.ª conversão depois de arrancar; as seguintes demoram 1–3 s |
| Erro de permissões no log | O utilizador do serviço não pode escrever na pasta pessoal | Acrescentar `Environment=HOME=/tmp` ao serviço (secção 3) |

Para ver o log da API: `sudo journalctl -u q360 -f`.

## 8. Modelos de outras seguradoras

O mecanismo serve para qualquer modelo Word, não só para o da Protteja. Para um novo modelo:
1. Carregar o Word em Administração › Documentos, com as marcas `{{variável}}`. A lista das marcas aceites aparece no ecrã do modelo.
2. Instalar no servidor as fontes que esse Word usa, em `/usr/local/share/fonts/<nome>`, e correr `sudo fc-cache -f`.
3. Publicar o modelo e gerar uma proposta em PDF para confirmar.

## 9. Atualizar

- **LibreOffice:** `sudo apt update && sudo apt install --only-upgrade libreoffice-writer-nogui` e depois `sudo systemctl restart q360`.
- **Fontes Inter:** repetir o passo 3.2 com o número da nova versão.
- **Docker:** reconstruir a imagem.

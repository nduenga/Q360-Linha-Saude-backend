# Motores PDF do Q360: Chromium e LibreOffice

As propostas de cotação com modelo Word são preenchidas nesse DOCX; em PDF, o mesmo ficheiro é convertido pelo LibreOffice. Templates sem ficheiro Word usam o renderer HTML/CSS e Chromium. Assim, a pré-visualização e a geração final seguem o modelo selecionado.

## 1. O que faz e quando é preciso

Uma seguradora pode ter um modelo Word com marcas `{{variável}}`. O formato determina o motor:

| Documento/formato | Motor | Resultado |
|---|---|---|
| Proposta com modelo Word, DOCX | `python-docx` | Modelo Word preenchido |
| Proposta com modelo Word, PDF | LibreOffice Writer | Modelo Word preenchido e convertido em PDF |
| Template sem ficheiro Word, HTML/PDF | Chromium (Playwright) | HTML do template impresso em PDF A4 |
| Apólice Word/PDF | LibreOffice | Modelo Word preenchido, convertido em PDF |

O conversor Chromium está em `apps/quote/application/chromium_converter.py`; o LibreOffice está em `apps/quote/application/office_converter.py`.

Em cada conversão, a plataforma:
1. procura o executável: definição `OFFICE_CONVERTER_BIN`, variável `OFFICE_CONVERTER_BIN` ou `Q360_SOFFICE_PATH`, depois `soffice`/`libreoffice` no PATH e, em macOS, na pasta padrão da aplicação;
2. corre `soffice --headless --convert-to pdf` numa pasta temporária, com um perfil próprio, para que duas conversões ao mesmo tempo não se atropelem;
3. desiste ao fim do limite configurado e regista a falha;
4. apaga a pasta temporária no fim.

A geração de PDF de templates HTML exige o Chromium. A geração a partir de modelos Word exige o LibreOffice. O Dockerfile de produção instala ambos.

## 2. Requisitos

- **Chromium headless para propostas.** O Playwright e o navegador são instalados no `Dockerfile` e no `Dockerfile.prod`.
- **Desenvolvimento em macOS.** O conversor usa o Google Chrome em `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` se o Chromium gerido pelo Playwright não estiver configurado. O pacote Playwright continua a ser necessário no mesmo ambiente Python que inicia o Django.
- **LibreOffice Writer** para PDFs de propostas e apólices baseados em DOCX.
- **Fontes Inter e Inter Display.** O CSS das propostas e os modelos Word Protteja usam estas fontes. Sem elas, o Chromium ou o LibreOffice substitui a tipografia.
- **Memória.** Cada conversão abre um processo do LibreOffice com cerca de 150–250 MB durante 1 a 3 segundos. Para 2 workers do gunicorn, conte com pelo menos **1 GB de RAM** no servidor.

## 3. Instalar num servidor Ubuntu/Debian (VPS)

```bash
# Para instalações fora de Docker, instalar os browsers/dependências Playwright
# no mesmo ambiente Python usado pela API:
python -m pip install -r requirements.production.txt
python -m playwright install --with-deps chromium

# LibreOffice é necessário para PDFs baseados em Word.
sudo apt update
sudo apt install -y --no-install-recommends libreoffice-writer-nogui fonts-dejavu-core fontconfig

# Fontes usadas nos modelos Word devem estar instaladas para preservar a tipografia.
curl -fsSL -o /tmp/inter.zip https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip
sudo mkdir -p /usr/local/share/fonts/inter
sudo unzip -j -o /tmp/inter.zip 'extras/ttf/*.ttf' -d /usr/local/share/fonts/inter
sudo fc-cache -f
rm /tmp/inter.zip

# Reiniciar a API para aplicar as dependências
sudo systemctl restart q360
```

No macOS com o Google Chrome instalado, basta instalar as dependências Python no virtualenv do backend; o conversor deteta o Chrome e não exige descarregar outro browser:

```bash
../.venv/bin/python -m pip install -r requirements.txt
```

Para indicar outro executável Chromium/Chrome, definir `Q360_CHROMIUM_EXECUTABLE` no ambiente do serviço.

No macOS, o conversor deteta `/Applications/LibreOffice.app/Contents/MacOS/soffice`. Se estiver noutro local, defina `Q360_SOFFICE_PATH` com o caminho completo e reinicie o processo Django.

O serviço `q360` corre como `www-data`, e isso não exige configuração extra: o perfil do LibreOffice é criado numa pasta temporária em cada conversão. Se aparecer um erro de permissões relacionado com a pasta pessoal, acrescente `Environment=HOME=/tmp` na secção `[Service]` de `/etc/systemd/system/q360.service` e depois corra `sudo systemctl daemon-reload && sudo systemctl restart q360`.

Se o LibreOffice estiver instalado fora do PATH, indique o caminho em `/etc/q360.env`:

```bash
Q360_SOFFICE_PATH=/opt/libreoffice/program/soffice
```

## 4. Servidor próprio com Docker Compose

O deploy geral usa `backend/docker-compose.prod.yml`, que constrói explicitamente `Dockerfile.prod`, instala Chromium e LibreOffice, e mantém PostgreSQL e media em volumes persistentes. O build executa `soffice --version` e falha se o LibreOffice estiver ausente. Segue os passos de instalação em [`DEPLOY.md`](DEPLOY.md); não é necessário instalar LibreOffice manualmente no host.

Para mudar a versão das fontes, reconstrói a imagem com `--build-arg INTER_VERSION=...` no comando de build do Compose.

## 6. Confirmar que está a funcionar

No servidor:

```bash
python -m playwright --version          # mostra a versão do Playwright
soffice --version                       # mostra a versão do LibreOffice (para apólices Word)
```

Para verificar uma proposta com modelo Word, pré-visualize em PDF e compare com o DOCX preenchido. Ambos usam o mesmo modelo da seguradora. Templates sem ficheiro Word continuam a usar Chromium.

No Q360:
1. Abrir a pré-visualização HTML de uma proposta Protteja com dados representativos.
2. Gerar a mesma proposta em **PDF**.
3. Confirmar conteúdo, valores, fontes, cabeçalho repetido, rodapé e quebras de página.

## 7. Resolução de problemas

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| Erro a indicar que Playwright não está instalado | O Django usa um ambiente Python sem o pacote | Instalar as dependências no virtualenv que executa Django e reiniciar o serviço |
| Chromium não inicia | Browser ou bibliotecas do sistema em falta | Executar `python -m playwright install --with-deps chromium` no ambiente da API, ou configurar `Q360_CHROMIUM_EXECUTABLE` |
| PDF de proposta ou apólice Word não é gerado | LibreOffice ausente ou caminho não detetado | Instalar o LibreOffice, reiniciar a API e confirmar `soffice --version`; se necessário configurar `Q360_SOFFICE_PATH` |
| A tipografia difere num PDF Word | Fonte do modelo Word ausente | `fc-list \| grep -i inter`; instalar a fonte e correr `sudo fc-cache -f` |
| Erro de permissões do navegador | Cache do browser inacessível ao utilizador da API | Definir `PLAYWRIGHT_BROWSERS_PATH` para uma pasta legível pelo serviço e reinstalar o Chromium nessa pasta |

Para ver o log da API: `sudo journalctl -u q360 -f`.

## 8. Modelos de outras seguradoras

Os modelos Word são preenchidos para DOCX e convertidos pelo LibreOffice para PDF, preservando as marcas do modelo. Templates sem ficheiro Word usam HTML. Para configurar um modelo:
1. Carregar o Word em Administração › Documentos, com as marcas `{{variável}}`. A lista das marcas aceites aparece no ecrã do modelo.
2. Instalar no servidor as fontes que esse Word usa, em `/usr/local/share/fonts/<nome>`, e correr `sudo fc-cache -f`.
3. Publicar o modelo e gerar uma proposta em PDF para confirmar.

## 9. Atualizar

- **LibreOffice:** `sudo apt update && sudo apt install --only-upgrade libreoffice-writer-nogui` e depois `sudo systemctl restart q360`.
- **Playwright/Chromium:** atualizar `playwright` nas dependências e reconstruir a imagem Docker para instalar o browser compatível.
- **Fontes Inter:** repetir o passo de instalação da fonte com o número da nova versão.
- **Docker:** reconstruir a imagem.

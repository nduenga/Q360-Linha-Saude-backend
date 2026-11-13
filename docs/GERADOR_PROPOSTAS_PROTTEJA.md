# Gerador DOCX de propostas Protteja

O gerador usa diretamente os modelos Word preparados: não reconstrói o documento em HTML ou PDF. Assim, ao preencher os marcadores, conserva a estrutura, estilos, imagens, logótipo, cores, cabeçalhos e rodapés existentes no DOCX.

O preenchimento é feito diretamente no XML dos marcadores. O Q360 copia todas as outras partes internas do ficheiro sem as regravar: fontes, tamanhos, cores, estilos, imagens, marcas, temas, posicionamento e texto fixo aprovado da Protteja ficam exatamente como no modelo. Apenas os valores em `{{marcadores}}` e as linhas repetíveis já previstas no modelo podem mudar.

Os oito modelos de origem ficam em `Protteja_Propostas_Saude_v2/Q360_PREPARADOS_FORMATADOS`. A pasta `Q360_PREPARADOS_FINAL_FORMATADOS` também é aceite automaticamente caso seja criada com esse nome.

## Instalação por tenant

Instale os ficheiros como rascunhos para revisão:

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py install_protteja_quote_templates --tenant-id <UUID_DO_TENANT>
```

O comando valida todos os marcadores antes de guardar e é idempotente: uma execução posterior não duplica um modelo cujo DOCX seja igual. Por segurança, os modelos são instalados como `DRAFT`; pré-visualize-os e publique-os na administração de modelos. Para publicar conscientemente durante a instalação, acrescente `--publish`.

Os códigos a enviar no campo `templateCode` ao gerar uma proposta são:

- `PROTTEJA_BUSINESS_INDIVIDUAL` e `PROTTEJA_BUSINESS_GRUPO`
- `PROTTEJA_BUSINESS_PLUS_INDIVIDUAL` e `PROTTEJA_BUSINESS_PLUS_GRUPO`
- `PROTTEJA_PREMIUM_INDIVIDUAL` e `PROTTEJA_PREMIUM_GRUPO`
- `PROTTEJA_PREMIUM_PLUS_INDIVIDUAL` e `PROTTEJA_PREMIUM_PLUS_GRUPO`

Use `format: "DOCX"` na geração. O documento resultante é criado a partir do modelo escolhido, com os valores e listas da cotação preenchidos. As limitações funcionais e os campos que não devem ser inventados estão em `GUIA_PREPARACAO_MODELOS_Q360.md` e `CAMPOS_NAO_FORNECIDOS_PELO_GERADOR_Q360.md`.

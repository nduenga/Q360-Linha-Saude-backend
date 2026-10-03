# Plataforma: super administradores e tenants

Os super administradores são a equipa interna (nunca pessoas de uma empresa cliente) e gerem os tenants pela API, sem aceder ao servidor.

## Primeiro super admin (uma vez, no servidor)
`python manage.py migrate` e depois `python manage.py create_platform_admin --email ... --name ...`.
Os restantes super admins criam-se pela interface (`POST /api/v1/platform/admins`).

## Autenticação
`POST /api/v1/platform/auth/login` devolve um token próprio (`token_type=platform`, chave `PLATFORM_ADMIN_JWT_SIGNING_KEY`).
Esse token só vale em `/api/v1/platform/*`; o token de staff não vale lá. Cinco falhas bloqueiam a conta 30 minutos.

## Rotas
| Rota | Função |
|---|---|
| GET /platform/me, POST /platform/me/password | perfil e mudança da própria palavra-passe |
| GET, POST /platform/tenants | listar (filtros `status`, `q`) e criar tenant + dados da empresa + primeiro ADMIN |
| GET, PATCH /platform/tenants/{id} | detalhe (contas e contagens), alterar nome, dados da empresa e estado |
| POST /platform/tenants/{id}/admins | acrescentar outro ADMIN ao tenant |
| POST /platform/tenants/{id}/accounts/{accountId}/reset-password | nova palavra-passe temporária de uma conta do tenant |
| GET, POST /platform/admins; PATCH /platform/admins/{id}; POST /platform/admins/{id}/reset-password | gerir super admins |
| GET /platform/audit | auditoria de plataforma (filtros `action`, `entityType`, `entityId`, `actorId`, `limit`) |

## Regras
- A palavra-passe temporária aparece uma única vez na resposta; só o hash é guardado e nunca vai para a auditoria.
- O email do ADMIN é único em toda a plataforma (o login do staff é só por email).
- Suspender ou desativar um tenant bloqueia de imediato o staff e o portal do cliente desse tenant (cache de 30 s); reativar repõe o acesso.
- Um super admin não se pode desativar a si próprio nem deixar a plataforma sem nenhum ativo.
- Cada tenant nasce vazio e isolado; o catálogo de coberturas de mercado cria-se quando o tenant o usa pela primeira vez.
- Dados da empresa (`profile`): legalName, nif, email, phone, address, country, notes.

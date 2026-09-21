# Auth0 como fornecedor de login (OD-ANGOLA-008)

**Estado do backend: já está pronto.** `apps/foundation/infrastructure/
jwt_actor_adapter.py` já é um "Resource Server" OIDC padrão (valida
assinatura via JWKS, `issuer`, `audience`, expiração) — não é específico
de nenhum fornecedor. Ligar o Auth0 é **configuração**, não código novo.

O que falta, por esta ordem:
1. Criares a conta e os dois recursos no Auth0 (este guia).
2. Configurares o script que injecta `tenant_id`/`roles`/`scope` no token
   (este guia dá o script exacto).
3. Definires as variáveis de ambiente do backend (este guia dá a lista).
4. Ligar o ecrã de login do frontend ao Auth0 — fica para depois de teres
   o Domain/Client ID reais (é código que preciso de testar contra a tua
   conta real, não faz sentido escrever às cegas).

---

## Passo 1 — Criar a conta Auth0

1. Vai a https://auth0.com/signup e cria uma conta gratuita (o plano
   "Free" chega perfeitamente para desenvolvimento e para um volume
   inicial de produção).
2. Ao criar o primeiro "Tenant" (é o nome que o Auth0 dá ao teu espaço —
   não confundir com o `tenant_id` do Q360, são coisas diferentes; ver
   nota na secção 3), escolhe uma região próxima (Europa, já que Angola
   não tem região própria) e um nome, ex. `q360-saude`.

## Passo 2 — Criar a API (o "Resource Server")

Isto representa o teu backend Django.

1. No painel Auth0: **Applications → APIs → Create API**.
2. **Name**: `Q360 Health API`.
3. **Identifier**: `https://api.q360health.ao` (não precisa de ser uma
   URL real acessível — é só um identificador único; é isto que vai para
   `OIDC_AUDIENCE` no backend).
4. **Signing Algorithm**: `RS256` (deixa a opção por omissão).
5. Cria. Guarda o **Identifier** — vais precisar dele no Passo 5.

## Passo 3 — Criar a Application (o que o frontend usa para o login)

1. **Applications → Applications → Create Application**.
2. Nome: `Q360 Health Frontend`.
3. Tipo: **Single Page Application** (é uma SPA em React/Vite).
4. Depois de criada, no separador **Settings**:
   - **Allowed Callback URLs**: `http://localhost:5173, http://localhost:5174`
     (adiciona o domínio real de produção mais tarde, quando existir).
   - **Allowed Logout URLs**: mesmo valor.
   - **Allowed Web Origins**: `http://localhost:5173, http://localhost:5174`.
5. Guarda **Domain** e **Client ID** (aparecem no topo desta página) —
   vais precisar deles para ligar o frontend.

## Passo 4 — Injectar tenant/roles/scope no token (Action)

O Auth0 não sabe nada sobre o teu modelo `Tenant`/`Role` — isso é dado
nosso, não dele. A forma correcta de o token do Auth0 carregar essa
informação é um **Action** que corre depois do login.

**Como o Auth0 exige que claims personalizadas tenham um "namespace"**
(um prefixo tipo URL, nunca um nome simples como `tenant_id` sozinho),
vamos usar `https://q360.co.ao/` como prefixo.

1. **Actions → Library → Build Custom → Create Action**.
2. Nome: `Add Q360 claims`. Trigger: **Login / Post Login**.
3. Cola este código (substitui o corpo gerado por omissão):

```javascript
exports.onExecutePostLogin = async (event, api) => {
  const namespace = 'https://q360.co.ao/';

  // Onde vem o tenant_id/roles de cada utilizador: guardados no
  // app_metadata do próprio utilizador Auth0 (User Management → Users →
  // <utilizador> → app_metadata), até existir um fluxo de
  // aprovisionamento automático de tenants. Formato esperado:
  // { "tenant_id": "<uuid do Tenant no Q360>", "roles": ["ADMIN"] }
  const tenantId = event.user.app_metadata?.tenant_id;
  const roles = event.user.app_metadata?.roles || [];

  if (!tenantId) {
    api.access.deny('Este utilizador ainda não tem um tenant_id configurado.');
    return;
  }

  api.idToken.setCustomClaim(namespace + 'tenant_id', tenantId);
  api.accessToken.setCustomClaim(namespace + 'tenant_id', tenantId);
  api.idToken.setCustomClaim(namespace + 'roles', roles);
  api.accessToken.setCustomClaim(namespace + 'roles', roles);

  // "scope" já é um claim OAuth2 nativo — o Auth0 preenche-o a partir
  // dos "Permissions" da API (Passo 4b) automaticamente, não precisa de
  // ser definido aqui à mão.
};
```

4. **Deploy** o Action.
5. **Actions → Flows → Login** → arrasta `Add Q360 claims` para dentro
   do fluxo (entre "Start" e "Complete") → **Apply**.

### Passo 4b — Definir os scopes na API

1. Volta à API criada no Passo 2 → separador **Permissions**.
2. Adiciona exactamente estes 5 (já são os scopes reais do sistema,
   ART-006 `components.securitySchemes.oauth2` — não inventar outros):
   `q360.read`, `q360.write`, `q360.approve`, `q360.admin`, `q360.audit`.
3. Ao pedires login no frontend, pedes o `scope` que quiseres conforme o
   utilizador (ex. um Aprovador só recebe `q360.read q360.write
   q360.approve`) — a atribuição de "que scopes cada utilizador pode
   pedir" faz-se em **Auth0 → APIs → (a tua API) → Machine to Machine
   Applications**, ou por RBAC nativo do Auth0 se activares essa
   funcionalidade (Enable RBAC, na API, separador Settings).

### Passo 4c — Criar os primeiros utilizadores reais

**User Management → Users → Create User** — um por cada pessoa real
(não reutilizar os `admin@q360.co.ao`/`aprovador@q360.co.ao`/
`subscritor@q360.co.ao` do modo dev, esses continuam só para testes
locais). Depois de criado, em **app_metadata**, cola:

```json
{
  "tenant_id": "<uuid do Tenant real no Q360 — ver tabela q360.tenant>",
  "roles": ["ADMIN"]
}
```

(`roles` aceita qualquer combinação de `ADMIN`, `PRODUCT_CONFIGURATOR`,
`SUBSCRIBER`, `APPROVER`, `AUDITOR` — os mesmos 5 do DOC-001 §18, nunca
inventar um novo).

## Passo 5 — Configurar o backend

Em `backend/.env` (ambiente de produção real: variáveis de ambiente do
servidor, nunca um ficheiro `.env` commitado):

```
OIDC_ISSUER=https://<o-teu-tenant-auth0>.eu.auth0.com/
OIDC_AUDIENCE=https://api.q360health.ao
OIDC_JWKS_URL=https://<o-teu-tenant-auth0>.eu.auth0.com/.well-known/jwks.json
OIDC_TENANT_CLAIM=https://q360.co.ao/tenant_id
OIDC_ROLES_CLAIM=https://q360.co.ao/roles
OIDC_SCOPE_CLAIM=scope
OIDC_STATIC_VERIFICATION_KEY=
```

**Importante:** deixar `OIDC_STATIC_VERIFICATION_KEY` vazio (ou removê-la
de vez) é o que faz o backend deixar de aceitar o atalho de
desenvolvimento e passar a validar só contra o Auth0 real —
`config/settings/production.py` já recusa arrancar em produção se essa
variável estiver definida, precisamente para isto nunca acontecer por
engano.

Não precisas de tocar em nenhum ficheiro `.py` — `jwt_actor_adapter.py`
já lê estas variáveis directamente (ver `config/settings/base.py`).

## Passo 6 — Ligar o frontend (fica para quando tiveres Domain/Client ID)

Quando tiveres os dois valores do Passo 3, digo-me e faço esta parte:
troca do `LoginPage.tsx`/`dev-login` actual pelo SDK oficial
(`@auth0/auth0-react`), com o fluxo padrão de redireccionamento
(Authorization Code + PKCE — nunca um POST directo de password, que é o
que o atalho de desenvolvimento faz hoje). Não escrevo este código às
cegas porque preciso de testar contra a tua conta Auth0 real antes de
confiar que funciona.

## O que NÃO fica resolvido por este guia

- **Aprovisionamento automático de tenants** (hoje o `tenant_id` de cada
  utilizador é colado à mão no `app_metadata` — não existe nenhum ecrã
  de "criar a minha seguradora" self-service). Fica para quando isso for
  pedido explicitamente.
- **Login de clientes finais** (Portal do Cliente) — este guia é só para
  os utilizadores internos/staff (backoffice). Ver
  `ROADMAP_PORTAL_CLIENTE.md` para a autenticação de clientes finais, que
  é deliberadamente um mecanismo diferente (nunca deve herdar os scopes
  internos `q360.*`).

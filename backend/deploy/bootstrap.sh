#!/usr/bin/env bash
# Corre NO SERVIDOR, dentro de <repo>/backend, com /etc/q360.env já preenchido.
# Cria as tabelas (migrate) e os dados iniciais. Pode ser repetido (exceto o email do admin).
# Uso: TENANT=q360 ADMIN_EMAIL=admin@x.com ADMIN_PASSWORD='...' bash deploy/bootstrap.sh
set -euo pipefail
: "${TENANT:?defina TENANT}" "${ADMIN_EMAIL:?defina ADMIN_EMAIL}" "${ADMIN_PASSWORD:?defina ADMIN_PASSWORD}"

set -a; source /etc/q360.env; set +a
source .venv/bin/activate

python manage.py migrate --noinput
python manage.py seed_dev_tenant --code "$TENANT" --name "${TENANT_NAME:-Q360 Saude}"
python manage.py create_staff_account --email "$ADMIN_EMAIL" --name "${ADMIN_NAME:-Admin}" \
  --tenant-code "$TENANT" --password "$ADMIN_PASSWORD" || echo "(admin ja existe, a continuar)"
python manage.py seed_default_pricing_config --tenant-code "$TENANT"
python manage.py seed_health_market_templates --tenant-code "$TENANT"
echo "OK - verifique /api/v1/health/ready"

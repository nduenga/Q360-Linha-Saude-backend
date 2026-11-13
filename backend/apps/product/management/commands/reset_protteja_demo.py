"""Replace a demonstration tenant's portfolio with the Protteja health range."""
from __future__ import annotations

import datetime

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.client.application.proposer_service import create_proposer
from apps.client.domain.enums import ProposerType
from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.permissions import Role
from apps.foundation.domain.scopes import Scope
from apps.foundation.domain.tenant import TenantId
from apps.foundation.infrastructure.models import Tenant


PROPOSERS = (
    {
        "proposer_type": ProposerType.INDIVIDUAL.value,
        "display_name": "Ana Patrícia Manuel",
        "nif": "123456789LA001",
        "email": "ana.manuel@exemplo.ao",
        "phone": "+244 923 000 101",
        "date_of_birth": datetime.date(1988, 5, 14),
    },
    {
        "proposer_type": ProposerType.INDIVIDUAL.value,
        "display_name": "Carlos Alberto Domingos",
        "nif": "123456790LA001",
        "email": "carlos.domingos@exemplo.ao",
        "phone": "+244 923 000 102",
        "date_of_birth": datetime.date(1982, 9, 3),
    },
    {
        "proposer_type": ProposerType.ORGANISATION.value,
        "display_name": "Kwanza Saúde Serviços, Lda.",
        "nif": "5417000001",
        "email": "rh@kwanzasaude.ao",
        "phone": "+244 222 000 201",
        "date_of_birth": None,
    },
    {
        "proposer_type": ProposerType.ORGANISATION.value,
        "display_name": "Luanda Horizonte, S.A.",
        "nif": "5417000002",
        "email": "pessoas@luandahorizonte.ao",
        "phone": "+244 222 000 202",
        "date_of_birth": None,
    },
)

# Tenant business tables are discovered from PostgreSQL and removed in foreign
# key order. Accounts are deliberately retained so the demo login survives.
_EXCLUDED_TABLES = {"tenant", "staff_account", "staff_account_role", "staff_refresh_token", "platform_admin"}


class Command(BaseCommand):
    help = "Apaga os dados operacionais de demonstração de um tenant e semeia a gama Protteja e tomadores compatíveis."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-code", required=True)
        parser.add_argument("--approve-as", default="admin.demo@q360.local")
        parser.add_argument("--confirm", action="store_true", help="Confirma a eliminação irreversível dos dados operacionais do tenant.")

    def handle(self, *args, **options):
        if not options["confirm"]:
            raise CommandError("Operação destrutiva: repita com --confirm.")
        tenant = Tenant.objects.filter(code=options["tenant_code"]).first()
        if tenant is None:
            raise CommandError(f"Tenant inexistente: {options['tenant_code']}")

        with transaction.atomic():
            removed = self._clear_tenant_business_data(tenant.id)
        self.stdout.write(self.style.WARNING(f"Dados operacionais removidos: {removed} registos."))

        call_command(
            "seed_protteja_products",
            tenant_code=tenant.code,
            approve_as=options["approve_as"],
        )
        call_command(
            "install_protteja_quote_templates",
            tenant_id=str(tenant.id),
            publish=True,
        )
        token = CurrentActorProvider.bind(
            Actor(
                actor_id="system:seed-protteja-demo",
                tenant_id=TenantId.parse(tenant.id),
                roles=frozenset({Role.ADMIN}),
                scopes=frozenset(Scope),
                actor_type="SYSTEM",
            )
        )
        try:
            for row in PROPOSERS:
                create_proposer(
                    **row,
                    external_reference=f"PROTTEJA-DEMO-{row['nif']}",
                    registration_number=row["nif"],
                    address="Luanda, Angola",
                    province="Luanda",
                    municipality="Luanda",
                    attributes={"seed": "protteja-demo", "compatibleSegments": ["INDIVIDUAL_FAMILY", "GROUP"]},
                    require_birth_date=row["proposer_type"] == ProposerType.INDIVIDUAL.value,
                )
        finally:
            CurrentActorProvider.reset(token)
        call_command("seed_protteja_products", tenant_code=tenant.code, activate=True)
        self.stdout.write(self.style.SUCCESS("Gama Protteja ativa e 4 tomadores compatíveis criados."))

    def _clear_tenant_business_data(self, tenant_id) -> int:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.columns
                WHERE table_schema = 'q360' AND column_name = 'tenant_id'
                GROUP BY table_name
                """
            )
            tables = {row[0] for row in cursor.fetchall()} - _EXCLUDED_TABLES
            cursor.execute(
                """
                SELECT child.relname, parent.relname
                FROM pg_constraint fk
                JOIN pg_class child ON child.oid = fk.conrelid
                JOIN pg_class parent ON parent.oid = fk.confrelid
                JOIN pg_namespace ns ON ns.oid = child.relnamespace
                WHERE fk.contype = 'f' AND ns.nspname = 'q360'
                """
            )
            edges = [(child, parent) for child, parent in cursor.fetchall() if child in tables and parent in tables]

            ordered: list[str] = []
            visiting, visited = set(), set()

            def visit(table: str) -> None:
                if table in visited or table in visiting:
                    return
                visiting.add(table)
                for child, parent in edges:
                    if child == table:
                        visit(parent)
                visiting.remove(table)
                visited.add(table)
                ordered.append(table)

            for table in sorted(tables):
                visit(table)
            # DFS appends parents first; delete the reverse order so each
            # child is gone before the row it references.
            total = 0
            for table in reversed(ordered):
                cursor.execute(f'DELETE FROM q360."{table}" WHERE tenant_id = %s', [str(tenant_id)])
                total += cursor.rowcount
            return total

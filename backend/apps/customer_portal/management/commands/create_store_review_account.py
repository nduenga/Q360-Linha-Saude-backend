"""Conta de demonstração para os revisores da Apple e da Google
(roadmap_mobile.md, Fase 4): entram na app com email + palavra-passe, sem
passar pelo primeiro acesso por código (os revisores não têm acesso à caixa de
correio).

Liga a conta a um cliente que já exista na seguradora (por número de registo):
escolha um cliente de demonstração, nunca um cliente real. Não cria apólices
nem cotações.

    python manage.py create_store_review_account --tenant-id <uuid> \\
        --registration-number <documento> --email revisor@exemplo.ao --confirm
"""
from __future__ import annotations

import secrets

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.client.infrastructure.models import Proposer
from apps.customer_portal.infrastructure.models import CustomerAccount, CustomerAccountProposer
from apps.foundation.infrastructure.models import Tenant


class Command(BaseCommand):
    help = "Cria (ou repõe a palavra-passe de) uma conta de demonstração para os revisores das lojas."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-id", required=True)
        parser.add_argument("--registration-number", required=True, help="Documento do cliente de demonstração.")
        parser.add_argument("--email", required=True)
        parser.add_argument("--password", help="Se omitida, gera-se uma e mostra-se no fim.")
        parser.add_argument("--confirm", action="store_true", help="Confirma que o cliente é de demonstração.")

    def handle(self, *args, **options):
        if not options["confirm"]:
            raise CommandError("Use --confirm para indicar que o cliente escolhido é de demonstração.")
        tenant = Tenant.objects.filter(id=options["tenant_id"]).first()
        if tenant is None:
            raise CommandError("Seguradora não encontrada.")
        proposer = Proposer.all_tenants.filter(
            tenant_id=tenant.id, registration_number=options["registration_number"]
        ).first()
        if proposer is None:
            raise CommandError("Não existe nenhum cliente com esse número de registo nesta seguradora.")
        email = options["email"].strip().lower()
        password = options["password"] or secrets.token_urlsafe(12)
        with transaction.atomic():
            account = CustomerAccount.all_tenants.filter(tenant_id=tenant.id, email__iexact=email).first()
            if account is None:
                account = CustomerAccount.all_tenants.create(tenant_id=tenant.id, email=email)
            CustomerAccount.all_tenants.filter(id=account.id).update(
                password_hash=make_password(password), password_set_at=timezone.now(), email_verified=True,
                failed_otp_attempts=0, locked_until=None, deleted_at=None,
            )
            CustomerAccountProposer.all_tenants.get_or_create(
                tenant_id=tenant.id, customer_account=account, proposer=proposer
            )
        self.stdout.write(f"Conta de revisão pronta: {email} / {password}  (seguradora {tenant.name}).")

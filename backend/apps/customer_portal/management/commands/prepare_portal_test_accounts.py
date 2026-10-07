"""Prepare existing production customers for first-access email testing.

This command never creates customer, quote, or policy business records and
never resets or verifies an existing account's password or email.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.client.infrastructure.models import Proposer
from apps.customer_portal.infrastructure.models import CustomerAccount, CustomerAccountProposer
from apps.foundation.infrastructure.models import Tenant
from apps.policy.infrastructure.models import Policy
from apps.quote.domain.enums import QuoteStatus
from apps.quote.infrastructure.models import Quote

TEST_EMAILS = (
    "helibrando@gmail.com",
    "fabiongila@gmail.com",
    "sethlussueki@gmail.com",
)


class Command(BaseCommand):
    help = (
        "Create/link Portal accounts for the three test emails against existing "
        "customer records. Does not change passwords or business records."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-id",
            required=True,
            help="Explicit UUID of the tenant containing the existing customer records.",
        )
        parser.add_argument(
            "--confirm-production",
            action="store_true",
            help="Required acknowledgement before changing account/link rows in a production tenant.",
        )

    def handle(self, *args, **options):
        if not options["confirm_production"]:
            raise CommandError(
                "This command changes customer-account associations. Re-run with "
                "--confirm-production after verifying the tenant and customer records."
            )

        tenant = Tenant.objects.filter(id=options["tenant_id"]).first()
        if tenant is None:
            raise CommandError(f"Tenant '{options['tenant_id']}' was not found.")

        records = {}
        errors = []
        for email in TEST_EMAILS:
            proposers = list(
                Proposer.all_tenants.filter(tenant_id=tenant.id, email__iexact=email).order_by("id")
            )
            eligible = []
            for proposer in proposers:
                policy_numbers = list(
                    Policy.all_tenants.filter(tenant_id=tenant.id, proposer_id=proposer.id)
                    .exclude(policy_number__isnull=True)
                    .order_by("created_at")
                    .values_list("policy_number", flat=True)
                )
                quote_numbers = list(
                    Quote.all_tenants.filter(tenant_id=tenant.id, proposer_id=proposer.id)
                    .exclude(status=QuoteStatus.DRAFT.value)
                    .exclude(quote_number__isnull=True)
                    .order_by("created_at")
                    .values_list("quote_number", flat=True)
                )
                references = [*policy_numbers, *quote_numbers]
                if references:
                    eligible.append((proposer, references))
            if not eligible:
                errors.append(
                    f"{email}: no existing proposer with a policy or non-draft quote "
                    "and the same registered email was found."
                )
            else:
                records[email] = eligible

        if errors:
            raise CommandError(
                "No changes were made. Add or verify the existing customer email and "
                "policy/quote records before retrying:\n- " + "\n- ".join(errors)
            )

        created_accounts = 0
        created_links = 0
        with transaction.atomic():
            for email, eligible in records.items():
                account = (
                    CustomerAccount.all_tenants.filter(tenant_id=tenant.id, email__iexact=email).first()
                )
                if account is None:
                    account = CustomerAccount.all_tenants.create(
                        tenant_id=tenant.id,
                        email=email,
                        password_hash=None,
                        password_set_at=None,
                        email_verified=False,
                    )
                    created_accounts += 1
                for proposer, _references in eligible:
                    _link, created = CustomerAccountProposer.all_tenants.get_or_create(
                        tenant_id=tenant.id,
                        customer_account=account,
                        proposer=proposer,
                    )
                    created_links += int(created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Portal test accounts prepared for tenant {tenant.code} ({tenant.id}). "
                f"Created {created_accounts} account(s) and {created_links} link(s); "
                "existing passwords and verification states were left unchanged."
            )
        )
        for email, eligible in records.items():
            for proposer, references in eligible:
                self.stdout.write(
                    f"  {email} -> {proposer.display_name}; reference: {references[0]}"
                )

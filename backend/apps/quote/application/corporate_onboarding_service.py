"""Atomic onboarding of a corporate population into a new quotation."""
from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.client.application import household_service, member_service
from apps.client.domain.enums import ProposerType
from apps.client.domain.errors import HouseholdValidationError
from apps.client.infrastructure.models import Proposer
from apps.foundation.interfaces.middleware import get_correlation_id
from apps.quote.application import quote_service, requirements_service


def create_corporate_quotation(
    *,
    plan_id,
    proposer_id=None,
    proposer_input: dict[str, Any] | None = None,
    source_channel: str | None = None,
    households: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create corporate people, optional households, quote and its premium.

    Every person in this explicit onboarding request becomes a QuoteMember.
    Merely joining a household never has that financial side effect.
    """
    with transaction.atomic():
        quote = quote_service.create_quote(
            proposer_id=proposer_id,
            proposer_input=proposer_input,
            plan_id=plan_id,
            source_channel=source_channel,
        )
        proposer = Proposer.objects.get(id=quote.proposer_id)
        if proposer.proposer_type != ProposerType.ORGANISATION.value:
            raise HouseholdValidationError("O onboarding corporativo requer um proponente ORGANISATION.")

        created = []
        for household_input in households:
            holder_input = household_input["holder"]
            joined_at = household_input["joinedAt"]
            holder = member_service.create_member(
                proposer=proposer, relationship_code=holder_input["relationshipCode"],
                first_name=holder_input["firstName"], last_name=holder_input.get("lastName"),
                date_of_birth=holder_input["dateOfBirth"], sex_code=holder_input.get("sexCode"),
                external_reference=holder_input.get("externalReference"), attributes=holder_input.get("attributes"),
                nif=holder_input.get("nif"),
            )
            household = None
            if household_input["createHousehold"]:
                household = household_service.create_household(
                    proposer=proposer, primary_member=holder, joined_at=joined_at
                )
            quote_service.add_quote_member(quote=quote, member_id=holder.id, correlation_id=get_correlation_id())

            dependant_ids = []
            for dependant_input in household_input["dependents"]:
                dependant = member_service.create_member(
                    proposer=proposer, relationship_code=dependant_input["relationshipCode"],
                    first_name=dependant_input["firstName"], last_name=dependant_input.get("lastName"),
                    date_of_birth=dependant_input["dateOfBirth"], sex_code=dependant_input.get("sexCode"),
                    external_reference=dependant_input.get("externalReference"), attributes=dependant_input.get("attributes"),
                    nif=dependant_input.get("nif"),
                )
                household_service.add_dependent(household=household, member=dependant, joined_at=joined_at)
                quote_service.add_quote_member(quote=quote, member_id=dependant.id, correlation_id=get_correlation_id())
                dependant_ids.append(str(dependant.id))

            created.append({
                "holderMemberId": str(holder.id),
                "householdId": str(household.id) if household else None,
                "dependentMemberIds": dependant_ids,
            })

        pricing = quote_service.price_quote(quote=quote, recalculate=True, correlation_id=get_correlation_id())
        quote.refresh_from_db()
        return {
            "quote": quote,
            "pricing": pricing,
            "requirements": requirements_service.evaluate_requirements(quote),
            "households": created,
        }

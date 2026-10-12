"""DTOs matching ART-006 schemas verbatim — see apps/product/interfaces/serializers.py
for the "why plain Serializer, not ModelSerializer" rationale."""
from __future__ import annotations

from rest_framework import serializers

from apps.client.domain.enums import ImportJobStatus, MemberStatus, ProposerStatus, ProposerType
from apps.client.domain.nif import NifFormatError, validate_agt_nif
from apps.client.domain.rules import require_date_of_birth
from apps.foundation.domain.problem import DomainProblem


class ProposerSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    proposerType = serializers.ChoiceField(source="proposer_type", choices=[t.value for t in ProposerType])
    externalReference = serializers.CharField(source="external_reference", allow_null=True)
    displayName = serializers.CharField(source="display_name")
    nif = serializers.CharField(allow_null=True)
    registrationNumber = serializers.CharField(source="registration_number", allow_null=True)
    dateOfBirth = serializers.DateField(source="date_of_birth", allow_null=True)
    email = serializers.CharField(allow_null=True)
    phone = serializers.CharField(allow_null=True)
    address = serializers.CharField(
        allow_null=True,
        allow_blank=True,
    )
    attributes = serializers.JSONField(source="attributes_json")
    status = serializers.ChoiceField(choices=[s.value for s in ProposerStatus])
    rowVersion = serializers.IntegerField(source="row_version")


class _ProposerNifRequestSerializer(serializers.Serializer):
    """Shared input handling for the canonical NIF and its legacy alias."""

    nif = serializers.CharField(min_length=1, max_length=30, required=False)
    dateOfBirth = serializers.DateField(required=False, allow_null=True, default=None)
    registrationNumber = serializers.CharField(min_length=1, max_length=100, required=False)

    def _proposer_type(self, attrs: dict) -> str | None:
        """Tipo que decide o formato do NIF: vem no corpo (criar) ou do
        proponente existente (editar, via `context["proposer_type"]`)."""
        return attrs.get("proposerType") or self.context.get("proposer_type")

    def _validated_birth_date(self, attrs: dict):
        """Proponente INDIVIDUAL: data de nascimento obrigatória. Empresa: ignorada."""
        if self._proposer_type(attrs) != "INDIVIDUAL":
            return None
        try:
            return require_date_of_birth(attrs.get("dateOfBirth"), who="proponente individual")
        except DomainProblem as exc:
            raise serializers.ValidationError({"dateOfBirth": str(exc)}) from exc

    def _validated_nif(self, attrs: dict) -> tuple[str, str]:
        proposer_type = self._proposer_type(attrs)
        raw_nif = attrs.get("nif")
        legacy_registration_number = attrs.get("registrationNumber")

        if raw_nif is None and legacy_registration_number is None:
            raise serializers.ValidationError({"nif": "Indique o NIF."})

        try:
            nif = validate_agt_nif(raw_nif if raw_nif is not None else legacy_registration_number, proposer_type)
        except NifFormatError as exc:
            raise serializers.ValidationError({"nif": str(exc)}) from exc

        if raw_nif is not None and legacy_registration_number is not None:
            try:
                legacy_nif = validate_agt_nif(legacy_registration_number, proposer_type)
            except NifFormatError as exc:
                raise serializers.ValidationError({"registrationNumber": str(exc)}) from exc
            if nif != legacy_nif:
                raise serializers.ValidationError(
                    {"registrationNumber": "O NIF e o registrationNumber devem coincidir quando ambos são enviados."}
                )

        # Keep old consumers (including the customer portal) working while
        # `nif` becomes the source of truth in the physical schema.
        return nif, nif


class ProposerCreateRequestSerializer(_ProposerNifRequestSerializer):
    """Product Owner decision (2026-09-26): registrationNumber (NIF), email
    and phone are mandatory when creating a Proposer — no longer optional
    identity/contact fields. `email`/`phone` columns added to `proposer`
    by apps/client/infrastructure/migrations/0003_proposer_contact_fields.py."""

    proposerType = serializers.ChoiceField(choices=[t.value for t in ProposerType])
    externalReference = serializers.CharField(allow_null=True, required=False, default=None)
    displayName = serializers.CharField(min_length=1, max_length=250)
    email = serializers.EmailField(max_length=254)
    phone = serializers.CharField(min_length=1, max_length=30)
    address = serializers.CharField(
        max_length=500,
        required=False,
        allow_null=True,
        allow_blank=True,
        default=None,
    )
    attributes = serializers.JSONField(required=False, default=dict)

    def validate(self, attrs: dict) -> dict:
        nif, registration_number = self._validated_nif(attrs)
        return {
            "proposer_type": attrs["proposerType"],
            "external_reference": attrs["externalReference"],
            "display_name": attrs["displayName"],
            "nif": nif,
            "registration_number": registration_number,
            "email": attrs["email"],
            "phone": attrs["phone"],
            "attributes": attrs["attributes"],
            "date_of_birth": self._validated_birth_date(attrs),
            "require_birth_date": True,
        }


class ProposerUpdateRequestSerializer(_ProposerNifRequestSerializer):
    displayName = serializers.CharField(min_length=1, max_length=250)
    email = serializers.EmailField(max_length=254)
    phone = serializers.CharField(min_length=1, max_length=30)
    address = serializers.CharField(
        max_length=500,
        required=False,
        allow_null=True,
        allow_blank=True,
        default=None,
    )
    attributes = serializers.JSONField(required=False, default=dict)
    rowVersion = serializers.IntegerField(min_value=0)

    def validate(self, attrs: dict) -> dict:
        nif, registration_number = self._validated_nif(attrs)
        return {
            "display_name": attrs["displayName"],
            "nif": nif,
            "registration_number": registration_number,
            "email": attrs["email"],
            "phone": attrs["phone"],
            "attributes": attrs["attributes"],
            "row_version": attrs["rowVersion"],
            "date_of_birth": self._validated_birth_date(attrs),
            "require_birth_date": True,
        }


class RelationshipCodeSerializer(serializers.Serializer):
    """Pragmatic V1 addition, not in ART-006 — see
    apps/client/application/relationship_service.py module docstring and
    ROADMAP_ANGOLA_CUSTOMIZATION.md OD-003."""

    id = serializers.UUIDField()
    code = serializers.CharField()
    label = serializers.CharField()
    category = serializers.CharField()


class MemberSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    proposerId = serializers.UUIDField(source="proposer_id")
    externalReference = serializers.CharField(source="external_reference", allow_null=True)
    relationshipCode = serializers.CharField(source="relationship_code")
    firstName = serializers.CharField(source="first_name", allow_null=True)
    lastName = serializers.CharField(source="last_name", allow_null=True)
    dateOfBirth = serializers.DateField(source="date_of_birth", allow_null=True)
    sexCode = serializers.CharField(source="sex_code", allow_null=True)
    attributes = serializers.JSONField(source="attributes_json")
    status = serializers.ChoiceField(choices=[s.value for s in MemberStatus])
    rowVersion = serializers.IntegerField(source="row_version")


class MemberCreateRequestSerializer(serializers.Serializer):
    proposerId = serializers.UUIDField()
    externalReference = serializers.CharField(allow_null=True, required=False, default=None)
    relationshipCode = serializers.CharField(min_length=1, max_length=40)
    firstName = serializers.CharField(allow_null=True, required=False, default=None)
    lastName = serializers.CharField(allow_null=True, required=False, default=None)
    # Obrigatória para todo o beneficiário/membro. Email e telefone NÃO existem
    # aqui: herdam os do titular (campos do proponente).
    dateOfBirth = serializers.DateField(required=True, allow_null=False)
    sexCode = serializers.CharField(allow_null=True, required=False, default=None)
    attributes = serializers.JSONField(required=False, default=dict)


class MemberUpdateRequestSerializer(serializers.Serializer):
    relationshipCode = serializers.CharField(min_length=1)
    firstName = serializers.CharField(allow_null=True, required=False, default=None)
    lastName = serializers.CharField(allow_null=True, required=False, default=None)
    dateOfBirth = serializers.DateField(required=True, allow_null=False)
    sexCode = serializers.CharField(allow_null=True, required=False, default=None)
    attributes = serializers.JSONField(required=False, default=dict)
    rowVersion = serializers.IntegerField(min_value=0)


class MemberDeleteRequestSerializer(serializers.Serializer):
    """Deletion is a reversible deactivation so quotes and pricing history
    that already reference a member remain intact."""

    rowVersion = serializers.IntegerField(min_value=0)


class ImportJobSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    proposerId = serializers.UUIDField(source="proposer_id", allow_null=True)
    status = serializers.ChoiceField(choices=[s.value for s in ImportJobStatus])
    totalRows = serializers.IntegerField(source="total_rows")
    validRows = serializers.IntegerField(source="valid_rows")
    invalidRows = serializers.IntegerField(source="invalid_rows")
    createdAt = serializers.DateTimeField(source="created_at")


class ImportCommitRequestSerializer(serializers.Serializer):
    confirm = serializers.BooleanField()

    def validate_confirm(self, value: bool) -> bool:
        if value is not True:
            raise serializers.ValidationError("É necessário confirmar (confirm tem de ser true).")
        return value


class ProposerDeleteRequestSerializer(serializers.Serializer):
    rowVersion = serializers.IntegerField(
        min_value=0
    )

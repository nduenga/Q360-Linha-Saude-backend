"""Controllers for the client module. Scopes copied from ART-006's
`security` block per `operationId` — cross-check against
docs/artifacts/ART-006-openapi/. DOC-001 s18 has no permission entries for
this domain (only `product:manage`/`pricing-config:manage` exist), so
these views are gated by OAuth2 scope alone — see
docs/08-integration-contract/BACKEND_FRONTEND_ALIGNMENT.md.
"""
from __future__ import annotations

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.parsers import MultiPartParser
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema

from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.middleware import requires_idempotency
from apps.foundation.interfaces.permissions import require_scope
from apps.client.application import household_service, import_service, member_service, proposer_service
from apps.client.application.relationship_service import list_relationship_codes
from apps.client.infrastructure.models import FamilyHousehold, FamilyHouseholdMember, ImportJob, InsuredMember, Person, Proposer
from apps.client.interfaces.serializers import (
    ImportCommitRequestSerializer,
    ImportJobSerializer,
    MemberCreateRequestSerializer,
    MemberDeleteRequestSerializer,
    MemberSerializer,
    MemberUpdateRequestSerializer,
    PersonSerializer,
    ProposerCreateRequestSerializer,
    ProposerDeleteRequestSerializer,
    ProposerSerializer,
    ProposerUpdateRequestSerializer,
    RelationshipCodeSerializer,
    HouseholdAddDependentSerializer, HouseholdCreateDependentSerializer, HouseholdCreateSerializer, HouseholdLinkPersonSerializer, HouseholdMemberSerializer,
    HouseholdRemoveDependentSerializer, HouseholdSerializer,
)
from shared.pagination import Q360PageNumberPagination


def _domain_operation(operation, **kwargs):
    """Translate validation failures from the domain boundary into ART-006 errors."""
    try:
        return operation(**kwargs)
    except ValueError as exc:
        raise ValidationError({"detail": str(exc)}) from exc


class RelationshipCodeListView(APIView):
    """Pragmatic V1 addition, not in ART-006 — see
    apps/client/application/relationship_service.py module docstring and
    ROADMAP_ANGOLA_CUSTOMIZATION.md OD-003. Lists the real, DB-backed
    catalogue of relationship codes for the current tenant, seeding it on
    first use — the frontend should build its "Relação" dropdown from
    this, never from a hardcoded array."""

    permission_classes = [require_scope(Scope.READ)]

    @extend_schema(parameters=[OpenApiParameter(
        name="householdRole", type=OpenApiTypes.STR, location=OpenApiParameter.QUERY,
        enum=["HOLDER", "DEPENDENT"], required=False,
        description="HOLDER devolve apenas TITULAR; DEPENDENT devolve relações elegíveis como dependente.",
    )])
    def get(self, request):
        household_role = request.query_params.get("householdRole", "DEPENDENT").upper()
        if household_role not in {"HOLDER", "DEPENDENT"}:
            raise ValidationError({"householdRole": "Use HOLDER ou DEPENDENT."})
        queryset = list_relationship_codes(household_role=household_role)
        paginator = Q360PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(RelationshipCodeSerializer(page, many=True).data)


class PersonListView(APIView):
    """Tenant-scoped search for reusing civil identities across households."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request):
        search = (request.query_params.get("search") or "").strip()
        if len(search) < 2:
            return Response([])
        people = Person.objects.filter(
            Q(first_name__icontains=search) | Q(last_name__icontains=search) | Q(nif__icontains=search)
        ).order_by("first_name", "last_name", "id")[:30]
        return Response(PersonSerializer(people, many=True).data)


@requires_idempotency
class ProposerListCreateView(APIView):
    """Proposer search accepts optional `q`, matching display name, NIF or email."""

    def get_permissions(self):
        scope = Scope.WRITE if self.request.method == "POST" else Scope.READ
        return [require_scope(scope)()]

    def get(self, request):
        queryset = Proposer.objects.all().order_by("display_name")
        search = request.query_params.get("q", "").strip()
        if search:
            queryset = queryset.filter(
                Q(display_name__icontains=search)
                | Q(nif__icontains=search)
                | Q(email__icontains=search)
            )
        paginator = Q360PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(ProposerSerializer(page, many=True).data)

    def post(self, request):
        body = ProposerCreateRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        proposer = proposer_service.create_proposer(**body.validated_data)
        # Convite por email para o Portal do Cliente (enviado depois do commit).
        from apps.customer_portal.application.invitation_service import invite_proposer

        invite_proposer(proposer)
        return Response(ProposerSerializer(proposer).data, status=201)


@requires_idempotency
@requires_idempotency
class ProposerDetailView(APIView):

    def get_permissions(self):
        return [
            require_scope(
                Scope.WRITE
                if self.request.method in ["PUT", "DELETE"]
                else Scope.READ
            )()
        ]

    def get(self, request, proposer_id):
        proposer = get_object_or_404(
            Proposer,
            id=proposer_id,
        )

        return Response(
            ProposerSerializer(proposer).data
        )

    def put(self, request, proposer_id):
        proposer = get_object_or_404(
            Proposer,
            id=proposer_id,
        )

        body = ProposerUpdateRequestSerializer(
            data=request.data,
            context={
                "proposer_type": proposer.proposer_type,
                "address": proposer.address,
                "province": proposer.province,
                "municipality": proposer.municipality,
            },
        )

        body.is_valid(
            raise_exception=True
        )

        updated = proposer_service.update_proposer(
            proposer=proposer,
            **body.validated_data,
        )

        return Response(
            ProposerSerializer(updated).data
        )

    def delete(self, request, proposer_id):
        proposer = get_object_or_404(
            Proposer,
            id=proposer_id,
        )

        body = ProposerDeleteRequestSerializer(
            data=request.data
        )

        body.is_valid(
            raise_exception=True
        )

        proposer = proposer_service.deactivate_proposer(
            proposer=proposer,
            row_version=body.validated_data["rowVersion"],
        )

        return Response(
            ProposerSerializer(proposer).data,
            status=200,
        )

@requires_idempotency
class MemberListCreateView(APIView):
    def get_permissions(self):
        scope = Scope.WRITE if self.request.method == "POST" else Scope.READ
        return [require_scope(scope)()]

    def get(self, request):
        queryset = InsuredMember.objects.all().order_by("last_name", "first_name")
        proposer_id = request.query_params.get("proposerId")
        if proposer_id:
            queryset = queryset.filter(proposer_id=proposer_id)
        paginator = Q360PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(MemberSerializer(page, many=True).data)

    def post(self, request):
        body = MemberCreateRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        proposer = get_object_or_404(Proposer, id=data.pop("proposerId"))
        member = member_service.create_member(
            proposer=proposer,
            relationship_code=data["relationshipCode"],
            first_name=data["firstName"],
            last_name=data["lastName"],
            date_of_birth=data["dateOfBirth"],
            sex_code=data["sexCode"],
            external_reference=data["externalReference"],
            attributes=data["attributes"],
            nif=data["nif"],
        )
        return Response(MemberSerializer(member).data, status=201)


@requires_idempotency
class MemberDetailView(APIView):
    def get_permissions(self):
        scope = Scope.WRITE if self.request.method in ("PUT", "DELETE") else Scope.READ
        return [require_scope(scope)()]

    def get(self, request, member_id):
        member = get_object_or_404(InsuredMember, id=member_id)
        return Response(MemberSerializer(member).data)

    def put(self, request, member_id):
        member = get_object_or_404(InsuredMember, id=member_id)
        body = MemberUpdateRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        updated = member_service.update_member(
            member=member,
            relationship_code=data["relationshipCode"],
            first_name=data["firstName"],
            last_name=data["lastName"],
            date_of_birth=data["dateOfBirth"],
            sex_code=data["sexCode"],
            attributes=data["attributes"],
            row_version=data["rowVersion"],
            nif=data.get("nif"),
            keep_nif="nif" not in data,
        )
        return Response(MemberSerializer(updated).data)

    def delete(self, request, member_id):
        member = get_object_or_404(InsuredMember, id=member_id)
        body = MemberDeleteRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        deactivated = member_service.deactivate_member(
            member=member,
            row_version=body.validated_data["rowVersion"],
        )
        return Response(MemberSerializer(deactivated).data)


@requires_idempotency
class MemberImportUploadView(APIView):
    # ART-006 uploadMemberImport is the one operation with a
    # multipart/form-data body; every other endpoint is JSON-only
    # (REST_FRAMEWORK["DEFAULT_PARSER_CLASSES"] is JSONParser only), so the
    # parser is overridden here instead of globally.
    parser_classes = [MultiPartParser]
    permission_classes = [require_scope(Scope.WRITE)]

    def post(self, request):
        uploaded_file = request.FILES.get("file")
        if uploaded_file is None:
            return Response({"file": "This field is required."}, status=400)
        proposer = None
        proposer_id = request.data.get("proposerId")
        if proposer_id:
            proposer = get_object_or_404(Proposer, id=proposer_id)

        actor = CurrentActorProvider.get()
        import_job = import_service.upload_member_import(
            proposer=proposer, uploaded_file=uploaded_file, actor_id=actor.actor_id if actor else "unknown"
        )
        return Response(ImportJobSerializer(import_job).data, status=202)


class MemberImportDetailView(APIView):
    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, import_id):
        import_job = get_object_or_404(ImportJob, id=import_id)
        return Response(ImportJobSerializer(import_job).data)


@requires_idempotency
class MemberImportCommitView(APIView):
    permission_classes = [require_scope(Scope.WRITE)]

    def post(self, request, import_id):
        body = ImportCommitRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        import_job = get_object_or_404(ImportJob, id=import_id)
        actor = CurrentActorProvider.get()
        committed = import_service.commit_member_import(
            import_job=import_job, actor_id=actor.actor_id if actor else "unknown"
        )
        return Response(ImportJobSerializer(committed).data, status=202)


class HouseholdListCreateView(APIView):
    """Optional family households for a corporate policyholder."""

    def get_permissions(self):
        return [require_scope(Scope.WRITE if self.request.method == "POST" else Scope.READ)()]

    def get(self, request):
        households = FamilyHousehold.objects.all().order_by("proposer_id", "created_at")
        if proposer_id := request.query_params.get("proposerId"):
            households = households.filter(proposer_id=proposer_id)
        return Response(HouseholdSerializer(households, many=True).data)

    @requires_idempotency
    def post(self, request):
        body = HouseholdCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        household = _domain_operation(
            household_service.create_household,
            proposer=get_object_or_404(Proposer, id=data["proposerId"]),
            primary_member=get_object_or_404(InsuredMember, id=data["primaryMemberId"]),
            joined_at=data["joinedAt"],
        )
        return Response(HouseholdSerializer(household).data, status=201)


class HouseholdDetailView(APIView):
    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, household_id):
        return Response(HouseholdSerializer(get_object_or_404(FamilyHousehold, id=household_id)).data)


class HouseholdMemberListAddView(APIView):
    def get_permissions(self):
        return [require_scope(Scope.WRITE if self.request.method == "POST" else Scope.READ)()]

    def get(self, request, household_id):
        household = get_object_or_404(FamilyHousehold, id=household_id)
        return Response(HouseholdMemberSerializer(household.memberships.select_related("member", "person").order_by("joined_at"), many=True).data)

    @requires_idempotency
    def post(self, request, household_id):
        body = HouseholdAddDependentSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        membership = _domain_operation(
            household_service.add_dependent,
            household=get_object_or_404(FamilyHousehold, id=household_id),
            member=get_object_or_404(InsuredMember, id=data["memberId"]),
            joined_at=data["joinedAt"],
        )
        return Response(HouseholdMemberSerializer(membership).data, status=201)


class HouseholdMemberRemoveView(APIView):
    permission_classes = [require_scope(Scope.WRITE)]

    @requires_idempotency
    def post(self, request, household_id, membership_id):
        body = HouseholdRemoveDependentSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        membership = get_object_or_404(FamilyHouseholdMember, id=membership_id, household_id=household_id)
        result = _domain_operation(
            household_service.remove_dependent,
            membership=membership, left_at=body.validated_data["leftAt"], row_version=body.validated_data["rowVersion"],
        )
        return Response(HouseholdMemberSerializer(result).data)


class HouseholdDependentCreateView(APIView):
    """Create an unregistered family dependant and add it to this household."""

    permission_classes = [require_scope(Scope.WRITE)]

    @requires_idempotency
    def post(self, request, household_id):
        body = HouseholdCreateDependentSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        membership = _domain_operation(
            household_service.create_dependent,
            household=get_object_or_404(FamilyHousehold, id=household_id),
            relationship_code=data["relationshipCode"],
            first_name=data["firstName"],
            last_name=data["lastName"],
            date_of_birth=data["dateOfBirth"],
            sex_code=data["sexCode"],
            external_reference=data["externalReference"],
            attributes=data["attributes"],
            nif=data["nif"],
            joined_at=data["joinedAt"],
        )
        return Response(HouseholdMemberSerializer(membership).data, status=201)


class HouseholdPersonDependentCreateView(APIView):
    """Create a civil person linked to a household, without an insurance enrollment."""

    permission_classes = [require_scope(Scope.WRITE)]

    @requires_idempotency
    def post(self, request, household_id):
        body = HouseholdLinkPersonSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        membership = _domain_operation(
            household_service.create_household_person,
            household=get_object_or_404(FamilyHousehold, id=household_id),
            relationship_code=data["relationshipCode"],
            person_id=data.get("personId"),
            first_name=data.get("firstName"),
            last_name=data.get("lastName"),
            date_of_birth=data.get("dateOfBirth"),
            sex_code=data.get("sexCode"),
            nif=data.get("nif"),
            joined_at=data["joinedAt"],
        )
        return Response(HouseholdMemberSerializer(membership).data, status=201)

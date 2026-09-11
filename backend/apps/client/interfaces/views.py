"""Controllers for the client module. Scopes copied from ART-006's
`security` block per `operationId` — cross-check against
docs/artifacts/ART-006-openapi/. DOC-001 s18 has no permission entries for
this domain (only `product:manage`/`pricing-config:manage` exist), so
these views are gated by OAuth2 scope alone — see
docs/08-integration-contract/BACKEND_FRONTEND_ALIGNMENT.md.
"""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.permissions import require_scope
from apps.client.application import import_service, member_service, proposer_service
from apps.client.infrastructure.models import ImportJob, InsuredMember, Proposer
from apps.client.interfaces.serializers import (
    ImportCommitRequestSerializer,
    ImportJobSerializer,
    MemberCreateRequestSerializer,
    MemberSerializer,
    MemberUpdateRequestSerializer,
    ProposerCreateRequestSerializer,
    ProposerSerializer,
    ProposerUpdateRequestSerializer,
)
from shared.pagination import Q360PageNumberPagination


class ProposerListCreateView(APIView):
    def get_permissions(self):
        scope = Scope.WRITE if self.request.method == "POST" else Scope.READ
        return [require_scope(scope)()]

    def get(self, request):
        paginator = Q360PageNumberPagination()
        page = paginator.paginate_queryset(Proposer.objects.all().order_by("display_name"), request)
        return paginator.get_paginated_response(ProposerSerializer(page, many=True).data)

    def post(self, request):
        body = ProposerCreateRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        proposer = proposer_service.create_proposer(**body.validated_data)
        return Response(ProposerSerializer(proposer).data, status=201)


class ProposerDetailView(APIView):
    def get_permissions(self):
        scope = Scope.WRITE if self.request.method == "PUT" else Scope.READ
        return [require_scope(scope)()]

    def get(self, request, proposer_id):
        proposer = get_object_or_404(Proposer, id=proposer_id)
        return Response(ProposerSerializer(proposer).data)

    def put(self, request, proposer_id):
        proposer = get_object_or_404(Proposer, id=proposer_id)
        body = ProposerUpdateRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        updated = proposer_service.update_proposer(proposer=proposer, **body.validated_data)
        return Response(ProposerSerializer(updated).data)


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
        )
        return Response(MemberSerializer(member).data, status=201)


class MemberDetailView(APIView):
    def get_permissions(self):
        scope = Scope.WRITE if self.request.method == "PUT" else Scope.READ
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
        )
        return Response(MemberSerializer(updated).data)


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

from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.permissions import require_scope
from apps.search.application import work_queue
from shared.status_labels import status_dictionary


class WorkQueueView(APIView):
    """`GET /work-queue` — a fila «Por tratar». Filtros: `kind` e `assignment` (mine, unassigned)."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request):
        kind = request.query_params.get("kind") or None
        assignment = request.query_params.get("assignment") or None
        if kind is not None and kind not in work_queue.KIND_LABELS:
            raise ValidationError({"kind": "Este tipo de tarefa não existe."})
        if assignment not in (None, "mine", "unassigned"):
            raise ValidationError({"assignment": "Use mine ou unassigned."})
        return Response(work_queue.build(actor=request.user.actor, kind=kind, assignment=assignment))


class StatusDictionaryView(APIView):
    """`GET /status-dictionary` — o nome de cada estado, por entidade e pela ordem do ciclo."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request):
        return Response(status_dictionary())

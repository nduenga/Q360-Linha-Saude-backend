from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.permissions import require_scope
from apps.search.application.global_search import global_search


class GlobalSearchView(APIView):
    """GET /search?q= — pesquisa global do back-office: clientes (nome, NIF,
    e-mail, telefone), cotações, produtos e apólices (número), até 5 de cada,
    só do tenant do utilizador. Com menos de 2 caracteres devolve vazio."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request):
        q = request.query_params.get('q', '')
        return Response(global_search(q))

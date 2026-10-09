from rest_framework.permissions import BasePermission
from apps.foundation.domain.permissions import Role

class IsPlatformAdmin(BasePermission):
    message="São necessárias credenciais de administrador da plataforma."
    def has_permission(self, request, view):
        actor=getattr(getattr(request,"user",None),"actor",None)
        return bool(actor and actor.actor_type=="PLATFORM_ADMIN" and actor.tenant_id is None and Role.PLATFORM_ADMIN in actor.roles)

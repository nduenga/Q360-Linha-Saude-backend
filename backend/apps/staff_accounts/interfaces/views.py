"""Public (pre-auth) staff identity endpoints - self-hosted replacement
for the Auth0 Universal Login / password grant the frontend used to call
directly. `apps.foundation.interfaces.authentication.JwtActorAuthentication`
still runs on every OTHER endpoint unchanged; only where the token now
comes from is different (apps.staff_accounts.infrastructure.staff_token).
"""
from __future__ import annotations

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.interfaces.middleware import get_correlation_id
from apps.platform_admin.application import auth_service as platform_auth
from apps.staff_accounts.infrastructure.models import StaffAccount
from apps.staff_accounts.application.auth_service import StaffAccountAuthService
from apps.staff_accounts.interfaces.rate_limit import is_login_rate_limited
from apps.staff_accounts.interfaces.serializers import (
    LoginRequestSerializer,
    LogoutRequestSerializer,
    RefreshRequestSerializer,
    TokenResponseSerializer,
)

_auth_service = StaffAccountAuthService()


def _too_many_requests() -> Response:
    return Response(
        {
            "title": "Limite excedido",
            "status": 429,
            "code": "RATE-LIMIT",
            "detail": "Demasiadas tentativas de início de sessão. Tente de novo mais tarde.",
            "correlationId": get_correlation_id() or "",
        },
        status=429,
        content_type="application/problem+json",
    )


def _token_response(result) -> Response:
    payload = {
        "accessToken": result.access_token,
        "refreshToken": result.refresh_token,
        "expiresIn": result.expires_in,
        "accountId": str(result.account.id),
        "name": result.account.name,
        "email": result.account.email,
        "roles": result.roles,
        "accountType": "STAFF",
    }
    return Response(TokenResponseSerializer(payload).data)


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        body = LoginRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data

        remote_addr = request.META.get("REMOTE_ADDR") or "unknown"
        if is_login_rate_limited(remote_addr=remote_addr, email=data["email"]):
            return _too_many_requests()

        # Um só formulário de login: se o email não pertence a nenhuma conta
        # de staff, tenta-se o super administrador da plataforma (equipa
        # interna). Uma conta de staff com palavra-passe errada nunca cai
        # aqui, por isso nada se revela sobre contas de plataforma.
        if not StaffAccount.all_tenants.filter(email__iexact=data["email"]).exists():
            try:
                token, expires, admin = platform_auth.login(
                    email=data["email"], password=data["password"], correlation_id=get_correlation_id()
                )
            except platform_auth.PlatformAuthenticationError:
                pass  # segue o fluxo normal e devolve o erro habitual de credenciais
            else:
                return Response(
                    TokenResponseSerializer(
                        {
                            "accessToken": token, "refreshToken": "", "expiresIn": expires, "accountId": str(admin.id),
                            "name": admin.name, "email": admin.email, "roles": ["PLATFORM_ADMIN"],
                            "accountType": "PLATFORM",
                        }
                    ).data
                )

        result = _auth_service.login(
            email=data["email"], password=data["password"], correlation_id=get_correlation_id()
        )
        return _token_response(result)


class RefreshView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        body = RefreshRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        result = _auth_service.refresh(
            refresh_token=body.validated_data["refreshToken"], correlation_id=get_correlation_id()
        )
        return _token_response(result)


class LogoutView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        body = LogoutRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        _auth_service.logout(refresh_token=body.validated_data["refreshToken"])
        return Response(status=204)

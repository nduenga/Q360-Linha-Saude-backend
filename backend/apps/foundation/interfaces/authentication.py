"""DRF authentication backed by JwtActorAdapter (Q360-S1-03).

Binds `CurrentActorProvider`/`CurrentTenantProvider` for the remainder of
the request as soon as the token is validated, and exposes the resolved
`Actor` as `request.user.actor` for views/permission classes.

`request.user` is intentionally NOT a stored Django user: ART-005 (the
canonical MVP schema) has no `user`/`role`/`permission` table. V1 identity
is federated via OIDC — DOC-004 s6.1 `JwtActorAdapter` maps JWT claims
directly to an `Actor`, with no local profile lookup.
"""
from __future__ import annotations

from django.contrib.auth.models import AnonymousUser
from rest_framework import authentication, exceptions

from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.actor import Actor
from apps.foundation.infrastructure.jwt_actor_adapter import InvalidTokenError, JwtActorAdapter

_adapter = JwtActorAdapter()


class ActorUser(AnonymousUser):
    """Adapts `Actor` to the `request.user` duck-type DRF/Django expect."""

    def __init__(self, actor: Actor) -> None:
        super().__init__()
        self.actor = actor

    @property
    def is_authenticated(self) -> bool:
        return True


class JwtActorAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).decode("utf-8")
        if not header or not header.lower().startswith(f"{self.keyword.lower()} "):
            return None
        token = header[len(self.keyword) + 1 :].strip()
        if not token:
            return None

        try:
            actor = _adapter.resolve(token)
        except InvalidTokenError as exc:
            raise exceptions.AuthenticationFailed(str(exc)) from exc

        CurrentActorProvider.bind(actor)
        return ActorUser(actor), token

    def authenticate_header(self, request):
        return self.keyword

"""Integridade da superfície da API: nenhuma rota protegida responde sem
autenticação, e nenhuma rota devolve erro de servidor (5xx) a pedidos
inválidos ou a identificadores inexistentes. Cobre todas as rotas, incluindo
as do simulador GTE, das apólices, da sinistralidade e do portal do cliente."""
from __future__ import annotations

import re
import uuid

import pytest
from django.urls import get_resolver
from rest_framework.test import APIClient

from tests.integration.test_tenant_isolation import _make_tenant, _oidc_static_key, make_client  # noqa: F401

METHODS = ("get", "post", "put", "patch", "delete")
PUBLIC = {
    "api/v1/health/live", "api/v1/health/ready", "api/v1/auth/login", "api/v1/auth/refresh", "api/v1/auth/logout",
    "api/v1/auth/dev-login", "api/v1/schema",
}
PORTAL_PUBLIC_SUFFIXES = ("/auth/request-access", "/auth/verify-otp")


def _routes():
    def walk(patterns, prefix=""):
        for p in patterns:
            if hasattr(p, "url_patterns"):
                yield from walk(p.url_patterns, prefix + str(p.pattern))
            else:
                yield prefix + str(p.pattern), p.callback

    for route, callback in walk(get_resolver().url_patterns):
        view = getattr(callback, "cls", None)
        if route.startswith("api/v1/") and view is not None:
            yield route, view


def _concrete(route: str) -> str:
    def fill(match: re.Match) -> str:
        kind = match.group(1) or "str"
        return {"uuid": str(uuid.uuid4()), "int": "1"}.get(kind, "x")

    return "/" + re.sub(r"<(?:(\w+):)?\w+>", fill, route)


def _is_public(route: str) -> bool:
    return route.rstrip("/") in PUBLIC or any(route.rstrip("/").endswith(s) for s in PORTAL_PUBLIC_SUFFIXES)


def _call(client: APIClient, method: str, url: str):
    return getattr(client, method)(url, {}, format="json") if method != "get" else client.get(url)


def test_the_api_has_the_expected_surface():
    routes = list(_routes())
    methods = sum(1 for _, view in routes for m in METHODS if hasattr(view, m))
    assert len(routes) >= 130 and methods >= 170


def test_every_protected_route_rejects_anonymous_calls(db):
    anonymous = APIClient()
    leaked = []
    for route, view in _routes():
        if _is_public(route):
            continue
        for method in (m for m in METHODS if hasattr(view, m)):
            response = _call(anonymous, method, _concrete(route))
            if response.status_code not in (401, 403):
                leaked.append((method.upper(), route, response.status_code))
    assert leaked == []


def test_no_route_returns_a_server_error_for_an_authenticated_admin(db):
    tenant = _make_tenant(suffix="surface")
    admin = make_client(tenant_id=tenant.id, roles=["ADMIN"], scope="q360.read q360.write q360.admin q360.approve q360.audit")
    failures = []
    for route, view in _routes():
        if _is_public(route) or "customer-portal" in route:
            continue
        for method in (m for m in METHODS if hasattr(view, m)):
            response = _call(admin, method, _concrete(route))
            if response.status_code >= 500:
                failures.append((method.upper(), route, response.status_code))
    assert failures == []


def test_portal_routes_need_a_portal_session_and_reject_staff_tokens(db):
    tenant = _make_tenant(suffix="portal-surface")
    staff = make_client(tenant_id=tenant.id, roles=["ADMIN"], scope="q360.read q360.write q360.admin q360.approve q360.audit")
    rejected = []
    for route, view in _routes():
        if "customer-portal" not in route or _is_public(route):
            continue
        for method in (m for m in METHODS if hasattr(view, m)):
            response = _call(staff, method, _concrete(route))
            if response.status_code not in (401, 403):
                rejected.append((method.upper(), route, response.status_code))
    assert rejected == []

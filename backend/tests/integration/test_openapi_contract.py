"""O contrato OpenAPI (ART-006 v1.4.0) descreve exactamente a API: todas as
rotas e métodos, pedido, respostas, segurança e referências — e os ficheiros
estão em dia com o código (`manage.py build_openapi`)."""
from __future__ import annotations

import re

import pytest
import yaml
from django.urls import get_resolver

from config.openapi import build

METHODS = ("get", "post", "put", "patch", "delete")
PUBLIC = {
    "/api/v1/health/live", "/api/v1/health/ready", "/api/v1/auth/login", "/api/v1/auth/refresh", "/api/v1/auth/logout",
    "/api/v1/auth/dev-login", "/api/v1/schema",
    "/api/v1/customer-portal/{tenant_id}/auth/request-access", "/api/v1/customer-portal/{tenant_id}/auth/verify-otp",
    "/api/v1/customer-portal/{tenant_id}/auth/login",
    "/api/v1/customer-portal/{tenant_id}/auth/first-access/request",
    "/api/v1/customer-portal/{tenant_id}/auth/first-access/confirm",
    "/api/v1/customer-portal/{tenant_id}/auth/password-reset/request",
    "/api/v1/customer-portal/{tenant_id}/auth/password-reset/confirm",
}
BODYLESS_POST = re.compile(r"/(approve|publish|retire|select|recalculate|retry|signed-url|proposal|reset-password|logout|market)$")


def _routes():
    def walk(patterns, prefix=""):
        for p in patterns:
            if hasattr(p, "url_patterns"):
                yield from walk(p.url_patterns, prefix + str(p.pattern))
            else:
                yield prefix + str(p.pattern), p.callback

    for route, callback in walk(get_resolver().url_patterns):
        if not route.startswith("api/v1/"):
            continue
        view = getattr(callback, "cls", None)
        if view is None:
            continue
        path = "/" + re.sub(r"<(?:\w+:)?(\w+)>", r"{\1}", route).rstrip("/")
        if path == "/api/v1/schema":  # the generator's own endpoint is not part of the contract
            continue
        for method in METHODS:
            if hasattr(view, method):
                yield path, method, view


@pytest.fixture(scope="module")
def contract():
    return yaml.safe_load(build.CONTRACT.read_text(encoding="utf-8"))


def test_every_route_and_method_is_in_the_contract(contract):
    missing = [(p, m) for p, m, _ in _routes() if m not in contract["paths"].get(p, {})]
    assert missing == []


def test_the_contract_has_no_operation_the_api_does_not_have(contract):
    implemented = {(p, m) for p, m, _ in _routes()}
    documented = {(p, m) for p, item in contract["paths"].items() for m in item if m in METHODS}
    assert documented - implemented == set()


def test_every_operation_is_fully_described(contract):
    problems = []
    for path, item in contract["paths"].items():
        for method in (m for m in item if m in METHODS):
            op = item[method]
            where = f"{method.upper()} {path}"
            if not op.get("operationId"):
                problems.append(f"{where}: sem operationId")
            if not op.get("summary"):
                problems.append(f"{where}: sem summary")
            if not op.get("tags"):
                problems.append(f"{where}: sem tags")
            codes = [str(c) for c in op.get("responses", {})]
            if not any(c.startswith("2") for c in codes):
                problems.append(f"{where}: sem resposta de sucesso")
            if path not in PUBLIC and "security" not in op and (path, method) not in {
                ("/api/v1/me", "get"), ("/api/v1/dashboard", "get"), ("/api/v1/customer-portal/me", "get"),
                ("/api/v1/customer-portal/eligibility", "post"),
            }:
                # operations kept from the approved contract inherit the global security
                if "security" not in contract:
                    problems.append(f"{where}: sem security")
            for name in re.findall(r"\{(\w+)\}", path):
                declared = [p for p in op.get("parameters", []) + item.get("parameters", []) if p.get("name") == name and p.get("in") == "path"]
                if not declared:
                    problems.append(f"{where}: parâmetro de caminho {name} não documentado")
            if method in ("post", "put", "patch") and "requestBody" not in op and not BODYLESS_POST.search(path):
                problems.append(f"{where}: sem requestBody")
    assert problems == []


def test_every_reference_resolves(contract):
    schemas = set(contract["components"]["schemas"])
    refs: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "$ref" and isinstance(value, str):
                    refs.add(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(contract)
    unresolved = sorted(r for r in refs if r.startswith("#/components/schemas/") and r.rsplit("/", 1)[1] not in schemas)
    assert unresolved == []


def test_error_responses_use_problem_json_and_cover_the_catalog(contract):
    op = contract["paths"]["/api/v1/quotes/{quote_id}/adjustments"]["post"]
    assert "application/problem+json" in op["responses"]["400"]["content"]
    assert op["responses"]["409"]["description"].startswith("Conflito")
    schema = contract["components"]["schemas"]["ProblemDetail"]
    assert {"title", "status", "code", "correlationId", "fieldErrors"} <= set(schema["properties"])


def test_key_operations_document_their_bodies_and_rules(contract):
    paths = contract["paths"]
    adjust = paths["/api/v1/quotes/{quote_id}/adjustments"]["post"]
    assert {p["name"] for p in adjust["parameters"]} >= {"dryRun", "Idempotency-Key", "quote_id"}
    assert adjust["security"] == [{"oauth2": ["q360.write"]}]
    assert "quote:calculate" in adjust["description"]
    assert paths["/api/v1/claims/imports"]["post"]["requestBody"]["content"]["multipart/form-data"]
    assert {p["name"] for p in paths["/api/v1/claims/summary"]["get"]["parameters"] if p.get("required")} == {"proposerId"}
    assert "customerPortalBearer" in str(paths["/api/v1/customer-portal/plan-benefits"]["get"]["security"])
    assert paths["/api/v1/health/live"]["get"].get("security", []) == []
    coverage = {p["name"] for p in paths["/api/v1/policies/{policy_id}/coverage"]["get"]["parameters"]}
    assert {"memberId", "date", "benefitCategory", "eventType"} <= coverage


def test_contract_files_are_up_to_date_with_the_code():
    generated, merged = build.build(write=False)
    assert build.GENERATED.read_text(encoding="utf-8") == generated, "run `manage.py build_openapi`"
    assert build.CONTRACT.read_text(encoding="utf-8") == merged, "run `manage.py build_openapi`"

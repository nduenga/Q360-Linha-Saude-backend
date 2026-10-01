"""Static analysis of DRF views to recover what each HTTP method accepts and
returns, so the OpenAPI contract is generated from the code instead of being
typed by hand: request serializer (`Serializer(data=request.data)`), response
serializers (`Serializer(obj).data`, `many=True`, paginated), success status
(`Response(..., status=N)`), query parameters (`request.query_params.get`) and
whether the view is paginated. Anything the analysis cannot see (a `Response`
built from a plain dict) is described in `extras.py`."""
from __future__ import annotations

import ast
import inspect
import sys
import textwrap
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MethodInfo:
    request: type | None = None
    request_many: bool = False
    responses: list[tuple[type, bool]] = field(default_factory=list)  # (serializer, many)
    status: int | None = None
    queries: list[str] = field(default_factory=list)
    paginated: bool = False
    file_response: bool = False
    returns_dict: bool = False
    statuses: set[int] = field(default_factory=set)


def _name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def analyse(view_cls: type, method: str) -> MethodInfo:
    info = MethodInfo()
    func = getattr(view_cls, method, None)
    if func is None:
        return info
    try:
        source = textwrap.dedent(inspect.getsource(func))
    except (OSError, TypeError):
        return info
    module = sys.modules[func.__module__]
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = _name(node.func)
        if callee and callee.endswith("Serializer"):
            serializer = getattr(module, callee, None)
            if serializer is None:
                continue
            kwargs = {k.arg: k.value for k in node.keywords if k.arg}
            many = isinstance(kwargs.get("many"), ast.Constant) and kwargs["many"].value is True
            if "data" in kwargs:
                if info.request is None:
                    info.request = serializer
                    info.request_many = many
            elif (serializer, many) not in info.responses:
                info.responses.append((serializer, many))
        elif callee == "Response":
            for kw in node.keywords:
                if kw.arg == "status" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, int):
                    info.statuses.add(kw.value.value)
            if node.args and isinstance(node.args[0], (ast.Dict,)):
                info.returns_dict = True
            elif node.args and not any(
                isinstance(sub, ast.Call) and (_name(sub.func) or "").endswith("Serializer") for sub in ast.walk(node.args[0])
            ):
                info.returns_dict = True
        elif callee == "HttpResponse":
            info.file_response = True
        elif callee in ("get", "getlist") and isinstance(node.func, ast.Attribute):
            base = node.func.value
            if isinstance(base, ast.Attribute) and base.attr == "query_params" and node.args and isinstance(node.args[0], ast.Constant):
                if node.args[0].value not in info.queries:
                    info.queries.append(node.args[0].value)
        elif callee in ("paginate_queryset", "get_paginated_response"):
            info.paginated = True
    success = [code for code in info.statuses if code < 400]
    if success:
        info.status = min(success)
    return info

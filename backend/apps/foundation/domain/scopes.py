"""OAuth2 scopes — Q360-MVP-ART-006 `components.securitySchemes.oauth2.flows
.authorizationCode.scopes`, verbatim.

This is a coarse-grained, HTTP-contract-level authorization layer, separate
from and in addition to the fine-grained business RBAC in
`domain/permissions.py` (DOC-001 s18). ART-006 attaches one of these scopes
to every operation's `security` block (e.g. GET operations require
`q360.read`, mutations require `q360.write`, configuration endpoints
require `q360.admin`) — both layers must be enforced; neither substitutes
for the other.

Do not add a scope here that is not listed in ART-006's securitySchemes.
"""
from __future__ import annotations

from enum import Enum


class Scope(str, Enum):
    READ = "q360.read"
    WRITE = "q360.write"
    APPROVE = "q360.approve"
    ADMIN = "q360.admin"
    AUDIT = "q360.audit"

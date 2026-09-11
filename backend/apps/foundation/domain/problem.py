"""Base for domain exceptions that must reach the client as a specific
ART-006 `ProblemDetail` (HTTP status + `x-q360-error-catalog` code) rather
than a generic 500.

Every business module's `domain/errors.py` (product, and later client,
eligibility, pricing, quotation, underwriting, documents) subclasses this
instead of foundation importing each module's exceptions — DOC-004 s3.1
forbids foundation depending on a business module. Framework-free by
design (plain Python, two class attributes): the mapping to an actual HTTP
`Response` happens once, generically, in
`apps.foundation.interfaces.exception_handler`.
"""
from __future__ import annotations


class DomainProblem(Exception):
    http_status: int
    problem_code: str

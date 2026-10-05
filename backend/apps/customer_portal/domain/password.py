"""Regras puras da palavra-passe do Portal Cliente e máscara do email.

Sem regras de composição (maiúsculas, símbolos): o que protege é o
comprimento e não ser uma palavra-passe previsível. Sem Django aqui, tal
como `lockout.py`.
"""
from __future__ import annotations

from apps.foundation.domain.problem import DomainProblem

MIN_LENGTH = 10
MAX_LENGTH = 128

# Palavras-passe que continuam a ser as mais usadas mesmo com 10+ caracteres.
_COMMON = frozenset(
    {
        "1234567890", "0123456789", "12345678910", "123456789012", "qwertyuiop", "qwerty1234", "qwerty12345",
        "password12", "password123", "password1234", "passw0rd123", "palavrapasse", "palavra-passe", "senha12345",
        "senha123456", "q360seguros", "q360saude123", "angola2026", "luanda12345", "iloveyou123", "abcdefghij",
        "abc1234567", "1q2w3e4r5t", "0000000000", "1111111111", "aaaaaaaaaa",
    }
)


class PortalPasswordInvalidError(DomainProblem):
    http_status = 400
    problem_code = "VALIDATION-400"


def validate_password_strength(password: str, *, email: str | None = None) -> None:
    if len(password) < MIN_LENGTH:
        raise PortalPasswordInvalidError(f"A palavra-passe deve ter pelo menos {MIN_LENGTH} caracteres.")
    if len(password) > MAX_LENGTH:
        raise PortalPasswordInvalidError(f"A palavra-passe deve ter no máximo {MAX_LENGTH} caracteres.")
    lowered = password.lower()
    if lowered in _COMMON or len(set(lowered)) <= 2:
        raise PortalPasswordInvalidError("Essa palavra-passe é demasiado comum. Escolha outra.")
    if lowered.isdigit() and _is_sequence(lowered):
        raise PortalPasswordInvalidError("Essa palavra-passe é demasiado previsível. Escolha outra.")
    if email:
        local = email.split("@", 1)[0].lower()
        if len(local) >= 4 and local in lowered:
            raise PortalPasswordInvalidError("A palavra-passe não pode conter o seu email.")


def _is_sequence(digits: str) -> bool:
    steps = {int(b) - int(a) for a, b in zip(digits, digits[1:])}
    return steps <= {1} or steps <= {-1}


def mask_email(email: str) -> str:
    """`joao.silva@gmail.com` -> `jo***@gmail.com`."""
    local, _, domain = email.partition("@")
    visible = local[:2] if len(local) > 2 else local[:1]
    return f"{visible}***@{domain}"

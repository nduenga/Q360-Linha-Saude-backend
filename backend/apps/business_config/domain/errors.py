from apps.foundation.domain.problem import DomainProblem


class ConfigurationStateError(DomainProblem):
    http_status = 409
    problem_code = "CONFLICT"


class ConfigurationVersionConflict(DomainProblem):
    http_status = 409
    problem_code = "VERSION-CONFLICT"


class FourEyesViolation(DomainProblem):
    http_status = 403
    problem_code = "SEC-403"


class InvalidConfiguration(DomainProblem):
    http_status = 400
    problem_code = "VALIDATION-400"


class RoleNotAllowed(DomainProblem):
    http_status = 403
    problem_code = "SEC-403"


class ProductSetupInputError(DomainProblem):
    """As opções/campos da cotação não batem com a configuração do produto
    (opção inexistente, campo obrigatório em falta, sem valor para a escolha)."""

    http_status = 422
    problem_code = "PRODUCT-SETUP-INPUT"

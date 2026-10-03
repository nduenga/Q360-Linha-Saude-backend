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

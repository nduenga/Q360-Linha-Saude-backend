from apps.foundation.domain.problem import DomainProblem


class PlatformNotFoundError(DomainProblem):
    http_status = 404
    problem_code = "NOT-FOUND"


class PlatformConflictError(DomainProblem):
    http_status = 409
    problem_code = "CONFLICT"


class PlatformRuleError(DomainProblem):
    http_status = 400
    problem_code = "VALIDATION-400"

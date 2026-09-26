"""Named use cases from DOC-004 s7 that protect a real invariant — everyday
CRUD lives in product_service.py / pricing_parameter_service.py instead.

`PublishProductVersionUseCase` was retired here
(DECISIONS_TAKEN.md#S09-POLICY-001, PO-APO-6, 2026-09-26): there is no more
ProductVersion to publish. The invariant it protected (a version cannot
publish while missing a mandatory BASE coverage) was already unreachable
in practice — `benefit_service.attach_core_benefits` attaches all 3 BASE
coverages unconditionally at Plan creation, and `remove_plan_benefit`
refuses to ever detach one — so no functional protection is lost by
removing the extra publish-time check along with the version concept it
was attached to.
"""
from __future__ import annotations

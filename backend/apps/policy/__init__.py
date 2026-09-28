"""Policy module (DECISIONS_TAKEN.md#S09-POLICY-001, ROADMAP_APOLICES.md
Fase 2+): the contract between the tomador (Proposer) and the seguradora,
created only when the tomador signs — never on Quote approval alone
(PO-APO-1). Depends on `apps.foundation` (tenant/audit/rules) and reads
`apps.quote` (Quote, QuoteSnapshot), `apps.client` (Proposer,
InsuredMember), `apps.product` (Plan) and `apps.eligibility`
(EligibilityEvaluation, RuleVersion) — same cross-module read pattern as
apps.quote itself (OPEN_DECISIONS.md#S04-CROSS-MODULE-001).
"""

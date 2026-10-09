from __future__ import annotations

from datetime import datetime, timezone as dt_tz
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import SimpleNamespace

from django.core.management.base import BaseCommand, CommandError

from apps.business_config.application.pricing import resolve_actuarial_coverage_premiums
from apps.business_config.application.service import (
    approve_configuration,
    create_configuration,
    submit_configuration,
)
from apps.business_config.infrastructure.models import BusinessConfiguration
from apps.business_config.seed.actuarial_model import build_actuarial_model
from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.tenant import TenantId
from apps.foundation.infrastructure.models import AuditEvent, Tenant


CREATOR_SUBJECT = "system:seed-default-pricing"
APPROVER_SUBJECT = "system:actuarial-approver"
APPROVER_EMAIL = "actuarial.approver@q360-saude.local"


class Command(BaseCommand):
    help = (
        "Valida o modelo actuarial SAU/SAG (94 células) e publica-o como "
        "BusinessConfiguration PUBLISHED do tenant atual (4-eyes bypass via "
        "actor especial approver, auditado como ACTUARIAL_MODEL_CLI_PUBLISHED). "
        "NÃO usar diretamente em produção sem validação do actuário responsável."
    )

    def add_arguments(self, parser):
        parser.add_argument("--tenant-code", default="dev-tenant")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Publica mesmo que já exista uma versão PUBLISHED (cria v2+).",
        )
        parser.add_argument(
            "--validate-only",
            action="store_true",
            help="Apenas corre a validação das 94 células sem publicar nada.",
        )
        parser.add_argument(
            "--effective-from",
            type=str,
            default=None,
            help="Data de vigência ISO (YYYY-MM-DD). Default: hoje em UTC.",
        )
        parser.add_argument(
            "--rebuild-from-workbook",
            action="store_true",
            help="Reimporta o ficheiro Excel mesmo que já exista em base de dados.",
        )
        parser.add_argument(
            "--acceptance-tolerance-bp",
            type=int,
            default=1,
            help="Tolerância máxima de diferença por célula em base points (1=0.01%). Default: 1.",
        )

    def handle(self, *args, **options):
        tolerance = Decimal(str(options["acceptance_tolerance_bp"])) / Decimal("10000")
        rebuild = bool(options["rebuild_from_workbook"])
        validate_only = bool(options["validate_only"])
        force = bool(options["force"])
        effective_from_str = options.get("effective_from")
        if effective_from_str:
            effective_from = datetime.strptime(effective_from_str, "%Y-%m-%d").date()
        else:
            effective_from = datetime.now(dt_tz.utc).date()

        try:
            tenant = Tenant.objects.get(code=options["tenant_code"])
        except Tenant.DoesNotExist as exc:
            raise CommandError(
                f"Não existe nenhum tenant com o código '{options['tenant_code']}'. Execute primeiro `manage.py seed_dev_tenant --code {options['tenant_code']}`."
            ) from exc

        tenant_id = TenantId.parse(tenant.id)
        creator = Actor(
            actor_id=CREATOR_SUBJECT,
            tenant_id=tenant_id,
            roles=frozenset(),
            scopes=frozenset(),
            actor_type="SYSTEM",
        )
        approver = Actor(
            actor_id=APPROVER_SUBJECT,
            tenant_id=tenant_id,
            roles=frozenset(),
            scopes=frozenset(),
            actor_type="SYSTEM",
        )

        creator_token = CurrentActorProvider.bind(creator)
        try:
            workbook_path = Path(build_actuarial_model.__code__.co_filename).parent / "Modelo_Actuarial_Saude_SAU_SAG_Angola.xlsx"
            if not workbook_path.exists():
                self.stdout.write(f"1. Importar modelo actuarial do ficheiro Excel...")
            else:
                self.stdout.write(self.style.WARNING(
                    f"Ficheiro workbook não encontrado em {workbook_path}. "
                    "A usar build_actuarial_model() vai gerar modelo em memória sem source_cell."
                ))

            model = build_actuarial_model()
            self.stdout.write(self.style.SUCCESS(
                f"OK — {len(model['reference_pure_premiums'])} prémios puros importados. "
                f"Moeda: {model['currency_code']}. Assumptions USD/AOA: {model['assumptions']['usd_to_aoa']}"
            ))

            self.stdout.write("\n2. Validar 94 células (LEV recalculado vs Excel cache)...")
            total = len(model["reference_pure_premiums"])
            passed = 0
            deviations: list[tuple[str, Decimal, Decimal, Decimal]] = []
            for idx, rate in enumerate(model["reference_pure_premiums"], start=1):
                segment = str(rate["segment"])
                plan = str(rate["plan"])
                actuarial_code = str(rate["coverage_code"])
                benefit_code = None
                for bc, acs in model["coverage_code_mapping"].items():
                    if actuarial_code in acs:
                        benefit_code = bc
                        break
                if benefit_code is None:
                    continue
                validation_sex = "F" if actuarial_code == "MAT" else "M"
                try:
                    result = resolve_actuarial_coverage_premiums(
                        model=model,
                        plan_code=self._plan_code(segment, plan),
                        coverages=[{"code": benefit_code, "contracted": True}],
                        age=30,
                        sex_code=validation_sex,
                    )
                    matched = next((r for r in result if r["code"] == actuarial_code), None)
                    if matched is None:
                        continue
                    excel_ref = Decimal(str(rate["annual_pure_premium"]))
                    calc = matched["pure_premium"]
                    if excel_ref > 0:
                        diff_pct = (calc - excel_ref) / excel_ref
                    else:
                        diff_pct = Decimal("0")
                    if abs(diff_pct) <= tolerance:
                        passed += 1
                    else:
                        deviations.append((rate.get("source_cell", actuarial_code), excel_ref, calc, diff_pct * Decimal("100")))
                except Exception as exc:
                    deviations.append((rate.get("source_cell", actuarial_code), Decimal("NaN"), Decimal("NaN"), Decimal("NaN")))
                    self.stderr.write(f"  ! Exceção em célula {rate.get('source_cell')}: {exc}")

            self.stdout.write(self.style.SUCCESS(f"Passaram {passed}/{total} (tolerância {float(tolerance)*100}%)."))
            if deviations:
                self.stderr.write(f"Desvios em {len(deviations)} células:")
                for src, exp, got, pct in deviations[:15]:
                    self.stderr.write(f"  - {src}: expected {exp}, got {got} ({pct}%)")
                if len(deviations) > 15:
                    self.stderr.write(f"  ... +{len(deviations)-15} mais.")
            if passed != total:
                self.stderr.write("\nValidação actuarial falhou. NÃO será publicada.")
                raise SystemExit(3)

            if validate_only:
                self.stdout.write("\n--validate-only definido. Saiu sem publicar.")
                return

            self.stdout.write(f"\n3. Publicar modelo no tenant {tenant.code}...")
            existing_published = BusinessConfiguration.objects.filter(
                tenant_id=tenant.id,
                config_key="pricing.actuarial_model",
                status="PUBLISHED",
            ).first()
            if existing_published and not force:
                self.stdout.write(
                    self.style.WARNING(
                        f"Já existe uma versão PUBLISHED (v{existing_published.version_no}) "
                        "para pricing.actuarial_model. Volte a lançar com --force para publicar uma nova "
                        "versão, ou --validate-only só para rever."
                    )
                )
                raise SystemExit(1)

            existing_draft = BusinessConfiguration.objects.filter(
                tenant_id=tenant.id,
                config_key="pricing.actuarial_model",
                status__in={"DRAFT", "PENDING_APPROVAL"},
            ).order_by("-created_at").first()
            if rebuild or existing_draft is None:
                create_req = SimpleNamespace()
                config = create_configuration(
                    create_req,
                    config_key="pricing.actuarial_model",
                    value=model,
                    effective_from=effective_from,
                    effective_to=None,
                    metadata={
                        "source": str(workbook_path.name),
                        "scope": "actuarial-model-publish-cli",
                        "requiresActuarialApproval": True,
                        "publishedByCli": True,
                        "validationCells": f"{passed}/{total}",
                    },
                )
            else:
                config = existing_draft
                config.value_json = model
                config.effective_from = effective_from
                config.save()

            submit_request = SimpleNamespace()
            submit_configuration(submit_request, config)

            CurrentActorProvider.reset(creator_token)
            approver_token = CurrentActorProvider.bind(approver)
            approval_request = SimpleNamespace()
            final = approve_configuration(approval_request, config)
            CurrentActorProvider.reset(approver_token)
            creator_token = CurrentActorProvider.bind(creator)

            try:
                AuditEvent.all_tenants.create(
                    tenant_id=tenant.id,
                    actor_id=APPROVER_SUBJECT,
                    actor_type="SYSTEM",
                    action="ACTUARIAL_MODEL_CLI_PUBLISHED",
                    entity_type="BUSINESS_CONFIGURATION",
                    entity_id=str(final.id),
                    source="cli:publish_actuarial_model",
                    metadata_json={
                        "validationCells": f"{passed}/{total}",
                        "toleranceBp": options["acceptance_tolerance_bp"],
                        "effectiveFrom": final.effective_from.isoformat(),
                        "creator": CREATOR_SUBJECT,
                        "approver": APPROVER_SUBJECT,
                        "workbookFile": workbook_path.name,
                    },
                    created_at=datetime.now(dt_tz.utc),
                )
            except Exception:
                pass  # auditoria falhou não deve bloquear publicação

            self.stdout.write(self.style.SUCCESS(
                f"\nModelo actuarial publicado com sucesso — PricingConfiguration v{final.version_no}.\n"
                f"  Tenant: {tenant.code} ({tenant.id})\n"
                f"  ID: {final.id}\n"
                f"  effective_from: {final.effective_from.isoformat()}\n"
                f"  checksum SHA-256: {final.checksum}\n"
                f"  validação: {passed}/{total} células (±{float(tolerance)*100}%)\n"
                "\nJá é possível usar o modelo em pricing e simulações. Para confirmar:\n"
                "   python manage.py build_openapi --check\n"
                "   pytest tests/test_actuarial_model_seed.py tests/pricing/ -xq\n"
            ))
        finally:
            CurrentActorProvider.reset(creator_token)

    # ─────── helpers ────────────────────────────────────────────────────────
    @staticmethod
    def _plan_code(segment: str, actuarial_plan: str) -> str:
        mapping = {
            ("SAU", "Base"): "IND-BASE",
            ("SAU", "Conforto"): "IND-MEDIO",
            ("SAU", "Premium"): "IND-SUPERIOR",
            ("SAG", "Colaboradores"): "GRP-COLABORADORES",
            ("SAG", "Quadros Médios"): "GRP-QUADROS",
            ("SAG", "Administração"): "GRP-ADMINISTRACAO",
        }
        try:
            return mapping[(segment, actuarial_plan)]
        except KeyError as exc:
            raise InvalidOperation(f"Par (segment={segment}, plano={actuarial_plan}) desconhecido") from exc

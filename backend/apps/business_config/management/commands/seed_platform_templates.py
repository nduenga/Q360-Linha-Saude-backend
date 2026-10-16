"""`manage.py seed_platform_templates`

Carrega na camada do fornecedor os modelos de partida que hoje vivem no
código: a configuração de referência de Angola (planos, coberturas, regras,
documentos — `seed/reference_rules.py`, com os produtos de mercado do PDF) e
o modelo actuarial SAU/SAG (Excel). Idempotente: só cria um modelo que ainda
não exista. A versão 1 entra publicada, registada como carga inicial do
sistema (proposta e aprovação com identidades distintas de sistema); as
versões seguintes seguem o ciclo normal de duas contas."""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.business_config.application.platform_templates import validate_content
from apps.business_config.seed.actuarial_model import build_actuarial_model
from apps.business_config.seed.reference_rules import CUSTOM_RULES, STATIC_CONFIGS
from apps.foundation.infrastructure.models import PlatformTemplateVersion

SEED_AUTHOR = "system:seed"
SEED_APPROVER = "system:seed-approval"


def templates() -> list[dict]:
    return [
        {
            "code": "saude-angola-referencia",
            "kind": "PRODUCT",
            "name": "Saúde Angola — configuração de referência (SAU e SAG)",
            "description": "Planos, coberturas, rede, regras de aceitação e de preço e documentos de referência, "
                           "e os produtos de mercado do PDF «Coberturas e Capitais». Valores indicativos.",
            "segment": None,
            "content": {"configurations": {**STATIC_CONFIGS, "rules.custom": CUSTOM_RULES}, "marketProducts": True},
            "source": "Modelo_Actuarial_Saude_SAU_SAG_Angola.xlsx; source_configuration_seed.json; PDF «Coberturas e Capitais»",
        },
        {
            "code": "modelo-actuarial-sau-sag",
            "kind": "ACTUARIAL_MODEL",
            "name": "Modelo actuarial SAU/SAG de referência",
            "description": "Prémio puro por cobertura, idade e sexo, fatores e carregamentos do Excel actuarial "
                           "(rascunho por validar pelo actuário).",
            "segment": None,
            "content": {"configurations": {"pricing.actuarial_model": build_actuarial_model()}},
            "source": "Modelo_Actuarial_Saude_SAU_SAG_Angola.xlsx",
        },
    ]


class Command(BaseCommand):
    help = "Carrega os modelos de partida iniciais do fornecedor (idempotente)."

    def handle(self, *args, **options):
        for tpl in templates():
            if PlatformTemplateVersion.objects.filter(code=tpl["code"]).exists():
                self.stdout.write(f"= {tpl['code']}: já existe")
                continue
            content = validate_content(tpl["kind"], tpl["content"])
            PlatformTemplateVersion.objects.create(
                code=tpl["code"], version_no=1, status=PlatformTemplateVersion.PUBLISHED, kind=tpl["kind"],
                name=tpl["name"], description=tpl["description"], segment=tpl["segment"], content_json=content,
                source=tpl["source"], reason="Carga inicial dos modelos que estavam no código (seed_platform_templates).",
                created_by=SEED_AUTHOR, decided_by=SEED_APPROVER, decided_at=timezone.now(),
                decision_note="Carga inicial do sistema.",
            )
            self.stdout.write(f"+ {tpl['code']}: publicado (v1)")

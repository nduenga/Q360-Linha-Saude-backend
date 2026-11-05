"""Tarefas diárias da plataforma, num único comando para o agendador.

Corre por esta ordem: expirar cotações e propostas de endosso, marcar
prestações vencidas e resolver apólices por falta de pagamento, fechar
renovações e expirar apólices. Cada tarefa é idempotente. Se uma falhar, as
seguintes correm na mesma e o comando termina com erro, para o agendador
(systemd ou Render) assinalar a falha.
"""
from __future__ import annotations

import logging

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)

DAILY_JOBS = (
    "expire_quotes",
    "expire_endorsement_offers",
    "premium_overdue_scan",
    "close_renewed_policies",
    "expire_policies",
)


class Command(BaseCommand):
    help = "Corre as tarefas diárias (uma vez por dia, no agendador do servidor)."

    def handle(self, *args, **options):
        failed = []
        for job in DAILY_JOBS:
            self.stdout.write(f"-> {job}")
            try:
                call_command(job, stdout=self.stdout, stderr=self.stderr)
            except Exception:  # noqa: BLE001 - uma tarefa falhada não pode impedir as seguintes
                logger.exception("A tarefa diária %s falhou", job)
                failed.append(job)
        if failed:
            raise CommandError(f"Tarefas diárias com falha: {', '.join(failed)}")
        self.stdout.write(self.style.SUCCESS("Tarefas diárias concluídas."))

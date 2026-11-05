"""Comprova a ligação ao servidor de email e, com --to, envia uma mensagem real.

Sem --to apenas abre a sessão e autentica, sem enviar nada. Com --to, a
mensagem só prova a entrega depois de confirmada na caixa de entrada.
"""
from __future__ import annotations

from django.conf import settings
from django.core.mail import get_connection, send_mail
from django.core.management.base import BaseCommand, CommandError

from apps.customer_portal.application.email_config import email_config_problems


class Command(BaseCommand):
    help = "Verifica a configuração de email; com --to envia uma mensagem de teste."

    def add_arguments(self, parser):
        parser.add_argument("--to", help="Endereço que recebe a mensagem de teste.")

    def handle(self, *args, **options):
        self.stdout.write(f"Serviço:   {settings.EMAIL_BACKEND}")
        self.stdout.write(f"Servidor:  {settings.EMAIL_HOST or '(vazio)'}:{settings.EMAIL_PORT}")
        self.stdout.write(f"Remetente: {settings.CUSTOMER_PORTAL_EMAIL_FROM}")
        self.stdout.write(f"Portal:    {settings.CUSTOMER_PORTAL_URL}")

        problems = email_config_problems()
        if problems:
            raise CommandError("Configuração incompleta:\n- " + "\n- ".join(problems))

        try:
            connection = get_connection(fail_silently=False)
            connection.open()
            connection.close()
            self.stdout.write(self.style.SUCCESS("Ligação e autenticação no servidor de email: OK."))
            if options["to"]:
                send_mail(
                    subject="Teste de email do Q360",
                    message="Esta mensagem confirma que o Q360 consegue enviar email. Pode ignorá-la.",
                    from_email=settings.CUSTOMER_PORTAL_EMAIL_FROM,
                    recipient_list=[options["to"]],
                    fail_silently=False,
                )
                self.stdout.write(self.style.SUCCESS(
                    f"Mensagem aceite pelo servidor. Confirme se chegou a {options['to']} (veja também o spam)."
                ))
        except Exception as exc:  # noqa: BLE001 - qualquer falha SMTP é o resultado deste diagnóstico
            raise CommandError(f"O servidor de email recusou: {type(exc).__name__}: {exc}") from exc

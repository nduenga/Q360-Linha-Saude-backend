"""OD-PORTAL-001 (Product Owner decision 2026-09-22): email OTP only.

Sends through Django's own email framework (`django.core.mail`), not a
bespoke client — which real provider handles it (SMTP, SES, SendGrid...)
is `settings.EMAIL_BACKEND`/`EMAIL_HOST_*` configuration per environment,
exactly like `OIDC_JWKS_URL` is for the staff IdP (config/settings/base.py).
Dev uses Django's console backend (settings printed to the log, no real
send); tests use the locmem backend (`django.core.mail.outbox`). Nothing
here pretends to be a real provider that isn't configured — this is the
actual Django email API, just unconfigured until an environment sets
EMAIL_HOST/EMAIL_HOST_USER/etc.
"""
from __future__ import annotations

from django.conf import settings
from django.core.mail import send_mail


def send_otp_email(*, to_email: str, otp: str) -> None:
    send_mail(
        subject="O seu código de acesso",
        message=(
            f"O seu código de acesso ao Portal do Cliente é: {otp}\n\n"
            f"Este código expira em {settings.CUSTOMER_PORTAL_OTP_TTL_SECONDS // 60} minutos. "
            "Se não pediu este código, ignore este email."
        ),
        from_email=settings.CUSTOMER_PORTAL_EMAIL_FROM,
        recipient_list=[to_email],
        fail_silently=False,
    )

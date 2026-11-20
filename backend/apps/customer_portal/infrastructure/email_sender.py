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

from email.utils import formataddr, parseaddr

import html as _html
from email.mime.image import MIMEImage

from django.conf import settings
from django.core.mail import EmailMultiAlternatives


def send_mail(*, subject: str, message: str, from_email: str, recipient_list: list[str], fail_silently: bool = False) -> int:
    """Como `django.core.mail.send_mail`, mais uma versão HTML com a cor e o
    logótipo da seguradora (ficha da plataforma), quando existirem. O texto
    simples continua a ser a mensagem principal."""
    email = EmailMultiAlternatives(subject=subject, body=message, from_email=from_email, to=recipient_list)
    branding = _branding()
    if branding is not None:
        color, logo = branding
        logo_tag = '<img src="cid:logo" alt="" style="max-height:48px;display:block;margin-bottom:8px">' if logo else ""
        paragraphs = "".join(
            f'<p style="margin:0 0 12px">{_html.escape(part).replace(chr(10), "<br>")}</p>'
            for part in message.split("\n\n")
        )
        html_body = (
            '<div style="font-family:Arial,sans-serif;font-size:14px;color:#1f2937;max-width:600px">'
            f'<div style="border-top:6px solid {color or "#0B3D91"};padding:16px 0 8px">{logo_tag}</div>'
            f"{paragraphs}</div>"
        )
        email.attach_alternative(html_body, "text/html")
        if logo:
            email.mixed_subtype = "related"
            image = MIMEImage(logo[0], _subtype="png" if logo[1] == "image/png" else "jpeg")
            image.add_header("Content-ID", "<logo>")
            image.add_header("Content-Disposition", "inline", filename="logo")
            email.attach(image)
    return email.send(fail_silently=fail_silently)


def _branding() -> tuple[str | None, tuple[bytes, str] | None] | None:
    from apps.foundation.application.context import CurrentTenantProvider
    from apps.foundation.infrastructure.models import Tenant
    from apps.platform_admin.application.tenant_settings import logo_bytes, settings_of

    tenant_id = CurrentTenantProvider.get()
    if tenant_id is None:
        return None
    try:
        tenant = Tenant.objects.filter(id=tenant_id.value).first()
    except RuntimeError:
        return None
    if tenant is None:
        return None
    branding = settings_of(tenant)["branding"]
    logo = logo_bytes(tenant.id) if branding.get("logo") else None
    if not branding.get("primaryColor") and logo is None:
        return None
    return branding.get("primaryColor"), logo


def sender(tenant_name: str | None = None) -> str:
    """Remetente «Q360 - <nome do tenant>» <endereço configurado>.

    O endereço vem de CUSTOMER_PORTAL_EMAIL_FROM (se já tiver um nome, só o
    endereço é aproveitado). O nome do tenant é o do contexto atual; sem
    tenant (p.ex. `check_email`) o nome fica só «Q360»."""
    address = parseaddr(settings.CUSTOMER_PORTAL_EMAIL_FROM)[1] or settings.CUSTOMER_PORTAL_EMAIL_FROM.strip()
    name = (tenant_name or _current_tenant_name() or "").strip()
    return formataddr((f"Q360 - {name}" if name else "Q360", address))


def _current_tenant_name() -> str | None:
    from apps.foundation.application.context import CurrentTenantProvider
    from apps.foundation.infrastructure.models import Tenant

    tenant_id = CurrentTenantProvider.get()
    if tenant_id is None:
        return None
    return Tenant.objects.filter(id=tenant_id.value).values_list("name", flat=True).first()


def send_otp_email(*, to_email: str, otp: str) -> None:
    send_mail(
        subject="O seu código de acesso",
        message=(
            f"O seu código de acesso ao Portal do Cliente é: {otp}\n\n"
            f"Este código expira em {settings.CUSTOMER_PORTAL_OTP_TTL_SECONDS // 60} minutos. "
            "Se não pediu este código, ignore este email."
        ),
        from_email=sender(),
        recipient_list=[to_email],
        fail_silently=False,
    )


def send_set_password_email(*, to_email: str, otp: str) -> None:
    send_mail(
        subject="Código para definir a sua palavra-passe",
        message=(
            f"O código para definir a palavra-passe do Portal do Cliente é: {otp}\n\n"
            f"Este código expira em {settings.CUSTOMER_PORTAL_OTP_TTL_SECONDS // 60} minutos. "
            "Se não pediu este código, ignore este email: a sua conta continua segura."
        ),
        from_email=sender(),
        recipient_list=[to_email],
        fail_silently=False,
    )


def send_portal_invitation_email(*, to_email: str, client_name: str, insurer_name: str, link: str,
                                 existing_account: bool, quote_number: str | None = None,
                                 policy_number: str | None = None) -> None:
    """Convite enviado quando a seguradora regista um proponente com email."""
    references = []
    if quote_number:
        references.append(f"Número da cotação: {quote_number}")
    if policy_number:
        references.append(f"Número da apólice: {policy_number}")
    reference_block = ("\n".join(references) + "\n\n") if references else ""
    if existing_account:
        which = ("o número da cotação indicado acima" if quote_number
                 else "o número da apólice indicado acima" if policy_number
                 else "o número da cotação ou apólice que vai receber")
        steps = ("Já existe uma conta no Portal do Cliente com este email. Para ver também este registo, "
                 f"use «Primeiro acesso» em {link} com {which} e o documento do cliente.")
    else:
        steps = (f"Para criar a sua palavra-passe, abra {link} e peça o código: enviamo-lo para "
                 "este email. Depois entra com o email e a palavra-passe que escolher.")
    send_mail(
        subject=f"{insurer_name}: acesso ao Portal do Cliente",
        message=(
            f"Olá {client_name},\n\n"
            f"A {insurer_name} registou-o(a) como cliente. No Portal do Cliente pode acompanhar "
            "as suas cotações, apólices, pagamentos e pedidos.\n\n"
            f"{reference_block}"
            f"{steps}\n\n"
            "Se não reconhece este registo, ignore este email."
        ),
        from_email=sender(insurer_name),
        recipient_list=[to_email],
        fail_silently=False,
    ) 

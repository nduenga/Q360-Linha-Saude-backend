import datetime
import jwt
from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.utils import timezone
from apps.platform_admin.application.audit_service import record_platform_audit
from apps.platform_admin.infrastructure.models import PlatformAdmin

from apps.foundation.domain.problem import DomainProblem


class PlatformAuthenticationError(DomainProblem):
    http_status = 401
    problem_code = "AUTH-401"

def login(*, email: str, password: str, correlation_id: str|None):
    account = PlatformAdmin.objects.filter(email__iexact=email.strip()).first()
    if account is None or account.status != PlatformAdmin.ACTIVE:
        record_platform_audit(actor_id="ANONYMOUS", action="platform.login_failed", entity_type="PlatformAdmin", correlation_id=correlation_id)
        raise PlatformAuthenticationError("Invalid email or password")
    now=timezone.now()
    if account.locked_until and account.locked_until > now:
        raise PlatformAuthenticationError("Platform administrator is temporarily locked")
    if not check_password(password, account.password_hash):
        attempts=account.failed_login_attempts+1; locked=None
        if attempts >= 5: locked=now+datetime.timedelta(minutes=30)
        PlatformAdmin.objects.filter(id=account.id).update(failed_login_attempts=attempts, locked_until=locked)
        record_platform_audit(actor_id=str(account.id), action="platform.login_failed", entity_type="PlatformAdmin", entity_id=str(account.id), correlation_id=correlation_id, metadata={"locked":locked is not None})
        raise PlatformAuthenticationError("Invalid email or password")
    ttl=settings.PLATFORM_ADMIN_ACCESS_TOKEN_TTL_SECONDS; now_utc=datetime.datetime.now(datetime.timezone.utc)
    claims={"sub":str(account.id),"token_type":"platform","roles":["PLATFORM_ADMIN"],"scope":"q360.read q360.write q360.admin q360.audit","iss":settings.PLATFORM_ADMIN_JWT_ISSUER,"aud":settings.PLATFORM_ADMIN_JWT_AUDIENCE,"iat":int(now_utc.timestamp()),"exp":int((now_utc+datetime.timedelta(seconds=ttl)).timestamp())}
    token=jwt.encode(claims, settings.PLATFORM_ADMIN_JWT_SIGNING_KEY, algorithm="HS256")
    PlatformAdmin.objects.filter(id=account.id).update(failed_login_attempts=0, locked_until=None, last_login_at=now)
    record_platform_audit(actor_id=str(account.id), action="platform.login_succeeded", entity_type="PlatformAdmin", entity_id=str(account.id), correlation_id=correlation_id)
    return token,ttl,account

from getpass import getpass
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand,CommandError
from apps.platform_admin.infrastructure.models import PlatformAdmin
class Command(BaseCommand):
    help="Create a platform administrator without storing a plaintext password."
    def add_arguments(self,parser): parser.add_argument("--email",required=True); parser.add_argument("--name",required=True)
    def handle(self,*args,**options):
        email=options["email"].strip().lower(); name=options["name"].strip()
        if PlatformAdmin.objects.filter(email__iexact=email).exists(): raise CommandError("Já existe um administrador da plataforma com este email.")
        p=getpass("Platform admin password: "); c=getpass("Confirm password: ")
        if p!=c: raise CommandError("As palavras-passe não coincidem.")
        if len(p)<12: raise CommandError("A palavra-passe tem de ter pelo menos 12 caracteres.")
        PlatformAdmin.objects.create(email=email,name=name,password_hash=make_password(p),status=PlatformAdmin.ACTIVE)
        self.stdout.write(self.style.SUCCESS(f"Platform admin created: {email}"))

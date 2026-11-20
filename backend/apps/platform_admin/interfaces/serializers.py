from rest_framework import serializers


class PlatformLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=320)
    password = serializers.CharField(max_length=200, write_only=True)


class PlatformLoginResponseSerializer(serializers.Serializer):
    accessToken = serializers.CharField()
    expiresIn = serializers.IntegerField()
    adminId = serializers.UUIDField()
    name = serializers.CharField()
    email = serializers.EmailField()


class TenantProfileSerializer(serializers.Serializer):
    # NIF de empresa: 10 dígitos (mesma regra do NIF de organização dos clientes).
    nif = serializers.RegexField(
        regex=r"^\d{10}$", max_length=10, required=False, allow_blank=True,
        error_messages={"invalid": "O NIF da seguradora deve ter exatamente 10 dígitos."},
    )
    email = serializers.EmailField(max_length=320, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=40, required=False, allow_blank=True)
    address = serializers.CharField(max_length=400, required=False, allow_blank=True)
    country = serializers.CharField(max_length=60, required=False, allow_blank=True)
    notes = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class TenantAdminSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    email = serializers.EmailField(max_length=320)


class CreateTenantSerializer(serializers.Serializer):
    # Opcional: sem código, é gerado a partir do nome (ver tenant_service.code_from_name).
    code = serializers.RegexField(regex=r"^[a-z0-9][a-z0-9_-]{2,49}$", max_length=50, required=False, allow_blank=True)
    name = serializers.CharField(max_length=200)
    profile = TenantProfileSerializer(required=False)
    admin = TenantAdminSerializer()


class UpdateTenantSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200, required=False)
    profile = TenantProfileSerializer(required=False)
    status = serializers.ChoiceField(choices=["ACTIVE", "SUSPENDED", "INACTIVE"], required=False)
    suspensionReason = serializers.CharField(max_length=1000, required=False, allow_blank=True,
                                             help_text="Obrigatório ao suspender (mínimo 10 caracteres).")
    reactivateOn = serializers.DateField(required=False, allow_null=True,
                                         help_text="Data em que a seguradora volta a ficar ativa (opcional).")


class TenantBrandingSerializer(serializers.Serializer):
    primaryColor = serializers.CharField(max_length=7, required=False, allow_blank=True, allow_null=True)
    secondaryColor = serializers.CharField(max_length=7, required=False, allow_blank=True, allow_null=True)


class TenantModulesSerializer(serializers.Serializer):
    customerPortal = serializers.BooleanField(required=False)


class TenantLimitsSerializer(serializers.Serializer):
    maxUsers = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    modules = TenantModulesSerializer(required=False)


class UpdateTenantSettingsSerializer(serializers.Serializer):
    branding = TenantBrandingSerializer(required=False)
    limits = TenantLimitsSerializer(required=False)


class TenantLogoUploadSerializer(serializers.Serializer):
    file = serializers.ImageField(help_text="PNG ou JPEG, até 1 MB.")


class OnboardingStepSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    status = serializers.ChoiceField(choices=["DONE", "PENDING", "WARNING"])
    detail = serializers.CharField()


class OnboardingSerializer(serializers.Serializer):
    steps = OnboardingStepSerializer(many=True)
    done = serializers.IntegerField()
    total = serializers.IntegerField()


class TenantHealthSerializer(serializers.Serializer):
    tenantId = serializers.UUIDField()
    status = serializers.CharField()
    lastLoginAt = serializers.DateTimeField(allow_null=True)
    activeUsers = serializers.IntegerField()
    maxUsers = serializers.IntegerField(allow_null=True)
    quotesThisMonth = serializers.IntegerField()
    policiesThisMonth = serializers.IntegerField()
    missingConfiguration = serializers.ListField(child=serializers.CharField())
    onboarding = OnboardingSerializer()
    suspension = serializers.JSONField(allow_null=True)


class AuditChangeSerializer(serializers.Serializer):
    field = serializers.CharField()
    before = serializers.JSONField(allow_null=True)
    after = serializers.JSONField(allow_null=True)


class AuditSearchEventSerializer(serializers.Serializer):
    id = serializers.CharField()
    source = serializers.ChoiceField(choices=["PLATFORM", "TENANT"])
    tenantId = serializers.CharField(allow_null=True)
    tenantName = serializers.CharField(allow_null=True)
    actorId = serializers.CharField(allow_null=True)
    actorName = serializers.CharField(allow_null=True)
    actorType = serializers.CharField(allow_null=True)
    action = serializers.CharField()
    actionLabel = serializers.CharField()
    entityType = serializers.CharField()
    entityId = serializers.CharField(allow_null=True)
    occurredAt = serializers.DateTimeField()
    correlationId = serializers.CharField(allow_null=True)
    metadata = serializers.JSONField()
    changes = AuditChangeSerializer(many=True)


class AuditSearchPageSerializer(serializers.Serializer):
    items = AuditSearchEventSerializer(many=True)
    page = serializers.IntegerField()
    size = serializers.IntegerField()
    total = serializers.IntegerField()


class PlatformAlertSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["FAILED_LOGINS", "LOCKED_ACCOUNT", "LEGAL_PARAMETER"])
    severity = serializers.ChoiceField(choices=["WARNING", "INFO"])
    tenantId = serializers.CharField(allow_null=True)
    title = serializers.CharField()
    detail = serializers.CharField()
    occurredAt = serializers.DateTimeField(allow_null=True)


class TenantResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()
    status = serializers.CharField()
    profile = TenantProfileSerializer()
    settings = serializers.JSONField(help_text="Suspensão, identidade visual (hasLogo), limites e módulos.")
    createdAt = serializers.DateTimeField()
    updatedAt = serializers.DateTimeField()


class TenantAccountSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    name = serializers.CharField()
    status = serializers.CharField()
    roles = serializers.ListField(child=serializers.CharField())
    lastLoginAt = serializers.DateTimeField(allow_null=True)


class TenantDetailSerializer(serializers.Serializer):
    tenant = TenantResponseSerializer()
    accounts = TenantAccountSerializer(many=True)
    stats = serializers.DictField(child=serializers.IntegerField())


class CreatedAdminSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    name = serializers.CharField()
    role = serializers.CharField()


class CreateTenantResponseSerializer(serializers.Serializer):
    tenant = TenantResponseSerializer()
    admin = CreatedAdminSerializer()
    temporaryPassword = serializers.CharField()
    temporaryPasswordNotice = serializers.CharField()


class TemporaryPasswordResponseSerializer(serializers.Serializer):
    accountId = serializers.UUIDField()
    email = serializers.EmailField()
    temporaryPassword = serializers.CharField()
    temporaryPasswordNotice = serializers.CharField()


class PlatformAdminSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    name = serializers.CharField()
    status = serializers.CharField()
    lastLoginAt = serializers.DateTimeField(allow_null=True)
    createdAt = serializers.DateTimeField()


class CreatePlatformAdminSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    email = serializers.EmailField(max_length=320)


class CreatePlatformAdminResponseSerializer(serializers.Serializer):
    admin = PlatformAdminSerializer()
    temporaryPassword = serializers.CharField()
    temporaryPasswordNotice = serializers.CharField()


class UpdatePlatformAdminStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["ACTIVE", "DISABLED"])


class ChangePasswordSerializer(serializers.Serializer):
    currentPassword = serializers.CharField(max_length=200)
    newPassword = serializers.CharField(max_length=200)


class PlatformAuditEventSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    actorId = serializers.CharField()
    actorName = serializers.CharField(allow_null=True)
    action = serializers.CharField()
    entityType = serializers.CharField()
    entityId = serializers.CharField(allow_null=True)
    entityLabel = serializers.CharField(allow_null=True, help_text="Nome legível do registo (seguradora, conta); null se não houver.")
    occurredAt = serializers.DateTimeField()
    correlationId = serializers.CharField(allow_null=True)
    metadata = serializers.JSONField()

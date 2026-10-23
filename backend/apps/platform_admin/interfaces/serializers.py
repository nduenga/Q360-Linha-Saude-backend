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
    legalName = serializers.CharField(max_length=200, required=False, allow_blank=True)
    nif = serializers.CharField(max_length=40, required=False, allow_blank=True)
    email = serializers.EmailField(max_length=320, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=40, required=False, allow_blank=True)
    address = serializers.CharField(max_length=400, required=False, allow_blank=True)
    country = serializers.CharField(max_length=60, required=False, allow_blank=True)
    notes = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class TenantAdminSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    email = serializers.EmailField(max_length=320)


class CreateTenantSerializer(serializers.Serializer):
    code = serializers.RegexField(regex=r"^[a-z0-9][a-z0-9_-]{2,49}$", max_length=50)
    name = serializers.CharField(max_length=200)
    profile = TenantProfileSerializer(required=False)
    admin = TenantAdminSerializer()


class UpdateTenantSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200, required=False)
    profile = TenantProfileSerializer(required=False)
    status = serializers.ChoiceField(choices=["ACTIVE", "SUSPENDED", "INACTIVE"], required=False)


class TenantResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()
    status = serializers.CharField()
    profile = TenantProfileSerializer()
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
    occurredAt = serializers.DateTimeField()
    correlationId = serializers.CharField(allow_null=True)
    metadata = serializers.JSONField()

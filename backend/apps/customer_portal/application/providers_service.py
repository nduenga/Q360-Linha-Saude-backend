"""Rede convencionada (roadmap_mobile.md, Fase 3): lista e mapa de prestadores
na app, com ordenação pela distância ao telemóvel. A gestão é do backoffice."""
from __future__ import annotations

import math
import uuid
from decimal import Decimal

from apps.customer_portal.domain.errors import PortalResourceNotFoundError
from apps.customer_portal.infrastructure.models import CareProvider

TYPES = ("HOSPITAL", "CLINIC", "LAB", "PHARMACY", "IMAGING", "DENTAL", "OTHER")
MAX_RESULTS = 100


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância pelo grande círculo (haversine)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlmb = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(a))


def describe(provider: CareProvider, *, distance: float | None = None) -> dict:
    return {
        "id": str(provider.id), "name": provider.name, "type": provider.provider_type,
        "specialties": list(provider.specialties or []), "province": provider.province,
        "municipality": provider.municipality, "address": provider.address, "phone": provider.phone,
        "openingHours": provider.opening_hours, "emergency": provider.emergency,
        "latitude": float(provider.latitude) if provider.latitude is not None else None,
        "longitude": float(provider.longitude) if provider.longitude is not None else None,
        "active": provider.active,
        "distanceKm": round(distance, 1) if distance is not None else None,
    }


def search(
    *, q: str = "", province: str = "", provider_type: str = "", specialty: str = "", emergency: bool | None = None,
    lat: float | None = None, lng: float | None = None, radius_km: float | None = None, limit: int = 50,
    include_inactive: bool = False,
) -> list[dict]:
    queryset = CareProvider.objects.all()
    if not include_inactive:
        queryset = queryset.filter(active=True)
    if province:
        queryset = queryset.filter(province__iexact=province)
    if provider_type:
        queryset = queryset.filter(provider_type=provider_type)
    if emergency is not None:
        queryset = queryset.filter(emergency=emergency)
    needle = q.strip().lower()
    wanted = specialty.strip().lower()
    rows: list[tuple[float | None, CareProvider]] = []
    for provider in queryset.order_by("name"):
        specialties = [s.lower() for s in (provider.specialties or [])]
        if needle and needle not in " ".join((provider.name, provider.municipality, provider.address, *specialties)).lower():
            continue
        if wanted and wanted not in specialties:
            continue
        distance = None
        if lat is not None and lng is not None and provider.latitude is not None:
            distance = distance_km(lat, lng, float(provider.latitude), float(provider.longitude))
            if radius_km is not None and distance > radius_km:
                continue
        elif radius_km is not None and lat is not None:
            continue  # sem coordenadas não se sabe se está dentro do raio
        rows.append((distance, provider))
    if lat is not None and lng is not None:
        rows.sort(key=lambda r: (r[0] is None, r[0] if r[0] is not None else 0, r[1].name))
    return [describe(p, distance=d) for d, p in rows[: max(1, min(limit, MAX_RESULTS))]]


# ------------------------------------------------------------ backoffice
def _clean(data: dict) -> dict:
    fields = {}
    mapping = {
        "name": "name", "type": "provider_type", "province": "province", "municipality": "municipality",
        "address": "address", "phone": "phone", "openingHours": "opening_hours", "emergency": "emergency",
        "active": "active",
    }
    for key, column in mapping.items():
        if key in data:
            fields[column] = data[key]
    if "specialties" in data:
        fields["specialties"] = [str(s).strip() for s in data["specialties"] if str(s).strip()]
    for key in ("latitude", "longitude"):
        if key in data:
            fields[key] = None if data[key] is None else Decimal(str(data[key]))
    return fields


def create(*, tenant_id: uuid.UUID, data: dict) -> dict:
    return describe(CareProvider.objects.create(tenant_id=tenant_id, **_clean(data)))


def update(provider_id: uuid.UUID, data: dict) -> dict:
    provider = CareProvider.objects.filter(id=provider_id).first()
    if provider is None:
        raise PortalResourceNotFoundError("Prestador não encontrado")
    for column, value in _clean(data).items():
        setattr(provider, column, value)
    provider.save()
    return describe(provider)


def deactivate(provider_id: uuid.UUID) -> None:
    """Não se apaga: sai da rede visível ao cliente."""
    if not CareProvider.objects.filter(id=provider_id).update(active=False):
        raise PortalResourceNotFoundError("Prestador não encontrado")

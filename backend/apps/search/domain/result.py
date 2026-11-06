from dataclasses import dataclass, asdict, field


@dataclass(frozen=True)
class SearchItem:
    id: str
    title: str
    subtitle: str
    href: str
    maskedNif: str | None = None
    city: str | None = None
    status: str | None = None
    statusLabel: str | None = None
    actions: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class SearchGroup:
    kind: str
    label: str
    items: list[SearchItem]

    def to_dict(self) -> dict:
        return {
            'kind': self.kind,
            'label': self.label,
            'items': [asdict(item) for item in self.items],
        }
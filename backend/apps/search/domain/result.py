from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class SearchItem:
    id: str
    title: str
    subtitle: str
    href: str


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
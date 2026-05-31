"""YAML-based EngagementRepository implementation.

Wraps the file-based engagement persistence using YAML as the
serialization format. Provides an implementation of the
EngagementRepository protocol from domain/interfaces.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from harness.domain.identifiers import Slug
from harness.domain.engagement.model import Engagement, EngagementStatus, HealthWarning
from harness.errors import EngagementNotFoundError
from harness.domain.engagement.repository import EngagementRepository as JsonEngagementRepository


class YamlEngagementRepository:
    """YAML-based engagement persistence.

    Delegates to the existing JSON-based EngagementRepository
    for storage, with typed interfaces matching the domain protocol.
    """

    def __init__(self, root: Path | None = None) -> None:
        self._impl = JsonEngagementRepository(root)

    @property
    def root(self) -> Path:
        return self._impl.root

    def save(self, engagement: object) -> None:
        if isinstance(engagement, Engagement):
            self._impl.save(engagement)

    def get(self, slug: Slug) -> Optional[object]:
        try:
            return self._impl.load(str(slug))
        except EngagementNotFoundError:
            return None

    def exists(self, slug: Slug) -> bool:
        return self._impl.exists(str(slug))

    def delete(self, slug: Slug) -> None:
        self._impl.delete(str(slug))

    def list_all(self) -> list[object]:
        return list(self._impl.list_all())

    def update_status(self, slug: Slug, status: object) -> object:
        eng_status = EngagementStatus(str(status)) if isinstance(status, str) else status
        return self._impl.update_status(str(slug), eng_status)

"""EngagementRepository — file-based persistence for engagements.

Provides save, load, and list_all operations for the Engagement
dataclass. Uses JSON files stored under
``.harness/engagements/<slug>/engagement.json``.

See V7 §5.23 for the engagement data model.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from harness.domain.engagement.model import Engagement, EngagementStatus, HealthWarning
from harness.errors import EngagementNotFoundError
from harness.paths import find_project_root, get_engagement_dir, get_engagements_dir


class EngagementRepository:
    """File-based persistence for Engagement dataclasses.

    Each engagement is stored as a JSON file in the project's
    ``.harness/engagements/<slug>/`` directory.

    Args:
        root: Project root directory. If None, auto-discovered from CWD.
    """

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or find_project_root() or Path.cwd()
        self._engagements_dir = get_engagements_dir(self._root)

    @property
    def root(self) -> Path:
        """The project root directory."""
        return self._root

    def _engagement_path(self, slug: str) -> Path:
        """Get the JSON file path for an engagement.

        Args:
            slug: Engagement slug.

        Returns:
            Path to the engagement's JSON file.
        """
        eng_dir = get_engagement_dir(self._root, slug)
        return eng_dir / "engagement.json"

    def _ensure_engagements_dir(self) -> None:
        """Ensure the engagements directory exists."""
        self._engagements_dir.mkdir(parents=True, exist_ok=True)

    def _engagement_to_dict(self, engagement: Engagement) -> dict[str, Any]:
        """Convert an Engagement dataclass to a JSON-serialisable dict.

        Args:
            engagement: The Engagement to serialise.

        Returns:
            Dict representation suitable for JSON serialisation.
        """
        result = asdict(engagement)
        # Convert datetimes to ISO strings
        if isinstance(result.get("created_at"), datetime):
            result["created_at"] = result["created_at"].isoformat()
        if isinstance(result.get("last_active"), datetime):
            result["last_active"] = result["last_active"].isoformat()
        # Convert warnings (dataclasses become dicts via asdict)
        if "warnings" in result:
            for w in result["warnings"]:
                if isinstance(w.get("timestamp"), datetime):
                    w["timestamp"] = w["timestamp"].isoformat()
        # Convert status enum to string
        if isinstance(result.get("status"), str):
            result["status"] = str(EngagementStatus(result["status"]).value)
        return result

    def _dict_to_engagement(self, data: dict[str, Any]) -> Engagement:
        """Convert a dict back to an Engagement dataclass.

        Args:
            data: Dict representation from JSON.

        Returns:
            Restored Engagement instance.
        """
        # Parse datetime strings
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if isinstance(data.get("last_active"), str):
            data["last_active"] = datetime.fromisoformat(data["last_active"])

        # Parse warnings
        warnings_data = data.pop("warnings", [])
        warnings: list[HealthWarning] = []
        for w in warnings_data:
            if isinstance(w.get("timestamp"), str):
                w["timestamp"] = datetime.fromisoformat(w["timestamp"])
            warnings.append(HealthWarning(**w))

        # Parse status from string
        if isinstance(data.get("status"), str):
            data["status"] = EngagementStatus(data["status"])

        engagement = Engagement(**data)
        engagement.warnings = warnings
        return engagement

    def save(self, engagement: Engagement) -> None:
        """Persist an engagement's state to disk.

        Creates the engagement directory if it doesn't exist.

        Args:
            engagement: The Engagement to save.

        Raises:
            ValueError: If engagement slug is empty.
        """
        if not engagement.slug:
            raise ValueError("Engagement slug cannot be empty")

        self._ensure_engagements_dir()

        eng_dir = get_engagement_dir(self._root, engagement.slug)
        eng_dir.mkdir(parents=True, exist_ok=True)

        path = self._engagement_path(engagement.slug)
        data = self._engagement_to_dict(engagement)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def load(self, slug: str) -> Engagement:
        """Load an engagement from disk by slug.

        Args:
            slug: The engagement slug to load.

        Returns:
            The restored Engagement instance.

        Raises:
            EngagementNotFoundError: If no engagement file exists for the slug.
            ValueError: If slug is empty.
        """
        if not slug:
            raise ValueError("Engagement slug cannot be empty")

        path = self._engagement_path(slug)
        if not path.is_file():
            raise EngagementNotFoundError(f"Engagement '{slug}' not found at {path}")

        try:
            with open(path) as f:
                data = json.load(f)
            return self._dict_to_engagement(data)
        except json.JSONDecodeError as exc:
            raise EngagementNotFoundError(
                f"Engagement '{slug}' state is corrupt: {exc}"
            ) from exc

    def exists(self, slug: str) -> bool:
        """Check if an engagement exists.

        Args:
            slug: The engagement slug to check.

        Returns:
            True if the engagement file exists.
        """
        return self._engagement_path(slug).is_file()

    def delete(self, slug: str) -> None:
        """Delete an engagement's state file from disk.

        Args:
            slug: The engagement slug to delete.

        Raises:
            EngagementNotFoundError: If no engagement file exists.
            ValueError: If slug is empty.
        """
        if not slug:
            raise ValueError("Engagement slug cannot be empty")

        path = self._engagement_path(slug)
        if not path.is_file():
            raise EngagementNotFoundError(f"Engagement '{slug}' not found at {path}")

        path.unlink()

    def list_all(self) -> list[Engagement]:
        """List all stored engagements.

        Scans the engagements directory for JSON files.

        Returns:
            List of all valid Engagement instances. Corrupt files are
            skipped (not raised).
        """
        if not self._engagements_dir.is_dir():
            return []

        engagements: list[Engagement] = []
        for json_file in sorted(self._engagements_dir.glob("*/engagement.json")):
            try:
                with open(json_file) as f:
                    data = json.load(f)
                engagements.append(self._dict_to_engagement(data))
            except (json.JSONDecodeError, KeyError, TypeError):
                # Skip corrupt files
                continue

        return engagements

    def update_status(self, slug: str, status: EngagementStatus) -> Engagement:
        """Update the status of an engagement in-place.

        A convenience method that loads, modifies, and saves.

        Args:
            slug: The engagement slug.
            status: The new status value.

        Returns:
            The updated Engagement instance.

        Raises:
            EngagementNotFoundError: If the engagement doesn't exist.
        """
        engagement = self.load(slug)
        engagement.status = status
        engagement.last_active = datetime.now()
        self.save(engagement)
        return engagement

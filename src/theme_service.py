"""Application-owned theme service, preview bus, and versioned commit events."""

from __future__ import annotations

import json
import threading
import uuid
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable

from theme_manager import (
    BUILTIN_THEME_BY_ID,
    DEFAULT_BUILTIN_ID,
    RepositoryReadOnlyError,
    ThemeDefinition,
    ThemeRepository,
    ThemeState,
)


EVENT_SCHEMA_VERSION = 1
MAX_SEEN_EVENT_IDS = 512


@dataclass(frozen=True, slots=True)
class ThemePreviewEvent:
    theme: ThemeDefinition
    render_revision: int


@dataclass(frozen=True, slots=True)
class ThemeCommitEvent:
    schema_version: int
    revision: int
    origin_id: str
    event_id: str
    theme: ThemeDefinition

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "revision": self.revision,
            "origin_id": self.origin_id,
            "event_id": self.event_id,
            "theme": self.theme.to_dict(),
        }


class _BuiltinOnlyRepository:
    """Read-only fallback used only when repository initialization raises."""

    def __init__(self, reason: str):
        self.state = ThemeState()
        self.read_only = True
        self.read_only_reason = reason
        self.revision = 0

    def active_theme(self) -> ThemeDefinition:
        return BUILTIN_THEME_BY_ID[DEFAULT_BUILTIN_ID]

    def list_themes(self):
        return list(BUILTIN_THEME_BY_ID.values())

    def list_custom_themes(self):
        return []

    def get(self, theme_id):
        return BUILTIN_THEME_BY_ID.get(theme_id)

    def reload(self):
        return self.state

    def __getattr__(self, name):
        if name in {
            "activate",
            "create_custom_theme",
            "update_custom_theme",
            "delete_custom_theme",
            "commit_snapshot",
        }:
            raise RepositoryReadOnlyError(self.read_only_reason)
        raise AttributeError(name)


class ThemeService:
    """The single service instance injected into the themed application tree."""

    def __init__(
        self,
        repository: ThemeRepository | None = None,
        *,
        repository_factory: Callable[[], ThemeRepository] = ThemeRepository,
        shared_manager: Any = None,
        origin_id: str | None = None,
    ):
        self.initialization_error: Exception | None = None
        if repository is None:
            try:
                repository = repository_factory()
            except Exception as exc:
                self.initialization_error = exc
                repository = _BuiltinOnlyRepository(str(exc))
        self.repository = repository
        self.shared_manager = shared_manager
        self.origin_id = origin_id or str(uuid.uuid4())
        self._preview_revision = 0
        self._preview_subscribers: list[Callable[[ThemePreviewEvent], None]] = []
        self._commit_subscribers: list[Callable[[ThemeCommitEvent], None]] = []
        self._seen_ids: set[str] = set()
        self._seen_order: deque[str] = deque()
        self._lock = threading.RLock()
        self._closed = False
        self._shared_signal = None
        if shared_manager is not None:
            signal = getattr(shared_manager, "theme_changed", None)
            if signal is not None and hasattr(signal, "connect"):
                signal.connect(self.receive_commit_event)
                self._shared_signal = signal

    @property
    def read_only(self) -> bool:
        return bool(getattr(self.repository, "read_only", False))

    @property
    def revision(self) -> int:
        return int(getattr(self.repository, "revision", self.repository.state.revision))

    @property
    def active_theme(self) -> ThemeDefinition:
        return self.repository.active_theme()

    @property
    def themes(self) -> tuple[ThemeDefinition, ...]:
        return tuple(self.repository.list_themes())

    def subscribe_preview(
        self, callback: Callable[[ThemePreviewEvent], None]
    ) -> Callable[[], None]:
        with self._lock:
            self._preview_subscribers.append(callback)
        return lambda: self._unsubscribe(self._preview_subscribers, callback)

    def subscribe_commit(
        self, callback: Callable[[ThemeCommitEvent], None]
    ) -> Callable[[], None]:
        with self._lock:
            self._commit_subscribers.append(callback)
        return lambda: self._unsubscribe(self._commit_subscribers, callback)

    def _unsubscribe(self, subscribers: list, callback: Callable) -> None:
        with self._lock:
            try:
                subscribers.remove(callback)
            except ValueError:
                pass

    def preview(self, theme: ThemeDefinition) -> ThemePreviewEvent:
        with self._lock:
            if self._closed:
                raise RuntimeError("theme service is closed")
            self._preview_revision += 1
            event = ThemePreviewEvent(theme, self._preview_revision)
            subscribers = tuple(self._preview_subscribers)
        for callback in subscribers:
            callback(event)
        return event

    def activate(self, theme_id: str) -> ThemeDefinition:
        theme = self.repository.activate(theme_id)
        self._after_local_commit()
        return theme

    def create_custom_theme(
        self,
        name: str,
        source: ThemeDefinition,
        *,
        activate: bool = True,
    ) -> ThemeDefinition:
        created = self.repository.create_custom_theme(
            name,
            source.palette,
            background=source.background,
            effects=source.effects,
            text_glow=source.text_glow,
            activate=activate,
        )
        self._after_local_commit()
        return created

    def save_custom_theme(self, theme: ThemeDefinition) -> ThemeDefinition:
        updated = self.repository.update_custom_theme(
            theme.id,
            name=theme.name,
            palette=theme.palette,
            background=theme.background,
            effects=theme.effects,
            text_glow=theme.text_glow,
        )
        self._after_local_commit()
        return updated

    def rename_custom_theme(self, theme_id: str, name: str) -> ThemeDefinition:
        updated = self.repository.rename_custom_theme(theme_id, name)
        self._after_local_commit()
        return updated

    def delete_custom_theme(self, theme_id: str) -> bool:
        deleted = self.repository.delete_custom_theme(theme_id)
        if deleted:
            self._after_local_commit()
        return deleted

    def _after_local_commit(self) -> ThemeCommitEvent:
        theme = self.repository.active_theme()
        event = ThemeCommitEvent(
            schema_version=EVENT_SCHEMA_VERSION,
            revision=self.repository.revision,
            origin_id=self.origin_id,
            event_id=str(uuid.uuid4()),
            theme=theme,
        )
        self._remember_event(event.event_id)
        self._emit_commit(event)
        self._broadcast(event)
        return event

    def _broadcast(self, event: ThemeCommitEvent) -> None:
        if self.shared_manager is None:
            return
        payload = event.to_dict()
        # Structural guarantee: messages contain paths/parameters, never image
        # bytes.  This serialization check also rejects accidental bytes.
        json.dumps(payload, ensure_ascii=False)
        broadcaster = getattr(self.shared_manager, "broadcast_theme_commit", None)
        if callable(broadcaster):
            broadcaster(payload)
        else:
            legacy = getattr(self.shared_manager, "broadcast_theme_change", None)
            if callable(legacy):
                legacy(payload)

    def _emit_commit(self, event: ThemeCommitEvent) -> None:
        with self._lock:
            subscribers = tuple(self._commit_subscribers)
        for callback in subscribers:
            callback(event)

    def _remember_event(self, event_id: str) -> None:
        with self._lock:
            if event_id in self._seen_ids:
                return
            self._seen_ids.add(event_id)
            self._seen_order.append(event_id)
            while len(self._seen_order) > MAX_SEEN_EVENT_IDS:
                expired = self._seen_order.popleft()
                self._seen_ids.discard(expired)

    def receive_commit_event(self, payload: Any) -> bool:
        if self._closed or not isinstance(payload, dict):
            return False
        try:
            schema = int(payload["schema_version"])
            revision = int(payload["revision"])
            origin_id = str(payload["origin_id"])
            event_id = str(uuid.UUID(str(payload["event_id"])))
            raw_theme = payload["theme"]
        except (KeyError, TypeError, ValueError):
            return False
        if schema != EVENT_SCHEMA_VERSION or revision < 0 or origin_id == self.origin_id:
            return False
        with self._lock:
            if event_id in self._seen_ids or revision <= self.revision:
                return False

        # The committed JSON file is authoritative.  The message snapshot is
        # validated for safe fallback/notification but never written back.
        try:
            raw_id = raw_theme.get("id")
            if raw_id in BUILTIN_THEME_BY_ID:
                message_theme = BUILTIN_THEME_BY_ID[raw_id]
            else:
                message_theme = ThemeDefinition.from_dict(raw_theme, custom_only=True)
        except Exception:
            return False
        try:
            self.repository.reload()
        except Exception:
            return False
        if self.revision < revision:
            return False
        theme = self.repository.active_theme()
        if theme.id != message_theme.id and self.revision == revision:
            return False
        event = ThemeCommitEvent(schema, revision, origin_id, event_id, theme)
        self._remember_event(event_id)
        self._emit_commit(event)
        return True

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._preview_subscribers.clear()
            self._commit_subscribers.clear()
        if self._shared_signal is not None and hasattr(self._shared_signal, "disconnect"):
            try:
                self._shared_signal.disconnect(self.receive_commit_event)
            except (TypeError, RuntimeError):
                pass


__all__ = [
    "EVENT_SCHEMA_VERSION",
    "ThemeCommitEvent",
    "ThemePreviewEvent",
    "ThemeService",
]

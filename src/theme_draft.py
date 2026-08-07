"""Explicit-save immutable draft controller for appearance themes."""

from __future__ import annotations

from dataclasses import replace
from enum import Enum
from typing import Any, Callable

from theme_manager import (
    BackgroundDefinition,
    ColorPalette,
    EffectDefinition,
    TextGlowDefinition,
    ThemeDefinition,
    normalize_hex_color,
)
from theme_service import ThemeCommitEvent, ThemeService


class DraftDecision(str, Enum):
    SAVE = "save"
    DISCARD = "discard"
    CANCEL = "cancel"


class ThemeDraftController:
    def __init__(self, service: ThemeService):
        self.service = service
        self._baseline = service.active_theme
        self._draft = self._baseline
        self._baseline_revision = service.revision
        self.last_error: Exception | None = None
        self._subscribers: list[Callable[[ThemeDefinition], None]] = []
        self._commit_unsubscribe = service.subscribe_commit(self._on_commit)

    @property
    def baseline(self) -> ThemeDefinition:
        return self._baseline

    @property
    def draft(self) -> ThemeDefinition:
        return self._draft

    @property
    def dirty(self) -> bool:
        return not self._draft.visually_equals(self._baseline)

    @property
    def can_save(self) -> bool:
        return not self._baseline.readonly

    @property
    def can_save_as(self) -> bool:
        return True

    @property
    def baseline_revision(self) -> int:
        return self._baseline_revision

    def subscribe(
        self, callback: Callable[[ThemeDefinition], None]
    ) -> Callable[[], None]:
        if callback not in self._subscribers:
            self._subscribers.append(callback)
        callback(self._draft)
        return lambda: self._unsubscribe(callback)

    def _unsubscribe(self, callback: Callable[[ThemeDefinition], None]) -> None:
        try:
            self._subscribers.remove(callback)
        except ValueError:
            pass

    def _notify(self) -> None:
        for callback in tuple(self._subscribers):
            callback(self._draft)

    def edit(self, **changes: Any) -> ThemeDefinition:
        if "colors" in changes:
            changes["palette"] = ColorPalette.from_mapping(changes.pop("colors"))
        if "background" in changes and isinstance(changes["background"], dict):
            changes["background"] = BackgroundDefinition.from_dict(changes["background"])
        if "effects" in changes and isinstance(changes["effects"], dict):
            changes["effects"] = EffectDefinition.from_dict(changes["effects"])
        if "text_glow" in changes and isinstance(changes["text_glow"], dict):
            changes["text_glow"] = TextGlowDefinition.from_dict(changes["text_glow"])
        # Direct dataclass replacement intentionally permits a builtin to
        # become a preview draft without mutating the builtin registry.
        self._draft = replace(self._draft, **changes)
        self.last_error = None
        self.service.preview(self._draft)
        self._notify()
        return self._draft

    def set_color(self, key: str, value: str) -> ThemeDefinition:
        palette = self._draft.palette.to_dict()
        if key not in palette:
            raise KeyError(key)
        palette[key] = normalize_hex_color(value)
        return self.edit(palette=ColorPalette.from_mapping(palette))

    def set_background(self, **changes: Any) -> ThemeDefinition:
        return self.edit(background=replace(self._draft.background, **changes))

    def set_effects(self, **changes: Any) -> ThemeDefinition:
        return self.edit(effects=replace(self._draft.effects, **changes))

    def set_text_glow(self, **changes: Any) -> ThemeDefinition:
        return self.edit(text_glow=replace(self._draft.text_glow, **changes))

    def save(self) -> bool:
        if not self.can_save:
            self.last_error = PermissionError("builtin theme drafts can only be saved as a custom theme")
            return False
        try:
            saved = self.service.save_custom_theme(self._draft)
        except Exception as exc:
            self.last_error = exc
            return False
        self._install_baseline(saved)
        return True

    def save_as(self, name: str) -> ThemeDefinition | None:
        try:
            saved = self.service.create_custom_theme(name, self._draft, activate=True)
        except Exception as exc:
            self.last_error = exc
            return None
        self._install_baseline(saved)
        return saved

    def rename(self, name: str) -> bool:
        if self._baseline.readonly:
            self.last_error = PermissionError("builtin themes cannot be renamed")
            return False
        try:
            renamed = self.service.rename_custom_theme(self._baseline.id, name)
        except Exception as exc:
            self.last_error = exc
            return False
        self._install_baseline(renamed)
        return True

    def delete_current(self) -> bool:
        if self._baseline.readonly:
            self.last_error = PermissionError("builtin themes cannot be deleted")
            return False
        try:
            if not self.service.delete_custom_theme(self._baseline.id):
                return False
        except Exception as exc:
            self.last_error = exc
            return False
        self._install_baseline(self.service.active_theme)
        return True

    def discard(self) -> None:
        self._draft = self._baseline
        self.last_error = None
        self.service.preview(self._draft)
        self._notify()

    def resolve_dirty(self, decision: DraftDecision | str) -> bool:
        if not self.dirty:
            return True
        decision = DraftDecision(decision)
        if decision is DraftDecision.CANCEL:
            return False
        if decision is DraftDecision.DISCARD:
            self.discard()
            return True
        return self.save()

    def switch_to(
        self,
        theme_id: str,
        decision_provider: Callable[[], DraftDecision | str] | None = None,
    ) -> bool:
        if theme_id == self._baseline.id and not self.dirty:
            return True
        if self.dirty:
            if decision_provider is None or not self.resolve_dirty(decision_provider()):
                return False
        try:
            selected = self.service.activate(theme_id)
        except Exception as exc:
            self.last_error = exc
            return False
        self._install_baseline(selected)
        return True

    def guard_navigation(
        self, decision_provider: Callable[[], DraftDecision | str] | None = None
    ) -> bool:
        if not self.dirty:
            return True
        if decision_provider is None:
            return False
        return self.resolve_dirty(decision_provider())

    def _install_baseline(self, theme: ThemeDefinition) -> None:
        self._baseline = theme
        self._draft = theme
        self._baseline_revision = self.service.revision
        self.last_error = None
        self.service.preview(theme)
        self._notify()

    def _on_commit(self, event: ThemeCommitEvent) -> None:
        # An external commit can safely refresh an untouched draft.  Dirty
        # local work remains intact until the user resolves it.
        if not self.dirty and event.origin_id != self.service.origin_id:
            self._install_baseline(event.theme)

    def close(self) -> None:
        self._commit_unsubscribe()
        self._subscribers.clear()


__all__ = ["DraftDecision", "ThemeDraftController"]

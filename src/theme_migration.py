"""Lossless migration from legacy settings.ini colors to a custom theme."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Callable

from theme_manager import (
    BUILTIN_THEMES,
    BackgroundDefinition,
    ColorPalette,
    ControlToggles,
    EffectDefinition,
    FrozenJsonMap,
    TextGlowDefinition,
    ThemeDefinition,
    ThemeRepository,
    compatibility_projection,
    normalize_theme_name,
    theme_name_key,
    thaw_json,
)


LEGACY_COLOR_KEYS = {
    "background": "background_color",
    "card_background": "card_background_color",
    "component_background": "component_background_color",
    "highlight_button": "highlight_button_color",
    "text_color": "text_color",
    "notification_info": "notification_info_color",
    "notification_warning": "notification_warning_color",
    "notification_error": "notification_error_color",
}


@dataclass(frozen=True, slots=True)
class LegacyThemeSnapshot:
    current_name: str
    palette: ColorPalette
    source: str = "settings.ini-v1"

    @property
    def fingerprint(self) -> str:
        canonical = json.dumps(
            {
                "source": self.source,
                "current_name": self.current_name,
                "colors": self.palette.to_dict(),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def from_mapping(
        cls, values: Mapping[str, Any], *, source: str = "settings.ini-v1"
    ) -> "LegacyThemeSnapshot":
        flattened = _flatten_legacy_mapping(values)
        fallback = BUILTIN_THEMES[0].palette
        colors = {
            palette_key: flattened.get(legacy_key, fallback[palette_key])
            for palette_key, legacy_key in LEGACY_COLOR_KEYS.items()
        }
        raw_name = flattened.get("current_theme", "迁移主题")
        try:
            name = normalize_theme_name(str(raw_name))
        except ValueError:
            name = "迁移主题"
        return cls(name, ColorPalette.from_mapping(colors), source)

    @classmethod
    def from_settings_manager(cls, settings_manager) -> "LegacyThemeSnapshot":
        fallback = BUILTIN_THEMES[0].palette
        values = {
            "current_theme": settings_manager.Custom.get_value("current_theme", "迁移主题")
        }
        for palette_key, legacy_key in LEGACY_COLOR_KEYS.items():
            values[legacy_key] = settings_manager.Custom.get_value(
                legacy_key, fallback[palette_key]
            )
        return cls.from_mapping(values)


@dataclass(frozen=True, slots=True)
class LegacyMigrationResult:
    theme: ThemeDefinition
    fingerprint: str
    created: bool
    projection_succeeded: bool


def _flatten_legacy_mapping(values: Mapping[str, Any]) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, value in values.items():
        if isinstance(value, Mapping) and str(key).casefold() in {
            "theme",
            "notification",
            "custom",
        }:
            for nested_key, nested_value in value.items():
                flattened[str(nested_key).casefold()] = nested_value
        else:
            flattened[str(key).casefold()] = value
    return flattened


def _migration_effects() -> EffectDefinition:
    return EffectDefinition(
        content_enabled=False,
        content_opacity=1.0,
        content_blur_radius=0.0,
        cards_enabled=False,
        controls_master_enabled=False,
        control_enabled=ControlToggles(
            buttons=False,
            text_inputs=False,
            selections=False,
            item_views=False,
            scrollbars=False,
        ),
        sidebar_enabled=False,
        sidebar_opacity=1.0,
        sidebar_blur_radius=0.0,
        hover_suspend_enabled=False,
    )


def _deterministic_migration_name(repository: ThemeRepository, requested: str) -> str:
    occupied = {theme_name_key(theme.name) for theme in repository.list_themes()}
    if theme_name_key(requested) not in occupied:
        return requested
    base = f"{requested}（迁移）"
    if theme_name_key(base) not in occupied:
        return base
    index = 2
    while True:
        candidate = f"{requested}（迁移 {index}）"
        if theme_name_key(candidate) not in occupied:
            return candidate
        index += 1


def _project(projector: Any, theme: ThemeDefinition) -> bool:
    if projector is None:
        return True
    payload = compatibility_projection(theme)
    try:
        if hasattr(projector, "project_theme_compatibility"):
            return bool(projector.project_theme_compatibility(payload))
        if callable(projector):
            return bool(projector(payload))
        raise TypeError("projection writer must be callable or SettingsManager-like")
    except Exception:
        return False


def migrate_legacy_snapshot(
    repository: ThemeRepository,
    snapshot: LegacyThemeSnapshot,
    *,
    projection_writer: Any = None,
) -> LegacyMigrationResult:
    fingerprint = snapshot.fingerprint
    migrated = next(
        (
            theme
            for theme in repository.list_custom_themes()
            if theme.extras.get("legacy_fingerprint") == fingerprint
        ),
        None,
    )
    created = False
    if migrated is None:
        recorded = repository.state.extras.get("legacy_fingerprints", ())
        if fingerprint not in recorded:
            name = _deterministic_migration_name(repository, snapshot.current_name)
            migrated = ThemeDefinition.new_custom(
                name,
                snapshot.palette,
                background=BackgroundDefinition(
                    image_path=None,
                    fit_mode="cover",
                    position="center",
                    image_opacity=1.0,
                    mask_color="#FFFFFF",
                    mask_opacity=0.0,
                ),
                effects=_migration_effects(),
                text_glow=TextGlowDefinition(enabled=False),
                extras={
                    "legacy_fingerprint": fingerprint,
                    "legacy_source": snapshot.source,
                },
            )
            extras = thaw_json(repository.state.extras)
            fingerprints = list(extras.get("legacy_fingerprints", []))
            fingerprints.append(fingerprint)
            extras["legacy_fingerprints"] = fingerprints
            repository.commit_snapshot(
                (*repository.state.themes, migrated),
                migrated.id,
                expected_revision=repository.revision,
                extras=FrozenJsonMap(extras),
            )
            created = True
        else:
            # A recorded fingerprint whose theme was quarantined must not
            # generate duplicates.  Keep the current authoritative snapshot.
            migrated = repository.active_theme()

    projection_succeeded = _project(projection_writer, repository.active_theme())
    return LegacyMigrationResult(migrated, fingerprint, created, projection_succeeded)


def migrate_legacy_settings(repository: ThemeRepository, settings_manager) -> LegacyMigrationResult:
    """Read legacy values, migrate once, repair INI, then bind projection reads."""
    snapshot = LegacyThemeSnapshot.from_settings_manager(settings_manager)
    result = migrate_legacy_snapshot(
        repository, snapshot, projection_writer=settings_manager
    )
    settings_manager.bind_theme_projection_provider(
        lambda: compatibility_projection(repository.active_theme())
    )
    return result


__all__ = [
    "LEGACY_COLOR_KEYS",
    "LegacyMigrationResult",
    "LegacyThemeSnapshot",
    "migrate_legacy_settings",
    "migrate_legacy_snapshot",
]

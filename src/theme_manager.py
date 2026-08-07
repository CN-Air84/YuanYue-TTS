"""Immutable appearance-theme model and authoritative JSON repository.

`theme-state.json` is the only source of truth for theme definitions and the
active theme id.  Built-ins live exclusively in this module; only custom
themes are serialized.
"""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
import threading
import unicodedata
import uuid
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


SCHEMA_VERSION = 1
DEFAULT_BUILTIN_ID = "builtin:clear-day"
COLOR_KEYS = (
    "background",
    "card_background",
    "component_background",
    "highlight_button",
    "text_color",
    "notification_info",
    "notification_warning",
    "notification_error",
)
CONTROL_CATEGORIES = ("buttons", "text_inputs", "selections", "item_views", "scrollbars")
BACKGROUND_FIT_MODES = ("cover", "contain", "stretch", "tile")
BACKGROUND_POSITIONS = (
    "top-left",
    "top",
    "top-right",
    "left",
    "center",
    "right",
    "bottom-left",
    "bottom",
    "bottom-right",
)
_HEX_COLOR_RE = re.compile(r"^#?([0-9A-Fa-f]{6})$")
_BUILTIN_ID_RE = re.compile(r"^builtin:[a-z0-9]+(?:-[a-z0-9]+)*$")


class ThemeError(Exception):
    """Base error for the theme domain."""


class ThemeValidationError(ThemeError, ValueError):
    pass


class ThemeNotFoundError(ThemeError, LookupError):
    pass


class ReadOnlyThemeError(ThemeError, ValueError):
    pass


class RepositoryReadOnlyError(ThemeError, PermissionError):
    pass


class RevisionConflictError(ThemeError):
    pass


class ReentrantWriteError(ThemeError):
    pass


def normalize_hex_color(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("color must be a string")
    match = _HEX_COLOR_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(f"invalid #RRGGBB color: {value!r}")
    return f"#{match.group(1).upper()}"


def normalize_theme_name(value: Any) -> str:
    if not isinstance(value, str):
        raise ThemeValidationError("theme name must be a string")
    normalized = unicodedata.normalize("NFC", value).strip()
    if not normalized:
        raise ThemeValidationError("theme name cannot be empty")
    if any(unicodedata.category(character).startswith("C") for character in normalized):
        raise ThemeValidationError("theme name cannot contain control or invisible characters")
    return normalized


def theme_name_key(value: str) -> str:
    return normalize_theme_name(value).casefold()


def canonical_custom_theme_id(value: Any) -> str:
    if not isinstance(value, str) or value.startswith("builtin:"):
        raise ThemeValidationError("custom theme id must be a canonical UUID4")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError, TypeError) as exc:
        raise ThemeValidationError("custom theme id must be a canonical UUID4") from exc
    canonical = str(parsed)
    if parsed.version != 4 or value != canonical:
        raise ThemeValidationError("custom theme id must be a lowercase canonical UUID4")
    return canonical


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_utc_timestamp(value: Any) -> str:
    if not isinstance(value, str):
        raise ThemeValidationError("timestamp must be an ISO-8601 string")
    candidate = value.strip()
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ThemeValidationError(f"invalid timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ThemeValidationError("timestamp must include UTC timezone")
    parsed = parsed.astimezone(timezone.utc).replace(microsecond=0)
    return parsed.isoformat().replace("+00:00", "Z")


def _freeze_json(value: Any) -> Any:
    if isinstance(value, FrozenJsonMap):
        return value
    if isinstance(value, Mapping):
        return FrozenJsonMap(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ThemeValidationError(f"unsupported JSON value: {type(value).__name__}")


def thaw_json(value: Any) -> Any:
    if isinstance(value, FrozenJsonMap):
        return {key: thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    return value


class FrozenJsonMap(Mapping[str, Any]):
    """Deeply immutable mapping used to round-trip unknown JSON fields."""

    __slots__ = ("_items", "_index")

    def __init__(self, values: Mapping[str, Any] | None = None):
        source = values or {}
        items: list[tuple[str, Any]] = []
        for key, value in source.items():
            if not isinstance(key, str):
                raise ThemeValidationError("JSON object keys must be strings")
            items.append((key, _freeze_json(value)))
        self._items = tuple(items)
        self._index = dict(items)

    def __getitem__(self, key: str) -> Any:
        return self._index[key]

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __repr__(self) -> str:
        return f"FrozenJsonMap({dict(self._items)!r})"

    def __hash__(self) -> int:
        return hash(self._items)


EMPTY_EXTRAS = FrozenJsonMap()


@dataclass(frozen=True, slots=True)
class ColorPalette(Mapping[str, str]):
    background: str
    card_background: str
    component_background: str
    highlight_button: str
    text_color: str
    notification_info: str
    notification_warning: str
    notification_error: str

    def __post_init__(self) -> None:
        for key in COLOR_KEYS:
            object.__setattr__(self, key, normalize_hex_color(getattr(self, key)))

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "ColorPalette":
        if not isinstance(values, Mapping):
            raise ThemeValidationError("colors must be an object")
        missing = [key for key in COLOR_KEYS if key not in values]
        if missing:
            raise ThemeValidationError(f"missing theme colors: {', '.join(missing)}")
        return cls(**{key: values[key] for key in COLOR_KEYS})

    def __getitem__(self, key: str) -> str:
        if key not in COLOR_KEYS:
            raise KeyError(key)
        return getattr(self, key)

    def __iter__(self) -> Iterator[str]:
        return iter(COLOR_KEYS)

    def __len__(self) -> int:
        return len(COLOR_KEYS)

    def to_dict(self) -> dict[str, str]:
        return {key: getattr(self, key) for key in COLOR_KEYS}


@dataclass(frozen=True, slots=True)
class ControlToggles(Mapping[str, bool]):
    buttons: bool = True
    text_inputs: bool = True
    selections: bool = True
    item_views: bool = True
    scrollbars: bool = True

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None) -> "ControlToggles":
        values = values or {}
        if not isinstance(values, Mapping):
            raise ThemeValidationError("control_enabled must be an object")
        return cls(**{key: bool(values.get(key, True)) for key in CONTROL_CATEGORIES})

    def __getitem__(self, key: str) -> bool:
        if key not in CONTROL_CATEGORIES:
            raise KeyError(key)
        return bool(getattr(self, key))

    def __iter__(self) -> Iterator[str]:
        return iter(CONTROL_CATEGORIES)

    def __len__(self) -> int:
        return len(CONTROL_CATEGORIES)

    def to_dict(self) -> dict[str, bool]:
        return {key: self[key] for key in CONTROL_CATEGORIES}


def _validate_fraction(name: str, value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ThemeValidationError(f"{name} must be numeric") from exc
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ThemeValidationError(f"{name} must be between 0 and 1")
    return number


def _validate_nonnegative(name: str, value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ThemeValidationError(f"{name} must be numeric") from exc
    if not math.isfinite(number) or number < 0:
        raise ThemeValidationError(f"{name} cannot be negative")
    return number


@dataclass(frozen=True, slots=True)
class BackgroundDefinition:
    image_path: str | None = None
    fit_mode: str = "cover"
    position: str = "center"
    image_opacity: float = 1.0
    mask_color: str = "#FFFFFF"
    mask_opacity: float = 0.0
    extras: FrozenJsonMap = field(default_factory=FrozenJsonMap, compare=False)

    def __post_init__(self) -> None:
        if self.image_path is not None:
            if not isinstance(self.image_path, str) or not self.image_path.strip():
                raise ThemeValidationError("background image path must be a non-empty string")
            object.__setattr__(self, "image_path", self.image_path.replace("\\", "/"))
        if self.fit_mode not in BACKGROUND_FIT_MODES:
            raise ThemeValidationError(f"unsupported background fit mode: {self.fit_mode!r}")
        if self.position not in BACKGROUND_POSITIONS:
            raise ThemeValidationError(f"unsupported background position: {self.position!r}")
        object.__setattr__(self, "image_opacity", _validate_fraction("image_opacity", self.image_opacity))
        object.__setattr__(self, "mask_color", normalize_hex_color(self.mask_color))
        object.__setattr__(self, "mask_opacity", _validate_fraction("mask_opacity", self.mask_opacity))
        object.__setattr__(self, "extras", _freeze_json(self.extras))

    @classmethod
    def from_dict(cls, values: Mapping[str, Any] | None) -> "BackgroundDefinition":
        values = values or {}
        if not isinstance(values, Mapping):
            raise ThemeValidationError("background must be an object")
        known = {"image_path", "fit_mode", "position", "image_opacity", "mask_color", "mask_opacity"}
        return cls(
            image_path=values.get("image_path"),
            fit_mode=values.get("fit_mode", "cover"),
            position=values.get("position", "center"),
            image_opacity=values.get("image_opacity", 1.0),
            mask_color=values.get("mask_color", "#FFFFFF"),
            mask_opacity=values.get("mask_opacity", 0.0),
            extras=FrozenJsonMap({key: value for key, value in values.items() if key not in known}),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = thaw_json(self.extras)
        payload.update(
            {
                "image_path": self.image_path,
                "fit_mode": self.fit_mode,
                "position": self.position,
                "image_opacity": self.image_opacity,
                "mask_color": self.mask_color,
                "mask_opacity": self.mask_opacity,
            }
        )
        return payload


@dataclass(frozen=True, slots=True)
class EffectDefinition:
    content_enabled: bool = True
    content_opacity: float = 0.92
    content_blur_radius: float = 18.0
    cards_enabled: bool = True
    controls_master_enabled: bool = True
    control_enabled: ControlToggles = field(default_factory=ControlToggles)
    sidebar_enabled: bool = True
    sidebar_opacity: float = 0.94
    sidebar_blur_radius: float = 20.0
    hover_suspend_enabled: bool = True
    hover_enter_ms: int = 90
    hover_restore_ms: int = 180
    extras: FrozenJsonMap = field(default_factory=FrozenJsonMap, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "content_enabled", bool(self.content_enabled))
        object.__setattr__(self, "cards_enabled", bool(self.cards_enabled))
        object.__setattr__(self, "controls_master_enabled", bool(self.controls_master_enabled))
        object.__setattr__(self, "sidebar_enabled", bool(self.sidebar_enabled))
        object.__setattr__(self, "hover_suspend_enabled", bool(self.hover_suspend_enabled))
        object.__setattr__(self, "content_opacity", _validate_fraction("content_opacity", self.content_opacity))
        object.__setattr__(self, "content_blur_radius", _validate_nonnegative("content_blur_radius", self.content_blur_radius))
        object.__setattr__(self, "sidebar_opacity", _validate_fraction("sidebar_opacity", self.sidebar_opacity))
        object.__setattr__(self, "sidebar_blur_radius", _validate_nonnegative("sidebar_blur_radius", self.sidebar_blur_radius))
        if isinstance(self.control_enabled, Mapping) and not isinstance(self.control_enabled, ControlToggles):
            object.__setattr__(self, "control_enabled", ControlToggles.from_mapping(self.control_enabled))
        if not isinstance(self.control_enabled, ControlToggles):
            raise ThemeValidationError("control_enabled must be ControlToggles")
        for name in ("hover_enter_ms", "hover_restore_ms"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 60_000:
                raise ThemeValidationError(f"{name} must be an integer between 0 and 60000")
        object.__setattr__(self, "extras", _freeze_json(self.extras))

    def control_is_effective(self, category: str) -> bool:
        return self.controls_master_enabled and self.control_enabled[category]

    @classmethod
    def from_dict(cls, values: Mapping[str, Any] | None) -> "EffectDefinition":
        values = values or {}
        if not isinstance(values, Mapping):
            raise ThemeValidationError("effects must be an object")
        known = {
            "content_enabled", "content_opacity", "content_blur_radius", "cards_enabled",
            "controls_master_enabled", "control_enabled", "sidebar_enabled", "sidebar_opacity",
            "sidebar_blur_radius", "hover_suspend_enabled", "hover_enter_ms", "hover_restore_ms",
        }
        defaults = cls()
        return cls(
            content_enabled=values.get("content_enabled", defaults.content_enabled),
            content_opacity=values.get("content_opacity", defaults.content_opacity),
            content_blur_radius=values.get("content_blur_radius", defaults.content_blur_radius),
            cards_enabled=values.get("cards_enabled", defaults.cards_enabled),
            controls_master_enabled=values.get("controls_master_enabled", defaults.controls_master_enabled),
            control_enabled=ControlToggles.from_mapping(values.get("control_enabled")),
            sidebar_enabled=values.get("sidebar_enabled", defaults.sidebar_enabled),
            sidebar_opacity=values.get("sidebar_opacity", defaults.sidebar_opacity),
            sidebar_blur_radius=values.get("sidebar_blur_radius", defaults.sidebar_blur_radius),
            hover_suspend_enabled=values.get("hover_suspend_enabled", defaults.hover_suspend_enabled),
            hover_enter_ms=values.get("hover_enter_ms", defaults.hover_enter_ms),
            hover_restore_ms=values.get("hover_restore_ms", defaults.hover_restore_ms),
            extras=FrozenJsonMap({key: value for key, value in values.items() if key not in known}),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = thaw_json(self.extras)
        payload.update(
            {
                "content_enabled": self.content_enabled,
                "content_opacity": self.content_opacity,
                "content_blur_radius": self.content_blur_radius,
                "cards_enabled": self.cards_enabled,
                "controls_master_enabled": self.controls_master_enabled,
                "control_enabled": self.control_enabled.to_dict(),
                "sidebar_enabled": self.sidebar_enabled,
                "sidebar_opacity": self.sidebar_opacity,
                "sidebar_blur_radius": self.sidebar_blur_radius,
                "hover_suspend_enabled": self.hover_suspend_enabled,
                "hover_enter_ms": self.hover_enter_ms,
                "hover_restore_ms": self.hover_restore_ms,
            }
        )
        return payload


@dataclass(frozen=True, slots=True)
class TextGlowDefinition:
    enabled: bool = True
    minimum_intensity: float = 0.18
    maximum_intensity: float = 0.55
    minimum_radius: float = 1.5
    maximum_radius: float = 6.0
    extras: FrozenJsonMap = field(default_factory=FrozenJsonMap, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "enabled", bool(self.enabled))
        object.__setattr__(self, "minimum_intensity", _validate_fraction("minimum_intensity", self.minimum_intensity))
        object.__setattr__(self, "maximum_intensity", _validate_fraction("maximum_intensity", self.maximum_intensity))
        object.__setattr__(self, "minimum_radius", _validate_nonnegative("minimum_radius", self.minimum_radius))
        object.__setattr__(self, "maximum_radius", _validate_nonnegative("maximum_radius", self.maximum_radius))
        object.__setattr__(self, "extras", _freeze_json(self.extras))

    @classmethod
    def from_dict(cls, values: Mapping[str, Any] | None) -> "TextGlowDefinition":
        values = values or {}
        if not isinstance(values, Mapping):
            raise ThemeValidationError("text_glow must be an object")
        known = {"enabled", "minimum_intensity", "maximum_intensity", "minimum_radius", "maximum_radius"}
        defaults = cls()
        return cls(
            enabled=values.get("enabled", defaults.enabled),
            minimum_intensity=values.get("minimum_intensity", defaults.minimum_intensity),
            maximum_intensity=values.get("maximum_intensity", defaults.maximum_intensity),
            minimum_radius=values.get("minimum_radius", defaults.minimum_radius),
            maximum_radius=values.get("maximum_radius", defaults.maximum_radius),
            extras=FrozenJsonMap({key: value for key, value in values.items() if key not in known}),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = thaw_json(self.extras)
        payload.update(
            {
                "enabled": self.enabled,
                "minimum_intensity": self.minimum_intensity,
                "maximum_intensity": self.maximum_intensity,
                "minimum_radius": self.minimum_radius,
                "maximum_radius": self.maximum_radius,
            }
        )
        return payload


@dataclass(frozen=True, slots=True)
class ThemeDefinition:
    id: str
    name: str
    palette: ColorPalette
    background: BackgroundDefinition = field(default_factory=BackgroundDefinition)
    effects: EffectDefinition = field(default_factory=EffectDefinition)
    text_glow: TextGlowDefinition = field(default_factory=TextGlowDefinition)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    extras: FrozenJsonMap = field(default_factory=FrozenJsonMap, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str):
            raise ThemeValidationError("theme id must be a string")
        if self.id.startswith("builtin:"):
            if not _BUILTIN_ID_RE.fullmatch(self.id):
                raise ThemeValidationError("invalid builtin theme id")
        else:
            canonical_custom_theme_id(self.id)
        object.__setattr__(self, "name", normalize_theme_name(self.name))
        if isinstance(self.palette, Mapping) and not isinstance(self.palette, ColorPalette):
            object.__setattr__(self, "palette", ColorPalette.from_mapping(self.palette))
        if not isinstance(self.palette, ColorPalette):
            raise ThemeValidationError("palette must be ColorPalette")
        if isinstance(self.background, Mapping):
            object.__setattr__(self, "background", BackgroundDefinition.from_dict(self.background))
        if isinstance(self.effects, Mapping):
            object.__setattr__(self, "effects", EffectDefinition.from_dict(self.effects))
        if isinstance(self.text_glow, Mapping):
            object.__setattr__(self, "text_glow", TextGlowDefinition.from_dict(self.text_glow))
        object.__setattr__(self, "created_at", normalize_utc_timestamp(self.created_at))
        object.__setattr__(self, "updated_at", normalize_utc_timestamp(self.updated_at))
        object.__setattr__(self, "extras", _freeze_json(self.extras))

    @property
    def colors(self) -> ColorPalette:
        return self.palette

    @property
    def readonly(self) -> bool:
        return self.id in BUILTIN_THEME_IDS

    @classmethod
    def new_custom(
        cls,
        name: str,
        palette: ColorPalette | Mapping[str, Any],
        *,
        background: BackgroundDefinition | Mapping[str, Any] | None = None,
        effects: EffectDefinition | Mapping[str, Any] | None = None,
        text_glow: TextGlowDefinition | Mapping[str, Any] | None = None,
        theme_id: str | None = None,
        extras: Mapping[str, Any] | FrozenJsonMap | None = None,
        timestamp: str | None = None,
    ) -> "ThemeDefinition":
        stamp = timestamp or utc_now_iso()
        return cls(
            id=theme_id or str(uuid.uuid4()),
            name=name,
            palette=palette if isinstance(palette, ColorPalette) else ColorPalette.from_mapping(palette),
            background=background or BackgroundDefinition(),
            effects=effects or EffectDefinition(),
            text_glow=text_glow or TextGlowDefinition(),
            created_at=stamp,
            updated_at=stamp,
            extras=FrozenJsonMap(extras or {}),
        )

    @classmethod
    def from_dict(cls, values: Mapping[str, Any], *, custom_only: bool = True) -> "ThemeDefinition":
        if not isinstance(values, Mapping):
            raise ThemeValidationError("theme entry must be an object")
        theme_id = values.get("id")
        if custom_only:
            canonical_custom_theme_id(theme_id)
        known = {"id", "name", "colors", "background", "effects", "text_glow", "created_at", "updated_at", "readonly"}
        if "readonly" in values:
            # Read-only status is registry-derived and must never be persisted.
            raise ThemeValidationError("custom theme must not persist readonly")
        return cls(
            id=theme_id,
            name=values.get("name"),
            palette=ColorPalette.from_mapping(values.get("colors", {})),
            background=BackgroundDefinition.from_dict(values.get("background")),
            effects=EffectDefinition.from_dict(values.get("effects")),
            text_glow=TextGlowDefinition.from_dict(values.get("text_glow")),
            created_at=values.get("created_at", utc_now_iso()),
            updated_at=values.get("updated_at", values.get("created_at", utc_now_iso())),
            extras=FrozenJsonMap({key: value for key, value in values.items() if key not in known}),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = thaw_json(self.extras)
        payload.update(
            {
                "id": self.id,
                "name": self.name,
                "colors": self.palette.to_dict(),
                "background": self.background.to_dict(),
                "effects": self.effects.to_dict(),
                "text_glow": self.text_glow.to_dict(),
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            }
        )
        return payload

    def visual_signature(self) -> tuple[Any, ...]:
        return self.palette, self.background, self.effects, self.text_glow

    def visually_equals(self, other: object) -> bool:
        return isinstance(other, ThemeDefinition) and self.visual_signature() == other.visual_signature()

    def with_updates(self, **changes: Any) -> "ThemeDefinition":
        if self.readonly:
            raise ReadOnlyThemeError(f"builtin theme {self.id} cannot be changed")
        changes.setdefault("updated_at", utc_now_iso())
        if "colors" in changes:
            changes["palette"] = ColorPalette.from_mapping(changes.pop("colors"))
        return replace(self, **changes)


def _builtin(theme_id: str, name: str, colors: Mapping[str, str]) -> ThemeDefinition:
    stamp = "2026-07-26T00:00:00Z"
    return ThemeDefinition(
        id=theme_id,
        name=name,
        palette=ColorPalette.from_mapping(colors),
        text_glow=TextGlowDefinition(enabled=False),
        created_at=stamp,
        updated_at=stamp,
    )


BUILTIN_THEMES = (
    _builtin("builtin:clear-day", "清昼", {
        "background": "#EEF3F8", "card_background": "#FFFFFF", "component_background": "#F8FAFD",
        "highlight_button": "#3E76D1", "text_color": "#202A35", "notification_info": "#DCEBFA",
        "notification_warning": "#FFF0D1", "notification_error": "#FBE0E2",
    }),
    _builtin("builtin:morning-mist-blue", "晨雾蓝", {
        "background": "#E8F1F8", "card_background": "#F8FCFF", "component_background": "#F1F7FC",
        "highlight_button": "#3977B8", "text_color": "#203142", "notification_info": "#D5EAF8",
        "notification_warning": "#FBEBCF", "notification_error": "#F8DDDF",
    }),
    _builtin("builtin:green-bamboo", "青竹", {
        "background": "#EAF3EC", "card_background": "#FAFDF9", "component_background": "#F1F8F1",
        "highlight_button": "#3F8563", "text_color": "#24352C", "notification_info": "#DCEEE6",
        "notification_warning": "#F7EBCB", "notification_error": "#F4DDDA",
    }),
    _builtin("builtin:amber-paper", "琥珀纸", {
        "background": "#F6EEDC", "card_background": "#FFFDF6", "component_background": "#FAF4E6",
        "highlight_button": "#A46D2D", "text_color": "#3A3025", "notification_info": "#E4ECF3",
        "notification_warning": "#F9E1AE", "notification_error": "#F3D9D4",
    }),
    _builtin("builtin:scarlet-cherry", "绯樱", {
        "background": "#F8EAEF", "card_background": "#FFF9FB", "component_background": "#FCEFF3",
        "highlight_button": "#B65373", "text_color": "#3B2730", "notification_info": "#E3E8F7",
        "notification_warning": "#F8E8C9", "notification_error": "#F7D9E0",
    }),
    _builtin("builtin:lavender-mist", "薰衣草雾", {
        "background": "#F0EBF8", "card_background": "#FCFAFF", "component_background": "#F5F0FB",
        "highlight_button": "#7661B1", "text_color": "#302A3F", "notification_info": "#E1E3F7",
        "notification_warning": "#F5E7CA", "notification_error": "#F3DDE5",
    }),
    _builtin("builtin:sea-salt-cyan", "海盐青", {
        "background": "#E7F3F2", "card_background": "#F9FEFD", "component_background": "#EFF8F7",
        "highlight_button": "#317E83", "text_color": "#213536", "notification_info": "#D5ECEC",
        "notification_warning": "#F5E9C9", "notification_error": "#F1DDDC",
    }),
)
BUILTIN_THEME_IDS = frozenset(theme.id for theme in BUILTIN_THEMES)
BUILTIN_THEME_BY_ID = {theme.id: theme for theme in BUILTIN_THEMES}


@dataclass(frozen=True, slots=True)
class ThemeState:
    schema_version: int = SCHEMA_VERSION
    revision: int = 0
    active_theme_id: str = DEFAULT_BUILTIN_ID
    themes: tuple[ThemeDefinition, ...] = ()
    extras: FrozenJsonMap = field(default_factory=FrozenJsonMap, compare=False)

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ThemeValidationError(f"unsupported in-memory schema version: {self.schema_version}")
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) or self.revision < 0:
            raise ThemeValidationError("revision must be a non-negative integer")
        object.__setattr__(self, "themes", tuple(self.themes))
        ids: set[str] = set()
        names = {theme_name_key(theme.name) for theme in BUILTIN_THEMES}
        for theme in self.themes:
            if theme.readonly or theme.id.startswith("builtin:"):
                raise ThemeValidationError("theme-state can contain custom themes only")
            if theme.id in ids:
                raise ThemeValidationError(f"duplicate theme id: {theme.id}")
            key = theme_name_key(theme.name)
            if key in names:
                raise ThemeValidationError(f"duplicate theme name: {theme.name}")
            ids.add(theme.id)
            names.add(key)
        valid_ids = BUILTIN_THEME_IDS | ids
        if self.active_theme_id not in valid_ids:
            raise ThemeValidationError(f"active theme does not exist: {self.active_theme_id}")
        object.__setattr__(self, "extras", _freeze_json(self.extras))

    def to_dict(self) -> dict[str, Any]:
        payload = thaw_json(self.extras)
        payload.update(
            {
                "schema_version": self.schema_version,
                "revision": self.revision,
                "active_theme_id": self.active_theme_id,
                "themes": [theme.to_dict() for theme in self.themes],
            }
        )
        return payload


@dataclass(frozen=True, slots=True)
class ThemeRenderContext:
    theme: ThemeDefinition
    minimum_font_size: float
    maximum_font_size: float
    logical_size: tuple[int, int]
    dpr: float
    render_revision: int

    def __post_init__(self) -> None:
        if self.minimum_font_size > self.maximum_font_size:
            raise ThemeValidationError("minimum font size cannot exceed maximum font size")
        if len(self.logical_size) != 2 or any(value <= 0 for value in self.logical_size):
            raise ThemeValidationError("logical size must contain two positive values")
        if self.dpr <= 0:
            raise ThemeValidationError("DPR must be positive")
        if self.render_revision < 0:
            raise ThemeValidationError("render revision cannot be negative")


@dataclass(frozen=True, slots=True)
class QuarantinedTheme:
    index: int
    reason: str
    raw: Any


class ThemeRepository:
    """Single-writer, revision-checked repository for theme-state.json."""

    def __init__(self, root_or_state_path: str | os.PathLike[str] | None = None):
        if root_or_state_path is None:
            from misc_func import get_app_base_path

            root = Path(get_app_base_path()) / "data" / "themes"
            state_path = root / "theme-state.json"
        else:
            supplied = Path(root_or_state_path)
            if supplied.suffix.lower() == ".json":
                state_path = supplied
                root = supplied.parent
            else:
                root = supplied
                state_path = root / "theme-state.json"
        self.root = root
        self.state_path = state_path
        self.assets_path = root / "assets"
        self._lock = threading.RLock()
        self._write_in_progress = False
        self._state = ThemeState()
        self._read_only_reason: str | None = None
        self._quarantined: tuple[QuarantinedTheme, ...] = ()
        self._isolated_state_path: Path | None = None
        self._raw_future_payload: Any = None
        self._load()

    @property
    def state(self) -> ThemeState:
        return self._state

    @property
    def revision(self) -> int:
        return self._state.revision

    @property
    def read_only(self) -> bool:
        return self._read_only_reason is not None

    @property
    def read_only_reason(self) -> str | None:
        return self._read_only_reason

    @property
    def quarantined_themes(self) -> tuple[QuarantinedTheme, ...]:
        return self._quarantined

    @property
    def isolated_state_path(self) -> Path | None:
        return self._isolated_state_path

    def reload(self) -> ThemeState:
        """Reload state written by another process without entering a write transaction."""
        with self._lock:
            self._state = ThemeState()
            self._read_only_reason = None
            self._quarantined = ()
            self._isolated_state_path = None
            self._raw_future_payload = None
            self._load()
            return self._state

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            self._isolate_corrupt_file()
            self._read_only_reason = f"corrupt theme state: {exc}"
            self._state = ThemeState()
            return
        if not isinstance(payload, Mapping):
            self._isolate_corrupt_file()
            self._read_only_reason = "theme state root is not an object"
            return
        schema = payload.get("schema_version", 0)
        if isinstance(schema, bool) or not isinstance(schema, int):
            self._isolate_corrupt_file()
            self._read_only_reason = "invalid schema version"
            return
        if schema > SCHEMA_VERSION:
            self._raw_future_payload = payload
            self._read_only_reason = f"theme schema {schema} is newer than supported {SCHEMA_VERSION}"
            return
        try:
            payload = self._migrate_payload(dict(payload), schema)
            self._state = self._parse_payload(payload)
        except ThemeValidationError as exc:
            self._isolate_corrupt_file()
            self._read_only_reason = f"invalid theme state: {exc}"
            self._state = ThemeState()

    def _isolate_corrupt_file(self) -> None:
        if not self.state_path.exists():
            return
        suffix = f".corrupt-{utc_now_iso().replace(':', '').replace('-', '')}-{uuid.uuid4().hex}.json"
        target = self.state_path.with_name(f"{self.state_path.stem}{suffix}")
        try:
            os.replace(self.state_path, target)
            self._isolated_state_path = target
        except OSError:
            self._isolated_state_path = None

    @staticmethod
    def _migrate_payload(payload: dict[str, Any], schema: int) -> dict[str, Any]:
        if schema < 0:
            raise ThemeValidationError("schema version cannot be negative")
        if schema == 0:
            payload.setdefault("revision", 0)
            payload.setdefault("active_theme_id", DEFAULT_BUILTIN_ID)
            payload.setdefault("themes", [])
            payload["schema_version"] = 1
            schema = 1
        if schema != SCHEMA_VERSION:
            raise ThemeValidationError(f"cannot migrate schema {schema}")
        return payload

    def _parse_payload(self, payload: Mapping[str, Any]) -> ThemeState:
        revision = payload.get("revision")
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
            raise ThemeValidationError("revision must be a non-negative integer")
        raw_themes = payload.get("themes")
        if not isinstance(raw_themes, list):
            raise ThemeValidationError("themes must be an array")

        accepted: list[ThemeDefinition] = []
        quarantined: list[QuarantinedTheme] = []
        ids: set[str] = set()
        names = {theme_name_key(theme.name) for theme in BUILTIN_THEMES}
        for index, raw in enumerate(raw_themes):
            try:
                theme = ThemeDefinition.from_dict(raw, custom_only=True)
                if theme.id in ids:
                    raise ThemeValidationError(f"duplicate id {theme.id}")
                name_key = theme_name_key(theme.name)
                if name_key in names:
                    raise ThemeValidationError(f"duplicate name {theme.name}")
                ids.add(theme.id)
                names.add(name_key)
                accepted.append(theme)
            except (ThemeError, ValueError, TypeError) as exc:
                quarantined.append(QuarantinedTheme(index, str(exc), _freeze_json(raw)))

        active = payload.get("active_theme_id")
        if active not in BUILTIN_THEME_IDS and active not in ids:
            active = DEFAULT_BUILTIN_ID
        known = {"schema_version", "revision", "active_theme_id", "themes"}
        self._quarantined = tuple(quarantined)
        return ThemeState(
            schema_version=SCHEMA_VERSION,
            revision=revision,
            active_theme_id=active,
            themes=tuple(accepted),
            extras=FrozenJsonMap({key: value for key, value in payload.items() if key not in known}),
        )

    def list_themes(self) -> list[ThemeDefinition]:
        return [*BUILTIN_THEMES, *self._state.themes]

    def list_custom_themes(self) -> list[ThemeDefinition]:
        return list(self._state.themes)

    def get(self, theme_id: str) -> ThemeDefinition | None:
        builtin = BUILTIN_THEME_BY_ID.get(theme_id)
        if builtin is not None:
            return builtin
        return next((theme for theme in self._state.themes if theme.id == theme_id), None)

    def active_theme(self) -> ThemeDefinition:
        return self.get(self._state.active_theme_id) or BUILTIN_THEME_BY_ID[DEFAULT_BUILTIN_ID]

    def _ensure_writable(self) -> None:
        if self.read_only:
            raise RepositoryReadOnlyError(self._read_only_reason or "repository is read-only")

    @staticmethod
    def _validate_unique_names(themes: Iterable[ThemeDefinition]) -> None:
        seen = {theme_name_key(theme.name) for theme in BUILTIN_THEMES}
        for theme in themes:
            key = theme_name_key(theme.name)
            if key in seen:
                raise ThemeValidationError(f"theme name already exists: {theme.name}")
            seen.add(key)

    def commit_snapshot(
        self,
        themes: Iterable[ThemeDefinition],
        active_theme_id: str,
        *,
        expected_revision: int | None = None,
        extras: FrozenJsonMap | Mapping[str, Any] | None = None,
    ) -> ThemeState:
        with self._lock:
            self._ensure_writable()
            if self._write_in_progress:
                raise ReentrantWriteError("theme repository write is already in progress")
            expected = self._state.revision if expected_revision is None else expected_revision
            if expected != self._state.revision:
                raise RevisionConflictError(
                    f"expected revision {expected}, current revision is {self._state.revision}"
                )
            themes_tuple = tuple(themes)
            self._validate_unique_names(themes_tuple)
            candidate = ThemeState(
                revision=self._state.revision + 1,
                active_theme_id=active_theme_id,
                themes=themes_tuple,
                extras=self._state.extras if extras is None else _freeze_json(extras),
            )
            self._write_in_progress = True
            try:
                self._atomic_write(candidate)
            finally:
                self._write_in_progress = False
            self._state = candidate
            return candidate

    def _atomic_write(self, state: ThemeState) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        file_descriptor: int | None = None
        temporary_path: str | None = None
        try:
            file_descriptor, temporary_path = tempfile.mkstemp(
                prefix=".theme-state.", suffix=".tmp", dir=self.root
            )
            with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as handle:
                file_descriptor = None
                json.dump(state.to_dict(), handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.state_path)
            temporary_path = None
        finally:
            if file_descriptor is not None:
                os.close(file_descriptor)
            if temporary_path and os.path.exists(temporary_path):
                try:
                    os.remove(temporary_path)
                except OSError:
                    pass

    def create_custom_theme(
        self,
        name: str,
        colors: ColorPalette | Mapping[str, Any] | None = None,
        *,
        template: ThemeDefinition | None = None,
        background: BackgroundDefinition | Mapping[str, Any] | None = None,
        effects: EffectDefinition | Mapping[str, Any] | None = None,
        text_glow: TextGlowDefinition | Mapping[str, Any] | None = None,
        activate: bool = False,
        extras: Mapping[str, Any] | None = None,
    ) -> ThemeDefinition:
        base = template or self.active_theme()
        palette = colors or base.palette
        theme = ThemeDefinition.new_custom(
            name,
            palette,
            background=background if background is not None else base.background,
            effects=effects if effects is not None else base.effects,
            text_glow=text_glow if text_glow is not None else base.text_glow,
            extras=extras,
        )
        active_id = theme.id if activate else self._state.active_theme_id
        self.commit_snapshot((*self._state.themes, theme), active_id)
        return theme

    def update_custom_theme(self, theme_id: str, **changes: Any) -> ThemeDefinition:
        current = self.get(theme_id)
        if current is None:
            raise ThemeNotFoundError(theme_id)
        if current.readonly:
            raise ReadOnlyThemeError(f"builtin theme {theme_id} cannot be changed")
        if "name" in changes:
            changes["name"] = normalize_theme_name(changes["name"])
        updated = current.with_updates(**changes)
        themes = tuple(updated if theme.id == theme_id else theme for theme in self._state.themes)
        self.commit_snapshot(themes, self._state.active_theme_id)
        return updated

    def rename_custom_theme(self, theme_id: str, name: str) -> ThemeDefinition:
        return self.update_custom_theme(theme_id, name=name)

    def activate(self, theme_id: str, *, expected_revision: int | None = None) -> ThemeDefinition:
        theme = self.get(theme_id)
        if theme is None:
            raise ThemeNotFoundError(theme_id)
        self.commit_snapshot(self._state.themes, theme_id, expected_revision=expected_revision)
        return theme

    def delete_custom_theme(self, theme_id: str) -> bool:
        current = self.get(theme_id)
        if current is None:
            return False
        if current.readonly:
            raise ReadOnlyThemeError(f"builtin theme {theme_id} cannot be deleted")
        remaining = tuple(theme for theme in self._state.themes if theme.id != theme_id)
        active = DEFAULT_BUILTIN_ID if self._state.active_theme_id == theme_id else self._state.active_theme_id
        self.commit_snapshot(remaining, active)
        return True


def compatibility_projection(theme: ThemeDefinition) -> dict[str, str]:
    return {
        "current_theme": theme.name,
        "background_color": theme.palette.background,
        "card_background_color": theme.palette.card_background,
        "component_background_color": theme.palette.component_background,
        "highlight_button_color": theme.palette.highlight_button,
        "text_color": theme.palette.text_color,
        "notification_info_color": theme.palette.notification_info,
        "notification_warning_color": theme.palette.notification_warning,
        "notification_error_color": theme.palette.notification_error,
    }


__all__ = [
    "BACKGROUND_FIT_MODES", "BACKGROUND_POSITIONS", "BUILTIN_THEMES", "BUILTIN_THEME_BY_ID",
    "COLOR_KEYS", "CONTROL_CATEGORIES", "SCHEMA_VERSION", "BackgroundDefinition", "ColorPalette",
    "ControlToggles", "EffectDefinition", "FrozenJsonMap", "QuarantinedTheme", "ReadOnlyThemeError",
    "ReentrantWriteError", "RepositoryReadOnlyError", "RevisionConflictError", "TextGlowDefinition",
    "ThemeDefinition", "ThemeError", "ThemeNotFoundError", "ThemeRenderContext", "ThemeRepository",
    "ThemeState", "ThemeValidationError", "canonical_custom_theme_id", "compatibility_projection",
    "normalize_hex_color", "normalize_theme_name", "theme_name_key", "thaw_json", "utc_now_iso",
]

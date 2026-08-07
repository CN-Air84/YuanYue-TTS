"""Explicit page/surface markers used by the scoped appearance engine."""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QAbstractScrollArea,
    QAbstractSpinBox,
    QComboBox,
    QLineEdit,
    QScrollArea,
    QWidget,
)

from theme_manager import CONTROL_CATEGORIES


def composite_editor_owner(widget: QWidget) -> QWidget | None:
    """Return the native composite control that owns an embedded line edit."""
    if not isinstance(widget, QLineEdit):
        return None
    parent = widget.parentWidget()
    if isinstance(parent, QAbstractSpinBox):
        return parent if parent.lineEdit() is widget else None
    if isinstance(parent, QComboBox) and parent.isEditable():
        return parent if parent.lineEdit() is widget else None
    return None


def _set_transparent(widget: QWidget, property_name: str) -> QWidget:
    widget.setProperty(property_name, True)
    widget.setAutoFillBackground(False)
    return widget


def configure_transparent_root(widget: QWidget) -> QWidget:
    """Mark a main-page root as wallpaper-transparent."""
    widget.setProperty("themePageRoot", True)
    return _set_transparent(widget, "themeTransparentRoot")


def configure_transparent_container(widget: QWidget) -> QWidget:
    """Mark a layout/stack/scroll container that is not its own surface."""
    _set_transparent(widget, "themeTransparentContainer")
    if isinstance(widget, QAbstractScrollArea):
        viewport = widget.viewport()
        if viewport is not None:
            _set_transparent(viewport, "themeTransparentContainer")
    return widget


def set_transparent_scroll_content(
    scroll_area: QScrollArea,
    content: QWidget,
) -> QWidget:
    """Adopt scroll content, then undo Qt's automatic opaque background."""
    scroll_area.setWidget(content)
    configure_transparent_container(scroll_area)
    return configure_transparent_container(content)


def configure_theme_card(
    widget: QWidget,
    *,
    preserve_outline: bool = False,
) -> QWidget:
    """Mark a card whose backdrop must sample the nearest themed surface.

    Page-owned card outlines are removed by default so themed surfaces blend
    cleanly into the content area. Screens that intentionally own their card
    outlines, such as the streaming page, can explicitly preserve them.
    """
    widget.setProperty("themeCard", True)
    widget.setProperty("themeCardPreserveOutline", bool(preserve_outline))
    widget.setAutoFillBackground(False)
    return widget


def configure_semantic_surface(
    widget: QWidget,
    *,
    preserve_text_color: bool = False,
) -> QWidget:
    """Keep media/status/warning content opaque and outside visual effects."""
    widget.setProperty("themeSemanticSurface", True)
    widget.setProperty("themeEffectsRootDisabled", True)
    widget.setProperty("themeEffectDisabled", True)
    widget.setProperty("themeGlowDisabled", True)
    widget.setProperty("themePreserveTextColor", preserve_text_color)
    return widget


def configure_independent_surface(widget: QWidget) -> QWidget:
    """Mark a popup/dialog/tool surface that must never sample wallpaper."""
    configure_semantic_surface(widget)
    widget.setProperty("themeIndependentSurface", True)
    return widget


def configure_material_overlay(widget: QWidget) -> QWidget:
    """Let an embedded overlay's children sample the main-window material.

    The overlay itself keeps its page-owned dimming paint.  Unlike an
    independent popup, it remains in the theme traversal so cards and controls
    below it can use the shared surface provider.
    """
    widget.setProperty("themeMaterialOverlay", True)
    widget.setProperty("themeIndependentSurface", False)
    widget.setProperty("themeEffectsRootDisabled", False)
    widget.setProperty("themeEffectDisabled", True)
    widget.setProperty("themeGlowDisabled", True)
    return widget


def configure_effect_widget(
    widget: QWidget,
    *,
    category: str | None = None,
    effect_disabled: bool = False,
    glow_disabled: bool = False,
) -> QWidget:
    """Apply the public category/opt-out contract to an adapted widget."""
    if category is not None:
        if category not in CONTROL_CATEGORIES:
            raise ValueError(f"unsupported theme effect category: {category}")
        widget.setProperty("themeEffectCategory", category)
    widget.setProperty("themeEffectDisabled", bool(effect_disabled))
    widget.setProperty("themeGlowDisabled", bool(glow_disabled))
    return widget


__all__ = [
    "composite_editor_owner",
    "configure_effect_widget",
    "configure_independent_surface",
    "configure_material_overlay",
    "configure_semantic_surface",
    "configure_theme_card",
    "configure_transparent_container",
    "configure_transparent_root",
    "set_transparent_scroll_content",
]

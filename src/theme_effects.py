"""Scoped layered surfaces, glyph glow policy, and hover suspension."""

from __future__ import annotations

import math
import re
import weakref
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from PIL import Image, ImageChops, ImageFilter
from PyQt5 import sip
from PyQt5.QtCore import (
    QEvent,
    QObject,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    QTimer,
    Qt,
    pyqtProperty,
    pyqtSignal,
)
from PyQt5.QtGui import (
    QColor,
    QFontMetrics,
    QFontMetricsF,
    QImage,
    QPainter,
    QPainterPath,
    QPalette,
    QRegion,
)
from PyQt5.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QAbstractSlider,
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDial,
    QFrame,
    QGroupBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QProxyStyle,
    QPushButton,
    QRadioButton,
    QScrollBar,
    QSlider,
    QStyle,
    QStyleOption,
    QStyleOptionButton,
    QStyleOptionGroupBox,
    QStyleOptionToolButton,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QTextEdit,
    QToolButton,
    QWidget,
)

from theme_background import WeightedLRU, pil_to_qimage
from theme_manager import EffectDefinition, ThemeDefinition, ThemeRenderContext
from theme_page_adapter import composite_editor_owner


class EffectCategory(str, Enum):
    BUTTONS = "buttons"
    TEXT_INPUTS = "text_inputs"
    SELECTIONS = "selections"
    ITEM_VIEWS = "item_views"
    SCROLLBARS = "scrollbars"


EDITABLE_TEXT_TYPES = (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox)
CARD_CORNER_RADIUS = 8.0
CARD_TITLE_CORNER_RADIUS = 6.0
CARD_TITLE_PADDING_X = 12
CARD_TITLE_PADDING_Y = 4
CONTROL_CORNER_RADIUS = 6.0
_BORDER_RADIUS_DECLARATION = re.compile(
    r"\bborder-radius\s*:\s*(\d+(?:\.\d+)?)\s*px",
    re.IGNORECASE,
)


def uses_themed_control_surface(widget: QWidget) -> bool:
    """Return whether the theme engine should paint a full-widget surface.

    Sliders and scroll bars already paint their groove and handle as subcontrols.
    Painting an additional rounded surface behind the whole widget creates an
    unwanted background when hover suspension makes that surface opaque.
    """
    return not isinstance(widget, (QSlider, QScrollBar))


def surface_corner_radius(widget: QWidget, fallback: float) -> float:
    """Return the page-declared radius so backdrop and QSS clips stay aligned."""
    explicit = widget.property("themeCornerRadius")
    if explicit is not None:
        try:
            return max(0.0, float(explicit))
        except (TypeError, ValueError):
            pass
    match = _BORDER_RADIUS_DECLARATION.search(widget.styleSheet())
    if match is not None:
        return max(0.0, float(match.group(1)))
    return max(0.0, float(fallback))


def card_surface_rect(widget: QWidget) -> QRect:
    """Return the visual frame box painted by a themed card."""
    if isinstance(widget, QGroupBox):
        option = QStyleOptionGroupBox()
        widget.initStyleOption(option)
        frame_rect = widget.style().subControlRect(
            QStyle.CC_GroupBox,
            option,
            QStyle.SC_GroupBoxFrame,
            widget,
        ).intersected(widget.rect())
        if not frame_rect.isEmpty():
            return frame_rect
    return widget.rect()


def card_title_surface_rect(widget: QWidget) -> QRect:
    """Return the padded title chip painted by a themed group box."""
    if not isinstance(widget, QGroupBox) or not widget.title().strip():
        return QRect()
    option = QStyleOptionGroupBox()
    widget.initStyleOption(option)
    title_rect = widget.style().subControlRect(
        QStyle.CC_GroupBox,
        option,
        QStyle.SC_GroupBoxLabel,
        widget,
    )
    if widget.isCheckable():
        checkbox_rect = widget.style().subControlRect(
            QStyle.CC_GroupBox,
            option,
            QStyle.SC_GroupBoxCheckBox,
            widget,
        )
        title_rect = title_rect.united(checkbox_rect)
    return title_rect.adjusted(
        -CARD_TITLE_PADDING_X,
        -CARD_TITLE_PADDING_Y,
        CARD_TITLE_PADDING_X,
        CARD_TITLE_PADDING_Y,
    ).intersected(widget.rect())


def is_independent_surface(widget: QWidget, root: QWidget | None = None) -> bool:
    if isinstance(widget, QMenu):
        return True
    flags = widget.windowFlags()
    window_type = flags & Qt.WindowType_Mask
    if window_type in (Qt.Popup, Qt.ToolTip):
        return True
    if (
        bool(widget.property("themeMaterialOverlay"))
        and widget.parentWidget() is not None
        and window_type == Qt.SubWindow
    ):
        return False
    return widget.isWindow() and widget is not root


def classify_widget(widget: QWidget, root: QWidget | None = None) -> EffectCategory | None:
    if bool(widget.property("themeEffectDisabled")) or is_independent_surface(widget, root):
        return None
    if composite_editor_owner(widget) is not None:
        return None
    explicit = widget.property("themeEffectCategory")
    if explicit:
        try:
            return EffectCategory(str(explicit))
        except ValueError:
            return None
    if isinstance(widget, QScrollBar):
        return EffectCategory.SCROLLBARS
    if isinstance(widget, (QCheckBox, QRadioButton, QComboBox, QSlider, QDial)):
        return EffectCategory.SELECTIONS
    if isinstance(widget, EDITABLE_TEXT_TYPES):
        return EffectCategory.TEXT_INPUTS
    if isinstance(widget, (QAbstractItemView, QHeaderView)):
        return EffectCategory.ITEM_VIEWS
    if isinstance(widget, QAbstractButton):
        return EffectCategory.BUTTONS
    return None


def nearest_surface_ancestor(widget: QWidget, root: QWidget | None = None):
    current = widget.parentWidget()
    while current is not None:
        provider = getattr(current, "_theme_surface_provider", None)
        if provider is not None:
            return provider
        if current is root:
            break
        current = current.parentWidget()
    return getattr(root, "_theme_surface_provider", None) if root is not None else None


class RootSurfaceProvider:
    def __init__(
        self,
        frame_provider: Callable[[], Any],
        root_widget: QWidget | None = None,
    ):
        self._frame_provider = frame_provider
        self._root_ref = weakref.ref(root_widget) if root_widget is not None else None

    def paint_surface(self, painter: QPainter, target: QRectF, source: QRectF) -> bool:
        frame = self._frame_provider()
        if frame is None:
            return False
        frame.draw(
            painter,
            target,
            source,
            material="content",
            logical_source=True,
        )
        return True

    def paint_window_surface(
        self, painter: QPainter, target: QRectF, source: QRectF
    ) -> bool:
        return self.paint_surface(painter, target, source)

    def source_rect_for(self, widget: QWidget, rect: QRect) -> QRectF:
        root = self._root_ref() if self._root_ref is not None else None
        if root is not None and not sip.isdeleted(root):
            point = root.mapFromGlobal(widget.mapToGlobal(rect.topLeft()))
        else:
            point = widget.mapTo(widget.window(), rect.topLeft())
        return QRectF(point.x(), point.y(), rect.width(), rect.height())


class CardSurfaceProvider:
    """Compose parent material then card color directly into the caller painter."""

    def __init__(
        self,
        card_widget: QWidget,
        parent_provider: Any,
        theme_provider: Callable[[], ThemeDefinition],
    ):
        self.card_widget = card_widget
        self.parent_provider = parent_provider
        self.theme_provider = theme_provider

    def source_rect_for(self, widget: QWidget, rect: QRect) -> QRectF:
        window = widget.window()
        window_point = widget.mapTo(window, rect.topLeft())
        local_point = self.card_widget.mapFrom(window, window_point)
        return QRectF(
            local_point.x(), local_point.y(), rect.width(), rect.height()
        )

    def paint_surface(self, painter: QPainter, target: QRectF, source: QRectF) -> bool:
        root_point = self.card_widget.mapTo(
            self.card_widget.window(), source.topLeft().toPoint()
        )
        root_source = QRectF(
            root_point.x(), root_point.y(), source.width(), source.height()
        )
        return self.paint_window_surface(painter, target, root_source)

    def paint_window_surface(
        self, painter: QPainter, target: QRectF, source: QRectF
    ) -> bool:
        parent_paint = getattr(
            self.parent_provider,
            "paint_window_surface",
            getattr(self.parent_provider, "paint_surface", None),
        )
        painted = bool(parent_paint and parent_paint(painter, target, source))
        theme = self.theme_provider()
        color = QColor(theme.palette.card_background)
        effect_enabled = (
            theme.effects.content_enabled and theme.effects.cards_enabled
        )
        color.setAlphaF(theme.effects.content_opacity if effect_enabled else 1.0)
        painter.fillRect(target, color)
        return painted


class _FrostedCardRegionBackdrop(QWidget):
    def __init__(
        self,
        card_widget: QWidget,
        surface_provider: CardSurfaceProvider,
        rect_provider: Callable[[QWidget], QRect],
        radius_provider: Callable[[QWidget], float],
        *,
        paint_above_card: bool = False,
    ):
        # Keep the material behind the card itself. A child backdrop is always
        # painted after its parent and would cover QGroupBox borders and titles.
        super().__init__(card_widget.parentWidget())
        self._card_ref = weakref.ref(card_widget)
        self._rect_provider = rect_provider
        self._radius_provider = radius_provider
        self._paint_above_card = paint_above_card
        self._surface_rect = card_widget.rect()
        self._syncing_geometry = False
        self.setProperty("themeEffectsRootDisabled", True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self._theme_surface_provider = surface_provider
        self.sync_geometry()

    def sync_geometry(self) -> None:
        card_widget = self._card_ref()
        if (
            card_widget is None
            or sip.isdeleted(card_widget)
            or self._syncing_geometry
        ):
            return
        parent = card_widget.parentWidget()
        if parent is None:
            self.hide()
            return
        self._syncing_geometry = True
        try:
            if self.parentWidget() is not parent:
                self.setParent(parent)
            self._surface_rect = self._rect_provider(card_widget)
            if self._surface_rect.isEmpty():
                self.hide()
                return
            surface_top_left = card_widget.mapTo(
                parent,
                self._surface_rect.topLeft(),
            )
            self.setGeometry(QRect(surface_top_left, self._surface_rect.size()))
            self.setVisible(not card_widget.isHidden())
            if self._paint_above_card:
                self.raise_()
            else:
                self.stackUnder(card_widget)
        finally:
            self._syncing_geometry = False

    def paintEvent(self, event):
        card_widget = self._card_ref()
        if card_widget is None or sip.isdeleted(card_widget):
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        bounds = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = self._radius_provider(card_widget)
        radius = min(radius, max(0.0, bounds.width() / 2), max(0.0, bounds.height() / 2))
        clip = QPainterPath()
        clip.addRoundedRect(bounds, radius, radius)
        painter.setClipPath(clip, Qt.IntersectClip)
        self._theme_surface_provider.paint_surface(
            painter,
            QRectF(self.rect()),
            QRectF(self._surface_rect),
        )


class FrostedCardBackdrop(_FrostedCardRegionBackdrop):
    def __init__(
        self,
        card_widget: QWidget,
        parent_provider: Any,
        theme_provider: Callable[[], ThemeDefinition],
    ):
        surface_provider = CardSurfaceProvider(
            card_widget,
            parent_provider,
            theme_provider,
        )
        card_widget._theme_surface_provider = surface_provider
        super().__init__(
            card_widget,
            surface_provider,
            card_surface_rect,
            lambda widget: surface_corner_radius(widget, CARD_CORNER_RADIUS),
        )


class FrostedCardTitleBackdrop(_FrostedCardRegionBackdrop):
    def __init__(
        self,
        card_widget: QGroupBox,
        surface_provider: CardSurfaceProvider,
    ):
        super().__init__(
            card_widget,
            surface_provider,
            card_title_surface_rect,
            lambda _widget: CARD_TITLE_CORNER_RADIUS,
            paint_above_card=True,
        )

    def paintEvent(self, event):
        super().paintEvent(event)
        card_widget = self._card_ref()
        if card_widget is None or sip.isdeleted(card_widget):
            return
        option = QStyleOptionGroupBox()
        card_widget.initStyleOption(option)
        title_rect = card_widget.style().subControlRect(
            QStyle.CC_GroupBox,
            option,
            QStyle.SC_GroupBoxLabel,
            card_widget,
        )
        if title_rect.isEmpty():
            return
        title_rect.translate(-self._surface_rect.topLeft())
        painter = QPainter(self)
        painter.setFont(card_widget.font())
        card_widget.style().drawItemText(
            painter,
            title_rect,
            Qt.AlignLeft | Qt.AlignVCenter,
            option.palette,
            card_widget.isEnabled(),
            card_widget.title(),
            QPalette.WindowText,
        )


class FrostedControlBackdrop(QWidget):
    """Sibling surface used when QSS would otherwise swallow proxy painting."""

    def __init__(
        self,
        target: QWidget,
        category: EffectCategory,
        surface_style: "ThemeSurfaceStyle",
    ):
        super().__init__(target.parentWidget())
        self._target_ref = weakref.ref(target)
        self.category = category
        self.surface_style = surface_style
        self.setProperty("themeEffectsRootDisabled", True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.sync_geometry()

    def sync_geometry(self) -> None:
        target = self._target_ref()
        if target is None:
            return
        parent = target.parentWidget()
        if parent is None:
            self.hide()
            return
        if self.parentWidget() is not parent:
            self.setParent(parent)
        self.setGeometry(target.geometry())
        self.stackUnder(target)
        self.setVisible(not target.isHidden())

    def paintEvent(self, event):
        target = self._target_ref()
        if target is None:
            return
        option = QStyleOption()
        option.initFrom(target)
        option.rect = self.rect()
        if isinstance(target, QAbstractButton):
            if target.isDown():
                option.state |= QStyle.State_Sunken
            if target.isChecked():
                option.state |= QStyle.State_On
        elif isinstance(target, QAbstractSlider) and target.isSliderDown():
            option.state |= QStyle.State_Sunken
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self.surface_style.paint_control_surface(
            option,
            painter,
            target,
            self.category,
        )


def _linear_channel(value: int) -> float:
    channel = value / 255.0
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


@dataclass(frozen=True, slots=True)
class GlowMetrics:
    intensity: float
    radius: float


@dataclass(frozen=True, slots=True)
class GlyphGlowFrame:
    image: QImage
    logical_size: tuple[float, float]


class ThemeTextGlowPolicy:
    DARK_LUMINANCE_MAX = 0.45

    @staticmethod
    def luminance(color: QColor | str) -> float:
        parsed = QColor(color)
        if not parsed.isValid():
            return 1.0
        red, green, blue, _ = parsed.getRgb()
        return (
            0.2126 * _linear_channel(red)
            + 0.7152 * _linear_channel(green)
            + 0.0722 * _linear_channel(blue)
        )

    def metrics(self, context: ThemeRenderContext, font_size: float) -> GlowMetrics:
        glow = context.theme.text_glow
        minimum = context.minimum_font_size
        maximum = context.maximum_font_size
        factor = 0.0 if minimum == maximum else (
            min(max(font_size, minimum), maximum) - minimum
        ) / (maximum - minimum)
        return GlowMetrics(
            glow.minimum_intensity
            + (glow.maximum_intensity - glow.minimum_intensity) * factor,
            glow.minimum_radius + (glow.maximum_radius - glow.minimum_radius) * factor,
        )

    def supports_widget(
        self,
        widget: QWidget,
        effective_text_color: QColor | str,
        theme: ThemeDefinition,
    ) -> bool:
        if not theme.text_glow.enabled or bool(widget.property("themeGlowDisabled")):
            return False
        if float(widget.property("themeHoverProgress") or 0.0) >= 1.0:
            return False
        if isinstance(widget, EDITABLE_TEXT_TYPES):
            return False
        if isinstance(widget, QComboBox) and widget.isEditable():
            return False
        if not isinstance(widget, (QLabel, QAbstractButton, QAbstractItemView)):
            return False
        return self.luminance(effective_text_color) <= self.DARK_LUMINANCE_MAX

    @staticmethod
    def password_display_text(line_edit: QLineEdit) -> str:
        return line_edit.displayText()


class GlyphGlowRenderer:
    def __init__(
        self,
        maximum_cache_bytes: int = 32 * 1024 * 1024,
        *,
        cache: WeightedLRU | None = None,
    ):
        self.cache = cache if cache is not None else WeightedLRU(maximum_cache_bytes)

    @staticmethod
    def _qimage_to_pil(image: QImage) -> Image.Image:
        converted = image.convertToFormat(QImage.Format_RGBA8888)
        pointer = converted.bits()
        pointer.setsize(converted.byteCount())
        return Image.frombytes(
            "RGBA", (converted.width(), converted.height()), bytes(pointer), "raw", "RGBA"
        )

    def _glow_from_mask(self, mask: QImage, metrics: GlowMetrics, dpr: float) -> QImage:
        radius = max(0.0, metrics.radius * dpr)
        source_alpha = self._qimage_to_pil(mask).getchannel("A")
        blurred = source_alpha.filter(ImageFilter.GaussianBlur(radius))
        # Native painting owns the glyph core; the overlay contributes only halo.
        glow_alpha = ImageChops.subtract(blurred, source_alpha)
        intensity = min(max(metrics.intensity, 0.0), 1.0)
        glow_alpha = glow_alpha.point(lambda value: round(value * intensity))
        glow = Image.new("RGBA", glow_alpha.size, (255, 255, 255, 0))
        glow.putalpha(glow_alpha)
        rendered = pil_to_qimage(glow)
        rendered.setDevicePixelRatio(dpr)
        return rendered

    def render_mask(
        self,
        cache_key: tuple[Any, ...],
        logical_size: tuple[float, float],
        metrics: GlowMetrics,
        dpr: float,
        draw_mask: Callable[[QPainter], None],
    ) -> QImage:
        """Blur text painted in the native widget's own coordinate system."""
        dpr = max(0.01, float(dpr))
        logical_width = max(1.0, float(logical_size[0]))
        logical_height = max(1.0, float(logical_size[1]))
        key = (
            "native-text-mask",
            cache_key,
            round(logical_width, 4),
            round(logical_height, 4),
            round(dpr, 4),
            round(metrics.radius, 4),
            round(metrics.intensity, 4),
        )
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        mask = QImage(
            max(1, math.ceil(logical_width * dpr)),
            max(1, math.ceil(logical_height * dpr)),
            QImage.Format_RGBA8888,
        )
        mask.fill(0)
        painter = QPainter(mask)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.scale(dpr, dpr)
        draw_mask(painter)
        painter.end()
        rendered = self._glow_from_mask(mask, metrics, dpr)
        self.cache.put(key, rendered, rendered.width() * rendered.height() * 4)
        return rendered

    def render_image_mask(
        self,
        cache_key: tuple[Any, ...],
        metrics: GlowMetrics,
        dpr: float,
        create_mask: Callable[[], QImage],
    ) -> QImage:
        """Blur a pre-rendered native text mask, creating it only on cache miss."""
        dpr = max(0.01, float(dpr))
        key = (
            "native-image-mask",
            cache_key,
            round(dpr, 4),
            round(metrics.radius, 4),
            round(metrics.intensity, 4),
        )
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        mask = create_mask()
        rendered = self._glow_from_mask(mask, metrics, dpr)
        self.cache.put(key, rendered, rendered.width() * rendered.height() * 4)
        return rendered
    def render_frame(
        self, text: str, font, metrics: GlowMetrics, dpr: float
    ) -> GlyphGlowFrame:
        """Compatibility renderer for callers without a native paint primitive."""
        dpr = max(0.01, float(dpr))
        key = (
            "standalone-glyph", text, font.toString(), round(dpr, 4),
            round(metrics.radius, 4), round(metrics.intensity, 4),
        )
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        path = QPainterPath()
        path.addText(QPointF(0, 0), font, text)
        bounds = path.boundingRect()
        padding = max(2, math.ceil(max(0.0, metrics.radius * dpr) * 3) + 2)
        logical_padding = padding / dpr
        logical_width = max(1.0 / dpr, bounds.width() + logical_padding * 2)
        logical_height = max(1.0 / dpr, bounds.height() + logical_padding * 2)
        mask = QImage(
            max(1, math.ceil(logical_width * dpr)),
            max(1, math.ceil(logical_height * dpr)),
            QImage.Format_RGBA8888,
        )
        mask.fill(0)
        painter = QPainter(mask)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.scale(dpr, dpr)
        painter.fillPath(
            path.translated(logical_padding - bounds.left(), logical_padding - bounds.top()),
            QColor(255, 255, 255, 255),
        )
        painter.end()
        rendered = self._glow_from_mask(mask, metrics, dpr)
        frame = GlyphGlowFrame(rendered, (rendered.width() / dpr, rendered.height() / dpr))
        self.cache.put(key, frame, rendered.width() * rendered.height() * 4)
        return frame

    def render(self, text: str, font, metrics: GlowMetrics, dpr: float) -> QImage:
        return self.render_frame(text, font, metrics, dpr).image

    def clear(self) -> None:
        self.cache.clear()

class GlyphGlowOverlay(QWidget):
    """Mouse-transparent halo generated from the widget's native text layout."""

    def __init__(
        self,
        target: QWidget,
        theme_provider: Callable[[], ThemeDefinition],
        context_provider: Callable[[], ThemeRenderContext],
        renderer: GlyphGlowRenderer,
    ):
        super().__init__(target)
        self.target = target
        self.theme_provider = theme_provider
        self.context_provider = context_provider
        self.renderer = renderer
        self.policy = ThemeTextGlowPolicy()
        self.setObjectName("themeGlyphGlowOverlay")
        self.setProperty("themeEffectsRootDisabled", True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.NoFocus)
        target.installEventFilter(self)
        self.sync_geometry()
        self.raise_()
        self.show()

    def sync_geometry(self) -> None:
        try:
            self.setGeometry(self.target.rect())
            self.raise_()
        except RuntimeError:
            pass

    def display_text(self) -> str:
        if isinstance(self.target, QLabel):
            if self.target.textFormat() == Qt.RichText or self.target.wordWrap():
                return ""
            return self.target.text()
        if isinstance(self.target, QAbstractButton):
            return self.target.text().replace("&&", "\0").replace("&", "").replace("\0", "&")
        return ""

    def _label_text_rect(self) -> QRect:
        label = self.target
        rect = label.contentsRect().adjusted(
            label.margin(), label.margin(), -label.margin(), -label.margin()
        )
        indent = label.indent()
        if indent < 0 and label.frameWidth() > 0:
            indent = QFontMetrics(label.font()).horizontalAdvance("x") // 2
        if indent > 0:
            alignment = label.alignment()
            if alignment & Qt.AlignLeft:
                rect.adjust(indent, 0, 0, 0)
            elif alignment & Qt.AlignRight:
                rect.adjust(0, 0, -indent, 0)
            if alignment & Qt.AlignTop:
                rect.adjust(0, indent, 0, 0)
            elif alignment & Qt.AlignBottom:
                rect.adjust(0, 0, 0, -indent)
        return rect

    def _native_text_rect(self) -> QRect:
        target = self.target
        style = target.style()
        if isinstance(target, QLabel):
            return self._label_text_rect()
        if isinstance(target, QPushButton):
            option = QStyleOptionButton()
            target.initStyleOption(option)
            return style.subElementRect(QStyle.SE_PushButtonContents, option, target)
        if isinstance(target, QCheckBox):
            option = QStyleOptionButton()
            target.initStyleOption(option)
            return style.subElementRect(QStyle.SE_CheckBoxContents, option, target)
        if isinstance(target, QRadioButton):
            option = QStyleOptionButton()
            target.initStyleOption(option)
            return style.subElementRect(QStyle.SE_RadioButtonContents, option, target)
        if isinstance(target, QToolButton):
            option = QStyleOptionToolButton()
            target.initStyleOption(option)
            return style.subElementRect(QStyle.SE_ToolButtonLayoutItem, option, target)
        return target.contentsRect()

    def _native_widget_text_mask(self, dpr: float) -> QImage:
        """Extract dark text pixels from the target's actual native rendering."""
        dpr = max(0.01, float(dpr))
        width = max(1, math.ceil(self.target.width() * dpr))
        height = max(1, math.ceil(self.target.height() * dpr))
        rendered = QImage(width, height, QImage.Format_RGBA8888)
        rendered.fill(0)
        painter = QPainter(rendered)
        painter.scale(dpr, dpr)
        # Excluding children prevents this overlay from recursively rendering itself.
        self.target.render(
            painter,
            QPoint(0, 0),
            QRegion(),
            QWidget.DrawWindowBackground,
        )
        painter.end()

        source = self.renderer._qimage_to_pil(rendered)
        pixels = source.load()
        text_color = self.target.palette().color(self.target.foregroundRole())
        text_red, text_green, text_blue, _ = text_color.getRgb()
        logical_rect = self._native_text_rect().intersected(self.target.rect())
        left = max(0, math.floor(logical_rect.left() * dpr))
        top = max(0, math.floor(logical_rect.top() * dpr))
        right = min(width, math.ceil((logical_rect.right() + 1) * dpr))
        bottom = min(height, math.ceil((logical_rect.bottom() + 1) * dpr))

        tolerance = 96
        alpha = Image.new("L", (width, height), 0)
        alpha_pixels = alpha.load()
        for y in range(top, bottom):
            for x in range(left, right):
                red, green, blue, source_alpha = pixels[x, y]
                distance = max(
                    abs(red - text_red),
                    abs(green - text_green),
                    abs(blue - text_blue),
                )
                if source_alpha and distance < tolerance:
                    alpha_pixels[x, y] = round(
                        source_alpha * (tolerance - distance) / tolerance
                    )

        mask = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        mask.putalpha(alpha)
        result = pil_to_qimage(mask)
        result.setDevicePixelRatio(dpr)
        return result
    def _cache_key(self, text: str) -> tuple[Any, ...]:
        target = self.target
        state = (
            target.isEnabled(), target.layoutDirection(),
            target.isChecked() if isinstance(target, QAbstractButton) else False,
            target.isDown() if isinstance(target, QAbstractButton) else False,
            target.alignment() if isinstance(target, QLabel) else 0,
            target.margin() if isinstance(target, QLabel) else 0,
            target.indent() if isinstance(target, QLabel) else 0,
            target.toolButtonStyle() if isinstance(target, QToolButton) else 0,
        )
        return (
            "widget-native-text", target.metaObject().className(),
            target.style().metaObject().className(), target.objectName(),
            target.styleSheet(), text, target.font().toString(),
            target.width(), target.height(),
            target.palette().color(target.foregroundRole()).rgba(),
            target.palette().color(target.backgroundRole()).rgba(),
            # Custom-painted widgets use this token to invalidate moved glyphs.
            target.property("themeGlowContentRevision"),
            state,
        )

    def eventFilter(self, watched, event):
        if watched is self.target:
            if event.type() in {
                QEvent.Resize, QEvent.Show, QEvent.LayoutRequest, QEvent.ContentsRectChange,
            }:
                self.sync_geometry()
            elif event.type() in {
                QEvent.FontChange, QEvent.PaletteChange, QEvent.StyleChange,
                QEvent.EnabledChange, QEvent.DynamicPropertyChange,
            }:
                self.update()
        return False

    def paintEvent(self, event):
        text = self.display_text()
        if not text:
            return
        theme = self.theme_provider()
        color = self.target.palette().color(self.target.foregroundRole())
        if not self.policy.supports_widget(self.target, color, theme):
            return
        context = self.context_provider()
        point_size = self.target.font().pointSizeF()
        if point_size <= 0:
            point_size = QFontMetricsF(self.target.font()).height()
        image = self.renderer.render_image_mask(
            self._cache_key(text),
            self.policy.metrics(context, point_size),
            context.dpr,
            lambda: self._native_widget_text_mask(context.dpr),
        )
        progress = min(max(float(self.target.property("themeHoverProgress") or 0.0), 0.0), 1.0)
        painter = QPainter(self)
        painter.setOpacity(1.0 - progress)
        painter.drawImage(QPointF(0, 0), image)


class ThemedItemDelegate(QStyledItemDelegate):
    def __init__(
        self,
        theme_provider: Callable[[], ThemeDefinition],
        context_provider: Callable[[], ThemeRenderContext],
        renderer: GlyphGlowRenderer,
        base_delegate: QStyledItemDelegate | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.theme_provider = theme_provider
        self.context_provider = context_provider
        self.renderer = renderer
        self.base_delegate = base_delegate
        self.policy = ThemeTextGlowPolicy()

    def paint(self, painter, option, index):
        if self.base_delegate is not None:
            self.base_delegate.paint(painter, option, index)
        else:
            super().paint(painter, option, index)
        view = self.parent()
        if not isinstance(view, QAbstractItemView):
            return
        styled_option = QStyleOptionViewItem(option)
        self.initStyleOption(styled_option, index)
        text = styled_option.text
        color = styled_option.palette.color(QPalette.Text)
        context = self.context_provider()
        theme = self.theme_provider()
        if not text or not self.policy.supports_widget(view, color, theme):
            return
        text_rect = view.style().subElementRect(QStyle.SE_ItemViewItemText, styled_option, view)
        if not text_rect.isValid() or text_rect.isEmpty():
            return
        relative_text_rect = QRect(text_rect)
        relative_text_rect.translate(-option.rect.x(), -option.rect.y())
        flags = int(styled_option.displayAlignment)
        if styled_option.features & QStyleOptionViewItem.WrapText:
            display_text = text
            flags |= int(Qt.TextWordWrap)
        else:
            display_text = QFontMetrics(styled_option.font).elidedText(
                text, styled_option.textElideMode, max(0, text_rect.width())
            )
            flags |= int(Qt.TextSingleLine)
        font_size = styled_option.font.pointSizeF()
        if font_size <= 0:
            font_size = QFontMetricsF(styled_option.font).height()
        cache_key = (
            "item-native-text", view.metaObject().className(),
            view.style().metaObject().className(), view.styleSheet(), display_text,
            styled_option.font.toString(), option.rect.width(), option.rect.height(),
            relative_text_rect.x(), relative_text_rect.y(), relative_text_rect.width(),
            relative_text_rect.height(), flags, int(styled_option.state),
        )
        def draw_mask(mask_painter: QPainter) -> None:
            mask_painter.setFont(styled_option.font)
            view.style().drawItemText(
                mask_painter, relative_text_rect, flags, styled_option.palette,
                bool(styled_option.state & QStyle.State_Enabled), display_text, QPalette.Text,
            )
        image = self.renderer.render_mask(
            cache_key, (option.rect.width(), option.rect.height()),
            self.policy.metrics(context, font_size), context.dpr, draw_mask,
        )
        progress = float(view.property("themeHoverProgress") or 0.0)
        painter.save()
        painter.setOpacity(1.0 - min(max(progress, 0.0), 1.0))
        painter.drawImage(QPointF(option.rect.x(), option.rect.y()), image)
        painter.restore()

    def sizeHint(self, option, index):
        if self.base_delegate is not None:
            size = self.base_delegate.sizeHint(option, index)
        else:
            size = super().sizeHint(option, index)
        view = self.parent()
        if isinstance(view, QAbstractItemView) and bool(
            view.property("themeComboPopupView")
        ):
            size.setHeight(max(32, size.height()))
        return size

class HoverEffectController(QObject):
    progressChanged = pyqtSignal(float)

    def __init__(
        self,
        widget: QWidget,
        effects: EffectDefinition,
        *,
        surface_widget: QWidget | None = None,
    ):
        super().__init__(widget)
        self.widget = widget
        self.surface_widget = surface_widget or widget
        self.effects = effects
        self._progress = 0.0
        self._destroyed = False
        self.animation = QPropertyAnimation(self, b"progress", self)
        self.animation.setStartValue(0.0)
        widget.installEventFilter(self)
        widget.destroyed.connect(self._on_destroyed)
        widget.setProperty("themeHoverProgress", 0.0)
        if self.surface_widget is not widget:
            self.surface_widget.setProperty("themeHoverProgress", 0.0)

    @pyqtProperty(float, notify=progressChanged)
    def progress(self) -> float:
        return self._progress

    @progress.setter
    def progress(self, value: float) -> None:
        self._progress = min(max(float(value), 0.0), 1.0)
        if not self._destroyed:
            self.widget.setProperty("themeHoverProgress", self._progress)
            self.widget.update()
            if self.surface_widget is not self.widget:
                self.surface_widget.setProperty(
                    "themeHoverProgress", self._progress
                )
                self.surface_widget.update()
        self.progressChanged.emit(self._progress)

    @property
    def suspended(self) -> bool:
        return self._progress >= 1.0

    @property
    def blur_enabled(self) -> bool:
        return not self.suspended

    @property
    def glow_enabled(self) -> bool:
        return not self.suspended

    def update_effects(self, effects: EffectDefinition) -> None:
        self.effects = effects
        if not effects.hover_suspend_enabled:
            self._animate_to(0.0, 0)

    def eventFilter(self, watched, event):
        if watched is self.widget and self.effects.hover_suspend_enabled:
            if event.type() == QEvent.Enter:
                self._animate_to(1.0, self.effects.hover_enter_ms)
            elif event.type() == QEvent.Leave:
                self._animate_to(0.0, self.effects.hover_restore_ms)
        return False

    def _animate_to(self, target: float, duration: int) -> None:
        if self._destroyed:
            return
        self.animation.stop()
        if duration <= 0:
            self.progress = target
            return
        self.animation.setStartValue(self._progress)
        self.animation.setEndValue(target)
        self.animation.setDuration(max(0, int(duration)))
        self.animation.start()

    def _on_destroyed(self):
        self._destroyed = True
        self.animation.stop()


class ThemeSurfaceStyle(QProxyStyle):
    """Proxy installed only on the themed root, never QApplication-wide."""

    _SURFACE_PRIMITIVES = frozenset(
        value
        for value in (
            QStyle.PE_PanelButtonCommand,
            QStyle.PE_FrameLineEdit,
            getattr(QStyle, "PE_PanelLineEdit", None),
            QStyle.PE_PanelItemViewRow,
            getattr(QStyle, "PE_PanelItemViewItem", None),
        )
        if value is not None
    )

    def __init__(
        self,
        root: QWidget,
        theme_provider: Callable[[], ThemeDefinition],
        surface_base_colors: weakref.WeakKeyDictionary | None = None,
    ):
        # Passing QApplication.style() to QProxyStyle transfers ownership in
        # Qt 5 and can delete the global style when this scoped proxy dies.
        super().__init__()
        self.root = root
        self.theme_provider = theme_provider
        self.surface_base_colors = (
            surface_base_colors
            if surface_base_colors is not None
            else weakref.WeakKeyDictionary()
        )

    def _category(self, widget: QWidget | None) -> EffectCategory | None:
        if widget is None:
            return None
        category = classify_widget(widget, self.root)
        if category is not None:
            return category
        parent = widget.parentWidget()
        if isinstance(parent, QAbstractItemView) and widget is parent.viewport():
            return EffectCategory.ITEM_VIEWS
        return None

    def paint_control_surface(
        self,
        option,
        painter: QPainter,
        widget: QWidget,
        category: EffectCategory,
    ) -> None:
        if not uses_themed_control_surface(widget):
            return

        theme = self.theme_provider()
        effects = theme.effects
        target = QRectF(option.rect)
        progress = min(
            max(float(widget.property("themeHoverProgress") or 0.0), 0.0),
            1.0,
        )
        effect_enabled = (
            effects.content_enabled
            and effects.control_is_effective(category.value)
        )

        painter.save()
        radius = surface_corner_radius(widget, CONTROL_CORNER_RADIUS)
        radius = min(radius, max(0.0, target.width() / 2), max(0.0, target.height() / 2))
        clip = QPainterPath()
        clip.addRoundedRect(target, radius, radius)
        painter.setClipPath(clip, Qt.IntersectClip)
        if effect_enabled:
            provider = nearest_surface_ancestor(widget, self.root)
            if provider is not None:
                source_for = getattr(provider, "source_rect_for", None)
                if source_for is None:
                    point = widget.mapTo(widget.window(), option.rect.topLeft())
                    source = QRectF(
                        point.x(),
                        point.y(),
                        option.rect.width(),
                        option.rect.height(),
                    )
                else:
                    source = source_for(widget, option.rect)
                provider.paint_surface(
                    painter,
                    target,
                    source,
                )

        state = option.state
        styled_base = self.surface_base_colors.get(widget)
        if state & QStyle.State_On:
            color = QColor(theme.palette.highlight_button)
        elif state & QStyle.State_Sunken:
            color = QColor(styled_base or theme.palette.highlight_button)
            if styled_base is not None:
                color = color.darker(112)
        else:
            color = QColor(styled_base or theme.palette.component_background)
            if state & QStyle.State_MouseOver:
                color = color.lighter(104)
        base_alpha = effects.content_opacity if effect_enabled else 1.0
        color.setAlphaF(base_alpha + (1.0 - base_alpha) * progress)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(target, radius, radius)

        if state & QStyle.State_HasFocus:
            pen = QColor(theme.palette.highlight_button)
            pen.setAlphaF(0.9)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(
                target.adjusted(0.5, 0.5, -0.5, -0.5),
                radius,
                radius,
            )
        elif not state & QStyle.State_Enabled:
            disabled = QColor(theme.palette.text_color)
            disabled.setAlphaF(0.18)
            painter.fillRect(target, disabled)
        painter.restore()

    def drawPrimitive(self, element, option, painter, widget=None):
        category = self._category(widget)
        if category is not None and element in self._SURFACE_PRIMITIVES:
            self.paint_control_surface(option, painter, widget, category)
            return
        super().drawPrimitive(element, option, painter, widget)

    def drawControl(self, element, option, painter, widget=None):
        category = self._category(widget)
        if category is not None and element in {
            QStyle.CE_CheckBox,
            QStyle.CE_RadioButton,
        }:
            self.paint_control_surface(option, painter, widget, category)
        super().drawControl(element, option, painter, widget)

    def drawComplexControl(self, control, option, painter, widget=None):
        category = self._category(widget)
        if (
            category is not None
            and uses_themed_control_surface(widget)
            and control in {
                QStyle.CC_ComboBox,
                QStyle.CC_Slider,
                QStyle.CC_ScrollBar,
                QStyle.CC_SpinBox,
            }
        ):
            self.paint_control_surface(option, painter, widget, category)
        super().drawComplexControl(control, option, painter, widget)


class ThemeEffectInstaller(QObject):
    def __init__(
        self,
        root: QWidget,
        theme_provider: Callable[[], ThemeDefinition],
        context_provider: Callable[[], ThemeRenderContext] | None = None,
        *,
        glyph_cache: WeightedLRU | None = None,
    ):
        super().__init__(root)
        self.root = root
        self.theme_provider = theme_provider
        self.context_provider = context_provider or self._default_context
        self.installed_widgets: weakref.WeakSet[QWidget] = weakref.WeakSet()
        self.hover_controllers: weakref.WeakKeyDictionary[
            QWidget, HoverEffectController
        ] = weakref.WeakKeyDictionary()
        self.original_styles: weakref.WeakKeyDictionary[QWidget, Any] = (
            weakref.WeakKeyDictionary()
        )
        self.original_style_sheets: weakref.WeakKeyDictionary[QWidget, str] = (
            weakref.WeakKeyDictionary()
        )
        self._style_sheet_guard: weakref.WeakSet[QWidget] = weakref.WeakSet()
        self.card_backdrops: weakref.WeakKeyDictionary[
            QWidget, FrostedCardBackdrop
        ] = weakref.WeakKeyDictionary()
        self.card_title_backdrops: weakref.WeakKeyDictionary[
            QGroupBox, FrostedCardTitleBackdrop
        ] = weakref.WeakKeyDictionary()
        self.control_backdrops: weakref.WeakKeyDictionary[
            QWidget, FrostedControlBackdrop
        ] = weakref.WeakKeyDictionary()
        self.card_parent_providers: weakref.WeakKeyDictionary[QWidget, Any] = (
            weakref.WeakKeyDictionary()
        )
        self.glow_overlays: weakref.WeakKeyDictionary[
            QWidget, GlyphGlowOverlay
        ] = weakref.WeakKeyDictionary()
        self.item_delegates: weakref.WeakKeyDictionary[QAbstractItemView, Any] = (
            weakref.WeakKeyDictionary()
        )
        self.independent_surfaces: weakref.WeakSet[QWidget] = weakref.WeakSet()
        self.combo_popup_views: weakref.WeakKeyDictionary[
            QComboBox, QAbstractItemView
        ] = weakref.WeakKeyDictionary()
        # Qt owns combo popup containers privately.  Keep their Python wrappers
        # alive while the installer is active; recreating a wrapper in the
        # native Show/Resize callback is unstable on Windows Qt 5.
        self.combo_popup_containers: dict[QWidget, QAbstractItemView] = {}
        self._pending_combo_popup_masks: set[QWidget] = set()
        self.combo_popup_original_view_palettes: weakref.WeakKeyDictionary[
            QAbstractItemView, QPalette
        ] = weakref.WeakKeyDictionary()
        self.combo_popup_original_container_styles: weakref.WeakKeyDictionary[
            QWidget, str
        ] = weakref.WeakKeyDictionary()
        self.combo_popup_original_container_palettes: weakref.WeakKeyDictionary[
            QWidget, QPalette
        ] = weakref.WeakKeyDictionary()
        self.combo_popup_original_translucent: weakref.WeakKeyDictionary[
            QWidget, bool
        ] = weakref.WeakKeyDictionary()
        self.combo_popup_original_autofill: weakref.WeakKeyDictionary[
            QWidget, bool
        ] = weakref.WeakKeyDictionary()
        self.glyph_renderer = GlyphGlowRenderer(cache=glyph_cache)
        self._closed = False
        self.surface_base_colors: weakref.WeakKeyDictionary[QWidget, QColor] = (
            weakref.WeakKeyDictionary()
        )
        self.surface_style = ThemeSurfaceStyle(
            root,
            theme_provider,
            self.surface_base_colors,
        )
        self.surface_style.setParent(root)
        self.original_styles[root] = self._restorable_style(root)
        root.setStyle(self.surface_style)
        root.installEventFilter(self)
        self.install_subtree(root)

    def _restorable_style(self, widget: QWidget):
        current_style = widget.style()
        style_class = current_style.metaObject().className()
        if (
            current_style is self.surface_style
            or widget.styleSheet().strip()
            or style_class == "QStyleSheetStyle"
        ):
            # QStyleSheetStyle is a private wrapper whose native instance is
            # replaced by setStyle().  Retaining that wrapper for close()
            # leaves a dangling SIP object, so rebuild QSS on the app style.
            return QApplication.style()
        return current_style

    _BACKGROUND_DECLARATION = re.compile(
        r"\bbackground(?:-color)?\s*:\s*([^;}]+)",
        re.IGNORECASE,
    )

    @classmethod
    def _background_color_from_style(cls, style_sheet: str) -> QColor | None:
        match = cls._BACKGROUND_DECLARATION.search(style_sheet)
        if match is None:
            return None
        value = match.group(1).strip().lower()
        if value in {"none", "transparent"}:
            return None
        functional = re.fullmatch(
            r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)"
            r"(?:\s*,\s*(\d+(?:\.\d+)?))?\s*\)",
            value,
        )
        if functional is not None:
            red, green, blue = (int(functional.group(i)) for i in range(1, 4))
            alpha_text = functional.group(4)
            alpha = 255
            if alpha_text is not None:
                numeric_alpha = float(alpha_text)
                alpha = round(numeric_alpha * 255) if numeric_alpha <= 1 else round(numeric_alpha)
            color = QColor(red, green, blue, max(0, min(alpha, 255)))
            return color if color.alpha() else None
        color = QColor(value)
        return color if color.isValid() and color.alpha() else None

    def _remember_surface_base_color(
        self,
        widget: QWidget,
        style_sheet: str,
    ) -> None:
        if not isinstance(widget, QPushButton):
            self.surface_base_colors.pop(widget, None)
            return
        color = self._background_color_from_style(style_sheet)
        if color is None:
            self.surface_base_colors.pop(widget, None)
            return
        self.surface_base_colors[widget] = color

    def _ensure_control_backdrop(
        self,
        widget: QWidget,
        category: EffectCategory,
    ) -> None:
        if (
            not uses_themed_control_surface(widget)
            or bool(widget.property("themeComboPopupView"))
            or widget in self.control_backdrops
            or widget.parentWidget() is None
        ):
            return
        backdrop = FrostedControlBackdrop(widget, category, self.surface_style)
        self.control_backdrops[widget] = backdrop
        controller = self.hover_controllers.get(widget)
        if controller is not None:
            controller.progressChanged.connect(backdrop.update)

    def _ensure_card_backdrop(self, widget: QWidget) -> None:
        if (
            not bool(widget.property("themeCard"))
            or widget in self.card_backdrops
            or widget.parentWidget() is None
        ):
            return
        parent_provider = nearest_surface_ancestor(widget, self.root)
        self.card_parent_providers[widget] = parent_provider
        backdrop = FrostedCardBackdrop(
            widget,
            parent_provider,
            self.theme_provider,
        )
        self.card_backdrops[widget] = backdrop
        if isinstance(widget, QGroupBox):
            self.card_title_backdrops[widget] = FrostedCardTitleBackdrop(
                widget,
                backdrop._theme_surface_provider,
            )

    def _default_context(self) -> ThemeRenderContext:
        return ThemeRenderContext(
            self.theme_provider(),
            10,
            30,
            (max(1, self.root.width()), max(1, self.root.height())),
            float(self.root.devicePixelRatioF()),
            0,
        )

    def _configure_independent_surface(self, widget: QWidget) -> None:
        self.independent_surfaces.add(widget)
        widget.setProperty("themeIndependentSurface", True)
        widget.setProperty("themeEffectDisabled", True)
        widget.setProperty("themeGlowDisabled", True)
        palette = widget.palette()
        theme = self.theme_provider()
        for role, color in (
            (QPalette.Window, theme.palette.card_background),
            (QPalette.Base, theme.palette.component_background),
            (QPalette.Button, theme.palette.component_background),
            (QPalette.Text, theme.palette.text_color),
            (QPalette.WindowText, theme.palette.text_color),
            (QPalette.ButtonText, theme.palette.text_color),
            (QPalette.Highlight, theme.palette.highlight_button),
        ):
            palette.setColor(role, QColor(color))
        widget.setPalette(palette)
        widget.setAutoFillBackground(True)
        widget.update()

    def install_subtree(self, widget: QWidget) -> None:
        if bool(widget.property("themeEffectsRootDisabled")) or bool(widget.property("legacyPlugin")):
            widget.setProperty("themeEffectDisabled", True)
            if isinstance(widget, QAbstractButton):
                self._install_widget(widget)
            return
        if is_independent_surface(widget, self.root):
            self._configure_independent_surface(widget)
            return
        self._install_widget(widget)
        for child in widget.findChildren(QWidget, options=Qt.FindDirectChildrenOnly):
            self.install_subtree(child)

    def _install_widget(self, widget: QWidget) -> None:
        if widget in self.installed_widgets:
            return
        self.installed_widgets.add(widget)
        widget.installEventFilter(self)
        widget_ref = weakref.ref(widget)
        installer_ref = weakref.ref(self)

        def forget_destroyed_widget(_destroyed=None):
            installer = installer_ref()
            if installer is not None:
                installer._forget_destroyed_widget(widget_ref)

        widget.destroyed.connect(forget_destroyed_widget)
        self._ensure_card_backdrop(widget)

        composite_owner = composite_editor_owner(widget)
        if composite_owner is not None:
            widget.setProperty("themeCompositeEditor", True)
            widget.setProperty("resolvedThemeEffectCategory", None)

        category = classify_widget(widget, self.root)
        if category is not None:
            # Read the page-owned tint before replacing the widget style.
            # On Qt 5 a non-empty QSS is represented by QStyleSheetStyle;
            # querying that wrapper after setStyle(self.surface_style) can
            # race its native replacement and terminate the process.
            local_style_sheet = widget.styleSheet()
            if local_style_sheet.strip():
                self._remember_surface_base_color(widget, local_style_sheet)
            widget.setProperty("resolvedThemeEffectCategory", category.value)
            if widget not in self.original_styles:
                self.original_styles[widget] = self._restorable_style(widget)
            widget.setStyle(self.surface_style)
            target = widget.viewport() if isinstance(widget, QAbstractItemView) else widget
            if isinstance(widget, QAbstractItemView):
                target.setProperty("themeEffectCategory", category.value)
                target.setStyle(self.surface_style)
            if uses_themed_control_surface(widget):
                controller = HoverEffectController(
                    target,
                    self.theme_provider().effects,
                    surface_widget=widget,
                )
                self.hover_controllers[widget] = controller

        self._install_transparent_qss_override(widget, category)

        if (
            isinstance(widget, (QLabel, QAbstractButton))
            and not bool(widget.property("themeGlowDisabled"))
        ):
            overlay = GlyphGlowOverlay(
                widget,
                self.theme_provider,
                self.context_provider,
                self.glyph_renderer,
            )
            self.glow_overlays[widget] = overlay
            controller = self.hover_controllers.get(widget)
            if controller is not None:
                controller.progressChanged.connect(overlay.update)

        if isinstance(widget, QAbstractItemView):
            existing = widget.itemDelegate()
            if existing is not None and not isinstance(existing, ThemedItemDelegate):
                self.item_delegates[widget] = existing
            widget.setItemDelegate(
                ThemedItemDelegate(
                        self.theme_provider,
                        self.context_provider,
                        self.glyph_renderer,
                        existing,
                        widget,
                    )
                )

        if isinstance(widget, QComboBox):
            popup_view = widget.view()
            if popup_view is not None and popup_view not in self.installed_widgets:
                self._configure_combo_popup(widget, popup_view)
                self.install_subtree(popup_view)

    def _apply_combo_popup_palette(self, view: QAbstractItemView) -> None:
        if view not in self.combo_popup_original_view_palettes:
            self.combo_popup_original_view_palettes[view] = QPalette(view.palette())
        theme = self.theme_provider()
        text = QColor(theme.palette.text_color)
        highlight = QColor(theme.palette.highlight_button)
        component = QColor(theme.palette.component_background)
        # Combo popups live in Qt's private top-level popup window.  They must
        # remain fully opaque: sampling the main-window frosted surface from a
        # separate native window produces a misplaced/unblurred wallpaper patch.
        component.setAlpha(255)
        selected = QColor(highlight)
        selected.setAlpha(178)
        palette = QPalette(view.palette())
        for role, color in (
            (QPalette.Base, component),
            (QPalette.Window, component),
            (QPalette.Text, text),
            (QPalette.WindowText, text),
            (QPalette.Highlight, selected),
            (QPalette.HighlightedText, QColor("#000000")),
        ):
            palette.setColor(role, color)
        # A local stylesheet creates a QStyleSheetStyle wrapper around Qt's
        # private popup view. Parent re-polishing then feeds its StyleChange
        # back through the normal backdrop refresh while the native popup is
        # resizing. Keep live theme colors on the public palette API instead.
        view.setPalette(palette)

    def _configure_combo_popup(
        self,
        combo: QComboBox,
        popup_view: QAbstractItemView,
    ) -> None:
        popup_view.setProperty("themeComboPopupView", True)
        popup_view.setProperty("themeCornerRadius", 5.0)
        if not popup_view.objectName():
            popup_view.setObjectName(f"themeComboPopupView_{id(popup_view):x}")
        popup_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        popup_view.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        popup_view.setTextElideMode(Qt.ElideRight)
        if hasattr(popup_view, "setSpacing"):
            popup_view.setSpacing(2)

        self.combo_popup_views[combo] = popup_view
        self._bind_combo_popup_container(popup_view)

    def _bind_combo_popup_container(self, popup_view: QAbstractItemView) -> None:
        """Style the public view without owning Qt's private popup window.

        Paint styling stays on the public view.  The private container is held
        only to keep its SIP wrapper stable and to apply a native mask after
        Show/Resize handling has returned; translucency remains disabled.
        """
        self._remember_combo_popup_container(popup_view)
        self._apply_combo_popup_palette(popup_view)

    def _remember_combo_popup_container(
        self, popup_view: QAbstractItemView
    ) -> QWidget | None:
        try:
            container = popup_view.window()
        except RuntimeError:
            return None
        if (
            container is popup_view
            or not self._is_live_qobject(container)
        ):
            return None

        for existing, existing_view in list(self.combo_popup_containers.items()):
            if existing_view is popup_view and existing is not container:
                if self._is_live_qobject(existing):
                    try:
                        existing.clearMask()
                    except RuntimeError:
                        pass
                self._forget_combo_popup_container(existing)

        if container not in self.combo_popup_containers:
            self.combo_popup_containers[container] = popup_view
            self.combo_popup_original_container_styles[container] = (
                container.styleSheet()
            )
            self.combo_popup_original_container_palettes[container] = QPalette(
                container.palette()
            )
            self.combo_popup_original_translucent[container] = (
                container.testAttribute(Qt.WA_TranslucentBackground)
            )
            self.combo_popup_original_autofill[container] = (
                container.autoFillBackground()
            )
            installer_ref = weakref.ref(self)
            container_ref = weakref.ref(container)

            def forget_destroyed_container(_destroyed=None):
                installer = installer_ref()
                destroyed_container = container_ref()
                if installer is not None and destroyed_container is not None:
                    installer._forget_combo_popup_container(destroyed_container)

            container.destroyed.connect(forget_destroyed_container)
        return container

    def _forget_combo_popup_container(self, container: QWidget) -> None:
        self._pending_combo_popup_masks.discard(container)
        self.combo_popup_containers.pop(container, None)
        self.combo_popup_original_container_styles.pop(container, None)
        self.combo_popup_original_container_palettes.pop(container, None)
        self.combo_popup_original_translucent.pop(container, None)
        self.combo_popup_original_autofill.pop(container, None)

    def _schedule_combo_popup_mask(self, popup_view: QAbstractItemView) -> None:
        container = self._remember_combo_popup_container(popup_view)
        if container is None or container in self._pending_combo_popup_masks:
            return
        self._pending_combo_popup_masks.add(container)
        installer_ref = weakref.ref(self)
        container_ref = weakref.ref(container)

        def apply_mask():
            installer = installer_ref()
            popup_container = container_ref()
            if installer is None or popup_container is None:
                return
            installer._pending_combo_popup_masks.discard(popup_container)
            if installer._closed or not installer._is_live_qobject(popup_container):
                return
            if installer.combo_popup_containers.get(popup_container) is not popup_view:
                return
            installer._sync_combo_popup_mask(popup_container)

        # setMask() can recreate the native popup window on Windows.  Running
        # it inside Qt's private Show/Resize stack can terminate the process.
        QTimer.singleShot(0, apply_mask)

    @staticmethod
    def _sync_combo_popup_mask(container: QWidget) -> None:
        rect = QRectF(container.rect()).adjusted(0.0, 0.0, -0.5, -0.5)
        if rect.isEmpty():
            return
        path = QPainterPath()
        path.addRoundedRect(rect, 9.0, 9.0)
        container.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def _install_transparent_qss_override(
        self,
        widget: QWidget,
        category: EffectCategory | None,
    ) -> None:
        if composite_editor_owner(widget) is not None:
            if (
                "/* theme-engine: composite editor is painted by its owner */"
                in widget.styleSheet()
            ):
                return
            if widget in self.original_style_sheets:
                return
            self.original_style_sheets[widget] = widget.styleSheet()
            self._append_composite_editor_qss_override(widget)
            return

        explicitly_transparent = any(
            bool(widget.property(name))
            for name in (
                "themeTransparentRoot",
                "themeTransparentContainer",
                "themeCard",
            )
        )
        force_black_button_text = (
            isinstance(widget, QAbstractButton)
            and not bool(widget.property("themePreserveTextColor"))
        )
        # A widget with no local QSS is normally already painted by the proxy
        # style. A matching ancestor selector sets WA_StyledBackground without
        # changing widget.styleSheet(); explicit surfaces in that state need a
        # local override to reveal their backdrop.
        local_style_sheet = widget.styleSheet()
        if explicitly_transparent and not local_style_sheet.strip():
            widget.ensurePolished()
        inherited_styled_background = (
            explicitly_transparent
            and widget.testAttribute(Qt.WA_StyledBackground)
        )
        if not local_style_sheet.strip() and not inherited_styled_background:
            return
        if category is None and not explicitly_transparent and not force_black_button_text:
            return
        if widget in self.original_style_sheets:
            return

        original_style_sheet = local_style_sheet
        self.original_style_sheets[widget] = original_style_sheet
        popup_view = (
            isinstance(widget, QAbstractItemView)
            and bool(widget.property("themeComboPopupView"))
        )
        if category is not None and not popup_view:
            self._ensure_control_backdrop(widget, category)
        self._append_transparent_qss_override(
            widget,
            category,
            # The combo popup view owns its own opaque surface.  Do not add the
            # transparent-surface override used by normal themed item views;
            # the popup container is intentionally left native and untouched.
            transparent_surface=(
                not popup_view
                and (category is not None or explicitly_transparent)
            ),
        )

    def _append_composite_editor_qss_override(self, widget: QLineEdit) -> None:
        base_style_sheet = self.original_style_sheets.get(widget, widget.styleSheet())
        object_name = widget.objectName()
        if not object_name:
            object_name = f"themeCompositeEditor_{id(widget):x}"
            widget.setObjectName(object_name)
        selectors = ",\n".join(
            f"#{object_name}{state}"
            for state in ("", ":hover", ":focus", ":disabled")
        )
        override = f"""
/* theme-engine: composite editor is painted by its owner */
{selectors} {{
    background: transparent;
    background-color: transparent;
    border: none;
    border-radius: 0px;
    margin: 0px;
    padding: 0px;
    min-height: 0px;
    outline: none;
}}
"""
        self._style_sheet_guard.add(widget)
        try:
            widget.setStyleSheet(base_style_sheet + override)
        finally:
            self._style_sheet_guard.discard(widget)

    def _append_transparent_qss_override(
        self,
        widget: QWidget,
        category: EffectCategory | None,
        *,
        transparent_surface: bool,
    ) -> None:
        base_style_sheet = self.original_style_sheets.get(widget, widget.styleSheet())
        object_name = widget.objectName()
        if not object_name:
            object_name = f"themeSurface_{id(widget):x}"
            widget.setObjectName(object_name)
        base_selectors = [f"#{object_name}"]
        for widget_type in type(widget).__mro__:
            try:
                is_widget_type = issubclass(widget_type, QWidget)
            except TypeError:
                is_widget_type = False
            if not is_widget_type:
                continue
            selector = f"{widget_type.__name__}#{object_name}"
            if selector not in base_selectors:
                base_selectors.append(selector)
        selectors = list(base_selectors)
        if category is not None or isinstance(widget, QAbstractButton):
            selectors.extend(
                f"{base_selector}{state}"
                for base_selector in base_selectors
                for state in (
                    ":hover",
                    ":pressed",
                    ":checked",
                    ":focus",
                    ":disabled",
                )
            )
        declarations = []
        if transparent_surface:
            declarations.extend((
                "background: transparent",
                "background-color: transparent",
            ))
        if (
            isinstance(widget, QAbstractButton)
            and not bool(widget.property("themePreserveTextColor"))
        ):
            declarations.append("color: #000000")
        borderless_card = (
            bool(widget.property("themeCard"))
            and not bool(widget.property("themeCardPreserveOutline"))
        )
        if borderless_card:
            declarations.append("border: none")
        override = (
            "\n/* theme-engine: the scoped style paints this surface */\n"
            + ",\n".join(selectors)
            + " { "
            + "; ".join(declarations)
            + "; }\n"
        )
        if isinstance(widget, QGroupBox) and bool(widget.property("themeCard")):
            title_declarations = [
                "background: transparent",
                "background-color: transparent",
            ]
            if borderless_card:
                title_declarations.append("border: none")
            override += (
                f"QGroupBox#{object_name}::title "
                "{ "
                + "; ".join(title_declarations)
                + "; }\n"
            )
        if category is EffectCategory.ITEM_VIEWS and transparent_surface:
            override += (
                f"#{object_name}::item, #{object_name}::item:hover "
                "{ background: transparent; background-color: transparent; }\n"
            )
        self._style_sheet_guard.add(widget)
        try:
            widget.setStyleSheet(base_style_sheet + override)
        finally:
            self._style_sheet_guard.discard(widget)

    def _forget_destroyed_widget(self, widget_ref) -> None:
        widget = widget_ref()
        if widget is None:
            return
        control_backdrop = self.control_backdrops.pop(widget, None)
        if self._is_live_qobject(control_backdrop):
            try:
                control_backdrop.hide()
                control_backdrop.setUpdatesEnabled(False)
                control_backdrop.setParent(None)
                control_backdrop.deleteLater()
            except RuntimeError:
                pass
        self.installed_widgets.discard(widget)
        self.hover_controllers.pop(widget, None)
        self.original_styles.pop(widget, None)
        self.original_style_sheets.pop(widget, None)
        self._style_sheet_guard.discard(widget)
        title_backdrop = self.card_title_backdrops.pop(widget, None)
        self._dispose_card_backdrop(title_backdrop)
        card_backdrop = self.card_backdrops.pop(widget, None)
        self._dispose_card_backdrop(card_backdrop)
        self.card_parent_providers.pop(widget, None)
        self.glow_overlays.pop(widget, None)
        self.item_delegates.pop(widget, None)
        self.independent_surfaces.discard(widget)
        self.surface_base_colors.pop(widget, None)

    @staticmethod
    def _is_live_qobject(value) -> bool:
        return value is not None and not sip.isdeleted(value)

    def _dispose_card_backdrop(self, backdrop) -> None:
        if not self._is_live_qobject(backdrop):
            return
        try:
            backdrop.hide()
            backdrop.setUpdatesEnabled(False)
            provider = getattr(backdrop, "_theme_surface_provider", None)
            if provider is not None:
                provider.card_widget = None
                backdrop._theme_surface_provider = None
            backdrop.setParent(None)
            backdrop.deleteLater()
        except RuntimeError:
            pass

    def _live_adapter_values(self, mapping):
        for widget, adapter in list(mapping.items()):
            if not self._is_live_qobject(widget):
                self._forget_destroyed_widget(weakref.ref(widget))
                continue
            if not self._is_live_qobject(adapter):
                mapping.pop(widget, None)
                continue
            yield adapter

    def update_theme(self, theme: ThemeDefinition) -> None:
        if self._closed or sip.isdeleted(self):
            return
        for controller in self._live_adapter_values(self.hover_controllers):
            controller.update_effects(theme.effects)
        for surface in list(self.independent_surfaces):
            if not self._is_live_qobject(surface):
                self.independent_surfaces.discard(surface)
                continue
            self._configure_independent_surface(surface)
        for backdrop in self._live_adapter_values(self.card_backdrops):
            backdrop.update()
        for backdrop in self._live_adapter_values(self.card_title_backdrops):
            backdrop.update()
        for backdrop in self._live_adapter_values(self.control_backdrops):
            backdrop.update()
        for combo, popup_view in list(self.combo_popup_views.items()):
            if not self._is_live_qobject(combo) or not self._is_live_qobject(popup_view):
                self.combo_popup_views.pop(combo, None)
                continue
            self._remember_combo_popup_container(popup_view)
            self._apply_combo_popup_palette(popup_view)
        for overlay in self._live_adapter_values(self.glow_overlays):
            overlay.update()
        for widget in list(self.installed_widgets):
            if not self._is_live_qobject(widget):
                self._forget_destroyed_widget(weakref.ref(widget))
                continue
            widget.update()

    def invalidate_glyph_cache(self) -> None:
        if self._closed or sip.isdeleted(self):
            return
        self.glyph_renderer.clear()
        for overlay in self._live_adapter_values(self.glow_overlays):
            overlay.update()
        for view, delegate in list(self.item_delegates.items()):
            if not self._is_live_qobject(view):
                self._forget_destroyed_widget(weakref.ref(view))
                continue
            if not self._is_live_qobject(delegate):
                self.item_delegates.pop(view, None)
                continue
            viewport = view.viewport()
            if self._is_live_qobject(viewport):
                viewport.update()

    def eventFilter(self, watched, event):
        if isinstance(watched, QComboBox) and event.type() == QEvent.Wheel:
            return True
        composite_owner = (
            composite_editor_owner(watched)
            if isinstance(watched, QWidget)
            else None
        )
        if composite_owner is not None:
            if event.type() == QEvent.Enter:
                controller = self.hover_controllers.get(composite_owner)
                if controller is not None:
                    controller.eventFilter(controller.widget, event)
            elif event.type() in {QEvent.FocusIn, QEvent.FocusOut}:
                composite_owner.update()
                backdrop = self.control_backdrops.get(composite_owner)
                if backdrop is not None:
                    backdrop.update()
        if (
            isinstance(watched, QWidget)
            and event.type() == QEvent.DynamicPropertyChange
            and bytes(event.propertyName())
            in {b"themeCard", b"themeCardPreserveOutline"}
            and bool(watched.property("themeCard"))
        ):
            self._ensure_card_backdrop(watched)
            category = classify_widget(watched, self.root)
            if watched in self.original_style_sheets:
                self._append_transparent_qss_override(
                    watched,
                    category,
                    transparent_surface=True,
                )
            else:
                self._install_transparent_qss_override(watched, category)
        if (
            isinstance(watched, QAbstractItemView)
            and bool(watched.property("themeComboPopupView"))
            and event.type() in {QEvent.Show, QEvent.Resize}
        ):
            self._schedule_combo_popup_mask(watched)
        if (
            isinstance(watched, QWidget)
            and event.type() == QEvent.StyleChange
            and watched not in self._style_sheet_guard
            and not bool(watched.property("themeComboPopupView"))
        ):
            category = classify_widget(watched, self.root)
            if composite_editor_owner(watched) is not None:
                current_style_sheet = watched.styleSheet()
                if (
                    "/* theme-engine: composite editor is painted by its owner */"
                    not in current_style_sheet
                ):
                    self.original_style_sheets[watched] = current_style_sheet
                    self._append_composite_editor_qss_override(watched)
            elif watched in self.original_style_sheets:
                self._refresh_style_sheet(watched)
            elif watched.styleSheet().strip() and (
                category is not None
                or any(
                    bool(watched.property(name))
                    for name in (
                        "themeTransparentRoot",
                        "themeTransparentContainer",
                        "themeCard",
                    )
                )
            ):
                self._install_transparent_qss_override(watched, category)
        if event.type() == QEvent.ChildPolished:
            child = event.child()
            if isinstance(child, QWidget):
                self.install_subtree(child)

        backdrop = self.card_backdrops.get(watched)
        if backdrop is not None:
            if event.type() in {
                QEvent.Move,
                QEvent.Resize,
                QEvent.Show,
                QEvent.LayoutRequest,
                QEvent.ParentChange,
                QEvent.StyleChange,
                QEvent.ZOrderChange,
            }:
                backdrop.sync_geometry()
            elif event.type() == QEvent.Hide:
                backdrop.hide()

        title_backdrop = self.card_title_backdrops.get(watched)
        if title_backdrop is not None:
            if event.type() in {
                QEvent.Move,
                QEvent.Resize,
                QEvent.Show,
                QEvent.LayoutRequest,
                QEvent.ParentChange,
                QEvent.StyleChange,
                QEvent.FontChange,
                QEvent.ZOrderChange,
            }:
                title_backdrop.sync_geometry()
            elif event.type() == QEvent.Hide:
                title_backdrop.hide()

        control_backdrop = self.control_backdrops.get(watched)
        if control_backdrop is not None:
            if event.type() in {
                QEvent.Move,
                QEvent.Resize,
                QEvent.Show,
                QEvent.LayoutRequest,
                QEvent.ParentChange,
            }:
                control_backdrop.sync_geometry()
            elif event.type() == QEvent.Hide:
                control_backdrop.hide()
            elif event.type() in {
                QEvent.EnabledChange,
                QEvent.FocusIn,
                QEvent.FocusOut,
                QEvent.Enter,
                QEvent.Leave,
                QEvent.MouseButtonPress,
                QEvent.MouseButtonRelease,
                QEvent.StyleChange,
            }:
                control_backdrop.update()
        return False

    def _refresh_style_sheet(self, target: QWidget) -> None:
        if (
            not self._is_live_qobject(target)
            or target not in self.original_style_sheets
            or bool(target.property("themeComboPopupView"))
        ):
            return
        current_style_sheet = target.styleSheet()
        if any(
            marker in current_style_sheet
            for marker in (
                "/* theme-engine: the scoped style paints this surface */",
                "/* theme-engine: composite editor is painted by its owner */",
            )
        ):
            return
        if composite_editor_owner(target) is not None:
            self.original_style_sheets[target] = current_style_sheet
            self._append_composite_editor_qss_override(target)
            return
        category = classify_widget(target, self.root)
        self.original_style_sheets[target] = current_style_sheet
        if category is not None:
            self._remember_surface_base_color(target, current_style_sheet)
            self._ensure_control_backdrop(target, category)
        explicitly_transparent = any(
            bool(target.property(name))
            for name in (
                "themeTransparentRoot",
                "themeTransparentContainer",
                "themeCard",
            )
        )
        self._append_transparent_qss_override(
            target,
            category,
            transparent_surface=(category is not None or explicitly_transparent),
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        root = self.root
        try:
            root.removeEventFilter(self)
        except RuntimeError:
            pass
        for view, delegate in list(self.item_delegates.items()):
            if not self._is_live_qobject(view):
                continue
            try:
                view.setItemDelegate(delegate)
            except RuntimeError:
                pass
        self.item_delegates.clear()
        for controller in list(self.hover_controllers.values()):
            try:
                controller._destroyed = True
                controller.animation.stop()
                controller.widget.removeEventFilter(controller)
                controller.setParent(None)
            except RuntimeError:
                pass
        for widget, overlay in list(self.glow_overlays.items()):
            if not self._is_live_qobject(widget) or not self._is_live_qobject(overlay):
                continue
            try:
                widget.removeEventFilter(overlay)
                overlay.hide()
                overlay.setUpdatesEnabled(False)
                overlay.setParent(None)
                overlay.deleteLater()
            except RuntimeError:
                pass
        self.glow_overlays.clear()
        for backdrop in list(self.control_backdrops.values()):
            if not self._is_live_qobject(backdrop):
                continue
            try:
                backdrop.hide()
                backdrop.setUpdatesEnabled(False)
                backdrop.setParent(None)
                backdrop.deleteLater()
            except RuntimeError:
                pass
        self.control_backdrops.clear()
        for backdrop in list(self.card_title_backdrops.values()):
            self._dispose_card_backdrop(backdrop)
        self.card_title_backdrops.clear()
        for widget, backdrop in list(self.card_backdrops.items()):
            if self._is_live_qobject(widget):
                try:
                    original = self.card_parent_providers.get(widget)
                    if original is None:
                        if hasattr(widget, "_theme_surface_provider"):
                            delattr(widget, "_theme_surface_provider")
                    else:
                        widget._theme_surface_provider = original
                except RuntimeError:
                    pass
            self._dispose_card_backdrop(backdrop)
        self.card_backdrops.clear()
        self.card_parent_providers.clear()
        for widget in list(self.installed_widgets):
            if not self._is_live_qobject(widget):
                continue
            try:
                widget.removeEventFilter(self)
                if widget in self.original_style_sheets:
                    widget.setStyleSheet(self.original_style_sheets[widget])
                original_style = self.original_styles.get(widget)
                if (
                    self._is_live_qobject(original_style)
                    and original_style is not self.surface_style
                    # Child controls inherit the root's scoped proxy style.
                    # Reinstalling saved child QStyle wrappers during teardown
                    # can race Qt's native popup/card lifecycle and crash.
                    and widget is root
                ):
                    widget.setStyle(original_style)
            except RuntimeError:
                pass
        for container, popup_view in list(self.combo_popup_containers.items()):
            if not self._is_live_qobject(container):
                continue
            try:
                container.removeEventFilter(self)
                container.clearMask()
                container.setStyleSheet(
                    self.combo_popup_original_container_styles.get(container, "")
                )
                original_container_palette = (
                    self.combo_popup_original_container_palettes.get(container)
                )
                if original_container_palette is not None:
                    container.setPalette(original_container_palette)
                container.setAttribute(
                    Qt.WA_TranslucentBackground,
                    self.combo_popup_original_translucent.get(container, False),
                )
                container.setAutoFillBackground(
                    self.combo_popup_original_autofill.get(container, False)
                )
                if self._is_live_qobject(popup_view):
                    original_palette = self.combo_popup_original_view_palettes.get(
                        popup_view
                    )
                    if original_palette is not None:
                        popup_view.setPalette(original_palette)
            except RuntimeError:
                pass
        self.surface_base_colors.clear()
        self.installed_widgets.clear()
        self.hover_controllers.clear()
        self.original_styles.clear()
        self.original_style_sheets.clear()
        self._style_sheet_guard.clear()
        self.independent_surfaces.clear()
        self.combo_popup_views.clear()
        self.combo_popup_containers.clear()
        self._pending_combo_popup_masks.clear()
        self.combo_popup_original_view_palettes.clear()
        self.combo_popup_original_container_styles.clear()
        self.combo_popup_original_container_palettes.clear()
        self.combo_popup_original_translucent.clear()
        self.combo_popup_original_autofill.clear()
        self.surface_style.root = None
        self.surface_style.setParent(None)
        self.root = None
        self.setParent(None)


SELECTION_SUBCONTROLS = {
    "checkbox": ("indicator", "label"),
    "radio": ("indicator", "label"),
    "slider": ("groove", "handle"),
    "combo": ("frame", "arrow", "popup"),
}
ITEM_VIEW_SUBCONTROLS = ("viewport", "delegate", "header", "editor", "scrollbar")


__all__ = [
    "CardSurfaceProvider",
    "EffectCategory",
    "FrostedCardBackdrop",
    "FrostedCardTitleBackdrop",
    "FrostedControlBackdrop",
    "GlyphGlowFrame",
    "GlyphGlowOverlay",
    "GlowMetrics",
    "GlyphGlowRenderer",
    "HoverEffectController",
    "ITEM_VIEW_SUBCONTROLS",
    "RootSurfaceProvider",
    "SELECTION_SUBCONTROLS",
    "ThemeEffectInstaller",
    "ThemeSurfaceStyle",
    "ThemeTextGlowPolicy",
    "ThemedItemDelegate",
    "card_title_surface_rect",
    "classify_widget",
    "composite_editor_owner",
    "is_independent_surface",
    "nearest_surface_ancestor",
]



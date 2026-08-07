"""Theme composition root and strict startup-blur hand-off for MainWindow."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from PyQt5.QtCore import QObject, QRectF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import QWidget

from theme_assets import ThemeAssetStore
from theme_background import BackgroundComposer, RenderedFrame, ThemeRenderEngine
from theme_draft import ThemeDraftController
from theme_effects import RootSurfaceProvider, ThemeEffectInstaller
from theme_manager import ThemeRenderContext, ThemeRepository, compatibility_projection
from theme_migration import migrate_legacy_settings
from theme_service import ThemeCommitEvent, ThemePreviewEvent, ThemeService


# The page adapters are migrated. Keep the environment flag as an internal
# rollback switch, but ship the revised theme engine enabled by default.
THEME_ENGINE_ENABLED_DEFAULT = True
THEME_ENGINE_ENVIRONMENT_FLAG = "YUANYUE_THEME_ENGINE"


def theme_engine_feature_enabled(environment: dict[str, str] | None = None) -> bool:
    environment = os.environ if environment is None else environment
    raw = environment.get(THEME_ENGINE_ENVIRONMENT_FLAG)
    if raw is None:
        return THEME_ENGINE_ENABLED_DEFAULT
    return str(raw).strip().casefold() in {"1", "true", "yes", "on"}


class ThemeBackgroundLayer(QWidget):
    def __init__(self, parent: QWidget, theme_provider):
        super().__init__(parent)
        self.theme_provider = theme_provider
        self.frame: RenderedFrame | None = None
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.NoFocus)

    def set_frame(self, frame: RenderedFrame) -> None:
        self.frame = frame
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.frame is not None:
            self.frame.draw(painter, QRectF(self.rect()))
        else:
            painter.fillRect(self.rect(), QColor(self.theme_provider().palette.background))


class SidebarMaterialLayer(ThemeBackgroundLayer):
    def paintEvent(self, event):
        theme = self.theme_provider()
        painter = QPainter(self)
        if self.frame is not None and theme.effects.sidebar_enabled:
            self.frame.draw(
                painter,
                QRectF(self.rect()),
                QRectF(0, 0, self.width(), self.height()),
                material="sidebar",
                logical_source=True,
            )
            overlay = QColor(theme.palette.card_background)
            overlay.setAlphaF(theme.effects.sidebar_opacity)
            painter.fillRect(self.rect(), overlay)
        else:
            painter.fillRect(self.rect(), QColor(theme.palette.card_background))


class _FrameBridge(QObject):
    frame_ready = pyqtSignal(object)


class ThemeRuntime:
    def __init__(
        self,
        service: ThemeService,
        settings_manager: Any,
        asset_store: ThemeAssetStore,
        composer: BackgroundComposer,
        render_engine: ThemeRenderEngine,
        draft_controller: ThemeDraftController,
        *,
        feature_enabled: bool,
        stabilization_delay_ms: int = 20,
    ):
        self.service = service
        self.settings_manager = settings_manager
        self.asset_store = asset_store
        self.composer = composer
        self.render_engine = render_engine
        self.draft_controller = draft_controller
        self.feature_enabled = bool(feature_enabled)
        self.stabilization_delay_ms = max(0, int(stabilization_delay_ms))
        self.window: QWidget | None = None
        self.background_layer: ThemeBackgroundLayer | None = None
        self.sidebar_layer: SidebarMaterialLayer | None = None
        self.effect_installer: ThemeEffectInstaller | None = None
        self.engine_enabled = False
        self.startup_blur_removed = False
        self._render_revision = 0
        self._closed = False
        self._frame_bridge = _FrameBridge()
        self._frame_bridge.frame_ready.connect(self._install_frame)
        self._unsubscribe_preview = service.subscribe_preview(self._on_preview)
        self._unsubscribe_commit = service.subscribe_commit(self._on_commit)

    def attach(self, window: QWidget) -> None:
        if self.window is not None and self.window is not window:
            raise RuntimeError("theme runtime is already attached to a MainWindow")
        self.window = window
        window.theme_runtime = self
        window.theme_service = self.service
        window.theme_draft_controller = self.draft_controller

        self.background_layer = ThemeBackgroundLayer(window, lambda: self.draft_controller.draft)
        self.background_layer.setObjectName("themeBackgroundLayer")
        self.background_layer.setGeometry(window.rect())
        self.background_layer.lower()
        self.background_layer.hide()
        root_provider = RootSurfaceProvider(
            lambda: self.render_engine.current_frame,
            window,
        )
        window._theme_surface_provider = root_provider

        self.sidebar_layer = SidebarMaterialLayer(window, lambda: self.draft_controller.draft)
        self.sidebar_layer.setObjectName("themeSidebarLayer")
        self.sidebar_layer.hide()
        self.sidebar_layer.lower()
        self.background_layer.lower()
        self.resize(window.width(), window.height())

    def attach_page(self, page: QWidget) -> None:
        page.theme_service = self.service
        page.theme_draft_controller = self.draft_controller
        if self.effect_installer is not None:
            self.effect_installer.install_subtree(page)

    def notify_startup_blur_removed(self) -> bool:
        if self._closed or self.window is None:
            return False
        if self.window.graphicsEffect() is not None:
            return False
        self.startup_blur_removed = True
        QTimer.singleShot(self.stabilization_delay_ms, self._enable_after_stable_paint)
        return True

    def _enable_after_stable_paint(self) -> None:
        if (
            self._closed
            or not self.feature_enabled
            or self.window is None
            or self.window.graphicsEffect() is not None
            or not self.startup_blur_removed
        ):
            return
        if self.effect_installer is None:
            self.effect_installer = ThemeEffectInstaller(
                self.window,
                lambda: self.draft_controller.draft,
                self.render_context,
                glyph_cache=self.render_engine.glyph_cache,
            )
        self.engine_enabled = True
        self.background_layer.show()
        self.background_layer.lower()
        self.sidebar_layer.show()
        self.sidebar_layer.lower()
        self.background_layer.lower()
        self._request_render(throttled=False)
        self.window.update()

    def resize(self, width: int, height: int) -> None:
        if self.window is None:
            return
        width, height = max(1, int(width)), max(1, int(height))
        if self.background_layer is not None:
            self.background_layer.setGeometry(0, 0, width, height)
        if self.sidebar_layer is not None:
            self.sidebar_layer.setGeometry(0, 0, max(1, int(width * 0.1)), height)
        if self.engine_enabled:
            self._request_render(throttled=True)

    def _on_preview(self, event: ThemePreviewEvent) -> None:
        self._render_revision = max(self._render_revision + 1, event.render_revision)
        if self.effect_installer:
            self.effect_installer.update_theme(event.theme)
        if self.engine_enabled:
            self._request_render(throttled=True)

    def _on_commit(self, event: ThemeCommitEvent) -> None:
        self._render_revision += 1
        if self.effect_installer:
            self.effect_installer.update_theme(event.theme)
        if self.engine_enabled:
            self._request_render(throttled=False)

    def render_context(self) -> ThemeRenderContext:
        window = self.window
        if window is None:
            logical_size = (1, 1)
            dpr = 1.0
            minimum_font_size = 10.0
            maximum_font_size = 30.0
        else:
            logical_size = (max(1, window.width()), max(1, window.height()))
            dpr = float(window.devicePixelRatioF())
            minimum_font_size = float(getattr(window, "min_font_size", 10.0))
            maximum_font_size = float(getattr(window, "max_font_size", 30.0))
        return ThemeRenderContext(
            self.draft_controller.draft,
            minimum_font_size,
            maximum_font_size,
            logical_size,
            dpr,
            self._render_revision,
        )

    def notify_font_context_changed(self) -> None:
        if self._closed:
            return
        self._render_revision += 1
        if self.effect_installer is not None:
            self.effect_installer.invalidate_glyph_cache()

    def _request_render(self, *, throttled: bool) -> None:
        if self.window is None or self._closed:
            return
        arguments = dict(
            theme=self.draft_controller.draft,
            theme_revision=self.service.revision,
            render_revision=self._render_revision,
            logical_size=(max(1, self.window.width()), max(1, self.window.height())),
            dpr=float(self.window.devicePixelRatioF()),
            callback=self._frame_bridge.frame_ready.emit,
        )
        if throttled:
            self.render_engine.request_throttled(**arguments)
        else:
            self.render_engine.request(**arguments)

    def _install_frame(self, frame: RenderedFrame) -> None:
        if self._closed or not self.engine_enabled:
            return
        if self.background_layer:
            self.background_layer.set_frame(frame)
        if self.sidebar_layer:
            self.sidebar_layer.set_frame(frame)
        if self.effect_installer:
            self.effect_installer.root.update()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.engine_enabled = False
        self._unsubscribe_preview()
        self._unsubscribe_commit()
        if self.effect_installer:
            self.effect_installer.close()
            self.effect_installer = None
        self.draft_controller.close()
        self.render_engine.close()
        self.service.close()


def build_theme_runtime(
    settings_manager: Any,
    shared_manager: Any = None,
    *,
    repository: ThemeRepository | None = None,
    feature_enabled: bool | None = None,
    migrate_legacy: bool = True,
    stabilization_delay_ms: int = 20,
) -> ThemeRuntime:
    repository = repository or ThemeRepository()
    had_authoritative_state = repository.state_path.exists()
    if migrate_legacy and not had_authoritative_state and not repository.read_only:
        migrate_legacy_settings(repository, settings_manager)
    else:
        settings_manager.project_theme_compatibility(
            compatibility_projection(repository.active_theme())
        )
        settings_manager.bind_theme_projection_provider(
            lambda: compatibility_projection(repository.active_theme())
        )
    service = ThemeService(repository, shared_manager=shared_manager)
    assets = ThemeAssetStore(repository.root)
    composer = BackgroundComposer(assets)
    engine = ThemeRenderEngine(composer)
    draft = ThemeDraftController(service)
    return ThemeRuntime(
        service,
        settings_manager,
        assets,
        composer,
        engine,
        draft,
        feature_enabled=(
            theme_engine_feature_enabled()
            if feature_enabled is None
            else feature_enabled
        ),
        stabilization_delay_ms=stabilization_delay_ms,
    )


__all__ = [
    "THEME_ENGINE_ENABLED_DEFAULT",
    "THEME_ENGINE_ENVIRONMENT_FLAG",
    "SidebarMaterialLayer",
    "ThemeBackgroundLayer",
    "ThemeRuntime",
    "build_theme_runtime",
    "theme_engine_feature_enabled",
]

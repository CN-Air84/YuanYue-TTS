"""
Plugin Management Page

This module provides the PluginPage class that implements the plugin management
interface using a tab-based architecture. It allows users to view, install,
uninstall, enable, and disable plugins.
"""

import os
import zipfile
import shutil
from pathlib import Path
from typing import Optional

try:
    from PyQt5.QtWidgets import (QWidget, QTabWidget, QVBoxLayout, 
                                QHBoxLayout, QListWidget, QPushButton,
                                QLabel, QTextEdit, QSplitter, QListWidgetItem,
                                QFrame, QMessageBox, QFileDialog, QScrollArea,
                                QGridLayout, QStackedWidget, QButtonGroup,
                                QGraphicsOpacityEffect, QSizePolicy)
    from PyQt5.QtCore import Qt, pyqtSignal, QSize, QTimer, QPropertyAnimation, QEasingCurve
    from PyQt5.QtGui import QFont, QPalette, QPainter
except ImportError:
    # Fallback for development/testing without PyQt5
    class QWidget:
        def __init__(self, parent=None):
            pass
    
    class QTabWidget(QWidget):
        pass
    
    class QVBoxLayout:
        def __init__(self):
            pass
    
    class QHBoxLayout:
        pass
    
    class QListWidget(QWidget):
        pass
    
    class QPushButton(QWidget):
        pass
    
    class QLabel(QWidget):
        pass
    
    class QTextEdit(QWidget):
        pass
    
    class QSplitter(QWidget):
        pass
    
    class QListWidgetItem:
        pass
    
    class QFrame(QWidget):
        pass
    
    class QMessageBox:
        @staticmethod
        def information(*args, **kwargs):
            pass
        @staticmethod
        def warning(*args, **kwargs):
            pass
        @staticmethod
        def question(*args, **kwargs):
            return 0
        Yes = 1
        No = 0
    
    class QFileDialog:
        @staticmethod
        def getOpenFileName(*args, **kwargs):
            return ("", "")
    
    class QScrollArea(QWidget):
        pass
    
    class QGridLayout:
        pass
    
    class QStackedWidget(QWidget):
        pass
    
    class QButtonGroup:
        def __init__(self, parent=None):
            self._buttons = {}
        def addButton(self, btn, id=None):
            pass
        def buttonClicked(self):
            pass
    
    class QGraphicsOpacityEffect:
        def __init__(self, parent=None):
            self._opacity = 1.0
            self._enabled = False
        def setEnabled(self, v):
            self._enabled = v
        def opacity(self):
            return self._opacity
    
    class QTimer:
        pass
    
    class QPropertyAnimation:
        def __init__(self, target=None, prop=b""):
            pass
        def setDuration(self, ms):
            pass
        def setEasingCurve(self, curve):
            pass
        def setStartValue(self, v):
            pass
        def setEndValue(self, v):
            pass
        def start(self):
            pass
        def stop(self):
            pass
        def finished(self):
            class _Sig:
                def connect(self, cb):
                    pass
            return _Sig()
    
    class QEasingCurve:
        InOutQuad = 0
    
    class QPainter:
        pass
    
    class QPalette:
        WindowText = 0

    class Qt:
        Horizontal = 1
        Vertical = 2
        UserRole = 256
        ScrollBarAlwaysOff = 0
        ScrollBarAsNeeded = 1
    
    class pyqtSignal:
        def __init__(self, *args):
            pass
    
    class QSize:
        def __init__(self, w, h):
            pass
    
    class QFont:
        pass

from plugin_instance import PluginStatus
from resource_urls import get_resource_url
from misc_func import SettingsManager
from theme_page_adapter import (
    configure_semantic_surface,
    configure_theme_card,
    configure_transparent_container,
    configure_transparent_root,
    set_transparent_scroll_content,
)


def _plugin_theme(settings_manager=None):
    """Read the user theme values used by the plugin page."""
    manager = settings_manager or SettingsManager()
    defaults = {
        "background": "#E5E8EF",
        "card": "#FFFFFF",
        "component": "#F5F8FF",
        "accent": "#5555FF",
        "text": "#20232A",
        "muted": "#747B86",
    }
    keys = {
        "background": ("background_color", defaults["background"]),
        "card": ("card_background_color", defaults["card"]),
        "component": ("component_background_color", defaults["component"]),
        "accent": ("highlight_button_color", defaults["accent"]),
        "text": ("text_color", defaults["text"]),
    }
    for name, (key, default) in keys.items():
        try:
            value = manager.get_Custom_value(key, default)
            if value:
                defaults[name] = value
        except Exception:
            pass
    return defaults


def _font_settings(settings_manager=None):
    """Return the configured font family and bounded base size."""
    manager = settings_manager or SettingsManager()
    try:
        family = manager.get_Custom_value("global_font", "微软雅黑") or "微软雅黑"
    except Exception:
        family = "微软雅黑"
    try:
        minimum = float(manager.get_Custom_value("min_font_size", "22"))
    except Exception:
        minimum = 22.0
    try:
        maximum = float(manager.get_Custom_value("max_font_size", "42"))
    except Exception:
        maximum = 42.0
    if maximum < minimum:
        minimum, maximum = maximum, minimum
    return family, minimum, maximum


class PluginPage(QWidget):
    """
    Plugin management interface with tab-based architecture
    
    Provides a user interface for managing plugins including viewing
    installed plugins, installing new plugins, and configuring plugin settings.
    
    Requirements: 6.1, 6.2, 6.3, 6.4
    """
    
    # Signals
    plugin_enabled = pyqtSignal(str)    # plugin_name
    plugin_disabled = pyqtSignal(str)   # plugin_name
    plugin_installed = pyqtSignal(str)  # plugin_path
    plugin_uninstalled = pyqtSignal(str) # plugin_name
    
    def __init__(self, parent=None):
        """
        Initialize the plugin management page
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        configure_transparent_root(self)
        self.parent_window = parent
        self.settings_manager = SettingsManager()
        self._ui_scale = 1.0
        self._body_font_size = 11
        self._title_font_size = 14
        self._font_family = "微软雅黑"
        self.plugin_manager = None  # Set by main window
        self._init_ui()
        self.update_ui_scale()
        
    def _init_ui(self):
        """Initialize the plugin page using the same hierarchy as SettingsPage."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.top_nav_container = StyledContainer()
        nav_layout = QHBoxLayout(self.top_nav_container)
        nav_layout.setContentsMargins(20, 16, 20, 16)
        nav_layout.setSpacing(12)

        self.installed_nav_btn = PluginNavButton("已安装插件")
        self.market_nav_btn = PluginNavButton("插件市场")
        self.settings_nav_btn = PluginNavButton("插件设置")
        self.installed_nav_btn.setChecked(True)

        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        for index, button in enumerate((
            self.installed_nav_btn,
            self.market_nav_btn,
            self.settings_nav_btn,
        )):
            self._nav_group.addButton(button, index)

        nav_layout.addStretch()
        nav_layout.addWidget(self.installed_nav_btn)
        nav_layout.addWidget(self.market_nav_btn)
        nav_layout.addWidget(self.settings_nav_btn)
        nav_layout.addStretch()
        layout.addWidget(self.top_nav_container)

        self.content_stack = QStackedWidget()
        configure_transparent_container(self.content_stack)
        self.content_stack.setStyleSheet("QStackedWidget { background: transparent; }")

        self.installed_tab = InstalledPluginsTab(self)
        self.market_tab = PluginMarketTab(self)
        self.settings_tab = PluginSettingsTab(self)
        self.content_stack.addWidget(self.installed_tab)
        self.content_stack.addWidget(self.market_tab)
        self.content_stack.addWidget(self.settings_tab)
        layout.addWidget(self.content_stack)

        self._stack_opacity = QGraphicsOpacityEffect(self.content_stack)
        self.content_stack.setGraphicsEffect(self._stack_opacity)
        self._stack_opacity.setEnabled(False)
        self._fade_animation = QPropertyAnimation(self._stack_opacity, b"opacity")
        self._fade_animation.setDuration(180)
        self._fade_animation.setEasingCurve(QEasingCurve.InOutQuad)
        self._fade_animation.finished.connect(self._finish_tab_transition)
        self._target_tab_index = 0
        self._nav_group.buttonClicked[int].connect(self._switch_tab)

    def _window_ratio(self):
        window = self.window()
        width = max(1, window.width())
        height = max(1, window.height())
        return (width / 1080.0 + height / 720.0) / 2.0

    def update_ui_scale(self):
        """Apply the configured font and a size-aware control scale."""
        ratio = self._window_ratio()
        family, minimum, maximum = _font_settings(self.settings_manager)
        base_size = minimum + (maximum - minimum) * (ratio - 1.0)
        base_size = max(minimum, min(maximum, base_size))
        self._font_family = family
        self._body_font_size = max(10, int(round(base_size * 0.5)))
        self._title_font_size = max(self._body_font_size + 2, int(round(self._body_font_size * 1.25)))
        self._ui_scale = max(0.78, min(1.55, ratio))

        self._apply_font_tree(self)
        self._apply_geometry_scale()
        self.apply_theme()

    def _apply_font_tree(self, root):
        role_sizes = {
            "nav": self._body_font_size + 1,
            "sectionTitle": self._title_font_size,
            "cardTitle": self._title_font_size + 1,
            "fieldTitle": max(8, int(round((self._body_font_size + 1) * 0.75))),
            "small": max(9, self._body_font_size - 1),
            "body": self._body_font_size,
        }
        for widget in [root, *root.findChildren(QWidget)]:
            role = widget.property("pluginFontRole") or "body"
            size = role_sizes.get(role, self._body_font_size)
            font = QFont(self._font_family, int(size))
            if role in {"sectionTitle", "cardTitle", "fieldTitle"}:
                font.setWeight(QFont.DemiBold)
            widget.setFont(font)

    def _apply_geometry_scale(self):
        scale = self._ui_scale
        outer = self.layout()
        if outer:
            margin = int(round(10 * scale))
            outer.setContentsMargins(margin, margin, margin, margin)
            outer.setSpacing(max(6, int(round(10 * scale))))
        nav_layout = self.top_nav_container.layout()
        if nav_layout:
            nav_layout.setContentsMargins(
                int(round(20 * scale)), int(round(16 * scale)),
                int(round(20 * scale)), int(round(16 * scale))
            )
            nav_layout.setSpacing(max(6, int(round(12 * scale))))
        for button in (self.installed_nav_btn, self.market_nav_btn, self.settings_nav_btn):
            button.setMinimumWidth(max(100, int(round(126 * scale))))
            button.setFixedHeight(max(32, int(round(38 * scale))))
        self.installed_tab.apply_scale(scale, self._font_family, self._body_font_size, self._title_font_size)
        self.market_tab.apply_scale(scale, self._font_family, self._body_font_size, self._title_font_size)
        self.settings_tab.apply_scale(scale, self._font_family, self._body_font_size, self._title_font_size)

    def apply_theme(self):
        colors = _plugin_theme(self.settings_manager)
        self.setStyleSheet(
            f"PluginPage {{ background-color: {colors['background']}; "
            f"color: {colors['text']}; }}"
        )
        for widget in self.findChildren(StyledContainer):
            widget.apply_theme(self.settings_manager)
        self.installed_tab.apply_theme()
        self.market_tab.apply_theme()
        self.settings_tab.apply_theme()

    def update_fonts(self, font=None):
        """Compatibility hook used by the main window font manager."""
        self.update_ui_scale()

    def resizeEvent(self, event):
        self.update_ui_scale()
        super().resizeEvent(event)

    def showEvent(self, event):
        self.update_ui_scale()
        super().showEvent(event)

    def _switch_tab(self, index: int):
        """Fade between plugin sections without changing the page geometry."""
        if self.content_stack.currentIndex() == index:
            return
        if index == 2 and self.plugin_manager:
            self.settings_tab._refresh_all()
            self.update_ui_scale()
        self._target_tab_index = index
        self._stack_opacity.setEnabled(True)
        self._fade_animation.stop()
        self._fade_animation.setStartValue(1.0)
        self._fade_animation.setEndValue(0.0)
        self._fade_animation.start()

    def _finish_tab_transition(self):
        if self._stack_opacity.opacity() < 0.5:
            self.content_stack.setCurrentIndex(self._target_tab_index)
            self._fade_animation.setStartValue(0.0)
            self._fade_animation.setEndValue(1.0)
            self._fade_animation.start()
        else:
            self._stack_opacity.setEnabled(False)

    def show_installed_plugins(self):
        """Return to the installed section after a market action."""
        self.installed_nav_btn.setChecked(True)
        self._switch_tab(0)
        
    def _legacy_settings_selector_ui(self):
        """Legacy selector prototype retained for compatibility."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._tab_bar = StyledContainer()
        self._tab_bar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self._tab_bar.setFixedWidth(210)
        tab_bar_layout = QVBoxLayout(self._tab_bar)
        tab_bar_layout.setContentsMargins(14, 16, 14, 16)
        tab_bar_layout.setSpacing(8)

        self.selector_title_label = QLabel("插件设置")
        self.selector_title_label.setProperty("pluginFontRole", "sectionTitle")
        self.selector_title_label.setStyleSheet(
            "background-color: transparent; border: none; font-weight: 600;"
        )
        tab_bar_layout.addWidget(self.selector_title_label)

        self._plugin_count_label = QLabel("0 个可配置插件")
        self._plugin_count_label.setProperty("pluginFontRole", "small")
        tab_bar_layout.addWidget(self._plugin_count_label)

        self._selector_host = QWidget()
        self._selector_host.setStyleSheet("background-color: transparent; border: none;")
        self._tab_button_row = QVBoxLayout(self._selector_host)
        self._tab_button_row.setContentsMargins(0, 8, 0, 0)
        self._tab_button_row.setSpacing(8)

        selector_scroll = QScrollArea()
        selector_scroll.setWidgetResizable(True)
        selector_scroll.setFrameShape(QFrame.NoFrame)
        selector_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        selector_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        selector_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        set_transparent_scroll_content(selector_scroll, self._selector_host)
        tab_bar_layout.addWidget(selector_scroll, 1)
        layout.addWidget(self._tab_bar)

        self._group = QButtonGroup(self)
        self._group.buttonClicked.connect(self._on_button_clicked)

        self._content_stack = QStackedWidget()
        self._content_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._content_stack.setStyleSheet("QStackedWidget { background: transparent; }")
        layout.addWidget(self._content_stack, 1)

        self._opacity_effect = QGraphicsOpacityEffect(self._content_stack)
        self._content_stack.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setEnabled(False)
        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_anim.setDuration(200)
        self._fade_anim.setEasingCurve(QEasingCurve.InOutQuad)
        self._fade_anim.finished.connect(self._on_fade_finished)
        self._target_index = 0

        self._show_empty_state("暂无可配置插件", "已启用的插件均未提供设置面板")
        self.apply_theme()

    def _legacy_settings_selector_scale(self, scale, family, body_size, title_size):
        self.layout().setSpacing(max(6, int(round(10 * scale))))
        self._tab_bar.setFixedWidth(max(170, int(round(210 * scale))))
        self._tab_bar.layout().setContentsMargins(
            int(round(14 * scale)), int(round(16 * scale)),
            int(round(14 * scale)), int(round(16 * scale))
        )
        self._tab_bar.layout().setSpacing(max(6, int(round(8 * scale))))
        self._tab_button_row.setSpacing(max(6, int(round(8 * scale))))
        for button in self._tab_buttons.values():
            button.apply_scale(scale)

    def _legacy_settings_selector_theme(self):
        colors = _plugin_theme(getattr(self.plugin_page, "settings_manager", None))
        if not hasattr(self, "_tab_bar"):
            return
        self._tab_bar.apply_theme(getattr(self.plugin_page, "settings_manager", None))
        self.selector_title_label.setStyleSheet(
            f"background-color: transparent; border: none; color: {colors['text']}; font-weight: 600;"
        )
        self._plugin_count_label.setStyleSheet(
            f"background-color: transparent; border: none; color: {colors['muted']};"
        )
        for button in self._tab_buttons.values():
            button.apply_theme(getattr(self.plugin_page, "settings_manager", None))

    def set_plugin_manager(self, plugin_manager):
        """
        Set the plugin manager reference
        
        Args:
            plugin_manager: PluginManager instance
        """
        self.plugin_manager = plugin_manager
        self.installed_tab.set_plugin_manager(plugin_manager)
        self.settings_tab.set_plugin_manager(plugin_manager)
        
        # Refresh plugin list after setting manager
        self.refresh_plugin_list()
        self.update_ui_scale()
        
    def refresh_plugin_list(self):
        """Refresh the list of installed plugins"""
        if self.plugin_manager:
            self.installed_tab.refresh_plugin_list()
        
    def on_plugin_selected(self, plugin_name: str):
        """
        Handle plugin selection in the list
        
        Args:
            plugin_name: Name of the selected plugin
        """
        self.installed_tab.on_plugin_selected(plugin_name)
        
    def on_enable_plugin(self):
        """Handle enable plugin button click"""
        self.installed_tab.on_enable_plugin()
        
    def on_disable_plugin(self):
        """Handle disable plugin button click"""
        self.installed_tab.on_disable_plugin()
        
    def on_uninstall_plugin(self):
        """Handle uninstall plugin button click"""
        self.installed_tab.on_uninstall_plugin()
        
    def on_install_plugin(self):
        """Handle install plugin button click"""
        self.installed_tab.on_install_plugin()
        
    def on_check_updates(self):
        """Handle check updates button click"""
        self.installed_tab.on_check_updates()


class StyledContainer(QFrame):
    """White settings-style surface used for major content groups."""
    def __init__(self, parent=None):
        super().__init__(parent)
        configure_theme_card(self)
        self.apply_theme()

    def apply_theme(self, settings_manager=None):
        colors = _plugin_theme(settings_manager)
        self.setStyleSheet(f"""
            StyledContainer {{
                background-color: {colors['card']};
                color: {colors['text']};
                border: 1px solid {colors['component']};
                border-radius: 6px;
            }}
        """)


class PluginNavButton(QPushButton):
    """Level-one navigation button aligned with the settings page controls."""
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setProperty("pluginFontRole", "nav")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumWidth(126)
        self.setFixedHeight(38)
        self.apply_theme()

    def apply_theme(self, settings_manager=None):
        colors = _plugin_theme(settings_manager)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {colors['card']};
                color: {colors['text']};
                border: 1px solid #B8BEC8;
                border-radius: 5px;
                padding: 7px 18px;
            }}
            QPushButton:hover:!checked {{
                background-color: #F5F6F8;
                border-color: #8F97A3;
            }}
            QPushButton:checked {{
                background-color: {colors['accent']};
                color: #FFFFFF;
                border-color: {colors['accent']};
                font-weight: 600;
            }}
            QPushButton:focus {{ outline: none; }}
        """)


class PluginFieldCard(QFrame):
    """Small tertiary card used for one plugin metadata field."""
    def __init__(self, title: str, value_label: QLabel, parent=None):
        super().__init__(parent)
        configure_theme_card(self)
        self.setObjectName("PluginFieldCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.title_label = QLabel(title)
        self.title_label.setProperty("pluginFontRole", "fieldTitle")
        self.title_label.setStyleSheet(
            "background-color: transparent; border: none; "
            "color: #747B86; font-weight: 600;"
        )
        self.value_label = value_label
        self.value_label.setProperty("pluginFontRole", "body")
        self.value_label.setWordWrap(True)
        self.value_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.value_label.setStyleSheet(
            "background-color: transparent; border: none; "
            "color: #20232A; padding-top: 3px;"
        )
        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(2)
        card_layout.addWidget(self.title_label)
        card_layout.addWidget(self.value_label)
        self.apply_theme()

    def apply_theme(self, settings_manager=None):
        colors = _plugin_theme(settings_manager)
        self.setStyleSheet(f"""
            QFrame#PluginFieldCard {{
                background-color: {colors['component']};
                border: 1px solid {colors['component']};
                border-radius: 5px;
            }}
        """)
        self.title_label.setStyleSheet(
            f"background-color: transparent; border: none; color: {colors['muted']}; "
            "font-weight: 600;"
        )
        self.value_label.setStyleSheet(
            f"background-color: transparent; border: none; color: {colors['text']}; "
            "padding-top: 3px;"
        )


class InstalledPluginsTab(QWidget):
    """
    Tab for managing installed plugins
    
    Displays list of installed plugins with name, version, author, status.
    Provides plugin details view and management controls.
    
    Requirements: 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10, 6.11, 6.12, 6.13, 6.14
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        configure_transparent_container(self)
        self.plugin_page = parent
        self.plugin_manager = None
        self.selected_plugin_name = None
        self._init_ui()
        
    def _init_ui_legacy(self):
        """Initialize UI with plugin list and details view (需求 6.3, 6.4)"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Left panel: Plugin list
        left_panel = StyledContainer()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)
        
        # Title and install button
        title_layout = QHBoxLayout()
        title_label = QLabel("插件列表")
        title_label.setStyleSheet(
            "color: #20232A; font-size: 15px; font-weight: 600; border: none;"
        )
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        self.plugin_count_label = QLabel("0 个")
        self.plugin_count_label.setStyleSheet(
            "color: #747B86; background: #F1F3F6; border: none; "
            "border-radius: 9px; padding: 2px 8px;"
        )
        title_layout.addWidget(self.plugin_count_label)
        
        # Install plugin button (需求 6.11, 6.12, 6.13)
        self.install_btn = QPushButton("安装插件")
        configure_semantic_surface(self.install_btn)
        self.install_btn.setCursor(Qt.PointingHandCursor)
        self.install_btn.setStyleSheet("""
            QPushButton {
                background-color: #5555FF;
                color: white;
                border: 1px solid #5555FF;
                border-radius: 4px;
                padding: 8px 14px;
            }
            QPushButton:hover {
                background-color: #4444DD;
                border-color: #4444DD;
            }
        """)
        self.install_btn.clicked.connect(self.on_install_plugin)
        title_layout.addWidget(self.install_btn)
        
        left_layout.addLayout(title_layout)
        
        # Plugin list widget (需求 6.3)
        self.plugin_list = QListWidget()
        self.plugin_list.setSpacing(2)
        self.plugin_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.plugin_list.setTextElideMode(Qt.ElideRight)
        self.plugin_list.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        self.plugin_list.setStyleSheet("""
            QListWidget {
                border: none;
                border-radius: 5px;
                background-color: #F6F7F9;
                padding: 5px;
                outline: none;
            }
            QListWidget::item {
                color: #343943;
                background-color: #FFFFFF;
                border: 1px solid #E0E3E8;
                border-radius: 4px;
                padding: 9px 10px;
            }
            QListWidget::item:selected {
                color: #292D85;
                background-color: #EEEEFF;
                border-color: #7777FF;
            }
            QListWidget::item:hover:!selected {
                background-color: #F9FAFB;
                border-color: #B9BFC8;
            }
        """)
        self.plugin_list.itemClicked.connect(self._on_plugin_item_clicked)
        left_layout.addWidget(self.plugin_list)
        
        # Check updates button (需求 10.1, 10.2)
        self.check_updates_btn = QPushButton("检查更新")
        configure_semantic_surface(self.check_updates_btn)
        self.check_updates_btn.setCursor(Qt.PointingHandCursor)
        self.check_updates_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #343943;
                border: 1px solid #BFC4CC;
                border-radius: 4px;
                padding: 8px 14px;
            }
            QPushButton:hover {
                background-color: #F3F4F6;
                border-color: #8F97A3;
            }
            QPushButton:disabled { color: #9CA2AC; background: #F4F5F6; }
        """)
        self.check_updates_btn.clicked.connect(self.on_check_updates)
        left_layout.addWidget(self.check_updates_btn)
        
        layout.addWidget(left_panel, 5)
        
        # Right panel: Plugin details and controls
        right_panel = StyledContainer()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(18, 16, 18, 16)
        right_layout.setSpacing(12)
        
        # Plugin details (需求 6.4)
        details_label = QLabel("插件详情")
        details_label.setStyleSheet(
            "color: #20232A; font-size: 15px; font-weight: 600; border: none;"
        )
        right_layout.addWidget(details_label)

        self.detail_hint = QLabel("插件状态与元数据")
        self.detail_hint.setWordWrap(True)
        self.detail_hint.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.detail_hint.setStyleSheet("color: #858C97; border: none;")
        right_layout.addWidget(self.detail_hint)
        
        # Scrollable details area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                border-radius: 5px;
                background-color: #F7F8FA;
            }
            QScrollBar:vertical { width: 8px; background: transparent; }
            QScrollBar::handle:vertical { background: #C8CDD5; border-radius: 4px; }
        """)
        
        details_widget = QWidget()
        details_widget.setStyleSheet("background: transparent;")
        self.details_layout = QVBoxLayout(details_widget)
        self.details_layout.setContentsMargins(14, 12, 14, 12)
        self.details_layout.setSpacing(6)
        self.details_layout.setAlignment(Qt.AlignTop)
        
        # Plugin info labels
        self.name_label = QLabel("名称: -")
        self.version_label = QLabel("版本: -")
        self.author_label = QLabel("作者: -")
        self.status_label = QLabel("状态: -")
        self.description_label = QLabel("描述: -")
        self.description_label.setWordWrap(True)
        self.update_date_label = QLabel("更新日期: -")
        self.github_label = QLabel("GitHub: -")
        self.github_label.setWordWrap(True)
        
        for label in [self.name_label, self.version_label, self.author_label,
                     self.status_label, self.description_label, 
                     self.update_date_label, self.github_label]:
            label.setWordWrap(True)
            label.setStyleSheet(
                "color: #3C424C; background: transparent; border: none; "
                "padding: 6px 4px;"
            )
            self.details_layout.addWidget(label)
        
        set_transparent_scroll_content(scroll_area, details_widget)
        right_layout.addWidget(scroll_area)
        
        # Control buttons (需求 6.5, 6.6, 6.7, 6.8, 6.9, 6.10)
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        self.enable_btn = QPushButton("启用")
        configure_semantic_surface(self.enable_btn)
        self.enable_btn.setCursor(Qt.PointingHandCursor)
        self.enable_btn.setStyleSheet("""
            QPushButton {
                background-color: #5555FF;
                color: white;
                border: 1px solid #5555FF;
                border-radius: 4px;
                padding: 8px 18px;
            }
            QPushButton:hover { background-color: #4444DD; }
            QPushButton:disabled {
                background-color: #E3E5E8;
                border-color: #E3E5E8;
                color: #9A9FA8;
            }
        """)
        self.enable_btn.clicked.connect(self.on_enable_plugin)
        self.enable_btn.setEnabled(False)
        
        self.disable_btn = QPushButton("停用")
        configure_semantic_surface(self.disable_btn)
        self.disable_btn.setCursor(Qt.PointingHandCursor)
        self.disable_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #343943;
                border: 1px solid #BFC4CC;
                border-radius: 4px;
                padding: 8px 18px;
            }
            QPushButton:hover { background-color: #F3F4F6; }
            QPushButton:disabled {
                background-color: #F1F2F4;
                color: #A4A9B1;
                border-color: #E1E3E6;
            }
        """)
        self.disable_btn.clicked.connect(self.on_disable_plugin)
        self.disable_btn.setEnabled(False)
        
        self.uninstall_btn = QPushButton("卸载")
        configure_semantic_surface(self.uninstall_btn)
        self.uninstall_btn.setCursor(Qt.PointingHandCursor)
        self.uninstall_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #C93C45;
                border: 1px solid #E0A2A7;
                border-radius: 4px;
                padding: 8px 18px;
            }
            QPushButton:hover { background-color: #FFF2F3; border-color: #C93C45; }
            QPushButton:disabled {
                background-color: #F7F7F8;
                color: #B7BBC2;
                border-color: #E4E5E8;
            }
        """)
        self.uninstall_btn.clicked.connect(self.on_uninstall_plugin)
        self.uninstall_btn.setEnabled(False)
        
        button_layout.addWidget(self.enable_btn)
        button_layout.addWidget(self.disable_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.uninstall_btn)
        
        right_layout.addLayout(button_layout)
        
        layout.addWidget(right_panel, 8)

    def _init_ui(self):
        """Build the settings-style installed-plugin inspector."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._left_panel = StyledContainer()
        left_layout = QVBoxLayout(self._left_panel)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)

        title_layout = QHBoxLayout()
        self.list_title_label = QLabel("插件列表")
        self.list_title_label.setProperty("pluginFontRole", "sectionTitle")
        self.list_title_label.setStyleSheet(
            "background-color: transparent; border: none; font-weight: 600;"
        )
        title_layout.addWidget(self.list_title_label)
        title_layout.addStretch()

        self.plugin_count_label = QLabel("0 个")
        self.plugin_count_label.setProperty("pluginFontRole", "small")
        self.plugin_count_label.setAlignment(Qt.AlignCenter)
        title_layout.addWidget(self.plugin_count_label)

        self.install_btn = QPushButton("安装插件")
        self.install_btn.setCursor(Qt.PointingHandCursor)
        self.install_btn.clicked.connect(self.on_install_plugin)
        title_layout.addWidget(self.install_btn)
        left_layout.addLayout(title_layout)

        self.plugin_list = QListWidget()
        self.plugin_list.setSpacing(2)
        self.plugin_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.plugin_list.setTextElideMode(Qt.ElideRight)
        self.plugin_list.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        self.plugin_list.itemClicked.connect(self._on_plugin_item_clicked)
        left_layout.addWidget(self.plugin_list)

        self.check_updates_btn = QPushButton("检查更新")
        self.check_updates_btn.setCursor(Qt.PointingHandCursor)
        self.check_updates_btn.clicked.connect(self.on_check_updates)
        left_layout.addWidget(self.check_updates_btn)

        self._right_panel = StyledContainer()
        right_layout = QVBoxLayout(self._right_panel)
        right_layout.setContentsMargins(18, 16, 18, 16)
        right_layout.setSpacing(10)

        self.details_title_label = QLabel("插件详情")
        self.details_title_label.setProperty("pluginFontRole", "sectionTitle")
        self.details_title_label.setStyleSheet(
            "background-color: transparent; border: none; font-weight: 600;"
        )
        right_layout.addWidget(self.details_title_label)

        # Kept as a compatibility attribute but intentionally not shown.
        self.detail_hint = QLabel("插件状态与元数据")
        self.detail_hint.hide()

        detail_scroll = QScrollArea()
        configure_transparent_container(detail_scroll)
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setFrameShape(QFrame.NoFrame)
        detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        detail_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._detail_scroll = detail_scroll

        details_widget = QWidget()
        configure_transparent_container(details_widget)
        details_widget.setStyleSheet("background-color: transparent; border: none;")
        self.details_layout = QVBoxLayout(details_widget)
        self.details_layout.setContentsMargins(0, 0, 0, 0)
        self.details_layout.setSpacing(10)
        self.details_layout.setAlignment(Qt.AlignTop)

        self.metadata_card = QFrame()
        configure_theme_card(self.metadata_card)
        self.metadata_card.setObjectName("PluginMetadataCard")
        self.metadata_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        metadata_layout = QVBoxLayout(self.metadata_card)
        metadata_layout.setContentsMargins(14, 12, 14, 14)
        metadata_layout.setSpacing(8)
        metadata_title = QLabel("基本信息")
        self.metadata_title_label = metadata_title
        metadata_title.setProperty("pluginFontRole", "cardTitle")
        metadata_title.setStyleSheet(
            "background-color: transparent; border: none; font-weight: 600;"
        )
        # Keep the compatibility label out of the layout; the metadata grid is
        # the card's visual header now, so it can use the reclaimed top space.
        metadata_title.hide()

        metadata_grid = QGridLayout()
        metadata_grid.setContentsMargins(0, 0, 0, 0)
        metadata_grid.setHorizontalSpacing(8)
        metadata_grid.setVerticalSpacing(8)
        metadata_layout.addLayout(metadata_grid)
        self._metadata_grid = metadata_grid
        self._field_cards = []

        def add_field(title, attribute, row, column, column_span=1):
            value = QLabel("-")
            setattr(self, attribute, value)
            field_card = PluginFieldCard(title, value, self.metadata_card)
            self._field_cards.append(field_card)
            metadata_grid.addWidget(field_card, row, column, 1, column_span)
            return value

        add_field("名称", "name_label", 0, 0)
        add_field("版本", "version_label", 0, 1)
        add_field("作者", "author_label", 1, 0)
        add_field("更新日期", "update_date_label", 1, 1)
        add_field("状态", "status_label", 2, 0, 2)
        metadata_grid.setColumnStretch(0, 1)
        metadata_grid.setColumnStretch(1, 1)

        self.details_layout.addWidget(self.metadata_card)

        self.description_card = QFrame()
        configure_theme_card(self.description_card)
        self.description_card.setObjectName("PluginDescriptionCard")
        self.description_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        description_layout = QVBoxLayout(self.description_card)
        description_layout.setContentsMargins(14, 12, 14, 14)
        description_layout.setSpacing(6)
        description_title = QLabel("描述")
        self.description_title_label = description_title
        description_title.setProperty("pluginFontRole", "cardTitle")
        description_title.setStyleSheet(
            "background-color: transparent; border: none; font-weight: 600;"
        )
        description_layout.addWidget(description_title)
        self.description_label = QLabel("-")
        self.description_label.setProperty("pluginFontRole", "body")
        self.description_label.setWordWrap(True)
        self.description_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        description_layout.addWidget(self.description_label)
        self.details_layout.addWidget(self.description_card)
        self.details_layout.addStretch()

        # Preserve the old attribute for callers that inspect metadata.
        self.github_label = QLabel("GitHub: -")
        self.github_label.hide()
        set_transparent_scroll_content(detail_scroll, details_widget)
        right_layout.addWidget(detail_scroll)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        self.enable_btn = QPushButton("启用")
        self.disable_btn = QPushButton("停用")
        self.uninstall_btn = QPushButton("卸载")
        for button in (self.enable_btn, self.disable_btn, self.uninstall_btn):
            button.setCursor(Qt.PointingHandCursor)
        self.enable_btn.clicked.connect(self.on_enable_plugin)
        self.disable_btn.clicked.connect(self.on_disable_plugin)
        self.uninstall_btn.clicked.connect(self.on_uninstall_plugin)
        self.enable_btn.setEnabled(False)
        self.disable_btn.setEnabled(False)
        self.uninstall_btn.setEnabled(False)
        button_layout.addWidget(self.enable_btn)
        button_layout.addWidget(self.disable_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.uninstall_btn)
        right_layout.addLayout(button_layout)

        layout.addWidget(self._left_panel, 5)
        layout.addWidget(self._right_panel, 8)
        self.apply_theme()

    def apply_scale(self, scale, family, body_size, title_size):
        self.layout().setSpacing(max(6, int(round(10 * scale))))
        self._left_panel.layout().setContentsMargins(
            int(round(16 * scale)), int(round(16 * scale)),
            int(round(16 * scale)), int(round(16 * scale))
        )
        self._left_panel.layout().setSpacing(max(8, int(round(12 * scale))))
        self._right_panel.layout().setContentsMargins(
            int(round(18 * scale)), int(round(16 * scale)),
            int(round(18 * scale)), int(round(16 * scale))
        )
        self._right_panel.layout().setSpacing(max(8, int(round(10 * scale))))
        self.details_layout.setSpacing(max(7, int(round(10 * scale))))
        self.metadata_card.layout().setContentsMargins(
            int(round(14 * scale)), int(round(12 * scale)),
            int(round(14 * scale)), int(round(14 * scale))
        )
        self.description_card.layout().setContentsMargins(
            int(round(14 * scale)), int(round(12 * scale)),
            int(round(14 * scale)), int(round(14 * scale))
        )
        self._metadata_grid.setHorizontalSpacing(max(6, int(round(8 * scale))))
        self._metadata_grid.setVerticalSpacing(max(6, int(round(8 * scale))))
        for card in self._field_cards:
            card.layout().setContentsMargins(
                int(round(12 * scale)), int(round(10 * scale)),
                int(round(12 * scale)), int(round(10 * scale))
            )
            card.layout().setSpacing(max(2, int(round(2 * scale))))
        for button in (self.install_btn, self.check_updates_btn,
                       self.enable_btn, self.disable_btn, self.uninstall_btn):
            button.setFixedHeight(max(30, int(round(36 * scale))))
        self._plugin_item_height = max(50, int(round(56 * scale)))
        for index in range(self.plugin_list.count()):
            item = self.plugin_list.item(index)
            item.setSizeHint(QSize(0, self._plugin_item_height))

    def apply_theme(self):
        settings_manager = getattr(self.plugin_page, "settings_manager", None)
        colors = _plugin_theme(settings_manager)
        if hasattr(self, "_left_panel"):
            self._left_panel.apply_theme(settings_manager)
            self._right_panel.apply_theme(settings_manager)
            self.plugin_list.setStyleSheet(f"""
                QListWidget {{
                    border: none; border-radius: 5px;
                    background-color: {colors['component']}; padding: 5px; outline: none;
                }}
                QListWidget::item {{
                    color: {colors['text']}; background-color: {colors['card']};
                    border: 1px solid {colors['component']}; border-radius: 4px;
                    padding: 6px 10px;
                }}
                QListWidget::item:selected {{
                    color: #FFFFFF; background-color: {colors['accent']};
                    border-color: {colors['accent']};
                }}
                QListWidget::item:hover:!selected {{
                    background-color: {colors['component']}; border-color: {colors['accent']};
                }}
            """)
            self._detail_scroll.setStyleSheet(f"""
                QScrollArea {{ border: none; border-radius: 5px;
                    background-color: {colors['component']}; }}
                QScrollBar:vertical {{ width: 8px; background: transparent; }}
                QScrollBar::handle:vertical {{ background: #C8CDD5; border-radius: 4px; }}
            """)
            for card in self._field_cards:
                card.apply_theme(settings_manager)
            self.description_label.setStyleSheet(
                f"background-color: transparent; border: none; color: {colors['text']};"
            )
            for card in (self.metadata_card, self.description_card):
                card.setStyleSheet(
                    f"QFrame#{card.objectName()} {{ background-color: {colors['card']}; "
                    f"border: 1px solid {colors['component']}; border-radius: 6px; }}"
                )
            self.list_title_label.setStyleSheet(
                f"background-color: transparent; border: none; color: {colors['text']}; font-weight: 600;"
            )
            self.details_title_label.setStyleSheet(
                f"background-color: transparent; border: none; color: {colors['text']}; font-weight: 600;"
            )
            for title in (self.metadata_title_label, self.description_title_label):
                title.setStyleSheet(
                    f"background-color: transparent; border: none; color: {colors['text']}; font-weight: 600;"
                )
            self.plugin_count_label.setStyleSheet(
                f"background-color: {colors['component']}; border: none; color: {colors['muted']}; "
                "border-radius: 9px; padding: 2px 8px;"
            )
            self._style_action_buttons(colors)

    def _style_action_buttons(self, colors):
        self.install_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {colors['accent']}; color: #FFFFFF;
                border: 1px solid {colors['accent']}; border-radius: 4px; padding: 7px 14px; }}
            QPushButton:hover {{ background-color: {colors['accent']}; }}
            QPushButton:disabled {{ background-color: {colors['component']}; color: {colors['muted']}; }}
        """)
        self.check_updates_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {colors['card']}; color: {colors['text']};
                border: 1px solid {colors['component']}; border-radius: 4px; padding: 7px 14px; }}
            QPushButton:hover {{ background-color: {colors['component']}; }}
            QPushButton:disabled {{ color: {colors['muted']}; background: {colors['component']}; }}
        """)
        self.enable_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {colors['accent']}; color: #FFFFFF;
                border: 1px solid {colors['accent']}; border-radius: 4px; padding: 7px 18px; }}
            QPushButton:hover {{ background-color: {colors['accent']}; }}
            QPushButton:disabled {{ background-color: {colors['component']}; color: {colors['muted']}; border-color: {colors['component']}; }}
        """)
        self.disable_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {colors['card']}; color: {colors['text']};
                border: 1px solid {colors['component']}; border-radius: 4px; padding: 7px 18px; }}
            QPushButton:hover {{ background-color: {colors['component']}; }}
            QPushButton:disabled {{ background-color: {colors['component']}; color: {colors['muted']}; border-color: {colors['component']}; }}
        """)
        self.uninstall_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {colors['card']}; color: #C93C45;
                border: 1px solid #E0A2A7; border-radius: 4px; padding: 7px 18px; }}
            QPushButton:hover {{ background-color: #FFF2F3; border-color: #C93C45; }}
            QPushButton:disabled {{ background-color: {colors['component']}; color: {colors['muted']}; border-color: {colors['component']}; }}
        """)
        
    def set_plugin_manager(self, plugin_manager):
        """Set plugin manager reference"""
        self.plugin_manager = plugin_manager
        self.refresh_plugin_list()
        
    def refresh_plugin_list(self):
        """Refresh the plugin list display (需求 6.3)"""
        if not self.plugin_manager:
            self.plugin_count_label.setText("0 个")
            return
        
        self.plugin_list.clear()
        plugins = list(self.plugin_manager.plugins.items())
        self.plugin_count_label.setText(f"{len(plugins)} 个")
        
        # Get all plugins from plugin manager
        selected_item = None
        for plugin_name, plugin_instance in plugins:
            metadata = plugin_instance.metadata
            status = plugin_instance.status
            
            # Create list item with plugin info
            item_text = f"{metadata.name} v{metadata.version}\n"
            item_text += f"作者: {metadata.author.github or metadata.author.bilibili}\n"
            item_text += f"状态: {self._get_status_text(status)}"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, plugin_name)
            item.setSizeHint(QSize(0, getattr(self, "_plugin_item_height", 56)))
            
            self.plugin_list.addItem(item)
            if plugin_name == self.selected_plugin_name:
                selected_item = item
        
        # Show message if no plugins
        if self.plugin_list.count() == 0:
            item = QListWidgetItem("暂无已安装插件")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.plugin_list.addItem(item)
            self._clear_details()
        elif selected_item is not None:
            self.plugin_list.setCurrentItem(selected_item)
        else:
            first_item = self.plugin_list.item(0)
            self.plugin_list.setCurrentItem(first_item)
            first_plugin_name = first_item.data(Qt.UserRole)
            if first_plugin_name:
                self.on_plugin_selected(first_plugin_name)
    
    def _get_status_text(self, status: PluginStatus) -> str:
        """Get localized status text"""
        status_map = {
            PluginStatus.NOT_LOADED: "未加载",
            PluginStatus.LOADED: "已加载",
            PluginStatus.ENABLED: "已启用",
            PluginStatus.DISABLED: "已禁用",
            PluginStatus.ERROR: "错误"
        }
        return status_map.get(status, "未知")

    def _update_status_label(self, status: PluginStatus):
        status_colors = {
            PluginStatus.ENABLED: "#247A52",
            PluginStatus.DISABLED: "#737A85",
            PluginStatus.ERROR: "#C93C45",
            PluginStatus.LOADED: "#346AA0",
            PluginStatus.NOT_LOADED: "#737A85",
        }
        color = status_colors.get(status, "#737A85")
        self.status_label.setText(self._get_status_text(status))
        self.status_label.setStyleSheet(
            f"color: {color}; background-color: transparent; border: none; "
            "font-weight: 600; padding: 6px 4px;"
        )
    
    def _on_plugin_item_clicked(self, item):
        """Handle plugin list item click"""
        plugin_name = item.data(Qt.UserRole)
        if plugin_name:
            self.on_plugin_selected(plugin_name)
    
    def on_plugin_selected(self, plugin_name: str):
        """Display plugin details when selected (需求 6.4)"""
        if not self.plugin_manager or plugin_name not in self.plugin_manager.plugins:
            return
        
        self.selected_plugin_name = plugin_name
        plugin_instance = self.plugin_manager.plugins[plugin_name]
        metadata = plugin_instance.metadata
        status = plugin_instance.status
        self.detail_hint.setText(f"当前状态 · {self._get_status_text(status)}")
        
        # Update details labels
        self.name_label.setText(metadata.name or "-")
        self.version_label.setText(metadata.version or "-")
        
        author_text = ""
        if metadata.author.github:
            author_text += f"GitHub: {metadata.author.github}"
        if metadata.author.bilibili:
            if author_text:
                author_text += " | "
            author_text += f"Bilibili: {metadata.author.bilibili}"
        self.author_label.setText(author_text or "-")

        self._update_status_label(status)
        self.description_label.setText(metadata.description or "无")
        self.update_date_label.setText(metadata.update_date or "未知")
        self.github_label.setText(f"GitHub仓库: {metadata.github_repo or '无'}")
        
        # Update button states (需求 6.5, 6.6, 6.7)
        self.enable_btn.setEnabled(status.can_enable())
        self.disable_btn.setEnabled(status.can_disable())
        self.uninstall_btn.setEnabled(True)
    
    def on_enable_plugin(self):
        """Handle enable plugin button click (需求 6.5, 6.6)"""
        if not self.selected_plugin_name or not self.plugin_manager:
            return
        
        success = self.plugin_manager.enable_plugin(self.selected_plugin_name)
        
        if success:
            QMessageBox.information(self, "成功", f"插件 {self.selected_plugin_name} 已启用")
            self.refresh_plugin_list()
            self.on_plugin_selected(self.selected_plugin_name)
        else:
            QMessageBox.warning(self, "失败", f"无法启用插件 {self.selected_plugin_name}")
    
    def on_disable_plugin(self):
        """Handle disable plugin button click (需求 6.6, 6.7)"""
        if not self.selected_plugin_name or not self.plugin_manager:
            return
        
        success = self.plugin_manager.disable_plugin(self.selected_plugin_name)
        
        if success:
            QMessageBox.information(self, "成功", f"插件 {self.selected_plugin_name} 已禁用")
            self.refresh_plugin_list()
            self.on_plugin_selected(self.selected_plugin_name)
        else:
            QMessageBox.warning(self, "失败", f"无法禁用插件 {self.selected_plugin_name}")
    
    def on_uninstall_plugin(self):
        """Handle uninstall plugin button click (需求 6.8, 6.9, 6.10)"""
        if not self.selected_plugin_name or not self.plugin_manager:
            return
        
        # Show confirmation dialog (需求 6.9)
        reply = QMessageBox.question(
            self,
            "确认卸载",
            f"确定要卸载插件 {self.selected_plugin_name} 吗？\n\n"
            "这将删除插件的所有文件，但保留配置数据。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Unload plugin first
        success = self.plugin_manager.unload_plugin(self.selected_plugin_name)
        
        if success:
            # Delete plugin directory (需求 6.10)
            plugin_dir = self.plugin_manager.plugin_directory / self.selected_plugin_name
            try:
                if plugin_dir.exists():
                    shutil.rmtree(plugin_dir)
                
                QMessageBox.information(self, "成功", f"插件 {self.selected_plugin_name} 已卸载")
                self.selected_plugin_name = None
                self.refresh_plugin_list()
                self._clear_details()
            except Exception as e:
                QMessageBox.warning(self, "失败", f"无法删除插件文件: {e}")
        else:
            QMessageBox.warning(self, "失败", f"无法卸载插件 {self.selected_plugin_name}")
    
    def on_install_plugin(self):
        """Handle install plugin button click (需求 6.11, 6.12, 6.13)"""
        if not self.plugin_manager:
            return
        
        # Open file dialog to select plugin ZIP file (需求 6.12)
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择插件包",
            "",
            "ZIP Files (*.zip)"
        )
        
        if not file_path:
            return
        
        try:
            # Extract ZIP file to plugins directory (需求 6.13)
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                # Get plugin name from ZIP (should be the root folder name)
                namelist = zip_ref.namelist()
                if not namelist:
                    raise ValueError("插件包为空")
                
                # Extract to plugins directory
                extract_path = self.plugin_manager.plugin_directory
                zip_ref.extractall(extract_path)
                
                # Find the extracted plugin directory
                plugin_name = namelist[0].split('/')[0]
                plugin_path = extract_path / plugin_name
                
                if not plugin_path.exists():
                    raise ValueError("无法找到解压后的插件目录")
                
                # Load the plugin
                success = self.plugin_manager.load_plugin(plugin_name)
                
                if success:
                    QMessageBox.information(self, "成功", f"插件 {plugin_name} 已安装")
                    self.refresh_plugin_list()
                else:
                    QMessageBox.warning(self, "失败", f"插件安装失败，请查看日志")
                    # Clean up failed installation
                    if plugin_path.exists():
                        shutil.rmtree(plugin_path)
        
        except Exception as e:
            QMessageBox.warning(self, "错误", f"安装插件时出错: {e}")
    
    def on_check_updates(self):
        """
        Handle check updates button click (需求 10.1, 10.2, 10.3, 10.4, 10.5)
        
        Checks for updates for all installed plugins that have a github_repo field.
        """
        if not self.plugin_manager:
            return
        
        # Disable button during check
        self.check_updates_btn.setEnabled(False)
        self.check_updates_btn.setText("检查中...")
        
        try:
            import requests
            import re
            from packaging import version as pkg_version
            
            updates_available = []
            errors = []
            
            # Check each plugin for updates
            for plugin_name, plugin_instance in self.plugin_manager.plugins.items():
                metadata = plugin_instance.metadata
                
                # Skip plugins without github_repo (需求 10.3)
                if not metadata.github_repo:
                    continue
                
                try:
                    # Parse GitHub repo URL (插件系统保持 GitHub)
                    # Expected format: https://github.com/owner/repo
                    match = re.match(r'https://github\.com/([^/]+)/([^/]+)', metadata.github_repo)
                    if not match:
                        errors.append(f"{plugin_name}: 无效的GitHub仓库URL")
                        continue
                    
                    owner, repo = match.groups()
                    
                    # Get latest release from GitHub API (保持 GitHub，不迁移)
                    api_url = get_resource_url('api_releases', owner=owner, repo=repo)
                    response = requests.get(api_url, timeout=10)
                    
                    if response.status_code == 404:
                        # No releases found
                        continue
                    elif response.status_code != 200:
                        errors.append(f"{plugin_name}: GitHub API请求失败 ({response.status_code})")
                        continue
                    
                    release_data = response.json()
                    latest_version = release_data.get('tag_name', '').lstrip('v')
                    
                    if not latest_version:
                        continue
                    
                    # Compare versions (需求 10.4)
                    try:
                        current_ver = pkg_version.parse(metadata.version)
                        latest_ver = pkg_version.parse(latest_version)
                        
                        if latest_ver > current_ver:
                            # Update available (需求 10.5)
                            download_url = None
                            for asset in release_data.get('assets', []):
                                if asset.get('name', '').endswith('.zip'):
                                    download_url = asset.get('browser_download_url')
                                    break
                            
                            updates_available.append({
                                'plugin_name': plugin_name,
                                'current_version': metadata.version,
                                'latest_version': latest_version,
                                'download_url': download_url,
                                'release_notes': release_data.get('body', '')
                            })
                    except Exception as e:
                        errors.append(f"{plugin_name}: 版本比较失败 ({e})")
                
                except requests.RequestException as e:
                    errors.append(f"{plugin_name}: 网络请求失败 ({e})")
                except Exception as e:
                    errors.append(f"{plugin_name}: 检查更新失败 ({e})")
            
            # Show results
            if updates_available:
                self._show_updates_dialog(updates_available)
            elif errors:
                error_msg = "检查更新时出现以下错误:\n\n" + "\n".join(errors)
                QMessageBox.warning(self, "检查更新", error_msg)
            else:
                QMessageBox.information(self, "检查更新", "所有插件都是最新版本")
        
        except ImportError:
            QMessageBox.warning(
                self,
                "缺少依赖",
                "更新检查功能需要安装 requests 和 packaging 库\n\n"
                "请运行: pip install requests packaging"
            )
        except Exception as e:
            QMessageBox.warning(self, "错误", f"检查更新时出错: {e}")
        finally:
            # Re-enable button
            self.check_updates_btn.setEnabled(True)
            self.check_updates_btn.setText("检查更新")
    
    def _show_updates_dialog(self, updates):
        """
        Show dialog with available updates (需求 10.5, 10.6)
        
        Args:
            updates: List of update information dictionaries
        """
        dialog = QMessageBox(self)
        dialog.setWindowTitle("可用更新")
        dialog.setIcon(QMessageBox.Information)
        
        message = f"发现 {len(updates)} 个插件有可用更新:\n\n"
        for update in updates:
            message += f"• {update['plugin_name']}: "
            message += f"{update['current_version']} → {update['latest_version']}\n"
        
        message += "\n是否要更新这些插件?"
        
        dialog.setText(message)
        dialog.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        dialog.setDefaultButton(QMessageBox.Yes)
        
        if dialog.exec_() == QMessageBox.Yes:
            self._install_updates(updates)
    
    def _install_updates(self, updates):
        """
        Install plugin updates (需求 10.6, 10.7, 10.8)
        
        Args:
            updates: List of update information dictionaries
        """
        import requests
        import tempfile
        
        success_count = 0
        failed_updates = []
        
        for update in updates:
            plugin_name = update['plugin_name']
            download_url = update.get('download_url')
            
            if not download_url:
                failed_updates.append(f"{plugin_name}: 无可用下载链接")
                continue
            
            try:
                # Download update (需求 10.7)
                response = requests.get(download_url, timeout=30)
                response.raise_for_status()
                
                # Save to temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_file:
                    temp_file.write(response.content)
                    temp_zip_path = temp_file.name
                
                # Unload current plugin
                if plugin_name in self.plugin_manager.plugins:
                    self.plugin_manager.unload_plugin(plugin_name)
                
                # Delete old plugin directory
                plugin_dir = self.plugin_manager.plugin_directory / plugin_name
                if plugin_dir.exists():
                    shutil.rmtree(plugin_dir)
                
                # Extract new version (需求 10.7)
                with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                    extract_path = self.plugin_manager.plugin_directory
                    zip_ref.extractall(extract_path)
                
                # Clean up temp file
                os.unlink(temp_zip_path)
                
                # Reload plugin (需求 10.8)
                if self.plugin_manager.load_plugin(plugin_name):
                    # Re-enable if it was enabled before
                    if self.plugin_manager._load_plugin_state(plugin_name):
                        self.plugin_manager.enable_plugin(plugin_name)
                    success_count += 1
                else:
                    failed_updates.append(f"{plugin_name}: 重新加载失败")
            
            except Exception as e:
                failed_updates.append(f"{plugin_name}: {e}")
        
        # Show results
        result_msg = f"成功更新 {success_count} 个插件"
        if failed_updates:
            result_msg += f"\n\n失败:\n" + "\n".join(failed_updates)
        
        QMessageBox.information(self, "更新完成", result_msg)
        
        # Refresh plugin list
        self.refresh_plugin_list()
    
    def _clear_details(self):
        """Clear plugin details display"""
        self.detail_hint.setText("插件状态与元数据")
        self.name_label.setText("-")
        self.version_label.setText("-")
        self.author_label.setText("-")
        self.status_label.setText("-")
        self.status_label.setStyleSheet(
            "color: #737A85; background-color: transparent; border: none; "
            "font-weight: 600; padding: 6px 4px;"
        )
        self.description_label.setText("-")
        self.update_date_label.setText("-")
        self.github_label.setText("GitHub: -")
        
        self.enable_btn.setEnabled(False)
        self.disable_btn.setEnabled(False)
        self.uninstall_btn.setEnabled(False)


class PluginMarketTab(QWidget):
    """
    Tab for plugin market (reserved for future implementation)
    
    Requirements: 6.2, 6.14
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        configure_transparent_container(self)
        self.plugin_page = parent
        self._init_ui()
    
    def _init_ui(self):
        """Show a quiet, useful unavailable state for the future market."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        container = StyledContainer()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(28, 24, 28, 28)
        container_layout.setSpacing(10)

        header_layout = QHBoxLayout()
        self.title_label = QLabel("插件市场")
        self.title_label.setProperty("pluginFontRole", "sectionTitle")
        self.title_label.setStyleSheet(
            "background-color: transparent; border: none; font-weight: 600;"
        )
        status = QLabel("筹备中")
        self.status_label = status
        status.setProperty("pluginFontRole", "small")
        status.setStyleSheet(
            "background-color: #F0F2F5; border: none; "
            "border-radius: 10px; padding: 3px 9px;"
        )
        header_layout.addWidget(self.title_label)
        header_layout.addSpacing(8)
        header_layout.addWidget(status)
        header_layout.addStretch()
        container_layout.addLayout(header_layout)

        self.subtitle_label = QLabel("在线插件目录尚未开放")
        self.subtitle_label.setProperty("pluginFontRole", "small")
        self.subtitle_label.setStyleSheet("background-color: transparent; border: none;")
        container_layout.addWidget(self.subtitle_label)
        container_layout.addStretch(2)

        self.state_title = QLabel("在线目录即将开放")
        self.state_title.setProperty("pluginFontRole", "cardTitle")
        self.state_title.setAlignment(Qt.AlignCenter)
        self.state_title.setStyleSheet(
            "background-color: transparent; border: none; font-weight: 600;"
        )
        container_layout.addWidget(self.state_title)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        action_row.addStretch()

        self.installed_btn = QPushButton("查看已安装")
        self.installed_btn.setCursor(Qt.PointingHandCursor)
        self.installed_btn.clicked.connect(self._show_installed)

        self.install_btn = QPushButton("从本地安装")
        self.install_btn.setCursor(Qt.PointingHandCursor)
        self.install_btn.clicked.connect(self._install_local_plugin)

        action_row.addWidget(self.installed_btn)
        action_row.addWidget(self.install_btn)
        action_row.addStretch()
        container_layout.addLayout(action_row)
        container_layout.addStretch(3)
        
        layout.addWidget(container)
        self._container = container
        self.apply_theme()

    def apply_scale(self, scale, family, body_size, title_size):
        self.layout().setContentsMargins(0, 0, 0, 0)
        self._container.layout().setContentsMargins(
            int(round(28 * scale)), int(round(24 * scale)),
            int(round(28 * scale)), int(round(28 * scale))
        )
        self._container.layout().setSpacing(max(6, int(round(10 * scale))))
        for button in (self.installed_btn, self.install_btn):
            button.setFixedHeight(max(30, int(round(36 * scale))))

    def apply_theme(self):
        colors = _plugin_theme(getattr(self.plugin_page, "settings_manager", None))
        if not hasattr(self, "_container"):
            return
        self._container.apply_theme(getattr(self.plugin_page, "settings_manager", None))
        self.title_label.setStyleSheet(
            f"background-color: transparent; border: none; color: {colors['text']}; font-weight: 600;"
        )
        self.subtitle_label.setStyleSheet(
            f"background-color: transparent; border: none; color: {colors['muted']};"
        )
        self.state_title.setStyleSheet(
            f"background-color: transparent; border: none; color: {colors['text']}; font-weight: 600;"
        )
        self.status_label.setStyleSheet(
            f"background-color: {colors['component']}; border: none; color: {colors['muted']}; "
            "border-radius: 10px; padding: 3px 9px;"
        )
        self.installed_btn.setStyleSheet(f"""
            QPushButton {{ color: {colors['text']}; background-color: {colors['card']};
                border: 1px solid {colors['component']}; border-radius: 4px; padding: 7px 16px; }}
            QPushButton:hover {{ background-color: {colors['component']}; }}
        """)
        self.install_btn.setStyleSheet(f"""
            QPushButton {{ color: #FFFFFF; background-color: {colors['accent']};
                border: 1px solid {colors['accent']}; border-radius: 4px; padding: 7px 16px; }}
            QPushButton:hover {{ background-color: {colors['accent']}; }}
        """)

    def _show_installed(self):
        if self.plugin_page:
            self.plugin_page.show_installed_plugins()

    def _install_local_plugin(self):
        if not self.plugin_page:
            return
        self.plugin_page.installed_tab.on_install_plugin()
        self.plugin_page.show_installed_plugins()


class FastScrollingLabel(QLabel):
    """流媒体页面 ScrollingLabel 的 2 倍速版本。文本超出时自动横向滚动。"""
    STEP_PX = 2
    GAP_PX = 40

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.setContentsMargins(0, 0, 0, 0)
        self.original_text = ""
        self.offset_px = 0
        self._max_offset = 0
        self.scroll_timer = QTimer(self)
        self.scroll_timer.setInterval(200)  # 2倍速
        self.scroll_timer.timeout.connect(self._scroll_text)
        self._paused = False
        self._overflow = False

    def set_scrolling_text(self, text: str):
        self.original_text = text
        self.offset_px = 0
        super().setText(text)
        self.update_text_display()

    def _recompute_overflow(self):
        fm = self.fontMetrics()
        margins = self.contentsMargins()
        widget_width = self.width() - margins.left() - margins.right()
        if widget_width <= 0:
            self._overflow = False
            self._max_offset = 0
            return
        text_width = fm.width(self.original_text)
        self._overflow = text_width > widget_width
        self._max_offset = max(0, text_width - widget_width + self.GAP_PX)

    def update_text_display(self):
        self._recompute_overflow()
        if not self._overflow:
            self.scroll_timer.stop()
            self.offset_px = 0
        elif not self._paused and not self.scroll_timer.isActive():
            self.scroll_timer.start()
        self.update()

    def pause_scroll(self):
        self._paused = True
        if self.scroll_timer.isActive():
            self.scroll_timer.stop()

    def resume_scroll(self):
        self._paused = False
        if self._overflow and not self.scroll_timer.isActive():
            self.scroll_timer.start()

    def _scroll_text(self):
        if not self._overflow:
            self.scroll_timer.stop()
            self.offset_px = 0
            self.update()
            return
        self.offset_px += self.STEP_PX
        if self.offset_px >= self._max_offset:
            self.offset_px = 0
        self.update()

    def paintEvent(self, event):
        if not self._overflow:
            super().paintEvent(event)
            return
        fm = self.fontMetrics()
        margins = self.contentsMargins()
        x_start = margins.left() - self.offset_px
        y = (self.height() + fm.ascent() - fm.descent()) // 2
        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setPen(self.palette().color(QPalette.WindowText))
        painter.drawText(x_start, y, self.original_text)
        painter.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_text_display()


class _PluginSubTabButton(QPushButton):
    """左侧二级选项卡按钮，内嵌 FastScrollingLabel。"""
    clicked_with_name = pyqtSignal(str)

    def __init__(self, plugin_name: str, parent=None):
        super().__init__(parent)
        self._plugin_name = plugin_name
        self.setCursor(Qt.PointingHandCursor)
        self.setCheckable(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumWidth(0)
        self.setFixedHeight(36)
        self.apply_theme()
        self._scroller = FastScrollingLabel(self)
        self._scroller.set_scrolling_text(plugin_name)
        self._update_scroller_style(False)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.setSpacing(0)
        lay.addWidget(self._scroller)

        def _on_enter(e):
            self._scroller.pause_scroll()
            super(type(self), self).enterEvent(e)

        def _on_leave(e):
            self._scroller.resume_scroll()
            super(type(self), self).leaveEvent(e)

        self.enterEvent = _on_enter
        self.leaveEvent = _on_leave
        self.toggled.connect(self._update_scroller_style)
        self.clicked.connect(lambda: self.clicked_with_name.emit(self._plugin_name))

    def _update_scroller_style(self, checked: bool):
        if not hasattr(self, "_scroller"):
            return
        color = "#FFFFFF" if checked else getattr(self, "_normal_text_color", "#343943")
        self._scroller.setStyleSheet(
            f"background: transparent; border: none; color: {color};"
        )

    def apply_scale(self, scale):
        self.setFixedHeight(max(32, int(round(36 * scale))))
        layout = self.layout()
        if layout:
            margin = max(5, int(round(8 * scale)))
            layout.setContentsMargins(margin, 0, margin, 0)

    def apply_theme(self, settings_manager=None):
        colors = _plugin_theme(settings_manager)
        self._normal_text_color = colors["text"]
        self.setStyleSheet(f"""
            _PluginSubTabButton {{
                background-color: {colors['card']};
                color: {colors['text']};
                border: 1px solid {colors['component']};
                border-radius: 5px;
                padding: 4px 6px;
                text-align: center;
            }}
            _PluginSubTabButton:checked {{
                background-color: {colors['accent']};
                border-color: {colors['accent']};
                color: #FFFFFF;
                font-weight: 600;
            }}
            _PluginSubTabButton:hover:!checked {{
                background-color: {colors['component']};
                border-color: {colors['accent']};
            }}
        """)
        self._update_scroller_style(self.isChecked())

    @property
    def plugin_name(self) -> str:
        return self._plugin_name


class PluginSettingsTab(QWidget):
    """
    Tab for plugin settings with a settings-style secondary selector.
    Each plugin that provides get_settings_widget() gets a sub-tab.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        configure_transparent_container(self)
        self.plugin_page = parent
        self.plugin_manager = None
        self._plugins: dict = {}
        self._tab_buttons: dict = {}
        self._init_ui()

    def _init_ui_legacy(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._tab_bar = StyledContainer()
        self._tab_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        tab_bar_layout = QHBoxLayout(self._tab_bar)
        tab_bar_layout.setContentsMargins(18, 14, 18, 14)
        tab_bar_layout.setSpacing(12)

        title = QLabel("设置面板")
        title.setStyleSheet(
            "color: #20232A; font-size: 15px; font-weight: 600; border: none;"
        )
        tab_bar_layout.addWidget(title)

        self._plugin_count_label = QLabel("0 个可配置插件")
        self._plugin_count_label.setStyleSheet(
            "color: #747B86; background: #F1F3F6; border: none; "
            "border-radius: 9px; padding: 2px 8px;"
        )
        tab_bar_layout.addWidget(self._plugin_count_label)

        self._selector_host = QWidget()
        self._selector_host.setStyleSheet("background: transparent;")
        self._selector_host.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._selector_host.setMinimumHeight(36)
        self._tab_button_row = QHBoxLayout(self._selector_host)
        self._tab_button_row.setContentsMargins(0, 0, 0, 0)
        self._tab_button_row.setSpacing(8)

        selector_scroll = QScrollArea()
        selector_scroll.setWidgetResizable(True)
        selector_scroll.setFrameShape(QFrame.NoFrame)
        selector_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        selector_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        selector_scroll.setFixedHeight(38)
        selector_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        set_transparent_scroll_content(selector_scroll, self._selector_host)
        tab_bar_layout.addWidget(selector_scroll, 1)

        layout.addWidget(self._tab_bar)

        self._group = QButtonGroup(self)
        self._group.buttonClicked.connect(self._on_button_clicked)

        self._content_stack = QStackedWidget()
        self._content_stack.setStyleSheet("QStackedWidget { background: transparent; }")
        layout.addWidget(self._content_stack)

        self._opacity_effect = QGraphicsOpacityEffect(self._content_stack)
        self._content_stack.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setEnabled(False)
        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_anim.setDuration(200)
        self._fade_anim.setEasingCurve(QEasingCurve.InOutQuad)
        self._fade_anim.finished.connect(self._on_fade_finished)
        self._target_index = 0

        self._show_empty_state("暂无可配置插件", "已启用的插件均未提供设置面板")

    def _init_ui(self):
        """Build a left-hand vertical selector and a right settings surface."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._tab_bar = StyledContainer()
        self._tab_bar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self._tab_bar.setFixedWidth(210)
        tab_bar_layout = QVBoxLayout(self._tab_bar)
        tab_bar_layout.setContentsMargins(14, 16, 14, 16)
        tab_bar_layout.setSpacing(8)

        self.selector_title_label = QLabel("插件设置")
        self.selector_title_label.setProperty("pluginFontRole", "sectionTitle")
        self.selector_title_label.setStyleSheet(
            "background-color: transparent; border: none; font-weight: 600;"
        )
        tab_bar_layout.addWidget(self.selector_title_label)

        self._plugin_count_label = QLabel("0 个可配置插件")
        self._plugin_count_label.setProperty("pluginFontRole", "small")
        tab_bar_layout.addWidget(self._plugin_count_label)

        self._selector_host = QWidget()
        configure_transparent_container(self._selector_host)
        self._selector_host.setStyleSheet("background-color: transparent; border: none;")
        self._tab_button_row = QVBoxLayout(self._selector_host)
        self._tab_button_row.setContentsMargins(0, 8, 0, 0)
        self._tab_button_row.setSpacing(8)

        selector_scroll = QScrollArea()
        configure_transparent_container(selector_scroll)
        selector_scroll.setWidgetResizable(True)
        selector_scroll.setFrameShape(QFrame.NoFrame)
        selector_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        selector_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        selector_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        set_transparent_scroll_content(selector_scroll, self._selector_host)
        tab_bar_layout.addWidget(selector_scroll, 1)
        layout.addWidget(self._tab_bar)

        self._group = QButtonGroup(self)
        self._group.buttonClicked.connect(self._on_button_clicked)

        self._content_stack = QStackedWidget()
        configure_transparent_container(self._content_stack)
        self._content_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._content_stack.setStyleSheet("QStackedWidget { background: transparent; }")
        layout.addWidget(self._content_stack, 1)

        self._opacity_effect = QGraphicsOpacityEffect(self._content_stack)
        self._content_stack.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setEnabled(False)
        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_anim.setDuration(200)
        self._fade_anim.setEasingCurve(QEasingCurve.InOutQuad)
        self._fade_anim.finished.connect(self._on_fade_finished)
        self._target_index = 0

        self._show_empty_state("暂无可配置插件", "已启用的插件均未提供设置面板")
        self.apply_theme()

    def apply_scale(self, scale, family, body_size, title_size):
        self.layout().setSpacing(max(6, int(round(10 * scale))))
        self._tab_bar.setFixedWidth(max(170, int(round(210 * scale))))
        self._tab_bar.layout().setContentsMargins(
            int(round(14 * scale)), int(round(16 * scale)),
            int(round(14 * scale)), int(round(16 * scale))
        )
        self._tab_bar.layout().setSpacing(max(6, int(round(8 * scale))))
        self._tab_button_row.setSpacing(max(6, int(round(8 * scale))))
        for button in self._tab_buttons.values():
            button.apply_scale(scale)

    def apply_theme(self):
        colors = _plugin_theme(getattr(self.plugin_page, "settings_manager", None))
        if not hasattr(self, "_tab_bar"):
            return
        self._tab_bar.apply_theme(getattr(self.plugin_page, "settings_manager", None))
        self.selector_title_label.setStyleSheet(
            f"background-color: transparent; border: none; color: {colors['text']}; font-weight: 600;"
        )
        self._plugin_count_label.setStyleSheet(
            f"background-color: transparent; border: none; color: {colors['muted']};"
        )
        for button in self._tab_buttons.values():
            button.apply_theme(getattr(self.plugin_page, "settings_manager", None))

    def _show_empty_state(self, title_text: str, detail_text: str):
        colors = _plugin_theme(getattr(self.plugin_page, "settings_manager", None))
        empty_state = StyledContainer()
        empty_layout = QVBoxLayout(empty_state)
        empty_layout.setContentsMargins(24, 24, 24, 24)
        empty_layout.addStretch()

        title = QLabel(title_text)
        title.setProperty("pluginFontRole", "cardTitle")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            f"background-color: transparent; border: none; color: {colors['text']}; font-weight: 600;"
        )
        detail = QLabel(detail_text)
        detail.setProperty("pluginFontRole", "body")
        detail.setAlignment(Qt.AlignCenter)
        detail.setStyleSheet(
            f"background-color: transparent; border: none; color: {colors['muted']};"
        )
        empty_layout.addWidget(title)
        empty_layout.addWidget(detail)
        empty_layout.addStretch()
        self._content_stack.addWidget(empty_state)

    def set_plugin_manager(self, plugin_manager):
        self.plugin_manager = plugin_manager
        self._refresh_all()

    def show_plugin_settings(self, plugin_name: str):
        self._refresh_all()
        if plugin_name in self._tab_buttons:
            self._tab_buttons[plugin_name].setChecked(True)
            idx = self._content_stack.indexOf(self._plugins.get(plugin_name))
            if idx >= 0:
                self._animate_to(idx)

    def _on_button_clicked(self, btn):
        for name, b in self._tab_buttons.items():
            if b is btn and name in self._plugins:
                idx = self._content_stack.indexOf(self._plugins[name])
                if idx >= 0:
                    self._animate_to(idx)
                break

    def _animate_to(self, index: int):
        if self._content_stack.currentIndex() == index:
            return
        self._target_index = index
        self._opacity_effect.setEnabled(True)
        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.start()

    def _on_fade_finished(self):
        if self._opacity_effect.opacity() < 0.5:
            self._content_stack.setCurrentIndex(self._target_index)
            self._fade_anim.setStartValue(0.0)
            self._fade_anim.setEndValue(1.0)
            self._fade_anim.start()
        else:
            self._opacity_effect.setEnabled(False)

    def _refresh_all(self):
        current_name = next(
            (name for name, button in self._tab_buttons.items() if button.isChecked()),
            None,
        )

        while self._tab_button_row.count():
            item = self._tab_button_row.takeAt(0)
            w = item.widget()
            if w:
                self._group.removeButton(w)
                w.deleteLater()

        while self._content_stack.count():
            w = self._content_stack.widget(0)
            self._content_stack.removeWidget(w)
            w.deleteLater()

        self._plugins.clear()
        self._tab_buttons.clear()
        self._plugin_count_label.setText("0 个可配置插件")

        if not self.plugin_manager:
            self._show_empty_state("插件系统尚未就绪", "暂时没有可显示的插件设置")
            return

        has_content = False
        for plugin_name, plugin_instance in self.plugin_manager.plugins.items():
            if plugin_instance.status != PluginStatus.ENABLED:
                continue
            mod = getattr(plugin_instance, 'module', None)
            if mod is None:
                continue
            if not hasattr(mod, 'get_settings_widget'):
                continue
            try:
                widget = mod.get_settings_widget(self._content_stack)
                if widget is None:
                    continue
                self._plugins[plugin_name] = widget
                self._content_stack.addWidget(widget)
                has_content = True
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    f"Plugin {plugin_name} get_settings_widget failed: {e}"
                )

        if not has_content:
            self._show_empty_state("暂无可配置插件", "已启用的插件均未提供设置面板")
            return

        self._plugin_count_label.setText(f"{len(self._plugins)} 个可配置插件")

        first_name = None
        btn_id = 0
        for plugin_name in self._plugins:
            if first_name is None:
                first_name = plugin_name
            btn = _PluginSubTabButton(plugin_name)
            self._group.addButton(btn, btn_id)
            btn_id += 1
            self._tab_button_row.addWidget(btn)
            self._tab_buttons[plugin_name] = btn

        self._tab_button_row.addStretch()

        selected_name = current_name if current_name in self._plugins else first_name
        if selected_name:
            self._tab_buttons[selected_name].setChecked(True)
            idx = self._content_stack.indexOf(self._plugins[selected_name])
            if idx >= 0:
                self._content_stack.setCurrentIndex(idx)

    def _switch_to(self, plugin_name: str):
        for name, btn in self._tab_buttons.items():
            btn.setChecked(name == plugin_name)
        if plugin_name in self._plugins:
            idx = self._content_stack.indexOf(self._plugins[plugin_name])
            if idx >= 0:
                self._animate_to(idx)

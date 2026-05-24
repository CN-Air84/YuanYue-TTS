# coding=utf-8
import sys
import json
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QLineEdit, QPushButton, QGroupBox, QFormLayout,
    QSpinBox, QDoubleSpinBox, QScrollArea, QCheckBox, QSlider, QFileDialog,
    QStackedWidget, QButtonGroup, QGraphicsOpacityEffect, QFrame, QSizePolicy,
    QGridLayout, QApplication, QSplitter, QMessageBox, QListWidget, QListWidgetItem,
    QCompleter
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QObject, QEvent, QVariantAnimation, pyqtProperty, 
    QPropertyAnimation, QParallelAnimationGroup, QEasingCurve, QUrl, QTimer,
    QMimeData
)
from PyQt5.QtGui import QFont, QColor, QDesktopServices, QDrag, QPixmap

from misc_func import SettingsManager, CustomConfig, get_app_base_path
from shared_memory_manager import get_shared_memory_manager
from debug_logger import debug_logger, LogLevel

_AI_MANAGER_MODULE = None


def _get_ai_manager_module():
    """按需加载 ai_manager，避免设置页模块导入时拉起重依赖。"""
    global _AI_MANAGER_MODULE
    if _AI_MANAGER_MODULE is None:
        import ai_manager as ai_manager_module
        _AI_MANAGER_MODULE = ai_manager_module
    return _AI_MANAGER_MODULE


class WheelEventFilter(QObject):
    """鼠标滚轮事件过滤器 - 禁止通过滚轮改变数值"""
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel:
            return True
        return False


class SmoothButton(QPushButton):
    """平滑变色动画按钮"""
    def __init__(self, text, btn_type="normal", parent=None):
        super().__init__(text, parent)
        self.btn_type = btn_type
        self.setCheckable(True)
        
        self.normal_bg = QColor(255, 255, 255)
        self.normal_color = QColor(0, 0, 0)
        self.normal_border = QColor("gray")
        
        if btn_type == "tab_level1" or btn_type == "tab_level2":
            self.checked_bg = QColor(85, 85, 255)
            self.checked_color = QColor(255, 255, 255)
            self.checked_border = QColor("gray")
            self.radius = 5
            self.padding = "8px 16px"
        elif btn_type == "model":
            self.checked_bg = QColor(0, 255, 0)
            self.checked_color = QColor(0, 0, 0)
            self.checked_border = QColor("#D0D0D0")
            self.radius = 4
            self.padding = "12px"
        elif btn_type == "action":
            self.normal_bg = QColor(85, 170, 255) 
            self.normal_color = QColor(255, 255, 255)
            self.normal_border = QColor("gray")
            self.checked_bg = self.normal_bg
            self.checked_color = self.normal_color
            self.checked_border = self.normal_border
            self.radius = 5
            self.padding = "8px 16px"
            self.setCheckable(False)
        else:
            self.checked_bg = QColor(230, 230, 230)
            self.checked_color = QColor(0, 0, 0)
            self.checked_border = QColor("gray")
            self.radius = 5
            self.padding = "8px 16px"
            
        self._bg_color = self.checked_bg if self.isChecked() else self.normal_bg
        self._text_color = self.checked_color if self.isChecked() else self.normal_color
        
        self.bg_anim = QVariantAnimation(self)
        self.bg_anim.setDuration(250)
        self.bg_anim.valueChanged.connect(self._on_bg_changed)
        
        self.color_anim = QVariantAnimation(self)
        self.color_anim.setDuration(250)
        self.color_anim.valueChanged.connect(self._on_color_changed)
        
        self.toggled.connect(self._on_toggled)
        self._update_stylesheet()
        
    def _on_toggled(self, checked):
        if self.btn_type == "action": return
        self.bg_anim.stop()
        self.color_anim.stop()
        
        self.bg_anim.setStartValue(self._bg_color)
        self.bg_anim.setEndValue(self.checked_bg if checked else self.normal_bg)
        
        self.color_anim.setStartValue(self._text_color)
        self.color_anim.setEndValue(self.checked_color if checked else self.normal_color)
        
        self.bg_anim.start()
        self.color_anim.start()

    def _on_bg_changed(self, color):
        self._bg_color = color
        self._update_stylesheet()
        
    def _on_color_changed(self, color):
        self._text_color = color
        self._update_stylesheet()
        
    def _update_stylesheet(self):
        border_color = self.checked_border.name() if self.isChecked() else self.normal_border.name()
        if self.btn_type == "model":
            border_color = "#D0D0D0"
        
        css = f"""
            QPushButton {{
                background-color: {self._bg_color.name()};
                color: {self._text_color.name()};
                border: 1px solid {border_color};
                border-radius: {self.radius}px;
                padding: {self.padding};
            }}
        """
        self.setStyleSheet(css)


class StyledContainer(QFrame):
    """带圆角白底灰边的容器"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            StyledContainer {
                background-color: #FFFFFF;
                border: 1px solid #D0D0D0;
                border-radius: 5px;
            }
        """)


# --- 兼容原有设置分组，稍作修改以适应新UI ---

class DownloadSettingsGroup(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings_manager = SettingsManager()
        self.wheel_filter = WheelEventFilter()
        self._init_styles()
        self._init_ui()
        self._load_settings()
        self._connect_signals()

    def _init_styles(self):
        self.STYLES = {
            'container': '''
                background-color: rgb(255, 255, 255);
                border-radius: 5px;
            ''',
            'input': '''
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                padding: 4px;
                selection-background-color: #4A90E2;
            ''',
            'select_button': '''
                background-color: rgb(125, 125, 255);
                border-radius: 5px;
                border: 1px solid gray;
                color:rgb(255, 255, 255);
            ''',
            'slider': '''
                QSlider::groove:horizontal {
                    background: #E0E0E0;
                    height: 16px;
                    border-radius: 6px;
                }
                QSlider::sub-page:horizontal {
                    background: #4A90E2;
                    border-radius: 3px;
                }
                QSlider::handle:horizontal {
                    background: white;
                    width: 12px;
                    height: 10px;
                    border-radius: 8px;
                    border: 2px solid #4A90E2;
                }
                QSlider::handle:horizontal:hover {
                    background: #F0F8FF;
                    border: 2px solid #357ABD;
                }
                QSlider::handle:horizontal:pressed {
                    background: #4A90E2;
                    border: 2px solid #357ABD;
                }
            ''',
            'label': '''
                border: none;
                background: transparent;
            ''',
            'combo': '''
                QComboBox {
                    background-color: white;
                    border: 1px solid #E0E0E0;
                    border-radius: 4px;
                    padding: 2px 8px;
                    min-height: 16px;
                    min-width: 80px;
                }
                QComboBox:focus {
                    border: 1px solid #4A90E2;
                }
                QComboBox::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: center right;
                    width: 24px;
                    border: none;
                    border-left: 1px solid #E0E0E0;
                    border-top-right-radius: 4px;
                    border-bottom-right-radius: 4px;
                }
                QComboBox::drop-down:hover {
                    background-color: #4A90E2;
                    border-left: 1px solid #4A90E2;
                }
                QComboBox::down-arrow {
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 6px solid #666;
                    width: 0px;
                    height: 0px;
                }
                QComboBox::drop-down:hover QComboBox::down-arrow {
                    border-top-color: white;
                }
                QComboBox QAbstractItemView {
                    background-color: white;
                    border: 1px solid #E0E0E0;
                    border-radius: 4px;
                    padding: 2px;
                    outline: none;
                    selection-background-color: #4A90E2;
                    selection-color: white;
                    alternate-background-color: #F9F9F9;
                }
                QComboBox QAbstractItemView::item {
                    height: 26px;
                    padding: 0 8px;
                    border-radius: 3px;
                    margin: 1px 2px;
                }
                QComboBox QAbstractItemView::item:hover {
                    background-color: #F0F8FF;
                    color: #333;
                }
            '''
        }
        # The container itself is styled by the scroll area, so we don't set it here.
        # self.setStyleSheet(self.STYLES['container'])

    def _init_ui(self):
        # Use a frame to hold the content and apply the container style
        container_frame = QFrame(self)
        container_frame.setStyleSheet(self.STYLES['container'])
        
        # Main layout for the DownloadSettingsGroup, which will contain the frame
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container_frame)

        layout = QFormLayout(container_frame)
        layout.setSpacing(28)
        layout.setContentsMargins(30, 20, 30, 20)

        # Download Threads
        thread_layout = QHBoxLayout()
        
        self.thread_min_label = QLabel("1")
        self.thread_min_label.setStyleSheet(self.STYLES['label'])
        
        self.thread_slider = QSlider(Qt.Horizontal)
        self.thread_slider.setRange(1, 32)
        self.thread_slider.setStyleSheet(self.STYLES['slider'])
        self.thread_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.thread_slider.setMinimumHeight(50)
        
        self.thread_max_label = QLabel("32")
        self.thread_max_label.setStyleSheet(self.STYLES['label'])
        
        self.thread_input = QLineEdit()
        self.thread_input.setFixedWidth(100)
        self.thread_input.setAlignment(Qt.AlignCenter)
        self.thread_input.setStyleSheet(self.STYLES['input'])

        thread_layout.addWidget(self.thread_min_label)
        thread_layout.addWidget(self.thread_slider)
        thread_layout.addWidget(self.thread_max_label)
        thread_layout.addWidget(self.thread_input)
        
        threads_label = QLabel("下载线程数:")
        threads_label.setStyleSheet(self.STYLES['label'])
        layout.addRow(threads_label, thread_layout)

        # Default Save Path
        self.save_path_display = QLineEdit()
        self.save_path_display.setReadOnly(True)
        self.save_path_display.setText("未实现")
        # 修改样式以预留右侧按钮空间
        path_style = self.STYLES['input'].replace('padding: 4px;', 'padding: 4px; padding-right: 75px;')
        self.save_path_display.setStyleSheet(path_style)
        
        self.save_path_button = QPushButton("选择路径", self.save_path_display)
        self.save_path_button.setCursor(Qt.PointingHandCursor)
        self.save_path_button.setEnabled(False)
        self.save_path_button.setStyleSheet('''
            QPushButton {
                background-color: #55aaff;
                border-radius: 4px;
                color: white;
                border: none;
            }
            QPushButton:hover {
                background-color: #4499ee;
            }
            QPushButton:disabled {
                background-color: #aaccff;
            }
        ''')
        
        inner_layout = QHBoxLayout(self.save_path_display)
        inner_layout.setContentsMargins(0, 0, 2, 0)
        self.save_path_button.setFixedSize(70, 26)
        inner_layout.addWidget(self.save_path_button, 0, Qt.AlignRight | Qt.AlignVCenter)
        
        save_path_label = QLabel("默认保存路径:")
        save_path_label.setStyleSheet(self.STYLES['label'])
        layout.addRow(save_path_label, self.save_path_display)

        # Github Mirror
        self.github_mirror_combo = QComboBox()
        self.github_mirror_combo.addItems([
            "直接从github服务器获取（海外首选）",
            "ghfast（中国大陆首选）",
            "ghproxy 主站（CloudFlare CDN，大陆备用）",
            "ghproxy HK（港澳台首选）",
            "ghproxy edgeone（备用）"
        ])
        self.github_mirror_combo.installEventFilter(self.wheel_filter)
        self.github_mirror_combo.setStyleSheet(self.STYLES['combo'])
        
        github_mirror_label = QLabel("Github下载加速源:")
        github_mirror_label.setStyleSheet(self.STYLES['label'])
        layout.addRow(github_mirror_label, self.github_mirror_combo)

        # Online Resource Source
        self.resource_source_combo = QComboBox()
        self.resource_source_combo.addItem("GitHub（默认）", "github")
        self.resource_source_combo.addItem("Gitee（国内镜像）", "gitee")
        self.resource_source_combo.addItem("（尚未完工）官网", "custom")
        self.resource_source_combo.installEventFilter(self.wheel_filter)
        self.resource_source_combo.setStyleSheet(self.STYLES['combo'])

        resource_source_label = QLabel("在线信息源:")
        resource_source_label.setStyleSheet(self.STYLES['label'])
        layout.addRow(resource_source_label, self.resource_source_combo)

        # 置底最大下载线程数：添加弹性空间
        spacer_widget = QWidget()
        spacer_widget.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        layout.addRow(spacer_widget)

        # Max Download Threads Input
        self.max_threads_input = QLineEdit()
        self.max_threads_input.setFixedWidth(75)
        self.max_threads_input.setStyleSheet(self.STYLES['input'])
        
        max_threads_label = QLabel("最大下载线程数:")
        max_threads_label.setStyleSheet(self.STYLES['label'])
        layout.addRow(max_threads_label, self.max_threads_input)

    def _connect_signals(self):
        self.thread_slider.valueChanged.connect(self._on_slider_changed)
        self.thread_input.editingFinished.connect(self._on_thread_input_editing_finished)
        self.max_threads_input.editingFinished.connect(self._on_max_threads_editing_finished)
        self.github_mirror_combo.currentTextChanged.connect(self._on_github_mirror_changed)
        self.resource_source_combo.currentIndexChanged.connect(self._on_resource_source_changed)

    def _on_slider_changed(self, value):
        self.thread_input.setText(str(value))
        self.settings_manager.Custom.set_value("download_threads", str(value))
        
    def _on_thread_input_editing_finished(self):
        text = self.thread_input.text()
        try:
            value = int(text)
            if 1 <= value <= self.thread_slider.maximum():
                self.thread_slider.setValue(value)
            else:
                self.thread_input.setText(str(self.thread_slider.value()))
        except (ValueError, TypeError):
            self.thread_input.setText(str(self.thread_slider.value()))

    def _on_max_threads_editing_finished(self):
        text = self.max_threads_input.text()
        try:
            value = int(text)
            if not (1 <= value <= 100):
                old_max = self.thread_slider.maximum()
                self.max_threads_input.setText(str(old_max))
                return

            self.thread_slider.setRange(1, value)
            self.thread_max_label.setText(str(value))
            self.settings_manager.Custom.set_value("max_download_threads", str(value))

        except (ValueError, TypeError):
            old_max = self.thread_slider.maximum()
            self.max_threads_input.setText(str(old_max))

    def _on_github_mirror_changed(self, text):
        selected_text = self.github_mirror_combo.currentText()
        self.settings_manager.Custom.set_value("github_mirror", selected_text)

    def _on_resource_source_changed(self, index):
        source = self.resource_source_combo.itemData(index)
        if not source:
            return
        self.settings_manager.Custom.set_value("resource_source", source)
        from resource_urls import ResourceURLManager
        ResourceURLManager.set_source(source)

    def _load_settings(self):
        max_download_threads_str = self.settings_manager.Custom.get_value("max_download_threads", "32")
        try:
            max_thread_val = int(max_download_threads_str)
            if not 1 <= max_thread_val <= 100:
                max_thread_val = 32
        except (ValueError, TypeError):
            max_thread_val = 32
        
        self.max_threads_input.setText(str(max_thread_val))
        self.thread_slider.setRange(1, max_thread_val)
        self.thread_max_label.setText(str(max_thread_val))

        download_threads_str = self.settings_manager.Custom.get_value("download_threads", "16")
        try:
            thread_val = int(download_threads_str)
            if not 1 <= thread_val <= max_thread_val:
                thread_val = min(16, max_thread_val)
        except (ValueError, TypeError):
            thread_val = min(16, max_thread_val)
            
        self.thread_slider.setValue(thread_val)
        self.thread_input.setText(str(thread_val))

        # Resource source
        from resource_urls import ResourceURLManager
        current_source = ResourceURLManager.get_current_source()
        idx = self.resource_source_combo.findData(current_source)
        if idx >= 0:
            self.resource_source_combo.setCurrentIndex(idx)


class DictationSettingsGroup(QWidget):
    """听写设置组"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings_manager = SettingsManager()
        self.wheel_filter = WheelEventFilter()
        self._init_styles()
        self._init_ui()
        self._load_settings()

    def _init_styles(self):
        self.STYLES = {
            'container': '''
                background-color: rgb(255, 255, 255);
                border-radius: 5px;
                border: 1px solid #D0D0D0;
            ''',
            'label': '''
                border: none;
                background: transparent;
            ''',
            'combo': '''
                QComboBox {
                    background-color: white;
                    border: 1px solid #E0E0E0;
                    border-radius: 4px;
                    padding: 4px 8px;
                    min-height: 20px;
                    min-width: 80px;
                }
                QComboBox:focus {
                    border: 1px solid #4A90E2;
                }
                QComboBox::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: center right;
                    width: 24px;
                    border: none;
                    border-left: 1px solid #E0E0E0;
                    border-top-right-radius: 4px;
                    border-bottom-right-radius: 4px;
                }
                QComboBox::drop-down:hover {
                    background-color: #4A90E2;
                    border-left: 1px solid #4A90E2;
                }
                QComboBox::down-arrow {
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 6px solid #666;
                    width: 0px;
                    height: 0px;
                }
                QComboBox::drop-down:hover QComboBox::down-arrow {
                    border-top-color: white;
                }
                QComboBox QAbstractItemView {
                    background-color: white;
                    border: 1px solid #E0E0E0;
                    border-radius: 4px;
                    padding: 2px;
                    outline: none;
                    selection-background-color: #4A90E2;
                    selection-color: white;
                    alternate-background-color: #F9F9F9;
                }
                QComboBox QAbstractItemView::item {
                    height: 26px;
                    padding: 0 8px;
                    border-radius: 3px;
                    margin: 1px 2px;
                }
                QComboBox QAbstractItemView::item:hover {
                    background-color: #F0F8FF;
                    color: #333;
                }
            ''',
            'checkbox': '''
                QCheckBox {
                    border: none;
                    background: transparent;
                    spacing: 5px;
                }
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                    border: 1px solid #D0D0D0;
                    border-radius: 3px;
                    background-color: white;
                }
                QCheckBox::indicator:checked {
                    background-color: rgb(85, 85, 255);
                    border: 1px solid rgb(85, 85, 255);
                }
            ''',
            'button': '''
                QPushButton {
                    background-color: #4A90E2;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 12px;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background-color: #357ABD;
                }
                QPushButton:pressed {
                    background-color: #2868A8;
                }
            ''',
            'list': '''
                QListWidget {
                    background-color: white;
                    border: 1px solid #E0E0E0;
                    border-radius: 4px;
                    padding: 4px;
                }
                QListWidget::item {
                    padding: 4px 8px;
                    border-radius: 3px;
                }
                QListWidget::item:hover {
                    background-color: #F0F8FF;
                }
                QListWidget::item:selected {
                    background-color: #4A90E2;
                    color: white;
                }
            ''',
            'line_edit': '''
                QLineEdit {
                    background-color: white;
                    border: 1px solid #E0E0E0;
                    border-radius: 4px;
                    padding: 4px 8px;
                    min-height: 20px;
                }
                QLineEdit:focus {
                    border: 1px solid #4A90E2;
                }
            '''
        }

    def _init_ui(self):
        container_frame = QFrame(self)
        container_frame.setStyleSheet(self.STYLES['container'])
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container_frame)

        layout = QVBoxLayout(container_frame)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 在线导入模式
        import_layout = QHBoxLayout()
        import_mode_label = QLabel("在线导入模式:")
        import_mode_label.setStyleSheet(self.STYLES['label'])
        
        self.import_mode_combo = QComboBox()
        self.import_mode_combo.addItem("GitHub导入模式", "github")
        self.import_mode_combo.addItem("智慧教育平台导入模式", "sei")
        self.import_mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.import_mode_combo.setStyleSheet(self.STYLES['combo'])
        self.import_mode_combo.installEventFilter(self.wheel_filter)
        
        import_layout.addWidget(import_mode_label)
        import_layout.addWidget(self.import_mode_combo)
        import_layout.addStretch()
        layout.addLayout(import_layout)
        
        # 标点提示开关
        hint_layout = QHBoxLayout()
        hint_label = QLabel("默认启用标点提示:")
        hint_label.setStyleSheet(self.STYLES['label'])
        
        self.punctuation_hint_checkbox = QCheckBox()
        self.punctuation_hint_checkbox.setStyleSheet(self.STYLES['checkbox'])
        self.punctuation_hint_checkbox.stateChanged.connect(self._on_punctuation_hint_changed)
        
        hint_layout.addWidget(hint_label)
        hint_layout.addWidget(self.punctuation_hint_checkbox)
        hint_layout.addStretch()
        layout.addLayout(hint_layout)
        
        # 默认停顿设置标题
        pause_title = QLabel("默认停顿设置:")
        pause_title.setStyleSheet(self.STYLES['label'] + "font-weight: bold; color: black;")
        layout.addWidget(pause_title)
        
        # 停顿符号按钮网格
        self.pause_buttons_layout = QGridLayout()
        self.pause_buttons_layout.setSpacing(8)
        self.pause_buttons = {}
        layout.addLayout(self.pause_buttons_layout)
        
        # 管理按钮
        manage_layout = QHBoxLayout()
        
        self.add_pause_button = QPushButton("添加分隔符")
        self.add_pause_button.setStyleSheet(self.STYLES['button'])
        self.add_pause_button.clicked.connect(self._add_pause_mark)
        manage_layout.addWidget(self.add_pause_button)
        
        self.edit_pause_button = QPushButton("编辑分隔符")
        self.edit_pause_button.setStyleSheet(self.STYLES['button'])
        self.edit_pause_button.clicked.connect(self._edit_pause_mark)
        manage_layout.addWidget(self.edit_pause_button)
        
        self.delete_pause_button = QPushButton("删除分隔符")
        self.delete_pause_button.setStyleSheet(self.STYLES['button'])
        self.delete_pause_button.clicked.connect(self._delete_pause_mark)
        manage_layout.addWidget(self.delete_pause_button)
        
        manage_layout.addStretch()
        layout.addLayout(manage_layout)
    
    def _on_mode_changed(self, index):
        mode_data = self.import_mode_combo.itemData(index)
        self.settings_manager.set_online_import_mode(mode_data == "sei")
    
    def _on_punctuation_hint_changed(self, state):
        """标点提示开关改变"""
        enabled = (state == Qt.Checked)
        self.settings_manager.Custom.set_value('default_punctuation_hint', str(enabled))
    
    def _on_pause_mark_toggled(self, name, enabled):
        """停顿符号按钮切换"""
        pause_marks = self._get_pause_marks()
        if name in pause_marks:
            pause_marks[name]['enabled'] = enabled
            self._save_pause_marks(pause_marks)
    
    def _add_pause_mark(self):
        """添加新的停顿符号"""
        from PyQt5.QtWidgets import QInputDialog, QMessageBox
        
        # 输入符号
        symbol, ok1 = QInputDialog.getText(self, "添加分隔符", "请输入分隔符（可以是多个字符）:")
        if not ok1 or not symbol:
            return
        
        # 输入名称
        name, ok2 = QInputDialog.getText(self, "添加分隔符", f"请输入'{symbol}'的名称:")
        if not ok2 or not name:
            return
        
        # 检查是否已存在
        pause_marks = self._get_pause_marks()
        if name in pause_marks:
            QMessageBox.warning(self, "警告", f"名称'{name}'已存在！")
            return
        
        # 添加到配置
        pause_marks[name] = {'symbol': symbol, 'enabled': True}
        self._save_pause_marks(pause_marks)
        self._refresh_pause_buttons()
    
    def _edit_pause_mark(self):
        """编辑选中的停顿符号"""
        from PyQt5.QtWidgets import QInputDialog, QMessageBox
        
        # 获取当前选中的按钮
        selected_name = None
        for name, btn in self.pause_buttons.items():
            if btn.hasFocus():
                selected_name = name
                break
        
        if not selected_name:
            QMessageBox.information(self, "提示", "请先点击要编辑的分隔符按钮")
            return
        
        pause_marks = self._get_pause_marks()
        if selected_name not in pause_marks:
            return
        
        old_symbol = pause_marks[selected_name]['symbol']
        
        # 输入新符号
        symbol, ok1 = QInputDialog.getText(self, "编辑分隔符", "请输入新的分隔符:", text=old_symbol)
        if not ok1 or not symbol:
            return
        
        # 输入新名称
        name, ok2 = QInputDialog.getText(self, "编辑分隔符", "请输入新的名称:", text=selected_name)
        if not ok2 or not name:
            return
        
        # 更新配置
        enabled = pause_marks[selected_name].get('enabled', True)
        del pause_marks[selected_name]
        pause_marks[name] = {'symbol': symbol, 'enabled': enabled}
        self._save_pause_marks(pause_marks)
        self._refresh_pause_buttons()
    
    def _delete_pause_mark(self):
        """删除选中的停顿符号"""
        from PyQt5.QtWidgets import QMessageBox
        
        # 获取当前选中的按钮
        selected_name = None
        for name, btn in self.pause_buttons.items():
            if btn.hasFocus():
                selected_name = name
                break
        
        if not selected_name:
            QMessageBox.information(self, "提示", "请先点击要删除的分隔符按钮")
            return
        
        # 确认删除
        reply = QMessageBox.question(self, "确认删除", 
                                     f"确定要删除分隔符'{selected_name}'吗？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            pause_marks = self._get_pause_marks()
            if selected_name in pause_marks:
                del pause_marks[selected_name]
                self._save_pause_marks(pause_marks)
                self._refresh_pause_buttons()
    
    def _get_pause_marks(self):
        """获取停顿符号配置"""
        import json
        marks_str = self.settings_manager.Custom.get_value('default_pause_marks', '')
        if marks_str:
            try:
                return json.loads(marks_str)
            except:
                pass
        
        # 返回默认配置
        return {
            '逗号': {'symbol': '，', 'enabled': True},
            '句号': {'symbol': '。', 'enabled': True},
            '叹号': {'symbol': '！', 'enabled': True},
            '问号': {'symbol': '？', 'enabled': True},
            '分号': {'symbol': '；', 'enabled': True},
            '冒号': {'symbol': '：', 'enabled': True},
            '省略号': {'symbol': '……', 'enabled': True},
            '左括号': {'symbol': '（', 'enabled': True},
            '右括号': {'symbol': '）', 'enabled': True},
            '斜杠': {'symbol': '/', 'enabled': True},
            '反斜杠': {'symbol': '\\', 'enabled': True},
            '波浪线': {'symbol': '~', 'enabled': True},
            '句点': {'symbol': '.', 'enabled': True},
            '英文逗号': {'symbol': ',', 'enabled': True},
            '英文叹号': {'symbol': '!', 'enabled': True},
            '英文问号': {'symbol': '?', 'enabled': True},
            '英文分号': {'symbol': ';', 'enabled': True},
            '英文冒号': {'symbol': ':', 'enabled': True},
            '英文左括号': {'symbol': '(', 'enabled': True},
            '英文右括号': {'symbol': ')', 'enabled': True},
            '换行': {'symbol': '\n', 'enabled': True},
        }
    
    def _save_pause_marks(self, marks):
        """保存停顿符号配置"""
        import json
        marks_str = json.dumps(marks, ensure_ascii=False)
        self.settings_manager.Custom.set_value('default_pause_marks', marks_str)
    
    def _refresh_pause_buttons(self):
        """刷新停顿符号按钮网格"""
        # 清除现有按钮
        for name, btn in self.pause_buttons.items():
            btn.deleteLater()
        self.pause_buttons.clear()
        
        # 获取停顿符号配置
        pause_marks = self._get_pause_marks()
        
        # 创建按钮
        row = 0
        col = 0
        max_cols = 6  # 每行最多6个按钮
        
        for name, config in sorted(pause_marks.items()):
            symbol = config['symbol']
            enabled = config.get('enabled', True)
            
            btn = PauseMarkButton(name, symbol, enabled, self)
            btn.toggled_signal.connect(self._on_pause_mark_toggled)
            
            self.pause_buttons_layout.addWidget(btn, row, col)
            self.pause_buttons[name] = btn
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
    def _load_settings(self):
        """加载设置"""
        # 加载在线导入模式
        is_sei_mode = self.settings_manager.get_online_import_mode()
        idx = self.import_mode_combo.findData("sei" if is_sei_mode else "github")
        if idx >= 0:
            self.import_mode_combo.setCurrentIndex(idx)
        
        # 加载标点提示开关
        hint_enabled = self.settings_manager.Custom.get_value('default_punctuation_hint', 'True')
        self.punctuation_hint_checkbox.setChecked(hint_enabled.lower() == 'true')
        
        # 加载停顿符号按钮
        self._refresh_pause_buttons()


class DraggableTabButton(QPushButton):
    def __init__(self, text, tab_name, parent=None):
        super().__init__(text, parent)
        self.tab_name = tab_name
        self.setMinimumSize(80, 35)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAcceptDrops(True)
        self.setStyleSheet("""
            QPushButton {
                background-color: white;
                border: 1px solid #A0A0A0;
                border-radius: 4px;
                color: #333;
            }
        """)
        self.drag_start_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return
        if not self.drag_start_pos:
            return
        if (event.pos() - self.drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.tab_name)
        drag.setMimeData(mime_data)
        
        pixmap = QPixmap(self.size())
        self.render(pixmap)
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.pos())
        
        self.hide()
        drop_action = drag.exec_(Qt.MoveAction)
        self.show()

class VerticalDragContainer(QWidget):
    order_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.v_layout = QVBoxLayout(self)
        self.v_layout.setSpacing(10)
        self.v_layout.setContentsMargins(0, 0, 0, 0)
        self.v_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.setAcceptDrops(True)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.drag_buttons = []
        
    def add_button(self, btn):
        self.drag_buttons.append(btn)
        self.v_layout.addWidget(btn)
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasText():
            tab_name = event.mimeData().text()
            source_btn = None
            for btn in self.drag_buttons:
                if btn.tab_name == tab_name:
                    source_btn = btn
                    break
            
            if source_btn:
                self.drag_buttons.remove(source_btn)
                
                drop_y = event.pos().y()
                target_index = 0
                current_y = 0
                
                for i, btn in enumerate(self.drag_buttons):
                    if drop_y > current_y + btn.height() / 2:
                        target_index = i + 1
                    current_y += btn.height() + self.v_layout.spacing()
                    
                self.drag_buttons.insert(target_index, source_btn)
                
                while self.v_layout.count():
                    item = self.v_layout.takeAt(0)
                    if item.widget():
                        item.widget().setParent(None)
                
                for btn in self.drag_buttons:
                    self.v_layout.addWidget(btn)
                    
                source_btn.show()
                self.order_changed.emit()
            event.acceptProposedAction()

class VisibilityButton(QPushButton):
    visibility_toggled = pyqtSignal(str, bool)
    
    def __init__(self, text, tab_name, is_visible, parent=None):
        super().__init__(text, parent)
        self.tab_name = tab_name
        self.is_visible = is_visible
        self.setMinimumSize(120, 60)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.update_style()
        self.clicked.connect(self.on_click)
        
    def on_click(self):
        if self.tab_name == 'settings':
            return
            
        self.is_visible = not self.is_visible
        self.update_style()
        self.visibility_toggled.emit(self.tab_name, self.is_visible)
        
    def update_style(self):
        if self.is_visible:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #55aaff;
                    color: white;
                    border: 1px solid #4499ee;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #66bbff;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #f5f5f5;
                    color: #999;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #e8e8e8;
                }
            """)


class PauseMarkButton(QPushButton):
    """停顿符号按钮"""
    toggled_signal = pyqtSignal(str, bool)  # 名称, 是否启用
    
    def __init__(self, name, symbol, is_enabled, parent=None):
        display_text = f"{name}\n{symbol}" if symbol != '\n' else f"{name}\n↵"
        super().__init__(display_text, parent)
        self.mark_name = name
        self.mark_symbol = symbol
        self.is_enabled = is_enabled
        self.setMinimumSize(80, 60)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.update_style()
        self.clicked.connect(self.on_click)
        
    def on_click(self):
        self.is_enabled = not self.is_enabled
        self.update_style()
        self.toggled_signal.emit(self.mark_name, self.is_enabled)
        
    def update_style(self):
        if self.is_enabled:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #55aaff;
                    color: white;
                    border: 1px solid #4499ee;
                    border-radius: 4px;
                    font-size: 24px;
                }
                QPushButton:hover {
                    background-color: #66bbff;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #f5f5f5;
                    color: #999;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    font-size: 24px;
                }
                QPushButton:hover {
                    background-color: #e8e8e8;
                }
            """)

class TabSettingsGroup(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings_manager = SettingsManager()
        self.available_tabs = {
            'welcome': '欢迎',
            'dictation': '听写',
            'settings': '设置',
            'personalization': '个性化',
            'misc': '杂项',
            'streaming': '流媒体',
            'plugins': '插件'
        }
        self.tab_order = []
        self.tab_visibility = []
        self.wheel_filter = WheelEventFilter()
        
        self.STYLES = {
            'container': '''
                background-color: rgb(255, 255, 255);
                border-radius: 5px;
            ''',
            'label': '''
                border: none;
                background: transparent;
            ''',
            'combo': '''
                QComboBox {
                    background-color: white;
                    border: 1px solid #E0E0E0;
                    border-radius: 4px;
                    padding: 2px 8px;
                    min-height: 28px;
                }
                QComboBox:focus {
                    border: 1px solid #4A90E2;
                }
                QComboBox::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: center right;
                    width: 24px;
                    border: none;
                    border-left: 1px solid #E0E0E0;
                    border-top-right-radius: 4px;
                    border-bottom-right-radius: 4px;
                }
                QComboBox::drop-down:hover {
                    background-color: #4A90E2;
                    border-left: 1px solid #4A90E2;
                }
                QComboBox::down-arrow {
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 6px solid #666;
                    width: 0px;
                    height: 0px;
                }
                QComboBox::drop-down:hover QComboBox::down-arrow {
                    border-top-color: white;
                }
                QComboBox QAbstractItemView {
                    background-color: white;
                    border: 1px solid #E0E0E0;
                    border-radius: 4px;
                    padding: 2px;
                    outline: none;
                    selection-background-color: #4A90E2;
                    selection-color: white;
                }
            '''
        }
        
        self._init_ui()
        self._load_settings()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(20)

        # --- Left Panel ---
        left_container = QFrame()
        left_container.setStyleSheet(self.STYLES['container'])
        left_container.setMinimumWidth(150)
        left_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(20, 30, 20, 30)
        left_layout.setSpacing(10)
        left_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        sort_title = QLabel("选项卡排序:")
        sort_title.setStyleSheet("font-weight: bold; border: none; background: transparent; color: black;")
        sort_title.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(sort_title)

        sort_subtitle = QLabel("上下拖动以排序")
        sort_subtitle.setStyleSheet("color: #666; border: none; background: transparent;")
        sort_subtitle.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(sort_subtitle)
        
        left_layout.addSpacing(15)

        self.drag_container_frame = QFrame()
        self.drag_container_frame.setStyleSheet("""
            QFrame {
                background-color: #F5F5F5;
                border-radius: 6px;
            }
        """)
        self.drag_container_frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        drag_frame_layout = QVBoxLayout(self.drag_container_frame)
        drag_frame_layout.setContentsMargins(10, 15, 10, 15)
        
        self.drag_container = VerticalDragContainer()
        self.drag_container.order_changed.connect(self._on_order_changed)
        self.drag_container.setStyleSheet("border: none;")
        drag_frame_layout.addWidget(self.drag_container)
        
        left_layout.addWidget(self.drag_container_frame)
        left_layout.addStretch()

        # --- Right Panel ---
        right_container = QFrame()
        right_container.setStyleSheet(self.STYLES['container'])
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(40, 50, 40, 40)
        right_layout.setSpacing(50)
        right_layout.setAlignment(Qt.AlignTop)

        # Row 1: Initial Tab
        initial_tab_layout = QHBoxLayout()
        initial_tab_label = QLabel("起始选项卡:")
        initial_tab_label.setStyleSheet("border: none; background: transparent; color: black;")
        initial_tab_label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        
        self.initial_tab_combo = QComboBox()
        self.initial_tab_combo.setStyleSheet(self.STYLES['combo'])
        self.initial_tab_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.initial_tab_combo.setMinimumWidth(200)
        self.initial_tab_combo.currentIndexChanged.connect(self._save_settings)
        self.initial_tab_combo.installEventFilter(self.wheel_filter)
        
        initial_tab_layout.addWidget(initial_tab_label)
        initial_tab_layout.addWidget(self.initial_tab_combo)
        initial_tab_layout.addStretch()
        
        right_layout.addLayout(initial_tab_layout)

        # Row 2: Visibility
        visibility_layout = QHBoxLayout()
        visibility_layout.setAlignment(Qt.AlignTop)
        
        vis_label_layout = QVBoxLayout()
        vis_label_layout.setAlignment(Qt.AlignTop)
        vis_label_layout.setSpacing(5)
        vis_title = QLabel("修改选项卡可见性:")
        vis_title.setStyleSheet("border: none; background: transparent; color: black;")
        vis_subtitle = QLabel("单击以修改")
        vis_subtitle.setStyleSheet("color: #666; border: none; background: transparent;")
        
        vis_label_container = QWidget()
        vis_label_container.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        v_lbl_layout = QVBoxLayout(vis_label_container)
        v_lbl_layout.setContentsMargins(0, 0, 0, 0)
        v_lbl_layout.addWidget(vis_title)
        v_lbl_layout.addWidget(vis_subtitle)
        v_lbl_layout.addStretch()
        
        self.visibility_grid = QGridLayout()
        self.visibility_grid.setVerticalSpacing(5)
        self.visibility_grid.setHorizontalSpacing(5)
        
        visibility_layout.addWidget(vis_label_container)
        visibility_layout.addLayout(self.visibility_grid)
        visibility_layout.addStretch()

        right_layout.addLayout(visibility_layout)
        right_layout.addStretch()

        main_layout.addWidget(left_container)
        main_layout.addWidget(right_container, 1)

    @property
    def _tab_manager(self):
        try:
            settings_page = self.parent()
            if settings_page is None:
                return None
            main_window = getattr(settings_page, 'parent_window', None)
            if main_window is None:
                return None
            return getattr(main_window, 'tab_manager', None)
        except Exception:
            return None

    def _load_settings(self):
        tab_manager = self._tab_manager
        if tab_manager:
            for config in tab_manager.tab_configs:
                if config.name not in self.available_tabs:
                    self.available_tabs[config.name] = config.display_name

        defaults = "welcome,dictation,settings,personalization,misc,streaming,plugins"
        order_str = self.settings_manager.get_Custom_value("tab_order", defaults)
        self.tab_order = [t.strip() for t in order_str.split(',') if t.strip() and t.strip() in self.available_tabs]
        for name in self.available_tabs:
            if name not in self.tab_order:
                self.tab_order.append(name)

        visibility_str = self.settings_manager.get_Custom_value("tab_visibility", defaults)
        self.tab_visibility = [t.strip() for t in visibility_str.split(',') if t.strip() and t.strip() in self.available_tabs]

        if 'settings' not in self.tab_visibility:
            self.tab_visibility.append('settings')
            self._save_settings()

        self._refresh_ui()

    def _refresh_ui(self):
        while self.drag_container.v_layout.count():
            item = self.drag_container.v_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self.drag_container.drag_buttons.clear()

        for name in self.tab_order:
            display_name = self.available_tabs.get(name, name)
            btn = DraggableTabButton(display_name, name)
            self.drag_container.add_button(btn)

        while self.visibility_grid.count():
            item = self.visibility_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        builtin_order = ["welcome", "dictation", "settings", "personalization", "misc", "streaming", "plugins"]
        extra_tabs = [name for name in self.available_tabs if name not in builtin_order]
        fixed_order = builtin_order + extra_tabs
        row, col = 0, 0
        for name in fixed_order:
            if name not in self.available_tabs: continue
            display_name = self.available_tabs.get(name, name)
            is_vis = (name in self.tab_visibility)
            btn = VisibilityButton(display_name, name, is_vis)
            btn.visibility_toggled.connect(self._on_visibility_changed)
            self.visibility_grid.addWidget(btn, row, col)
            col += 1
            if col > 2:
                col = 0
                row += 1

        self._update_initial_tab_combo()

    def _update_initial_tab_combo(self):
        current_selection = self.settings_manager.get_Custom_value("initial_tab", "welcome")
        self.initial_tab_combo.blockSignals(True)
        self.initial_tab_combo.clear()
        
        for name in self.tab_order:
            if name in self.tab_visibility:
                self.initial_tab_combo.addItem(self.available_tabs[name], name)
        
        idx = self.initial_tab_combo.findData(current_selection)
        if idx >= 0:
            self.initial_tab_combo.setCurrentIndex(idx)
        else:
            if self.initial_tab_combo.count() > 0:
                self.initial_tab_combo.setCurrentIndex(0)
                self.initial_tab_combo.blockSignals(False)
                self._save_settings()
                self.initial_tab_combo.blockSignals(True)
            
        self.initial_tab_combo.blockSignals(False)

    def _on_order_changed(self):
        new_order = [btn.tab_name for btn in self.drag_container.drag_buttons]
        self.tab_order = new_order
        self._update_initial_tab_combo()
        self._save_settings()

    def _on_visibility_changed(self, name, is_visible):
        if is_visible:
            if name not in self.tab_visibility:
                self.tab_visibility.append(name)
        else:
            if name in self.tab_visibility:
                self.tab_visibility.remove(name)
        self._update_initial_tab_combo()
        self._save_settings()

    def _save_settings(self):
        self.settings_manager.set_Custom_value("tab_order", ",".join(self.tab_order))
        self.settings_manager.set_Custom_value("tab_visibility", ",".join(self.tab_visibility))
        if self.initial_tab_combo.currentData():
            self.settings_manager.set_Custom_value("initial_tab", self.initial_tab_combo.currentData())


class SettingsPage(QWidget):
    """主设置页面"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.settings_manager = SettingsManager()
        self._init_ui()
        self._update_fonts()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # --- Top Navigation ---
        self.top_nav_container = StyledContainer()
        top_nav_layout = QHBoxLayout(self.top_nav_container)
        top_nav_layout.setContentsMargins(20, 20, 20, 20)
        top_nav_layout.setSpacing(20)
        
        self.btn_ai = SmoothButton("AI设置", "tab_level1")
        self.btn_download = SmoothButton("下载设置", "tab_level1")
        self.btn_dictation = SmoothButton("听写设置", "tab_level1")
        self.btn_tab = SmoothButton("选项卡设置", "tab_level1")
        
        self.btn_ai.setChecked(True)
        
        self.level1_group = QButtonGroup(self)
        self.level1_group.addButton(self.btn_ai, 0)
        self.level1_group.addButton(self.btn_download, 1)
        self.level1_group.addButton(self.btn_dictation, 2)
        self.level1_group.addButton(self.btn_tab, 3)
        self.level1_group.buttonClicked[int].connect(self._on_level1_changed)
        
        top_nav_layout.addStretch()
        top_nav_layout.addWidget(self.btn_ai)
        top_nav_layout.addWidget(self.btn_download)
        top_nav_layout.addWidget(self.btn_dictation)
        top_nav_layout.addWidget(self.btn_tab)
        top_nav_layout.addStretch()
        
        main_layout.addWidget(self.top_nav_container)
        
        # --- Stacked Content ---
        self.stacked_widget = QStackedWidget()
        
        from ai_settings_ui import AiSettingsTab
        self.ai_settings_tab = AiSettingsTab(self)
        
        self.download_scroll = QScrollArea()
        self.download_scroll.setWidgetResizable(True)
        self.download_scroll.setFrameShape(QFrame.NoFrame)
        self.download_group = DownloadSettingsGroup(self)
        self.download_scroll.setWidget(self.download_group)
        
        self.import_scroll = QScrollArea()
        self.import_scroll.setWidgetResizable(True)
        self.import_scroll.setFrameShape(QFrame.NoFrame)
        self.dictation_group = DictationSettingsGroup(self)
        self.import_scroll.setWidget(self.dictation_group)
        
        self.tab_scroll = QScrollArea()
        self.tab_scroll.setWidgetResizable(True)
        self.tab_scroll.setFrameShape(QFrame.NoFrame)
        self.tab_settings_group = TabSettingsGroup(self)
        self.tab_scroll.setWidget(self.tab_settings_group)
        
        self.stacked_widget.addWidget(self.ai_settings_tab)
        self.stacked_widget.addWidget(self.download_scroll)
        self.stacked_widget.addWidget(self.import_scroll)
        self.stacked_widget.addWidget(self.tab_scroll)
        
        main_layout.addWidget(self.stacked_widget)
        
        # 添加渐隐渐显动画
        self.stacked_opacity_effect = QGraphicsOpacityEffect(self.stacked_widget)
        self.stacked_widget.setGraphicsEffect(self.stacked_opacity_effect)
        self.stacked_opacity_effect.setEnabled(False)
        self.fade_animation = QPropertyAnimation(self.stacked_opacity_effect, b"opacity")
        self.fade_animation.setDuration(200) # 动画时长
        self.fade_animation.setEasingCurve(QEasingCurve.InOutQuad) # 平滑过渡
        self.fade_animation.finished.connect(self._on_fade_animation_finished)
        self.target_stacked_index = 0 # 记录目标索引
        
    def resizeEvent(self, event):
        self._update_fonts()
        super().resizeEvent(event)
        
    def _on_level1_changed(self, index):
        if self.stacked_widget.currentIndex() == index:
            return
        self.target_stacked_index = index
        self.stacked_opacity_effect.setEnabled(True)
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.start()

        # 一级选项卡切换时，使用带有动画的方法，使其与整体渐变效果同步进行
        if index != 0:
            self.ai_settings_tab.hide_right_panel()
        else:
            self.ai_settings_tab.show_right_panel_if_needed()

    def _on_fade_animation_finished(self):
        if self.stacked_opacity_effect.opacity() == 0.0:
            self.stacked_widget.setCurrentIndex(self.target_stacked_index)
            self.fade_animation.setStartValue(0.0)
            self.fade_animation.setEndValue(1.0)
            self.fade_animation.start()
        else:
            self.stacked_opacity_effect.setEnabled(False)

    def update_fonts(self, font):
        self._update_fonts()
        
    def _update_fonts(self):
        if not self.parent_window: return
        
        current_width = self.parent_window.width()
        current_height = self.parent_window.height()
        ratio = (current_width / 1080 + current_height / 720) / 2
        
        base_font_size = 22 + (42 - 22) * (ratio - 1)
        base_font_size = max(22, min(42, int(base_font_size)))
        
        global_font_name = self.settings_manager.Custom.get_value("global_font", "微软雅黑")
        base_font = QFont(global_font_name, int(base_font_size * 0.5))
        
        # 递归应用字体，不使用样式表中的font属性
        def set_font_recursive(widget):
            widget.setFont(base_font)
            for child in widget.findChildren(QWidget):
                child.setFont(base_font)
                
        set_font_recursive(self)
        
        if hasattr(self, "ai_settings_tab") and hasattr(self.ai_settings_tab, "update_ui_scale"):
            self.ai_settings_tab.update_ui_scale(self.parent_window)

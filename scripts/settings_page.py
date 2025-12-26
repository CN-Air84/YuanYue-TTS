# coding=utf-8
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QLineEdit, QPushButton, QGroupBox, QFormLayout,
    QSpinBox, QScrollArea, QCheckBox, QSlider, QFileDialog
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QEvent
from PyQt5.QtGui import QFont

from misc_func import SettingsManager, CustomConfig
from shared_memory_manager import get_shared_memory_manager


class SettingsCustomConfig:
    """设置页面配置常量"""
    
    # 间距系统配置
    SPACING_SYSTEM = {
        'xs': 4,    # 组件内间距
        'sm': 8,    # 组件间小间距
        'md': 16,   # 组件间中间距
        'lg': 24,   # 分组间间距
        'xl': 32    # 大区块间距
    }
    
    # 卡片样式模板
    CARD_STYLE = """
        QGroupBox {
            background-color: #ffffff;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 16px;
            margin-top: 8px;
            margin-bottom: 8px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 16px;
            padding: 4px 12px;
            background-color: #ffffff;
            color: #333333;
            font-weight: bold;
            border-radius: 6px;
            border: 1px solid #e0e0e0;
        }
        QLabel {
            background-color: transparent;
        }
    """
    
    # 统一的控件样式系统
    UNIFIED_STYLES = {
        'input': """
            QLineEdit, QSpinBox, QDoubleSpinBox {
                border: 2px solid #d0d0d0;
                border-radius: 6px;
                padding: 8px 12px;
                background-color: #ffffff;
                color: #333333;
                min-height: 32px;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border-color: #4A90E2;
                outline: none;
            }
            QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover {
                border-color: #808080;
            }
            QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
                background-color: #f5f5f5;
                color: #999999;
                border-color: #e0e0e0;
            }
            QSpinBox::up-button, QDoubleSpinBox::up-button {
                width: 0px;
                height: 0px;
            }
            QSpinBox::down-button, QDoubleSpinBox::down-button {
                width: 0px;
                height: 0px;
            }
        """,
        'button': """
            QPushButton {
                border: 2px solid #4A90E2;
                border-radius: 6px;
                padding: 8px 16px;
                background-color: #4A90E2;
                color: #ffffff;
                font-weight: 500;
                min-height: 32px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #357ABD;
                border-color: #357ABD;
            }
            QPushButton:pressed {
                background-color: #2E5A8E;
                border-color: #2E5A8E;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                border-color: #cccccc;
                color: #999999;
            }
        """,
        'combo': """
            QComboBox {
                border: 2px solid #d0d0d0;
                border-radius: 6px;
                padding: 8px 12px;
                background-color: #ffffff;
                color: #333333;
                min-height: 32px;
            }
            QComboBox:hover {
                border-color: #808080;
            }
            QComboBox:focus {
                border-color: #4A90E2;
                outline: none;
            }
            QComboBox::drop-down {
                border-left: 1px solid #d0d0d0;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #333333;
                width: 0px;
                height: 0px;
            }
        """,
        'checkbox': """
            QCheckBox {
                background-color: #ffffff;
                color: #333333;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #d0d0d0;
                border-radius: 4px;
                background-color: #ffffff;
            }
            QCheckBox::indicator:checked {
                background-color: #4A90E2;
                border-color: #4A90E2;
            }
            QCheckBox::indicator:hover {
                border-color: #808080;
            }
        """,
        'slider': """
            QSlider::groove:horizontal {
                border: 2px solid #e0e0e0;
                height: 12px;
                background: #FFFFFF;
                border-radius: 6px;
            }
            QSlider::sub-page:horizontal {
                background: #44AADD;
                border-radius: 6px;
            }
            QSlider::add-page:horizontal {
                background: #FFFFFF;
                border-radius: 6px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                border: 2px solid #44AADD;
                width: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #F5F5F5;
            }
            QSlider::handle:horizontal:pressed {
                background: #E0E0E0;
            }
        """,
        'slider_orange': """
            QSlider::groove:horizontal {
                border: 2px solid #e0e0e0;
                height: 12px;
                background: #FFFFFF;
                border-radius: 6px;
            }
            QSlider::sub-page:horizontal {
                background: #FFA500;
                border-radius: 6px;
            }
            QSlider::add-page:horizontal {
                background: #FFFFFF;
                border-radius: 6px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                border: 2px solid #FFA500;
                width: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #F5F5F5;
            }
            QSlider::handle:horizontal:pressed {
                background: #E0E0E0;
            }
        """,
        'slider_button': """
            QPushButton {
                background-color: #ffffff;
                color: #333333;
                border: 2px solid #d0d0d0;
                border-radius: 6px;
                font-weight: bold;
                min-width: 32px;
                min-height: 32px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
                border-color: #808080;
            }
            QPushButton:pressed {
                background-color: #e0e0e0;
            }
        """
    }
    
    @staticmethod
    def get_dynamic_card_style(title_font_size=14, font_family="微软雅黑"):
        """获取动态卡片样式 - 根据字体大小调整标题样式"""
        return f"""
            QGroupBox {{
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 16px;
                margin-top: 8px;
                margin-bottom: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 16px;
                padding: 4px 12px;
                background-color: #ffffff;
                color: #333333;
                font-weight: bold;
                font-size: {title_font_size}px;
                font-family: "{font_family}";
                border-radius: 6px;
                border: 1px solid #e0e0e0;
            }}
            QLabel {{
                background-color: transparent;
            }}
        """


class WheelEventFilter(QObject):
    """鼠标滚轮事件过滤器 - 禁止通过滚轮改变数值"""
    
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel:
            return True
        return False


class ApiKeyGroup(QGroupBox):
    """API密钥设置组 - 卡片式设计"""
    
    def __init__(self, parent=None):
        super().__init__("API密钥设置", parent)
        self.settings_manager = SettingsManager()
        self.wheel_filter = WheelEventFilter()
        self._init_ui()
        self._load_settings()
        self._apply_card_style()
    
    def _apply_card_style(self):
        """应用卡片样式"""
        title_font_size = 14
        if self.parent() and hasattr(self.parent(), 'parent_window') and self.parent().parent_window:
            current_width = self.parent().parent_window.width()
            current_height = self.parent().parent_window.height()
            base_width = 1024
            base_height = 768
            width_ratio = current_width / base_width
            height_ratio = current_height / base_height
            ratio = (width_ratio + height_ratio) / 2
            title_font_size = max(12, min(18, int(14 * ratio)))
        
        global_font_name = self.settings_manager.Custom.get_value("global_font", "微软雅黑")
        self.setStyleSheet(SettingsCustomConfig.get_dynamic_card_style(title_font_size, global_font_name))
        self.setContentsMargins(SettingsCustomConfig.SPACING_SYSTEM['lg'], 
                              SettingsCustomConfig.SPACING_SYSTEM['lg'],
                              SettingsCustomConfig.SPACING_SYSTEM['lg'], 
                              SettingsCustomConfig.SPACING_SYSTEM['lg'])
    
    def _init_ui(self):
        """初始化UI"""
        layout = QFormLayout()
        layout.setVerticalSpacing(SettingsCustomConfig.SPACING_SYSTEM['md'])
        
        self.chatglm_key_input = QLineEdit()
        self.chatglm_key_input.setPlaceholderText("请输入ChatGLM API密钥")
        self.chatglm_key_input.textChanged.connect(
            lambda text: self.settings_manager.set_api_key("api_key_ChatGLM", text)
        )
        self.chatglm_key_input.setStyleSheet(SettingsCustomConfig.UNIFIED_STYLES['input'])
        self.chatglm_key_input.installEventFilter(self.wheel_filter)
        
        layout.addRow("ChatGLM Key:", self.chatglm_key_input)
        self.setLayout(layout)
    
    def _load_settings(self):
        """加载设置"""
        api_key = self.settings_manager.get_api_key("api_key_ChatGLM")
        self.chatglm_key_input.setText(api_key)


class GenerationSettingsGroup(QGroupBox):
    """生成设置组 - 卡片式设计"""
    
    def __init__(self, parent=None):
        super().__init__("生成设置", parent)
        self.settings_manager = SettingsManager()
        self.wheel_filter = WheelEventFilter()
        self._init_ui()
        self._load_settings()
        self._apply_card_style()
    
    def _apply_card_style(self):
        """应用卡片样式"""
        title_font_size = 14
        if self.parent() and hasattr(self.parent(), 'parent_window') and self.parent().parent_window:
            current_width = self.parent().parent_window.width()
            current_height = self.parent().parent_window.height()
            base_width = 1024
            base_height = 768
            width_ratio = current_width / base_width
            height_ratio = current_height / base_height
            ratio = (width_ratio + height_ratio) / 2
            title_font_size = max(12, min(18, int(14 * ratio)))
        
        global_font_name = self.settings_manager.Custom.get_value("global_font", "微软雅黑")
        self.setStyleSheet(SettingsCustomConfig.get_dynamic_card_style(title_font_size, global_font_name))
        self.setContentsMargins(SettingsCustomConfig.SPACING_SYSTEM['lg'], 
                              SettingsCustomConfig.SPACING_SYSTEM['lg'],
                              SettingsCustomConfig.SPACING_SYSTEM['lg'], 
                              SettingsCustomConfig.SPACING_SYSTEM['lg'])
    
    def _init_ui(self):
        """初始化UI"""
        layout = QFormLayout()
        layout.setVerticalSpacing(SettingsCustomConfig.SPACING_SYSTEM['md'])
        
        # 默认音源
        self.voice_source_combo = QComboBox()
        self.voice_source_combo.addItems(['EdgeAPI'])
        self.voice_source_combo.currentTextChanged.connect(
            lambda text: self.settings_manager.set_api_key('default_voice_1', text)
        )
        self.voice_source_combo.setStyleSheet(SettingsCustomConfig.UNIFIED_STYLES['combo'])
        self.voice_source_combo.installEventFilter(self.wheel_filter)
        layout.addRow("默认音源:", self.voice_source_combo)
        
        # 默认音色
        self.voice_combo = QComboBox()
        self.voice_combo.addItems(['中文'])
        self.voice_combo.currentTextChanged.connect(
            lambda text: self.settings_manager.set_api_key('default_voice_2', text)
        )
        self.voice_combo.setStyleSheet(SettingsCustomConfig.UNIFIED_STYLES['combo'])
        self.voice_combo.installEventFilter(self.wheel_filter)
        layout.addRow("默认音色:", self.voice_combo)
        
        # 默认语速
        speed_layout = QHBoxLayout()
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(-25, 25)
        self.speed_slider.setValue(0)
        self.speed_slider.valueChanged.connect(self._on_speed_changed)
        self.speed_slider.setStyleSheet(SettingsCustomConfig.UNIFIED_STYLES['slider'])
        
        self.speed_minus_btn = QPushButton('-')
        self.speed_minus_btn.setFixedSize(32, 32)
        self.speed_minus_btn.clicked.connect(lambda: self._adjust_speed(-1))
        self.speed_minus_btn.setStyleSheet(SettingsCustomConfig.UNIFIED_STYLES['slider_button'])
        
        self.speed_plus_btn = QPushButton('+')
        self.speed_plus_btn.setFixedSize(32, 32)
        self.speed_plus_btn.clicked.connect(lambda: self._adjust_speed(1))
        self.speed_plus_btn.setStyleSheet(SettingsCustomConfig.UNIFIED_STYLES['slider_button'])
        
        self.speed_display = QLabel("0")
        self.speed_display.setAlignment(Qt.AlignCenter)
        self.speed_display.setMinimumWidth(40)
        
        speed_layout.addWidget(self.speed_display)
        speed_layout.addWidget(self.speed_minus_btn)
        speed_layout.addWidget(self.speed_slider)
        speed_layout.addWidget(self.speed_plus_btn)
        layout.addRow("默认语速:", speed_layout)
        
        # 音频拉伸
        self.stretch_enable_checkbox = QCheckBox("启用音频拉伸")
        self.stretch_enable_checkbox.stateChanged.connect(self._on_stretch_enable_changed)
        self.stretch_enable_checkbox.setStyleSheet(SettingsCustomConfig.UNIFIED_STYLES['checkbox'])
        layout.addRow(self.stretch_enable_checkbox)
        
        stretch_layout = QHBoxLayout()
        self.stretch_slider = QSlider(Qt.Horizontal)
        self.stretch_slider.setRange(5, 200)
        self.stretch_slider.setValue(100)
        self.stretch_slider.valueChanged.connect(self._on_stretch_factor_changed)
        self.stretch_slider.setStyleSheet(SettingsCustomConfig.UNIFIED_STYLES['slider_orange'])
        
        self.stretch_minus_btn = QPushButton('-')
        self.stretch_minus_btn.setFixedSize(32, 32)
        self.stretch_minus_btn.clicked.connect(lambda: self._adjust_stretch(-1))
        self.stretch_minus_btn.setStyleSheet(SettingsCustomConfig.UNIFIED_STYLES['slider_button'])
        
        self.stretch_plus_btn = QPushButton('+')
        self.stretch_plus_btn.setFixedSize(32, 32)
        self.stretch_plus_btn.clicked.connect(lambda: self._adjust_stretch(1))
        self.stretch_plus_btn.setStyleSheet(SettingsCustomConfig.UNIFIED_STYLES['slider_button'])
        
        self.stretch_display = QLabel("1.00")
        self.stretch_display.setAlignment(Qt.AlignCenter)
        self.stretch_display.setMinimumWidth(40)
        
        self.stretch_info = QLabel("(变速不变调，范围: 0.05倍 - 2.00倍)")
        self.stretch_info.setStyleSheet("color: #666666; font-size: 12px;")
        
        stretch_layout.addWidget(self.stretch_display)
        stretch_layout.addWidget(self.stretch_minus_btn)
        stretch_layout.addWidget(self.stretch_slider)
        stretch_layout.addWidget(self.stretch_plus_btn)
        layout.addRow("音频拉伸系数:", stretch_layout)
        layout.addRow("", self.stretch_info)
        
        # 保存路径
        path_layout = QHBoxLayout()
        self.save_path_display = QLineEdit()
        self.save_path_display.setReadOnly(True)
        self.save_path_display.setStyleSheet(SettingsCustomConfig.UNIFIED_STYLES['input'])
        
        self.save_path_button = QPushButton("选择路径")
        self.save_path_button.clicked.connect(self._select_save_path)
        self.save_path_button.setStyleSheet(SettingsCustomConfig.UNIFIED_STYLES['button'])
        
        path_layout.addWidget(self.save_path_display)
        path_layout.addWidget(self.save_path_button)
        layout.addRow("保存路径:", path_layout)
        
        self.setLayout(layout)
        
        self._set_stretch_controls_enabled(False)
    
    def _load_settings(self):
        """加载设置"""
        voice1 = self.settings_manager.get_default_voice(1)
        voice2 = self.settings_manager.get_default_voice(2)
        
        index1 = self.voice_source_combo.findText(voice1)
        if index1 >= 0:
            self.voice_source_combo.setCurrentIndex(index1)
        
        index2 = self.voice_combo.findText(voice2)
        if index2 >= 0:
            self.voice_combo.setCurrentIndex(index2)
        
        speed = self.settings_manager.get_default_speed()
        self.speed_slider.setValue(speed)
        self.speed_display.setText(str(speed))
        
        stretch_factor = self.settings_manager.get_stretch_factor()
        self.stretch_slider.setValue(int(stretch_factor * 100))
        self.stretch_display.setText(f"{stretch_factor:.2f}")
        
        stretch_enabled = self.settings_manager.get_stretch_enabled()
        self.stretch_enable_checkbox.setChecked(stretch_enabled)
        self._set_stretch_controls_enabled(stretch_enabled)
        
        save_path = self.settings_manager.get_default_save_path()
        self.save_path_display.setText(save_path)
    
    def _on_speed_changed(self, value):
        """语速改变时的处理"""
        self.speed_display.setText(str(value))
        self.settings_manager.set_default_speed(value)
    
    def _adjust_speed(self, delta):
        """调整语速"""
        current_value = self.speed_slider.value()
        new_value = current_value + delta
        if self.speed_slider.minimum() <= new_value <= self.speed_slider.maximum():
            self.speed_slider.setValue(new_value)
    
    def _on_stretch_enable_changed(self, state):
        """音频拉伸开关改变时的处理"""
        enabled = state == Qt.Checked
        self.settings_manager.set_stretch_enabled(enabled)
        self._set_stretch_controls_enabled(enabled)
    
    def _on_stretch_factor_changed(self, value):
        """音频拉伸系数改变时的处理"""
        factor = value / 100.0
        self.stretch_display.setText(f"{factor:.2f}")
        self.settings_manager.set_stretch_factor(factor)
    
    def _adjust_stretch(self, delta):
        """调整音频拉伸系数"""
        current_value = self.stretch_slider.value()
        new_value = current_value + delta
        if self.stretch_slider.minimum() <= new_value <= self.stretch_slider.maximum():
            self.stretch_slider.setValue(new_value)
    
    def _set_stretch_controls_enabled(self, enabled):
        """设置音频拉伸控件是否启用"""
        self.stretch_slider.setEnabled(enabled)
        self.stretch_minus_btn.setEnabled(enabled)
        self.stretch_plus_btn.setEnabled(enabled)
        self.stretch_display.setEnabled(enabled)
    
    def _select_save_path(self):
        """选择保存路径"""
        directory = QFileDialog.getExistingDirectory(self, "选择默认保存路径")
        if directory:
            self.save_path_display.setText(directory)
            self.settings_manager.set_default_save_path(directory)
    
    def update_fonts(self, font):
        """更新字体"""
        self.voice_source_combo.setFont(font)
        self.voice_combo.setFont(font)
        self.speed_minus_btn.setFont(font)
        self.speed_plus_btn.setFont(font)
        self.speed_display.setFont(font)
        self.stretch_enable_checkbox.setFont(font)
        self.stretch_minus_btn.setFont(font)
        self.stretch_plus_btn.setFont(font)
        self.stretch_display.setFont(font)
        self.stretch_info.setFont(font)
        self.save_path_display.setFont(font)
        self.save_path_button.setFont(font)


class DownloadSettingsGroup(QGroupBox):
    """下载设置组 - 卡片式设计"""
    
    def __init__(self, parent=None):
        super().__init__("下载设置", parent)
        self.settings_manager = SettingsManager()
        self.wheel_filter = WheelEventFilter()
        self._init_ui()
        self._load_settings()
        self._apply_card_style()
    
    def _apply_card_style(self):
        """应用卡片样式"""
        title_font_size = 14
        if self.parent() and hasattr(self.parent(), 'parent_window') and self.parent().parent_window:
            current_width = self.parent().parent_window.width()
            current_height = self.parent().parent_window.height()
            base_width = 1024
            base_height = 768
            width_ratio = current_width / base_width
            height_ratio = current_height / base_height
            ratio = (width_ratio + height_ratio) / 2
            title_font_size = max(12, min(18, int(14 * ratio)))
        
        global_font_name = self.settings_manager.Custom.get_value("global_font", "微软雅黑")
        self.setStyleSheet(SettingsCustomConfig.get_dynamic_card_style(title_font_size, global_font_name))
        self.setContentsMargins(SettingsCustomConfig.SPACING_SYSTEM['lg'], 
                              SettingsCustomConfig.SPACING_SYSTEM['lg'],
                              SettingsCustomConfig.SPACING_SYSTEM['lg'], 
                              SettingsCustomConfig.SPACING_SYSTEM['lg'])
    
    def _init_ui(self):
        """初始化UI"""
        layout = QFormLayout()
        layout.setVerticalSpacing(SettingsCustomConfig.SPACING_SYSTEM['md'])
        
        # Github下载加速源
        self.github_mirror_combo = QComboBox()
        self.github_mirror_combo.addItems([
        "直接从github服务器获取（海外首选）",
        "ghfast（中国大陆首选）",
        "ghproxy 主站（CloudFlare CDN，大陆备用）",
        "ghproxy HK（港澳台首选）",
        "ghproxy edgeone（备用）"
        ])
        self.github_mirror_combo.currentTextChanged.connect(
            lambda text: self.settings_manager.Custom.set_value("github_mirror", text)
        )
        self.github_mirror_combo.setStyleSheet(SettingsCustomConfig.UNIFIED_STYLES['combo'])
        self.github_mirror_combo.installEventFilter(self.wheel_filter)
        layout.addRow("Github下载加速源:", self.github_mirror_combo)
        
        # 下载线程数
        self.download_threads_spin = QSpinBox()
        self.download_threads_spin.setRange(1, 16)
        self.download_threads_spin.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("download_threads", str(value))
        )
        self.download_threads_spin.setStyleSheet(SettingsCustomConfig.UNIFIED_STYLES['input'])
        self.download_threads_spin.installEventFilter(self.wheel_filter)
        layout.addRow("下载线程数:", self.download_threads_spin)
        
        self.setLayout(layout)
    
    def _load_settings(self):
        """加载设置"""
        github_mirror = self.settings_manager.Custom.get_value("github_mirror", "https://ghproxy.com")
        index = self.github_mirror_combo.findText(github_mirror)
        if index >= 0:
            self.github_mirror_combo.setCurrentIndex(index)
        
        download_threads = self.settings_manager.Custom.get_value("download_threads", "4")
        self.download_threads_spin.setValue(int(download_threads))


class SettingsPage(QWidget):
    """设置页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.settings_manager = SettingsManager()
        self.wheel_filter = WheelEventFilter()
        
        # 字体大小设置
        self.min_font_size = 22
        self.max_font_size = 42
        self.default_width = 1080
        self.default_height = 720
        
        self._init_ui()
        self._update_fonts()
    
    def resizeEvent(self, event):
        """窗口大小改变时更新字体和样式"""
        self._update_fonts()
        super().resizeEvent(event)
    
    def _init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 创建滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background-color: #f0f0f0;
                width: 12px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #c0c0c0;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #a0a0a0;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
        """)
        
        # 创建内容部件
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setSpacing(15)
        
        # API密钥设置
        self.api_key_group = ApiKeyGroup(self)
        self.content_layout.addWidget(self.api_key_group)
        
        # 生成设置
        self.generation_group = GenerationSettingsGroup(self)
        self.content_layout.addWidget(self.generation_group)
        
        # 下载设置
        self.download_group = DownloadSettingsGroup(self)
        self.content_layout.addWidget(self.download_group)
        
        # 添加拉伸，使内容顶部对齐
        self.content_layout.addStretch(1)
        
        # 设置滚动区域的内容部件
        self.scroll_area.setWidget(self.content_widget)
        
        # 将滚动区域添加到主布局
        main_layout.addWidget(self.scroll_area, 1)
        
        self.setLayout(main_layout)
    
    def update_fonts(self, font):
        """更新所有字体 - 已弃用，使用_update_fonts代替"""
        self._update_fonts()
    
    def _update_fonts(self):
        """更新字体大小 - 使用与主界面相同的算法"""
        if not self.parent_window:
            return
            
        current_width = self.parent_window.width()
        current_height = self.parent_window.height()
        
        # 计算基础字体大小
        width_ratio = current_width / self.default_width
        height_ratio = current_height / self.default_height
        ratio = (width_ratio + height_ratio) / 2
        
        # 更新卡片样式（标题字体大小）
        self._update_card_styles()
        
        base_font_size = (self.min_font_size + 
                         (self.max_font_size - self.min_font_size) * (ratio - 1))
        base_font_size = max(self.min_font_size, min(self.max_font_size, base_font_size))
        
        # 转换为整数
        base_font_size = int(base_font_size)
        
        # 计算其他字体大小
        other_font_size = int(base_font_size * 0.5)
        small_font_size = int(base_font_size * 0.4)
        
        # 获取全局字体设置
        global_font_name = self.settings_manager.Custom.get_value("global_font", "微软雅黑")
        
        # 创建字体
        base_font = QFont(global_font_name, base_font_size)
        other_font = QFont(global_font_name, other_font_size)
        small_font = QFont(global_font_name, small_font_size)
        
        # 应用字体到所有控件
        self._apply_fonts_to_widgets(other_font, small_font)
    
    def _update_card_styles(self):
        """更新所有卡片组的标题样式"""
        # 计算标题字体大小
        current_width = self.parent_window.width()
        current_height = self.parent_window.height()
        base_width = 1024
        base_height = 768
        
        width_ratio = current_width / base_width
        height_ratio = current_height / base_height
        ratio = (width_ratio + height_ratio) / 2
        
        # 标题字体大小范围：12-18px
        title_font_size = max(12, min(18, int(14 * ratio)))
        
        # 获取全局字体设置
        global_font_name = self.settings_manager.Custom.get_value("global_font", "微软雅黑")
        
        # 更新所有卡片组的样式
        dynamic_style = SettingsCustomConfig.get_dynamic_card_style(title_font_size, global_font_name)
        
        # 应用到各个设置组
        self.api_key_group.setStyleSheet(dynamic_style)
        self.generation_group.setStyleSheet(dynamic_style)
        self.download_group.setStyleSheet(dynamic_style)
    
    def _apply_fonts_to_widgets(self, font, small_font):
        """应用字体到所有控件"""
        # 应用字体到API密钥设置组
        self.api_key_group.setFont(font)
        self.api_key_group.chatglm_key_input.setFont(font)
        self._set_form_layout_labels_font(self.api_key_group.layout(), font)
        
        # 应用字体到生成设置组
        self.generation_group.setFont(font)
        self.generation_group.voice_source_combo.setFont(font)
        self.generation_group.voice_combo.setFont(font)
        self.generation_group.speed_minus_btn.setFont(font)
        self.generation_group.speed_plus_btn.setFont(font)
        self.generation_group.speed_display.setFont(font)
        self.generation_group.stretch_enable_checkbox.setFont(font)
        self.generation_group.stretch_minus_btn.setFont(font)
        self.generation_group.stretch_plus_btn.setFont(font)
        self.generation_group.stretch_display.setFont(font)
        self.generation_group.stretch_info.setFont(small_font)
        self.generation_group.save_path_display.setFont(font)
        self.generation_group.save_path_button.setFont(font)
        self._set_form_layout_labels_font(self.generation_group.layout(), font)
        
        # 应用字体到下载设置组
        self.download_group.setFont(font)
        self.download_group.github_mirror_combo.setFont(font)
        self.download_group.download_threads_spin.setFont(font)
        self._set_form_layout_labels_font(self.download_group.layout(), font)
    
    def _set_form_layout_labels_font(self, layout, font):
        """设置QFormLayout中所有标签的字体"""
        if not isinstance(layout, QFormLayout):
            return
        
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), QLabel):
                item.widget().setFont(font)

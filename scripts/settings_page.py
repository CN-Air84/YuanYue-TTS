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
from debug_logger import debug_logger, LogLevel


class SettingsCustomConfig:
    """设置页面配置常量"""
    
    # 统一控件样式系统
    @staticmethod
    def get_unified_styles(text_color="#333333", component_bg_color="#ffffff"):
        return {
            'input': f"""
                QLineEdit, QSpinBox, QDoubleSpinBox {{
                    border: 2px solid #d0d0d0;
                    border-radius: 6px;
                    padding: 8px 12px;
                    margin: 0px;
                    background-color: {component_bg_color};
                    color: {text_color};
                    min-height: 32px;
                }}
                QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
                    border-color: #4A90E2;
                    outline: none;
                }}
                QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
                    border-color: #808080;
                }}
                QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
                    background-color: #f5f5f5;
                    color: #999999;
                    border-color: #e0e0e0;
                }}
                QSpinBox::up-button, QDoubleSpinBox::up-button,
                QSpinBox::down-button, QDoubleSpinBox::down-button {{
                    width: 0px;
                    height: 0px;
                    border: none;
                }}
            """,
            'button': f"""
                QPushButton {{
                    border: 2px solid #4A90E2;
                    border-radius: 6px;
                    padding: 8px 16px;
                    margin: 0px;
                    background-color: #4A90E2;
                    color: #ffffff;
                    font-weight: 500;
                    min-height: 32px;
                    min-width: 80px;
                }}
                QPushButton:hover {{
                    background-color: #357ABD;
                    border-color: #357ABD;
                }}
                QPushButton:pressed {{
                    background-color: #2E5A8E;
                    border-color: #2E5A8E;
                }}
                QPushButton:disabled {{
                    background-color: #cccccc;
                    border-color: #cccccc;
                    color: #999999;
                }}
            """,
            'combo': f"""
                QComboBox {{
                    border: 2px solid #d0d0d0;
                    border-radius: 6px;
                    padding: 8px 35px 8px 12px;
                    margin: 0px;
                    background-color: {component_bg_color};
                    color: {text_color};
                    min-height: 32px;
                }}
                QComboBox:hover {{
                    border-color: #808080;
                }}
                QComboBox:focus {{
                    border-color: #4A90E2;
                    outline: none;
                }}
                QComboBox::drop-down {{
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 30px;
                    border-left: 1px solid #d0d0d0;
                    border-top-right-radius: 6px;
                    border-bottom-right-radius: 6px;
                }}
                QComboBox::down-arrow {{
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 5px solid {text_color};
                    width: 0px;
                    height: 0px;
                    margin-right: 2px;
                }}
            """,
            'checkbox': f"""
                QCheckBox {{
                    spacing: 8px;
                    color: {text_color};
                    margin: 0px;
                }}
                QCheckBox::indicator {{
                    width: 20px;
                    height: 20px;
                    border: 2px solid #d0d0d0;
                    border-radius: 4px;
                    background-color: {component_bg_color};
                }}
                QCheckBox::indicator:checked {{
                    background-color: #4A90E2;
                    border-color: #4A90E2;
                    image: none;
                }}
                QCheckBox::indicator:hover {{
                    border-color: #4A90E2;
                }}
            """,
            'slider': """
                QSlider::groove:horizontal {
                    border: 1px solid #d0d0d0;
                    height: 6px;
                    background: #f0f0f0;
                    margin: 2px 0;
                    border-radius: 3px;
                }
                QSlider::handle:horizontal {
                    background: #4A90E2;
                    border: 1px solid #4A90E2;
                    width: 16px;
                    height: 16px;
                    margin: -6px 0;
                    border-radius: 8px;
                }
                QSlider::handle:horizontal:hover {
                    background: #357ABD;
                    border-color: #357ABD;
                }
            """,
            'slider_button': f"""
                QPushButton {{
                    border: 1px solid #d0d0d0;
                    border-radius: 4px;
                    background-color: {component_bg_color};
                    color: {text_color};
                    padding: 2px;
                    margin: 0px;
                }}
                QPushButton:hover {{
                    background-color: #e0e0e0;
                    border-color: #808080;
                }}
                QPushButton:pressed {{
                    background-color: #d0d0d0;
                }}
                QPushButton:disabled {{
                    background-color: #f5f5f5;
                    color: #cccccc;
                }}
            """

            #真够壮观的
        }

    # 间距系统配置
    SPACING_SYSTEM = {
        'xs': 4,    # 组件内间距
        'sm': 8,    # 组件间小间距
        'md': 16,   # 组件间中间距
        'lg': 24,   # 分组间间距
        'xl': 32    # 大区块间距
    }
    
    # 卡片样式模板
    @staticmethod
    def get_dynamic_card_style(title_font_size=14, font_family="微软雅黑", card_bg="#F5F8FF", text_color="#333333"):
        return f"""
            QGroupBox {{
                background-color: {card_bg};
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 16px;
                margin-top: 8px;
                margin-bottom: 8px;
                color: {text_color};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 16px;
                padding: 4px 12px;
                background-color: {card_bg};
                color: {text_color};
                font-size: {title_font_size}px;
                font-family: "{font_family}";
                font-weight: bold;
                border-radius: 6px;
                border: 1px solid #e0e0e0;
            }}
            QLabel {{
                background-color: transparent;
                color: {text_color};
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
        debug_logger.output("settings_page.py", LogLevel.INFO, "初始化 ApiKeyGroup...", fold_code="SETTINGS_API")
        self.settings_manager = SettingsManager()
        self.wheel_filter = WheelEventFilter()
        self._init_ui()
        self._load_settings()
        self._apply_card_style()
    
    def _apply_card_style(self):
        """应用卡片样式"""
        try:
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
            card_bg = self.settings_manager.get_Custom_value("card_background_color", "#F5F8FF")
            text_color = self.settings_manager.get_Custom_value("text_color", "#333333")
            
            debug_logger.output("settings_page.py", LogLevel.DEBUG, f"应用 ApiKeyGroup 样式: font={global_font_name}, bg={card_bg}, text={text_color}", fold_code="SETTINGS_API")
            
            self.setStyleSheet(SettingsCustomConfig.get_dynamic_card_style(title_font_size, global_font_name, card_bg, text_color))
            self.setContentsMargins(SettingsCustomConfig.SPACING_SYSTEM['lg'], 
                                  SettingsCustomConfig.SPACING_SYSTEM['lg'],
                                  SettingsCustomConfig.SPACING_SYSTEM['lg'], 
                                  SettingsCustomConfig.SPACING_SYSTEM['lg'])
        except Exception as e:
            debug_logger.output("settings_page.py", LogLevel.ERROR, f"应用 ApiKeyGroup 样式时出错: {str(e)}", fold_code="SETTINGS_API")
    
    def _init_ui(self):
        """初始化UI"""
        try:
            layout = QFormLayout()
            layout.setVerticalSpacing(SettingsCustomConfig.SPACING_SYSTEM['md'])
            
            text_color = self.settings_manager.get_Custom_value("text_color", "#333333")
            component_bg = self.settings_manager.get_Custom_value("component_background_color", "#ffffff")
            unified_styles = SettingsCustomConfig.get_unified_styles(text_color, component_bg)
            
            self.chatglm_key_input = QLineEdit()
            self.chatglm_key_input.setPlaceholderText("请输入ChatGLM API密钥")
            self.chatglm_key_input.textChanged.connect(self._on_key_changed)
            self.chatglm_key_input.setStyleSheet(unified_styles['input'])
            self.chatglm_key_input.installEventFilter(self.wheel_filter)
            
            layout.addRow("ChatGLM Key:", self.chatglm_key_input)
            self.setLayout(layout)
            debug_logger.output("settings_page.py", LogLevel.INFO, "ApiKeyGroup UI初始化完成", fold_code="SETTINGS_API")
        except Exception as e:
            debug_logger.output("settings_page.py", LogLevel.ERROR, f"ApiKeyGroup UI初始化失败: {str(e)}", fold_code="SETTINGS_API")

    def _on_key_changed(self, text):
        """API密钥变更处理"""
        try:

            debug_logger.output("settings_page.py", LogLevel.DEBUG, f"ChatGLM API密钥已更新, 长度: {key_len}, 密钥: {text}", fold_code="SETTINGS_API")
            self.settings_manager.set_api_key("api_key_ChatGLM", text)
        except Exception as e:
            debug_logger.output("settings_page.py", LogLevel.ERROR, f"保存API密钥时出错: {str(e)}", fold_code="SETTINGS_API")
    
    def _load_settings(self):
        """加载设置"""
        try:
            api_key = self.settings_manager.get_api_key("api_key_ChatGLM")
            self.chatglm_key_input.setText(api_key)
            debug_logger.output("settings_page.py", LogLevel.INFO, "ApiKeyGroup 设置加载完成", fold_code="SETTINGS_API")
        except Exception as e:
            debug_logger.output("settings_page.py", LogLevel.ERROR, f"加载API密钥时出错: {str(e)}", fold_code="SETTINGS_API")


class GenerationSettingsGroup(QGroupBox):
    """生成设置组 - 卡片式设计"""
    
    def __init__(self, parent=None):
        super().__init__("生成设置", parent)
        debug_logger.output("settings_page.py", LogLevel.INFO, "初始化 GenerationSettingsGroup...", fold_code="SETTINGS_GEN")
        self.settings_manager = SettingsManager()
        self.wheel_filter = WheelEventFilter()
        self._init_ui()
        self._load_settings()
        self._apply_card_style()
    
    def _apply_card_style(self):
        """应用卡片样式"""
        try:
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
            card_bg = self.settings_manager.get_Custom_value("card_background_color", "#F5F8FF")
            
            debug_logger.output("settings_page.py", LogLevel.DEBUG, f"应用 GenerationSettingsGroup 样式: font={global_font_name}, bg={card_bg}", fold_code="SETTINGS_GEN")
            
            self.setStyleSheet(SettingsCustomConfig.get_dynamic_card_style(title_font_size, global_font_name, card_bg))
            self.setContentsMargins(SettingsCustomConfig.SPACING_SYSTEM['lg'], 
                                  SettingsCustomConfig.SPACING_SYSTEM['lg'],
                                  SettingsCustomConfig.SPACING_SYSTEM['lg'], 
                                  SettingsCustomConfig.SPACING_SYSTEM['lg'])
        except Exception as e:
            debug_logger.output("settings_page.py", LogLevel.ERROR, f"应用 GenerationSettingsGroup 样式时出错: {str(e)}", fold_code="SETTINGS_GEN")
    
    def _init_ui(self):
        """初始化UI"""
        try:
            layout = QFormLayout()
            layout.setVerticalSpacing(SettingsCustomConfig.SPACING_SYSTEM['md'])
            
            text_color = self.settings_manager.get_Custom_value("text_color", "#333333")
            component_bg = self.settings_manager.get_Custom_value("component_background_color", "#ffffff")
            unified_styles = SettingsCustomConfig.get_unified_styles(text_color, component_bg)
            
            # 默认音源
            self.voice_source_combo = QComboBox()
            self.voice_source_combo.addItems(['EdgeAPI'])
            self.voice_source_combo.currentTextChanged.connect(
                lambda text: self.settings_manager.set_api_key('default_voice_1', text)
            )
            self.voice_source_combo.setStyleSheet(unified_styles['combo'])
            self.voice_source_combo.installEventFilter(self.wheel_filter)
            layout.addRow("默认音源:", self.voice_source_combo)
            
            # 默认音色
            self.voice_combo = QComboBox()
            self.voice_combo.addItems(['中文'])
            self.voice_combo.currentTextChanged.connect(
                lambda text: self.settings_manager.set_api_key('default_voice_2', text)
            )
            self.voice_combo.setStyleSheet(unified_styles['combo'])
            self.voice_combo.installEventFilter(self.wheel_filter)
            layout.addRow("默认音色:", self.voice_combo)
            
            # 默认语速
            speed_layout = QHBoxLayout()
            self.speed_slider = QSlider(Qt.Horizontal)
            self.speed_slider.setRange(-100, 100)
            self.speed_slider.valueChanged.connect(self._on_speed_changed)
            self.speed_slider.setStyleSheet(unified_styles['slider'])
            
            self.speed_minus_btn = QPushButton('-')
            self.speed_minus_btn.setFixedSize(32, 32)
            self.speed_minus_btn.clicked.connect(lambda: self._adjust_speed(-1))
            self.speed_minus_btn.setStyleSheet(unified_styles['slider_button'])
            
            self.speed_plus_btn = QPushButton('+')
            self.speed_plus_btn.setFixedSize(32, 32)
            self.speed_plus_btn.clicked.connect(lambda: self._adjust_speed(1))
            self.speed_plus_btn.setStyleSheet(unified_styles['slider_button'])
            
            self.speed_display = QLabel("0")
            self.speed_display.setAlignment(Qt.AlignCenter)
            self.speed_display.setMinimumWidth(40)
            
            speed_layout.addWidget(self.speed_display)
            speed_layout.addWidget(self.speed_minus_btn)
            speed_layout.addWidget(self.speed_slider)
            speed_layout.addWidget(self.speed_plus_btn)
            layout.addRow("默认语速:", speed_layout)
            
            self.setLayout(layout)
            debug_logger.output("settings_page.py", LogLevel.INFO, "GenerationSettingsGroup UI初始化完成", fold_code="SETTINGS_GEN")
        except Exception as e:
            debug_logger.output("settings_page.py", LogLevel.ERROR, f"GenerationSettingsGroup UI初始化失败: {str(e)}", fold_code="SETTINGS_GEN")
        
        # 原先的音频拉伸
        # 每日西北有孤忠（1/1）
        # self.stretch_enable_checkbox = QCheckBox("启用音频拉伸")
        # self.stretch_enable_checkbox.stateChanged.connect(self._on_stretch_enable_changed)
        # self.stretch_enable_checkbox.setStyleSheet(unified_styles['checkbox'])
        # layout.addRow(self.stretch_enable_checkbox)
        # 
        # stretch_layout = QHBoxLayout()
        # self.stretch_slider = QSlider(Qt.Horizontal)
        # self.stretch_slider.setRange(5, 200)
        # self.stretch_slider.setValue(100)
        # self.stretch_slider.valueChanged.connect(self._on_stretch_factor_changed)
        # self.stretch_slider.setStyleSheet(unified_styles['slider'])
        # 
        # self.stretch_minus_btn = QPushButton('-')
        # self.stretch_minus_btn.setFixedSize(32, 32)
        # self.stretch_minus_btn.clicked.connect(lambda: self._adjust_speed(-1))
        # self.stretch_minus_btn.setStyleSheet(unified_styles['slider_button'])
        # 
        # self.stretch_plus_btn = QPushButton('+')
        # self.stretch_plus_btn.setFixedSize(32, 32)
        # self.stretch_plus_btn.clicked.connect(lambda: self._adjust_speed(1))
        # self.stretch_plus_btn.setStyleSheet(unified_styles['slider_button'])
        # 
        # self.stretch_display = QLabel("1.00")
        # self.stretch_display.setAlignment(Qt.AlignCenter)
        # self.stretch_display.setMinimumWidth(40)
        # 
        # self.stretch_info = QLabel("(变速不变调，范围: 0.05倍 - 2.00倍)")
        # self.stretch_info.setStyleSheet(f"color: {text_color}; font-size: 12px;")
        # 
        # stretch_layout.addWidget(self.stretch_display)
        # stretch_layout.addWidget(self.stretch_minus_btn)
        # stretch_layout.addWidget(self.stretch_slider)
        # stretch_layout.addWidget(self.stretch_plus_btn)
        # layout.addRow("音频拉伸系数:", stretch_layout)
        # layout.addRow("", self.stretch_info)
        
        # 保存路径
        path_layout = QHBoxLayout()
        self.save_path_display = QLineEdit()
        self.save_path_display.setReadOnly(True)
        self.save_path_display.setStyleSheet(unified_styles['input'])
        
        self.save_path_button = QPushButton("选择路径")
        self.save_path_button.clicked.connect(self._select_save_path)
        self.save_path_button.setStyleSheet(unified_styles['button'])
        
        path_layout.addWidget(self.save_path_display)
        path_layout.addWidget(self.save_path_button)
        layout.addRow("保存路径:", path_layout)
        
        self.setLayout(layout)
        
    
    def _load_settings(self):
        """加载设置"""
        try:
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
            
            save_path = self.settings_manager.get_default_save_path()
            self.save_path_display.setText(save_path)
            debug_logger.output("settings_page.py", LogLevel.INFO, "GenerationSettingsGroup 设置加载完成", fold_code="SETTINGS_GEN")
        except Exception as e:
            debug_logger.output("settings_page.py", LogLevel.ERROR, f"加载生成设置时出错: {str(e)}", fold_code="SETTINGS_GEN")
    
    def _on_speed_changed(self, value):
        """语速改变时的处理"""
        try:
            debug_logger.output("settings_page.py", LogLevel.INFO, f"默认语速变更: {value}", fold_code="SETTINGS_GEN")
            self.speed_display.setText(str(value))
            self.settings_manager.set_default_speed(value)
        except Exception as e:
            debug_logger.output("settings_page.py", LogLevel.ERROR, f"更新默认语速时出错: {str(e)}", fold_code="SETTINGS_GEN")
    
    def _adjust_speed(self, delta):
        """调整语速"""
        try:
            current_value = self.speed_slider.value()
            new_value = current_value + delta
            if self.speed_slider.minimum() <= new_value <= self.speed_slider.maximum():
                debug_logger.output("settings_page.py", LogLevel.INFO, f"微调语速: {current_value} -> {new_value}", fold_code="SETTINGS_GEN")
                self.speed_slider.setValue(new_value)
        except Exception as e:
            debug_logger.output("settings_page.py", LogLevel.ERROR, f"微调默认语速时出错: {str(e)}", fold_code="SETTINGS_GEN")
    
    def _set_stretch_controls_enabled(self, enabled):
        """设置音频拉伸控件是否启用"""
        # 音频拉伸给注释了
        pass
    
    def _select_save_path(self):
        """选择保存路径"""
        try:
            debug_logger.output("settings_page.py", LogLevel.INFO, "打开默认保存路径选择对话框", fold_code="SETTINGS_PATH")
            directory = QFileDialog.getExistingDirectory(self, "选择默认保存路径")
            if directory:
                debug_logger.output("settings_page.py", LogLevel.INFO, f"选择默认保存路径: {directory}", fold_code="SETTINGS_PATH")
                self.save_path_display.setText(directory)
                self.settings_manager.set_default_save_path(directory)
        except Exception as e:
            debug_logger.output("settings_page.py", LogLevel.ERROR, f"选择保存路径时出错: {str(e)}", fold_code="SETTINGS_PATH")
    
    def update_fonts(self, font):
        """更新字体"""
        self.voice_source_combo.setFont(font)
        self.voice_combo.setFont(font)
        self.speed_minus_btn.setFont(font)
        self.speed_plus_btn.setFont(font)
        self.speed_display.setFont(font)
        # 音频拉伸
        # self.stretch_enable_checkbox.setFont(font)
        # self.stretch_minus_btn.setFont(font)
        # self.stretch_plus_btn.setFont(font)
        # self.stretch_display.setFont(font)
        # self.stretch_info.setFont(font)
        self.save_path_display.setFont(font)
        self.save_path_button.setFont(font)


class DownloadSettingsGroup(QGroupBox):
    """下载设置组 - 卡片式设计"""
    
    def __init__(self, parent=None):
        super().__init__("下载设置", parent)
        debug_logger.output("settings_page.py", LogLevel.INFO, "初始化 DownloadSettingsGroup...", fold_code="SETTINGS_DOWNLOAD")
        self.settings_manager = SettingsManager()
        self.wheel_filter = WheelEventFilter()
        self._init_ui()
        self._load_settings()
        self._apply_card_style()
    
    def _apply_card_style(self):
        """应用卡片样式"""
        try:
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
            card_bg = self.settings_manager.get_Custom_value("card_background_color", "#F5F8FF")
            
            debug_logger.output("settings_page.py", LogLevel.DEBUG, f"应用 DownloadSettingsGroup 样式: font={global_font_name}, bg={card_bg}", fold_code="SETTINGS_DOWNLOAD")
            
            self.setStyleSheet(SettingsCustomConfig.get_dynamic_card_style(title_font_size, global_font_name, card_bg))
            self.setContentsMargins(SettingsCustomConfig.SPACING_SYSTEM['lg'], 
                                  SettingsCustomConfig.SPACING_SYSTEM['lg'],
                                  SettingsCustomConfig.SPACING_SYSTEM['lg'], 
                                  SettingsCustomConfig.SPACING_SYSTEM['lg'])
        except Exception as e:
            debug_logger.output("settings_page.py", LogLevel.ERROR, f"应用 DownloadSettingsGroup 样式时出错: {str(e)}", fold_code="SETTINGS_DOWNLOAD")
    
    def _init_ui(self):
        """初始化UI"""
        try:
            layout = QFormLayout()
            layout.setVerticalSpacing(SettingsCustomConfig.SPACING_SYSTEM['md'])
            
            text_color = self.settings_manager.get_Custom_value("text_color", "#333333")
            component_bg = self.settings_manager.get_Custom_value("component_background_color", "#ffffff")
            unified_styles = SettingsCustomConfig.get_unified_styles(text_color, component_bg)
            
            # Github下载加速源已迁移到在线导入设置
            # self.github_mirror_combo = QComboBox()
            # self.github_mirror_combo.addItems([
            # "直接从github服务器获取（海外首选）",
            # "ghfast（中国大陆首选）",
            # "ghproxy 主站（CloudFlare CDN，大陆备用）",
            # "ghproxy HK（港澳台首选）",
            # "ghproxy edgeone（备用）"
            # ])
            # self.github_mirror_combo.currentTextChanged.connect(self._on_github_mirror_changed)
            # self.github_mirror_combo.setStyleSheet(unified_styles['combo'])
            # self.github_mirror_combo.installEventFilter(self.wheel_filter)
            # layout.addRow("Github下载加速源:", self.github_mirror_combo)
            
            # 下载线程数
            self.download_threads_spin = QSpinBox()
            self.download_threads_spin.setRange(1, 16)
            self.download_threads_spin.valueChanged.connect(self._on_download_threads_changed)
            self.download_threads_spin.setStyleSheet(unified_styles['input'])
            self.download_threads_spin.installEventFilter(self.wheel_filter)
            layout.addRow("下载线程数:", self.download_threads_spin)
            
            # 默认保存地址 - 未实装
            save_path_layout = QHBoxLayout()
            self.save_path_display = QLineEdit()
            self.save_path_display.setReadOnly(True)
            self.save_path_display.setPlaceholderText("未实装")
            self.save_path_display.setStyleSheet(unified_styles['input'])
            
            self.save_path_button = QPushButton("选择路径")
            self.save_path_button.setEnabled(False)
            self.save_path_button.setStyleSheet(unified_styles['button'])
            
            save_path_layout.addWidget(self.save_path_display)
            save_path_layout.addWidget(self.save_path_button)
            layout.addRow("默认保存地址:", save_path_layout)
            
            self.setLayout(layout)
            debug_logger.output("settings_page.py", LogLevel.INFO, "DownloadSettingsGroup UI初始化完成", fold_code="SETTINGS_DOWNLOAD")
        except Exception as e:
            debug_logger.output("settings_page.py", LogLevel.ERROR, f"DownloadSettingsGroup UI初始化失败: {str(e)}", fold_code="SETTINGS_DOWNLOAD")

    def _on_github_mirror_changed(self, text):
        """Github镜像源变更 - 已迁移到在线导入设置"""
        try:
            debug_logger.output("settings_page.py", LogLevel.INFO, f"Github下载加速源变更: {text}", fold_code="SETTINGS_DOWNLOAD")
            self.settings_manager.Custom.set_value("github_mirror", text)
        except Exception as e:
            debug_logger.output("settings_page.py", LogLevel.ERROR, f"保存Github镜像设置时出错: {str(e)}", fold_code="SETTINGS_DOWNLOAD")

    def _on_download_threads_changed(self, value):
        """下载线程数变更"""
        try:
            debug_logger.output("settings_page.py", LogLevel.INFO, f"下载线程数变更: {value}", fold_code="SETTINGS_DOWNLOAD")
            self.settings_manager.Custom.set_value("download_threads", str(value))
        except Exception as e:
            debug_logger.output("settings_page.py", LogLevel.ERROR, f"保存下载线程设置时出错: {str(e)}", fold_code="SETTINGS_DOWNLOAD")
    
    def _load_settings(self):
        """加载设置"""
        try:
            # Github下载加速源已迁移到在线导入设置
            # github_mirror = self.settings_manager.Custom.get_value("github_mirror", "https://ghproxy.com")
            # index = self.github_mirror_combo.findText(github_mirror)
            # if index >= 0:
            #     self.github_mirror_combo.setCurrentIndex(index)
            
            download_threads = self.settings_manager.Custom.get_value("download_threads", "4")
            self.download_threads_spin.setValue(int(download_threads))
            debug_logger.output("settings_page.py", LogLevel.INFO, "DownloadSettingsGroup 设置加载完成", fold_code="SETTINGS_DOWNLOAD")
        except Exception as e:
            debug_logger.output("settings_page.py", LogLevel.ERROR, f"加载下载设置时出错: {str(e)}", fold_code="SETTINGS_DOWNLOAD")


class OnlineImportSettingsGroup(QGroupBox):
    """在线导入设置组 - 卡片式设计"""
    
    def __init__(self, parent=None):
        super().__init__("在线导入设置", parent)
        debug_logger.output("settings_page.py", LogLevel.INFO, "初始化 OnlineImportSettingsGroup...", fold_code="SETTINGS_IMPORT")
        self.settings_manager = SettingsManager()
        self.wheel_filter = WheelEventFilter()
        self._init_ui()
        self._load_settings()
        self._apply_card_style()
    
    def _apply_card_style(self):
        """应用卡片样式"""
        try:
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
            card_bg = self.settings_manager.get_Custom_value("card_background_color", "#F5F8FF")
            
            debug_logger.output("settings_page.py", LogLevel.DEBUG, f"应用 OnlineImportSettingsGroup 样式: font={global_font_name}, bg={card_bg}", fold_code="SETTINGS_IMPORT")
            
            self.setStyleSheet(SettingsCustomConfig.get_dynamic_card_style(title_font_size, global_font_name, card_bg))
            self.setContentsMargins(SettingsCustomConfig.SPACING_SYSTEM['lg'], 
                                  SettingsCustomConfig.SPACING_SYSTEM['lg'],
                                  SettingsCustomConfig.SPACING_SYSTEM['lg'], 
                                  SettingsCustomConfig.SPACING_SYSTEM['lg'])
        except Exception as e:
            debug_logger.output("settings_page.py", LogLevel.ERROR, f"应用 OnlineImportSettingsGroup 样式时出错: {str(e)}", fold_code="SETTINGS_IMPORT")
    
    def _init_ui(self):
        """初始化UI"""
        try:
            layout = QFormLayout()
            layout.setVerticalSpacing(SettingsCustomConfig.SPACING_SYSTEM['md'])
            
            text_color = self.settings_manager.get_Custom_value("text_color", "#333333")
            component_bg = self.settings_manager.get_Custom_value("component_background_color", "#ffffff")
            unified_styles = SettingsCustomConfig.get_unified_styles(text_color, component_bg)
            
            # 在线导入模式下拉框
            self.import_mode_combo = QComboBox()
            self.import_mode_combo.addItem("GitHub导入模式", "github")
            self.import_mode_combo.addItem("智慧教育平台导入模式", "sei")
            self.import_mode_combo.currentIndexChanged.connect(self._on_mode_changed)
            self.import_mode_combo.setStyleSheet(unified_styles['combo'])
            layout.addRow("在线导入模式:", self.import_mode_combo)
            
            # 迁来的Github下载加速源
            self.github_mirror_combo = QComboBox()
            self.github_mirror_combo.addItems([
            "直接从github服务器获取（海外首选）",
            "ghfast（中国大陆首选）",
            "ghproxy 主站（CloudFlare CDN，大陆备用）",
            "ghproxy HK（港澳台首选）",
            "ghproxy edgeone（备用）"
            ])
            self.github_mirror_combo.currentTextChanged.connect(self._on_github_mirror_changed)
            self.github_mirror_combo.setStyleSheet(unified_styles['combo'])
            self.github_mirror_combo.installEventFilter(self.wheel_filter)
            layout.addRow("Github下载加速源:", self.github_mirror_combo)
            
            self.setLayout(layout)
            debug_logger.output("settings_page.py", LogLevel.INFO, "OnlineImportSettingsGroup UI初始化完成", fold_code="SETTINGS_IMPORT")
        except Exception as e:
            debug_logger.output("settings_page.py", LogLevel.ERROR, f"OnlineImportSettingsGroup UI初始化失败: {str(e)}", fold_code="SETTINGS_IMPORT")
    
    def _on_mode_changed(self, index):
        """模式改变时的回调"""
        try:
            mode_data = self.import_mode_combo.itemData(index)
            is_sei_mode = (mode_data == "sei")
            debug_logger.output("settings_page.py", LogLevel.INFO, f"在线导入模式变更: {mode_data}, is_sei_mode={is_sei_mode}", fold_code="SETTINGS_IMPORT")
            result = self.settings_manager.set_online_import_mode(is_sei_mode)
            debug_logger.output("settings_page.py", LogLevel.INFO, f"在线导入模式保存结果: {result}", fold_code="SETTINGS_IMPORT")
        except Exception as e:
            debug_logger.output("settings_page.py", LogLevel.ERROR, f"变更在线导入模式时出错: {str(e)}", fold_code="SETTINGS_IMPORT")
    
    def _on_github_mirror_changed(self, text):
        """Github镜像源变更"""
        try:
            debug_logger.output("settings_page.py", LogLevel.INFO, f"Github下载加速源变更: {text}", fold_code="SETTINGS_IMPORT")
            self.settings_manager.Custom.set_value("github_mirror", text)
        except Exception as e:
            debug_logger.output("settings_page.py", LogLevel.ERROR, f"保存Github镜像设置时出错: {str(e)}", fold_code="SETTINGS_IMPORT")
    
    def _load_settings(self):
        """加载设置"""
        try:
            is_sei_mode = self.settings_manager.get_online_import_mode()
            if is_sei_mode:
                index = self.import_mode_combo.findData("sei")
            else:
                index = self.import_mode_combo.findData("github")
            if index >= 0:
                self.import_mode_combo.setCurrentIndex(index)
            
            # Github下载加速源
            github_mirror = self.settings_manager.Custom.get_value("github_mirror", "https://ghproxy.com")
            index = self.github_mirror_combo.findText(github_mirror)
            if index >= 0:
                self.github_mirror_combo.setCurrentIndex(index)
            
            debug_logger.output("settings_page.py", LogLevel.INFO, "OnlineImportSettingsGroup 设置加载完成", fold_code="SETTINGS_IMPORT")
        except Exception as e:
            debug_logger.output("settings_page.py", LogLevel.ERROR, f"加载在线导入设置时出错: {str(e)}", fold_code="SETTINGS_IMPORT")


class TabSettingsGroup(QGroupBox):
    """选项卡设置组 - 卡片式设计"""
    
    def __init__(self, parent=None):
        super().__init__("选项卡设置", parent)
        debug_logger.output("settings_page.py", LogLevel.INFO, "初始化 TabSettingsGroup...", fold_code="SETTINGS_TAB")
        self.settings_manager = SettingsManager()
        self.available_tabs = {
            'welcome': '欢迎',
            'dictation': '听写',
            'settings': '设置',
            'personalization': '个性化',
            'misc': '杂项',
            'streaming': '流媒体'
        }
        self.tab_order = []
        self.tab_visibility = []
        self.wheel_filter = WheelEventFilter()
        self._init_ui()
        self._load_settings()
        self._apply_card_style()
    
    def _apply_card_style(self):
        """应用卡片样式"""
        try:
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
            card_bg = self.settings_manager.get_Custom_value("card_background_color", "#F5F8FF")
            
            debug_logger.output("settings_page.py", LogLevel.DEBUG, f"应用 TabSettingsGroup 样式: font={global_font_name}, bg={card_bg}", fold_code="SETTINGS_TAB")
            
            self.setStyleSheet(SettingsCustomConfig.get_dynamic_card_style(title_font_size, global_font_name, card_bg))
            self.setContentsMargins(SettingsCustomConfig.SPACING_SYSTEM['lg'], 
                                  SettingsCustomConfig.SPACING_SYSTEM['lg'],
                                  SettingsCustomConfig.SPACING_SYSTEM['lg'], 
                                  SettingsCustomConfig.SPACING_SYSTEM['lg'])
        except Exception as e:
            debug_logger.output("settings_page.py", LogLevel.ERROR, f"应用 TabSettingsGroup 样式时出错: {str(e)}", fold_code="SETTINGS_TAB")
    
    def _init_ui(self):
        """初始化UI"""
        try:
            self.main_v_layout = QVBoxLayout()
            self.main_v_layout.setSpacing(SettingsCustomConfig.SPACING_SYSTEM['md'])
            
            text_color = self.settings_manager.get_Custom_value("text_color", "#333333")
            component_bg = self.settings_manager.get_Custom_value("component_background_color", "#ffffff")
            unified_styles = SettingsCustomConfig.get_unified_styles(text_color, component_bg)
            
            # 1. 起始选项卡设置 (使用 QFormLayout 以对齐其他卡片)
            self.top_form_layout = QFormLayout()
            self.top_form_layout.setVerticalSpacing(SettingsCustomConfig.SPACING_SYSTEM['md'])
            
            self.initial_tab_combo = QComboBox()
            for name, display_name in self.available_tabs.items():
                self.initial_tab_combo.addItem(display_name, name)
            self.initial_tab_combo.currentIndexChanged.connect(self._save_settings)
            self.initial_tab_combo.setStyleSheet(unified_styles['combo'])
            self.initial_tab_combo.installEventFilter(self.wheel_filter)
            
            self.top_form_layout.addRow("起始选项卡:", self.initial_tab_combo)
            self.main_v_layout.addLayout(self.top_form_layout)
            
            # 2. 选项卡排序和可见性标题
            list_header_layout = QHBoxLayout()
            self.list_header = QLabel("选项卡排序与可见性 (勾选以显示，使用按钮调整顺序):")
            self.list_header.setStyleSheet(f"font-weight: bold; margin-top: 10px; color: {text_color};")
            
            self.restart_hint = QLabel("(修改后需重启软件生效)")
            self.restart_hint.setStyleSheet("color: #FF4500; margin-top: 10px;") # 保持红色作为提示
            
            list_header_layout.addWidget(self.list_header)
            list_header_layout.addWidget(self.restart_hint)
            list_header_layout.addStretch(1)
            self.main_v_layout.addLayout(list_header_layout)
            
            # 3. 选项卡列表容器
            self.tab_list_container = QWidget()
            self.tab_list_layout = QVBoxLayout(self.tab_list_container)
            self.tab_list_layout.setContentsMargins(0, 0, 0, 0)
            self.tab_list_layout.setSpacing(SettingsCustomConfig.SPACING_SYSTEM['sm'])
            self.main_v_layout.addWidget(self.tab_list_container)
            
            self.setLayout(self.main_v_layout)
            debug_logger.output("settings_page.py", LogLevel.INFO, "TabSettingsGroup UI初始化完成", fold_code="SETTINGS_TAB")
        except Exception as e:
            debug_logger.output("settings_page.py", LogLevel.ERROR, f"TabSettingsGroup UI初始化失败: {str(e)}", fold_code="SETTINGS_TAB")
    
    def _load_settings(self):
        """加载设置"""
        try:
            # 加载排序
            order_str = self.settings_manager.get_Custom_value("tab_order", "welcome,dictation,settings,personalization,misc,streaming")
            self.tab_order = [t.strip() for t in order_str.split(',') if t.strip() and t.strip() in self.available_tabs]
            # 补全缺失的选项卡
            for name in self.available_tabs:
                if name not in self.tab_order:
                    self.tab_order.append(name)
            
            # 加载可见性
            visibility_str = self.settings_manager.get_Custom_value("tab_visibility", "welcome,dictation,settings,personalization,misc,streaming")
            self.tab_visibility = [t.strip() for t in visibility_str.split(',') if t.strip() and t.strip() in self.available_tabs]
            
            # 加载初始页
            initial_tab = self.settings_manager.get_Custom_value("initial_tab", "welcome")
            idx = self.initial_tab_combo.findData(initial_tab)
            if idx >= 0:
                # 暂时断开信号以避免加载时触发保存
                self.initial_tab_combo.blockSignals(True)
                self.initial_tab_combo.setCurrentIndex(idx)
                self.initial_tab_combo.blockSignals(False)
                
            self._refresh_tab_list_ui()
            debug_logger.output("settings_page.py", LogLevel.INFO, "TabSettingsGroup 设置加载完成", fold_code="SETTINGS_TAB")
        except Exception as e:
            debug_logger.output("settings_page.py", LogLevel.ERROR, f"加载选项卡设置时出错: {str(e)}", fold_code="SETTINGS_TAB")
    
    def _refresh_tab_list_ui(self):
        """刷新选项卡列表UI"""
        try:
            debug_logger.output("settings_page.py", LogLevel.INFO, "开始刷新选项卡列表UI", fold_code="SETTINGS_TAB")
            # 清除现有项目
            clear_count = 0
            while self.tab_list_layout.count():
                item = self.tab_list_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    try:
                        widget.deleteLater()
                        clear_count += 1
                    except Exception as e:
                        debug_logger.output("settings_page.py", LogLevel.WARNING, f"删除选项卡项组件时出错: {str(e)}", fold_code="SETTINGS_TAB")
            
            if clear_count > 0:
                debug_logger.output("settings_page.py", LogLevel.DEBUG, f"已清除 {clear_count} 个旧选项卡组件", fold_code="SETTINGS_TAB")
            
            # 确保 'settings' 始终在可见列表中
            if 'settings' not in self.tab_visibility:
                debug_logger.output("settings_page.py", LogLevel.WARNING, "检测到设置选项卡被隐藏，正在强制恢复显示以防止用户无法再次进入设置", fold_code="SETTINGS_TAB")
                self.tab_visibility.append('settings')
                self._save_settings()

            # 获取当前全局字体和文字颜色
            global_font_name = self.settings_manager.Custom.get_value("global_font", "微软雅黑")
            text_color = self.settings_manager.get_Custom_value("text_color", "#333333")
            component_bg = self.settings_manager.get_Custom_value("component_background_color", "#ffffff")
            unified_styles = SettingsCustomConfig.get_unified_styles(text_color, component_bg)
            
            # 根据当前顺序创建项目
            for i, name in enumerate(self.tab_order):
                row_widget = QWidget()
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(5, 2, 5, 2)
                
                # 复选框 (可见性)
                display_name = self.available_tabs.get(name, name)
                cb = QCheckBox(display_name)
                cb.setChecked(name in self.tab_visibility)
                # 应用全局字体
                cb.setFont(QFont(global_font_name))
                # 设置选项卡强制可见
                if name == 'settings':
                    cb.setEnabled(False)
                    cb.setToolTip("“设置”选项卡必须始终可见")
                
                cb.stateChanged.connect(lambda state, n=name: self._on_visibility_changed(n, state))
                cb.setStyleSheet(unified_styles['checkbox'])
                
                # 向上按钮
                up_btn = QPushButton("↑")
                up_btn.setFont(QFont(global_font_name))
                up_btn.setFixedSize(30, 30)
                up_btn.setEnabled(i > 0)
                up_btn.clicked.connect(lambda checked, idx=i: self._move_tab(idx, -1))
                up_btn.setStyleSheet(unified_styles['slider_button'])
                
                # 向下按钮
                down_btn = QPushButton("↓")
                down_btn.setFont(QFont(global_font_name))
                down_btn.setFixedSize(30, 30)
                down_btn.setEnabled(i < len(self.tab_order) - 1)
                down_btn.clicked.connect(lambda checked, idx=i: self._move_tab(idx, 1))
                down_btn.setStyleSheet(unified_styles['slider_button'])
                
                row_layout.addWidget(cb)
                row_layout.addStretch(1)
                row_layout.addWidget(up_btn)
                row_layout.addWidget(down_btn)
                
                self.tab_list_layout.addWidget(row_widget)
            
            # 更新起始页下拉框
            self._update_initial_tab_combo()
            
            # 触发父窗口更新字体，确保新创建的控件应用正确的缩放
            if self.parent() and hasattr(self.parent(), '_update_fonts'):
                self.parent()._update_fonts()
                
            debug_logger.output("settings_page.py", LogLevel.INFO, f"选项卡列表UI刷新完成 (共 {len(self.tab_order)} 项)", fold_code="SETTINGS_TAB")
        except Exception as e:
            debug_logger.output("settings_page.py", LogLevel.ERROR, f"刷新选项卡列表UI时发生异常: {str(e)}", fold_code="SETTINGS_TAB")

    def _update_initial_tab_combo(self):
        """根据可见性更新起始页下拉框"""
        try:
            current_selection = self.initial_tab_combo.currentData()
            
            self.initial_tab_combo.blockSignals(True)
            self.initial_tab_combo.clear()
            
            # 仅添加当前可见的选项卡，并保持 tab_order 中的顺序
            for name in self.tab_order:
                if name in self.tab_visibility:
                    self.initial_tab_combo.addItem(self.available_tabs[name], name)
            
            # 尝试恢复之前的选择
            idx = self.initial_tab_combo.findData(current_selection)
            if idx >= 0:
                self.initial_tab_combo.setCurrentIndex(idx)
            else:
                # 如果之前的选择现在不可见，默认选第一个（通常是'welcome'或'settings'）
                self.initial_tab_combo.setCurrentIndex(0)
                # 保存
                self.initial_tab_combo.blockSignals(False)
                self._save_settings()
                self.initial_tab_combo.blockSignals(True)
                
            self.initial_tab_combo.blockSignals(False)
            debug_logger.output("settings_page.py", LogLevel.INFO, f"起始选项卡下拉框更新完成, 当前选中: {self.initial_tab_combo.currentText()}", fold_code="SETTINGS_TAB")
        except Exception as e:
            debug_logger.output("settings_page.py", LogLevel.ERROR, f"更新起始选项卡下拉框时出错: {str(e)}", fold_code="SETTINGS_TAB")
            
    def _on_visibility_changed(self, name, state):
        """可见性改变"""
        try:
            is_visible = (state == Qt.Checked)
            debug_logger.output("settings_page.py", LogLevel.INFO, f"选项卡可见性变更: {name} -> {is_visible}", fold_code="SETTINGS_TAB")
            if is_visible:
                if name not in self.tab_visibility:
                    self.tab_visibility.append(name)
            else:
                if name in self.tab_visibility:
                    self.tab_visibility.remove(name)
            
            # 刷新起始页下拉框
            self._update_initial_tab_combo()
            self._save_settings()
        except Exception as e:
            debug_logger.output("settings_page.py", LogLevel.ERROR, f"处理选项卡可见性变更时出错 ({name}): {str(e)}", fold_code="SETTINGS_TAB")
        
    def _move_tab(self, index, direction):
        """移动选项卡位置"""
        try:
            new_index = index + direction
            if 0 <= new_index < len(self.tab_order):
                debug_logger.output("settings_page.py", LogLevel.INFO, f"移动选项卡: {self.tab_order[index]} 从 {index} 移动到 {new_index}", fold_code="SETTINGS_TAB")
                self.tab_order[index], self.tab_order[new_index] = self.tab_order[new_index], self.tab_order[index]
                self._refresh_tab_list_ui()
                self._save_settings()
        except Exception as e:
            debug_logger.output("settings_page.py", LogLevel.ERROR, f"移动选项卡位置时出错: {str(e)}", fold_code="SETTINGS_TAB")
            
    def _save_settings(self):
        """保存所有选项卡设置"""
        try:
            debug_logger.output("settings_page.py", LogLevel.INFO, "正在保存选项卡设置...", fold_code="SETTINGS_TAB")
            order_str = ",".join(self.tab_order)
            visibility_str = ",".join(self.tab_visibility)
            initial_tab = self.initial_tab_combo.currentData()
            
            self.settings_manager.set_Custom_value("tab_order", order_str)
            self.settings_manager.set_Custom_value("tab_visibility", visibility_str)
            self.settings_manager.set_Custom_value("initial_tab", initial_tab)
            debug_logger.output("settings_page.py", LogLevel.INFO, "选项卡设置保存成功", fold_code="SETTINGS_TAB")
        except Exception as e:
            debug_logger.output("settings_page.py", LogLevel.ERROR, f"保存选项卡设置时出错: {str(e)}", fold_code="SETTINGS_TAB")


class SettingsPage(QWidget):
    """设置页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        debug_logger.output("settings_page.py", LogLevel.INFO, "初始化设置页面...", fold_code="SETTINGS_INIT")
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
        
        # 连接设置变更信号
        if hasattr(self.parent_window, 'shared_memory_manager'):
            self.parent_window.shared_memory_manager.settings_changed.connect(self._on_settings_changed)

    def _on_settings_changed(self, section, data):
        """处理设置变更"""
        if section == 'Custom':
            # 检查是否是颜色相关的变更
            if 'text_color' in data or 'component_background_color' in data or 'card_background_color' in data:
                # 更新所有子分组的样式
                for group in [self.api_key_group, self.generation_group, 
                             self.download_group, self.online_import_group, 
                             self.tab_settings_group]:
                    if hasattr(group, '_apply_card_style'):
                        group._apply_card_style()
                    # 更新内部组件样式
                    self._update_group_text_styles(group)

    def _update_group_text_styles(self, group):
        """更新分组内所有标签和输入框的文字颜色和背景"""
        import re
        text_color = self.settings_manager.get_Custom_value("text_color", "#333333")
        component_bg = self.settings_manager.get_Custom_value("component_background_color", "#ffffff")
        unified_styles = SettingsCustomConfig.get_unified_styles(text_color, component_bg)
        
        # 递归更新子部件
        def update_widget_styles(widget):
            if isinstance(widget, QLabel):
                # 排除 restart_hint 等特殊红色标签
                current_style = widget.styleSheet()
                if "color: #FF4500" not in current_style:
                    if "color:" in current_style:
                        new_style = re.sub(r'color:\s*#[a-zA-Z0-9]+;?', f'color: {text_color};', current_style)
                        widget.setStyleSheet(new_style)
                    else:
                        widget.setStyleSheet(f"color: {text_color};")
            elif isinstance(widget, (QLineEdit, QSpinBox, QDoubleSpinBox)):
                widget.setStyleSheet(unified_styles['input'])
            elif isinstance(widget, QComboBox):
                widget.setStyleSheet(unified_styles['combo'])
            elif isinstance(widget, QCheckBox):
                widget.setStyleSheet(unified_styles['checkbox'])
            elif isinstance(widget, QPushButton):
                # 区分普通按钮和 slider_button
                if widget.width() <= 40 and widget.height() <= 40:
                    widget.setStyleSheet(unified_styles['slider_button'])
                else:
                    widget.setStyleSheet(unified_styles['button'])
            
            # 遍历子部件
            for child in widget.children():
                if isinstance(child, QWidget):
                    update_widget_styles(child)
        
        update_widget_styles(group)
    
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
        # self.generation_group = GenerationSettingsGroup(self)
        # self.content_layout.addWidget(self.generation_group)
        
        # 下载设置
        self.download_group = DownloadSettingsGroup(self)
        self.content_layout.addWidget(self.download_group)
        
        # 在线导入设置
        self.online_import_group = OnlineImportSettingsGroup(self)
        self.content_layout.addWidget(self.online_import_group)
        
        # 选项卡设置
        self.tab_settings_group = TabSettingsGroup(self)
        self.content_layout.addWidget(self.tab_settings_group)
        
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
        card_bg = self.settings_manager.get_Custom_value("card_background_color", "#F5F8FF")
        
        # 更新所有卡片组的样式
        dynamic_style = SettingsCustomConfig.get_dynamic_card_style(title_font_size, global_font_name, card_bg)
        
        # 应用到各个设置组
        if hasattr(self, 'api_key_group'):
            self.api_key_group.setStyleSheet(dynamic_style)
        if hasattr(self, 'generation_group'):
            self.generation_group.setStyleSheet(dynamic_style)
        if hasattr(self, 'download_group'):
            self.download_group.setStyleSheet(dynamic_style)
        if hasattr(self, 'online_import_group'):
            self.online_import_group.setStyleSheet(dynamic_style)
        if hasattr(self, 'tab_settings_group'):
            self.tab_settings_group.setStyleSheet(dynamic_style)
    
    def _apply_fonts_to_widgets(self, font, small_font):
        """应用字体到所有控件"""
        # 应用字体到API密钥设置组
        if hasattr(self, 'api_key_group'):
            self.api_key_group.setFont(font)
            self.api_key_group.chatglm_key_input.setFont(font)
            self._set_form_layout_labels_font(self.api_key_group.layout(), font)
        
        # 应用字体到生成设置组
        # if hasattr(self, 'generation_group'):
        #     self.generation_group.setFont(font)
        #     self.generation_group.voice_source_combo.setFont(font)
        #     self.generation_group.voice_combo.setFont(font)
        #     self.generation_group.speed_minus_btn.setFont(font)
        #     self.generation_group.speed_plus_btn.setFont(font)
        #     self.generation_group.speed_display.setFont(font)
        #     # self.generation_group.stretch_enable_checkbox.setFont(font)
        #     # self.generation_group.stretch_minus_btn.setFont(font)
        #     # self.generation_group.stretch_plus_btn.setFont(font)
        #     # self.generation_group.stretch_display.setFont(font)
        #     # self.generation_group.stretch_info.setFont(small_font)
        #     self.generation_group.save_path_display.setFont(font)
        #     self.generation_group.save_path_button.setFont(font)
        #     self._set_form_layout_labels_font(self.generation_group.layout(), font)
        
        # 应用字体到下载设置组
        if hasattr(self, 'download_group'):
            self.download_group.setFont(font)
            self.download_group.download_threads_spin.setFont(font)
            self.download_group.save_path_display.setFont(font)
            self.download_group.save_path_button.setFont(font)
            self._set_form_layout_labels_font(self.download_group.layout(), font)
        
        # 应用字体到在线导入设置组
        if hasattr(self, 'online_import_group'):
            self.online_import_group.setFont(font)
            self.online_import_group.import_mode_combo.setFont(font)
            self.online_import_group.github_mirror_combo.setFont(font)
            self._set_form_layout_labels_font(self.online_import_group.layout(), font)
        
        # 应用字体到选项卡设置组
        if hasattr(self, 'tab_settings_group'):
            self.tab_settings_group.setFont(font)
            self.tab_settings_group.initial_tab_combo.setFont(font)
            self.tab_settings_group.list_header.setFont(font)
            self.tab_settings_group.restart_hint.setFont(small_font)
            self._set_form_layout_labels_font(self.tab_settings_group.top_form_layout, font)
            
            # 遍历选项卡列表中的所有控件
            for i in range(self.tab_settings_group.tab_list_layout.count()):
                row_item = self.tab_settings_group.tab_list_layout.itemAt(i)
                if row_item and row_item.widget():
                    row_widget = row_item.widget()
                    # 遍历行部件中的复选框和按钮
                    for child in row_widget.findChildren(QWidget):
                        if isinstance(child, (QCheckBox, QPushButton)):
                            child.setFont(font)
    
    def _set_form_layout_labels_font(self, layout, font):
        """设置QFormLayout中所有标签的字体"""
        if not isinstance(layout, QFormLayout):
            return
        
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), QLabel):
                item.widget().setFont(font)

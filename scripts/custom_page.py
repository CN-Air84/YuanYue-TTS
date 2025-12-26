# coding=utf-8
import os
import re
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QLineEdit, QPushButton, QColorDialog, QGroupBox, QFormLayout,
    QSpinBox, QMessageBox, QDoubleSpinBox, QScrollArea, QGridLayout,
    QFontComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QEvent
from PyQt5.QtGui import QFont, QColor, QFontDatabase

from misc_func import SettingsManager
import misc_func
from audio_preview import KeyboardControlScheme
from shared_memory_manager import get_shared_memory_manager

class CustomConfig:
    """个性化配置常量"""
    
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
        """
    }
    
    # 窗口尺寸预设已迁移到misc_func.py中的CustomConfig类
    
    # 键盘控制方案选项
    KEYBOARD_SCHEMES = KeyboardControlScheme.get_all_schemes()
    
    # 默认颜色配置
    DEFAULT_COLORS = {
        "background": "#E5E8EF",
        "notification_info": "#3498db",
        "notification_warning": "#f0da12",
        "notification_error": "#db3444"
    }
    
    # 默认字体配置
    DEFAULT_FONTS = {
        "global_font": "微软雅黑",
        "min_font_size": "22",
        "max_font_size": "42"
    }
    
    # 默认通知配置
    DEFAULT_NOTIFICATIONS = {
        "animation_appear": "400",
        "animation_disappear": "400", 
        "animation_move": "500",
        "position_m": "12",
        "position_n": "12.25",
        "width_ratio": "1",
        "height_ratio": "0.5",
        "max_visible": "5",
        "offset_n": "1",
        "spacing_n": "1.25",
        "auto_close_time": "3000"
    }
    
    @staticmethod
    def get_dynamic_card_style(title_font_size=14):
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
            # 阻止滚轮事件
            return True
        return False


class ColorPickerWidget(QWidget):
    """增强的颜色选择器组件 - 带视觉反馈和错误处理"""
    
    color_changed = pyqtSignal(str)
    
    def __init__(self, initial_color: str = "#000000", parent=None):
        super().__init__(parent)
        self.color_value = initial_color
        self.wheel_filter = WheelEventFilter()
        self.valid_color = "#d0d0d0"  # 有效颜色边框
        self.invalid_color = "#ff4444"  # 无效颜色边框
        self.focus_color = "#4A90E2"   # 焦点颜色边框
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(CustomConfig.SPACING_SYSTEM['sm'])
        
        # 颜色显示框
        self.color_display = QLabel()
        self.color_display.setFixedSize(40, 32)  # 增大尺寸
        self.color_display.setCursor(Qt.PointingHandCursor)  # 添加手型光标
        self._update_color_display()
        self.color_display.mousePressEvent = self._show_color_dialog
        
        # 颜色输入框
        self.color_input = QLineEdit(self.color_value)
        self.color_input.setFixedWidth(100)  # 增加宽度
        self.color_input.textChanged.connect(self._on_text_changed)
        self.color_input.setStyleSheet(CustomConfig.UNIFIED_STYLES['input'])
        self.color_input.setMaxLength(7)  # 限制输入长度
        # 安装滚轮事件过滤器
        self.color_input.installEventFilter(self.wheel_filter)
        
        layout.addWidget(self.color_display)
        layout.addWidget(self.color_input)
        layout.addStretch()  # 添加弹性空间
        
        self.setLayout(layout)
        
        # 连接信号 - 点击颜色显示框打开颜色选择器
        self.color_display.mousePressEvent = lambda event: self._show_color_dialog()
        self.color_display.setCursor(Qt.PointingHandCursor)  # 添加手型光标
    
    def _apply_card_style(self):
        """应用卡片样式"""
        self.setStyleSheet(CustomConfig.CARD_STYLE)
        self.setContentsMargins(
            CustomConfig.SPACING_SYSTEM['lg'],
            CustomConfig.SPACING_SYSTEM['lg'],
            CustomConfig.SPACING_SYSTEM['lg'],
            CustomConfig.SPACING_SYSTEM['lg']
        )
    
    def _update_color_display(self):
        """更新颜色显示框样式"""
        self.color_display.setStyleSheet(f"""
            QLabel {{
                background-color: {self.color_value};
                border: 2px solid {self.valid_color};
                border-radius: 6px;
                padding: 2px;
            }}
            QLabel:hover {{
                border-color: {self.focus_color};
                border-width: 3px;
            }}
        """)
    
    def _show_color_dialog(self, event=None):
        """显示颜色选择对话框"""
        color = QColorDialog.getColor(QColor(self.color_value), self, "选择颜色")
        if color.isValid():
            self.set_color(color.name())
    
    def _on_text_changed(self, text: str):
        """文本输入改变事件 - 带视觉反馈"""
        if self._is_valid_color(text):
            self.color_value = text
            self._update_color_display() 
            self.color_input.setStyleSheet(CustomConfig.UNIFIED_STYLES['input'])  # 恢复默认样式
            self.color_changed.emit(text)
        else:
            # 无效颜色时显示错误状态
            self.color_input.setStyleSheet(f"""
                QLineEdit {{
                    background-color: #fff5f5;
                    color: #cc0000;
                    border: 2px solid {self.invalid_color};
                    border-radius: 10px;
                    padding: 5px;
                }}
            """)
    
    def _is_valid_color(self, color_str: str) -> bool:
        """检查颜色字符串是否有效"""
        pattern = r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$'
        return re.match(pattern, color_str) is not None
    
    def set_color(self, color: str):
        """设置颜色 - 带验证"""
        if self._is_valid_color(color):
            self.color_value = color
            self.color_input.setText(color)
            self._update_color_display() 
            self.color_input.setStyleSheet(CustomConfig.UNIFIED_STYLES['input'])  # 恢复默认样式
            self.color_changed.emit(color)
    
    def get_color(self) -> str:
        """获取颜色"""
        return self.color_value


class KeyboardControlGroup(QGroupBox):
    """键盘控制设置组 - 卡片式设计"""
    
    def __init__(self, parent=None):
        super().__init__("键盘控制设置", parent)
        self.settings_manager = SettingsManager()
        self.wheel_filter = WheelEventFilter()
        self._init_ui()
        self._load_settings()
        self._apply_card_style()
    
    def _apply_card_style(self):
        """应用卡片样式"""
        # 获取父窗口的字体大小来计算标题字体大小
        title_font_size = 14  # 默认标题字体大小
        if self.parent() and hasattr(self.parent(), 'parent_window') and self.parent().parent_window:
            # 计算基于窗口大小的标题字体大小
            current_width = self.parent().parent_window.width()
            current_height = self.parent().parent_window.height()
            base_width = 1024
            base_height = 768
            
            width_ratio = current_width / base_width
            height_ratio = current_height / base_height
            ratio = (width_ratio + height_ratio) / 2
            
            # 标题字体大小范围：12-18px
            title_font_size = max(12, min(18, int(14 * ratio)))
        
        # 使用动态卡片样式
        self.setStyleSheet(CustomConfig.get_dynamic_card_style(title_font_size))
        self.setContentsMargins(CustomConfig.SPACING_SYSTEM['lg'], 
                              CustomConfig.SPACING_SYSTEM['lg'],
                              CustomConfig.SPACING_SYSTEM['lg'], 
                              CustomConfig.SPACING_SYSTEM['lg'])
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        layout.setSpacing(CustomConfig.SPACING_SYSTEM['md'])  # 添加间距
        
        # 标题标签
        title_label = QLabel("选择键盘控制方案:   （注：需要重启软件）")
        title_label.setStyleSheet("font-weight: bold; color: #333;")
        
        # 键盘控制方案选择
        self.scheme_combo = QComboBox()
        schemes = KeyboardControlScheme.get_all_schemes()
        for scheme_id, scheme_name in schemes.items():
            self.scheme_combo.addItem(scheme_name, scheme_id)
        
        self.scheme_combo.currentIndexChanged.connect(self._on_scheme_changed)
        self.scheme_combo.setStyleSheet(CustomConfig.UNIFIED_STYLES['combo'])
        # 安装滚轮事件过滤器
        self.scheme_combo.installEventFilter(self.wheel_filter)
        
        # 方案说明标签
        self.scheme_description = QLabel()
        self.scheme_description.setWordWrap(True)
        self.scheme_description.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 12px;
                background-color: #f8f9fa;
                padding: 8px;
                border-radius: 6px;
                border: 1px solid #e9ecef;
            }
        """)
        
        layout.addWidget(title_label)
        layout.addWidget(self.scheme_combo)
        layout.addWidget(self.scheme_description)
        layout.addStretch()  # 添加弹性空间
        
        self.setLayout(layout)
        
        # 更新初始方案说明
        self._update_scheme_description()
    
    def _apply_card_style(self):
        """应用卡片样式"""
        self.setStyleSheet(CustomConfig.CARD_STYLE)
        # 设置内边距
        self.setContentsMargins(
            CustomConfig.SPACING_SYSTEM['lg'],
            CustomConfig.SPACING_SYSTEM['lg'],
            CustomConfig.SPACING_SYSTEM['lg'],
            CustomConfig.SPACING_SYSTEM['lg']
        )
    
    def _load_settings(self):
        """加载设置"""
        keyboard_scheme = self.settings_manager.Custom.get_value("keyboard_scheme", "1")
        try:
            scheme_id = int(keyboard_scheme)
            index = self.scheme_combo.findData(scheme_id)
            if index >= 0:
                self.scheme_combo.setCurrentIndex(index)
        except (ValueError, TypeError):
            self.scheme_combo.setCurrentIndex(0)  # 默认方案①
    
    def _on_scheme_changed(self, index):
        """键盘控制方案改变事件"""
        scheme_id = self.scheme_combo.currentData()
        self.settings_manager.Custom.set_value("keyboard_scheme", str(scheme_id))
        
        # 更新方案说明
        self._update_scheme_description()
        
        # 更新音频预览的键盘控制方案
        if hasattr(self.parent(), 'parent_window'):
            self.parent().parent_window.audio_preview.set_keyboard_scheme(scheme_id)
    
    def _update_scheme_description(self):
        """更新方案说明"""
        scheme_id = self.scheme_combo.currentData()
        
        descriptions = {
            1: "方案①：空格键暂停/继续，A键回退5秒，W键增加音量，S键降低音量",
            2: "方案②：右Shift键暂停/继续，方向键控制音量和进度，=键和-键控制大跨度进度",
            3: "方案③：小键盘0或5暂停/继续，小键盘8和2控制音量，小键盘4回退5秒"
        }
        
        self.scheme_description.setText(descriptions.get(scheme_id, ""))
    
    def _get_combo_box_style(self):
        global_font = self.settings_manager.Custom.get_value("global_font", "微软雅黑")
        return f"""
        QComboBox {{
            font-family: "{global_font}"; background-color: white; color: black; 
            border: 2px solid gray; border-radius: 10px; padding: 5px;
        }}
        QComboBox::drop-down {{
            border-left-width: 2px; border-left-color: gray; border-left-style: solid;
            border-top-right-radius: 10px; border-bottom-right-radius: 10px;
            width: 30px;
        }}
        QComboBox::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid black;
            width: 0px;
            height: 0px;
        }}
        """


class WindowSizeGroup(QGroupBox):
    """窗口尺寸设置组 - 卡片式设计"""
    
    def __init__(self, parent=None):
        super().__init__("窗口尺寸设置", parent)
        self.settings_manager = SettingsManager()
        self.wheel_filter = WheelEventFilter()
        self._init_ui()
        self._load_settings()
        self._apply_card_style()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QFormLayout()
        layout.setVerticalSpacing(CustomConfig.SPACING_SYSTEM['md'])  # 添加垂直间距
        
        # 标题标签
        title_label = QLabel("预设窗口尺寸:")
        title_label.setStyleSheet("font-weight: bold; color: #333;")
        
        # 窗口尺寸选择
        self.size_combo = QComboBox()
        self.size_combo.addItems(misc_func.CustomConfig.get_window_sizes())
        self.size_combo.currentTextChanged.connect(self._on_size_changed)
        self.size_combo.setStyleSheet(CustomConfig.UNIFIED_STYLES['combo'])
        # 安装滚轮事件过滤器
        self.size_combo.installEventFilter(self.wheel_filter)
        
        layout.addRow(title_label, self.size_combo)
        
        self.setLayout(layout)
    
    def _apply_card_style(self):
        """应用卡片样式"""
        self.setStyleSheet(CustomConfig.CARD_STYLE)
        self.setContentsMargins(
            CustomConfig.SPACING_SYSTEM['lg'],
            CustomConfig.SPACING_SYSTEM['lg'],
            CustomConfig.SPACING_SYSTEM['lg'],
            CustomConfig.SPACING_SYSTEM['lg']
        )
    
    def _load_settings(self):
        """加载设置"""
        window_size = self.settings_manager.Custom.get_value("window_size", "1024x768")
        if window_size in misc_func.CustomConfig.get_window_sizes():
            self.size_combo.setCurrentText(window_size)
    
    def _on_size_changed(self, size: str):
        """窗口尺寸改变事件"""
        self.settings_manager.Custom.set_value("window_size", size)


class ColorSettingsGroup(QGroupBox):
    """颜色设置组 - 卡片式设计"""
    
    # 主题预设
    COLOR_THEMES = {
        "默认": {
            "background": "#E5E8EF",
            "highlight_button": "#4682B4",
            "notification_info": "#3498db",
            "notification_warning": "#f0da12",
            "notification_error": "#db3444"
        },
        "深色": {
            "background": "#2b2b2b",
            "highlight_button": "#1e88e5",
            "notification_info": "#1e88e5",
            "notification_warning": "#ffb300",
            "notification_error": "#e53935"
        },
        "护眼": {
            "background": "#cce8cf",
            "highlight_button": "#4caf50",
            "notification_info": "#4caf50",
            "notification_warning": "#ff9800",
            "notification_error": "#f44336"
        }
    }
    
    def __init__(self, parent=None):
        super().__init__("颜色设置", parent)
        self.settings_manager = SettingsManager()
        self.wheel_filter = WheelEventFilter()  # 添加滚轮事件过滤器
        self._init_ui()
        self._load_settings()
        self._apply_card_style()
    
    def _init_ui(self):
        """初始化UI - 使用网格布局增强视觉效果"""
        layout = QGridLayout()
        layout.setHorizontalSpacing(CustomConfig.SPACING_SYSTEM['lg'])  # 水平间距
        layout.setVerticalSpacing(CustomConfig.SPACING_SYSTEM['md'])    # 垂直间距
        
        # 主题预设选择器
        theme_label = QLabel("主题预设:")
        theme_label.setStyleSheet("font-weight: bold; color: #333;")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["自定义"] + misc_func.CustomConfig.get_theme_names())
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        self.theme_combo.setStyleSheet(CustomConfig.UNIFIED_STYLES['combo'])
        # 安装滚轮事件过滤器
        self.theme_combo.installEventFilter(self.wheel_filter)
        
        # 创建颜色选择器
        self.background_color = ColorPickerWidget()
        self.highlight_button_color = ColorPickerWidget()
        self.info_color = ColorPickerWidget()
        self.warning_color = ColorPickerWidget()
        self.error_color = ColorPickerWidget()
        
        # 连接信号
        self.background_color.color_changed.connect(
            lambda color: self._on_color_changed("background_color", color)
        )
        self.highlight_button_color.color_changed.connect(
            lambda color: self._on_color_changed("highlight_button_color", color)
        )
        self.info_color.color_changed.connect(
            lambda color: self._on_color_changed("notification_info_color", color)
        )
        self.warning_color.color_changed.connect(
            lambda color: self._on_color_changed("notification_warning_color", color)
        )
        self.error_color.color_changed.connect(
            lambda color: self._on_color_changed("notification_error_color", color)
        )
        
        # 添加标签和颜色选择器到网格
        layout.addWidget(theme_label, 0, 0)
        layout.addWidget(self.theme_combo, 0, 1)
        layout.addWidget(QLabel("背景颜色:"), 1, 0)
        layout.addWidget(self.background_color, 1, 1)
        layout.addWidget(QLabel("高亮按钮颜色:"), 2, 0)
        layout.addWidget(self.highlight_button_color, 2, 1)
        layout.addWidget(QLabel("信息通知颜色:"), 3, 0)
        layout.addWidget(self.info_color, 3, 1)
        layout.addWidget(QLabel("警告通知颜色:"), 4, 0)
        layout.addWidget(self.warning_color, 4, 1)
        layout.addWidget(QLabel("错误通知颜色:"), 5, 0)
        layout.addWidget(self.error_color, 5, 1)
        
        # 设置列拉伸
        layout.setColumnStretch(1, 1)
        
        self.setLayout(layout)
    
    def _apply_card_style(self):
        """应用卡片样式"""
        self.setStyleSheet(CustomConfig.CARD_STYLE)
        self.setContentsMargins(CustomConfig.SPACING_SYSTEM['lg'], 
                              CustomConfig.SPACING_SYSTEM['lg'],
                              CustomConfig.SPACING_SYSTEM['lg'], 
                              CustomConfig.SPACING_SYSTEM['lg'])
    
    def _on_theme_changed(self, theme_name: str):
        """主题预设改变事件"""
        if theme_name and theme_name != "自定义":
            # 获取主题颜色
            theme_colors = misc_func.CustomConfig.get_theme_colors(theme_name)
            
            # 应用主题颜色到颜色选择器
            self.background_color.set_color(theme_colors["background"])
            self.highlight_button_color.set_color(theme_colors["highlight_button"])
            self.info_color.set_color(theme_colors["notification_info"])
            self.warning_color.set_color(theme_colors["notification_warning"])
            self.error_color.set_color(theme_colors["notification_error"])
            
            # 保存到设置
            self.settings_manager.Custom.set_value("background_color", theme_colors["background"])
            self.settings_manager.Custom.set_value("highlight_button_color", theme_colors["highlight_button"])
            self.settings_manager.Custom.set_value("notification_info_color", theme_colors["notification_info"])
            self.settings_manager.Custom.set_value("notification_warning_color", theme_colors["notification_warning"])
            self.settings_manager.Custom.set_value("notification_error_color", theme_colors["notification_error"])
            
            # 保存当前主题名称，不切换到自定义
            self.settings_manager.Custom.set_value("current_theme", theme_name)
            
            # 立即应用主题到整个应用程序
            self._apply_theme_to_app(theme_colors)
    
    def _apply_theme_to_app(self, theme_colors: dict):
        """应用主题到整个应用程序"""
        try:
            # 获取主窗口实例
            main_window = self.window()
            if main_window and hasattr(main_window, 'tab_manager'):
                # 应用主题样式到主窗口
                self._apply_colors_to_main_window(main_window, theme_colors)
                
                # 刷新主窗口主题显示
                if hasattr(main_window, 'refresh_theme'):
                    main_window.refresh_theme()
                
                # 更新所有页面的样式
                if hasattr(main_window.tab_manager, 'tabs'):
                    for tab_name, tab_widget in main_window.tab_manager.tabs.items():
                        if hasattr(tab_widget, 'setStyleSheet'):
                            self._apply_theme_to_widget(tab_widget, theme_colors)
        except Exception as e:
            # 应用主题时出错，记录日志但不中断程序运行
            pass
    
    def _apply_colors_to_main_window(self, main_window, theme_colors: dict):
        """应用颜色到主窗口"""
        # 检查是否需要白色文字
        use_white_text = misc_func.CustomConfig.should_use_white_text(theme_colors["background"])
        text_color = "#FFFFFF" if use_white_text else "#333333"
        
        # 创建主窗口样式
        main_style = f"""
        QMainWindow {{
            background-color: {theme_colors["background"]};
            color: {text_color};
        }}
        
        QTabWidget::pane {{
            background-color: {theme_colors["background"]};
            border: 1px solid #CCCCCC;
        }}
        
        QTabBar::tab {{
            background-color: {theme_colors["background"]};
            color: {text_color};
            padding: 8px 16px;
            border: 1px solid #CCCCCC;
            margin-right: 2px;
        }}
        
        QTabBar::tab:selected {{
            background-color: {theme_colors["notification_info"]};
            border-bottom: 2px solid {theme_colors["notification_info"]};
        }}
        
        QTabBar::tab:hover {{
            background-color: {theme_colors["notification_info"]};
        }}
        """
        
        main_window.setStyleSheet(main_style)
    
    def _apply_theme_to_widget(self, widget, theme_colors: dict):
        """应用主题到具体控件"""
        # 检查是否需要白色文字
        use_white_text = misc_func.CustomConfig.should_use_white_text(theme_colors["background"])
        text_color = "#FFFFFF" if use_white_text else "#333333"
        
        # 基础样式
        widget_style = f"""
        QWidget {{
            background-color: {theme_colors["background"]};
            color: {text_color};
        }}
        
        QLabel {{
            color: {text_color};
        }}
        
        QGroupBox {{
            color: {text_color};
            border: 2px solid {theme_colors["notification_info"]};
            border-radius: 8px;
            margin-top: 8px;
            padding-top: 8px;
        }}
        
        QGroupBox::title {{
            color: {text_color};
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }}
        """
        
        widget.setStyleSheet(widget_style)
    
    def _on_color_changed(self, color_key: str, color: str):
        """颜色改变事件"""
        # 保存颜色设置
        self.settings_manager.Custom.set_value(color_key, color)
        
        # 当用户手动修改颜色时，切换到自定义主题
        self.theme_combo.blockSignals(True)  # 阻止信号避免循环
        self.theme_combo.setCurrentText("自定义")
        self.theme_combo.blockSignals(False)
        self.settings_manager.Custom.set_value("current_theme", "自定义")
    
    def _load_settings(self):
        """加载颜色设置"""
        # 背景颜色
        bg_color = self.settings_manager.Custom.get_value(
            "background_color", 
            CustomConfig.DEFAULT_COLORS["background"]
        )
        self.background_color.set_color(bg_color)
        
        # 高亮按钮颜色
        highlight_color = self.settings_manager.Custom.get_value(
            "highlight_button_color",
            "#4682B4"  # 默认钢蓝色
        )
        self.highlight_button_color.set_color(highlight_color)
        
        # 通知颜色
        info_color = self.settings_manager.Custom.get_value(
            "notification_info_color",
            CustomConfig.DEFAULT_COLORS["notification_info"]
        )
        self.info_color.set_color(info_color)
        
        warning_color = self.settings_manager.Custom.get_value(
            "notification_warning_color",
            CustomConfig.DEFAULT_COLORS["notification_warning"]
        )
        self.warning_color.set_color(warning_color)
        
        error_color = self.settings_manager.Custom.get_value(
            "notification_error_color",
            CustomConfig.DEFAULT_COLORS["notification_error"]
        )
        self.error_color.set_color(error_color)
        
        # 加载当前主题
        current_theme = self.settings_manager.Custom.get_value("current_theme", "自定义")
        
        # 设置当前主题（不触发信号）
        self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentText(current_theme)
        self.theme_combo.blockSignals(False)


class FontSettingsGroup(QGroupBox):
    """字体设置组 - 卡片式设计"""
    
    def __init__(self, parent=None):
        super().__init__("字体设置", parent)
        self.settings_manager = SettingsManager()
        self.wheel_filter = WheelEventFilter()
        self._init_ui()
        self._load_settings()
        self._apply_card_style()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QFormLayout()
        layout.setVerticalSpacing(CustomConfig.SPACING_SYSTEM['md'])  # 添加垂直间距
        
        # 标题标签
        font_label = QLabel("全局字体:")
        font_label.setStyleSheet("font-weight: bold; color: #333;")
        
        # 全局字体
        self.global_font = QFontComboBox()
        self.global_font.setFontFilters(QFontComboBox.ScalableFonts)  # 只显示可缩放字体
        self.global_font.setMinimumWidth(200)  # 设置最小宽度
        self.global_font.currentFontChanged.connect(
            lambda font: self.settings_manager.Custom.set_value("global_font", font.family())
        )
        self.global_font.setStyleSheet(CustomConfig.UNIFIED_STYLES['combo'])
        # 安装滚轮事件过滤器
        self.global_font.installEventFilter(self.wheel_filter)
        
        # 标题标签
        min_label = QLabel("最小字号:")
        min_label.setStyleSheet("font-weight: bold; color: #333;")
        
        # 最小字号
        self.min_font_size = QSpinBox()
        self.min_font_size.setRange(8, 50)
        self.min_font_size.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("min_font_size", str(value))
        )
        self.min_font_size.setStyleSheet(CustomConfig.UNIFIED_STYLES['input'])
        self.min_font_size.setSuffix(" pt")
        # 安装滚轮事件过滤器
        self.min_font_size.installEventFilter(self.wheel_filter)
        
        # 标题标签
        max_label = QLabel("最大字号:")
        max_label.setStyleSheet("font-weight: bold; color: #333;")
        
        # 最大字号
        self.max_font_size = QSpinBox()
        self.max_font_size.setRange(10, 100)
        self.max_font_size.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("max_font_size", str(value))
        )
        self.max_font_size.setStyleSheet(CustomConfig.UNIFIED_STYLES['input'])
        self.max_font_size.setSuffix(" pt")
        # 安装滚轮事件过滤器
        self.max_font_size.installEventFilter(self.wheel_filter)
        
        layout.addRow(font_label, self.global_font)
        layout.addRow(min_label, self.min_font_size)
        layout.addRow(max_label, self.max_font_size)
        
        self.setLayout(layout)
    
    def _apply_card_style(self):
        """应用卡片样式"""
        self.setStyleSheet(CustomConfig.CARD_STYLE)
        self.setContentsMargins(CustomConfig.SPACING_SYSTEM['lg'], 
                              CustomConfig.SPACING_SYSTEM['lg'],
                              CustomConfig.SPACING_SYSTEM['lg'], 
                              CustomConfig.SPACING_SYSTEM['lg'])
    
    def _load_settings(self):
        """加载设置"""
        # 全局字体
        global_font = self.settings_manager.Custom.get_value(
            "global_font",
            CustomConfig.DEFAULT_FONTS["global_font"]
        )
        # 在字体选择器中找到并设置当前字体
        font_db = QFontDatabase()
        available_families = font_db.families()
        if global_font in available_families:
            font = font_db.font(global_font, "", 12)
            self.global_font.setCurrentFont(font)
        
        # 最小字号
        min_size = int(self.settings_manager.Custom.get_value(
            "min_font_size",
            CustomConfig.DEFAULT_FONTS["min_font_size"]
        ))
        self.min_font_size.setValue(min_size)
        
        # 最大字号
        max_size = int(self.settings_manager.Custom.get_value(
            "max_font_size",
            CustomConfig.DEFAULT_FONTS["max_font_size"]
        ))
        self.max_font_size.setValue(max_size)
    
    def _filter_chinese_fonts(self):
        """过滤并只显示支持中文的字体"""
        # 常见的中文字体列表
        chinese_fonts = [
            "微软雅黑", "Microsoft YaHei",
            "宋体", "SimSun",
            "黑体", "SimHei", 
            "楷体", "KaiTi",
            "仿宋", "FangSong",
            "新宋体", "NSimSun",
            "华文宋体", "STSong",
            "华文黑体", "STHeiti",
            "华文楷体", "STKaiti",
            "华文仿宋", "STFangsong",
            "Arial Unicode MS",
            "Lucida Sans Unicode"
        ]
        
        # 获取字体数据库
        font_db = QFontDatabase()
        available_families = font_db.families()
        
        # 创建支持中文的字体列表
        supported_chinese_fonts = []
        for font_name in chinese_fonts:
            if font_name in available_families:
                supported_chinese_fonts.append(font_name)
        
        # 如果没有找到中文字体，保留所有字体
        if not supported_chinese_fonts:
            return
            
        # 清空当前字体列表
        self.global_font.clear()
        
        # 只添加支持中文的字体
        for font_name in supported_chinese_fonts:
            self.global_font.addItem(font_name)
    



class IndicatorSettingsGroup(QGroupBox):
    """指示器设置组 - 卡片式设计"""
    
    def __init__(self, parent=None):
        super().__init__("指示器设置", parent)
        self.settings_manager = SettingsManager()
        self.wheel_filter = WheelEventFilter()
        self._init_ui()
        self._load_settings()
        self._apply_card_style()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QFormLayout()
        layout.setVerticalSpacing(CustomConfig.SPACING_SYSTEM['md'])
        
        # X轴偏移设置
        
        # X轴偏移设置
        self.x_offset = QSpinBox()
        self.x_offset.setRange(-50, 50)
        self.x_offset.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("indicator_x_offset", str(value))
        )
        self.x_offset.setStyleSheet(CustomConfig.UNIFIED_STYLES['input'])
        # 安装滚轮事件过滤器
        self.x_offset.installEventFilter(self.wheel_filter)
        
        # Y轴偏移设置
        self.y_offset = QSpinBox()
        self.y_offset.setRange(-50, 50)
        self.y_offset.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("indicator_y_offset", str(value))
        )
        self.y_offset.setStyleSheet(CustomConfig.UNIFIED_STYLES['input'])
        # 安装滚轮事件过滤器
        self.y_offset.installEventFilter(self.wheel_filter)
        
        # 宽度调整设置
        self.width_adjust = QSpinBox()
        self.width_adjust.setRange(-100, 100)
        self.width_adjust.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("indicator_width_adjust", str(value))
        )
        self.width_adjust.setStyleSheet(CustomConfig.UNIFIED_STYLES['input'])
        # 安装滚轮事件过滤器
        self.width_adjust.installEventFilter(self.wheel_filter)
        
        # 高度调整设置
        self.height_adjust = QSpinBox()
        self.height_adjust.setRange(-100, 100)
        self.height_adjust.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("indicator_height_adjust", str(value))
        )
        self.height_adjust.setStyleSheet(CustomConfig.UNIFIED_STYLES['input'])
        # 安装滚轮事件过滤器
        self.height_adjust.installEventFilter(self.wheel_filter)
        
        # 添加到布局
        layout.addRow("X轴偏移(px):", self.x_offset)
        layout.addRow("Y轴偏移(px):", self.y_offset)
        layout.addRow("宽度调整(px):", self.width_adjust)
        layout.addRow("高度调整(px):", self.height_adjust)
        
        self.setLayout(layout)
    
    def _apply_card_style(self):
        """应用卡片样式"""
        self.setStyleSheet(CustomConfig.CARD_STYLE)
        self.setContentsMargins(CustomConfig.SPACING_SYSTEM['lg'], 
                              CustomConfig.SPACING_SYSTEM['lg'],
                              CustomConfig.SPACING_SYSTEM['lg'], 
                              CustomConfig.SPACING_SYSTEM['lg'])
    
    def _load_settings(self):
        """加载设置"""
        # X轴偏移设置
        self.x_offset.setValue(int(self.settings_manager.Custom.get_value(
            "indicator_x_offset",
            "0"  # 默认值
        )))
        
        # Y轴偏移设置
        self.y_offset.setValue(int(self.settings_manager.Custom.get_value(
            "indicator_y_offset",
            "0"  # 默认值
        )))
        
        # 宽度调整设置
        self.width_adjust.setValue(int(self.settings_manager.Custom.get_value(
            "indicator_width_adjust",
            "0"  # 默认值
        )))
        
        # 高度调整设置
        self.height_adjust.setValue(int(self.settings_manager.Custom.get_value(
            "indicator_height_adjust",
            "0"  # 默认值
        )))

    def _apply_card_style(self):
        """应用卡片样式"""
        self.setStyleSheet(CustomConfig.CARD_STYLE)
        self.setContentsMargins(CustomConfig.SPACING_SYSTEM['lg'], 
                              CustomConfig.SPACING_SYSTEM['lg'],
                              CustomConfig.SPACING_SYSTEM['lg'], 
                              CustomConfig.SPACING_SYSTEM['lg'])


class AnimationSettingsGroup(QGroupBox):
    """动画设置组 - 卡片式设计"""
    
    def __init__(self, parent=None):
        super().__init__("动画设置", parent)
        self.settings_manager = SettingsManager()
        self.wheel_filter = WheelEventFilter()
        self._init_ui()
        self._load_settings()
        self._apply_card_style()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QFormLayout()
        layout.setVerticalSpacing(CustomConfig.SPACING_SYSTEM['md'])
        
        # 换页动画速度设置（移除时长限制）
        self.tab_switch_speed = QSpinBox()
        self.tab_switch_speed.setRange(1, 10000)  # 1ms到10000ms，更宽的范围
        self.tab_switch_speed.setSuffix(" ms")
        self.tab_switch_speed.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("tab_switch_speed", str(value))
        )
        self.tab_switch_speed.setStyleSheet(CustomConfig.UNIFIED_STYLES['input'])
        # 安装滚轮事件过滤器
        self.tab_switch_speed.installEventFilter(self.wheel_filter)
        
        # 消息框动画速度设置（移除时长限制）
        self.animation_appear = QSpinBox()
        self.animation_appear.setRange(1, 10000)  # 1ms到10000ms，更宽的范围
        self.animation_appear.setSuffix(" ms")
        self.animation_appear.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("animation_appear", str(value))
        )
        self.animation_appear.setStyleSheet(CustomConfig.UNIFIED_STYLES['input'])
        # 安装滚轮事件过滤器
        self.animation_appear.installEventFilter(self.wheel_filter)
        
        self.animation_disappear = QSpinBox()
        self.animation_disappear.setRange(1, 10000)  # 1ms到10000ms，更宽的范围
        self.animation_disappear.setSuffix(" ms")
        self.animation_disappear.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("animation_disappear", str(value))
        )
        self.animation_disappear.setStyleSheet(CustomConfig.UNIFIED_STYLES['input'])
        # 安装滚轮事件过滤器
        self.animation_disappear.installEventFilter(self.wheel_filter)
        
        self.animation_move = QSpinBox()
        self.animation_move.setRange(1, 10000)  # 1ms到10000ms，更宽的范围
        self.animation_move.setSuffix(" ms")
        self.animation_move.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("animation_move", str(value))
        )
        self.animation_move.setStyleSheet(CustomConfig.UNIFIED_STYLES['input'])
        # 安装滚轮事件过滤器
        self.animation_move.installEventFilter(self.wheel_filter)
        
        # 指示器动画速度设置（改为毫秒单位）
        self.indicator_animation_speed = QSpinBox()
        self.indicator_animation_speed.setRange(1,10000)  # 10ms到2000ms，无限制范围
        self.indicator_animation_speed.setSuffix(" ms")
        self.indicator_animation_speed.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("indicator_animation_speed", str(value))
        )
        self.indicator_animation_speed.setStyleSheet(CustomConfig.UNIFIED_STYLES['input'])
        # 安装滚轮事件过滤器
        self.indicator_animation_speed.installEventFilter(self.wheel_filter)
        
        # 添加到布局
        layout.addRow("换页动画速度:", self.tab_switch_speed)
        layout.addRow("消息框出现动画:", self.animation_appear)
        layout.addRow("消息框消失动画:", self.animation_disappear)
        layout.addRow("消息框移动动画:", self.animation_move)
        layout.addRow("指示器动画速度:", self.indicator_animation_speed)
        
        self.setLayout(layout)
    
    def _apply_card_style(self):
        """应用卡片样式"""
        self.setStyleSheet(CustomConfig.CARD_STYLE)
        self.setContentsMargins(CustomConfig.SPACING_SYSTEM['lg'], 
                              CustomConfig.SPACING_SYSTEM['lg'],
                              CustomConfig.SPACING_SYSTEM['lg'], 
                              CustomConfig.SPACING_SYSTEM['lg'])
    
    def _load_settings(self):
        """加载设置"""
        # 换页动画速度
        self.tab_switch_speed.setValue(int(self.settings_manager.Custom.get_value(
            "tab_switch_speed",
            "300"  # 默认300ms
        )))
        
        # 消息框动画设置
        self.animation_appear.setValue(int(self.settings_manager.Custom.get_value(
            "animation_appear",
            CustomConfig.DEFAULT_NOTIFICATIONS["animation_appear"]
        )))
        
        self.animation_disappear.setValue(int(self.settings_manager.Custom.get_value(
            "animation_disappear",
            CustomConfig.DEFAULT_NOTIFICATIONS["animation_disappear"]
        )))
        
        self.animation_move.setValue(int(self.settings_manager.Custom.get_value(
            "animation_move",
            CustomConfig.DEFAULT_NOTIFICATIONS["animation_move"]
        )))
        
        # 指示器动画速度设置（改为毫秒单位）
        try:
            # 尝试读取旧格式的小数值并转换为毫秒
            old_value = self.settings_manager.Custom.get_value("indicator_animation_speed", "50")
            if "." in old_value:
                # 如果是小数值（旧格式），转换为毫秒
                ms_value = int(float(old_value) * 1000)
            else:
                # 如果是整数值（新格式），直接使用
                ms_value = int(old_value)
            self.indicator_animation_speed.setValue(ms_value)
        except (ValueError, TypeError):
            # 如果转换失败，使用默认值
            self.indicator_animation_speed.setValue(50)


class NotificationSettingsGroup(QGroupBox):
    """通知设置组 - 卡片式设计"""
    
    def __init__(self, parent=None):
        super().__init__("通知设置", parent)
        self.settings_manager = SettingsManager()
        self.wheel_filter = WheelEventFilter()
        self._init_ui()
        self._load_settings()
        self._apply_card_style()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QFormLayout()
        layout.setVerticalSpacing(CustomConfig.SPACING_SYSTEM['md'])
        
        # 位置设置 - 应用设置界面样式
        self.position_m = QSpinBox()
        self.position_m.setRange(0, 16)
        self.position_m.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("position_m", str(value))
        )
        self.position_m.setStyleSheet(CustomConfig.UNIFIED_STYLES['input'])
        # 安装滚轮事件过滤器
        self.position_m.installEventFilter(self.wheel_filter)
        
        # 修改为 QDoubleSpinBox
        self.position_n = QDoubleSpinBox()
        self.position_n.setRange(0, 16)
        self.position_n.setSingleStep(0.25)
        self.position_n.setDecimals(2)  # 设置小数点位数
        self.position_n.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("position_n", str(value))
        )
        self.position_n.setStyleSheet(CustomConfig.UNIFIED_STYLES['input'])
        # 安装滚轮事件过滤器
        self.position_n.installEventFilter(self.wheel_filter)
        
        # 尺寸比例 - 修改为 QDoubleSpinBox
        self.width_ratio = QDoubleSpinBox()
        self.width_ratio.setRange(0.1, 5.0)
        self.width_ratio.setSingleStep(0.1)
        self.width_ratio.setDecimals(2)
        self.width_ratio.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("width_ratio", str(value))
        )
        self.width_ratio.setStyleSheet(CustomConfig.UNIFIED_STYLES['input'])
        # 安装滚轮事件过滤器
        self.width_ratio.installEventFilter(self.wheel_filter)
        
        self.height_ratio = QDoubleSpinBox()
        self.height_ratio.setRange(0.1, 5.0)
        self.height_ratio.setSingleStep(0.1)
        self.height_ratio.setDecimals(2)
        self.height_ratio.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("height_ratio", str(value))
        )
        self.height_ratio.setStyleSheet(CustomConfig.UNIFIED_STYLES['input'])
        # 安装滚轮事件过滤器
        self.height_ratio.installEventFilter(self.wheel_filter)
        
        # 其他设置
        self.max_visible = QSpinBox()
        self.max_visible.setRange(1, 20)
        self.max_visible.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("max_visible", str(value))
        )
        self.max_visible.setStyleSheet(CustomConfig.UNIFIED_STYLES['input'])
        # 安装滚轮事件过滤器
        self.max_visible.installEventFilter(self.wheel_filter)
        
        self.offset_n = QSpinBox()
        self.offset_n.setRange(1, 10)
        self.offset_n.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("offset_n", str(value))
        )
        self.offset_n.setStyleSheet(CustomConfig.UNIFIED_STYLES['input'])
        # 安装滚轮事件过滤器
        self.offset_n.installEventFilter(self.wheel_filter)
        
        # 修改为 QDoubleSpinBox
        self.spacing_n = QDoubleSpinBox()
        self.spacing_n.setRange(0.1, 5.0)
        self.spacing_n.setSingleStep(0.1)
        self.spacing_n.setDecimals(2)
        self.spacing_n.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("spacing_n", str(value))
        )
        self.spacing_n.setStyleSheet(CustomConfig.UNIFIED_STYLES['input'])
        # 安装滚轮事件过滤器
        self.spacing_n.installEventFilter(self.wheel_filter)
        
        self.auto_close_time = QSpinBox()
        self.auto_close_time.setRange(1000, 30000)
        self.auto_close_time.setSingleStep(500)
        self.auto_close_time.setSuffix(" ms")
        self.auto_close_time.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("auto_close_time", str(value))
        )
        self.auto_close_time.setStyleSheet(CustomConfig.UNIFIED_STYLES['input'])
        # 安装滚轮事件过滤器
        self.auto_close_time.installEventFilter(self.wheel_filter)
        
        # 添加到布局
        layout.addRow("位置 M 坐标:", self.position_m)
        layout.addRow("位置 N 坐标:", self.position_n)
        layout.addRow("宽度比例:", self.width_ratio)
        layout.addRow("高度比例:", self.height_ratio)
        layout.addRow("最大可见数:", self.max_visible)
        layout.addRow("偏移量 N:", self.offset_n)
        layout.addRow("间距 N:", self.spacing_n)
        layout.addRow("自动关闭时间:", self.auto_close_time)
        
        self.setLayout(layout)
    
    def _apply_card_style(self):
        """应用卡片样式"""
        self.setStyleSheet(CustomConfig.CARD_STYLE)
        self.setContentsMargins(CustomConfig.SPACING_SYSTEM['lg'], 
                              CustomConfig.SPACING_SYSTEM['lg'],
                              CustomConfig.SPACING_SYSTEM['lg'], 
                              CustomConfig.SPACING_SYSTEM['lg'])
    
    def _load_settings(self):
        """加载设置"""
        # 位置设置
        self.position_m.setValue(int(self.settings_manager.Custom.get_value(
            "position_m",
            CustomConfig.DEFAULT_NOTIFICATIONS["position_m"]
        )))
        
        self.position_n.setValue(float(self.settings_manager.Custom.get_value(
            "position_n",
            CustomConfig.DEFAULT_NOTIFICATIONS["position_n"]
        )))
        
        # 尺寸比例
        self.width_ratio.setValue(float(self.settings_manager.Custom.get_value(
            "width_ratio",
            CustomConfig.DEFAULT_NOTIFICATIONS["width_ratio"]
        )))
        
        self.height_ratio.setValue(float(self.settings_manager.Custom.get_value(
            "height_ratio",
            CustomConfig.DEFAULT_NOTIFICATIONS["height_ratio"]
        )))
        
        # 其他设置
        self.max_visible.setValue(int(self.settings_manager.Custom.get_value(
            "max_visible",
            CustomConfig.DEFAULT_NOTIFICATIONS["max_visible"]
        )))
        
        self.offset_n.setValue(int(self.settings_manager.Custom.get_value(
            "offset_n",
            CustomConfig.DEFAULT_NOTIFICATIONS["offset_n"]
        )))
        
        self.spacing_n.setValue(float(self.settings_manager.Custom.get_value(
            "spacing_n",
            CustomConfig.DEFAULT_NOTIFICATIONS["spacing_n"]
        )))
        
        self.auto_close_time.setValue(int(self.settings_manager.Custom.get_value(
            "auto_close_time",
            CustomConfig.DEFAULT_NOTIFICATIONS["auto_close_time"]
        )))
    



class CustomPage(QWidget):
    """个性化设置页面"""
    
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
    
    def _init_ui(self):
        """初始化UI"""
        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 添加m、n定义提示
        self.hint_label = QLabel(
            "提示：\n"
            "①在通知设置中，m和n是相对单位。m = 窗口宽度/16，n = 窗口高度/16。\n"
            "例如，位置 M=12 表示距离窗口左侧 12*m 像素，位置 N=12.25 表示距离窗口顶部 12.25*n 像素。\n"
            "②\"全局字体\"、\"全局最小/最大字号\"不适用于消息提示框。\n"
            "③键盘控制方案仅在音频播放时生效，不影响鼠标操作。"
        )
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet("""
            QLabel {
                background-color: #f8f8f8;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 8px;
                color: #666;
            }
        """)
        main_layout.addWidget(self.hint_label)
        
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
        self.content_layout.setSpacing(15)  # 增加组件间距
        
        # 键盘控制方案设置（新增）
        self.keyboard_group = KeyboardControlGroup(self)
        self.content_layout.addWidget(self.keyboard_group)
        
        # 窗口尺寸设置
        self.window_size_group = WindowSizeGroup(self)
        self.content_layout.addWidget(self.window_size_group)
        
        # 颜色设置
        self.color_group = ColorSettingsGroup(self)
        self.content_layout.addWidget(self.color_group)
        
        # 字体设置
        self.font_group = FontSettingsGroup(self)
        self.content_layout.addWidget(self.font_group)
        
        # 指示器设置
        self.indicator_group = IndicatorSettingsGroup(self)
        self.content_layout.addWidget(self.indicator_group)
        
        # 动画设置
        self.animation_group = AnimationSettingsGroup(self)
        self.content_layout.addWidget(self.animation_group)
        
        # 通知设置
        self.notification_group = NotificationSettingsGroup(self)
        self.content_layout.addWidget(self.notification_group)
        
        # 添加拉伸，使内容顶部对齐
        self.content_layout.addStretch(1)
        
        # 设置滚动区域的内容部件
        self.scroll_area.setWidget(self.content_widget)
        
        # 操作按钮
        button_layout = QHBoxLayout()
        
        self.reset_button = QPushButton("重置为默认")
        self.reset_button.clicked.connect(self._reset_to_defaults)
        self.reset_button.setStyleSheet(self._get_button_style())
        
        self.apply_button = QPushButton("应用设置")
        self.apply_button.clicked.connect(self._apply_settings)
        self.apply_button.setStyleSheet(self._get_button_style())
        
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()
        button_layout.addWidget(self.apply_button)
        
        # 将滚动区域和按钮添加到主布局
        main_layout.addWidget(self.scroll_area, 1)  # 1表示滚动区域可以拉伸
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
        
        # 初始字体更新
        self._update_fonts()
        
        # 启动时自动应用设置（不弹窗）
        self._apply_settings_silently()
    
    def resizeEvent(self, event):
        """处理窗口大小变化事件"""
        self._update_fonts()
        super().resizeEvent(event)
    
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
        
        # 应用字体到所有控件（除了全局字体输入框）
        self._apply_fonts_to_widgets(other_font, small_font)
        
        # 更新按钮样式（因为字体可能改变）
        self.reset_button.setStyleSheet(self._get_button_style())
        self.apply_button.setStyleSheet(self._get_button_style())
    
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
        
        # 更新所有卡片组的样式
        dynamic_style = CustomConfig.get_dynamic_card_style(title_font_size)
        
        # 应用到各个设置组
        self.keyboard_group.setStyleSheet(dynamic_style)
        self.window_size_group.setStyleSheet(dynamic_style)
        self.color_group.setStyleSheet(dynamic_style)
        self.font_group.setStyleSheet(dynamic_style)
        self.indicator_group.setStyleSheet(dynamic_style)
        self.animation_group.setStyleSheet(dynamic_style)
        self.notification_group.setStyleSheet(dynamic_style)
    
    def _apply_fonts_to_widgets(self, font, small_font):
        """应用字体到所有控件"""
        # 应用字体到提示标签
        self.hint_label.setFont(small_font)
        
        # 应用字体到键盘控制组
        self.keyboard_group.setFont(font)
        self.keyboard_group.scheme_combo.setFont(font)
        self.keyboard_group.scheme_description.setFont(small_font)
        
        # 应用字体到窗口尺寸组
        self.window_size_group.setFont(font)
        self.window_size_group.size_combo.setFont(font)
        
        # 应用字体到颜色设置组
        self.color_group.setFont(font)
        for color_picker in [self.color_group.background_color, 
                            self.color_group.info_color,
                            self.color_group.warning_color,
                            self.color_group.error_color]:
            color_picker.color_input.setFont(font)
        
        # 应用字体到字体设置组（注意：全局字体输入框不应用字体）
        self.font_group.setFont(font)
        self.font_group.min_font_size.setFont(font)
        self.font_group.max_font_size.setFont(font)
        
        # 应用字体到指示器设置组
        self.indicator_group.setFont(font)
        for widget in [self.indicator_group.x_offset,
                      self.indicator_group.y_offset,
                      self.indicator_group.width_adjust,
                      self.indicator_group.height_adjust]:
            widget.setFont(font)
        
        # 应用字体到动画设置组
        self.animation_group.setFont(font)
        for widget in [self.animation_group.tab_switch_speed,
                      self.animation_group.animation_appear,
                      self.animation_group.animation_disappear,
                      self.animation_group.animation_move]:
            widget.setFont(font)
        
        # 应用字体到通知设置组
        self.notification_group.setFont(font)
        for widget in [self.notification_group.position_m,
                      self.notification_group.position_n,
                      self.notification_group.width_ratio,
                      self.notification_group.height_ratio,
                      self.notification_group.max_visible,
                      self.notification_group.offset_n,
                      self.notification_group.spacing_n,
                      self.notification_group.auto_close_time]:
            widget.setFont(font)
        
        # 应用字体到按钮
        self.reset_button.setFont(font)
        self.apply_button.setFont(font)
        
        # 应用字体到所有表单标签
        self._apply_font_to_form_labels(font)
        
        # 应用字体到所有输入框和选择框
        self._apply_font_to_inputs_and_combos(font)
    
    def _apply_font_to_form_labels(self, font):
        """应用字体到所有表单标签（左侧标题）"""
        # 递归函数，遍历所有子控件
        def apply_font_recursive(widget):
            if isinstance(widget, QLabel):
                # 检查是否是表单标签（通常表单标签有特定的文本内容）
                # 这里我们简单地假设所有QLabel都是表单标签
                widget.setFont(font)
            
            # 递归遍历所有子控件
            for child in widget.children():
                if isinstance(child, QWidget):
                    apply_font_recursive(child)
        
        # 从内容部件开始递归应用字体
        apply_font_recursive(self.content_widget)
    
    def _apply_font_to_inputs_and_combos(self, font):
        """应用字体到所有输入框和选择框"""
        # 递归函数，遍历所有子控件
        def apply_font_recursive(widget):
            # 应用字体到输入框
            if isinstance(widget, (QLineEdit, QSpinBox, QDoubleSpinBox)):
                widget.setFont(font)
            # 应用字体到选择框
            elif isinstance(widget, QComboBox):
                widget.setFont(font)
            
            # 递归遍历所有子控件
            for child in widget.children():
                if isinstance(child, QWidget):
                    apply_font_recursive(child)
        
        # 从内容部件开始递归应用字体
        apply_font_recursive(self.content_widget)
    
    def _reset_to_defaults(self):
        """重置为默认设置"""
        reply = QMessageBox.question(
            self, 
            "确认重置",
            "确定要重置所有个性化设置为默认值吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 重置键盘控制方案
            self.settings_manager.Custom.set_value("keyboard_scheme", "1")
            
            # 重置窗口尺寸
            self.settings_manager.Custom.set_value("window_size", "1024x768")
            
            # 重置颜色
            for key, value in CustomConfig.DEFAULT_COLORS.items():
                self.settings_manager.Custom.set_value(f"{key}_color", value)
            # 重置高亮按钮颜色
            self.settings_manager.Custom.set_value("highlight_button_color", "#4682B4")
            
            # 重置字体
            for key, value in CustomConfig.DEFAULT_FONTS.items():
                self.settings_manager.Custom.set_value(key, value)
            
            # 重置通知
            for key, value in CustomConfig.DEFAULT_NOTIFICATIONS.items():
                self.settings_manager.Custom.set_value(key, value)
            
            # 重置指示器设置
            self.settings_manager.Custom.set_value("indicator_animation_speed", "0.1")
            self.settings_manager.Custom.set_value("indicator_x_offset", "0")
            self.settings_manager.Custom.set_value("indicator_y_offset", "0")
            self.settings_manager.Custom.set_value("indicator_width_adjust", "0")
            self.settings_manager.Custom.set_value("indicator_height_adjust", "0")
            
            # 重新加载设置
            self.keyboard_group._load_settings()
            self.window_size_group._load_settings()
            self.color_group._load_settings()
            self.font_group._load_settings()
            self.notification_group._load_settings()
            
            # 更新字体
            self._update_fonts()
            
            QMessageBox.information(self, "重置成功", "个性化设置已重置为默认值")
    
    def _apply_settings(self):
        """应用设置"""
        self._apply_settings_silently()
        QMessageBox.information(self, "应用成功", "个性化设置已应用，部分设置需要重启程序才能生效")
    
    def _apply_settings_silently(self):
        """静默应用设置（不弹窗）"""
        # 获取共享内存管理器
        shared_manager = get_shared_memory_manager()
        
        # 应用窗口尺寸
        window_size = self.settings_manager.Custom.get_value("window_size", "1024x768")
        if self.parent_window:
            width, height = map(int, window_size.split('x'))
            self.parent_window.resize(width, height)
            # 广播窗口尺寸更改
            shared_manager.broadcast_window_size_change(width, height)
        
        # 应用背景颜色
        bg_color = self.settings_manager.Custom.get_value(
            "background_color", 
            CustomConfig.DEFAULT_COLORS["background"]
        )
        if self.parent_window:
            self.parent_window.setStyleSheet(f"background-color: {bg_color};")
            # 重新计算并刷新选项卡栏背景颜色
            self.parent_window._calculate_tab_bar_background_color(bg_color)
            # 触发重绘以更新选项卡栏背景和高亮按钮
            self.parent_window.update()
            
            # 刷新生成选项卡
            if hasattr(self.parent_window, 'generation_page') and self.parent_window.generation_page:
                self.parent_window.generation_page._update_fonts()
                self.parent_window.generation_page._check_inputs_and_update_button()
        
        # 应用个性化页面自身的背景颜色
        self.setStyleSheet(f"background-color: {bg_color};")
        
        # 更新字体
        self._update_fonts()
        
        # 广播设置更改
        settings_data = {
            'window_size': window_size,
            'background_color': bg_color,
            'global_font': self.settings_manager.Custom.get_value("global_font", "微软雅黑"),
            'min_font_size': self.settings_manager.Custom.get_value("min_font_size", "22"),
            'max_font_size': self.settings_manager.Custom.get_value("max_font_size", "42"),
            'keyboard_scheme': self.settings_manager.Custom.get_value("keyboard_scheme", "1"),
            'notification_colors': {
                'info': self.settings_manager.Custom.get_value("info_color", CustomConfig.DEFAULT_COLORS["notification_info"]),
                'warning': self.settings_manager.Custom.get_value("warning_color", CustomConfig.DEFAULT_COLORS["notification_warning"]),
                'error': self.settings_manager.Custom.get_value("error_color", CustomConfig.DEFAULT_COLORS["notification_error"])
            },
            'notification_settings': {
                'animation_appear': self.settings_manager.Custom.get_value("animation_appear", "400"),
                'animation_disappear': self.settings_manager.Custom.get_value("animation_disappear", "400"),
                'animation_move': self.settings_manager.Custom.get_value("animation_move", "500"),
                'position_m': self.settings_manager.Custom.get_value("position_m", "12"),
                'position_n': self.settings_manager.Custom.get_value("position_n", "12.25"),
                'width_ratio': self.settings_manager.Custom.get_value("width_ratio", "1"),
                'height_ratio': self.settings_manager.Custom.get_value("height_ratio", "0.5"),
                'max_visible': self.settings_manager.Custom.get_value("max_visible", "5"),
                'offset_n': self.settings_manager.Custom.get_value("offset_n", "1"),
                'spacing_n': self.settings_manager.Custom.get_value("spacing_n", "1.25"),
                'auto_close_time': self.settings_manager.Custom.get_value("auto_close_time", "3000")
            }
        }
        
        # 广播字体更改
        font_data = {
            'global_font': settings_data['global_font'],
            'min_font_size': settings_data['min_font_size'],
            'max_font_size': settings_data['max_font_size']
        }
        shared_manager.broadcast_font_change(font_data)
        
        # 广播主题更改
        theme_data = {
            'background_color': bg_color,
            'notification_colors': settings_data['notification_colors']
        }
        shared_manager.broadcast_theme_change(theme_data)
        
        # 广播总体设置更改
        shared_manager.broadcast_settings_change('custom_page', settings_data)
        
        # 强制重新加载当前页面以应用新设置
        self._reload_page()
    
    def _reload_page(self):
        """重新加载页面以应用最新设置"""
        try:
            # 重新加载所有设置
            self.keyboard_group._load_settings()
            self.window_size_group._load_settings()
            self.color_group._load_settings()
            self.font_group._load_settings()
            self.notification_group._load_settings()
            
            # 更新UI显示
            self._update_fonts()
            
            # 重新加载完成，可根据需要添加日志记录
            pass
        except Exception as e:
            # 重新加载失败，可根据需要添加日志记录
            pass
    
    def _get_button_style(self):
        """获取按钮样式 - 使用用户设置的字体"""
        # 获取用户设置的字体
        global_font_name = self.settings_manager.Custom.get_value("global_font", "微软雅黑")
        return f"""
            QPushButton {{
                font-family: "{global_font_name}"; background-color: white; color: black;
                border: 2px solid gray; border-radius: 5px; font-weight: bold;
                padding: 8px 16px;
            }}
            QPushButton:hover {{ background-color: #f0f0f0; }}
        """
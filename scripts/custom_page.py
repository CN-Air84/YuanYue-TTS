import os
import re
from typing import Dict, Any, List
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QLineEdit, QPushButton, QColorDialog, QGroupBox, QFormLayout,
    QSpinBox, QMessageBox, QDoubleSpinBox, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QEvent
from PyQt5.QtGui import QFont, QColor, QPalette

from misc_func import SettingsManager
from audio_preview import KeyboardControlScheme

'''
本段代码在SimeonTest Re1时使用 DeepSeek 重构，
感谢小鲸鱼把我写的“狗皮膏药”改成了虎皮膏药。

This code was refactored during SimeonTest RE1 using DeepSeek. 
thanks to DS for changing my “Dog-skin plaster” to tiger-skin plaster.
(it's just a figure of speech.)
'''

class CustomConfig:
    """个性化配置常量"""
    
    # 预设窗口尺寸选项
    WINDOW_SIZES = [
    "1024x600",
    "1024x768",
    "1280x720",
    "1280x768",
    "1280x800",
    "1280x960",
    "1280x1024",
    "1400x1050",
    "1440x900",
    "1600x1024",
    "1600x1050",
    "1600x1200",
    "1680x1050",
    "1900x1200",
    "1920x1080",
    "1920x1200",
    "2048x1536",
    "2560x1600",
    "2560x2048",
    "3200x2400",
    "3840x2400"
    ]
    
    # 键盘控制方案选项
    KEYBOARD_SCHEMES = KeyboardControlScheme.get_all_schemes()
    
    # 默认颜色配置
    DEFAULT_COLORS = {
        "background": "#69E0A5",
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


class WheelEventFilter(QObject):
    """鼠标滚轮事件过滤器 - 禁止通过滚轮改变数值"""
    
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel:
            # 阻止滚轮事件
            return True
        return False


class ColorPickerWidget(QWidget):
    """颜色选择器组件"""
    
    color_changed = pyqtSignal(str)
    
    def __init__(self, initial_color: str = "#000000", parent=None):
        super().__init__(parent)
        self.color_value = initial_color
        self.wheel_filter = WheelEventFilter()
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 颜色显示框
        self.color_display = QLabel()
        self.color_display.setFixedSize(30, 30)
        self.color_display.setStyleSheet(f"background-color: {self.color_value}; border: 2px solid gray; border-radius: 5px;")
        self.color_display.mousePressEvent = self._show_color_dialog
        
        # 颜色输入框 - 应用设置界面样式
        self.color_input = QLineEdit(self.color_value)
        self.color_input.setFixedWidth(80)
        self.color_input.textChanged.connect(self._on_text_changed)
        self.color_input.setStyleSheet(self._get_input_style())
        # 安装滚轮事件过滤器
        self.color_input.installEventFilter(self.wheel_filter)
        
        # 调色盘按钮 - 应用设置界面样式
        self.palette_button = QPushButton("调色盘")
        self.palette_button.clicked.connect(self._show_color_dialog)
        self.palette_button.setStyleSheet(self._get_button_style())
        
        layout.addWidget(self.color_display)
        layout.addWidget(self.color_input)
        layout.addWidget(self.palette_button)
        
        self.setLayout(layout)
    
    def _show_color_dialog(self, event=None):
        """显示颜色选择对话框"""
        color = QColorDialog.getColor(QColor(self.color_value), self, "选择颜色")
        if color.isValid():
            self.set_color(color.name())
    
    def _on_text_changed(self, text: str):
        """文本输入改变事件"""
        if self._is_valid_color(text):
            self.color_value = text
            self.color_display.setStyleSheet(f"background-color: {text}; border: 2px solid gray; border-radius: 5px;")
            self.color_changed.emit(text)
    
    def _is_valid_color(self, color_str: str) -> bool:
        """检查颜色字符串是否有效"""
        pattern = r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$'
        return re.match(pattern, color_str) is not None
    
    def set_color(self, color: str):
        """设置颜色"""
        if self._is_valid_color(color):
            self.color_value = color
            self.color_input.setText(color)
            self.color_display.setStyleSheet(f"background-color: {color}; border: 2px solid gray; border-radius: 5px;")
            self.color_changed.emit(color)
    
    def get_color(self) -> str:
        """获取颜色"""
        return self.color_value
    
    def _get_input_style(self):
        """获取输入框样式 - 与设置界面保持一致"""
        return "QLineEdit { background-color: white; color: black; border: 2px solid gray; border-radius: 10px; padding: 5px; }"
    
    def _get_button_style(self):
        """获取按钮样式 - 与设置界面保持一致"""
        return """
            QPushButton {
                font-family: "微软雅黑"; background-color: white; color: black;
                border: 2px solid gray; border-radius: 5px; font-weight: bold;
            }
            QPushButton:hover { background-color: #f0f0f0; }
        """


class KeyboardControlGroup(QGroupBox):
    """键盘控制设置组"""
    
    def __init__(self, parent=None):
        super().__init__("键盘控制方案", parent)
        self.settings_manager = SettingsManager()
        self.wheel_filter = WheelEventFilter()
        self._init_ui()
        self._load_settings()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        
        # 键盘控制方案选择 - 应用设置界面样式
        self.scheme_combo = QComboBox()
        schemes = KeyboardControlScheme.get_all_schemes()
        for scheme_id, scheme_name in schemes.items():
            self.scheme_combo.addItem(scheme_name, scheme_id)
        
        self.scheme_combo.currentIndexChanged.connect(self._on_scheme_changed)
        self.scheme_combo.setStyleSheet(self._get_combo_box_style())
        # 安装滚轮事件过滤器
        self.scheme_combo.installEventFilter(self.wheel_filter)
        
        # 方案说明标签
        self.scheme_description = QLabel()
        self.scheme_description.setWordWrap(True)
        self.scheme_description.setStyleSheet("color: #666666; font-size: 12px; margin-top: 5px;")
        
        layout.addWidget(QLabel("选择键盘控制方案:   （注：需要重启软件）"))
        layout.addWidget(self.scheme_combo)
        layout.addWidget(self.scheme_description)
        
        self.setLayout(layout)
        
        # 更新初始方案说明
        self._update_scheme_description()
    
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
        """获取下拉框样式 - 与设置界面保持一致"""
        return """
            QComboBox {
                font-family: "微软雅黑"; background-color: white; color: black; 
                border: 2px solid gray; border-radius: 10px; padding: 5px;
            }
            QComboBox::drop-down {
                border-left-width: 2px; border-left-color: gray; border-left-style: solid;
                border-top-right-radius: 10px; border-bottom-right-radius: 10px;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid black;
                width: 0px;
                height: 0px;
            }
            QComboBox:hover {
                background-color: #f0f0f0;
            }
        """


class WindowSizeGroup(QGroupBox):
    """窗口尺寸设置组"""
    
    def __init__(self, parent=None):
        super().__init__("窗口尺寸设置", parent)
        self.settings_manager = SettingsManager()
        self.wheel_filter = WheelEventFilter()
        self._init_ui()
        self._load_settings()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QFormLayout()
        
        # 窗口尺寸选择 - 应用设置界面样式
        self.size_combo = QComboBox()
        self.size_combo.addItems(CustomConfig.WINDOW_SIZES)
        self.size_combo.currentTextChanged.connect(self._on_size_changed)
        self.size_combo.setStyleSheet(self._get_combo_box_style())
        # 安装滚轮事件过滤器
        self.size_combo.installEventFilter(self.wheel_filter)
        
        layout.addRow("预设窗口尺寸:", self.size_combo)
        
        self.setLayout(layout)
    
    def _load_settings(self):
        """加载设置"""
        window_size = self.settings_manager.Custom.get_value("window_size", "1024x768")
        if window_size in CustomConfig.WINDOW_SIZES:
            self.size_combo.setCurrentText(window_size)
    
    def _on_size_changed(self, size: str):
        """窗口尺寸改变事件"""
        self.settings_manager.Custom.set_value("window_size", size)
    
    def _get_combo_box_style(self):
        """获取下拉框样式 - 与设置界面保持一致"""
        return """
            QComboBox {
                font-family: "微软雅黑"; background-color: white; color: black; 
                border: 2px solid gray; border-radius: 10px; padding: 5px;
            }
            QComboBox::drop-down {
                border-left-width: 2px; border-left-color: gray; border-left-style: solid;
                border-top-right-radius: 10px; border-bottom-right-radius: 10px;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid black;
                width: 0px;
                height: 0px;
            }
            QComboBox:hover {
                background-color: #f0f0f0;
            }
        """


class ColorSettingsGroup(QGroupBox):
    """颜色设置组"""
    
    def __init__(self, parent=None):
        super().__init__("颜色设置", parent)
        self.settings_manager = SettingsManager()
        self._init_ui()
        self._load_settings()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QFormLayout()
        
        # 背景颜色
        self.background_color = ColorPickerWidget()
        self.background_color.color_changed.connect(
            lambda color: self.settings_manager.Custom.set_value("background_color", color)
        )
        
        # 信息通知颜色
        self.info_color = ColorPickerWidget()
        self.info_color.color_changed.connect(
            lambda color: self.settings_manager.Custom.set_value("notification_info_color", color)
        )
        
        # 警告通知颜色
        self.warning_color = ColorPickerWidget()
        self.warning_color.color_changed.connect(
            lambda color: self.settings_manager.Custom.set_value("notification_warning_color", color)
        )
        
        # 错误通知颜色
        self.error_color = ColorPickerWidget()
        self.error_color.color_changed.connect(
            lambda color: self.settings_manager.Custom.set_value("notification_error_color", color)
        )
        
        layout.addRow("背景颜色:", self.background_color)
        layout.addRow("信息通知颜色:", self.info_color)
        layout.addRow("警告通知颜色:", self.warning_color)
        layout.addRow("错误通知颜色:", self.error_color)
        
        self.setLayout(layout)
    
    def _load_settings(self):
        """加载颜色设置"""
        # 背景颜色
        bg_color = self.settings_manager.Custom.get_value(
            "background_color", 
            CustomConfig.DEFAULT_COLORS["background"]
        )
        self.background_color.set_color(bg_color)
        
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


class FontSettingsGroup(QGroupBox):
    """字体设置组"""
    
    def __init__(self, parent=None):
        super().__init__("字体设置", parent)
        self.settings_manager = SettingsManager()
        self.wheel_filter = WheelEventFilter()
        self._init_ui()
        self._load_settings()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QFormLayout()
        
        # 全局字体 - 应用设置界面样式
        self.global_font = QLineEdit()
        self.global_font.textChanged.connect(
            lambda text: self.settings_manager.Custom.set_value("global_font", text)
        )
        self.global_font.setStyleSheet(self._get_input_style())
        # 注意：全局字体输入框不安装滚轮过滤器，因为用户可能需要滚动查看长字体名称
        
        # 最小字号 - 应用设置界面样式
        self.min_font_size = QSpinBox()
        self.min_font_size.setRange(8, 50)
        self.min_font_size.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("min_font_size", str(value))
        )
        self.min_font_size.setStyleSheet(self._get_spinbox_style())
        # 安装滚轮事件过滤器
        self.min_font_size.installEventFilter(self.wheel_filter)
        
        # 最大字号 - 应用设置界面样式
        self.max_font_size = QSpinBox()
        self.max_font_size.setRange(10, 100)
        self.max_font_size.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("max_font_size", str(value))
        )
        self.max_font_size.setStyleSheet(self._get_spinbox_style())
        # 安装滚轮事件过滤器
        self.max_font_size.installEventFilter(self.wheel_filter)
        
        layout.addRow("全局字体:", self.global_font)
        layout.addRow("最小字号:", self.min_font_size)
        layout.addRow("最大字号:", self.max_font_size)
        
        self.setLayout(layout)
    
    def _load_settings(self):
        """加载设置"""
        # 全局字体
        global_font = self.settings_manager.Custom.get_value(
            "global_font",
            CustomConfig.DEFAULT_FONTS["global_font"]
        )
        self.global_font.setText(global_font)
        
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
    
    def _get_input_style(self):
        """获取输入框样式 - 与设置界面保持一致"""
        return "QLineEdit { background-color: white; color: black; border: 2px solid gray; border-radius: 10px; padding: 5px; }"
    
    def _get_spinbox_style(self):
        """获取SpinBox样式 - 与设置界面保持一致"""
        return """
            QSpinBox {
                font-family: "微软雅黑"; background-color: white; color: black; 
                border: 2px solid gray; border-radius: 10px; padding: 5px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                border: 1px solid gray;
                background-color: #f0f0f0;
                border-radius: 5px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #e0e0e0;
            }
        """


class NotificationSettingsGroup(QGroupBox):
    """通知设置组"""
    
    def __init__(self, parent=None):
        super().__init__("通知设置", parent)
        self.settings_manager = SettingsManager()
        self.wheel_filter = WheelEventFilter()
        self._init_ui()
        self._load_settings()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QFormLayout()
        
        # 动画时长设置 - 应用设置界面样式
        self.animation_appear = QSpinBox()
        self.animation_appear.setRange(100, 5000)
        self.animation_appear.setSuffix(" ms")
        self.animation_appear.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("animation_appear", str(value))
        )
        self.animation_appear.setStyleSheet(self._get_spinbox_style())
        # 安装滚轮事件过滤器
        self.animation_appear.installEventFilter(self.wheel_filter)
        
        self.animation_disappear = QSpinBox()
        self.animation_disappear.setRange(100, 5000)
        self.animation_disappear.setSuffix(" ms")
        self.animation_disappear.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("animation_disappear", str(value))
        )
        self.animation_disappear.setStyleSheet(self._get_spinbox_style())
        # 安装滚轮事件过滤器
        self.animation_disappear.installEventFilter(self.wheel_filter)
        
        self.animation_move = QSpinBox()
        self.animation_move.setRange(100, 5000)
        self.animation_move.setSuffix(" ms")
        self.animation_move.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("animation_move", str(value))
        )
        self.animation_move.setStyleSheet(self._get_spinbox_style())
        # 安装滚轮事件过滤器
        self.animation_move.installEventFilter(self.wheel_filter)
        
        # 位置设置 - 应用设置界面样式
        self.position_m = QSpinBox()
        self.position_m.setRange(1, 20)
        self.position_m.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("position_m", str(value))
        )
        self.position_m.setStyleSheet(self._get_spinbox_style())
        # 安装滚轮事件过滤器
        self.position_m.installEventFilter(self.wheel_filter)
        
        # 修改为 QDoubleSpinBox - 应用设置界面样式
        self.position_n = QDoubleSpinBox()
        self.position_n.setRange(1, 20)
        self.position_n.setSingleStep(0.25)
        self.position_n.setDecimals(2)  # 设置小数点位数
        self.position_n.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("position_n", str(value))
        )
        self.position_n.setStyleSheet(self._get_double_spinbox_style())
        # 安装滚轮事件过滤器
        self.position_n.installEventFilter(self.wheel_filter)
        
        # 尺寸比例 - 修改为 QDoubleSpinBox - 应用设置界面样式
        self.width_ratio = QDoubleSpinBox()
        self.width_ratio.setRange(0.1, 5.0)
        self.width_ratio.setSingleStep(0.1)
        self.width_ratio.setDecimals(2)
        self.width_ratio.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("width_ratio", str(value))
        )
        self.width_ratio.setStyleSheet(self._get_double_spinbox_style())
        # 安装滚轮事件过滤器
        self.width_ratio.installEventFilter(self.wheel_filter)
        
        self.height_ratio = QDoubleSpinBox()
        self.height_ratio.setRange(0.1, 5.0)
        self.height_ratio.setSingleStep(0.1)
        self.height_ratio.setDecimals(2)
        self.height_ratio.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("height_ratio", str(value))
        )
        self.height_ratio.setStyleSheet(self._get_double_spinbox_style())
        # 安装滚轮事件过滤器
        self.height_ratio.installEventFilter(self.wheel_filter)
        
        # 其他设置 - 应用设置界面样式
        self.max_visible = QSpinBox()
        self.max_visible.setRange(1, 20)
        self.max_visible.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("max_visible", str(value))
        )
        self.max_visible.setStyleSheet(self._get_spinbox_style())
        # 安装滚轮事件过滤器
        self.max_visible.installEventFilter(self.wheel_filter)
        
        self.offset_n = QSpinBox()
        self.offset_n.setRange(1, 10)
        self.offset_n.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("offset_n", str(value))
        )
        self.offset_n.setStyleSheet(self._get_spinbox_style())
        # 安装滚轮事件过滤器
        self.offset_n.installEventFilter(self.wheel_filter)
        
        # 修改为 QDoubleSpinBox - 应用设置界面样式
        self.spacing_n = QDoubleSpinBox()
        self.spacing_n.setRange(0.1, 5.0)
        self.spacing_n.setSingleStep(0.1)
        self.spacing_n.setDecimals(2)
        self.spacing_n.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("spacing_n", str(value))
        )
        self.spacing_n.setStyleSheet(self._get_double_spinbox_style())
        # 安装滚轮事件过滤器
        self.spacing_n.installEventFilter(self.wheel_filter)
        
        self.auto_close_time = QSpinBox()
        self.auto_close_time.setRange(1000, 30000)
        self.auto_close_time.setSingleStep(500)
        self.auto_close_time.setSuffix(" ms")
        self.auto_close_time.valueChanged.connect(
            lambda value: self.settings_manager.Custom.set_value("auto_close_time", str(value))
        )
        self.auto_close_time.setStyleSheet(self._get_spinbox_style())
        # 安装滚轮事件过滤器
        self.auto_close_time.installEventFilter(self.wheel_filter)
        
        # 添加到布局
        layout.addRow("出现动画时长:", self.animation_appear)
        layout.addRow("消失动画时长:", self.animation_disappear)
        layout.addRow("移动动画时长:", self.animation_move)
        layout.addRow("位置 M 坐标:", self.position_m)
        layout.addRow("位置 N 坐标:", self.position_n)
        layout.addRow("宽度比例:", self.width_ratio)
        layout.addRow("高度比例:", self.height_ratio)
        layout.addRow("最大可见数:", self.max_visible)
        layout.addRow("偏移量 N:", self.offset_n)
        layout.addRow("间距 N:", self.spacing_n)
        layout.addRow("自动关闭时间:", self.auto_close_time)
        
        self.setLayout(layout)
    
    def _load_settings(self):
        """加载设置"""
        # 动画设置
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
    
    def _get_spinbox_style(self):
        """获取SpinBox样式 - 与设置界面保持一致"""
        return """
            QSpinBox {
                font-family: "微软雅黑"; background-color: white; color: black; 
                border: 2px solid gray; border-radius: 10px; padding: 5px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                border: 1px solid gray;
                background-color: #f0f0f0;
                border-radius: 5px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #e0e0e0;
            }
        """
    
    def _get_double_spinbox_style(self):
        """获取DoubleSpinBox样式 - 与设置界面保持一致"""
        return """
            QDoubleSpinBox {
                font-family: "微软雅黑"; background-color: white; color: black; 
                border: 2px solid gray; border-radius: 10px; padding: 5px;
            }
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                border: 1px solid gray;
                background-color: #f0f0f0;
                border-radius: 5px;
            }
            QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
                background-color: #e0e0e0;
            }
        """


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
        
        # 通知设置
        self.notification_group = NotificationSettingsGroup(self)
        self.content_layout.addWidget(self.notification_group)
        
        # 添加拉伸，使内容顶部对齐
        self.content_layout.addStretch(1)
        
        # 设置滚动区域的内容部件
        self.scroll_area.setWidget(self.content_widget)
        
        # 操作按钮 - 应用设置界面样式
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
            color_picker.palette_button.setFont(font)
        
        # 应用字体到字体设置组（注意：全局字体输入框不应用字体）
        self.font_group.setFont(font)
        self.font_group.min_font_size.setFont(font)
        self.font_group.max_font_size.setFont(font)
        
        # 应用字体到通知设置组
        self.notification_group.setFont(font)
        for widget in [self.notification_group.animation_appear,
                      self.notification_group.animation_disappear,
                      self.notification_group.animation_move,
                      self.notification_group.position_m,
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
            
            # 重置字体
            for key, value in CustomConfig.DEFAULT_FONTS.items():
                self.settings_manager.Custom.set_value(key, value)
            
            # 重置通知
            for key, value in CustomConfig.DEFAULT_NOTIFICATIONS.items():
                self.settings_manager.Custom.set_value(key, value)
            
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
        # 应用窗口尺寸
        window_size = self.settings_manager.Custom.get_value("window_size", "1024x768")
        if self.parent_window:
            width, height = map(int, window_size.split('x'))
            self.parent_window.resize(width, height)
        
        # 应用背景颜色
        bg_color = self.settings_manager.Custom.get_value(
            "background_color", 
            CustomConfig.DEFAULT_COLORS["background"]
        )
        if self.parent_window:
            self.parent_window.setStyleSheet(f"background-color: {bg_color};")
        
        # 更新字体
        self._update_fonts()
        
        QMessageBox.information(self, "应用成功", "个性化设置已应用，部分设置需要重启程序才能生效")
    
    def _get_button_style(self):
        """获取按钮样式 - 与设置界面保持一致"""
        return """
            QPushButton {
                font-family: "微软雅黑"; background-color: white; color: black;
                border: 2px solid gray; border-radius: 5px; font-weight: bold;
                padding: 8px 16px;
            }
            QPushButton:hover { background-color: #f0f0f0; }
        """
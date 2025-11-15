import threading
from typing import Dict, List, Callable, Any
from PyQt5.QtWidgets import (QWidget, QPushButton, QSlider, QTextEdit, QCheckBox, QComboBox, QLabel)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, pyqtSlot
from PyQt5.QtGui import QFont

from misc_func import AudioConfig, VoiceConfig, ContentHasher, AudioFileManager, InputValidator
from iw_text_import import show_text_import_dialog

'''
本段代码在SimeonTest Re1时使用 DeepSeek 重构，
我自己都不知道小鲸鱼怎么把600多行“精简”成980多行的，
不过看着还挺工整的。
This code uses DeepSeek refactoring at Simeontest RE1,
i don't even know how DeepSeek “Condensed” 600 lines into 980 lines,
it looks neat, though.
'''

class GenerationSignals(QObject):
    """生成页面信号类，用于线程安全通信"""
    
    generation_complete = pyqtSignal(bool, str)
    preview_generated = pyqtSignal(str)
    preview_error = pyqtSignal(str)
    update_button_state = pyqtSignal(bool, str)


class ParameterControl:
    """参数控制类 - 管理单个参数的控制组件"""
    
    def __init__(self, parent, name: str, display_name: str, min_val: int, max_val: int, 
                 callback: Callable, initial_value: int = 0):
        self.parent = parent
        self.name = name
        self.display_name = display_name
        self.min_val = min_val
        self.max_val = max_val
        self.callback = callback
        self.initial_value = initial_value
        
        self.slider = None
        self.label = None
        self.plus_button = None
        self.minus_button = None
        
        self._create_controls()
    
    def _create_controls(self):
        """创建控制组件"""
        # 创建标签
        self.label = QLabel(f"{self.display_name}: {self.initial_value}", self.parent)
        
        # 创建滑动条
        self.slider = QSlider(Qt.Horizontal, self.parent)
        self.slider.setRange(self.min_val, self.max_val)
        self.slider.setValue(self.initial_value)
        self.slider.valueChanged.connect(self.callback)
        self.slider.setStyleSheet(self._get_slider_style())
        
        # 创建+/-按钮
        self.plus_button = QPushButton('+', self.parent)
        self.plus_button.clicked.connect(lambda: self._adjust_value(1))
        self.plus_button.setStyleSheet(self._get_button_style())
        
        self.minus_button = QPushButton('-', self.parent)
        self.minus_button.clicked.connect(lambda: self._adjust_value(-1))
        self.minus_button.setStyleSheet(self._get_button_style())
    
    def _adjust_value(self, delta: int):
        """调整参数值"""
        current_value = self.slider.value()
        new_value = current_value + delta
        if self.min_val <= new_value <= self.max_val:
            self.slider.setValue(new_value)
    
    def update_display(self, value: int):
        """更新显示"""
        self.label.setText(f"{self.display_name}: {value}")
    
    def set_value(self, value: int):
        """设置参数值"""
        self.slider.setValue(value)
    
    def get_value(self) -> int:
        """获取参数值"""
        return self.slider.value()
    
    def _get_slider_style(self) -> str:
        """获取滑动条样式"""
        return """
        QSlider::groove:horizontal {
            border: none;
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
        """
    
    def _get_button_style(self) -> str:
        """获取按钮样式"""
        return """
            QPushButton {
                font-family: "微软雅黑"; background-color: white; color: black;
                border: 2px solid gray; border-radius: 5px; font-weight: bold;
            }
            QPushButton:hover { background-color: #f0f0f0; }
        """


class VoiceSelection:
    """音色选择类"""
    
    def __init__(self, parent):
        self.parent = parent
        self.combo_box = None
        
        self._create_controls()
    
    def _create_controls(self):
        """创建音色选择控件"""
        self.combo_box = QComboBox(self.parent)
        voices = VoiceConfig.get_voices()
        self.combo_box.addItems(voices)
        self.combo_box.setCurrentIndex(0)
        self.combo_box.currentIndexChanged.connect(self._update_voice)
        self.combo_box.setStyleSheet(self._get_combo_box_style())
    
    def _update_voice(self, index: int):
        """更新音色选择"""
        voice = self.combo_box.itemText(index)
        if hasattr(self.parent, 'config'):
            self.parent.config.voice = voice
        if hasattr(self.parent, '_check_inputs_and_update_button'):
            self.parent._check_inputs_and_update_button()
        if hasattr(self.parent, '_check_content_changed'):
            self.parent._check_content_changed()
        
        # 修复：音色改变时停止预览并重置状态
        if (hasattr(self.parent, 'parent_window') and 
            (self.parent.parent_window.is_playing or 
             self.parent.parent_window.audio_preview.is_paused)):
            self.parent.parent_window.audio_preview.stop_audio()
            self.parent.parent_window.has_preview = False
            if hasattr(self.parent, 'preview_button'):
                self.parent.preview_button.setText("生成预览")
    
    def get_current_voice(self) -> str:
        """获取当前选中的音色"""
        return self.combo_box.currentText()
    
    def _get_combo_box_style(self) -> str:
        """获取下拉框样式"""
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


class TextEditSection:
    """文本编辑区域类"""
    
    def __init__(self, parent):
        self.parent = parent
        self.text_edit = None
        self.overlay_button = None
        
        self._create_controls()
    
    def _create_controls(self):
        """创建文本编辑控件"""
        self.text_edit = QTextEdit(self.parent)
        self.text_edit.textChanged.connect(self._update_content)
        self.text_edit.setStyleSheet("QTextEdit { background-color: white; color: black; border: 3px solid gray; border-radius: 10px; }")
        
        # 文本框文字固定为16点字号
        text_edit_font = QFont("微软雅黑", 9)
        self.text_edit.setFont(text_edit_font)
        
        # 创建缩窄的透明覆盖按钮（让开文本框滑动条）
        self.overlay_button = QPushButton(self.parent)
        self.overlay_button.setStyleSheet("QPushButton { background-color: transparent; border: none; }")
        self.overlay_button.clicked.connect(self._open_text_import_dialog)
    
    def _update_content(self):
        """更新文本内容"""
        if hasattr(self.parent, 'config'):
            self.parent.config.content = self.text_edit.toPlainText()
        if hasattr(self.parent, '_check_inputs_and_update_button'):
            self.parent._check_inputs_and_update_button()
        if hasattr(self.parent, '_check_content_changed'):
            self.parent._check_content_changed()
    
    def _open_text_import_dialog(self):
        """打开文本导入对话框"""
        # 获取主窗口的尺寸和位置
        main_window = self.parent.parent_window
        if main_window:
            # 创建窗口尺寸对象
            window_rect = main_window.geometry()
            
            # 获取当前文本框的内容
            current_text = self.text_edit.toPlainText()
            
            # 调用文本导入对话框，传入当前文本内容
            imported_text = show_text_import_dialog(self.parent, window_rect, current_text)
            
            # 如果用户确认了导入，更新文本框内容
            if imported_text is not None:  # 明确检查是否为None
                self.text_edit.setPlainText(imported_text)
                self._update_content()  # 触发内容更新
    
    def set_text(self, text: str):
        """设置文本内容"""
        self.text_edit.setPlainText(text)
    
    def get_text(self) -> str:
        """获取文本内容"""
        return self.text_edit.toPlainText()


class PreviewControl:
    """预览控制类"""
    
    def __init__(self, parent):
        self.parent = parent
        
        self.preview_button = None
        self.pause_button = None
        self.stop_button = None
        self.preview_progress = None
        self.volume_slider = None  # 新增音量控制
        self.volume_label = None   # 新增音量显示
        self.volume_value_label = None  # 新增音量数值显示
        
        self.is_seeking = False
        
        self._create_controls()
    
    def _create_controls(self):
        """创建预览控制控件"""
        # 生成/播放预览按钮
        self.preview_button = QPushButton('生成预览', self.parent)
        self.preview_button.clicked.connect(self._handle_preview_button)
        self.preview_button.setStyleSheet(self._get_button_style("rgb(0, 100, 200)", "rgb(0, 120, 220)"))
        
        # 暂停/继续按钮
        self.pause_button = QPushButton('暂停', self.parent)
        self.pause_button.clicked.connect(self._toggle_pause)
        self.pause_button.setStyleSheet(self._get_button_style("rgb(100, 100, 100)", "rgb(120, 120, 120)"))
        self.pause_button.setEnabled(False)
        
        # 停止预览按钮
        self.stop_button = QPushButton('停止', self.parent)
        self.stop_button.clicked.connect(self._stop_audio)
        self.stop_button.setStyleSheet(self._get_button_style("rgb(200, 0, 0)", "rgb(220, 0, 0)"))
        self.stop_button.setEnabled(False)
        
        # 横向进度条
        self.preview_progress = QSlider(Qt.Horizontal, self.parent)
        self.preview_progress.setRange(0, 1000)
        self.preview_progress.setValue(0)
        self.preview_progress.sliderPressed.connect(self._on_progress_pressed)
        self.preview_progress.sliderReleased.connect(self._on_progress_released)
        self.preview_progress.valueChanged.connect(self._on_progress_changed)
        self.preview_progress.setStyleSheet(self._get_progress_style())
        
        # 新增：音量控制
        self._create_volume_controls()
    
    def _create_volume_controls(self):
        """创建音量控制控件"""
        # 音量标签
        self.volume_label = QLabel("音量", self.parent)
        self.volume_label.setAlignment(Qt.AlignCenter)
        
        # 音量滑动条
        self.volume_slider = QSlider(Qt.Horizontal, self.parent)
        self.volume_slider.setRange(0, 100)  # 0-100%
        self.volume_slider.setValue(100)     # 默认100%
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        self.volume_slider.setStyleSheet(self._get_volume_slider_style())
        
        # 音量数值显示
        self.volume_value_label = QLabel("100%", self.parent)
        self.volume_value_label.setAlignment(Qt.AlignCenter)
    
    def _on_volume_changed(self, value: int):
        """音量改变事件"""
        if hasattr(self.parent, 'parent_window'):
            # 转换为 0.0-1.0 的范围
            volume = value / 100.0
            success = self.parent.parent_window.audio_preview.set_volume(volume)
            
            # 更新音量显示
            if success:
                self.volume_value_label.setText(f"{value}%")
    
    def _handle_preview_button(self):
        """处理预览按钮点击"""
        if (hasattr(self.parent, 'parent_window') and 
            self.parent.parent_window.has_preview and 
            self.parent._is_content_unchanged()):
            self.parent.parent_window.audio_preview.play_preview()
        else:
            self.parent._generate_preview_audio()
    
    def _toggle_pause(self):
        """切换暂停状态"""
        if hasattr(self.parent, 'parent_window'):
            self.parent.parent_window.audio_preview.toggle_pause()
    
    def _stop_audio(self):
        """停止音频播放"""
        if hasattr(self.parent, 'parent_window'):
            self.parent.parent_window.audio_preview.stop_audio()
    
    def _on_progress_pressed(self):
        """进度条按下事件"""
        if hasattr(self.parent, 'parent_window'):
            self.parent.parent_window.audio_preview.set_seeking(True)
    
    def _on_progress_released(self):
        """进度条释放事件"""
        if (hasattr(self.parent, 'parent_window') and 
            self.parent.parent_window.is_playing):
            
            # 获取进度百分比
            percentage = self.preview_progress.value() / 1000.0
            self.parent.parent_window.audio_preview.seek_to_percentage(percentage)
    
    def _on_progress_changed(self, value: int):
        """进度条值改变事件"""
        if (hasattr(self.parent, 'parent_window') and 
            self.parent.parent_window.audio_preview.is_seeking and 
            self.parent.parent_window.is_playing):
            # 实时更新显示，但不实际跳转（等待释放）
            pass
    
    def update_preview_button_state(self, has_preview: bool, content_unchanged: bool):
        """更新预览按钮状态"""
        if has_preview and content_unchanged:
            self.preview_button.setText("播放预览")
        else:
            self.preview_button.setText("生成预览")
    
    def set_playback_controls_enabled(self, playing: bool):
        """设置播放控制按钮状态"""
        self.preview_button.setEnabled(not playing)
        self.pause_button.setEnabled(playing)
        self.stop_button.setEnabled(playing)
    
    def update_pause_button_text(self, paused: bool):
        """更新暂停按钮文本"""
        self.pause_button.setText("继续" if paused else "暂停")
    
    def _get_button_style(self, normal_color: str, hover_color: str) -> str:
        """获取按钮样式"""
        return f"""
            QPushButton {{
                font-family: "微软雅黑"; background-color: {normal_color}; color: white;
                border: 2px solid gray; border-radius: 5px;
            }}
            QPushButton:hover {{ background-color: {hover_color}; }}
        """
    
    def _get_progress_style(self) -> str:
        """获取进度条样式"""
        return """
        QSlider::groove:horizontal {
            border: none;
            height: 18px;
            background: #FFFFFF;
            border-radius: 9px;
        }
        
        QSlider::sub-page:horizontal {
            background: #4CAF50;
            border-radius: 9px;
        }
        
        QSlider::add-page:horizontal {
            background: #FFFFFF;
            border-radius: 9px;
        }
        
        QSlider::handle:horizontal {
            background: #FFFFFF;
            border: 2px solid #4CAF50;
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
        """
    
    def _get_volume_slider_style(self):
        """获取音量滑动条样式"""
        return """
        QSlider::groove:horizontal {
            border: none;
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
        """


class GenerationControl:
    """生成控制类"""
    
    def __init__(self, parent):
        self.parent = parent
        self.button = None
        
        self._create_controls()
    
    def _create_controls(self):
        """创建生成控制控件"""
        self.button = QPushButton('生成并保存音频', self.parent)
        self.button.clicked.connect(self._generate_audio)
        # 初始设置为红色
        self._set_button_style(is_error=True)
    
    def _generate_audio(self):
        """生成音频文件"""
        if hasattr(self.parent, '_generate_audio'):
            self.parent._generate_audio()
    
    def set_button_state(self, is_error: bool, text: str = None):
        """设置按钮状态"""
        self._set_button_style(is_error)
        if text:
            self.button.setText(text)
    
    def set_enabled(self, enabled: bool):
        """设置按钮启用状态"""
        self.button.setEnabled(enabled)
    
    def _set_button_style(self, is_error: bool = False):
        """设置按钮样式"""
        if is_error:
            style = """
                QPushButton {
                    font-family: "微软雅黑"; background-color: red; color: white;
                    border: 2px solid gray; border-radius: 10px;
                }
                QPushButton:hover { background-color: darkred; }
            """
        else:
            style = """
                QPushButton {
                    font-family: "微软雅黑"; background-color: rgb(0, 150, 0); color: white;
                    border: 2px solid gray; border-radius: 10px;
                }
                QPushButton:hover { background-color: rgb(0, 180, 0); }
            """
        self.button.setStyleSheet(style)


class GenerationPage(QWidget):
    """生成页面 - 重构为模块化结构"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = parent.config if parent else AudioConfig()
        self.signals = GenerationSignals()
        
        # 初始化组件
        self._init_components()
        self._connect_signals()
        
    def _init_components(self):
        """初始化所有组件"""
        # 创建参数控制
        self.parameter_controls = {
            'speed': ParameterControl(self, 'speed', '语速', -25, 25, self._update_speed),
            'pitch': ParameterControl(self, 'pitch', '音调', -10, 10, self._update_pitch),
            'volume': ParameterControl(self, 'volume', '音量', -10, 0, self._update_volume)
        }
        
        # 创建其他组件
        self.voice_selection = VoiceSelection(self)
        self.text_edit_section = TextEditSection(self)
        self.preview_control = PreviewControl(self)
        self.generation_control = GenerationControl(self)
        
        # 创建提示控件
        self._create_hint_controls()
        
    def _create_hint_controls(self):
        """创建提示控件"""
        self.checkbox = QCheckBox(self)
        self.hint_label = QLabel("提示1", self)
        
    def _connect_signals(self):
        """连接信号槽"""
        self.signals.generation_complete.connect(self._on_generation_complete_safe)
        self.signals.preview_generated.connect(self._on_preview_generated_safe)
        self.signals.preview_error.connect(self._handle_preview_error_safe)
        self.signals.update_button_state.connect(self._update_button_state_safe)
        
    def resizeEvent(self, event):
        """处理页面大小变化事件"""
        width = self.width()
        height = self.height()
        n = width / 16
        m = height / 16
        offset_m = m

        # 布局开关和提示文本
        checkbox_size = 20
        self.checkbox.setGeometry(int(0 * n), int(0 * m - offset_m), checkbox_size, checkbox_size)
        self.hint_label.setGeometry(int(1 * n), int(0 * m - offset_m), int(2 * n), int(m))

        # 布局水平滑动条及±按钮 - 右半侧元素左边界向右移动0.25n，并缩窄以让出右侧10px
        slider_height = int(0.8 * m)
        button_size = int(0.8 * m)
        
        # 右半侧元素左边界偏移量
        right_offset = int(0.25 * n)
        
        # 计算缩放因子，让出右侧10px空间
        scale_factor = (width - 10) / width
        
        # 语速控件 
        speed_y = int(2 * m - offset_m)
        self._layout_parameter_control('speed', speed_y, right_offset, scale_factor, n, m, button_size, slider_height)
        
        # 音调控件 
        pitch_y = int(4 * m - offset_m)
        self._layout_parameter_control('pitch', pitch_y, right_offset, scale_factor, n, m, button_size, slider_height)
        
        # 音量控件 
        volume_y = int(6 * m - offset_m)
        self._layout_parameter_control('volume', volume_y, right_offset, scale_factor, n, m, button_size, slider_height)

        # 布局文本编辑框 - 左边界向左移动2n，并缩窄
        text_edit_x = int(0 * n)  # 从2*n改为0*n
        text_edit_y = int(2 * m - offset_m)
        text_edit_width = int(8 * n * scale_factor)  # 宽度增加2n以保持右边界不变，并缩窄
        text_edit_height = int(11 * m)  # 高度减小，为底部控件让出空间
        self.text_edit_section.text_edit.setGeometry(text_edit_x, text_edit_y, text_edit_width, text_edit_height)
        
        # 布局缩窄的透明覆盖按钮，让开文本框滑动条
        # 宽度减少20像素以让开滑动条，位置向右偏移
        overlay_width = text_edit_width - 20  # 缩窄宽度
        self.text_edit_section.overlay_button.setGeometry(text_edit_x, text_edit_y, overlay_width, text_edit_height)

        # 计算按钮位置参数
        # "生成预览"和"生成并保存音频"按钮的位置
        # 左侧与提示文本左侧对齐 (8.1*n + right_offset)
        # 右侧与"+"按钮右侧对齐 (14.9*n + button_size + right_offset)
        buttons_left = int(8.1 * n * scale_factor) + right_offset
        buttons_right = int(14.9 * n * scale_factor) + button_size + right_offset
        total_buttons_width = buttons_right - buttons_left
        button_width = total_buttons_width // 2
        
        # 两个按钮中间间隔0.25n
        button_spacing = int(0.25 * n * scale_factor)
        
        # 每个按钮宽度为 (总宽度 - 间隔) / 2
        button_width = (total_buttons_width - button_spacing) // 2
        
        # 按钮上移至与音量提示文本下边界间隔5px
        # 音量提示文本下边界: volume_y + m
        buttons_y = volume_y + int(m) + 5
        
        # 按钮高度保持3*m
        button_height = int(3 * m)
        
        # 布局"生成预览"按钮
        self.preview_control.preview_button.setGeometry(buttons_left, buttons_y, button_width, button_height)
        
        # 布局"生成并保存音频"按钮 (右侧按钮)
        self.generation_control.button.setGeometry(buttons_left + button_width + button_spacing, buttons_y, button_width, button_height)

        # 音色选择栏上移 - 下移0.15m
        # 音色选择栏下边界与按钮下边界间隔5px
        # 按钮下边界: buttons_y + button_height
        voice_combo_y = buttons_y + button_height + 5 + int(0.15 * m)  # 下移0.15m
        voice_combo_height = int(m)
        
        # 布局下拉框 - 左边界与生成预览左边界对齐，右边界与生成音频并保存右边界对齐
        voice_combo_width = buttons_right - buttons_left
        self.voice_selection.combo_box.setGeometry(buttons_left, voice_combo_y, voice_combo_width, voice_combo_height)

        # 播放进度条和暂停停止键下移至播放进度条下边界距离窗口下边界0.25m
        # 窗口下边界: 16*m - offset_m
        # 播放进度条下边界: (16*m - offset_m) - 0.25*m = 15.75*m - offset_m
        progress_bottom = int(15.75 * m - offset_m)
        progress_height = int(m)
        progress_y = progress_bottom - progress_height
        
        # 进度条 - 左边界向左移动2n，与文本框对齐，并缩窄
        progress_x = int(0 * n)  # 从2*n改为0*n
        # 进度条右边界与"+"键右边界对齐
        progress_right = int(14.9 * n * scale_factor) + button_size + right_offset
        progress_width = progress_right - progress_x
        self.preview_control.preview_progress.setGeometry(progress_x, progress_y, progress_width, progress_height)
        
        # 暂停和停止按钮 - 在进度条上方，高度缩窄为原先的2/3
        control_button_height = int(1.0 * m)  # 从1.5*m改为1.0*m (2/3)
        control_button_width = int(2 * n * scale_factor)
        
        # 计算居中位置
        total_control_buttons_width = 2 * control_button_width
        control_buttons_start_x = progress_x + (progress_width - total_control_buttons_width) // 2
        control_buttons_y = progress_y - control_button_height
        
        self.preview_control.pause_button.setGeometry(control_buttons_start_x, control_buttons_y, control_button_width, control_button_height)
        self.preview_control.stop_button.setGeometry(control_buttons_start_x + control_button_width, control_buttons_y, control_button_width, control_button_height)
        
        # 新增：布局音量控制 - 移动到停止键右边
        self._layout_volume_controls(width, height, n, m, scale_factor, right_offset, progress_y, control_buttons_y, control_button_height)

        # 更新字体
        self._update_fonts()

    def _layout_volume_controls(self, width, height, n, m, scale_factor, right_offset, progress_y, control_buttons_y, control_button_height):
        """布局音量控制控件"""
        
        volume_x = int(10* n * scale_factor) + right_offset  
        volume_y = control_buttons_y 
        
        # 音量标签
        label_width = int(1.5 * n * scale_factor)
        self.preview_control.volume_label.setGeometry(
            volume_x, volume_y, label_width, control_button_height
        )
        
        # 音量滑动条
        slider_width = int(2.5 * n * scale_factor)
        self.preview_control.volume_slider.setGeometry(
            volume_x + label_width, volume_y, slider_width, control_button_height
        )
        
        # 音量数值显示
        value_width = int(1.8 * n * scale_factor)
        self.preview_control.volume_value_label.setGeometry(
            volume_x + label_width + slider_width, volume_y, value_width, control_button_height
        )

    def _layout_parameter_control(self, param_name: str, y_pos: int, right_offset: int, 
                                 scale_factor: float, n: float, m: float, 
                                 button_size: int, slider_height: int):
        """布局参数控制组件"""
        control = self.parameter_controls[param_name]
        
        control.label.setGeometry(int(8.1 * n * scale_factor) + right_offset, y_pos, int(2 * n * scale_factor), int(m))
        control.minus_button.setGeometry(int(10.1 * n * scale_factor) + right_offset, y_pos, button_size, button_size)  
        control.slider.setGeometry(int(10.8 * n * scale_factor) + right_offset, y_pos, int(4 * n * scale_factor), slider_height)  
        control.plus_button.setGeometry(int(14.9 * n * scale_factor) + right_offset, y_pos, button_size, button_size)

    def _update_fonts(self):
        """更新字体大小"""
        if not self.parent_window:
            return
            
        current_width = self.parent_window.width()
        current_height = self.parent_window.height()
        
        # 使用与主界面相同的算法
        min_font_size = 22
        max_font_size = 42
        default_width = 1080
        default_height = 720
        
        width_ratio = current_width / default_width
        height_ratio = current_height / default_height
        ratio = (width_ratio + height_ratio) / 2
        
        base_font_size = min_font_size + (max_font_size - min_font_size) * (ratio - 1)
        base_font_size = max(min_font_size, min(max_font_size, base_font_size))
        
        # 转换为整数
        base_font_size = int(base_font_size)
        
        # 计算其他字体大小
        other_font_size = int(base_font_size * 0.5)
        other_font = QFont("微软雅黑", other_font_size)
        
        # 应用字体到音量控制标签
        self.preview_control.volume_label.setFont(other_font)
        self.preview_control.volume_value_label.setFont(other_font)

    # 参数更新方法
    def _update_speed(self, value: int):
        self._update_parameter('speed', value, "语速")

    def _update_pitch(self, value: int):
        self._update_parameter('pitch', value, "音调")

    def _update_volume(self, value: int):
        self._update_parameter('volume', value, "音量")

    def _update_parameter(self, param: str, value: int, display_name: str):
        """更新参数"""
        setattr(self.config, param, value)
        self.parameter_controls[param].update_display(value)
        self._check_inputs_and_update_button()
        self._check_content_changed()

    # 音频预览相关方法
    def _generate_preview_audio(self):
        """生成预览音频"""
        print("开始生成预览音频")
        
        # 修复问题①：如果文本框没有文本，使用默认文本
        if not self.config.content.strip():
            # 使用AudioConfig的默认内容
            default_config = AudioConfig()
            self.config.content = default_config.content
            # 更新文本框显示
            self.text_edit_section.set_text(self.config.content)
            print(f"使用默认文本: {self.config.content}")
        
        if not self._validate_preview_inputs():
            return
            
        self.preview_control.preview_button.setEnabled(False)
        self.preview_control.preview_button.setText("生成中...")
        
        threading.Thread(
            target=self.parent_window.audio_generator.generate_preview,
            args=(self.config, self._on_preview_generated_thread, self._handle_preview_error_thread),
            daemon=True
        ).start()

    def _on_preview_generated_thread(self, file_path: str):
        """预览音频生成完成处理 - 线程版本"""
        self.signals.preview_generated.emit(file_path)

    @pyqtSlot(str)
    def _on_preview_generated_safe(self, file_path: str):
        """预览音频生成完成处理 - 线程安全版本"""
        self.preview_control.preview_button.setEnabled(True)
        self.preview_control.update_preview_button_state(True, True)
        
        cache_key = ContentHasher.get_cache_key(self.config)
        self.parent_window.audio_cache[cache_key] = file_path
        self.parent_window.current_audio_path = file_path
        
        self.parent_window.last_content_hash = ContentHasher.get_content_hash(self.config)
        self.parent_window.has_preview = True
        
        # 使用新的消息系统
        self.parent_window.notification_manager.show_message("预览音频生成完成", "I", 3000)
        
        print(f"预览音频生成完成: {file_path}")

    def _handle_preview_error_thread(self, error: str):
        """处理预览错误 - 线程版本"""
        self.signals.preview_error.emit(error)

    @pyqtSlot(str)
    def _handle_preview_error_safe(self, error: str):
        """处理预览错误 - 线程安全版本"""
        print(f"生成预览音频时发生错误: {error}")
        self.preview_control.preview_button.setEnabled(True)
        self.preview_control.update_preview_button_state(False, False)
        self.parent_window.has_preview = False
        
        # 使用新的消息系统
        self.parent_window.notification_manager.show_message(f"生成预览失败: {error}", "E", 5000)

    # 音频生成相关方法
    def _generate_audio(self):
        """生成音频文件 - 异步版本"""
        print("开始生成音频")
        
        if not self._validate_inputs():
            return
        
        # 设置默认保存路径
        self.config.save_path = AudioFileManager.get_default_save_path(self.config, self.parent_window.settings_manager)
        if not self.config.save_path:
            # 使用新的消息系统
            self.parent_window.notification_manager.show_message("请先在设置中配置默认保存路径", "W", 5000)
            return
            
        self.generation_control.set_enabled(False)
        self.generation_control.set_button_state(False, "生成中...")
        
        threading.Thread(
            target=self.parent_window.audio_generator.generate_audio,
            args=(self.config, self._on_generation_complete_thread),
            daemon=True
        ).start()

    def _on_generation_complete_thread(self, success: bool, message: str):
        """音频生成完成回调 - 线程版本"""
        self.signals.generation_complete.emit(success, message)

    @pyqtSlot(bool, str)
    def _on_generation_complete_safe(self, success: bool, message: str):
        """音频生成完成回调 - 线程安全版本"""
        self.generation_control.set_enabled(True)
        self.generation_control.set_button_state(not success, "生成并保存音频")
        
        if success:
            # 使用新的消息系统
            self.parent_window.notification_manager.show_message("音频成功生成并保存", "I", 3000)
            print("音频生成成功")
        else:
            # 使用新的消息系统
            self.parent_window.notification_manager.show_message(f"音频生成失败: {message}", "E", 5000)
            print(f"音频生成失败: {message}")

    # 验证方法
    def _validate_preview_inputs(self) -> bool:
        """验证预览输入"""
        success, message = InputValidator.validate_preview_inputs(self.config)
        if not success:
            # 使用新的消息系统
            self.parent_window.notification_manager.show_message(message, "W", 5000)
            print(message)
            return False
        return True

    def _validate_inputs(self) -> bool:
        """验证输入参数"""
        success, message = InputValidator.validate_generation_inputs(self.config, self.parent_window.settings_manager)
        if not success:
            # 使用新的消息系统
            self.parent_window.notification_manager.show_message(message, "W", 5000)
            print(message)
            return False
        return True

    # 状态检查方法
    def _check_inputs_and_update_button(self):
        """检查输入并更新按钮状态"""
        has_error, empty_fields = InputValidator.check_inputs_for_button(self.config, self.parent_window.settings_manager)
        # 使用信号安全地更新UI
        self.signals.update_button_state.emit(has_error, ", ".join(empty_fields))

    @pyqtSlot(bool, str)
    def _update_button_state_safe(self, has_error: bool, empty_fields_text: str):
        """线程安全地更新按钮状态"""
        self.generation_control.set_button_state(has_error)

    def _check_content_changed(self):
        """检查内容是否改变"""
        current_hash = ContentHasher.get_content_hash(self.config)
        content_changed = (self.parent_window.last_content_hash is None or 
                          current_hash != self.parent_window.last_content_hash)
        
        if content_changed and self.parent_window.has_preview:
            self.preview_control.update_preview_button_state(False, False)
            self.parent_window.has_preview = False
            # 修复：内容改变时停止预览播放
            if self.parent_window.is_playing or self.parent_window.audio_preview.is_paused:
                self.parent_window.audio_preview.stop_audio()

    def _is_content_unchanged(self) -> bool:
        """检查内容是否未改变"""
        current_hash = ContentHasher.get_content_hash(self.config)
        return (self.parent_window.last_content_hash is not None and 
                current_hash == self.parent_window.last_content_hash)

    # 工具方法
    def _get_content_hash(self) -> str:
        """获取内容哈希值"""
        return ContentHasher.get_content_hash(self.config)

    def _get_cache_key(self) -> str:
        """获取缓存键"""
        return ContentHasher.get_cache_key(self.config)

if __name__ == "__main__":
    print(0)
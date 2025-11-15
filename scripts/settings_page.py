from PyQt5.QtWidgets import (QWidget, QPushButton, QSlider, QLineEdit, QComboBox, QLabel, QFileDialog, QCheckBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from misc_func import SettingsManager, CustomConfig
'''
本段代码完全由DeepSeek编写。
AI太好用了你们知道吗

This code is written entirely by DeepSeek.
Ai is so easy to use, you know
'''

class SettingsSection:
    """设置部分基类 - 为不同类型的设置提供统一接口"""
    
    def __init__(self, parent, settings_manager):
        self.parent = parent
        self.settings_manager = settings_manager
        self.widgets = {}
        
    def create_ui(self):
        """创建UI组件 - 子类必须实现"""
        raise NotImplementedError("子类必须实现create_ui方法")
        
    def load_settings(self):
        """加载设置 - 子类必须实现"""
        raise NotImplementedError("子类必须实现load_settings方法")
        
    def resize_ui(self, width, height, n, m, scale_factor):
        """调整UI布局 - 子类必须实现"""
        raise NotImplementedError("子类必须实现resize_ui方法")
        
    def update_fonts(self, font, small_font=None):
        """更新字体 - 子类必须实现"""
        raise NotImplementedError("子类必须实现update_fonts方法")


class ApiKeySection(SettingsSection):
    """API Key设置部分"""
    
    def __init__(self, parent, settings_manager):
        super().__init__(parent, settings_manager)
        self.key_configs = [
            {"name": "ChatGLM Key", "id": "api_key_ChatGLM", "enabled": True},
            {"name": "Azure未实现", "id": "api_key_Azure", "enabled": False},
            {"name": "Gemini未实现", "id": "api_key_Gemini", "enabled": False},
            {"name": "留空", "id": "api_key_4", "enabled": False},
            {"name": "留空", "id": "api_key_5", "enabled": False}
        ]
        
    def create_ui(self):
        """创建API Key UI组件"""
        self.widgets['labels'] = []
        self.widgets['inputs'] = []
        
        for config in self.key_configs:
            if config["enabled"]:
                label = QLabel(config["name"], self.parent)
                input_field = QLineEdit(self.parent)
                input_field.textChanged.connect(
                    lambda text, key_id=config["id"]: self._on_api_key_changed(key_id, text)
                )
                input_field.setStyleSheet(self._get_input_style())
                
                self.widgets['labels'].append(label)
                self.widgets['inputs'].append(input_field)
                
        # 保留被注释掉的代码结构以便未来恢复
        # key_names = ["ChatGLM Key", "Azure未实现", "Gemini未实现", "留空", "留空"]
        # key_ids = ["api_key_ChatGLM", "api_key_Azure", "api_key_Gemini", "api_key_4", "api_key_5"]
        
    def load_settings(self):
        """加载API Key设置"""
        for i, config in enumerate(self.key_configs):
            if config["enabled"] and i < len(self.widgets['inputs']):
                api_key = self.settings_manager.get_api_key(config["id"])
                self.widgets['inputs'][i].setText(api_key)
                
    def resize_ui(self, width, height, n, m, scale_factor):
        """调整API Key部分布局"""
        if not self.widgets.get('labels'):
            return
            
        y_pos = int(2 * m)
        for i, (label, input_field) in enumerate(zip(self.widgets['labels'], self.widgets['inputs'])):
            current_y = y_pos + i * int(1.5 * m)  # 为未来多行布局预留空间
            label.setGeometry(int(2 * n * scale_factor), current_y, int(3 * n * scale_factor), int(m))
            input_field.setGeometry(int(6 * n * scale_factor), current_y, int(8 * n * scale_factor), int(m))
            
    def update_fonts(self, font, small_font=None):
        """更新API Key部分字体"""
        for label in self.widgets.get('labels', []):
            label.setFont(font)
        for input_field in self.widgets.get('inputs', []):
            input_field.setFont(font)
            
    def _on_api_key_changed(self, key_name, text):
        """API Key改变时的处理"""
        success = self.settings_manager.set_api_key(key_name, text)
        if not success:
            self.parent.parent_window.notification_manager.show_message("无法保存API Key设置", "E", 5000)
            
    def _get_input_style(self):
        """获取输入框样式"""
        return "QLineEdit { background-color: white; color: black; border: 3px solid gray; border-radius: 10px; padding: 5px; }"


class VoiceSection(SettingsSection):
    """音色设置部分"""
    
    def __init__(self, parent, settings_manager):
        super().__init__(parent, settings_manager)
        
    def create_ui(self):
        """创建音色设置UI组件"""
        self.widgets['default_voice_label'] = QLabel("默认音色", self.parent)
        
        self.widgets['default_voice_source'] = QComboBox(self.parent)
        self.widgets['default_voice'] = QComboBox(self.parent)
        
        for combo in [self.widgets['default_voice_source'], self.widgets['default_voice']]:
            combo.setStyleSheet(self._get_combo_box_style())
        
        # 只保留EdgeAPI选项，注释掉其他未实现的功能
        self.widgets['default_voice_source'].addItems(['EdgeAPI'])  # , 'Azure', 'ChatGLM', 'Gemini', '留空'])
        self.widgets['default_voice_source'].currentTextChanged.connect(
            lambda text: self._on_default_voice_changed('default_voice_1', text)
        )
        self.widgets['default_voice'].addItems(['中文'])  # , 'Azure', 'ChatGLM', 'Gemini', '留空'])
        self.widgets['default_voice'].currentTextChanged.connect(
            lambda text: self._on_default_voice_changed('default_voice_2', text)
        )
        
    def load_settings(self):
        """加载音色设置"""
        voice1 = self.settings_manager.get_default_voice(1)
        voice2 = self.settings_manager.get_default_voice(2)
        
        index1 = self.widgets['default_voice_source'].findText(voice1)
        if index1 >= 0:
            self.widgets['default_voice_source'].setCurrentIndex(index1)
            
        index2 = self.widgets['default_voice'].findText(voice2)
        if index2 >= 0:
            self.widgets['default_voice'].setCurrentIndex(index2)
            
    def resize_ui(self, width, height, n, m, scale_factor):
        """调整音色部分布局"""
        voice_y = int(4 * m)  # 上移，因为只显示一行API Key
        self.widgets['default_voice_label'].setGeometry(int(2 * n * scale_factor), voice_y, int(3 * n * scale_factor), int(m))
        self.widgets['default_voice_source'].setGeometry(int(6 * n * scale_factor), voice_y, int(3 * n * scale_factor), int(m))
        self.widgets['default_voice'].setGeometry(int(10 * n * scale_factor), voice_y, int(4 * n * scale_factor), int(m))
        
    def update_fonts(self, font, small_font=None):
        """更新音色部分字体"""
        self.widgets['default_voice_label'].setFont(font)
        self.widgets['default_voice_source'].setFont(font)
        self.widgets['default_voice'].setFont(font)
        
    def _on_default_voice_changed(self, key_name, text):
        """默认音色改变时的处理"""
        success = self.settings_manager.set_api_key(key_name, text)
        if not success:
            self.parent.parent_window.notification_manager.show_message("无法保存音色设置", "E", 5000)
            
    def _get_combo_box_style(self):
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


class SavePathSection(SettingsSection):
    """保存路径设置部分"""
    
    def __init__(self, parent, settings_manager):
        super().__init__(parent, settings_manager)
        
    def create_ui(self):
        """创建保存路径UI组件"""
        self.widgets['default_save_path_label'] = QLabel("默认保存路径", self.parent)
        self.widgets['save_path_display'] = QLineEdit(self.parent)
        self.widgets['save_path_display'].setReadOnly(True)
        self.widgets['save_path_display'].setStyleSheet(self._get_input_style())
        
        self.widgets['save_path_button'] = QPushButton("选择路径", self.parent)
        self.widgets['save_path_button'].clicked.connect(self._select_default_save_path)
        self.widgets['save_path_button'].setStyleSheet(self._get_button_style())
        
    def load_settings(self):
        """加载保存路径设置"""
        save_path = self.settings_manager.get_default_save_path()
        self.widgets['save_path_display'].setText(save_path)
        
    def resize_ui(self, width, height, n, m, scale_factor):
        """调整保存路径部分布局"""
        save_path_y = int(5 * m)
        self.widgets['default_save_path_label'].setGeometry(int(2 * n * scale_factor), save_path_y, int(3 * n * scale_factor), int(m))
        self.widgets['save_path_display'].setGeometry(int(6 * n * scale_factor), save_path_y, int(6 * n * scale_factor), int(m))
        # 选择路径按钮右边界作为对齐基准
        self.widgets['save_path_button'].setGeometry(int(12 * n * scale_factor), save_path_y, int(2 * n * scale_factor), int(m))
        
    def update_fonts(self, font, small_font=None):
        """更新保存路径部分字体"""
        self.widgets['default_save_path_label'].setFont(font)
        self.widgets['save_path_display'].setFont(font)
        self.widgets['save_path_button'].setFont(font)
        
    def _select_default_save_path(self):
        """选择默认保存路径"""
        directory = QFileDialog.getExistingDirectory(self.parent, "选择默认保存路径")
        if directory:
            self.widgets['save_path_display'].setText(directory)
            success = self.settings_manager.set_default_save_path(directory)
            if not success:
                self.parent.parent_window.notification_manager.show_message("无法保存路径设置", "E", 5000)
                
    def _get_input_style(self):
        """获取输入框样式"""
        return "QLineEdit { background-color: white; color: black; border: 3px solid gray; border-radius: 10px; padding: 5px; }"
    
    def _get_button_style(self):
        """获取按钮样式"""
        return """
            QPushButton {
                font-family: "微软雅黑"; background-color: white; color: black;
                border: 2px solid gray; border-radius: 5px; font-weight: bold;
            }
            QPushButton:hover { background-color: #f0f0f0; }
        """


class SpeedSection(SettingsSection):
    """语速设置部分"""
    
    def __init__(self, parent, settings_manager):
        super().__init__(parent, settings_manager)
        
    def create_ui(self):
        """创建语速设置UI组件"""
        self.widgets['default_speed_label'] = QLabel("默认语速", self.parent)
        
        self.widgets['speed_slider'] = QSlider(Qt.Horizontal, self.parent)
        self.widgets['speed_slider'].setRange(-25, 25)
        self.widgets['speed_slider'].setValue(0)
        self.widgets['speed_slider'].valueChanged.connect(self._on_default_speed_changed)
        self.widgets['speed_slider'].setStyleSheet(self._get_slider_style("#44AADD"))
        
        # 添加+/-按钮
        self.widgets['speed_minus_button'] = QPushButton('-', self.parent)
        self.widgets['speed_minus_button'].clicked.connect(lambda: self._adjust_speed(-1))
        self.widgets['speed_minus_button'].setStyleSheet(self._get_button_style())
        
        self.widgets['speed_plus_button'] = QPushButton('+', self.parent)
        self.widgets['speed_plus_button'].clicked.connect(lambda: self._adjust_speed(1))
        self.widgets['speed_plus_button'].setStyleSheet(self._get_button_style())
        
        # 添加实时显示语速数值的标签
        self.widgets['speed_display_label'] = QLabel("0", self.parent)
        self.widgets['speed_display_label'].setAlignment(Qt.AlignCenter)
        
    def load_settings(self):
        """加载语速设置"""
        speed = self.settings_manager.get_default_speed()
        self.widgets['speed_slider'].setValue(speed)
        self.widgets['speed_display_label'].setText(str(speed))
        
    def resize_ui(self, width, height, n, m, scale_factor):
        """调整语速部分布局"""
        speed_y = int(6 * m)
        self.widgets['default_speed_label'].setGeometry(int(2 * n * scale_factor), speed_y, int(3 * n * scale_factor), int(m))
        
        # 语速控件布局
        button_size = int(0.8 * m)
        slider_width = int(6 * n * scale_factor)  # 增加滑动条宽度
        
        # 计算控件起始位置
        controls_start_x = int(6 * n * scale_factor)
        
        # 布局语速控件：[-] [滑动条] [数值] [+]
        self.widgets['speed_minus_button'].setGeometry(controls_start_x, speed_y, button_size, button_size)
        self.widgets['speed_slider'].setGeometry(controls_start_x + button_size + 5, speed_y, slider_width, int(m))
        
        # 数值显示在滑动条右侧
        display_label_width = int(1.5 * n * scale_factor)
        self.widgets['speed_display_label'].setGeometry(controls_start_x + button_size + slider_width + 10, speed_y, display_label_width, int(m))
        
        # +按钮在数值右侧
        self.widgets['speed_plus_button'].setGeometry(controls_start_x + button_size + slider_width + display_label_width + 15, speed_y, button_size, button_size)
        
    def update_fonts(self, font, small_font=None):
        """更新语速部分字体"""
        self.widgets['default_speed_label'].setFont(font)
        self.widgets['speed_minus_button'].setFont(font)
        self.widgets['speed_plus_button'].setFont(font)
        self.widgets['speed_display_label'].setFont(font)
        
    def _adjust_speed(self, delta):
        """调整语速"""
        current_value = self.widgets['speed_slider'].value()
        new_value = current_value + delta
        if self.widgets['speed_slider'].minimum() <= new_value <= self.widgets['speed_slider'].maximum():
            self.widgets['speed_slider'].setValue(new_value)
            
    def _on_default_speed_changed(self, value):
        """默认语速改变时的处理"""
        # 更新显示标签
        self.widgets['speed_display_label'].setText(str(value))
        
        success = self.settings_manager.set_default_speed(value)
        if not success:
            self.parent.parent_window.notification_manager.show_message("无法保存语速设置", "E", 5000)
            
    def _get_slider_style(self, color):
        """获取滑动条样式"""
        return f"""
        QSlider::groove:horizontal {{
            border: none;
            height: 12px;
            background: #FFFFFF;
            border-radius: 6px;
        }}
        
        QSlider::sub-page:horizontal {{
            background: {color};
            border-radius: 6px;
        }}
        
        QSlider::add-page:horizontal {{
            background: #FFFFFF;
            border-radius: 6px;
        }}
        
        QSlider::handle:horizontal {{
            background: #FFFFFF;
            border: 2px solid {color};
            width: 16px;
            margin: -6px 0;
            border-radius: 8px;
        }}
        
        QSlider::handle:horizontal:hover {{
            background: #F5F5F5;
        }}
        
        QSlider::handle:horizontal:pressed {{
            background: #E0E0E0;
        }}
        """
    
    def _get_button_style(self):
        """获取按钮样式"""
        return """
            QPushButton {
                font-family: "微软雅黑"; background-color: white; color: black;
                border: 2px solid gray; border-radius: 5px; font-weight: bold;
            }
            QPushButton:hover { background-color: #f0f0f0; }
        """


class AudioStretchSection(SettingsSection):
    """音频拉伸设置部分"""
    
    def __init__(self, parent, settings_manager):
        super().__init__(parent, settings_manager)
        
    def create_ui(self):
        """创建音频拉伸UI组件"""
        self.widgets['stretch_enable_checkbox'] = QCheckBox("启用音频拉伸", self.parent)
        self.widgets['stretch_enable_checkbox'].setChecked(False)  # 默认关闭
        self.widgets['stretch_enable_checkbox'].stateChanged.connect(self._on_stretch_enable_changed)
        
        # 音频拉伸数值标签
        self.widgets['audio_stretch_label'] = QLabel("1.00", self.parent)
        self.widgets['audio_stretch_label'].setAlignment(Qt.AlignCenter)
        
        self.widgets['stretch_slider'] = QSlider(Qt.Horizontal, self.parent)
        self.widgets['stretch_slider'].setRange(5, 200)  # 0.05倍到2.00倍，使用整数表示
        self.widgets['stretch_slider'].setValue(100)  # 默认1.0倍
        self.widgets['stretch_slider'].valueChanged.connect(self._on_stretch_factor_changed)
        self.widgets['stretch_slider'].setStyleSheet(self._get_slider_style("#FFA500"))
        
        # 添加+/-按钮
        self.widgets['stretch_minus_button'] = QPushButton('-', self.parent)
        self.widgets['stretch_minus_button'].clicked.connect(lambda: self._adjust_stretch(-0.01))
        self.widgets['stretch_minus_button'].setStyleSheet(self._get_button_style())
        
        self.widgets['stretch_plus_button'] = QPushButton('+', self.parent)
        self.widgets['stretch_plus_button'].clicked.connect(lambda: self._adjust_stretch(0.01))
        self.widgets['stretch_plus_button'].setStyleSheet(self._get_button_style())
        
        self.widgets['stretch_info_label'] = QLabel("(变速不变调，范围: 0.05倍 - 2.00倍)", self.parent)
        self.widgets['stretch_info_label'].setStyleSheet("color: #666666; font-size: 12px;")
        
        # 初始状态：禁用拉伸控件
        self._set_stretch_controls_enabled(False)
        
    def load_settings(self):
        """加载音频拉伸设置"""
        stretch_factor = self.settings_manager.get_stretch_factor()
        self.widgets['stretch_slider'].setValue(int(stretch_factor * 100))
        self.widgets['audio_stretch_label'].setText(f"{stretch_factor:.2f}")
        
        # 加载音频拉伸开关状态
        stretch_enabled = self.settings_manager.get_stretch_enabled()
        self.widgets['stretch_enable_checkbox'].setChecked(stretch_enabled)
        self._set_stretch_controls_enabled(stretch_enabled)
        
    def resize_ui(self, width, height, n, m, scale_factor):
        """调整音频拉伸部分布局"""
        stretch_y = int(7 * m)
        
        # 音频拉伸开关
        checkbox_width = int(3 * n * scale_factor)
        self.widgets['stretch_enable_checkbox'].setGeometry(int(2 * n * scale_factor), stretch_y, checkbox_width, int(m))
        
        # 布局拉伸控件：[-] [滑动条] [数值] [+]
        controls_start_x = int(6 * n * scale_factor)
        button_size = int(0.8 * m)
        slider_width = int(6 * n * scale_factor)
        display_label_width = int(1.5 * n * scale_factor)
        
        self.widgets['stretch_minus_button'].setGeometry(controls_start_x, stretch_y, button_size, button_size)
        self.widgets['stretch_slider'].setGeometry(controls_start_x + button_size + 5, stretch_y, slider_width, int(m))
        
        # 数值显示在滑动条右侧
        self.widgets['audio_stretch_label'].setGeometry(controls_start_x + button_size + slider_width + 10, stretch_y, display_label_width, int(m))
        
        # +按钮在数值右侧 - 确保可见
        self.widgets['stretch_plus_button'].setGeometry(controls_start_x + button_size + slider_width + display_label_width + 15, stretch_y, button_size, button_size)
        
        # 音频拉伸信息标签
        stretch_info_y = int(8 * m)
        self.widgets['stretch_info_label'].setGeometry(controls_start_x, stretch_info_y, int(8 * n * scale_factor), int(m))
        
    def update_fonts(self, font, small_font=None):
        """更新音频拉伸部分字体"""
        self.widgets['stretch_enable_checkbox'].setFont(font)
        self.widgets['audio_stretch_label'].setFont(font)
        self.widgets['stretch_minus_button'].setFont(font)
        self.widgets['stretch_plus_button'].setFont(font)
        if small_font:
            self.widgets['stretch_info_label'].setFont(small_font)
        
    def _adjust_stretch(self, delta):
        """调整拉伸倍数"""
        current_value = self.widgets['stretch_slider'].value() / 100.0
        new_value = current_value + delta
        if 0.05 <= new_value <= 2.00:
            self.widgets['stretch_slider'].setValue(int(new_value * 100))
            
    def _set_stretch_controls_enabled(self, enabled):
        """设置拉伸控件启用状态"""
        self.widgets['stretch_slider'].setEnabled(enabled)
        self.widgets['stretch_minus_button'].setEnabled(enabled)
        self.widgets['stretch_plus_button'].setEnabled(enabled)
        self.widgets['audio_stretch_label'].setEnabled(enabled)
        
    def _on_stretch_factor_changed(self, value):
        """音频拉伸倍数改变时的处理"""
        stretch_factor = value / 100.0
        # 更新显示标签
        self.widgets['audio_stretch_label'].setText(f"{stretch_factor:.2f}")
        
        # 更新主窗口配置
        if self.parent.parent_window:
            self.parent.parent_window.config.stretch_factor = stretch_factor
            
        # 保存设置
        success = self.settings_manager.set_stretch_factor(stretch_factor)
        if not success:
            self.parent.parent_window.notification_manager.show_message("无法保存音频拉伸设置", "E", 5000)
            
    def _on_stretch_enable_changed(self, state):
        """音频拉伸开关状态改变时的处理"""
        enabled = (state == Qt.Checked)
        self._set_stretch_controls_enabled(enabled)
        
        # 保存设置
        success = self.settings_manager.set_stretch_enabled(enabled)
        if not success:
            self.parent.parent_window.notification_manager.show_message("无法保存音频拉伸开关设置", "E", 5000)
            
    def _get_slider_style(self, color):
        """获取滑动条样式"""
        return f"""
        QSlider::groove:horizontal {{
            border: none;
            height: 12px;
            background: #FFFFFF;
            border-radius: 6px;
        }}
        
        QSlider::sub-page:horizontal {{
            background: {color};
            border-radius: 6px;
        }}
        
        QSlider::add-page:horizontal {{
            background: #FFFFFF;
            border-radius: 6px;
        }}
        
        QSlider::handle:horizontal {{
            background: #FFFFFF;
            border: 2px solid {color};
            width: 16px;
            margin: -6px 0;
            border-radius: 8px;
        }}
        
        QSlider::handle:horizontal:hover {{
            background: #F5F5F5;
        }}
        
        QSlider::handle:horizontal:pressed {{
            background: #E0E0E0;
        }}
        """
    
    def _get_button_style(self):
        """获取按钮样式"""
        return """
            QPushButton {
                font-family: "微软雅黑"; background-color: white; color: black;
                border: 2px solid gray; border-radius: 5px; font-weight: bold;
            }
            QPushButton:hover { background-color: #f0f0f0; }
        """


class GitHubAccelerationSection(SettingsSection):
    """GitHub下载加速设置部分"""
    
    def __init__(self, parent, settings_manager):
        super().__init__(parent, settings_manager)
        
    def create_ui(self):
        """创建GitHub下载加速UI组件"""
        self.widgets['github_acceleration_label'] = QLabel("GitHub下载加速", self.parent)
        
        self.widgets['github_acceleration_combo'] = QComboBox(self.parent)
        self.widgets['github_acceleration_combo'].addItems(CustomConfig.GITHUB_ACCELERATION_OPTIONS)
        self.widgets['github_acceleration_combo'].currentIndexChanged.connect(self._on_github_acceleration_changed)
        self.widgets['github_acceleration_combo'].setStyleSheet(self._get_combo_box_style())
        
    def load_settings(self):
        """加载GitHub下载加速设置"""
        acceleration_index = self.settings_manager.get_github_acceleration()
        if 0 <= acceleration_index < len(CustomConfig.GITHUB_ACCELERATION_OPTIONS):
            self.widgets['github_acceleration_combo'].setCurrentIndex(acceleration_index)
        
    def resize_ui(self, width, height, n, m, scale_factor):
        """调整GitHub下载加速部分布局"""
        github_y = int(9 * m)  # 放在音频拉伸设置下面
        self.widgets['github_acceleration_label'].setGeometry(int(2 * n * scale_factor), github_y, int(4 * n * scale_factor), int(m))
        self.widgets['github_acceleration_combo'].setGeometry(int(6 * n * scale_factor), github_y, int(8 * n * scale_factor), int(m))
        
    def update_fonts(self, font, small_font=None):
        """更新GitHub下载加速部分字体"""
        self.widgets['github_acceleration_label'].setFont(font)
        self.widgets['github_acceleration_combo'].setFont(font)
        
    def _on_github_acceleration_changed(self, index):
        """GitHub下载加速选项改变时的处理"""
        success = self.settings_manager.set_github_acceleration(index)
        if not success:
            self.parent.parent_window.notification_manager.show_message("无法保存GitHub下载加速设置", "E", 5000)
            
    def _get_combo_box_style(self):
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


class SettingsPage(QWidget):
    """设置页面 - 重构为模块化结构"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.settings_manager = SettingsManager()
        self.sections = []
        
        self._init_ui()
        
    def _init_ui(self):
        """初始化UI"""
        self._create_sections()
        self._load_all_settings()
        
    def _create_sections(self):
        """创建所有设置部分"""
        # 注册所有设置部分
        self.sections = [
            ApiKeySection(self, self.settings_manager),
            VoiceSection(self, self.settings_manager),
            SavePathSection(self, self.settings_manager),
            SpeedSection(self, self.settings_manager),
            AudioStretchSection(self, self.settings_manager),
            GitHubAccelerationSection(self, self.settings_manager)  # 新增GitHub下载加速部分
        ]
        
        # 创建各部分的UI
        for section in self.sections:
            section.create_ui()
            
    def _load_all_settings(self):
        """加载所有设置"""
        for section in self.sections:
            section.load_settings()
        
    def resizeEvent(self, event):
        """处理页面大小变化事件"""
        width = self.width()
        height = self.height()
        n = width / 16
        m = height / 16
        
        # 计算缩放因子，让出右侧10px空间
        scale_factor = (width - 10) / width
        
        # 调整所有部分的布局
        for section in self.sections:
            section.resize_ui(width, height, n, m, scale_factor)
            
        # 更新字体大小
        self._update_fonts()
        
        super().resizeEvent(event)
        
    def _update_fonts(self):
        """更新字体大小"""
        if not self.parent_window:
            return
            
        current_width = self.parent_window.width()
        current_height = self.parent_window.height()
        
        width_ratio = current_width / self.parent_window.default_width
        height_ratio = current_height / self.parent_window.default_height
        ratio = (width_ratio + height_ratio) / 2
        
        base_font_size = self.parent_window.min_font_size + (self.parent_window.max_font_size - self.parent_window.min_font_size) * (ratio - 1)
        base_font_size = max(self.parent_window.min_font_size, min(self.parent_window.max_font_size, base_font_size))
        
        other_font_size = int(base_font_size * 0.5)
        other_font = QFont("微软雅黑", other_font_size)
        
        small_font_size = int(other_font_size * 0.8)
        small_font = QFont("微软雅黑", small_font_size)
        
        # 更新所有部分的字体
        for section in self.sections:
            section.update_fonts(other_font, small_font)

if __name__ == "__main__":
    print(0)
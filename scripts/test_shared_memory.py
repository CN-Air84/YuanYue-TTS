#!/usr/bin/env python3
"""
测试共享内存信号广播机制
"""

import sys
import time
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt
from shared_memory_manager import get_shared_memory_manager

class TestSender(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("测试发送器")
        self.shared_manager = get_shared_memory_manager()
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout()
        
        self.label = QLabel("发送测试信号")
        layout.addWidget(self.label)
        
        btn_font = QPushButton("发送字体更改")
        btn_font.clicked.connect(self.send_font_change)
        layout.addWidget(btn_font)
        
        btn_theme = QPushButton("发送主题更改")
        btn_theme.clicked.connect(self.send_theme_change)
        layout.addWidget(btn_theme)
        
        btn_size = QPushButton("发送窗口尺寸更改")
        btn_size.clicked.connect(self.send_size_change)
        layout.addWidget(btn_size)
        
        btn_settings = QPushButton("发送设置更改")
        btn_settings.clicked.connect(self.send_settings_change)
        layout.addWidget(btn_settings)
        
        self.setLayout(layout)
    
    def send_font_change(self):
        font_data = {
            'family': '微软雅黑',
            'size': 14,
            'bold': False,
            'italic': False
        }
        self.shared_manager.broadcast_font_change(font_data)
        self.label.setText("字体信号已发送")
    
    def send_theme_change(self):
        theme_data = {
            'background_color': '#FF6B6B',
            'text_color': '#FFFFFF'
        }
        self.shared_manager.broadcast_theme_change(theme_data)
        self.label.setText("主题信号已发送")
    
    def send_size_change(self):
        self.shared_manager.broadcast_window_size_change(1200, 800)
        self.label.setText("窗口尺寸信号已发送")
    
    def send_settings_change(self):
        settings_data = {
            'window_width': 1200,
            'window_height': 800,
            'background_color': '#FF6B6B',
            'font_family': '微软雅黑',
            'font_size': 14
        }
        self.shared_manager.broadcast_settings_change('custom_page', settings_data)
        self.label.setText("设置信号已发送")

class TestReceiver(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("测试接收器")
        self.shared_manager = get_shared_memory_manager()
        self._init_ui()
        self._connect_shared_memory_signals()
    
    def _init_ui(self):
        layout = QVBoxLayout()
        
        self.label = QLabel("等待接收信号...")
        self.label.setStyleSheet("font-size: 16px; padding: 20px;")
        layout.addWidget(self.label)
        
        self.setLayout(layout)
    
    def _connect_shared_memory_signals(self):
        self.shared_manager.font_changed.connect(self.on_font_changed)
        self.shared_manager.theme_changed.connect(self.on_theme_changed)
        self.shared_manager.window_size_changed.connect(self.on_size_changed)
        self.shared_manager.settings_changed.connect(self.on_settings_changed)
    
    def on_font_changed(self, font_data):
        self.label.setText(f"收到字体更改: {font_data}")
        print(f"接收器：字体已更新 - {font_data}")
    
    def on_theme_changed(self, theme_data):
        self.label.setText(f"收到主题更改: {theme_data}")
        bg_color = theme_data.get('background_color', '#FFFFFF')
        self.setStyleSheet(f"background-color: {bg_color};")
        print(f"接收器：主题已更新 - {theme_data}")
    
    def on_size_changed(self, width, height):
        self.label.setText(f"收到窗口尺寸更改: {width}x{height}")
        print(f"接收器：窗口尺寸已更新 - {width}x{height}")
    
    def on_settings_changed(self, page_name, settings_data):
        self.label.setText(f"收到设置更改: {page_name} - {settings_data}")
        print(f"接收器：设置已更新 - {page_name} - {settings_data}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 创建发送器和接收器
    sender = TestSender()
    receiver = TestReceiver()
    
    # 显示窗口
    sender.show()
    receiver.show()
    
    print("测试程序已启动")
    print("点击发送器按钮来测试共享内存信号广播")
    
    sys.exit(app.exec_())
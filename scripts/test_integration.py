#!/usr/bin/env python3
"""
集成测试：验证各页面之间的共享内存信号通信
"""

import sys
import time
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, 
                             QWidget, QVBoxLayout, QLabel, QPushButton)
from PyQt5.QtCore import Qt
from shared_memory_manager import get_shared_memory_manager

# 模拟各个页面
class MockCustomPage(QWidget):
    def __init__(self):
        super().__init__()
        self.shared_manager = get_shared_memory_manager()
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout()
        self.label = QLabel("个性化页面 (信号发送者)")
        self.label.setStyleSheet("font-size: 16px; padding: 10px;")
        layout.addWidget(self.label)
        
        btn = QPushButton("发送设置更新信号")
        btn.clicked.connect(self.send_settings_update)
        layout.addWidget(btn)
        
        self.setLayout(layout)
    
    def send_settings_update(self):
        """模拟个性化页面发送设置更新"""
        settings_data = {
            'window_width': 1400,
            'window_height': 900,
            'background_color': '#4ECDC4',
            'font_family': 'Arial',
            'font_size': 16
        }
        self.shared_manager.broadcast_settings_change('custom_page', settings_data)
        self.label.setText("个性化页面：设置信号已发送！")

class MockGenerationPage(QWidget):
    def __init__(self):
        super().__init__()
        self.shared_manager = get_shared_memory_manager()
        self._init_ui()
        self._connect_shared_memory_signals()
    
    def _init_ui(self):
        layout = QVBoxLayout()
        self.label = QLabel("生成页面 (信号接收者)")
        self.label.setStyleSheet("font-size: 16px; padding: 10px;")
        layout.addWidget(self.label)
        
        self.status_label = QLabel("等待接收信号...")
        self.status_label.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
    
    def _connect_shared_memory_signals(self):
        self.shared_manager.font_changed.connect(self.on_font_changed)
        self.shared_manager.theme_changed.connect(self.on_theme_changed)
        self.shared_manager.window_size_changed.connect(self.on_size_changed)
        self.shared_manager.settings_changed.connect(self.on_settings_changed)
    
    def on_font_changed(self, font_data):
        self.status_label.setText(f"收到字体更改: {font_data.get('family', 'Unknown')}")
        print(f"生成页面：字体已更新 - {font_data}")
    
    def on_theme_changed(self, theme_data):
        bg_color = theme_data.get('background_color', '#FFFFFF')
        self.setStyleSheet(f"background-color: {bg_color};")
        self.status_label.setText(f"收到主题更改: {bg_color}")
        print(f"生成页面：主题已更新 - {theme_data}")
    
    def on_size_changed(self, width, height):
        self.status_label.setText(f"收到窗口尺寸: {width}x{height}")
        print(f"生成页面：窗口尺寸已更新 - {width}x{height}")
    
    def on_settings_changed(self, page_name, settings_data):
        self.status_label.setText(f"收到设置更改: {page_name}")
        print(f"生成页面：设置已更新 - {page_name} - {settings_data}")

class MockSettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.shared_manager = get_shared_memory_manager()
        self._init_ui()
        self._connect_shared_memory_signals()
    
    def _init_ui(self):
        layout = QVBoxLayout()
        self.label = QLabel("设置页面 (信号接收者)")
        self.label.setStyleSheet("font-size: 16px; padding: 10px;")
        layout.addWidget(self.label)
        
        self.status_label = QLabel("等待接收信号...")
        self.status_label.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
    
    def _connect_shared_memory_signals(self):
        self.shared_manager.font_changed.connect(self.on_font_changed)
        self.shared_manager.theme_changed.connect(self.on_theme_changed)
        self.shared_manager.window_size_changed.connect(self.on_size_changed)
        self.shared_manager.settings_changed.connect(self.on_settings_changed)
    
    def on_font_changed(self, font_data):
        self.status_label.setText(f"收到字体更改: {font_data.get('family', 'Unknown')}")
        print(f"设置页面：字体已更新 - {font_data}")
    
    def on_theme_changed(self, theme_data):
        bg_color = theme_data.get('background_color', '#FFFFFF')
        self.setStyleSheet(f"background-color: {bg_color};")
        self.status_label.setText(f"收到主题更改: {bg_color}")
        print(f"设置页面：主题已更新 - {theme_data}")
    
    def on_size_changed(self, width, height):
        self.status_label.setText(f"收到窗口尺寸: {width}x{height}")
        print(f"设置页面：窗口尺寸已更新 - {width}x{height}")
    
    def on_settings_changed(self, page_name, settings_data):
        self.status_label.setText(f"收到设置更改: {page_name}")
        print(f"设置页面：设置已更新 - {page_name} - {settings_data}")

class MockMiscPage(QWidget):
    def __init__(self):
        super().__init__()
        self.shared_manager = get_shared_memory_manager()
        self._init_ui()
        self._connect_shared_memory_signals()
    
    def _init_ui(self):
        layout = QVBoxLayout()
        self.label = QLabel("杂项页面 (信号接收者)")
        self.label.setStyleSheet("font-size: 16px; padding: 10px;")
        layout.addWidget(self.label)
        
        self.status_label = QLabel("等待接收信号...")
        self.status_label.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
    
    def _connect_shared_memory_signals(self):
        self.shared_manager.font_changed.connect(self.on_font_changed)
        self.shared_manager.theme_changed.connect(self.on_theme_changed)
        self.shared_manager.window_size_changed.connect(self.on_size_changed)
        self.shared_manager.settings_changed.connect(self.on_settings_changed)
    
    def on_font_changed(self, font_data):
        self.status_label.setText(f"收到字体更改: {font_data.get('family', 'Unknown')}")
        print(f"杂项页面：字体已更新 - {font_data}")
    
    def on_theme_changed(self, theme_data):
        bg_color = theme_data.get('background_color', '#FFFFFF')
        self.setStyleSheet(f"background-color: {bg_color};")
        self.status_label.setText(f"收到主题更改: {bg_color}")
        print(f"杂项页面：主题已更新 - {theme_data}")
    
    def on_size_changed(self, width, height):
        self.status_label.setText(f"收到窗口尺寸: {width}x{height}")
        print(f"杂项页面：窗口尺寸已更新 - {width}x{height}")
    
    def on_settings_changed(self, page_name, settings_data):
        self.status_label.setText(f"收到设置更改: {page_name}")
        print(f"杂项页面：设置已更新 - {page_name} - {settings_data}")

class IntegrationTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("共享内存信号广播集成测试")
        self.setGeometry(100, 100, 800, 600)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
        
        # 创建模拟页面
        self.custom_page = MockCustomPage()
        self.generation_page = MockGenerationPage()
        self.settings_page = MockSettingsPage()
        self.misc_page = MockMiscPage()
        
        # 添加到标签页
        self.tab_widget.addTab(self.custom_page, "个性化页面")
        self.tab_widget.addTab(self.generation_page, "生成页面")
        self.tab_widget.addTab(self.settings_page, "设置页面")
        self.tab_widget.addTab(self.misc_page, "杂项页面")
        
        print("集成测试已启动")
        print("切换到'个性化页面'标签，点击按钮发送测试信号")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = IntegrationTestWindow()
    window.show()
    
    sys.exit(app.exec_())
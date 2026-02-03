# coding=utf-8
import os
import time
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QCheckBox, QFileDialog, QMessageBox, QSpinBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

try:
    from misc_func import SettingsManager
    SETTINGS_AVAILABLE = True
except ImportError:
    SETTINGS_AVAILABLE = False

class MoreSettingsDialog(QDialog):
    """更多设置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("更多设置")
        self.setFixedSize(400, 300) # 设置固定大小
        
        if SETTINGS_AVAILABLE:
            self.global_font = SettingsManager().get_Custom_value('global_font', '微软雅黑')
            self.min_font_size = int(SettingsManager().get_Custom_value('min_font_size', '22'))
            self.max_font_size = int(SettingsManager().get_Custom_value('max_font_size', '42'))
        else:
            self.global_font = '微软雅黑'
            self.min_font_size = 22
            self.max_font_size = 42
        
        self.default_width = 1080
        self.default_height = 1080
        
        self._init_ui()
        self._update_fonts()
    
    def _init_ui(self):
        # 应用样式
        self._apply_styles()
        
        layout = QVBoxLayout()
        
        # UA输入框
        ua_layout = QHBoxLayout()
        ua_label = QLabel("User-Agent:")
        ua_label.setObjectName("ua_label")
        self.ua_edit = QLineEdit()
        self.ua_edit.setPlaceholderText("留空使用默认UA")
        ua_layout.addWidget(ua_label)
        ua_layout.addWidget(self.ua_edit)
        layout.addLayout(ua_layout)
        
        # 代理地址输入框
        proxy_layout = QHBoxLayout()
        proxy_label = QLabel("代理地址:")
        proxy_label.setObjectName("proxy_label")
        self.proxy_edit = QLineEdit()
        self.proxy_edit.setPlaceholderText("不推荐贸然修改  留空则不使用代理")
        proxy_layout.addWidget(proxy_label)
        proxy_layout.addWidget(self.proxy_edit)
        layout.addLayout(proxy_layout)
        
        # SSL验证复选框
        ssl_layout = QHBoxLayout()
        self.ssl_checkbox = QCheckBox("启用SSL验证")
        self.ssl_checkbox.setChecked(True)
        ssl_layout.addWidget(self.ssl_checkbox)
        ssl_layout.addStretch()
        layout.addLayout(ssl_layout)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("确定")
        self.cancel_button = QPushButton("取消")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def resizeEvent(self, event):
        """处理窗口大小变化事件"""
        self._update_fonts()
        super().resizeEvent(event)
    
    def _calculate_font_sizes(self):
        """计算字体大小"""
        # 优先参考主窗口的大小进行比例计算
        if self.parent_window:
            current_width = self.parent_window.width()
            current_height = self.parent_window.height()
        else:
            current_width = self.width()
            current_height = self.height()
        
        # 参考 generation_page 的计算逻辑
        default_width = 1080
        default_height = 720
        
        width_ratio = current_width / default_width
        height_ratio = current_height / default_height
        ratio = (width_ratio + height_ratio) / 2
        
        base_font_size = self.min_font_size + (self.max_font_size - self.min_font_size) * (ratio - 1)
        base_font_size = max(self.min_font_size, min(self.max_font_size, base_font_size))
        
        base_font_size = int(base_font_size)
        other_font_size = int(base_font_size * 0.5)
        return base_font_size, other_font_size
    
    def _update_fonts(self):
        """更新字体"""
        try:
            base_font_size, other_font_size = self._calculate_font_sizes()
            
            # 更新控件字体
            other_font = QFont(self.global_font, other_font_size)
            
            # 更新所有 QLabel, QLineEdit, QPushButton, QCheckBox
            for widget in self.findChildren((QLabel, QLineEdit, QPushButton, QCheckBox)):
                widget.setFont(other_font)
                
        except Exception as e:
            print(f"更新字体时出错: {e}")
    
    def _apply_styles(self):
        """应用与主界面一致的样式"""
        # 获取全局字体设置
        global_font = '微软雅黑'
        background_color = SettingsManager().get_Custom_value("background_color", "#E5E8EF") if SETTINGS_AVAILABLE else "#E5E8EF"
        
        # 优先从父窗口的设置管理器获取背景颜色（与主窗口保持一致）
        if self.parent_window and hasattr(self.parent_window, 'settings_manager'):
            try:
                background_color = self.parent_window.settings_manager.get_Custom_value("background_color", "#E5E8EF")
            except:
                pass
        
        # 尝试从共享内存管理器获取字体设置
        try:
            from shared_memory_manager import get_shared_memory_manager
            shared_manager = get_shared_memory_manager()
            if shared_manager and hasattr(shared_manager, 'current_settings'):
                global_font = shared_manager.current_settings.get('global_font', '微软雅黑')
        except ImportError:
            pass
        
        # 应用样式表
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {background_color};
            }}
            QPushButton {{
                font-family: "{global_font}";
                background-color: white;
                color: black;
                border: 2px solid gray;
                border-radius: 5px;
                font-weight: bold;
                padding: 5px;
                min-height: 25px;
            }}
            QPushButton:hover {{
                background-color: #f0f0f0;
            }}
            QPushButton:pressed {{
                background-color: #e0e0e0;
            }}
            QLabel {
                font-family: "{global_font}";
                font-size: 14px;
                color: black;
                background-color: transparent;
            }
            QLineEdit {{
                font-family: "{global_font}";
                background-color: white;
                color: black;
                border: 2px solid gray;
                border-radius: 10px;
                padding: 5px;
                min-height: 25px;
            }}
            QLineEdit:focus {{
                border: 2px solid #0078d4;
            }}
            QCheckBox {{
                font-family: "{global_font}";
                font-size: 14px;
                color: black;
                spacing: 5px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
            }}
            QCheckBox::indicator:unchecked {{
                border: 2px solid gray;
                background-color: white;
                border-radius: 3px;
            }}
            QCheckBox::indicator:checked {{
                border: 2px solid #0078d4;
                background-color: #0078d4;
                border-radius: 3px;
            }}
        """)
    
    def get_settings(self):
        """获取设置值"""
        user_agent = self.ua_edit.text().strip() or None
        proxy_text = self.proxy_edit.text().strip()
        verify_ssl = self.ssl_checkbox.isChecked()
        
        proxy = None
        if proxy_text:
            proxy = {
                "http": proxy_text,
                "https": proxy_text
            }
        
        return {
            "user_agent": user_agent,
            "proxy": proxy,
            "verify_ssl": verify_ssl
        }


class MultiThreadDownloadDialog(QDialog):
    """多线程下载主对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("多线程高速下载")
        self.setFixedSize(800, 450) # 设置固定大小，禁止用户调整尺寸
        
        if SETTINGS_AVAILABLE:
            self.global_font = SettingsManager().get_Custom_value('global_font', '微软雅黑')
            self.min_font_size = int(SettingsManager().get_Custom_value('min_font_size', '22'))
            self.max_font_size = int(SettingsManager().get_Custom_value('max_font_size', '42'))
        else:
            self.global_font = '微软雅黑'
            self.min_font_size = 22
            self.max_font_size = 42
        
        self.default_width = 1080
        self.default_height = 1080
        
        # 默认设置
        self.default_threads = 16
        self.default_save_path = os.path.expanduser("~/Downloads")
        
        # 更多设置
        self.more_settings = {}
        
        self._init_ui()
        self._update_fonts()
    
    def _init_ui(self):
        # 应用样式
        self._apply_styles()
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 下载链接
        url_label = QLabel("下载链接 (URL):")
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("在此粘贴下载链接...")
        layout.addWidget(url_label)
        layout.addWidget(self.url_edit)
        
        # 中间行：文件名、线程数、保存路径
        middle_layout = QHBoxLayout()
        middle_layout.setSpacing(20)
        
        # 1. 保存文件名
        filename_col = QVBoxLayout()
        filename_label = QLabel("保存文件名 (带后缀):")
        self.filename_edit = QLineEdit()
        self.filename_edit.setPlaceholderText("留空则自动提取")
        filename_col.addWidget(filename_label)
        filename_col.addWidget(self.filename_edit)
        middle_layout.addLayout(filename_col, 2) # 权重稍大
        
        # 2. 下载线程数
        thread_col = QVBoxLayout()
        thread_label = QLabel("下载线程数:")
        self.thread_spin = QSpinBox()
        self.thread_spin.setRange(1, 128)
        self.thread_spin.setValue(self.default_threads)
        self.thread_spin.setAlignment(Qt.AlignCenter)
        thread_col.addWidget(thread_label)
        thread_col.addWidget(self.thread_spin)
        middle_layout.addLayout(thread_col, 1)
        
        # 3. 保存路径
        path_col = QVBoxLayout()
        path_label = QLabel("保存路径:")
        path_input_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setText(self.default_save_path)
        self.browse_button = QPushButton("浏览")
        self.browse_button.clicked.connect(self._browse_save_path)
        path_input_layout.addWidget(self.path_edit)
        path_input_layout.addWidget(self.browse_button)
        path_col.addWidget(path_label)
        path_col.addLayout(path_input_layout)
        middle_layout.addLayout(path_col, 3) # 权重最大
        
        layout.addLayout(middle_layout)
        
        # 更多下载设置
        self.more_button = QPushButton("更多下载设置")
        self.more_button.clicked.connect(self._show_more_settings)
        layout.addWidget(self.more_button)
        
        # 底部按钮
        bottom_layout = QHBoxLayout()
        self.cancel_button = QPushButton("取消")
        self.download_button = QPushButton("开始下载")
        self.download_button.setObjectName("download_button") # 用于特殊样式
        
        self.cancel_button.clicked.connect(self.reject)
        self.download_button.clicked.connect(self._start_download)
        
        bottom_layout.addWidget(self.cancel_button)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.download_button, 1)
        layout.addLayout(bottom_layout)
        
        self.setLayout(layout)
    
    def resizeEvent(self, event):
        """处理窗口大小变化事件"""
        self._update_fonts()
        super().resizeEvent(event)
    
    def _calculate_font_sizes(self):
        """计算字体大小"""
        # 优先参考主窗口的大小进行比例计算
        if self.parent_window:
            current_width = self.parent_window.width()
            current_height = self.parent_window.height()
        else:
            current_width = self.width()
            current_height = self.height()
        
        # 参考 generation_page 的计算逻辑
        default_width = 1080
        default_height = 720
        
        width_ratio = current_width / default_width
        height_ratio = current_height / default_height
        ratio = (width_ratio + height_ratio) / 2
        
        base_font_size = self.min_font_size + (self.max_font_size - self.min_font_size) * (ratio - 1)
        base_font_size = max(self.min_font_size, min(self.max_font_size, base_font_size))
        
        base_font_size = int(base_font_size)
        other_font_size = int(base_font_size * 0.5)
        return base_font_size, other_font_size
    
    def _update_fonts(self):
        """更新字体"""
        try:
            base_font_size, other_font_size = self._calculate_font_sizes()
            
            # 获取字体名称
            font_name = self.global_font
            
            # 更新控件字体
            other_font = QFont(font_name, other_font_size)
            
            # 更新所有子控件字体
            for widget in self.findChildren((QLabel, QLineEdit, QSpinBox, QPushButton, QCheckBox)):
                widget.setFont(other_font)
                    
        except Exception as e:
            print(f"更新字体时出错: {e}")
    
    def _apply_styles(self):
        """应用与主界面一致的样式"""
        # 获取全局字体设置
        background_color = "#E5E8EF"
        
        # 优先从父窗口的设置管理器获取背景颜色（与主窗口保持一致）
        if self.parent_window and hasattr(self.parent_window, 'settings_manager'):
            try:
                background_color = self.parent_window.settings_manager.get_Custom_value("background_color", "#E5E8EF")
            except:
                pass
        elif SETTINGS_AVAILABLE:
            # 如果没有父窗口，则尝试直接从设置管理器获取
            try:
                settings_manager = SettingsManager()
                background_color = settings_manager.get_Custom_value("background_color", "#E5E8EF")
            except:
                pass
        
        # 应用样式表
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {background_color};
            }}
            QPushButton {{
                font-family: "{self.global_font}";
                background-color: white;
                color: black;
                border: 2px solid #A0A0A0;
                border-radius: 8px;
                font-weight: bold;
                padding: 8px 15px;
                min-height: 35px;
            }}
            QPushButton:hover {{
                background-color: #F5F5F5;
                border: 2px solid #808080;
            }}
            QPushButton:pressed {{
                background-color: #E0E0E0;
            }}
            QPushButton#download_button {{
                min-width: 200px;
                background-color: white;
            }}
            QLabel {{
                font-family: "{self.global_font}";
                font-weight: bold;
                color: #202020;
                margin-top: 5px;
                background-color: transparent;
            }}
            QLineEdit {{
                font-family: "{self.global_font}";
                background-color: white;
                color: black;
                border: 2px solid #A0A0A0;
                border-radius: 8px;
                padding: 5px 10px;
                min-height: 35px;
            }}
            QLineEdit:focus {{
                border: 2px solid #0078D4;
            }}
            QSpinBox {{
                font-family: "{self.global_font}";
                background-color: white;
                color: black;
                border: 2px solid #A0A0A0;
                border-radius: 8px;
                padding: 5px;
                min-height: 35px;
                min-width: 80px;
            }}
            QSpinBox:focus {{
                border: 2px solid #0078D4;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 25px;
                border-left: 1px solid #A0A0A0;
            }}
        """)
    
    def _browse_save_path(self):
        """浏览保存路径"""
        path = QFileDialog.getExistingDirectory(self, "选择保存路径", self.path_edit.text())
        if path:
            self.path_edit.setText(path)
    
    def _show_more_settings(self):
        """显示更多设置对话框"""
        dialog = MoreSettingsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.more_settings = dialog.get_settings()
    
    def _start_download(self):
        """开始下载"""
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "错误", "请输入下载链接")
            return
        
        # 获取线程数
        thread_num = self.thread_spin.value()
        
        # 获取文件名
        filename = self.filename_edit.text().strip()
        
        # 获取保存路径
        save_path = self.path_edit.text().strip() or self.default_save_path
        
        # 创建目录（如果不存在）
        try:
            os.makedirs(save_path, exist_ok=True)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法创建保存目录: {str(e)}")
            return
        
        # 获取文件名
        filename = self.filename_edit.text().strip()
        if not filename:
            # 尝试从URL提取文件名
            filename = url.split('/')[-1].split('?')[0]
            if not filename:
                filename = f"download_{int(time.time())}"
        
        # 导入多线程下载器
        try:
            from multi_thread_downloader import download
            
            # 开始下载
            success = download(
                url=url,
                save_dir=save_path,
                filename=filename,
                thread_num=thread_num,
                user_agent=self.more_settings.get('user_agent'),
                verify_ssl=self.more_settings.get('verify_ssl', True),
                proxy=self.more_settings.get('proxy')
            )
            
            if success:
                QMessageBox.information(self, "成功", "下载完成！")
                self.accept()
            else:
                QMessageBox.warning(self, "失败", "下载失败，请检查链接和网络设置")
                
        except ImportError:
            QMessageBox.critical(self, "错误", "多线程下载模块未找到")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"下载过程中发生错误: {str(e)}")

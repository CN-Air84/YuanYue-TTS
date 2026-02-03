# coding=utf-8
"""
杂项功能页面模块
提供AI OCR、PDF下载、多线程下载等辅助功能
"""

import sys
import os
import base64
import requests
import time
import zipfile
import subprocess
from PyQt5.QtWidgets import (
    QWidget, QPushButton, QGridLayout, QMessageBox, QApplication,
    QDialog, QVBoxLayout, QTextEdit, QFileDialog, QLabel, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QLineEdit, QCheckBox, QTabWidget, QTableWidget, QTableWidgetItem
)
try:
    from multi_thread_downloader import download
except ImportError:
    download = None
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl, QTimer
from PyQt5.QtGui import QFont, QPixmap, QDesktopServices
import certifi
from shared_memory_manager import get_shared_memory_manager

# 导入拆分后的子页面
from mp_ai_ocr import AIOCRWorker, TextResultDialog
from mp_pdf_download import PDFDownloadDialog
from mp_about import AboutDialog
from mp_license import LicenseDialog
from mp_resource_download import ResourceDownloadDialog
from mp_multi_thread_download import MultiThreadDownloadDialog


# ===== 常量定义 =====
# 界面字体大小和窗口尺寸常量
MIN_FONT_SIZE = 22
MAX_FONT_SIZE = 42
DEFAULT_WIDTH = 1080
DEFAULT_HEIGHT = 1080
# ===== 常量定义结束 =====

try:
    from docxfix import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    from misc_func import SettingsManager
    SETTINGS_AVAILABLE = True
except ImportError:
    SETTINGS_AVAILABLE = False

try:
    from iw_dialogs import LoadingDialog
    DIALOGS_AVAILABLE = True
except ImportError:
    DIALOGS_AVAILABLE = False


class MiscPage(QWidget):
    """杂项功能页面 - 提供各种辅助工具功能"""
    
    def __init__(self, parent=None):
        """
        初始化杂项功能页面
        
        Args:
            parent: 父窗口
        """
        super().__init__(parent)
        self.parent_window = parent
        
        from misc_func import SettingsManager
        settings_manager = SettingsManager()
        self.global_font = settings_manager.get_Custom_value('global_font', '微软雅黑')
        self.min_font_size = int(settings_manager.get_Custom_value('min_font_size', '22'))
        self.max_font_size = int(settings_manager.get_Custom_value('max_font_size', '42'))
        self.background_color = settings_manager.get_Custom_value('background_color', '#E5E8EF')
        self.text_color = settings_manager.get_Custom_value('text_color', '#333333')
        
        self.setStyleSheet(f"""
            QWidget {{background-color: {self.background_color}; color: {self.text_color};}}
            QPushButton {{font-family: "{self.global_font}";}}
        """)
        
        self.shared_manager = get_shared_memory_manager()
        self._connect_shared_memory_signals()
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化用户界面"""
        self._create_buttons()
        self._setup_layout()
        self._update_fonts()
    
    def _create_buttons(self):
        """创建功能按钮"""
        self.buttons = []
        
        button_configs = [
            ("AI图片OCR", self._on_ai_image_ocr),
            ("PDF电子书下载", self._on_pdf_ebook_download), 
            ("资源下载", self._on_resource_download),
            ("关于", self._on_about),
            ("多线程下载", self._on_multi_thread_download),
            ("预留6", self._on_reserved_function),
            ("预留7", self._on_reserved_function),
            ("预留8", self._on_reserved_function),
            ("许可协议", self._on_license_agreement)
        ]
        
        for text, slot in button_configs:
            button = QPushButton(text, self)
            button.clicked.connect(slot)
            button.setStyleSheet(self._get_button_style())
            self.buttons.append(button)
    
    def _setup_layout(self):
        """设置页面布局"""
        layout = QGridLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(50, 50, 50, 50)
        
        positions = [(i, j) for i in range(3) for j in range(3)]
        
        for position, button in zip(positions, self.buttons):
            layout.addWidget(button, *position)
        
        self.setLayout(layout)
    
    def _get_button_style(self):
        """获取按钮样式"""
        return f"""
            QPushButton {{
                font-family: "{self.global_font}"; 
                background-color: white; 
                color: {self.text_color};
                border: 3px solid gray; 
                border-radius: 15px;
                font-weight: bold;
                min-height: 80px;
            }}
            QPushButton:hover {{
                background-color: #f0f0f0;
                border: 3px solid #444444;
            }}
            QPushButton:pressed {{
                background-color: #e0e0e0;
            }}
        """
    
    def _update_fonts(self):
        """更新界面字体大小"""
        if not self.parent_window:
            return
            
        current_width = self.parent_window.width()
        current_height = self.parent_window.height()
        
        DEFAULT_WIDTH = 1080
        DEFAULT_HEIGHT = 1080
        MIN_FONT_SIZE = self.min_font_size
        MAX_FONT_SIZE = self.max_font_size
        
        width_ratio = current_width / DEFAULT_WIDTH
        height_ratio = current_height / DEFAULT_HEIGHT
        ratio = (width_ratio + height_ratio) / 2
        
        base_font_size = (MIN_FONT_SIZE + 
                         (MAX_FONT_SIZE - MIN_FONT_SIZE) * (ratio - 1))
        base_font_size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, base_font_size))
        
        base_font_size = int(base_font_size)
        button_font_size = int(base_font_size * 0.6)
        button_font = QFont(self.global_font, button_font_size)
        
        for button in self.buttons:
            button.setFont(button_font)
    
    def resizeEvent(self, event):
        """处理窗口大小变化事件"""
        self._update_fonts()
        super().resizeEvent(event)
    
    def _on_ai_image_ocr(self):
        """处理AI图片OCR功能"""
        if not SETTINGS_AVAILABLE:
            QMessageBox.warning(self, "错误", "设置管理器不可用")
            return
        
        settings_manager = SettingsManager()
        api_key = settings_manager.get_api_key("api_key_ChatGLM")
        if not api_key:
            QMessageBox.warning(self, "提示", "请先在设置中配置ChatGLM API Key")
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "", "图片文件 (*.png *.jpg *.jpeg *.webp)"
        )
        
        if not file_path:
            return
        
        loading_dialog = LoadingDialog(self) if DIALOGS_AVAILABLE else None
        if loading_dialog:
            loading_dialog.text_label.setText("正在识别图片文字...")
            loading_dialog.show()
            QApplication.processEvents()
        
        self.ai_worker = AIOCRWorker(api_key, file_path)
        self.ai_worker.finished_signal.connect(
            lambda text: self._on_ai_ocr_finished(text, loading_dialog)
        )
        self.ai_worker.error_signal.connect(
            lambda error: self._on_ai_ocr_error(error, loading_dialog)
        )
        self.ai_worker.start()
    
    def _on_ai_ocr_finished(self, text, loading_dialog):
        """
        处理AI OCR完成事件
        
        Args:
            text (str): OCR识别结果
            loading_dialog: 加载对话框
        """
        if loading_dialog:
            loading_dialog.close()
        
        if text:
            dialog = TextResultDialog(self, "AI图片OCR结果", text)
            dialog.exec_()
        else:
            QMessageBox.warning(self, "提示", "未识别到文字")
    
    def _on_ai_ocr_error(self, error, loading_dialog):
        """
        处理AI OCR错误事件
        
        Args:
            error (str): 错误信息
            loading_dialog: 加载对话框
        """
        if loading_dialog:
            loading_dialog.close()
        QMessageBox.critical(self, "错误", error)
    
    def _on_pdf_ebook_download(self):
        """处理PDF电子书下载功能"""
        if self.parent_window:
            window_rect = self.parent_window.geometry()
            dialog = PDFDownloadDialog(self, window_rect)
            dialog.exec_()
    
    def _on_about(self):
        """处理关于功能"""
        dialog = AboutDialog(self)
        dialog.exec_()
    
    def _on_license_agreement(self):
        """处理许可协议功能"""
        dialog = LicenseDialog(self)
        dialog.exec_()
    
    def _on_resource_download(self):
        """资源下载功能"""
        try:
            self.resource_info = self._fetch_resource_list()
            if self.resource_info:
                dialog = ResourceDownloadDialog(self, self.resource_info)
                dialog.exec_()
            else:
                QMessageBox.warning(self, "提示", "未能获取到资源列表")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"获取资源列表失败: {str(e)}")

    def _fetch_resource_list(self):
        """从远程获取资源列表"""
        url = "https://cn-air84.github.io/YuanYue-TTS/res/resList.txt"
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        resource_info = []
        for line in response.text.strip().split('\n'):
            line = line.strip()
            if not line:
                continue

            try:
                at_pos = line.find('@{')
                if at_pos == -1:
                    continue

                close_brace_pos = line.find('}', at_pos)
                if close_brace_pos == -1:
                    continue

                url_str = line[at_pos + 2:close_brace_pos]

                import urllib.parse
                try:
                    url_str = urllib.parse.unquote(url_str)
                except:
                    pass

                name_end = line.find(']')
                if name_end == -1 or name_end > at_pos:
                    continue

                name_part = line[1:name_end]

                desc_start = name_end + 1
                if line[desc_start:desc_start + 1] == '@':
                    desc_start += 1
                desc_part = line[desc_start:at_pos]

                task = None
                task_start = line.find('<', close_brace_pos)
                if task_start != -1 and task_start + 1 < len(line):
                    task_end = line.find('>', task_start)
                    if task_end != -1:
                        task_str = line[task_start + 1:task_end]
                        if task_str.startswith('UnzipTo '):
                            target_path = task_str[8:]
                            if target_path.startswith('./'):
                                target_path = target_path[2:]
                            if target_path.endswith('/'):
                                target_path = target_path[:-1]
                            task = {'type': 'UnzipTo', 'path': target_path}

                resource_info.append({
                    'name': name_part,
                    'desc': desc_part,
                    'url': url_str,
                    'task': task
                })
            except Exception:
                continue

        return resource_info

    def _get_github_accelerated_url(self, original_url):
        """根据加速选项获取下载URL"""
        github_mirror = "直接从github服务器获取（海外首选）"
        if SETTINGS_AVAILABLE:
            github_mirror = SettingsManager().get_Custom_value('github_mirror', '直接从github服务器获取（海外首选）')
            print(f"[DEBUG] GitHub mirror setting: {github_mirror}")

        mirror_mapping = {
            "直接从github服务器获取（海外首选）": 0,
            "ghfast（中国大陆首选）": 1,
            "ghproxy 主站（CloudFlare CDN，大陆备用）": 2,
            "ghproxy HK（港澳台首选）": 3,
            "ghproxy edgeone（备用）": 4
        }

        github_acceleration = mirror_mapping.get(github_mirror, 0)

        if 'github.com' in original_url and github_acceleration > 0:
            if github_acceleration == 1:  # ghfast镜像
                return f"https://ghfast.top/{original_url}"
            elif github_acceleration == 2:  # ghproxy主站
                return f"https://gh-proxy.org/{original_url}"
            elif github_acceleration == 3:  # ghproxy HK
                return f"https://hk.gh-proxy.org/{original_url}"
            elif github_acceleration == 4:  # ghproxy edgeone
                return f"https://edgeone.gh-proxy.org/{original_url}"

        return original_url
    
    def _on_multi_thread_download(self):
        """处理多线程下载功能"""
        dialog = MultiThreadDownloadDialog(self)
        dialog.exec_()
    
    def _on_reserved_function(self):
        """处理预留功能"""
        button = self.sender()
        if button:
            msg = QMessageBox(self)
            msg.setWindowTitle("功能预留")
            msg.setText(f"还不知道要做什么……\n要是有啥好点子可以来github交个PR/issue，\n感谢您的支持")
            msg.setIcon(QMessageBox.Information)
            msg.setStyleSheet(f"QMessageBox {{ background-color: {self.background_color}; }} QLabel {{ background-color: transparent; }}")
            msg.exec_()
    
    def _connect_shared_memory_signals(self):
        """连接共享内存信号"""
        # 连接字体变化信号
        self.shared_manager.font_changed.connect(self._on_font_changed_from_shared_memory)
        
        # 连接主题变化信号
        self.shared_manager.theme_changed.connect(self._on_theme_changed_from_shared_memory)
        
        # 连接窗口大小变化信号
        self.shared_manager.window_size_changed.connect(self._on_window_size_changed_from_shared_memory)
        
        # 连接设置变化信号
        self.shared_manager.settings_changed.connect(self._on_settings_changed_from_shared_memory)
    
    def _on_font_changed_from_shared_memory(self, font_data):
        """从共享内存接收字体变化"""
        self._update_fonts()
    
    def _on_theme_changed_from_shared_memory(self, theme_data):
        """从共享内存接收主题变化"""
        # 这里可以添加主题更新的具体逻辑
    
    def _on_window_size_changed_from_shared_memory(self, width, height):
        """从共享内存接收窗口大小变化"""
        self._update_fonts()
    
    def _on_settings_changed_from_shared_memory(self, page_name, settings_data):
        """从共享内存接收设置变化"""
        if page_name in ['custom', 'custom_page']:
            # 更新背景颜色
            if 'background_color' in settings_data:
                self.background_color = settings_data['background_color']
                self.setStyleSheet(f"""
                    QWidget {{background-color: {self.background_color}; color: {self.text_color};}}
                    QPushButton {{font-family: "{self.global_font}";}}
                """)
            
            # 更新文字颜色
            if 'text_color' in settings_data:
                self.text_color = settings_data['text_color']
                self.setStyleSheet(f"""
                    QWidget {{background-color: {self.background_color}; color: {self.text_color};}}
                    QPushButton {{font-family: "{self.global_font}";}}
                """)
                # 更新所有按钮样式
                for button in self.buttons:
                    button.setStyleSheet(self._get_button_style())
            
            # 如果有全局字体更新，也可以在这里处理
            if 'global_font' in settings_data:
                self.global_font = settings_data['global_font']
                self._update_fonts()

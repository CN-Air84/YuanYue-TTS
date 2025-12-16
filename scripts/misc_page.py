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
from PyQt5.QtWidgets import (
    QWidget, QPushButton, QGridLayout, QMessageBox, QApplication,
    QDialog, QVBoxLayout, QTextEdit, QFileDialog, QLabel, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QLineEdit, QCheckBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt5.QtGui import QFont, QPixmap, QDesktopServices
import certifi
from shared_memory_manager import get_shared_memory_manager


# ===== 常量定义 =====
# 关于页面图片URL
ABOUT_IMAGE_URLS = [
    'https://avatars.githubusercontent.com/u/80259542?s=48&v=4',
    'https://avatars.githubusercontent.com/u/80259542?s=48&v=4',
    'https://avatars.githubusercontent.com/u/80259542?s=48&v=4'
]

# 关于页面按钮文字和链接
ABOUT_BUTTON_TEXTS = ["", "", "GitHub项目主页", "Github更新",'','']
ABOUT_BUTTON_URLS = [
    "",
    "",
    "https://github.com/CN-Air84/YuanYue-TTS",
    "https://github.com/CN-Air84/YuanYue-TTS/releases",
    "",
    ""
]

# 界面字体大小和窗口尺寸常量
MIN_FONT_SIZE = 22
MAX_FONT_SIZE = 42
DEFAULT_WIDTH = 1080
DEFAULT_HEIGHT = 720
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


class AIOCRWorker(QThread):
    """AI OCR工作线程类 - 使用ChatGLM进行图片文字识别"""
    
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    
    def __init__(self, api_key, image_path):
        """
        初始化AI OCR工作线程
        
        Args:
            api_key (str): ChatGLM API密钥
            image_path (str): 图片文件路径
        """
        super().__init__()
        self.api_key = api_key
        self.image_path = image_path
    
    def run(self):
        """执行AI OCR识别任务"""
        try:
            from openai import OpenAI
            
            client = OpenAI(
                api_key=self.api_key,
                base_url="https://open.bigmodel.cn/api/paas/v4/"
            )
            
            def encode_image(image_path):
                """将图片编码为base64格式"""
                with open(image_path, "rb") as image_file:
                    return base64.b64encode(image_file.read()).decode('utf-8')
            
            base64_image = encode_image(self.image_path)
            
            prompt = "请提取这张图片中的所有文字内容，输出纯文字格式。"
            
            response = client.chat.completions.create(
                model="glm-4v-flash",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                        ]
                    }
                ],
                max_tokens=1000
            )
            result = response.choices[0].message.content
            self.finished_signal.emit(result)
            
        except Exception as e:
            self.error_signal.emit(f"AI识别失败: {str(e)}")


class TextResultDialog(QDialog):
    """文本结果显示对话框 - 用于显示OCR和文档提取的结果"""
    
    def __init__(self, parent=None, title="文本提取结果", content=""):
        """
        初始化文本结果显示对话框
        
        Args:
            parent: 父窗口
            title (str): 对话框标题
            content (str): 显示的文本内容
        """
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle(title)
        self.resize(600, 400)
        
        layout = QVBoxLayout()
        
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(content)
        
        # 从共享内存管理器获取字体设置
        shared_manager = get_shared_memory_manager()
        if shared_manager and hasattr(shared_manager, 'current_settings'):
            global_font = shared_manager.current_settings.get('global_font', '微软雅黑')
        else:
            global_font = '微软雅黑'
            
        self.text_edit.setStyleSheet(f"""
        QTextEdit {{
            background-color: white;
            color: black;
            border: 2px solid gray;
            border-radius: 10px;
            font-family: "{global_font}";
            font-size: 12px;
            }}
        """)

        layout.addWidget(self.text_edit)
        
        button_layout = QHBoxLayout()
        
        self.copy_button = QPushButton("复制结果")
        self.copy_button.setStyleSheet(f"""
            QPushButton {{
            font-family: "{global_font}";
            background-color: white;
            color: black;
            border: 2px solid gray;
            border-radius: 5px;
            padding: 5px 10px;
            font-weight: bold;
            }}
            QPushButton:hover {{
            background-color: #f0f0f0;
            }}
        """)

        self.copy_button.clicked.connect(self.copy_text)
        
        self.close_button = QPushButton("关闭")
        self.close_button.setStyleSheet(f"""
            QPushButton {{
            font-family: "{global_font}";
            background-color: white;
            color: black;
            border: 2px solid gray;
            border-radius: 5px;
            padding: 5px 10px;
            font-weight: bold;
            }}
            QPushButton:hover {{
            background-color: #f0f0f0;
            }}
        """)
        self.close_button.clicked.connect(self.accept)
        
        button_layout.addWidget(self.copy_button)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        self._update_fonts()
    
    def _update_fonts(self):
        """更新界面字体大小"""
        if not self.parent_window:
            return
            
        current_width = self.width()
        current_height = self.height()
        
        width_ratio = current_width / DEFAULT_WIDTH
        height_ratio = current_height / DEFAULT_HEIGHT
        ratio = (width_ratio + height_ratio) / 2
        
        base_font_size = (MIN_FONT_SIZE + 
                         (MAX_FONT_SIZE - MIN_FONT_SIZE) * (ratio - 1))
        base_font_size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, base_font_size))
        
        base_font_size = int(base_font_size)
        button_font_size = int(base_font_size * 0.5)
        
        # 从共享内存管理器获取字体设置
        shared_manager = get_shared_memory_manager()
        if shared_manager and hasattr(shared_manager, 'current_settings'):
            global_font = shared_manager.current_settings.get('global_font', '微软雅黑')
        else:
            global_font = '微软雅黑'
            
        button_font = QFont(global_font, button_font_size)

        
        self.copy_button.setFont(button_font)
        self.close_button.setFont(button_font)
    
    def resizeEvent(self, event):
        """处理窗口大小变化事件"""
        self._update_fonts()
        super().resizeEvent(event)
    
    def _connect_shared_memory_signals(self):
        """连接共享内存信号"""
        # 连接字体更改信号
        self.shared_manager.font_changed.connect(self._on_font_changed_from_shared_memory)
        # 连接主题更改信号
        self.shared_manager.theme_changed.connect(self._on_theme_changed_from_shared_memory)
        # 连接窗口尺寸更改信号
        self.shared_manager.window_size_changed.connect(self._on_window_size_changed_from_shared_memory)
        # 连接设置更改信号
        self.shared_manager.settings_changed.connect(self._on_settings_changed_from_shared_memory)
    
    def _on_font_changed_from_shared_memory(self, font_data):
        """从共享内存接收字体更改"""
        try:
            # 更新字体设置
            self._update_fonts()
        except Exception as e:
            pass
    
    def _on_theme_changed_from_shared_memory(self, theme_data):
        """从共享内存接收主题更改"""
        try:
            # 应用背景颜色
            bg_color = theme_data.get('background_color', '#E5E8EF')
            self.setStyleSheet(f"background-color: {bg_color};")
        except Exception as e:
            pass
    
    def _on_window_size_changed_from_shared_memory(self, width, height):
        """从共享内存接收窗口尺寸更改"""
        try:
            # 重新布局控件
            if hasattr(self, 'resizeEvent'):
                # 触发重新布局
                self.resize(self.width(), self.height())
        except Exception as e:
            pass
    
    def _on_settings_changed_from_shared_memory(self, page_name, settings_data):
        """从共享内存接收设置更改"""
        try:
            if page_name == 'custom_page':
                # 如果是来自个性化页面的设置更改，更新相关设置
                # 重新加载页面以应用新设置
                self._reload_page(settings_data)
        except Exception as e:
            pass
    
    def _reload_page(self, settings_data=None):
        """重新加载页面以应用最新设置"""
        try:
            # 更新字体
            self._update_fonts()
            
            # 更新主题样式
            if settings_data:
                bg_color = settings_data.get('background_color', '#E5E8EF')
                self.setStyleSheet(f"background-color: {bg_color};")
            
            # 重新布局控件（触发resize事件）
            if hasattr(self, 'resizeEvent'):
                self.resize(self.width(), self.height())
        except Exception as e:
            pass
    
    def copy_text(self):
        """复制文本到剪贴板"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.text_edit.toPlainText())
        QMessageBox.information(self, "成功", "文本已复制到剪贴板")


class PDFDownloadDialog(QDialog):
    """PDF电子书下载对话框 - 从GitHub仓库下载PDF文件"""
    
    def __init__(self, parent=None, window_size=None):
        """
        初始化PDF下载对话框
        
        Args:
            parent: 父窗口
            window_size: 窗口尺寸
        """
        super().__init__(parent)
        self.parent_window = parent
        self.window_size = window_size
        self.selected_file_info = None
        self.selected_pdf_name = None
        self.settings_manager = SettingsManager() if SETTINGS_AVAILABLE else None
        self.current_path = ""
        self.path_history = []
        
        self.init_ui()
        self.load_root_directory()
        self._update_fonts()
    
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("PDF电子书下载")
        if self.window_size:
            self.setGeometry(self.window_size)
        else:
            self.resize(800, 600)
        
        # 从共享内存管理器获取字体设置
        shared_manager = get_shared_memory_manager()
        if shared_manager and hasattr(shared_manager, 'current_settings'):
            global_font = shared_manager.current_settings.get('global_font', '微软雅黑')
        else:
            global_font = '微软雅黑'
            
        self.setStyleSheet(f"""
        QDialog {{background-color: #E5E8EF;}}
        QPushButton {{
            font-family: "{global_font}"; background-color: white; color: black;
            border: 2px solid gray; border-radius: 5px; font-weight: bold; padding: 5px;
        }}
        QPushButton:hover {{background-color: #f0f0f0;}}
        QLabel {{font-family: "{global_font}"; font-size: 14px;}}
        QLineEdit {{
            font-family: "{global_font}"; background-color: white; color: black;
            border: 2px solid gray; border-radius: 10px; padding: 5px;
        }}
        QTreeWidget {{
            font-family: "{global_font}"; background-color: white; color: black;
            border: 2px solid gray; border-radius: 5px;
        }}
        """)

        
        main_layout = QVBoxLayout()
        
        nav_layout = QHBoxLayout()
        
        self.back_button = QPushButton("返回上级", self)
        self.back_button.clicked.connect(self.go_back)
        self.back_button.setEnabled(False)
        
        self.path_label = QLabel("当前路径: /")
        
        self.refresh_button = QPushButton("刷新", self)
        self.refresh_button.clicked.connect(self.refresh_current_directory)
        
        nav_layout.addWidget(self.back_button)
        nav_layout.addWidget(self.path_label)
        nav_layout.addStretch()
        nav_layout.addWidget(self.refresh_button)
        
        main_layout.addLayout(nav_layout)
        
        self.tree_widget = QTreeWidget(self)
        self.tree_widget.setHeaderLabels(["名称", "类型", "大小"])
        self.tree_widget.setColumnWidth(0, 400)
        self.tree_widget.setColumnWidth(1, 100)
        self.tree_widget.setColumnWidth(2, 100)
        self.tree_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        
        main_layout.addWidget(self.tree_widget)
        
        bottom_layout = QHBoxLayout()
        
        self.save_path_label = QLabel("保存路径:")
        self.save_path_input = QLineEdit()
        self.save_path_input.setPlaceholderText("选择或输入保存路径...")
        self.save_path_input.setMaximumWidth(200)
        
        self.browse_button = QPushButton("浏览")
        self.browse_button.clicked.connect(self.browse_save_path)
        
        bottom_layout.addWidget(self.save_path_label)
        bottom_layout.addWidget(self.save_path_input)
        bottom_layout.addWidget(self.browse_button)
        
        main_layout.addLayout(bottom_layout)
        
        button_layout = QHBoxLayout()
        self.cancel_button = QPushButton("取消", self)
        self.cancel_button.clicked.connect(self.reject)
        
        self.download_button = QPushButton("确认下载", self)
        self.download_button.clicked.connect(self.download_pdf)
        self.download_button.setEnabled(False)
        
        button_layout.addWidget(self.cancel_button)
        button_layout.addStretch()
        button_layout.addWidget(self.download_button)
        
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)
    
    def _update_fonts(self):
        """更新界面字体大小"""
        if not self.parent_window:
            return
            
        current_width = self.width()
        current_height = self.height()
        
        width_ratio = current_width / DEFAULT_WIDTH
        height_ratio = current_height / DEFAULT_HEIGHT
        ratio = (width_ratio + height_ratio) / 2
        
        base_font_size = (MIN_FONT_SIZE + 
                         (MAX_FONT_SIZE - MIN_FONT_SIZE) * (ratio - 1))
        base_font_size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, base_font_size))
        
        base_font_size = int(base_font_size)
        other_font_size = int(base_font_size * 0.5)
        other_font = QFont("微软雅黑", other_font_size)
        
        for widget in [self.path_label, self.save_path_label]:
            widget.setFont(other_font)
            
        for widget in [self.back_button, self.refresh_button, self.browse_button, 
                      self.cancel_button, self.download_button]:
            widget.setFont(other_font)
            
        self.save_path_input.setFont(other_font)
        self.tree_widget.setFont(other_font)
    
    def resizeEvent(self, event):
        """处理窗口大小变化事件"""
        self._update_fonts()
        super().resizeEvent(event)
    
    def load_root_directory(self):
        """加载根目录"""
        self.current_path = ""
        self.path_history = []
        self.load_directory_contents("")
    
    def load_directory_contents(self, path):
        """
        加载指定路径的目录内容
        
        Args:
            path (str): 目录路径
        """
        self.tree_widget.clear()
        
        try:
            url = f"https://api.github.com/repos/TapXWorld/ChinaTextbook/contents/{path}"
            response = requests.get(url, verify=certifi.where(), timeout=15)
            response.raise_for_status()
            contents = response.json()
            
            for item in contents:
                if item['name'] == '.cache':
                    continue
                    
                if item['type'] == 'dir':
                    dir_item = QTreeWidgetItem([item['name'], "文件夹", ""])
                    dir_item.setData(0, Qt.UserRole, {'type': 'dir', 'path': item['path']})
                    self.tree_widget.addTopLevelItem(dir_item)
                elif item['type'] == 'file' and item['name'].lower().endswith('.pdf'):
                    size = self.format_file_size(item.get('size', 0))
                    file_item = QTreeWidgetItem([item['name'], "PDF文件", size])
                    file_item.setData(0, Qt.UserRole, {
                        'type': 'file', 
                        'path': item['path'],
                        'file_info': item
                    })
                    self.tree_widget.addTopLevelItem(file_item)
            
            self.path_label.setText(f"当前路径: /{path}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法加载目录内容: {str(e)}")
    
    def format_file_size(self, size_bytes):
        """
        格式化文件大小显示
        
        Args:
            size_bytes (int): 文件大小（字节）
            
        Returns:
            str: 格式化后的文件大小字符串
        """
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"
    
    def on_item_double_clicked(self, item, column):
        """
        处理列表项双击事件
        
        Args:
            item: 被点击的项
            column: 列索引
        """
        item_data = item.data(0, Qt.UserRole)
        if not item_data:
            return
            
        if item_data['type'] == 'dir':
            self.path_history.append(self.current_path)
            self.current_path = item_data['path']
            self.back_button.setEnabled(True)
            self.load_directory_contents(self.current_path)
        elif item_data['type'] == 'file':
            self.selected_file_info = item_data['file_info']
            self.selected_pdf_name = item.text(0)
            self.download_button.setEnabled(True)
    
    def go_back(self):
        """返回上级目录"""
        if self.path_history:
            self.current_path = self.path_history.pop()
            self.load_directory_contents(self.current_path)
            
            if not self.path_history:
                self.back_button.setEnabled(False)
    
    def refresh_current_directory(self):
        """刷新当前目录"""
        self.load_directory_contents(self.current_path)
    
    def browse_save_path(self):
        """浏览保存路径"""
        directory = QFileDialog.getExistingDirectory(self, "选择保存路径")
        if directory:
            if self.selected_pdf_name:
                full_path = os.path.join(directory, self.selected_pdf_name)
                self.save_path_input.setText(full_path)
            else:
                self.save_path_input.setText(directory)
    
    def download_pdf(self):
        """下载PDF文件"""
        if not self.selected_file_info:
            QMessageBox.warning(self, "提示", "请先选择PDF文件")
            return
        
        save_path = self.save_path_input.text().strip()
        if not save_path:
            save_path = self.get_default_save_path()
        
        if not save_path:
            QMessageBox.warning(self, "提示", "请选择保存路径")
            return
        
        loading_dialog = LoadingDialog(self) if DIALOGS_AVAILABLE else None
        if loading_dialog:
            loading_dialog.text_label.setText(f"正在下载 {self.selected_pdf_name}...")
            loading_dialog.show()
            QApplication.processEvents()
        
        try:
            pdf_url = self.get_pdf_download_url(self.selected_file_info)
            
            response = requests.get(pdf_url, stream=True, verify=certifi.where(), timeout=30)
            response.raise_for_status()
            
            if not save_path.endswith('.pdf'):
                save_path += '.pdf'
            
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    QApplication.processEvents()
            
            if loading_dialog:
                loading_dialog.close()
            
            QMessageBox.information(self, "下载完成", f"PDF文件已保存到:\n{save_path}")
            self.accept()
            
        except Exception as e:
            if loading_dialog:
                loading_dialog.close()
            QMessageBox.critical(self, "错误", f"下载失败: {str(e)}")
    
    def get_default_save_path(self):
        """
        获取默认保存路径
        
        Returns:
            str: 默认保存路径
        """
        if self.selected_pdf_name:
            downloads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloaded_pdfs")
            os.makedirs(downloads_dir, exist_ok=True)
            return os.path.join(downloads_dir, self.selected_pdf_name)
        return ""
    
    def get_pdf_download_url(self, file_info):
        """
        获取PDF文件下载URL
        
        Args:
            file_info (dict): 文件信息
            
        Returns:
            str: PDF文件下载URL
            
        Raises:
            Exception: 获取URL失败时抛出异常
        """
        try:
            if 'download_url' in file_info and file_info['download_url']:
                return file_info['download_url']
            
            file_path = file_info['path']
            raw_url = f"https://raw.githubusercontent.com/TapXWorld/ChinaTextbook/main/{file_path}"
            return raw_url
            
        except Exception as e:
            raise Exception(f"无法获取PDF下载URL: {str(e)}")


class AboutDialog(QDialog):
    """关于对话框 - 显示程序信息和开发者信息"""
    
    def __init__(self, parent=None):
        """
        初始化关于对话框
        
        Args:
            parent: 父窗口
        """
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("关于")
        self.resize(700, 600)
        
        self.setStyleSheet("""
            QDialog {background-color: #E5E8EF;}
            QPushButton {
                font-family: "微软雅黑"; background-color: white; color: black;
                border: 2px solid gray; border-radius: 5px; font-weight: bold; padding: 5px;
            }
            QPushButton:hover {background-color: #f0f0f0;}
            QLabel {font-family: "微软雅黑";}
        """)
        
        layout = QVBoxLayout()
        
        # 标题
        self.title_label = QLabel("关于")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)
        
        # 正文
        self.content_label = QLabel(
            "源悦TTS，\n"
            "一款以学生为本、由学生研发、为学生而生的文本转语音程序。\n"
            '——————————————————\n'
            '大部分外围设施（尤其是官网）还没有准备好，望各位谅解。\n'
            '此版本为公测版，仍有部分功能未适配/未实现，望各位谅解。\n'
            '感谢各位的鼎力支持，各位的支持是我的最大动力。\n'
            '——————————————————\n'
            '另：若发现ghfast加速功能无法使用，很有可能是ghfast被限制了。请在github交issue提醒我，万分感谢。\n'
            '——————————————————\n'
            "by Air84 2025.12.11\n"
            "version:SimeonTest 0.7 "
        )
        self.content_label.setAlignment(Qt.AlignCenter)
        self.content_label.setWordWrap(True)
        layout.addWidget(self.content_label)
        
        # 图片区
        image_layout = QHBoxLayout()
        self.image_labels = []
        
        for i in range(3):
            image_label = QLabel()
            image_label.setAlignment(Qt.AlignCenter)
            image_label.setFixedSize(150, 150)
            image_label.setStyleSheet("border: 1px solid gray; background-color: white;")
            image_layout.addWidget(image_label)
            self.image_labels.append(image_label)
        
        layout.addLayout(image_layout)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        self.buttons = []
        
        for i, text in enumerate(ABOUT_BUTTON_TEXTS):
            button = QPushButton(text)
            button.setStyleSheet("""
                QPushButton {
                    font-family: "微软雅黑"; background-color: white; color: black;
                    border: 2px solid gray; border-radius: 5px; font-weight: bold; padding: 5px;
                }
                QPushButton:hover {background-color: #f0f0f0;}
            """)
            button.clicked.connect(lambda checked, idx=i: self.open_url(idx))
            button_layout.addWidget(button)
            self.buttons.append(button)
        
        layout.addLayout(button_layout)
        
        # 关闭按钮
        close_button = QPushButton("关闭")
        close_button.setStyleSheet("""
            QPushButton {
                font-family: "微软雅黑"; background-color: white; color: black;
                border: 2px solid gray; border-radius: 5px; font-weight: bold; padding: 5px;
            }
            QPushButton:hover {background-color: #f0f0f0;}
        """)
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)
        
        self.setLayout(layout)
        
        # 加载图片
        self.load_images()
        
        self._update_fonts()
    
    def _update_fonts(self):
        """更新界面字体大小"""
        if not self.parent_window:
            return
            
        current_width = self.width()
        current_height = self.height()
        
        width_ratio = current_width / DEFAULT_WIDTH
        height_ratio = current_height / DEFAULT_HEIGHT
        ratio = (width_ratio + height_ratio) / 2
        
        base_font_size = (MIN_FONT_SIZE + 
                         (MAX_FONT_SIZE - MIN_FONT_SIZE) * (ratio - 1))
        base_font_size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, base_font_size))
        
        base_font_size = int(base_font_size)
        title_font_size = int(base_font_size * 1.125 * 0.5)
        content_font_size = int(base_font_size * 0.5)
        button_font_size = int(base_font_size * 0.5 * 0.5)
        
        # 获取字体
        font_name = "微软雅黑"
        if self.parent_window and hasattr(self.parent_window, 'settings_manager'):
            settings_manager = self.parent_window.settings_manager
            custom_font = settings_manager.Custom.get_value("global_font", "微软雅黑")
            font_name = custom_font
        
        title_font = QFont(font_name, title_font_size)
        title_font.setBold(True)
        
        content_font = QFont(font_name, content_font_size)
        button_font = QFont(font_name, button_font_size)
        
        self.title_label.setFont(title_font)
        self.content_label.setFont(content_font)
        
        for button in self.buttons:
            button.setFont(button_font)
    
    def resizeEvent(self, event):
        """处理窗口大小变化事件"""
        self._update_fonts()
        super().resizeEvent(event)
    
    def load_images(self):
        """加载关于页面图片"""
        cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
        os.makedirs(cache_dir, exist_ok=True)
        
        for i, url in enumerate(ABOUT_IMAGE_URLS):
            if not url:
                continue
                
            cache_path = os.path.join(cache_dir, f"about_image_{i}.png")
            
            # 先翻缓存
            if os.path.exists(cache_path):
                pixmap = QPixmap(cache_path)
                if not pixmap.isNull():
                    self.image_labels[i].setPixmap(pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    continue
            
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    pixmap = QPixmap()
                    pixmap.loadFromData(response.content)
                    if not pixmap.isNull():
                        self.image_labels[i].setPixmap(pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                        pixmap.save(cache_path, "PNG")
                    else:
                        self.image_labels[i].setText("获取错误")
                else:
                    self.image_labels[i].setText("获取错误")
            except Exception as e:
                self.image_labels[i].setText("获取错误")
    
    def open_url(self, index):
        """
        打开指定索引的URL
        
        Args:
            index (int): URL索引
        """
        if index < len(ABOUT_BUTTON_URLS) and ABOUT_BUTTON_URLS[index]:
            QDesktopServices.openUrl(QUrl(ABOUT_BUTTON_URLS[index]))


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
        
        # 获取共享内存管理器
        self.shared_manager = get_shared_memory_manager()
        
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
            ("docx文字提取", self._on_docx_text_extraction),
            ("关于", self._on_about),
            ("多线程下载", self._on_multi_thread_download),
            ("预留6", self._on_reserved_function),
            ("预留7", self._on_reserved_function),
            ("预留8", self._on_reserved_function),
            ("预留9", self._on_reserved_function)
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
        return """
            QPushButton {
                font-family: "微软雅黑"; 
                background-color: white; 
                color: black;
                border: 3px solid gray; 
                border-radius: 15px;
                font-weight: bold;
                min-height: 80px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
                border: 3px solid #444444;
            }
            QPushButton:pressed {
                background-color: #e0e0e0;
            }
        """
    
    def _update_fonts(self):
        """更新界面字体大小"""
        if not self.parent_window:
            return
            
        current_width = self.parent_window.width()
        current_height = self.parent_window.height()
        
        width_ratio = current_width / DEFAULT_WIDTH
        height_ratio = current_height / DEFAULT_HEIGHT
        ratio = (width_ratio + height_ratio) / 2
        
        base_font_size = (MIN_FONT_SIZE + 
                         (MAX_FONT_SIZE - MIN_FONT_SIZE) * (ratio - 1))
        base_font_size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, base_font_size))
        
        base_font_size = int(base_font_size)
        button_font_size = int(base_font_size * 0.6)
        button_font = QFont("微软雅黑", button_font_size)
        
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
    
    def _on_docx_text_extraction(self):
        """处理DOCX文字提取功能"""
        if not DOCX_AVAILABLE:
            QMessageBox.warning(self, "错误", "文档处理模块不可用")
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择Word文档", "", "Word Documents (*.docx)"
        )
        
        if not file_path:
            return
        
        try:
            doc = Document(file_path)
            content = '\n'.join([p.text for p in doc.paragraphs])
            
            dialog = TextResultDialog(self, "DOCX文本提取结果", content)
            dialog.exec_()
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"文档提取失败: {str(e)}")
    
    def _on_about(self):
        """处理关于功能"""
        dialog = AboutDialog(self)
        dialog.exec_()
    
    def _on_reserved_function(self):
        """处理预留功能"""
        button = self.sender()
        if button:
            QMessageBox.information(self, "功能预留", 
                                  f"还不知道要做什么……\n要是有啥好点子可以来github交个PR/issue，\n感谢您的支持")
    
    def _on_multi_thread_download(self):
        """处理多线程下载功能"""
        dialog = MultiThreadDownloadDialog(self)
        dialog.exec_()
    
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
        pass


# ==================== 多线程下载功能 ====================

class MoreSettingsDialog(QDialog):
    """更多设置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("更多设置")
        self.resize(400, 300)
        
        # 字体大小相关参数
        self.min_font_size = 22
        self.max_font_size = 42
        self.default_width = 1080
        self.default_height = 720
        
        self._init_ui()
        self._update_fonts()
    
    def _init_ui(self):
        # 应用样式
        self._apply_styles()
        
        layout = QVBoxLayout()
        
        # 保存文件名输入框
        filename_layout = QHBoxLayout()
        filename_label = QLabel("保存文件名:")
        self.filename_edit = QLineEdit()
        self.filename_edit.setPlaceholderText("留空则自动提取")
        filename_layout.addWidget(filename_label)
        filename_layout.addWidget(self.filename_edit)
        layout.addLayout(filename_layout)
        
        # UA输入框
        ua_layout = QHBoxLayout()
        ua_label = QLabel("User-Agent:")
        self.ua_edit = QLineEdit()
        self.ua_edit.setPlaceholderText("留空使用默认UA")
        ua_layout.addWidget(ua_label)
        ua_layout.addWidget(self.ua_edit)
        layout.addLayout(ua_layout)
        
        # 代理地址输入框
        proxy_layout = QHBoxLayout()
        proxy_label = QLabel("代理地址:")
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
        current_width = self.width()
        current_height = self.height()
        width_ratio = current_width / self.default_width
        height_ratio = current_height / self.default_height
        ratio = (width_ratio + height_ratio) / 2
        base_font_size = (self.min_font_size + 
                         (self.max_font_size - self.min_font_size) * (ratio - 1))
        base_font_size = max(self.min_font_size, min(self.max_font_size, base_font_size))
        base_font_size = int(base_font_size)
        other_font_size = int(base_font_size * 0.5)
        return base_font_size, other_font_size
    
    def _update_fonts(self):
        """更新字体"""
        try:
            base_font_size, other_font_size = self._calculate_font_sizes()
            
            # 获取字体
            font_name = "微软雅黑"
            if self.parent_window and hasattr(self.parent_window, 'settings_manager'):
                try:
                    font_name = self.parent_window.settings_manager.get_Custom_value("global_font", "微软雅黑")
                except:
                    pass
            else:
                # 如果没有父窗口，则尝试直接从设置管理器获取
                try:
                    from misc_func import SettingsManager
                    settings_manager = SettingsManager()
                    font_name = settings_manager.get_Custom_value("global_font", "微软雅黑")
                except:
                    pass
            
            # 更新控件字体
            other_font = QFont(font_name, other_font_size)
            
            # 更新标签字体
            for widget in [self.filename_edit, self.ua_edit, self.proxy_edit]:
                if widget:
                    widget.setFont(other_font)
            
            # 更新按钮字体
            for button in [self.ok_button, self.cancel_button]:
                if button:
                    button.setFont(other_font)
                    
            # 更新标签字体
            for label in [self.findChild(QLabel, "filename_label"), 
                         self.findChild(QLabel, "ua_label"),
                         self.findChild(QLabel, "proxy_label")]:
                if label:
                    label.setFont(other_font)
            
            # 更新复选框字体
            if hasattr(self, 'ssl_checkbox') and self.ssl_checkbox:
                self.ssl_checkbox.setFont(other_font)
                
        except Exception as e:
            print(f"更新字体时出错: {e}")
    
    def _apply_styles(self):
        """应用与主界面一致的样式"""
        # 获取全局字体设置
        global_font = '微软雅黑'
        background_color = '#E5E8EF'
        
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
            QLabel {{
                font-family: "{global_font}";
                font-size: 14px;
                color: black;
            }}
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
        filename = self.filename_edit.text().strip() or None
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
            "filename": filename,
            "user_agent": user_agent,
            "proxy": proxy,
            "verify_ssl": verify_ssl
        }


class MultiThreadDownloadDialog(QDialog):
    """多线程下载主对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("多线程下载")
        self.resize(500, 200)
        
        # 字体大小相关参数
        self.min_font_size = 22
        self.max_font_size = 42
        self.default_width = 1080
        self.default_height = 720
        
        # 默认设置
        self.default_threads = 4
        self.default_save_path = os.path.expanduser("~/Downloads")
        
        # 更多设置
        self.more_settings = {}
        
        self._init_ui()
        self._update_fonts()
    
    def _init_ui(self):
        # 应用样式
        self._apply_styles()
        
        layout = QVBoxLayout()
        
        # 下载链接输入框
        url_layout = QHBoxLayout()
        url_label = QLabel("下载链接:")
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("请输入要下载的文件链接")
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_edit)
        layout.addLayout(url_layout)
        
        # 线程数和保存路径布局
        settings_layout = QHBoxLayout()
        
        # 线程数输入框
        thread_layout = QVBoxLayout()
        thread_label = QLabel("线程数:")
        self.thread_edit = QLineEdit()
        self.thread_edit.setPlaceholderText(f"默认{self.default_threads}")
        self.thread_edit.setText(str(self.default_threads))
        thread_layout.addWidget(thread_label)
        thread_layout.addWidget(self.thread_edit)
        settings_layout.addLayout(thread_layout)
        
        # 保存路径输入框
        path_layout = QVBoxLayout()
        path_label = QLabel("保存路径:")
        path_input_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(f"默认{self.default_save_path}")
        self.path_edit.setText(self.default_save_path)
        self.browse_button = QPushButton("浏览")
        self.browse_button.clicked.connect(self._browse_save_path)
        path_input_layout.addWidget(self.path_edit)
        path_input_layout.addWidget(self.browse_button)
        path_layout.addWidget(path_label)
        path_layout.addLayout(path_input_layout)
        settings_layout.addLayout(path_layout)
        
        layout.addLayout(settings_layout)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        self.more_button = QPushButton("更多设置")
        self.download_button = QPushButton("开始下载")
        self.cancel_button = QPushButton("取消")
        
        self.more_button.clicked.connect(self._show_more_settings)
        self.download_button.clicked.connect(self._start_download)
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.more_button)
        button_layout.addStretch()
        button_layout.addWidget(self.download_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def resizeEvent(self, event):
        """处理窗口大小变化事件"""
        self._update_fonts()
        super().resizeEvent(event)
    
    def _calculate_font_sizes(self):
        """计算字体大小"""
        current_width = self.width()
        current_height = self.height()
        width_ratio = current_width / self.default_width
        height_ratio = current_height / self.default_height
        ratio = (width_ratio + height_ratio) / 2
        base_font_size = (self.min_font_size + 
                         (self.max_font_size - self.min_font_size) * (ratio - 1))
        base_font_size = max(self.min_font_size, min(self.max_font_size, base_font_size))
        base_font_size = int(base_font_size)
        other_font_size = int(base_font_size * 0.5)
        return base_font_size, other_font_size
    
    def _update_fonts(self):
        """更新字体"""
        try:
            base_font_size, other_font_size = self._calculate_font_sizes()
            
            # 获取字体
            font_name = "微软雅黑"
            if self.parent_window and hasattr(self.parent_window, 'settings_manager'):
                try:
                    font_name = self.parent_window.settings_manager.get_Custom_value("global_font", "微软雅黑")
                except:
                    pass
            else:
                # 如果没有父窗口，则尝试直接从设置管理器获取
                try:
                    from misc_func import SettingsManager
                    settings_manager = SettingsManager()
                    font_name = settings_manager.get_Custom_value("global_font", "微软雅黑")
                except:
                    pass
            
            # 更新控件字体
            other_font = QFont(font_name, other_font_size)
            
            # 更新标签字体
            for widget in [self.url_edit, self.thread_edit, self.path_edit]:
                if widget:
                    widget.setFont(other_font)
            
            # 更新按钮字体
            for button in [self.browse_button, self.more_button, 
                          self.download_button, self.cancel_button]:
                if button:
                    button.setFont(other_font)
                    
            # 更新标签字体
            # 这里可以根据需要更新特定标签的字体
            
        except Exception as e:
            print(f"更新字体时出错: {e}")
    
    def _apply_styles(self):
        """应用与主界面一致的样式"""
        # 获取全局字体设置
        global_font = '微软雅黑'
        background_color = '#E5E8EF'
        
        # 优先从父窗口的设置管理器获取背景颜色（与主窗口保持一致）
        if self.parent_window and hasattr(self.parent_window, 'settings_manager'):
            try:
                background_color = self.parent_window.settings_manager.get_Custom_value("background_color", "#E5E8EF")
            except:
                pass
        else:
            # 如果没有父窗口，则尝试直接从设置管理器获取
            try:
                from misc_func import SettingsManager
                settings_manager = SettingsManager()
                background_color = settings_manager.get_Custom_value("background_color", "#E5E8EF")
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
            QLabel {{
                font-family: "{global_font}";
                font-size: 14px;
                color: black;
            }}
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
        thread_text = self.thread_edit.text().strip()
        thread_num = self.default_threads
        if thread_text:
            try:
                thread_num = int(thread_text)
                if thread_num < 1:
                    QMessageBox.warning(self, "错误", "线程数必须大于0")
                    return
            except ValueError:
                QMessageBox.warning(self, "错误", "请输入有效的线程数")
                return
        
        # 获取保存路径
        save_path = self.path_edit.text().strip() or self.default_save_path
        
        # 创建目录（如果不存在）
        try:
            os.makedirs(save_path, exist_ok=True)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法创建保存目录: {str(e)}")
            return
        
        # 获取文件名
        filename = self.more_settings.get('filename')
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


# 测试代码已注释，避免在运行主程序时创建额外的窗口
# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#     window = QWidget()
#     window.setWindowTitle("杂项功能测试")
#     window.resize(800, 600)
#     misc_page = MiscPage(window)
#     layout = QVBoxLayout()
#     layout.addWidget(misc_page)
#     window.setLayout(layout)
#     window.show()
#     sys.exit(app.exec_())
import sys
import os
import base64
import tempfile
import requests
from typing import Optional
from PyQt5.QtWidgets import (
    QWidget, QPushButton, QGridLayout, QMessageBox, QApplication,
    QDialog, QVBoxLayout, QTextEdit, QFileDialog, QLabel, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QFormLayout, QLineEdit
)
from PyQt5.QtCore import Qt, QRect, QThread, pyqtSignal, QUrl
from PyQt5.QtGui import QFont, QPixmap, QDesktopServices
import certifi



# ===== 常量定义 =====
#图片URL
ABOUT_IMAGE_URLS = [
    'https://youke1.picui.cn/s1/2025/11/13/6915e2f462bb7.png',
    'https://www.baidu.com',
    'https://www.baidu.com'
]
#链接和文字
ABOUT_BUTTON_TEXTS = ["官网", "官网更新", "GitHub项目主页", "Github更新", "python-docx","ghfast"]
ABOUT_BUTTON_URLS = [
    "https://play.simpfun.cn:22501",
    "https://play.simpfun.cn:22501/releases.html",
    "https://github.com/CN-Air84/YuanYue-TTS",
    "https://github.com/CN-Air84/YuanYue-TTS/releases",
    "https://github.com/python-openxml/python-docx",
    "https://www.ghfast.top/"
]
#向后煎熔
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
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    
    def __init__(self, api_key, image_path):
        super().__init__()
        self.api_key = api_key
        self.image_path = image_path
    
    def run(self):
        try:
            from openai import OpenAI
            
            client = OpenAI(
                api_key=self.api_key,
                base_url="https://open.bigmodel.cn/api/paas/v4/"
            )
            
            def encode_image(image_path):
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
    def __init__(self, parent=None, title="文本提取结果", content=""):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle(title)
        self.resize(600, 400)
        
        layout = QVBoxLayout()
        
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(content)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: white;
                color: black;
                border: 2px solid gray;
                border-radius: 10px;
                font-family: "微软雅黑";
                font-size: 12px;
            }
        """)
        layout.addWidget(self.text_edit)
        
        button_layout = QHBoxLayout()
        
        self.copy_button = QPushButton("复制结果")
        self.copy_button.setStyleSheet("""
            QPushButton {
                font-family: "微软雅黑";
                background-color: white;
                color: black;
                border: 2px solid gray;
                border-radius: 5px;
                padding: 5px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
        """)
        self.copy_button.clicked.connect(self.copy_text)
        
        self.close_button = QPushButton("关闭")
        self.close_button.setStyleSheet("""
            QPushButton {
                font-family: "微软雅黑";
                background-color: white;
                color: black;
                border: 2px solid gray;
                border-radius: 5px;
                padding: 5px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
        """)
        self.close_button.clicked.connect(self.accept)
        
        button_layout.addWidget(self.copy_button)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        self._update_fonts()
    
    def _update_fonts(self):
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
        button_font = QFont("微软雅黑", button_font_size)
        
        self.copy_button.setFont(button_font)
        self.close_button.setFont(button_font)
    
    def resizeEvent(self, event):
        self._update_fonts()
        super().resizeEvent(event)
    
    def copy_text(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.text_edit.toPlainText())
        QMessageBox.information(self, "成功", "文本已复制到剪贴板")


class PDFDownloadDialog(QDialog):
    def __init__(self, parent=None, window_size=None):
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
        self.setWindowTitle("PDF电子书下载")
        if self.window_size:
            self.setGeometry(self.window_size)
        else:
            self.resize(800, 600)
        
        self.setStyleSheet("""
            QDialog {background-color: #69E0A5;}
            QPushButton {
                font-family: "微软雅黑"; background-color: white; color: black;
                border: 2px solid gray; border-radius: 5px; font-weight: bold; padding: 5px;
            }
            QPushButton:hover {background-color: #f0f0f0;}
            QLabel {font-family: "微软雅黑"; font-size: 14px;}
            QLineEdit {
                font-family: "微软雅黑"; background-color: white; color: black;
                border: 2px solid gray; border-radius: 10px; padding: 5px;
            }
            QTreeWidget {
                font-family: "微软雅黑"; background-color: white; color: black;
                border: 2px solid gray; border-radius: 5px;
            }
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
        self._update_fonts()
        super().resizeEvent(event)
    
    def load_root_directory(self):
        self.current_path = ""
        self.path_history = []
        self.load_directory_contents("")
    
    def load_directory_contents(self, path):
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
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"
    
    def on_item_double_clicked(self, item, column):
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
        if self.path_history:
            self.current_path = self.path_history.pop()
            self.load_directory_contents(self.current_path)
            
            if not self.path_history:
                self.back_button.setEnabled(False)
    
    def refresh_current_directory(self):
        self.load_directory_contents(self.current_path)
    
    def browse_save_path(self):
        directory = QFileDialog.getExistingDirectory(self, "选择保存路径")
        if directory:
            if self.selected_pdf_name:
                full_path = os.path.join(directory, self.selected_pdf_name)
                self.save_path_input.setText(full_path)
            else:
                self.save_path_input.setText(directory)
    
    def download_pdf(self):
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
        if self.selected_pdf_name:
            downloads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloaded_pdfs")
            os.makedirs(downloads_dir, exist_ok=True)
            return os.path.join(downloads_dir, self.selected_pdf_name)
        return ""
    
    def get_pdf_download_url(self, file_info):
        try:
            if 'download_url' in file_info and file_info['download_url']:
                return file_info['download_url']
            
            file_path = file_info['path']
            raw_url = f"https://raw.githubusercontent.com/TapXWorld/ChinaTextbook/main/{file_path}"
            return raw_url
            
        except Exception as e:
            raise Exception(f"无法获取PDF下载URL: {str(e)}")


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("关于")
        self.resize(700, 600)
        
        self.setStyleSheet("""
            QDialog {background-color: #69E0A5;}
            QPushButton {
                font-family: "微软雅黑"; background-color: white; color: black;
                border: 2px solid gray; border-radius: 5px; font-weight: bold; padding: 5px;
            }
            QPushButton:hover {background-color: #f0f0f0;}
            QLabel {font-family: "微软雅黑";}
        """)
        
        layout = QVBoxLayout()
        
        #标题
        self.title_label = QLabel("关于")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)
        
        #正文
        self.content_label = QLabel(
            "源悦TTS，\n"
            "一款以学生为本、由学生研发、为学生而生的文本转语音程序。\n"
            '——————————————————\n'
            '大部分外围设施（尤其是官网）还没有准备好，望各位谅解。\n'
            '此版本为公测版，仍有部分功能未适配/未实现，望各位谅解。\n'
            '——————————————————\n'
            '程序引用了python-docx库并对其进行了大幅修改，感谢原作者。\n'
            '电子书下载加速基于ghfast.top。感谢。\n'
            '感谢各位的鼎力支持，各位的支持是我的最大动力。\n'
            '——————————————————\n'
            '左图为微信赞赏码。不差钱的哥们可以赞助个五毛一块的，\n'
            '但是用这一块钱买根笔显然更合适。\n'
            '——————————————————\n'
            '另：若发现ghfast加速功能无法使用，很有可能是ghfast被限制了。请在github交issue提醒我，万分感谢。\n'
            '——————————————————\n'
            "by Air84 2025.11.16\n"
            "version:SimeonTest 0.6 Alpha-Release"
        )
        self.content_label.setAlignment(Qt.AlignCenter)
        self.content_label.setWordWrap(True)
        layout.addWidget(self.content_label)
        
        #图片区
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
        
        #按钮区域
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
        
        #关闭按钮
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
        
        #加载图片
        self.load_images()
        
        self._update_fonts()
    
    def _update_fonts(self):
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
        
        #获取字体
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
        self._update_fonts()
        super().resizeEvent(event)
    
    def load_images(self):
        cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
        os.makedirs(cache_dir, exist_ok=True)
        
        for i, url in enumerate(ABOUT_IMAGE_URLS):
            if not url:
                continue
                
            cache_path = os.path.join(cache_dir, f"about_image_{i}.png")
            
            #先翻缓存
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
                print(f"加载图片失败: {e}")
                self.image_labels[i].setText("获取错误")
    
    def open_url(self, index):
        if index < len(ABOUT_BUTTON_URLS) and ABOUT_BUTTON_URLS[index]:
            QDesktopServices.openUrl(QUrl(ABOUT_BUTTON_URLS[index]))


class MiscPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        
        self._init_ui()
    
    def _init_ui(self):
        self._create_buttons()
        self._setup_layout()
        self._update_fonts()
    
    def _create_buttons(self):
        self.buttons = []
        
        button_configs = [
            ("AI图片OCR", self._on_ai_image_ocr),
            ("PDF电子书下载", self._on_pdf_ebook_download), 
            ("docx文字提取", self._on_docx_text_extraction),
            ("关于", self._on_about),
            ("预留5", self._on_reserved_function),
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
        layout = QGridLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(50, 50, 50, 50)
        
        positions = [(i, j) for i in range(3) for j in range(3)]
        
        for position, button in zip(positions, self.buttons):
            layout.addWidget(button, *position)
        
        self.setLayout(layout)
    
    def _get_button_style(self):
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
        self._update_fonts()
        super().resizeEvent(event)
    
    def _on_ai_image_ocr(self):
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
        if loading_dialog:
            loading_dialog.close()
        
        if text:
            dialog = TextResultDialog(self, "AI图片OCR结果", text)
            dialog.exec_()
        else:
            QMessageBox.warning(self, "提示", "未识别到文字")
    
    def _on_ai_ocr_error(self, error, loading_dialog):
        if loading_dialog:
            loading_dialog.close()
        QMessageBox.critical(self, "错误", error)
    
    def _on_pdf_ebook_download(self):
        if self.parent_window:
            window_rect = self.parent_window.geometry()
            dialog = PDFDownloadDialog(self, window_rect)
            dialog.exec_()
    
    def _on_docx_text_extraction(self):
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
        dialog = AboutDialog(self)
        dialog.exec_()
    
    def _on_reserved_function(self):
        button = self.sender()
        if button:
            QMessageBox.information(self, "功能预留", 
                                  f"还不知道要做什么……\n要是有啥好点子可以来github交个PR/issue，\n感谢您的支持")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("杂项功能测试")
    window.resize(800, 600)
    misc_page = MiscPage(window)
    layout = QVBoxLayout()
    layout.addWidget(misc_page)
    window.setLayout(layout)
    window.show()
    sys.exit(app.exec_())
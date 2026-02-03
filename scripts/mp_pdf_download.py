# coding=utf-8
import os
import requests
import certifi
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, 
    QTreeWidget, QTreeWidgetItem, QFileDialog, QMessageBox, QApplication
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

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
        
        if SETTINGS_AVAILABLE:
            self.global_font = self.settings_manager.get_Custom_value('global_font', '微软雅黑')
            self.min_font_size = int(self.settings_manager.get_Custom_value('min_font_size', '22'))
            self.max_font_size = int(self.settings_manager.get_Custom_value('max_font_size', '42'))
        else:
            self.global_font = '微软雅黑'
            self.min_font_size = 22
            self.max_font_size = 42
        
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
            
        background_color = self.settings_manager.get_Custom_value("background_color", "#E5E8EF") if self.settings_manager else "#E5E8EF"
        self.setStyleSheet(f"""
        QDialog {{background-color: {background_color};}}
        QPushButton {{
            font-family: "{self.global_font}"; background-color: white; color: black;
            border: 2px solid gray; border-radius: 5px; font-weight: bold; padding: 5px;
        }}
        QPushButton:hover {{background-color: #f0f0f0;}}
        QLabel {{
            font-family: "{self.global_font}"; 
            font-size: 14px;
            background-color: transparent;
        }}
        QLineEdit {{
            font-family: "{self.global_font}"; background-color: white; color: black;
            border: 2px solid gray; border-radius: 10px; padding: 5px;
        }}
        QTreeWidget {{
            font-family: "{self.global_font}"; background-color: white; color: black;
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
        current_width = self.width()
        current_height = self.height()
        
        DEFAULT_WIDTH = 800
        DEFAULT_HEIGHT = 600
        MIN_FONT_SIZE = self.min_font_size
        MAX_FONT_SIZE = self.max_font_size
        
        width_ratio = current_width / DEFAULT_WIDTH
        height_ratio = current_height / DEFAULT_HEIGHT
        ratio = (width_ratio + height_ratio) / 2
        
        base_font_size = (MIN_FONT_SIZE + 
                         (MAX_FONT_SIZE - MIN_FONT_SIZE) * (ratio - 1))
        base_font_size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, base_font_size))
        
        base_font_size = int(base_font_size)
        other_font_size = int(base_font_size * 0.5)
        other_font = QFont(self.global_font, other_font_size)
        
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
            
            # 使用带背景色的信息框
            msg = QMessageBox(self)
            msg.setWindowTitle("下载完成")
            msg.setText(f"PDF文件已保存到:\n{save_path}")
            msg.setIcon(QMessageBox.Information)
            background_color = self.settings_manager.get_Custom_value("background_color", "#E5E8EF") if self.settings_manager else "#E5E8EF"
            msg.setStyleSheet(f"QMessageBox {{ background-color: {background_color}; }} QLabel {{ background-color: transparent; }}")
            msg.exec_()
            
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

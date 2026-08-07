# coding=utf-8
import sys
import os
import re
import base64
import io
import tempfile
import requests
from PyQt5.QtWidgets import (QApplication, QPushButton, QLineEdit, QTreeWidget, 
                             QMessageBox, QVBoxLayout, QHBoxLayout, QDialog, QLabel, 
                             QTreeWidgetItem)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt5.QtGui import QFont, QDesktopServices
from multi_thread_downloader import download
from PIL import Image
import certifi
import fitz  # PyMuPDF
import tchMP
from debug_logger import debug_logger, LogLevel

from misc_func import get_app_base_path
from resource_urls import get_resource_url, apply_mirror

try:
    from misc_func import SettingsManager
    SETTINGS_AVAILABLE = True
except ImportError:
    SETTINGS_AVAILABLE = False

from iw_dialogs import LoadingDialog, PageOffsetDialog

SMARTEDU_URL = "https://basic.smartedu.cn/tchMaterial"
TCHMATERIAL_URL_PATTERN = re.compile(r'contentId=')


class AIOCRWorker(QThread):
    """AI OCR识别线程 - 使用AIManager"""
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    debug_signal = pyqtSignal(str, str)
    
    def __init__(self, image_path, prompt):
        super().__init__()
        self.image_path = image_path
        self.prompt = prompt
    
    def run(self):
        try:
            debug_logger.output("iw_online_import.py", LogLevel.INFO, "AIOCRWorker: 开始识别", fold_code="OI_WORKER")
            from ai_manager import get_ai_manager, AIRequest, AIScene
            
            ai_manager = get_ai_manager()
            
            def encode_image(image_path):
                try:
                    from PIL import Image
                    import io
                    
                    with Image.open(image_path) as img:
                        max_side = 1560
                        if img.width > max_side or img.height > max_side:
                            img.thumbnail((max_side, max_side), Image.LANCZOS)
                            
                        if img.mode != "RGB":
                            img = img.convert("RGB")
                            
                        buffer = io.BytesIO()
                        img.save(buffer, format="JPEG", quality=80, optimize=True)
                        img_bytes = buffer.getvalue()
                        
                        debug_logger.output("iw_online_import.py", LogLevel.INFO, f"图像预处理完成: {img.width}x{img.height}, 大小: {len(img_bytes)/1024:.1f}KB", fold_code="OI_WORKER")
                        return base64.b64encode(img_bytes).decode('utf-8')
                except Exception as e:
                    debug_logger.output("iw_online_import.py", LogLevel.WARNING, f"图像预处理失败: {e}", fold_code="OI_WORKER")
                    with open(image_path, "rb") as f:
                        return base64.b64encode(f.read()).decode('utf-8')
            
            base64_image = encode_image(self.image_path)
            
            self.debug_signal.emit("prompt", self.prompt)
            
            max_retries = 2
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    if attempt > 0:
                        debug_logger.output("iw_online_import.py", LogLevel.INFO, f"正在进行第 {attempt} 次识别重试...", fold_code="OI_WORKER")
                    
                    request = AIRequest(
                        prompt=self.prompt,
                        scene=AIScene.VISION,
                        image_base64=base64_image
                    )
                    
                    response = ai_manager.chat(request)
                    
                    if response.success:
                        self.debug_signal.emit("response", response.text)
                        self.finished_signal.emit(response.text)
                        debug_logger.output("iw_online_import.py", LogLevel.INFO, f"AI OCR 识别成功", fold_code="OI_WORKER")
                        return
                    else:
                        raise Exception(response.error or "识别失败")
                        
                except Exception as e:
                    last_exception = e
                    if "400" in str(e) and attempt == 0:
                        debug_logger.output("iw_online_import.py", LogLevel.WARNING, f"初次识别触发 400 错误: {e}", fold_code="OI_WORKER")
                    
                    if attempt < max_retries:
                        import time
                        time.sleep(1)
                    else:
                        raise last_exception
            
        except Exception as e:
            self.error_signal.emit(f"AI识别失败: {str(e)}")
class OnlineImportDialog(QDialog):
    """在线导入对话框"""
    def __init__(self, parent=None, window_size=None):
        super().__init__(parent)
        debug_logger.output("iw_online_import.py", LogLevel.INFO, "初始化 OnlineImportDialog", fold_code="OI_INIT")
        self.window_size = window_size
        self.selected_pdf_url = None
        self.selected_pdf_name = None
        self.settings_manager = SettingsManager() if SETTINGS_AVAILABLE else None
        self.current_path = ""  #当前浏览的路径
        self.path_history = []  #路径历史记录，用于返回上一级
        self.debug_prompt = ""  #存储调试信息
        self.debug_response = ""  #也存储调试信息
        self.parent_window = parent
        
        # 批处理状态变量
        self.is_batch_processing = False
        self.batch_queue = []
        self.batch_results = []
        self.batch_pdf_path = ""
        self.batch_extract_type = ""
        self.total_batch_count = 0
        
        self.is_sei_mode = self.settings_manager.get_online_import_mode() if self.settings_manager else False
        debug_logger.output("iw_online_import.py", LogLevel.INFO, f"在线导入模式: {'SEI' if self.is_sei_mode else 'GitHub'}", fold_code="OI_INIT")
        
        self.init_ui()
        
        # 设置窗口默认位置为主窗口中心
        if parent:
            self.center_on_parent()
        
        # 根据模式初始化
        if not self.is_sei_mode:
            debug_logger.output("iw_online_import.py", LogLevel.INFO, "正在加载 GitHub 模式 UI", fold_code="OI_INIT")
            self.load_root_directory()
        else:
            debug_logger.output("iw_online_import.py", LogLevel.INFO, "正在加载 SEI 模式 UI", fold_code="OI_INIT")
            self._init_sei_mode_ui()
    
    def center_on_parent(self):
        """将窗口居中显示在主窗口上"""
        debug_logger.output("iw_online_import.py", LogLevel.INFO, "将 OnlineImportDialog 居中", fold_code="OI_INIT")
        if self.parent_window:
            parent_geometry = self.parent_window.geometry()
            x = parent_geometry.x() + (parent_geometry.width() - self.width()) // 2
            y = parent_geometry.y() + (parent_geometry.height() - self.height()) // 2
            self.move(x, y)

    def init_ui(self):
        """初始化UI界面"""
        debug_logger.output("iw_online_import.py", LogLevel.INFO, "初始化 OnlineImportDialog UI", fold_code="OI_INIT")
        self.setWindowTitle("从教科书中导入 - 选择一本教科书并指定内容：")
        if self.window_size:
            self.setGeometry(self.window_size)
        else:
            self.resize(800, 600)
        
        global_font = self.parent_window.settings_manager.Custom.get_value("global_font", "微软雅黑") if self.parent_window else "微软雅黑"
        # 获取用户设置的背景颜色，默认为#E5E8EF
        background_color = self.settings_manager.get_Custom_value("background_color", "#E5E8EF") if self.settings_manager else "#E5E8EF"
        self.setStyleSheet(f"""
            QDialog {{background-color: {background_color};}}
            QPushButton {{font-family: "{global_font}"; background-color: white; color: black;
                    border: 2px solid gray; border-radius: 5px; font-weight: bold; padding: 5px;}}
            QPushButton:hover {{background-color: #f0f0f0;}}
            QLabel {{font-family: "{global_font}"; font-size: 14px; background-color: transparent;}}
            QLineEdit {{font-family: "{global_font}"; background-color: white; color: black;
               border: 2px solid gray; border-radius: 5px; padding: 5px;}}
            QTreeWidget {{font-family: "{global_font}"; background-color: white; color: black;
                 border: 2px solid gray; border-radius: 5px;}}
            """)
        
        self.main_layout = QVBoxLayout()
        
        # 路径导航和操作按钮
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
        
        self.main_layout.addLayout(nav_layout)
        
        # 目录浏览器
        self.tree_widget = QTreeWidget(self)
        self.tree_widget.setHeaderLabels(["名称", "类型", "大小"])
        self.tree_widget.setColumnWidth(0, 400)
        self.tree_widget.setColumnWidth(1, 100)
        self.tree_widget.setColumnWidth(2, 100)
        self.tree_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        
        self.main_layout.addWidget(self.tree_widget)
        
        # 底部控件
        bottom_layout = QHBoxLayout()
        
        # 页码输入框（放大到原来的2倍）
        self.page_input = QLineEdit()
        self.page_input.setPlaceholderText("页码")
        self.page_input.setMaximumWidth(160)
        
        # 提取内容输入框（放大到原来的2倍）
        self.extract_input = QLineEdit()
        self.extract_input.setPlaceholderText("提取内容（例如：注释）")
        self.extract_input.setMaximumWidth(320)
        
        self.status_label = QLabel("请选择PDF文件")
        self.status_label.setAlignment(Qt.AlignCenter)
        
        # 创建标签并保存为成员变量
        self.page_label = QLabel("页码:")
        self.extract_label = QLabel("提取内容:")
        
        bottom_layout.addWidget(self.page_label)
        bottom_layout.addWidget(self.page_input)
        bottom_layout.addWidget(self.extract_label)
        bottom_layout.addWidget(self.extract_input)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.status_label)
        bottom_layout.addStretch()
        
        self.main_layout.addLayout(bottom_layout)
        
        # 按钮
        button_layout = QHBoxLayout()
        self.cancel_button = QPushButton("取消", self)
        self.cancel_button.clicked.connect(self.reject)
        
        self.confirm_button = QPushButton("确认导入", self)
        self.confirm_button.clicked.connect(self.process_selection)
        self.confirm_button.setEnabled(False)
        
        button_layout.addWidget(self.cancel_button)
        button_layout.addStretch()
        button_layout.addWidget(self.confirm_button)
        
        self.main_layout.addLayout(button_layout)
        
        self.setLayout(self.main_layout)
        
        # 更新字体大小
        self._update_fonts()

    def _init_sei_mode_ui(self):
        debug_logger.output("iw_online_import.py", LogLevel.INFO, "初始化 SEI 模式 UI (手动输入)", fold_code="OI_SEI")
        self.back_button.setVisible(False)
        self.refresh_button.setVisible(False)
        self.path_label.setVisible(False)
        self.tree_widget.setVisible(False)
        self.resize(650, 380)
        self.setWindowTitle("从教科书中导入 - 智慧教育平台模式")

        self.status_label.setText("已自动打开智慧教育平台，请在浏览器中找到教材详情页，复制链接后粘贴到下方。")

        hint = QLabel('操作步骤：\n1. 浏览器已自动打开智慧教育平台\n2. 找到需要的教科书，进入详情页\n3. 复制浏览器地址栏的完整链接，粘贴到下方输入框\n4. 输入页码和提取内容后点击"确认导入"')
        hint.setWordWrap(True)

        url_layout = QHBoxLayout()
        self.sei_url_input = QLineEdit()
        self.sei_url_input.setPlaceholderText("粘贴教材详情页链接（例如 https://basic.smartedu.cn/tchMaterial/detail?contentType=assets_document&contentId=...）")
        self.sei_url_input.textChanged.connect(self._on_sei_url_changed)
        url_layout.addWidget(self.sei_url_input)

        open_btn = QPushButton("打开平台")
        open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(SMARTEDU_URL)))
        url_layout.addWidget(open_btn)

        self.main_layout.insertWidget(2, hint)
        self.main_layout.insertWidget(3, QLabel("教材链接:"))
        self.main_layout.insertLayout(4, url_layout)

        QDesktopServices.openUrl(QUrl(SMARTEDU_URL))

    def _on_sei_url_changed(self, text):
        self.confirm_button.setEnabled(bool(text.strip()))

    def _update_fonts(self):
        """更新字体大小"""
        debug_logger.output("iw_online_import.py", LogLevel.INFO, "更新 OnlineImportDialog 字体大小", fold_code="OI_INIT")
        if not self.parent_window:
            return
            
        current_width = self.width()
        current_height = self.height()
        
        min_font_size = 22
        max_font_size = 42
        default_width = 1366
        default_height = 768
        
        width_ratio = current_width / default_width
        height_ratio = current_height / default_height
        ratio = (width_ratio + height_ratio) / 2
        
        base_font_size = min_font_size + (max_font_size - min_font_size) * (ratio - 1)
        base_font_size = max(min_font_size, min(max_font_size, base_font_size))
        
        other_font_size = int(base_font_size * 0.5)
        global_font = self.parent_window.settings_manager.Custom.get_value("global_font", "微软雅黑") if self.parent_window else "微软雅黑"
        other_font = QFont(global_font, other_font_size)
        
        #设置所有标签 and 输入框的字体
        for widget in [self.path_label, self.status_label, self.page_label, self.extract_label]:
            if widget.isVisible():
                widget.setFont(other_font)
            
        for widget in [self.back_button, self.refresh_button, self.cancel_button, self.confirm_button]:
            if widget.isVisible():
                widget.setFont(other_font)
            
        for widget in [self.page_input, self.extract_input]:
            if widget.isVisible():
                widget.setFont(other_font)
            
        if self.tree_widget.isVisible():
            self.tree_widget.setFont(other_font)

    def resizeEvent(self, event):
        """处理窗口大小变化事件"""
        super().resizeEvent(event)
        self._update_fonts()

    def load_root_directory(self):
        """加载根目录"""
        debug_logger.output("iw_online_import.py", LogLevel.INFO, "正在加载 GitHub 根目录", fold_code="OI_DIR")
        self.current_path = ""
        self.path_history = []
        self.load_directory_contents("")

    def load_directory_contents(self, path):
        """加载指定路径的目录内容"""
        debug_logger.output("iw_online_import.py", LogLevel.INFO, f"正在加载目录内容: {path}", fold_code="OI_DIR")
        self.status_label.setText("正在加载目录内容...")
        self.tree_widget.clear()
        
        try:
            url = get_resource_url('textbook_api', path)
            debug_logger.output("iw_online_import.py", LogLevel.INFO, f"发送请求到: {url}", fold_code="OI_DIR")
            
            response = requests.get(url, verify=certifi.where(), timeout=15)
            response.raise_for_status()
            contents = response.json()
            debug_logger.output("iw_online_import.py", LogLevel.INFO, f"成功获取目录内容，项目数: {len(contents)}", fold_code="OI_DIR")
            
            #添加目录项
            for item in contents:
                # 跳过不需要显示的文件夹
                if item['name'] == '.cache':
                    continue
                elif '刷习题' in item['name']:
                    continue
                    
                if item['type'] == 'dir':
                    #文件夹
                    dir_item = QTreeWidgetItem([item['name'], "文件夹", ""])
                    dir_item.setData(0, Qt.UserRole, {'type': 'dir', 'path': item['path']})
                    self.tree_widget.addTopLevelItem(dir_item)
                elif item['type'] == 'file' and item['name'].lower().endswith('.pdf'):
                    # PDF文件（先存路径）
                    size = self.format_file_size(item.get('size', 0))
                    file_item = QTreeWidgetItem([item['name'], "PDF文件", size])
                    
                    file_item.setData(0, Qt.UserRole, {
                        'type': 'file', 
                        'path': item['path'],
                        'file_info': item
                    })
                    self.tree_widget.addTopLevelItem(file_item)
            
            self.path_label.setText(f"当前路径: /{path}")
            self.status_label.setText(f"加载完成，共 {len(contents)} 个项目")
            debug_logger.output("iw_online_import.py", LogLevel.INFO, f"当前路径已更新: /{path}", fold_code="OI_DIR")
            
        except Exception as e:
            debug_logger.output("iw_online_import.py", LogLevel.ERROR, f"加载目录内容失败: {e}", fold_code="OI_DIR")
            self.status_label.setText(f"加载失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"无法加载目录内容: ……{str(e)[0:10]}")

    def _get_download_url(self, original_url):
        """根据加速选项获取下载URL"""
        github_acceleration = self.settings_manager.get_github_acceleration() if self.settings_manager else 0
        
        if github_acceleration > 0:
            return apply_mirror(original_url, mirror_index=github_acceleration)
        else:  # 默认直接从GitHub获取
            return original_url

    def format_file_size(self, size_bytes):
        """格式化文件大小"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"

    def on_item_double_clicked(self, item, column):
        """处理项目双击事件"""
        item_data = item.data(0, Qt.UserRole)
        if not item_data:
            debug_logger.output("iw_online_import.py", LogLevel.WARNING, "双击的项目没有关联数据", fold_code="OI_DIR")
            return
            
        if item_data['type'] == 'dir':
            #进入目录
            debug_logger.output("iw_online_import.py", LogLevel.INFO, f"正在进入目录: {item_data['path']}", fold_code="OI_DIR")
            self.path_history.append(self.current_path)
            self.current_path = item_data['path']
            self.back_button.setEnabled(True)
            self.load_directory_contents(self.current_path)
        elif item_data['type'] == 'file':
            #选择PDF文件
            self.selected_file_info = item_data['file_info']
            self.selected_pdf_name = item.text(0)
            debug_logger.output("iw_online_import.py", LogLevel.INFO, f"已选择 PDF 文件: {self.selected_pdf_name}", fold_code="OI_DIR")
            self.status_label.setText(f"已选择: {self.selected_pdf_name}")
            self.confirm_button.setEnabled(True)
        else:
            debug_logger.output("iw_online_import.py", LogLevel.ERROR, f"未知的项目类型: {item_data.get('type')}", fold_code="OI_DIR")
            self.status_label.setText(f"发生错误，请截图并在github上提交issue（杂项→帮助→Github项目主页）")

    def go_back(self):
        """返回上一级目录"""
        if self.path_history:
            old_path = self.current_path
            self.current_path = self.path_history.pop()
            debug_logger.output("iw_online_import.py", LogLevel.INFO, f"返回上一级目录: {old_path} -> {self.current_path}", fold_code="OI_DIR")
            self.load_directory_contents(self.current_path)
            
            if not self.path_history:
                self.back_button.setEnabled(False)
        else:
            debug_logger.output("iw_online_import.py", LogLevel.WARNING, "已经在根目录，无法返回", fold_code="OI_DIR")

    def refresh_current_directory(self):
        """刷新当前目录"""
        debug_logger.output("iw_online_import.py", LogLevel.INFO, f"刷新当前目录: {self.current_path}", fold_code="OI_DIR")
        self.load_directory_contents(self.current_path)

    def process_sei_import(self):
        debug_logger.output("iw_online_import.py", LogLevel.INFO, "开始处理 SEI 导入流程", fold_code="OI_SEI")
        page_str = self.page_input.text().strip()
        pages = self.parse_page_string(page_str)
        
        if not pages:
            debug_logger.output("iw_online_import.py", LogLevel.WARNING, f"无效的页码输入: '{page_str}'", fold_code="OI_SEI")
            QMessageBox.warning(self, "提示", "请输入有效页码\n支持格式：\n- 单页：5\n- 范围：1-3 或 1~3\n- 列表：1,3,5 或 1、3、5\n- 混合：1-3, 5, 7~9")
            return
            
        if len(pages) > 4:
            reply = QMessageBox.question(self, "确认", f"您选择了 {len(pages)} 页进行导入，这可能需要较长时间。\n确认要继续吗？",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return
        
        extract_type = self.extract_input.text().strip() or "所有文字"
        debug_logger.output("iw_online_import.py", LogLevel.INFO, f"SEI 导入参数: 页码={pages}, 提取内容='{extract_type}'", fold_code="OI_SEI")
        
        loading_dialog = LoadingDialog(self)
        loading_dialog.text_label.setText("正在解析教材链接...")
        loading_dialog.show()
        QApplication.processEvents()
        
        try:
            sei_url = getattr(self, 'captured_sei_url', None)
            if not sei_url:
                debug_logger.output("iw_online_import.py", LogLevel.ERROR, "未捕获到教材链接", fold_code="OI_SEI")
                loading_dialog.close()
                QMessageBox.critical(self, "错误", "未捕获到教材链接，请重新选择教材。")
                return
            
            debug_logger.output("iw_online_import.py", LogLevel.INFO, f"使用捕获的链接: {sei_url}", fold_code="OI_SEI")
            loading_dialog.text_label.setText("正在解析下载链接...")
            QApplication.processEvents()
            
            download_url, pdf_title, _ = tchMP.parse(sei_url, bookmarks=False)
            if not download_url:
                debug_logger.output("iw_online_import.py", LogLevel.ERROR, "tchMP 解析下载链接失败", fold_code="OI_SEI")
                loading_dialog.close()
                QMessageBox.critical(self, "错误", "无法解析下载链接")
                return
            
            debug_logger.output("iw_online_import.py", LogLevel.INFO, f"解析成功: PDF 标题='{pdf_title}', URL='{download_url}'", fold_code="OI_SEI")
            
            downloads_dir = os.path.join(get_app_base_path(), "downloaded_pdfs")
            if not os.path.exists(downloads_dir):
                debug_logger.output("iw_online_import.py", LogLevel.INFO, f"创建下载目录: {downloads_dir}", fold_code="OI_SEI")
                os.makedirs(downloads_dir)
            
            if pdf_title:
                filename = re.sub(r'[^\w\-_.]', '_', pdf_title) + '.pdf'
            else:
                filename = self._extract_filename_from_url(sei_url)
                if not filename:
                    from datetime import datetime
                    filename = datetime.now().strftime("%H-%M-%S.pdf")
            
            saved_pdf_path = os.path.join(downloads_dir, filename)
            debug_logger.output("iw_online_import.py", LogLevel.INFO, f"目标保存路径: {saved_pdf_path}", fold_code="OI_SEI")
            
            if os.path.exists(saved_pdf_path):
                debug_logger.output("iw_online_import.py", LogLevel.INFO, "检测到本地已存在同名 PDF，跳过下载", fold_code="OI_SEI")
                loading_dialog.close()
                self.status_label.setText(f"使用本地PDF文件: {saved_pdf_path}")
                self.process_pdf_with_offset(saved_pdf_path, pages, extract_type)
                return
            
            debug_logger.output("iw_online_import.py", LogLevel.INFO, f"正在下载 PDF: {filename}", fold_code="OI_SEI")
            loading_dialog.text_label.setText(f"正在下载: {filename}")
            QApplication.processEvents()
            
            is_private_resource = "ndr-private.ykt.cbern.com.cn" in download_url.lower()
            if is_private_resource:
                debug_logger.output(
                    "iw_online_import.py", LogLevel.INFO,
                    "智慧教育平台私有资源使用 tchMP 会话直接下载",
                    fold_code="OI_SEI",
                )
                tchMP.download_file(download_url, saved_pdf_path)
            else:
                thread_num = self.settings_manager.get_download_thread_num() if self.settings_manager else 1
                debug_logger.output("iw_online_import.py", LogLevel.INFO, f"下载线程数: {thread_num}", fold_code="OI_SEI")
                referer = "https://ykt.cbern.com.cn/" if "ykt.cbern.com.cn" in download_url else None
                download(
                    url=download_url,
                    save_dir=downloads_dir,
                    filename=filename,
                    thread_num=thread_num,
                    verify_ssl=False,
                    referer=referer,
                )
            
            loading_dialog.close()
            
            if os.path.exists(saved_pdf_path):
                debug_logger.output("iw_online_import.py", LogLevel.INFO, f"PDF 下载成功，保存在: {saved_pdf_path}", fold_code="OI_SEI")
                self.status_label.setText(f"PDF已保存到: {saved_pdf_path}")
                self.process_pdf_with_offset(saved_pdf_path, pages, extract_type)
            else:
                debug_logger.output("iw_online_import.py", LogLevel.ERROR, "PDF 下载失败，未找到文件", fold_code="OI_SEI")
                QMessageBox.critical(self, "错误", "PDF文件下载失败")
                
        except Exception as e:
            debug_logger.output("iw_online_import.py", LogLevel.ERROR, f"SEI 导入处理失败: {e}", fold_code="OI_SEI")
            loading_dialog.close()
            QMessageBox.critical(self, "错误", f"处理失败: {str(e)}")

    def _extract_filename_from_url(self, url):
        """尝试从URL中提取文件名"""
        try:
            debug_logger.output("iw_online_import.py", LogLevel.INFO, f"尝试从 URL 提取文件名: {url}", fold_code="OI_SEI")
            # 尝试从URL路径中提取文件名
            parsed = re.search(r'/([^/]+?)(?:\.pdf)?(?:\?|$)', url)
            if parsed:
                filename = parsed.group(1)
                # 确保文件名以.pdf结尾
                if not filename.lower().endswith('.pdf'):
                    filename += '.pdf'
                # 清理文件名中的非法字符
                filename = re.sub(r'[^\w\-_.]', '_', filename)
                debug_logger.output("iw_online_import.py", LogLevel.INFO, f"成功提取文件名: {filename}", fold_code="OI_SEI")
                return filename
        except Exception as e:
            debug_logger.output("iw_online_import.py", LogLevel.WARNING, f"从 URL 提取文件名失败: {e}", fold_code="OI_SEI")
        return None

    def parse_page_string(self, page_str):
        """解析页码字符串，支持 a-b, a~b, a,b, a、b"""
        try:
            # 统一分隔符
            s = page_str.replace('，', ',').replace('、', ',')
            # 统一范围符
            s = s.replace('~', '-')
            
            parts = s.split(',')
            pages = set()
            
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                    
                if '-' in part:
                    if part.count('-') > 1: # 处理类似 1-3-5 的非法格式，或者负数（虽然这里不太可能有负数页码）
                        return None
                    start_str, end_str = part.split('-')
                    if not start_str.isdigit() or not end_str.isdigit():
                        return None
                    start, end = int(start_str), int(end_str)
                    if start > end:
                        start, end = end, start
                    pages.update(range(start, end + 1))
                else:
                    if not part.isdigit():
                        return None
                    pages.add(int(part))
            
            if not pages:
                return None
                
            return sorted(list(pages))
        except Exception:
            return None

    def process_selection(self):
        is_sei_mode = self.settings_manager.get_online_import_mode() if self.settings_manager else False
        debug_logger.output("iw_online_import.py", LogLevel.INFO, f"处理确认选择，当前 SEI 模式: {is_sei_mode}", fold_code="OI_CONFIRM")
        
        if is_sei_mode:
            url_text = self.sei_url_input.text().strip() if hasattr(self, 'sei_url_input') else ''
            if not url_text:
                QMessageBox.warning(self, "提示", "请粘贴教材详情页链接")
                return
            if 'contentId=' not in url_text:
                QMessageBox.warning(self, "提示", "链接格式不正确，请粘贴完整的教材详情页链接（需包含 contentId=...）")
                return
            self.captured_sei_url = url_text
            self.process_sei_import()
        else:
            # GitHub导入模式（原有逻辑）
            if not hasattr(self, 'selected_file_info'):
                debug_logger.output("iw_online_import.py", LogLevel.WARNING, "GitHub 模式下未选择文件", fold_code="OI_CONFIRM")
                QMessageBox.warning(self, "提示", "请先选择PDF文件")
                return
            
            page_str = self.page_input.text().strip()
            pages = self.parse_page_string(page_str)
            
            if not pages:
                debug_logger.output("iw_online_import.py", LogLevel.WARNING, f"GitHub 模式下无效页码: '{page_str}'", fold_code="OI_CONFIRM")
                QMessageBox.warning(self, "提示", "请输入有效页码\n支持格式：\n- 单页：5\n- 范围：1-3 或 1~3\n- 列表：1,3,5 或 1、3、5\n- 混合：1-3, 5, 7~9")
                return
            
            # 检查页码数量，超过4页提示用户
            if len(pages) > 4:
                reply = QMessageBox.question(self, "确认", f"您选择了 {len(pages)} 页进行导入，这可能需要较长时间。\n确认要继续吗？",
                                           QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.No:
                    return
            
            # 获取提取内容
            extract_type = self.extract_input.text().strip() or "所有文字"
            debug_logger.output("iw_online_import.py", LogLevel.INFO, f"GitHub 模式参数: 文件='{self.selected_pdf_name}', 页码={pages}, 提取内容='{extract_type}'", fold_code="OI_CONFIRM")
            
            # 使用AI OCR处理
            self.process_with_ai_ocr(pages, extract_type)

    def start_batch_processing(self, pdf_path, actual_pages, extract_type):
        """开始批处理多个页面"""
        self.batch_queue = list(actual_pages) # 复制一份
        self.batch_results = []
        self.batch_pdf_path = pdf_path
        self.batch_extract_type = extract_type
        self.is_batch_processing = True
        self.total_batch_count = len(actual_pages)
        
        debug_logger.output("iw_online_import.py", LogLevel.INFO, f"启动批处理，共 {len(actual_pages)} 页", fold_code="OI_BATCH")
        
        # 启动处理
        self.process_next_batch_item()

    def process_next_batch_item(self):
        """处理批次中的下一项"""
        if not self.batch_queue:
            # 全部完成
            debug_logger.output("iw_online_import.py", LogLevel.INFO, f"批处理完成，共 {len(self.batch_results)} 页", fold_code="OI_BATCH")
            self.is_batch_processing = False
            
            if self.batch_results:
                final_text = "\n\n".join(self.batch_results)
                self.result_text = final_text
                self.accept()
            else:
                QMessageBox.warning(self, "提示", "未能识别到任何文字")
            return

        current_page = self.batch_queue.pop(0)
        current_index = self.total_batch_count - len(self.batch_queue)
        debug_logger.output("iw_online_import.py", LogLevel.INFO, f"批处理进度: {current_index}/{self.total_batch_count}, 处理页码索引: {current_page}", fold_code="OI_BATCH")
        
        # 调用 process_single_page
        # 注意：process_single_page 会创建 LoadingDialog。
        self.process_single_page(self.batch_pdf_path, current_page, self.batch_extract_type)

    def process_with_ai_ocr(self, user_pages, extract_type):
        """AI处理PDF"""
        debug_logger.output("iw_online_import.py", LogLevel.INFO, f"开始 AI OCR 处理流程: 页码={user_pages}", fold_code="OI_CONFIRM")
        loading_dialog = LoadingDialog(self)
        text_per_line=int((len(self.selected_pdf_name)-8)/2)
        loading_dialog.text_label.setText(f"正在处理 ……\n{self.selected_pdf_name[8:8+text_per_line]}\n{self.selected_pdf_name[8+text_per_line:9+2*text_per_line]}")  # 显示处理中的PDF名称
        loading_dialog.show()
        QApplication.processEvents()
        try:
            # 检查本地是否有同名PDF
            local_pdf_path = self._check_local_pdf(self.selected_pdf_name)
            
            if local_pdf_path:
                debug_logger.output("iw_online_import.py", LogLevel.INFO, f"使用本地缓存 PDF: {local_pdf_path}", fold_code="OI_CONFIRM")
                self.status_label.setText(f"使用本地PDF: {local_pdf_path}")
                loading_dialog.close()
                self.process_pdf_with_offset(local_pdf_path, user_pages, extract_type)
            else:
                debug_logger.output("iw_online_import.py", LogLevel.INFO, "本地无缓存，准备下载 PDF", fold_code="OI_CONFIRM")
                self._download_pdf_and_process(user_pages, extract_type, loading_dialog)
                
        except Exception as e:
            debug_logger.output("iw_online_import.py", LogLevel.ERROR, f"AI OCR 处理失败: {e}", fold_code="OI_CONFIRM")
            loading_dialog.close()
            QMessageBox.critical(self, "错误", f"处理失败: {str(e)}")

    def _check_local_pdf(self, pdf_name):
        """检查本地是否有同名PDF"""
        try:
            downloads_dir = os.path.join(get_app_base_path(), "downloaded_pdfs")
            debug_logger.output("iw_online_import.py", LogLevel.INFO, f"检查本地缓存目录: {downloads_dir}", fold_code="OI_FILE")
            if not os.path.exists(downloads_dir):
                debug_logger.output("iw_online_import.py", LogLevel.INFO, "本地缓存目录不存在", fold_code="OI_FILE")
                return None
            
            # 首先尝试直接匹配
            direct_path = os.path.join(downloads_dir, pdf_name)
            if os.path.exists(direct_path):
                debug_logger.output("iw_online_import.py", LogLevel.INFO, f"找到直接匹配的本地文件: {direct_path}", fold_code="OI_FILE")
                return direct_path
            
            # 如果是SEI模式，尝试转换文件名格式
            if self.is_sei_mode:
                converted_filename = self._convert_sei_filename(pdf_name)
                converted_path = os.path.join(downloads_dir, converted_filename)
                debug_logger.output("iw_online_import.py", LogLevel.INFO, f"SEI 模式尝试匹配转换后的文件名: {converted_filename}", fold_code="OI_FILE")
                if os.path.exists(converted_path):
                    debug_logger.output("iw_online_import.py", LogLevel.INFO, f"找到转换后匹配的本地文件: {converted_path}", fold_code="OI_FILE")
                    return converted_path
            
            # 最后尝试安全名称匹配
            safe_name = re.sub(r'[^\w\-_.]', '_', pdf_name)
            debug_logger.output("iw_online_import.py", LogLevel.INFO, f"尝试安全名称匹配: {safe_name}", fold_code="OI_FILE")
            for filename in os.listdir(downloads_dir):
                if filename.endswith('.pdf'):
                    local_safe_name = re.sub(r'[^\w\-_.]', '_', filename)
                    if safe_name == local_safe_name:
                        full_path = os.path.join(downloads_dir, filename)
                        debug_logger.output("iw_online_import.py", LogLevel.INFO, f"找到安全名称匹配的本地文件: {full_path}", fold_code="OI_FILE")
                        return full_path
            
            debug_logger.output("iw_online_import.py", LogLevel.INFO, "未找到匹配的本地 PDF 文件", fold_code="OI_FILE")
            return None
        except Exception as e:
            debug_logger.output("iw_online_import.py", LogLevel.WARNING, f"检查本地 PDF 失败: {e}", fold_code="OI_FILE")
            return None

    def _convert_sei_filename(self, sei_filename):
        """将SEI显示的文件名转换为本地存储的文件名格式"""
        debug_logger.output("iw_online_import.py", LogLevel.INFO, f"转换 SEI 文件名: {sei_filename}", fold_code="OI_FILE")
        # 替换特殊字符为下划线
        converted = sei_filename.replace("（", "_")
        converted = converted.replace("）", "_")
        converted = converted.replace("·", "_")
        converted = converted.replace(" ", "_")
        converted = converted.replace("/", "_")
        converted = converted.replace("\\", "_")
        # 去除多余的下划线
        converted = re.sub(r'__+', '_', converted)
        # 添加.pdf后缀
        if not converted.endswith('.pdf'):
            converted += '.pdf'
        debug_logger.output("iw_online_import.py", LogLevel.INFO, f"转换后文件名: {converted}", fold_code="OI_FILE")
        return converted
    
    def _download_pdf_and_process(self, user_pages, extract_type, loading_dialog):
        """下载PDF并处理"""
        debug_logger.output("iw_online_import.py", LogLevel.INFO, "开始 GitHub 模式下载流程", fold_code="OI_FILE")
        try:
            # 检查本地是否已存在PDF文件
            pdf_name = self.selected_file_info.get('name', 'unknown.pdf')
            downloads_dir = os.path.join(get_app_base_path(), "downloaded_pdfs")
            saved_pdf_path = os.path.join(downloads_dir, pdf_name)
            
            # 检查本地PDF文件
            local_pdf_path = self._check_local_pdf(pdf_name)
            if local_pdf_path:
                debug_logger.output("iw_online_import.py", LogLevel.INFO, f"检测到本地已存在 PDF: {local_pdf_path}", fold_code="OI_FILE")
                loading_dialog.close()
                self.status_label.setText(f"使用本地PDF文件: {local_pdf_path}")
                self.ask_for_page_offset(local_pdf_path, user_pages, extract_type)
                return
            
            #获取下载URL
            pdf_url = self._get_pdf_download_url(self.selected_file_info)
            # 根据GitHub下载加速设置构建最终下载URL
            final_download_url = self._get_download_url(pdf_url)
            debug_logger.output("iw_online_import.py", LogLevel.INFO, f"下载 URL: {final_download_url}", fold_code="OI_FILE")
            
            #获取用户设置的下载线程数
            thread_num = self.settings_manager.get_download_thread_num() if self.settings_manager else 5
            debug_logger.output("iw_online_import.py", LogLevel.INFO, f"下载线程数: {thread_num}", fold_code="OI_FILE")
            
            #使用多线程下载器下载文件
            download(
                url=final_download_url,
                save_dir=downloads_dir,
                filename=pdf_name,
                thread_num=thread_num,
                verify_ssl=False
            )
            
            loading_dialog.close()
            
            if os.path.exists(saved_pdf_path):
                debug_logger.output("iw_online_import.py", LogLevel.INFO, f"PDF 下载成功: {saved_pdf_path}", fold_code="OI_FILE")
                self.status_label.setText(f"PDF已保存到: {saved_pdf_path}")
                #询问实际页码
                self.ask_for_page_offset(saved_pdf_path, user_pages, extract_type)
            else:
                debug_logger.output("iw_online_import.py", LogLevel.ERROR, "PDF 下载后未找到文件", fold_code="OI_FILE")
                QMessageBox.critical(self, "错误", "PDF文件保存失败")
                
        except Exception as e:
            debug_logger.output("iw_online_import.py", LogLevel.ERROR, f"下载 PDF 流程出错: {e}", fold_code="OI_FILE")
            loading_dialog.close()
            QMessageBox.critical(self, "错误", f"下载失败: {str(e)}")

    def ask_for_page_offset(self, pdf_path, user_pages, extract_type):
        """询问用户页码偏移量"""
        debug_logger.output("iw_online_import.py", LogLevel.INFO, f"弹出页码偏移对话框: {os.path.basename(pdf_path)}", fold_code="OI_FILE")
        
        # 使用第一个页码作为参考
        first_page = user_pages[0]
        
        dialog = PageOffsetDialog(self, os.path.basename(pdf_path), str(first_page), pdf_path)
        if dialog.exec_() == QDialog.Accepted and dialog.actual_page:
            actual_page = int(dialog.actual_page)
            #计算偏移量
            offset = actual_page - first_page
            debug_logger.output("iw_online_import.py", LogLevel.INFO, f"用户设置实际页码: {actual_page}, 偏移量: {offset}", fold_code="OI_FILE")
            #保存偏移量
            self._save_page_offset(os.path.basename(pdf_path), offset)
            #使用实际页码处理PDF
            self.process_pdf_with_offset(pdf_path, user_pages, extract_type)
        else:
            debug_logger.output("iw_online_import.py", LogLevel.INFO, "用户取消了页码偏移设置", fold_code="OI_FILE")

    def _save_page_offset(self, pdf_name, offset):
        """保存页码偏移量到设置文件"""
        try:
            if self.settings_manager:
                setting_name = f"pdfOffset_{pdf_name}"
                debug_logger.output("iw_online_import.py", LogLevel.INFO, f"保存偏移量: {setting_name}={offset}", fold_code="OI_FILE")
                self.settings_manager.set_offset_value(setting_name, str(offset))
        except Exception as e:
            debug_logger.output("iw_online_import.py", LogLevel.WARNING, f"保存偏移量失败: {e}", fold_code="OI_FILE")

    def _get_page_offset(self, pdf_name):
        """从设置文件获取页码偏移量"""
        try:
            if self.settings_manager:
                setting_name = f"pdfOffset_{pdf_name}"
                offset_str = self.settings_manager.get_offset_value(setting_name, "")
                if offset_str and (offset_str.isdigit() or (offset_str.startswith('-') and offset_str[1:].isdigit())):
                    offset = int(offset_str)
                    debug_logger.output("iw_online_import.py", LogLevel.INFO, f"获取到保存的偏移量: {setting_name}={offset}", fold_code="OI_FILE")
                    return offset
            return None
        except Exception as e:
            debug_logger.output("iw_online_import.py", LogLevel.WARNING, f"获取偏移量失败: {e}", fold_code="OI_FILE")
            return None

    def process_pdf_with_offset(self, pdf_path, user_pages, extract_type):
        """使用偏移量处理PDF"""
        pdf_name = os.path.basename(pdf_path)
        debug_logger.output("iw_online_import.py", LogLevel.INFO, f"使用偏移量处理 PDF: {pdf_name}, 用户输入页码: {user_pages}", fold_code="OI_FILE")
        offset = self._get_page_offset(pdf_name)
        
        if offset is not None:
            #有偏移量，直接算页码
            actual_pages = [p + offset - 1 for p in user_pages] # 0-based索引
            debug_logger.output("iw_online_import.py", LogLevel.INFO, f"应用偏移量 {offset}，实际页码列表: {actual_pages}", fold_code="OI_FILE")
            
            # 启动批处理
            self.start_batch_processing(pdf_path, actual_pages, extract_type)
        else:
            #没有偏移量，显示对话框让用户确认页码
            debug_logger.output("iw_online_import.py", LogLevel.INFO, "未找到保存的偏移量，需要询问用户", fold_code="OI_FILE")
            self.ask_for_page_offset(pdf_path, user_pages, extract_type)

    def _open_pdf_file(self, pdf_path):
        """使用系统默认方式打开PDF文件"""
        debug_logger.output("iw_online_import.py", LogLevel.INFO, f"使用系统默认方式打开 PDF: {pdf_path}", fold_code="OI_FILE")
        try:
            if sys.platform == "win32":  # Windows
                os.startfile(pdf_path)
            elif sys.platform == "darwin":  # Mac
                os.system(f"open '{pdf_path}'")
            else:  # Linux
                os.system(f"xdg-open '{pdf_path}'")
        except Exception as e:
            debug_logger.output("iw_online_import.py", LogLevel.ERROR, f"打开 PDF 失败: {e}", fold_code="OI_FILE")

    def process_single_page(self, pdf_path, page_number, extract_type):
        """处理单页PDF"""
        debug_logger.output("iw_online_import.py", LogLevel.INFO, f"开始处理单页 PDF: {os.path.basename(pdf_path)}, 索引={page_number}", fold_code="OI_FILE")
        loading_dialog = LoadingDialog(self)
        loading_dialog.text_label.setText(f"正在转换第{page_number+1}页为图片...")
        
        if self.is_batch_processing and self.total_batch_count > 1:
            # 计算已完成的数量：总数 - (队列中剩余 + 当前正在处理的1个)
            completed_count = self.total_batch_count - len(self.batch_queue) - 1
            # 更新进度条，显示当前批处理进度
            loading_dialog.update_progress(completed_count, self.total_batch_count)
            
        loading_dialog.show()
        QApplication.processEvents()
        try:
            #转图像
            image_path = self._convert_pdf_page_to_image(pdf_path, page_number)
            loading_dialog.close()
            
            if image_path:
                debug_logger.output("iw_online_import.py", LogLevel.INFO, f"页面已转换为图片: {image_path}", fold_code="OI_FILE")
                self.process_image_with_ai(image_path, extract_type, pdf_path)
            else:
                debug_logger.output("iw_online_import.py", LogLevel.ERROR, "PDF 页面转换图片失败", fold_code="OI_FILE")
                QMessageBox.critical(self, "错误", "PDF页面转换失败")
                
        except Exception as e:
            debug_logger.output("iw_online_import.py", LogLevel.ERROR, f"处理单页 PDF 异常: {e}", fold_code="OI_FILE")
            loading_dialog.close()
            QMessageBox.critical(self, "错误", f"处理失败: {str(e)}")

    def _convert_pdf_page_to_image(self, pdf_path, page_number):
        """将PDF单页转换为图像"""
        debug_logger.output("iw_online_import.py", LogLevel.INFO, f"正在将 PDF 页转换为图像: {os.path.basename(pdf_path)}, 索引={page_number}", fold_code="OI_FILE")
        try:
            #打开文档
            doc = fitz.open(pdf_path)
            if page_number < 0 or page_number >= doc.page_count:
                debug_logger.output("iw_online_import.py", LogLevel.ERROR, f"页码超出范围: {page_number}, 总页数: {doc.page_count}", fold_code="OI_FILE")
                doc.close()
                raise ValueError(f"页码超出范围，共{doc.page_count}页")
            
            #指定页面
            page = doc.load_page(page_number)
            
            #3倍放大
            matrix = fitz.Matrix(3, 3)
            pix = page.get_pixmap(matrix=matrix)
            
            #转换为PIL图像
            img_data = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_data))
            
            doc.close()
            
            #保存图像到临时文件
            cache_dir = os.path.join(get_app_base_path(), 'cache')
            os.makedirs(cache_dir, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=cache_dir, suffix=f"_page{page_number+1}.png", delete=False) as temp_img:
                image.save(temp_img, "PNG", quality=95)
                temp_name = temp_img.name
                debug_logger.output("iw_online_import.py", LogLevel.INFO, f"临时图片已保存: {temp_name}", fold_code="OI_FILE")
                return temp_name
            
        except Exception as e:
            debug_logger.output("iw_online_import.py", LogLevel.ERROR, f"PDF 转图像失败: {e}", fold_code="OI_FILE")
            raise Exception(f"PDF页面转图像失败: {str(e)}")

    @staticmethod
    def _get_pdf_download_url(file_info):
        """获取PDF文件的真实下载URL"""
        try:
            #直接用API返回的download_url
            if 'download_url' in file_info and file_info['download_url']:
                return file_info['download_url']
            
            #构建原始GitHub URL（使用 resource_urls 统一管理）
            file_path = file_info['path']
            raw_url = get_resource_url('textbook_raw', file_path)
            return raw_url
            
        except Exception as e:
            raise Exception(f"无法获取PDF下载URL: {str(e)}")

    @staticmethod
    def _save_pdf_to_directory(pdf_data, pdf_name):
        """保存PDF文件到程序目录"""
        try:
            downloads_dir = os.path.join(get_app_base_path(), "downloaded_pdfs")
            if not os.path.exists(downloads_dir):
                os.makedirs(downloads_dir)
            safe_name = re.sub(r'[^\w\-_.]', '_', pdf_name)
            filepath = os.path.join(downloads_dir, safe_name)
            if os.path.exists(filepath):
                return filepath
            
            with open(filepath, 'wb') as f:
                f.write(pdf_data)
            
            return filepath
        except Exception as e:
            # 保存PDF失败，静默处理
            return ""

    def process_image_with_ai(self, image_path, extract_type, pdf_path=""):
        """使用AI处理图像"""
        debug_logger.output("iw_online_import.py", LogLevel.INFO, f"开始 AI 图像识别: 提取类型={extract_type}", fold_code="OI_AI")
        
        from ai_manager import get_ai_manager, AIScene
        ai_manager = get_ai_manager()
        default_model = ai_manager.get_default_model(AIScene.VISION)
        
        if not default_model:
            configured = ai_manager.get_configured_providers(AIScene.VISION)
            debug_logger.output("iw_online_import.py", LogLevel.WARNING, "未配置 AI API Key", fold_code="OI_AI")
            if configured:
                QMessageBox.warning(self, "API Key未设置", f"请在设置界面中配置{configured[0]} API Key")
            else:
                QMessageBox.warning(self, "API Key未设置", "请在设置界面中配置 AI API Key")
            return
        
        prompt = f"""
请仔细识别这张图片中的所有文字内容。
要求：
1. 准确识别所有文字，包括标题、正文、注释等
2. 将₁②⑶⒋Ⅴ❻㈦之类特殊数字符号转为普通数字
3. 忽略所有注释角标
4. 保持原文的格式和结构
5. 输出纯文字格式，不要添加额外说明
6. 说出公式而不要使用latex，如:
    b²-4ac→"b的平方减去4倍的ac"、
    傅里叶正变换公式→"F 括号 ω 等于，从负无穷到正无穷的积分，被积函数是 f 括号 t 乘以 e 的负 jωt 次方，最后乘以 dt"
7. 若不是中文，将所有的句号、逗号（或二者在其他语言中的等效物）转换为中文的"句号""逗号"二字
请提取{extract_type}："""
        
        loading_dialog = LoadingDialog(self)
        loading_dialog.text_label.setText(f"AI正在识别图片中的{extract_type}...")
        
        if self.is_batch_processing and self.total_batch_count > 1:
            completed_count = self.total_batch_count - len(self.batch_queue) - 1
            loading_dialog.update_progress(completed_count, self.total_batch_count)
            
        loading_dialog.show()
        QApplication.processEvents()
        
        debug_logger.output("iw_online_import.py", LogLevel.INFO, f"启动 AIOCRWorker, 图片: {image_path}", fold_code="OI_AI")
        self.ai_worker = AIOCRWorker(image_path, prompt)
        self.ai_worker.finished_signal.connect(lambda text: self.on_ai_finished(text, loading_dialog, image_path))
        self.ai_worker.error_signal.connect(lambda err: self.on_ai_error(err, loading_dialog, image_path))
        self.ai_worker.start()

    def on_ai_finished(self, text, loading_dialog, image_path):
        """AI处理完成"""
        debug_logger.output("iw_online_import.py", LogLevel.INFO, "AI 图像识别成功完成", fold_code="OI_AI")
        loading_dialog.close()
        
        #清理临时图像
        if os.path.exists(image_path):
            try:
                os.unlink(image_path)
                debug_logger.output("iw_online_import.py", LogLevel.INFO, f"已清理临时图片: {image_path}", fold_code="OI_AI")
            except Exception as e:
                debug_logger.output("iw_online_import.py", LogLevel.WARNING, f"清理临时图片失败: {e}", fold_code="OI_AI")
        
        if text:
            debug_logger.output("iw_online_import.py", LogLevel.INFO, f"成功获取识别文本，长度: {len(text)}", fold_code="OI_AI")
            if self.is_batch_processing:
                self.batch_results.append(text)
                self.process_next_batch_item()
            else:
                self.result_text = text
                self.accept()
        else:
            debug_logger.output("iw_online_import.py", LogLevel.WARNING, "AI 未能识别到任何文字", fold_code="OI_AI")
            if self.is_batch_processing:
                self.batch_results.append(f"[第 {self.total_batch_count - len(self.batch_queue)} 页识别为空]")
                self.process_next_batch_item()
            else:
                QMessageBox.warning(self, "提示", "未能识别到文字")

    def on_ai_error(self, error_message, loading_dialog, image_path):
        """AI处理错误"""
        debug_logger.output("iw_online_import.py", LogLevel.ERROR, f"AI 图像识别发生错误: {error_message}", fold_code="OI_AI")
        loading_dialog.close()
        
        #清理临时图像
        if os.path.exists(image_path):
            try:
                os.unlink(image_path)
                debug_logger.output("iw_online_import.py", LogLevel.INFO, f"已清理临时图片: {image_path}", fold_code="OI_AI")
            except Exception as e:
                debug_logger.output("iw_online_import.py", LogLevel.WARNING, f"清理临时图片失败: {e}", fold_code="OI_AI")
        
        if self.is_batch_processing:
            error_text = f"[第 {self.total_batch_count - len(self.batch_queue)} 页识别失败: {error_message}]"
            self.batch_results.append(error_text)
            QMessageBox.warning(self, "处理出错", f"当前页面处理失败: {error_message}\n将继续处理下一页。")
            self.process_next_batch_item()
        else:
            QMessageBox.critical(self, "错误", error_message)

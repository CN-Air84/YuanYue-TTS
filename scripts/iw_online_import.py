# coding=utf-8
import sys
import os
import re
import base64
import io
import tempfile
import subprocess
import requests
from multiprocessing import Event
from PyQt5.QtWidgets import (QApplication, QPushButton, QLineEdit, QTreeWidget, 
                            QMessageBox, QVBoxLayout, QHBoxLayout, QDialog, QLabel, 
                            QTreeWidgetItem)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from multi_thread_downloader import download
from PIL import Image
import certifi
import fitz  # PyMuPDF
import tchMP

from misc_func import get_app_base_path

try:
    from misc_func import SettingsManager
    SETTINGS_AVAILABLE = True
except ImportError:
    SETTINGS_AVAILABLE = False

from iw_dialogs import LoadingDialog, PageOffsetDialog

class SEIRunnerThread(QThread):
    """运行SmartEduInteract.exe的线程"""
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    
    def __init__(self, exe_path):
        super().__init__()
        self.exe_path = exe_path
    
    def run(self):
        """运行SEI.exe"""
        try:
            process = subprocess.Popen([self.exe_path], cwd=os.path.dirname(self.exe_path))
            process.wait()
            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))

class AIOCRWorker(QThread):
    """AI OCR识别线程"""
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    debug_signal = pyqtSignal(str, str)  # 类型, 内容
    
    def __init__(self, api_key, image_path, prompt):
        super().__init__()
        self.api_key = api_key
        self.image_path = image_path
        self.prompt = prompt
    
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
            
            #发送提示词
            self.debug_signal.emit("prompt", self.prompt)
            
            response = client.chat.completions.create(
                model="glm-4v-flash",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self.prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                        ]
                    }
                ],
                max_tokens=1000
            )
            result = response.choices[0].message.content
            self.debug_signal.emit("response", result)
            self.finished_signal.emit(result)
            
        except Exception as e:
            self.error_signal.emit(f"ChatGLM识别失败: {str(e)}")
class OnlineImportDialog(QDialog):
    """在线导入对话框"""
    def __init__(self, parent=None, window_size=None):
        super().__init__(parent)
        self.window_size = window_size
        self.selected_pdf_url = None
        self.selected_pdf_name = None
        self.settings_manager = SettingsManager() if SETTINGS_AVAILABLE else None
        self.current_path = ""  #当前浏览的路径
        self.path_history = []  #路径历史记录，用于返回上一级
        self.debug_prompt = ""  #存储调试信息
        self.debug_response = ""  #也存储调试信息
        self.parent_window = parent
        
        # 检查在线导入模式
        self.is_sei_mode = self.settings_manager.get_online_import_mode() if self.settings_manager else False
        print(f"[DEBUG] OnlineImportDialog: is_sei_mode = {self.is_sei_mode}")
        
        self.init_ui()
        
        # 设置窗口默认位置为主窗口中心
        if parent:
            self.center_on_parent()
        
        # 根据模式初始化
        if not self.is_sei_mode:
            print("[DEBUG] Loading GitHub mode UI")
            self.load_root_directory()
        else:
            print("[DEBUG] Loading SEI mode UI")
            self._init_sei_mode_ui()
    
    def center_on_parent(self):
        """将窗口居中显示在主窗口上"""
        if self.parent_window:
            parent_geometry = self.parent_window.geometry()
            x = parent_geometry.x() + (parent_geometry.width() - self.width()) // 2
            y = parent_geometry.y() + (parent_geometry.height() - self.height()) // 2
            self.move(x, y)

    def init_ui(self):
        """初始化UI界面"""
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
            QLabel {{font-family: "{global_font}"; font-size: 14px;}}
            QLineEdit {{font-family: "{global_font}"; background-color: white; color: black;
               border: 2px solid gray; border-radius: 5px; padding: 5px;}}
            QTreeWidget {{font-family: "{global_font}"; background-color: white; color: black;
                 border: 2px solid gray; border-radius: 5px;}}
            """)
        
        main_layout = QVBoxLayout()
        
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
        
        main_layout.addLayout(nav_layout)
        
        # 目录浏览器
        self.tree_widget = QTreeWidget(self)
        self.tree_widget.setHeaderLabels(["名称", "类型", "大小"])
        self.tree_widget.setColumnWidth(0, 400)
        self.tree_widget.setColumnWidth(1, 100)
        self.tree_widget.setColumnWidth(2, 100)
        self.tree_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        
        main_layout.addWidget(self.tree_widget)
        
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
        
        main_layout.addLayout(bottom_layout)
        
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
        
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
        
        # 更新字体大小
        self._update_fonts()

    def _init_sei_mode_ui(self):
        """初始化SEI模式的UI"""
        # 隐藏GitHub模式相关的UI元素
        self.back_button.setVisible(False)
        self.refresh_button.setVisible(False)
        self.path_label.setVisible(False)
        self.tree_widget.setVisible(False)
        
        # 设置合适的窗口大小
        self.resize(500, 300)
        
        # 隐藏页码和提取内容输入框，先启动SEI.exe
        self.page_label.setVisible(False)
        self.page_input.setVisible(False)
        self.extract_label.setVisible(False)
        self.extract_input.setVisible(False)
        self.confirm_button.setEnabled(False)
        
        # 更新状态标签
        self.status_label.setText("智慧教育平台导入模式\n正在呼出智慧教育平台交互窗口……\n请选择需要的书籍，选择后程序会自动解析。")
        
        # 更新窗口标题
        self.setWindowTitle("从教科书中导入 - 智慧教育平台模式")
        
        # 启动SEI.exe
        self._launch_sei_and_show_inputs()

    def _launch_sei_and_show_inputs(self):
        """启动SEI.exe并在结束后显示输入框"""
        print("[DEBUG] _launch_sei_and_show_inputs: Starting SEI.exe")
        
        try:
            # 启动SmartEduInteract.exe并等待结束
            sei_exe_path = os.path.join(get_app_base_path(), "SEI", "SmartEduInteract.exe")
            if not os.path.exists(sei_exe_path):
                QMessageBox.critical(self, "错误", f"找不到SmartEduInteract.exe\n路径: {sei_exe_path}")
                return
            
            # 使用新线程运行SEI，避免阻塞主线程
            print(f"[DEBUG] _launch_sei_and_show_inputs: Launching {sei_exe_path}")
            self.status_label.setText("正在呼出智慧教育平台交互窗口...")
            
            self.sei_thread = SEIRunnerThread(sei_exe_path)
            self.sei_thread.finished_signal.connect(self._on_sei_finished)
            self.sei_thread.error_signal.connect(self._on_sei_error)
            self.sei_thread.start()
            print("[DEBUG] _launch_sei_and_show_inputs: SEI thread started")
            
        except Exception as e:
            print(f"[DEBUG] _launch_sei_and_show_inputs: Exception - {e}")
            QMessageBox.critical(self, "错误", f"启动SmartEduInteract失败: {str(e)}")
    
    def _on_sei_finished(self):
        """SEI运行完成后的回调"""
        print("[DEBUG] _on_sei_finished: SEI.exe finished")
        
        # 显示输入框
        self.page_label.setVisible(True)
        self.page_input.setVisible(True)
        self.extract_label.setVisible(True)
        self.extract_input.setVisible(True)
        self.confirm_button.setEnabled(True)
        self.status_label.setVisible(False)
    
    def _on_sei_error(self, error_msg):
        """SEI运行失败的回调"""
        print(f"[DEBUG] _on_sei_error: {error_msg}")
        QMessageBox.critical(self, "错误", f"运行SmartEduInteract失败: {error_msg}")

    def _update_fonts(self):
        """更新字体大小"""
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
        
        #设置所有标签和输入框的字体
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
        self.current_path = ""
        self.path_history = []
        self.load_directory_contents("")

    def load_directory_contents(self, path):
        """加载指定路径的目录内容"""
        self.status_label.setText("正在加载目录内容...")
        self.tree_widget.clear()
        
        try:
            url = f"https://api.github.com/repos/TapXWorld/ChinaTextbook/contents/{path}"
            
            response = requests.get(url, verify=certifi.where(), timeout=15)
            response.raise_for_status()
            contents = response.json()
            
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
            
        except Exception as e:
            self.status_label.setText(f"加载失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"无法加载目录内容: ……{str(e)[0:10]}")

    def _get_download_url(self, original_url):
        """根据加速选项获取下载URL"""
        github_acceleration = self.settings_manager.get_github_acceleration() if self.settings_manager else 0
        
        if github_acceleration == 1:  # ghfast镜像
            return f"https://ghfast.top/{original_url}"
        elif github_acceleration == 2:  # ghproxy主站            
            return f"https://gh-proxy.org/{original_url}"
        elif github_acceleration == 3:  # ghproxy HK            
            return f"https://hk.gh-proxy.org/{original_url}"
        elif github_acceleration == 4:  # ghproxy edgeone
            return f"https://edgeone.gh-proxy.org/{original_url}"
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
            return
            
        if item_data['type'] == 'dir':
            #进入目录
            self.path_history.append(self.current_path)
            self.current_path = item_data['path']
            self.back_button.setEnabled(True)
            self.load_directory_contents(self.current_path)
        elif item_data['type'] == 'file':
            #选择PDF文件
            self.selected_file_info = item_data['file_info']
            self.selected_pdf_name = item.text(0)
            self.status_label.setText(f"已选择: {self.selected_pdf_name}")
            self.confirm_button.setEnabled(True)
        else:
            self.status_label.setText(f"发生错误，请截图并在github上提交issue（杂项→帮助→Github项目主页）")

    def go_back(self):
        """返回上一级目录"""
        if self.path_history:
            self.current_path = self.path_history.pop()
            self.load_directory_contents(self.current_path)
            
            if not self.path_history:
                self.back_button.setEnabled(False)

    def refresh_current_directory(self):
        """刷新当前目录"""
        self.load_directory_contents(self.current_path)

    def process_sei_import(self):
        """处理通过SmartEduInteract.exe的在线导入（第二种解决方案）"""
        # 首先检查页码输入
        page_str = self.page_input.text().strip()
        if not page_str or not page_str.isdigit():
            QMessageBox.warning(self, "提示", "请输入有效页码")
            return
        
        page_number = int(page_str)
        extract_type = self.extract_input.text().strip() or "所有文字"
        
        loading_dialog = LoadingDialog(self)
        loading_dialog.text_label.setText("正在读取链接信息...")
        loading_dialog.show()
        QApplication.processEvents()
        
        try:
            # 1. 读取links.txt文件
            links_txt_path = os.path.join(get_app_base_path(), "SEI", "links.txt")
            if not os.path.exists(links_txt_path):
                loading_dialog.close()
                QMessageBox.critical(self, "错误", f"找不到links.txt\n路径: {links_txt_path}")
                return
            
            # 2. 提取最后一串链接
            last_link = self._extract_last_link_from_file(links_txt_path)
            if not last_link:
                loading_dialog.close()
                QMessageBox.critical(self, "错误", "未能从links.txt中提取到有效链接")
                return
            
            # 3. 调用tchMP.parse解析下载链接和标题
            loading_dialog.text_label.setText("正在解析下载链接...")
            QApplication.processEvents()
            
            download_url, pdf_title, _ = tchMP.parse(last_link, bookmarks=False)
            if not download_url:
                loading_dialog.close()
                QMessageBox.critical(self, "错误", "无法解析下载链接")
                return
            
            print(f"[DEBUG] process_sei_import: PDF title = {pdf_title}")
            
            # 4. 确定保存路径和文件名
            downloads_dir = os.path.join(get_app_base_path(), "downloaded_pdfs")
            if not os.path.exists(downloads_dir):
                os.makedirs(downloads_dir)
            
            # 使用服务器提供的标题作为文件名
            if pdf_title:
                filename = re.sub(r'[^\w\-_.]', '_', pdf_title) + '.pdf'
            else:
                # 如果没有标题，尝试从链接中提取文件名，如果没有则使用时间戳
                filename = self._extract_filename_from_url(last_link)
                if not filename:
                    # 使用hh-mm-ss.pdf格式
                    from datetime import datetime
                    filename = datetime.now().strftime("%H-%M-%S.pdf")
            
            saved_pdf_path = os.path.join(downloads_dir, filename)
            
            # 5. 检查本地是否已存在该PDF文件
            if os.path.exists(saved_pdf_path):
                loading_dialog.close()
                self.status_label.setText(f"使用本地PDF文件: {saved_pdf_path}")
                self.process_pdf_with_offset(saved_pdf_path, page_number, extract_type)
                return
            
            # 5. 使用multi_thread_downloader.download下载文件（使用用户设置的线程数）
            loading_dialog.text_label.setText(f"正在下载: {filename}")
            QApplication.processEvents()
            
            # 获取用户设置的下载线程数
            thread_num = self.settings_manager.get_download_thread_num() if self.settings_manager else 1
            print(f"[DEBUG] process_sei_import: Using thread_num = {thread_num}")
            
            download(
                url=download_url,
                save_dir=downloads_dir,
                filename=filename,
                thread_num=thread_num,
                verify_ssl=False
            )
            
            loading_dialog.close()
            
            # 6. 检查下载是否成功
            if os.path.exists(saved_pdf_path):
                self.status_label.setText(f"PDF已保存到: {saved_pdf_path}")
                
                # 直接使用偏移量处理PDF
                self.process_pdf_with_offset(saved_pdf_path, page_number, extract_type)
            else:
                QMessageBox.critical(self, "错误", "PDF文件下载失败")
                
        except Exception as e:
            loading_dialog.close()
            QMessageBox.critical(self, "错误", f"处理失败: {str(e)}")

    def _extract_last_link_from_file(self, file_path):
        """从links.txt中提取最后一串链接"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 匹配 [YY-MM-DD hh-mm-ss]网址 或 [YY_MM_DD hh-mm-ss]网址 格式的链接
            # 支持 - 和 _ 两种日期分隔符
            pattern = r'\[\d{2}[-_]\d{2}[-_]\d{2}\s+\d{2}-\d{2}-\d{2}\](https?://[^\s]+)'
            matches = re.findall(pattern, content)
            
            print(f"[DEBUG] _extract_last_link_from_file: Found {len(matches)} links")
            if matches:
                print(f"[DEBUG] _extract_last_link_from_file: Last link = {matches[-1]}")
                return matches[-1]
            
            print("[DEBUG] _extract_last_link_from_file: No links found")
            return None
        except Exception as e:
            print(f"[DEBUG] _extract_last_link_from_file: Exception - {e}")
            return None

    def _extract_filename_from_url(self, url):
        """尝试从URL中提取文件名"""
        try:
            # 尝试从URL路径中提取文件名
            parsed = re.search(r'/([^/]+?)(?:\.pdf)?(?:\?|$)', url)
            if parsed:
                filename = parsed.group(1)
                # 确保文件名以.pdf结尾
                if not filename.lower().endswith('.pdf'):
                    filename += '.pdf'
                # 清理文件名中的非法字符
                filename = re.sub(r'[^\w\-_.]', '_', filename)
                return filename
        except:
            pass
        return None

    def process_selection(self):
        """处理选择的文件"""
        # 检查在线导入模式
        is_sei_mode = self.settings_manager.get_online_import_mode() if self.settings_manager else False
        print(f"[DEBUG] process_selection: is_sei_mode = {is_sei_mode}")
        
        if is_sei_mode:
            # 智慧教育平台导入模式
            print("[DEBUG] Calling process_sei_import()")
            self.process_sei_import()
        else:
            # GitHub导入模式（原有逻辑）
            if not hasattr(self, 'selected_file_info'):
                QMessageBox.warning(self, "提示", "请先选择PDF文件")
                return
            
            page_str = self.page_input.text().strip()
            if not page_str or not page_str.isdigit():
                QMessageBox.warning(self, "提示", "请输入有效页码")
                return
            
            page_number = int(page_str)  # 用户输入的页码
            
            # 获取提取内容
            extract_type = self.extract_input.text().strip()
            if not extract_type:
                extract_type = "所有文字"
            
            # 使用AI OCR处理
            self.process_with_ai_ocr(page_number, extract_type)

    def process_with_ai_ocr(self, user_page, extract_type):
        """AI处理PDF"""
        loading_dialog = LoadingDialog(self)
        text_per_line=int((len(self.selected_pdf_name)-8)/2)
        loading_dialog.text_label.setText(f"正在处理 ……\n{self.selected_pdf_name[8:8+text_per_line]}\n{self.selected_pdf_name[8+text_per_line:9+2*text_per_line]}")  # 显示处理中的PDF名称
        loading_dialog.show()
        QApplication.processEvents()
        try:
            # 检查本地是否有同名PDF
            local_pdf_path = self._check_local_pdf(self.selected_pdf_name)
            
            if local_pdf_path:
                self.status_label.setText(f"使用本地PDF: {local_pdf_path}")
                loading_dialog.close()
                self.process_pdf_with_offset(local_pdf_path, user_page, extract_type)
            else:
                self._download_pdf_and_process(user_page, extract_type, loading_dialog)
                
        except Exception as e:
            loading_dialog.close()
            QMessageBox.critical(self, "错误", f"处理失败: {str(e)}")

    def _check_local_pdf(self, pdf_name):
        """检查本地是否有同名PDF"""
        try:
            downloads_dir = os.path.join(get_app_base_path(), "downloaded_pdfs")
            if not os.path.exists(downloads_dir):
                return None
            
            # 首先尝试直接匹配
            direct_path = os.path.join(downloads_dir, pdf_name)
            if os.path.exists(direct_path):
                return direct_path
            
            # 如果是SEI模式，尝试转换文件名格式
            if self.is_sei_mode:
                converted_filename = self._convert_sei_filename(pdf_name)
                converted_path = os.path.join(downloads_dir, converted_filename)
                if os.path.exists(converted_path):
                    return converted_path
            
            # 最后尝试安全名称匹配
            safe_name = re.sub(r'[^\w\-_.]', '_', pdf_name)
            for filename in os.listdir(downloads_dir):
                if filename.endswith('.pdf'):
                    local_safe_name = re.sub(r'[^\w\-_.]', '_', filename)
                    if safe_name == local_safe_name:
                        return os.path.join(downloads_dir, filename)
            
            return None
        except Exception as e:
            # 检查本地PDF失败，静默处理
            return None

    def _convert_sei_filename(self, sei_filename):
        """将SEI显示的文件名转换为本地存储的文件名格式"""
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
        return converted
    
    def _download_pdf_and_process(self, user_page, extract_type, loading_dialog):
        """下载PDF并处理"""
        try:
            # 检查本地是否已存在PDF文件
            pdf_name = self.selected_file_info.get('name', 'unknown.pdf')
            downloads_dir = os.path.join(get_app_base_path(), "downloaded_pdfs")
            saved_pdf_path = os.path.join(downloads_dir, pdf_name)
            
            # 检查本地PDF文件
            local_pdf_path = self._check_local_pdf(pdf_name)
            if local_pdf_path:
                loading_dialog.close()
                self.status_label.setText(f"使用本地PDF文件: {local_pdf_path}")
                self.ask_for_page_offset(local_pdf_path, user_page, extract_type)
                return
            
            #导入多线程下载模块
            
            
            #获取下载URL
            pdf_url = self._get_pdf_download_url(self.selected_file_info)
            
            # 根据GitHub下载加速设置构建最终下载URL
            final_download_url = self._get_download_url(pdf_url)
            
            #获取用户设置的下载线程数
            thread_num = self.settings_manager.get_download_thread_num() if self.settings_manager else 5
            
            #使用多线程下载器下载文件
            download(
                url=final_download_url,
                save_dir=downloads_dir,
                filename=pdf_name,
                thread_num=thread_num,  # 使用用户设置的线程数
                verify_ssl=False  # 禁用SSL验证以提高兼容性
            )
            
            loading_dialog.close()
            
            if os.path.exists(saved_pdf_path):
                self.status_label.setText(f"PDF已保存到: {saved_pdf_path}")
                #询问实际页码
                self.ask_for_page_offset(saved_pdf_path, user_page, extract_type)
            else:
                QMessageBox.critical(self, "错误", "PDF文件保存失败")
                
        except Exception as e:
            loading_dialog.close()
            QMessageBox.critical(self, "错误", f"下载失败: {str(e)}")

    def ask_for_page_offset(self, pdf_path, user_page, extract_type):
        """询问用户页码偏移量"""
        dialog = PageOffsetDialog(self, os.path.basename(pdf_path), str(user_page), pdf_path)
        if dialog.exec_() == QDialog.Accepted and dialog.actual_page:
            actual_page = int(dialog.actual_page)
            #计算偏移量
            offset = actual_page - user_page
            #保存偏移量
            self._save_page_offset(os.path.basename(pdf_path), offset)
            #使用实际页码处理PDF
            self.process_single_page(pdf_path, actual_page - 1, extract_type)

    def _save_page_offset(self, pdf_name, offset):
        """保存页码偏移量到设置文件"""
        try:
            if self.settings_manager:
                setting_name = f"pdfOffset_{pdf_name}"
                self.settings_manager.set_offset_value(setting_name, str(offset))
        except Exception as e:
            # 保存页码偏移量失败，静默处理
            pass

    def _get_page_offset(self, pdf_name):
        """从设置文件获取页码偏移量"""
        try:
            if self.settings_manager:
                setting_name = f"pdfOffset_{pdf_name}"
                offset_str = self.settings_manager.get_offset_value(setting_name, "")
                if offset_str and offset_str.isdigit():
                    return int(offset_str)
            return None
        except Exception as e:
            # 获取页码偏移量失败，静默处理
            return None

    def process_pdf_with_offset(self, pdf_path, user_page, extract_type):
        """使用偏移量处理PDF"""
        pdf_name = os.path.basename(pdf_path)
        offset = self._get_page_offset(pdf_name)
        
        if offset is not None:
            #有偏移量，直接算页码
            actual_page = user_page + offset
            self.process_single_page(pdf_path, actual_page - 1, extract_type)#0-based索引
        else:
            #没有偏移量，显示对话框让用户确认页码
            #对话框会在5秒后自动打开PDF，或者用户手动点击"打开PDF"按钮
            self.ask_for_page_offset(pdf_path, user_page, extract_type)

    def _open_pdf_file(self, pdf_path):
        """使用系统默认方式打开PDF文件"""
        try:
            if sys.platform == "win32":  # Windows
                os.startfile(pdf_path)
            elif sys.platform == "darwin":  # Mac
                os.system(f"open '{pdf_path}'")
            else:  # Linux
                os.system(f"xdg-open '{pdf_path}'")
        except Exception as e:
            # 打开PDF文件失败，静默处理
            pass

    def process_single_page(self, pdf_path, page_number, extract_type):
        """处理单页PDF"""
        loading_dialog = LoadingDialog(self)
        loading_dialog.text_label.setText(f"正在转换第{page_number+1}页为图片...")
        loading_dialog.show()
        QApplication.processEvents()
        try:
            #转图像
            image_path = self._convert_pdf_page_to_image(pdf_path, page_number)
            loading_dialog.close()
            
            if image_path:
                self.process_image_with_ai(image_path, extract_type, pdf_path)
            else:
                QMessageBox.critical(self, "错误", "PDF页面转换失败")
                
        except Exception as e:
            loading_dialog.close()
            QMessageBox.critical(self, "错误", f"处理失败: {str(e)}")

    def _convert_pdf_page_to_image(self, pdf_path, page_number):
        """将PDF单页转换为图像"""
        try:
            #打开文档
            doc = fitz.open(pdf_path)
            if page_number < 0 or page_number >= doc.page_count:
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
            with tempfile.NamedTemporaryFile(dir='./cache/', suffix=f"_page{page_number+1}.png", delete=False) as temp_img:
                image.save(temp_img, "PNG", quality=95)
                return temp_img.name
            
        except Exception as e:
            raise Exception(f"PDF页面转图像失败: {str(e)}")

    @staticmethod
    def _get_pdf_download_url(file_info):
        """获取PDF文件的真实下载URL"""
        try:
            #直接用API返回的download_url
            if 'download_url' in file_info and file_info['download_url']:
                return file_info['download_url']
            
            #构建原始GitHub URL
            file_path = file_info['path']
            raw_url = f"https://raw.githubusercontent.com/TapXWorld/ChinaTextbook/main/{file_path}"
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
        api_key = self.settings_manager.get_api_key("api_key_ChatGLM") if self.settings_manager else ""
        if not api_key:
            QMessageBox.warning(self, "API Key未设置", "请在设置界面中配置ChatGLM API Key")
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
        loading_dialog.show()
        QApplication.processEvents()
        
        self.ai_worker = AIOCRWorker(api_key, image_path, prompt)
        self.ai_worker.finished_signal.connect(lambda text: self.on_ai_finished(text, loading_dialog, image_path))
        self.ai_worker.error_signal.connect(lambda err: self.on_ai_error(err, loading_dialog, image_path))
        self.ai_worker.start()

    def on_ai_finished(self, text, loading_dialog, image_path):
        """AI处理完成"""
        loading_dialog.close()
        
        #清理临时图像
        if os.path.exists(image_path):
            try:
                os.unlink(image_path)
            except:
                pass
        
        if text:
            self.result_text = text
            self.accept()
        else:
            QMessageBox.warning(self, "提示", "未能识别到文字")

    def on_ai_error(self, error_message, loading_dialog, image_path):
        """AI处理错误"""
        loading_dialog.close()
        
        #清理临时图像
        if os.path.exists(image_path):
            try:
                os.unlink(image_path)
            except:
                pass
                    
        QMessageBox.critical(self, "错误", error_message)
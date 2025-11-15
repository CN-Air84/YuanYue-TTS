import sys
import os
import re
import time
import datetime
import base64
import io
import json
import tempfile
import requests
from multiprocessing import Process, Queue, Event

from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QTextEdit, QFileDialog, 
                            QMessageBox, QVBoxLayout, QHBoxLayout, QDialog, QLabel, 
                            QInputDialog, QComboBox, QLineEdit, QFormLayout, QTreeWidget, 
                            QTreeWidgetItem, QCheckBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QRect
from PyQt5.QtGui import QPainter, QColor, QPen, QFont

from PIL import Image, ImageDraw, ImageFont
import certifi
import fitz  # PyMuPDF
PYTMUPDF_AVAILABLE = True #沟槽的我VS沟槽的之前的我 lol

try:
    from misc_func import SettingsManager
    SETTINGS_AVAILABLE = True
except ImportError:
    SETTINGS_AVAILABLE = False

from iw_dialogs import LoadingDialog, PageOffsetDialog

#AI线程
class AIOCRWorker(QThread):
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    debug_signal = pyqtSignal(str, str)  #类型, 内容
    
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
#在线导入对话框
class OnlineImportDialog(QDialog):
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
        self.init_ui()
        self.load_root_directory()

    def init_ui(self):
        self.setWindowTitle("从教科书中导入 - 选择一本教科书并指定内容：")
        if self.window_size:
            self.setGeometry(self.window_size)
        else:
            self.resize(800, 600)
        
        self.setStyleSheet("""
            QDialog {background-color: #69E0A5;}
            QPushButton {font-family: "微软雅黑"; background-color: white; color: black;
                         border: 2px solid gray; border-radius: 5px; font-weight: bold; padding: 5px;}
            QPushButton:hover {background-color: #f0f0f0;}
            QLabel {font-family: "微软雅黑"; font-size: 14px;}
            QLineEdit {font-family: "微软雅黑"; background-color: white; color: black;
                       border: 2px solid gray; border-radius: 5px; padding: 5px;}
            QTreeWidget {font-family: "微软雅黑"; background-color: white; color: black;
                         border: 2px solid gray; border-radius: 5px;}
        """)
        
        main_layout = QVBoxLayout()
        
        #路径导航和操作按钮
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
        
        # 页码输入框（缩短为原来的1/2）
        self.page_input = QLineEdit()
        self.page_input.setPlaceholderText("页码")
        self.page_input.setMaximumWidth(80)
        
        # 提取内容输入框
        self.extract_input = QLineEdit()
        self.extract_input.setPlaceholderText("提取内容（例如：注释）")
        
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
        other_font = QFont("微软雅黑", other_font_size)
        
        #设置所有标签和输入框的字体
        for widget in [self.path_label, self.status_label, self.page_label, self.extract_label]:
            widget.setFont(other_font)
            
        for widget in [self.back_button, self.refresh_button, self.cancel_button, self.confirm_button]:
            widget.setFont(other_font)
            
        for widget in [self.page_input, self.extract_input]:
            widget.setFont(other_font)
            
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
            # 目录查询始终使用GitHub官方API
            url = f"https://api.github.com/repos/TapXWorld/ChinaTextbook/contents/{path}"
            
            response = requests.get(url, verify=certifi.where(), timeout=15)
            response.raise_for_status()
            contents = response.json()
            
            #添加目录项
            for item in contents:
                #跳过不该有的文件夹
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
            QMessageBox.critical(self, "错误", f"无法加载目录内容: {str(e)}")

    def _get_download_url(self, original_url):
        """根据加速选项获取下载URL"""
        github_acceleration = self.settings_manager.get_github_acceleration() if self.settings_manager else 0
        
        if github_acceleration == 1:  # ghfast镜像
            return f"https://ghfast.top/{original_url}"
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

    def process_selection(self):
        """处理选择的文件"""
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
        loading_dialog.text_label.setText(f"正在处理 ……{self.selected_pdf_name[8:]}...")#目前是前8个字符不要 苦一苦大学用户 骂名我来担
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
            downloads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloaded_pdfs")
            if not os.path.exists(downloads_dir):
                return None
            safe_name = re.sub(r'[^\w\-_.]', '_', pdf_name)
            
            #查找PDF文件
            for filename in os.listdir(downloads_dir):
                local_safe_name = re.sub(r'[^\w\-_.]', '_', filename)
                if filename.endswith('.pdf') and safe_name == local_safe_name:
                    return os.path.join(downloads_dir, filename)
            
            return None
        except Exception as e:
            print(f"检查本地PDF失败: {e}")
            return None

    def _download_pdf_and_process(self, user_page, extract_type, loading_dialog):
        """下载PDF并处理"""
        try:
            #获取下载URL
            pdf_url = self._get_pdf_download_url(self.selected_file_info)
            
            # 根据GitHub下载加速设置构建最终下载URL
            final_download_url = self._get_download_url(pdf_url)
            
            response = requests.get(final_download_url, stream=True, verify=certifi.where(), timeout=30)
            response.raise_for_status()
            
            pdf_data = b""
            for chunk in response.iter_content(chunk_size=8192):
                pdf_data += chunk
                QApplication.processEvents()
            
            #保存PDF文件
            pdf_name = self.selected_file_info.get('name', 'unknown.pdf')
            saved_pdf_path = self._save_pdf_to_directory(pdf_data, pdf_name)
            
            loading_dialog.close()
            
            if saved_pdf_path:
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
            print(f"保存页码偏移量失败: {e}")

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
            print(f"获取页码偏移量失败: {e}")
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
            #没有偏移量
            self._open_pdf_file(pdf_path)
            self.ask_for_page_offset(pdf_path, user_page, extract_type)

    def _open_pdf_file(self, pdf_path):
        """使用系统默认方式打开PDF文件"""
        try:
            if sys.platform == "win32":#windows
                os.startfile(pdf_path)
            elif sys.platform == "darwin":#mac
                os.system(f"open '{pdf_path}'")
            else:  #Linux
                os.system(f"xdg-open '{pdf_path}'")
        except Exception as e:
            print(f"打开PDF文件失败: {e}")

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
            with tempfile.NamedTemporaryFile(suffix=f"_page{page_number+1}.png", delete=False) as temp_img:
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
            downloads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloaded_pdfs")
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
            print(f"保存PDF失败: {str(e)}")
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
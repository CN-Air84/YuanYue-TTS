# coding=utf-8
import base64
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QTextEdit, QHBoxLayout, QPushButton, QMessageBox, QApplication
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from shared_memory_manager import get_shared_memory_manager
from debug_logger import debug_logger, LogLevel
from ai_manager import get_ai_manager, AIRequest, AIScene

# 界面字体大小和窗口尺寸常量
MIN_FONT_SIZE = 22
MAX_FONT_SIZE = 42
DEFAULT_WIDTH = 1080
DEFAULT_HEIGHT = 1080

try:
    from misc_func import SettingsManager
    SETTINGS_AVAILABLE = True
except ImportError:
    SETTINGS_AVAILABLE = False

class AIOCRWorker(QThread):
    """AI OCR工作线程类 - 使用AIManager进行图片文字识别"""
    
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    
    def __init__(self, image_path):
        """
        初始化AI OCR工作线程
        
        Args:
            image_path (str): 图片文件路径
        """
        super().__init__()
        self.image_path = image_path
    
    def run(self):
        """执行AI OCR识别任务"""
        debug_logger.output("mp_ai_ocr.py", LogLevel.INFO, f"开始 AI OCR 识别任务, 图片路径: {self.image_path}", fold_code="AI_OCR_RUN")
        try:
            ai_manager = get_ai_manager()
            
            debug_logger.output("mp_ai_ocr.py", LogLevel.INFO, "正在通过 AIManager 发送 OCR 请求", fold_code="AI_OCR_RUN")
            
            prompt = "请提取这张图片中的所有文字内容，输出纯文字格式。"
            
            request = AIRequest(
                prompt=prompt,
                scene=AIScene.VISION,
                image_path=self.image_path
            )
            
            response = ai_manager.chat(request)
            result = response.text
            
            debug_logger.output("mp_ai_ocr.py", LogLevel.INFO, 
                f"AI OCR 识别成功, 提取文字长度: {len(result)}, "
                f"使用模型: {response.model_used} ({response.provider_used})", 
                fold_code="AI_OCR_RUN")
            self.finished_signal.emit(result)
            
        except Exception as e:
            debug_logger.output("mp_ai_ocr.py", LogLevel.ERROR, f"AI OCR 识别失败: {str(e)}", fold_code="AI_OCR_RUN")
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
        debug_logger.output("mp_ai_ocr.py", LogLevel.INFO, f"初始化文本结果对话框: {title}", fold_code="AI_OCR_UI")
        self.parent_window = parent
        self.setWindowTitle(title)
        self.resize(600, 400)
        
        if SETTINGS_AVAILABLE:
            self.settings_manager = SettingsManager()
            self.global_font = self.settings_manager.get_Custom_value('global_font', '微软雅黑')
            background_color = self.settings_manager.get_Custom_value('background_color', '#E5E8EF')
            self.text_color = self.settings_manager.get_Custom_value('text_color', '#333333')
        else:
            self.global_font = '微软雅黑'
            background_color = '#E5E8EF'
            self.text_color = '#333333'
        
        self.setStyleSheet(f"QWidget {{ background-color: {background_color}; color: {self.text_color}; }}")
        
        layout = QVBoxLayout()
        
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(content)
            
        self.text_edit.setStyleSheet(f"""
        QTextEdit {{
            background-color: white;
            color: black;
            border: 2px solid gray;
            border-radius: 10px;
            font-family: "{self.global_font}";
            font-size: 12px;
            }}
        """)

        layout.addWidget(self.text_edit)
        
        button_layout = QHBoxLayout()
        
        self.copy_button = QPushButton("复制结果")
        self.copy_button.clicked.connect(self.copy_text)
        
        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.accept)
        
        # 应用按钮样式
        self._update_button_styles()
        
        button_layout.addWidget(self.copy_button)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        # 连接共享内存信号
        self.shared_manager = get_shared_memory_manager()
        self._connect_shared_memory_signals()
        
        self._update_fonts()
    
    def _update_button_styles(self):
        """更新按钮样式"""
        button_style = f"""
            QPushButton {{
                font-family: "{self.global_font}";
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
        """
        self.copy_button.setStyleSheet(button_style)
        self.close_button.setStyleSheet(button_style)
    
    def _update_fonts(self):
        """更新界面字体大小"""
        if not self.parent_window:
            return
            
        current_width = self.width()
        current_height = self.height()
        debug_logger.output("mp_ai_ocr.py", LogLevel.INFO, f"更新文本结果对话框字体, 尺寸: {current_width}x{current_height}", fold_code="AI_OCR_UI")
        
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
        debug_logger.output("mp_ai_ocr.py", LogLevel.INFO, "收到共享内存字体更改信号", fold_code="AI_OCR_SHARED")
        try:
            # 更新字体设置
            self._update_fonts()
        except Exception as e:
            debug_logger.output("mp_ai_ocr.py", LogLevel.WARNING, f"处理共享内存字体更改失败: {str(e)}", fold_code="AI_OCR_SHARED")
    
    def _on_theme_changed_from_shared_memory(self, theme_data):
        """从共享内存接收主题更改"""
        debug_logger.output("mp_ai_ocr.py", LogLevel.INFO, "收到共享内存主题更改信号", fold_code="AI_OCR_SHARED")
        try:
            # 应用背景颜色和文字颜色
            bg_color = theme_data.get('background_color', '#E5E8EF')
            text_color = theme_data.get('text_color', '#333333')
            if SETTINGS_AVAILABLE:
                bg_color = SettingsManager().get_Custom_value('background_color', bg_color)
                text_color = SettingsManager().get_Custom_value('text_color', text_color)
            
            self.text_color = text_color
            self.setStyleSheet(f"QWidget {{ background-color: {bg_color}; color: {self.text_color}; }}")
            self._update_button_styles()
        except Exception as e:
            debug_logger.output("mp_ai_ocr.py", LogLevel.WARNING, f"处理共享内存主题更改失败: {str(e)}", fold_code="AI_OCR_SHARED")
    
    def _on_window_size_changed_from_shared_memory(self, width, height):
        """从共享内存接收窗口尺寸更改"""
        debug_logger.output("mp_ai_ocr.py", LogLevel.INFO, f"收到共享内存窗口尺寸更改信号: {width}x{height}", fold_code="AI_OCR_SHARED")
        try:
            # 重新布局控件
            if hasattr(self, 'resizeEvent'):
                # 触发重新布局
                self.resize(self.width(), self.height())
        except Exception as e:
            debug_logger.output("mp_ai_ocr.py", LogLevel.WARNING, f"处理共享内存窗口尺寸更改失败: {str(e)}", fold_code="AI_OCR_SHARED")
    
    def _on_settings_changed_from_shared_memory(self, page_name, settings_data):
        """从共享内存接收设置更改"""
        debug_logger.output("mp_ai_ocr.py", LogLevel.INFO, f"收到共享内存设置更改信号: {page_name}", fold_code="AI_OCR_SHARED")
        try:
            if page_name in ['custom', 'custom_page']:
                # 如果是来自个性化页面的设置更改，更新相关设置
                # 重新加载页面以应用新设置
                self._reload_page(settings_data)
        except Exception as e:
            debug_logger.output("mp_ai_ocr.py", LogLevel.WARNING, f"处理共享内存设置更改失败: {str(e)}", fold_code="AI_OCR_SHARED")
    
    def _reload_page(self, settings_data=None):
        """重新加载页面以应用最新设置"""
        debug_logger.output("mp_ai_ocr.py", LogLevel.INFO, "重新加载文本结果对话框页面设置", fold_code="AI_OCR_UI")
        try:
            if SETTINGS_AVAILABLE:
                settings = SettingsManager()
                bg_color = settings.get_Custom_value('background_color', '#E5E8EF')
                self.text_color = settings.get_Custom_value('text_color', '#333333')
                self.global_font = settings.get_Custom_value('global_font', '微软雅黑')
            else:
                bg_color = '#E5E8EF'
                self.text_color = '#333333'
                self.global_font = '微软雅黑'

            # 应用样式
            self.setStyleSheet(f"QWidget {{ background-color: {bg_color}; color: {self.text_color}; }}")
            
            # 更新文本编辑框样式
            self.text_edit.setStyleSheet(f"""
                QTextEdit {{
                    background-color: white;
                    color: black;
                    border: 2px solid gray;
                    border-radius: 10px;
                    font-family: "{self.global_font}";
                    font-size: 12px;
                }}
            """)
            
            # 更新按钮样式
            self._update_button_styles()
            
            # 更新字体
            self._update_fonts()
            
            # 重新布局控件（触发resize事件）
            if hasattr(self, 'resizeEvent'):
                self.resize(self.width(), self.height())
        except Exception as e:
            pass
    
    def copy_text(self):
        """复制文本到剪贴板"""
        debug_logger.output("mp_ai_ocr.py", LogLevel.INFO, "正在将提取的文本复制到剪贴板", fold_code="AI_OCR_UI")
        clipboard = QApplication.clipboard()
        clipboard.setText(self.text_edit.toPlainText())
        QMessageBox.information(self, "成功", "文本已复制到剪贴板")

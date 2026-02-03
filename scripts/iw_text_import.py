# coding=utf-8
import sys
import os
from typing import Optional
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QTextEdit, QFileDialog, 
    QMessageBox, QVBoxLayout, QHBoxLayout, QDialog
)
from PyQt5.QtCore import  QRect
from PyQt5.QtGui import QFont

from docxfix import Document
from iw_dialogs import MultiImageImportDialog, LoadingDialog, ClearConfirmationDialog
from iw_online_import import OnlineImportDialog, AIOCRWorker
try:
    from misc_func import SettingsManager
    SETTINGS_AVAILABLE = True
except ImportError:
    SETTINGS_AVAILABLE = False


class TextImportConfig:
    """文本导入配置类"""
    
    DEFAULT_STYLE = """
        QDialog {background-color: transparent;}
        QPushButton {
            font-family: "微软雅黑"; background-color: white; color: black;
            border: 2px solid gray; border-radius: 5px; font-weight: bold; padding: 5px;
        }
        QPushButton:hover {background-color: #f0f0f0;}
        QTextEdit {
            background-color: white; color: black; border: 2px solid gray; 
            border-radius: 10px; font-family: "微软雅黑"; font-size: 14px;
        }
        QComboBox {
            font-family: "微软雅黑"; background-color: white; color: black;
            border: 2px solid gray; border-radius: 10px; padding: 5px;
        }
    """
    
    BUTTON_TEXTS = {
        'txt': "从txt导入",
        'doc': "从docx导入", 
        'online': "线上导入",
        'image': "从图片导入",
        'clear': "清空",
        'confirm': "确认"
    }
    
    SUPPORTED_IMAGE_FORMATS = "图片文件 (*.png *.jpg *.jpeg *.webp)"
    SUPPORTED_TEXT_FORMATS = "Text Files (*.txt)"
    SUPPORTED_DOC_FORMATS = "Word Documents (*.docx)"


class TextImportManager:
    """文本导入管理器"""
    
    def __init__(self, settings_manager: Optional[SettingsManager] = None):
        self.settings_manager = settings_manager
    
    def import_from_txt(self, parent_dialog: QDialog) -> Optional[str]:
        """从TXT文件导入文本"""
        file_path, _ = QFileDialog.getOpenFileName(
            parent_dialog, "选择文件", "", TextImportConfig.SUPPORTED_TEXT_FORMATS
        )
        
        if not file_path:
            return None
            
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            QMessageBox.critical(parent_dialog, "错误", f"读取失败: {str(e)}")
            return None
    
    def import_from_docx(self, parent_dialog: QDialog) -> Optional[str]:
        """从DOCX文件导入文本"""
        file_path, _ = QFileDialog.getOpenFileName(
            parent_dialog, "选择文件", "", TextImportConfig.SUPPORTED_DOC_FORMATS
        )
        
        if not file_path:
            return None
            
        try:
            doc = Document(file_path)
            content = '\n'.join([p.text for p in doc.paragraphs])
            return content
        except Exception as e:
            QMessageBox.critical(parent_dialog, "错误", f"读取失败: {str(e)}")
            return None
    
    def import_from_image(self, parent_dialog: QDialog) -> Optional[tuple[list[str], str]]:
        """从图片导入文本"""
        if not self.settings_manager:
            QMessageBox.warning(parent_dialog, "提示", "设置管理器不可用")
            return None
        
        api_key = self.settings_manager.get_api_key("api_key_ChatGLM")
        if not api_key:
            QMessageBox.warning(parent_dialog, "提示", "请配置ChatGLM API Key")
            return None
        
        file_paths, _ = QFileDialog.getOpenFileNames(
            parent_dialog, "选择图片", "", TextImportConfig.SUPPORTED_IMAGE_FORMATS
        )
        
        if not file_paths:
            return None
        
        if len(file_paths) > 5:
            QMessageBox.warning(parent_dialog, "提示", "最多只能选择5张图片")
            return None
            
        return file_paths, api_key


class TextEditController:
    """文本编辑控制器"""
    
    def __init__(self, text_edit: QTextEdit):
        self.text_edit = text_edit
    
    def get_text(self) -> str:
        """获取文本内容"""
        return self.text_edit.toPlainText()
    
    def set_text(self, text: str) -> None:
        """设置文本内容"""
        self.text_edit.setPlainText(text)
    
    def append_text(self, text: str, separator: str = "\n\n") -> None:
        """追加文本内容"""
        current_text = self.get_text()
        if current_text:
            new_text = current_text + separator + text
        else:
            new_text = text
        self.set_text(new_text)
    
    def clear_text(self) -> None:
        """清空文本内容"""
        self.text_edit.clear()


class ImportButtonHandler:
    """导入按钮处理器"""
    
    def __init__(self, parent_dialog: QDialog, text_controller: TextEditController, 
                 import_manager: TextImportManager):
        self.parent_dialog = parent_dialog
        self.text_controller = text_controller
        self.import_manager = import_manager
        self.ai_worker = None
        self.loading_dialog = None
        self.processed_count = 0 # 新增：已处理图片计数
        self.failed_count = 0 # 新增：失败图片计数
        self.total_images_to_process = 0 # 新增：总共需要处理的图片数量
        self.current_ocr_queue = [] # 新增：OCR图片队列
        self.current_ocr_remarks = [] # 新增：OCR备注队列
    
    def handle_txt_import(self) -> None:
        """处理TXT导入"""
        content = self.import_manager.import_from_txt(self.parent_dialog)
        if content:
            self.text_controller.set_text(content)
    
    def handle_docx_import(self) -> None:
        """处理DOCX导入"""
        content = self.import_manager.import_from_docx(self.parent_dialog)
        if content:
            self.text_controller.set_text(content)
    
    def handle_online_import(self) -> None:
        """处理在线导入"""
        dialog = OnlineImportDialog(self.parent_dialog, self.parent_dialog.geometry())
        if dialog.exec_() == QDialog.Accepted and hasattr(dialog, 'result_text'):
            self.text_controller.append_text(dialog.result_text)
    
    def handle_image_import(self) -> None:
        """处理图片导入"""
        result = self.import_manager.import_from_image(self.parent_dialog)
        if not result:
            return
            
        initial_file_paths, api_key = result
        
        # 显示多图片导入对话框
        multi_image_dialog = MultiImageImportDialog(self.parent_dialog, initial_file_paths)
        if multi_image_dialog.exec_() == QDialog.Accepted:
            sorted_image_paths = multi_image_dialog.result_image_paths
            sorted_image_remarks = multi_image_dialog.get_image_remarks()
            if not sorted_image_paths:
                QMessageBox.warning(self.parent_dialog, "提示", "没有选择图片进行导入。")
                return
            
            self.current_ocr_queue = list(sorted_image_paths)
            self.current_ocr_remarks = list(sorted_image_remarks)
            self.api_key = api_key # 存储api_key供后续OCR使用
            self.processed_count = 0 # 初始化计数器
            self.failed_count = 0 # 初始化计数器
            self.total_images_to_process = len(sorted_image_paths) # 设置总数
            self.loading_dialog = LoadingDialog(self.parent_dialog)
            self.loading_dialog.show()
            self._process_next_ocr_image()
        else:
            # 用户取消了多图片导入对话框
            pass
    
    def _process_next_ocr_image(self) -> None:
        """处理OCR队列中的下一张图片"""
        if not self.current_ocr_queue:
            # 队列为空，所有图片处理完毕
            if self.loading_dialog:
                self.loading_dialog.close()
            
            success_count = self.total_images_to_process - self.failed_count
            QMessageBox.information(
                self.parent_dialog, 
                "完成", 
                f"所有图片已处理完毕。\n成功: {success_count} 张, 失败: {self.failed_count} 张。"
            )
            return
            
        file_path = self.current_ocr_queue.pop(0) # 取出队列中的第一张图片
        remark = self.current_ocr_remarks.pop(0) # 取出对应的备注
        
        if self.loading_dialog:
            self.loading_dialog.set_message(f"正在处理图片: {os.path.basename(file_path)}...")
        
        prompt = (
            "请提取这张图片中的文字内容，"
            "将₁②⑶⒋Ⅴ❻㈦之类特殊数字符号转为普通数字，"
            "忽略所有注释角标，输出纯文字格式。"
            "严禁输出任何与图片无关的提示语（如：“这张图片中包含以下文字：”等）。"
        )
        if remark:
            prompt += f"\n\n用户想要提取图片中的：{remark}。忽略所有其他文字。"
        
        self.ai_worker = AIOCRWorker(self.api_key, file_path, prompt)
        self.ai_worker.finished_signal.connect(self._on_ai_ocr_finished_multi)
        self.ai_worker.error_signal.connect(self._on_ai_ocr_error_multi)
        self.ai_worker.start()
    
    def handle_clear_text(self) -> None:
        """处理清空文本"""
        dialog = ClearConfirmationDialog(self.parent_dialog)
        if dialog.exec_() == QDialog.Accepted and dialog.result:
            self.text_controller.clear_text()
    
    def _on_ai_ocr_finished_multi(self, text: str) -> None:
        """多图片AI OCR完成处理"""
        self.processed_count += 1
        current_image_name = os.path.basename(self.ai_worker.image_path)
        
        if text:
            self.text_controller.append_text(text)
            if self.loading_dialog:
                self.loading_dialog.set_message(
                    f"已处理 {self.processed_count}/{self.total_images_to_process} 张图片: {current_image_name} 成功"
                )
        else:
            self.failed_count += 1
            if self.loading_dialog:
                self.loading_dialog.set_message(
                    f"已处理 {self.processed_count}/{self.total_images_to_process} 张图片: {current_image_name} 未识别到文字"
                )
            QMessageBox.warning(self.parent_dialog, "提示", f"图片 {current_image_name} 未识别到文字")
        
        # 继续处理下一张图片
        self._process_next_ocr_image()
    
    def _on_ai_ocr_error_multi(self, error: str) -> None:
        """多图片AI OCR错误处理"""
        self.processed_count += 1
        current_image_name = os.path.basename(self.ai_worker.image_path)
        self.failed_count += 1
        
        if self.loading_dialog:
            self.loading_dialog.set_message(
                f"已处理 {self.processed_count}/{self.total_images_to_process} 张图片: {current_image_name} 失败"
            )
        QMessageBox.critical(self.parent_dialog, "错误", f"图片 {current_image_name} 处理失败: {error}")
        
        # 即使出错也尝试处理下一张图片
        self._process_next_ocr_image()
    
    def _on_ai_ocr_finished_single(self, text: str) -> None:
        """单图片AI OCR完成处理 (兼容旧版)"""
        if self.loading_dialog:
            self.loading_dialog.close()
        
        if text:
            self.text_controller.append_text(text)
        else:
            QMessageBox.warning(self.parent_dialog, "提示", "未识别到文字")
    
    def _on_ai_ocr_error_single(self, error: str) -> None:
        """单图片AI OCR错误处理 (兼容旧版)"""
        if self.loading_dialog:
            self.loading_dialog.close()
        QMessageBox.critical(self.parent_dialog, "错误", error)
    
    def cleanup(self) -> None:
        """清理资源"""
        if self.ai_worker and self.ai_worker.isRunning():
            self.ai_worker.terminate()
        if self.loading_dialog:
            self.loading_dialog.close()


class TextImportDialog(QDialog):
    """文本导入对话框"""
    
    def __init__(self, parent: Optional[QWidget] = None, 
                 window_size: Optional[QRect] = None, 
                 initial_text: str = ""):
        super().__init__(parent)
        self.window_size = window_size
        self.text_content = ""
        self.initial_text = initial_text
        
        # 初始化管理器
        self.settings_manager = SettingsManager() if SETTINGS_AVAILABLE else None
        self.import_manager = TextImportManager(self.settings_manager)
        
        self._init_ui()
        self._setup_connections()
        self._update_fonts()
        
    def _init_ui(self) -> None:
        """初始化UI"""
        self.setWindowTitle("文本导入")
        # 获取用户设置的背景颜色，默认为#E5E8EF
        background_color = self.settings_manager.get_Custom_value("background_color", "#E5E8EF") if self.settings_manager else "#E5E8EF"
        # 动态生成样式表
        dynamic_style = f"""
        QDialog {{background-color: {background_color};}}
        QPushButton {{
            font-family: "微软雅黑"; background-color: white; color: black;
            border: 2px solid gray; border-radius: 5px; font-weight: bold; padding: 5px;
        }}
        QPushButton:hover {{background-color: #f0f0f0;}}
        QTextEdit {{
            background-color: white; color: black; border: 2px solid gray; 
            border-radius: 10px; font-family: "微软雅黑"; font-size: 14px;
        }}
        QComboBox {{
            font-family: "微软雅黑"; background-color: white; color: black;
            border: 2px solid gray; border-radius: 10px; padding: 5px;
        }}
        """
        self.setStyleSheet(dynamic_style)
        
        if self.window_size:
            self.setGeometry(self.window_size)
        
        main_layout = QVBoxLayout()
        
        # 创建文本编辑器
        self.text_edit = QTextEdit(self)
        self.text_edit.setPlainText(self.initial_text)
        main_layout.addWidget(self.text_edit)
        
        # 创建按钮布局
        button_layout = QHBoxLayout()
        self._create_import_buttons(button_layout)
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
    
    def _create_import_buttons(self, layout: QHBoxLayout) -> None:
        """创建导入按钮"""
        texts = TextImportConfig.BUTTON_TEXTS
        
        self.txt_button = QPushButton(texts['txt'], self)
        self.doc_button = QPushButton(texts['doc'], self)
        self.online_button = QPushButton(texts['online'], self)
        self.image_button = QPushButton(texts['image'], self)
        self.clear_button = QPushButton(texts['clear'], self)
        self.confirm_button = QPushButton(texts['confirm'], self)
        
        layout.addWidget(self.txt_button)
        layout.addWidget(self.doc_button)
        layout.addWidget(self.online_button)
        layout.addWidget(self.image_button)
        layout.addWidget(self.clear_button)
        layout.addWidget(self.confirm_button)
    
    def _setup_connections(self) -> None:
        """设置信号连接"""
        # 初始化控制器和处理器
        self.text_controller = TextEditController(self.text_edit)
        self.button_handler = ImportButtonHandler(
            self, self.text_controller, self.import_manager
        )
        
        #连接按钮信号
        self.txt_button.clicked.connect(self.button_handler.handle_txt_import)
        self.doc_button.clicked.connect(self.button_handler.handle_docx_import)
        self.online_button.clicked.connect(self.button_handler.handle_online_import)
        self.image_button.clicked.connect(self.button_handler.handle_image_import)
        self.clear_button.clicked.connect(self.button_handler.handle_clear_text)
        self.confirm_button.clicked.connect(self._confirm_import)
    
    def _update_fonts(self) -> None:
        """更新字体大小"""
        current_width = self.width()
        current_height = self.height()
        
        min_font_size = 10
        max_font_size = 20
        default_width = 800
        default_height = 600
        
        width_ratio = current_width / default_width
        height_ratio = current_height / default_height
        ratio = (width_ratio + height_ratio) / 2
        
        font_size = min_font_size + (max_font_size - min_font_size) * (ratio - 1)
        font_size = max(min_font_size, min(max_font_size, font_size))
        
        try:
            global_font = self.settings_manager.Custom.get_value("global_font", "微软雅黑") if self.settings_manager else "微软雅黑"
        except:
            global_font = "微软雅黑"
        
        font = QFont(global_font, int(font_size))
        
        # 更新按钮字体
        for button in [self.txt_button, self.doc_button, self.online_button, 
                      self.image_button, self.clear_button, self.confirm_button]:
            button.setFont(font)
        
        # 更新文本编辑器字体
        text_edit_font = QFont(global_font, int(font_size * 0.8))
        self.text_edit.setFont(text_edit_font)
    
    def resizeEvent(self, event) -> None:
        """处理窗口大小变化事件"""
        super().resizeEvent(event)
        self._update_fonts()
    
    def _confirm_import(self) -> None:
        """确认导入"""
        self.text_content = self.text_controller.get_text()
        self.accept()
    
    def closeEvent(self, event) -> None:
        """关闭事件处理"""
        self.button_handler.cleanup()
        self.reject()
        event.accept()
    
    def get_imported_text(self) -> str:
        """获取导入的文本内容"""
        return self.text_content


class TextImportDialogFactory:
    """文本导入对话框工厂"""
    
    @staticmethod
    def create_text_import_dialog(parent: Optional[QWidget] = None,
                                 window_size: Optional[QRect] = None,
                                 initial_text: str = "") -> TextImportDialog:
        """创建文本导入对话框"""
        return TextImportDialog(parent, window_size, initial_text)
    
    @staticmethod
    def show_text_import_dialog(parent: Optional[QWidget] = None,
                               window_size: Optional[QRect] = None,
                               initial_text: str = "") -> Optional[str]:
        """
        显示文本导入对话框并返回结果
        
        Returns:
            Optional[str]: 导入的文本内容，如果取消则为None
        """
        dialog = TextImportDialogFactory.create_text_import_dialog(
            parent, window_size, initial_text
        )
        result = dialog.exec_()
        return dialog.get_imported_text() if result == QDialog.Accepted else None

def show_text_import_dialog(parent: Optional[QWidget] = None,
                           window_size: Optional[QRect] = None,
                           initial_text: str = "") -> Optional[str]:
    """
    显示文本导入对话框（向后兼容函数）
    
    Args:
        parent: 父窗口
        window_size: 窗口尺寸
        initial_text: 初始文本
        
    Returns:
        Optional[str]: 导入的文本内容，如果取消则为None
    """
    return TextImportDialogFactory.show_text_import_dialog(
        parent, window_size, initial_text
    )



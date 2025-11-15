import sys
import os
from typing import Optional, Callable
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QTextEdit, QFileDialog, 
    QMessageBox, QVBoxLayout, QHBoxLayout, QDialog, QLabel
)
from PyQt5.QtCore import Qt, QRect

from docxfix import Document
from iw_dialogs import LoadingDialog, ClearConfirmationDialog, DialogFactory
from iw_online_import import OnlineImportDialog, AIOCRWorker
try:
    from misc_func import SettingsManager
    SETTINGS_AVAILABLE = True
except ImportError:
    SETTINGS_AVAILABLE = False


class TextImportConfig:
    """文本导入配置类"""
    
    DEFAULT_STYLE = """
        QDialog {background-color: #69E0A5;}
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
    
    def import_from_image(self, parent_dialog: QDialog) -> Optional[str]:
        """从图片导入文本"""
        if not self.settings_manager:
            QMessageBox.warning(parent_dialog, "提示", "设置管理器不可用")
            return None
        
        api_key = self.settings_manager.get_api_key("api_key_ChatGLM")
        if not api_key:
            QMessageBox.warning(parent_dialog, "提示", "请配置ChatGLM API Key")
            return None
        
        file_path, _ = QFileDialog.getOpenFileName(
            parent_dialog, "选择图片", "", TextImportConfig.SUPPORTED_IMAGE_FORMATS
        )
        
        if not file_path:
            return None
            
        return file_path, api_key


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
            
        file_path, api_key = result
        
        self.loading_dialog = DialogFactory.create_loading_dialog(self.parent_dialog)
        self.loading_dialog.show()
        
        prompt = (
            "请提取这张图片中的所有文字内容，"
            "将₁②⑶⒋Ⅴ❻㈦之类特殊数字符号转为普通数字，"
            "忽略所有注释角标，输出纯文字格式。"
        )
        
        self.ai_worker = AIOCRWorker(api_key, file_path, prompt)
        self.ai_worker.finished_signal.connect(self._on_ai_ocr_finished)
        self.ai_worker.error_signal.connect(self._on_ai_ocr_error)
        self.ai_worker.start()
    
    def handle_clear_text(self) -> None:
        """处理清空文本"""
        dialog = DialogFactory.create_clear_confirmation_dialog(self.parent_dialog)
        if dialog.exec_() == QDialog.Accepted and dialog.result:
            self.text_controller.clear_text()
    
    def _on_ai_ocr_finished(self, text: str) -> None:
        """AI OCR完成处理"""
        if self.loading_dialog:
            self.loading_dialog.close()
        
        if text:
            self.text_controller.append_text(text)
        else:
            QMessageBox.warning(self.parent_dialog, "提示", "未识别到文字")
    
    def _on_ai_ocr_error(self, error: str) -> None:
        """AI OCR错误处理"""
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
        
        #初始化管理器
        self.settings_manager = SettingsManager() if SETTINGS_AVAILABLE else None
        self.import_manager = TextImportManager(self.settings_manager)
        
        self._init_ui()
        self._setup_connections()
        
    def _init_ui(self) -> None:
        """初始化UI"""
        self.setWindowTitle("文本导入")
        self.setStyleSheet(TextImportConfig.DEFAULT_STYLE)
        
        if self.window_size:
            self.setGeometry(self.window_size)
        
        main_layout = QVBoxLayout()
        
        #创建文本编辑器
        self.text_edit = QTextEdit(self)
        self.text_edit.setPlainText(self.initial_text)
        main_layout.addWidget(self.text_edit)
        
        #创建按钮布局
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
        #初始化控制器和处理器
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

#向后兼容
#我真的是服了
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


#检查模式
if __name__ == "__main__":
    app = QApplication(sys.argv)
    imported_text = show_text_import_dialog(initial_text="这是初始文本")
    print(f"导入的文本: {imported_text}")
    
    sys.exit(app.exec_())
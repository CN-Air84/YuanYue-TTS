import sys
import os
import random
from typing import Optional, Tuple, Callable
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QTextEdit, QFileDialog, 
    QMessageBox, QVBoxLayout, QHBoxLayout, QDialog, QLabel, 
    QInputDialog, QComboBox, QLineEdit, QFormLayout, QTreeWidget, 
    QTreeWidgetItem, QCheckBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QRect
from PyQt5.QtGui import QPainter, QColor, QPen, QFont


class AnimationConfig:
    """动画配置常量"""
    ANIMATION_DURATION = 35  # 动画更新间隔(毫秒)
    WIDGET_SIZE = 80  # 动画部件尺寸
    RECT_MARGIN = 10  # 矩形边距
    PEN_WIDTH = 10  # 画笔宽度
    START_ANGLE_MULTIPLIER = 16  # 起始角度乘数
    SPAN_ANGLE = 270 * 16  # 跨度角度


class AnimationWidget(QWidget):
    """自定义动画部件"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.angle = 0
        self.setFixedSize(AnimationConfig.WIDGET_SIZE, AnimationConfig.WIDGET_SIZE)
        
    def update_angle(self, angle: int) -> None:
        """更新动画角度"""
        self.angle = angle
        self.update()
    
    def paintEvent(self, event) -> None:
        """绘制事件"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制背景圆
        rect = QRect(
            AnimationConfig.RECT_MARGIN, 
            AnimationConfig.RECT_MARGIN, 
            AnimationConfig.WIDGET_SIZE - 2 * AnimationConfig.RECT_MARGIN,
            AnimationConfig.WIDGET_SIZE - 2 * AnimationConfig.RECT_MARGIN
        )
        painter.setPen(QPen(QColor(200, 200, 200), AnimationConfig.PEN_WIDTH))
        painter.drawEllipse(rect)
        
        # 绘制进度弧
        pen = QPen(QColor(139, 196, 234), AnimationConfig.PEN_WIDTH)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        
        start_angle = self.angle * AnimationConfig.START_ANGLE_MULTIPLIER
        painter.drawArc(rect, start_angle, AnimationConfig.SPAN_ANGLE)
        painter.end()


class DialogStyleManager:
    """对话框样式管理器"""
    
    @staticmethod
    def get_loading_dialog_style() -> str:
        """获取加载对话框样式"""
        return """
            QDialog {background-color: #D2D4D3;}
            QLabel {font-family: "微软雅黑"; font-size: 16px; color: #333333;}
        """
    
    @staticmethod
    def get_page_offset_dialog_style() -> str:
        """获取页码偏移对话框样式"""
        return """
            QDialog {background-color: #D2D4D3;}
            QPushButton {
                font-family: "微软雅黑"; background-color: white; color: black;
                border: 2px solid gray; border-radius: 5px; font-weight: bold; padding: 5px;
            }
            QPushButton:hover {background-color: #f0f0f0;}
            QLabel {font-family: "微软雅黑"; font-size: 14px;}
            QLineEdit {
                font-family: "微软雅黑"; background-color: white; color: black;
                border: 2px solid gray; border-radius: 5px; padding: 5px;
            }
        """
    
    @staticmethod
    def get_confirmation_dialog_style() -> str:
        """获取确认对话框样式"""
        return """
            QDialog {background-color: #D2D4D3;}
            QPushButton {
                font-family: "微软雅黑"; background-color: white; color: black;
                font-size: 10px; padding: 1px;
            }
            QPushButton:hover {background-color: #f0f0f0;}
            QLabel {color: red; font-family: "微软雅黑"; font-size: 24px; font-weight: bold;}
        """
    
    @staticmethod
    def get_closing_dialog_style() -> str:
        """获取关闭对话框样式"""
        return """
            QDialog {background-color: #D2D4D3;}
            QPushButton {
                font-family: "微软雅黑"; background-color: white; color: black;
                font-size: 24px; padding: 1px;
            }
            QPushButton:hover {background-color: #f0f0f0;}
            QLabel {color: red; font-family: "微软雅黑"; font-size: 24px; font-weight: bold;}
        """


class LoadingDialog(QDialog):
    """加载对话框"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.angle = 0
        self._init_ui()
        
    def _init_ui(self) -> None:
        """初始化UI"""
        self.setWindowTitle("处理中...")
        self.setFixedSize(300, 200)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
        self.setStyleSheet(DialogStyleManager.get_loading_dialog_style())
        
        layout = QVBoxLayout()
        self.animation_widget = AnimationWidget(self)
        self.text_label = QLabel("正在处理，请稍候...")
        self.text_label.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(self.animation_widget, 0, Qt.AlignCenter)
        layout.addWidget(self.text_label)
        self.setLayout(layout)
        
        self._setup_animation_timer()
    
    def _setup_animation_timer(self) -> None:
        """设置动画定时器"""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(AnimationConfig.ANIMATION_DURATION)
    
    def update_animation(self) -> None:
        """更新动画"""
        self.angle = (self.angle + 10) % 360
        self.animation_widget.update_angle(self.angle)
    
    def showEvent(self, event) -> None:
        """显示事件处理"""
        super().showEvent(event)
        self.timer.start(AnimationConfig.ANIMATION_DURATION)
    
    def hideEvent(self, event) -> None:
        """隐藏事件处理"""
        super().hideEvent(event)
        self.timer.stop()


class PageOffsetDialog(QDialog):
    """页码偏移量询问对话框"""
    
    def __init__(self, parent: Optional[QWidget] = None, pdf_name: str = "", 
                 user_page: str = "", pdf_path: str = ""):
        super().__init__(parent)
        self.pdf_name = pdf_name
        self.user_page = user_page
        self.pdf_path = pdf_path
        self.actual_page = ""
        self.pdf_opened = False
        self._init_ui()
        
    def _init_ui(self) -> None:
        """初始化UI"""
        self.setWindowTitle("页码偏移量设置")
        self.setFixedSize(450, 250)
        self.setStyleSheet(DialogStyleManager.get_page_offset_dialog_style())
        
        layout = QVBoxLayout()
        
        # 信息显示
        info_label = QLabel(
            f"PDF文件: {self.pdf_name}\n\n"
            f"您输入的页码: {self.user_page}\n\n"
            "请查看PDF文件，确定该页在PDF中的实际页码:"
        )
        info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_label)
        
        # 页码输入
        form_layout = QFormLayout()
        self.page_input = QLineEdit()
        self.page_input.setPlaceholderText("请输入实际页码")
        form_layout.addRow("实际页码:", self.page_input)
        layout.addLayout(form_layout)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        self.open_pdf_button = QPushButton("打开PDF")
        self.open_pdf_button.clicked.connect(self._open_pdf)
        
        self.confirm_button = QPushButton("确认")
        self.confirm_button.clicked.connect(self._confirm)
        
        button_layout.addWidget(self.open_pdf_button)
        button_layout.addStretch()
        button_layout.addWidget(self.confirm_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        self._setup_auto_open_timer()
    
    def _setup_auto_open_timer(self) -> None:
        """设置自动打开PDF定时器"""
        self.open_timer = QTimer(self)
        self.open_timer.setSingleShot(True)
        self.open_timer.timeout.connect(self._auto_open_pdf)
        self.open_timer.start(5000)
    
    def _open_pdf(self) -> None:
        """手动打开PDF文件"""
        if not self.pdf_opened:
            self._open_pdf_file(self.pdf_path)
            self.pdf_opened = True
            self.open_pdf_button.setEnabled(False)
            self.open_pdf_button.setText("PDF已打开")
    
    def _auto_open_pdf(self) -> None:
        """自动打开PDF文件"""
        if not self.pdf_opened:
            self._open_pdf_file(self.pdf_path)
            self.pdf_opened = True
            self.open_pdf_button.setEnabled(False)
            self.open_pdf_button.setText("PDF已自动打开")
    
    def _open_pdf_file(self, pdf_path: str) -> None:
        """使用系统默认方式打开PDF文件"""
        try:
            if sys.platform == "win32":#windows
                os.startfile(pdf_path)
            elif sys.platform == "darwin":#mac
                os.system(f"open '{pdf_path}'")
            else:#Linux
                os.system(f"xdg-open '{pdf_path}'")
        except Exception as e:
            print(f"打开PDF文件失败: {e}")
    
    def _confirm(self) -> None:
        """确认按钮处理"""
        page_text = self.page_input.text().strip()
        if page_text and page_text.isdigit():
            self.actual_page = page_text
            self.accept()
        else:
            QMessageBox.warning(self, "提示", "请输入有效的页码")


class ClearConfirmationDialog(QDialog):
    """清空确认对话框"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.result = False
        self.buttons = []
        self._init_ui()
        
    def _init_ui(self) -> None:
        """初始化UI"""
        self.setWindowTitle("确认清空")
        self.setFixedSize(400, 200)
        self.setStyleSheet(DialogStyleManager.get_confirmation_dialog_style())
        
        layout = QVBoxLayout()
        label = QLabel(
            "确认清空吗？\n"
            "（若点击文本输入与导入界面\n"
            "右上角的关闭按钮\n"
            "则会先清除后退出）"
        )
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        
        #随机按钮布局
        button_layout = QHBoxLayout()
        self._create_random_buttons(button_layout)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def _create_random_buttons(self, layout: QHBoxLayout) -> None:
        """创建随机排列的确认按钮"""
        yes_position = random.randint(0, 4)
        
        for i in range(5):
            if i == yes_position:
                button = QPushButton("是", self)
                button.clicked.connect(self._on_yes_clicked)
            else:
                button = QPushButton("否", self)
                button.clicked.connect(self._on_no_clicked)
            self.buttons.append(button)
            layout.addWidget(button)
    
    def _on_yes_clicked(self) -> None:
        """是按钮点击处理"""
        self.result = True
        self.accept()
    
    def _on_no_clicked(self) -> None:
        """否按钮点击处理"""
        self.result = False
        self.reject()


class ClosingDialog(QDialog):
    """关闭确认对话框"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.result = False
        self.buttons = []
        self._init_ui()
        
    def _init_ui(self) -> None:
        """初始化UI"""
        self.setWindowTitle("提示")  # 空标题
        self.setFixedSize(400, 200)
        self.setStyleSheet(DialogStyleManager.get_closing_dialog_style())
        
        layout = QVBoxLayout()
        label = QLabel("点击\"确认\"以退出文本编辑界面。\n而非点击右上角的\"X\"。")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        
        # 确认按钮布局
        button_layout = QHBoxLayout()
        self._create_confirmation_buttons(button_layout)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def _create_confirmation_buttons(self, layout: QHBoxLayout) -> None:
        """创建确认按钮"""
        confirmation_texts = ['好', '知道了', '确认', '明白']
        
        for text in confirmation_texts:
            button = QPushButton(text, self)
            button.clicked.connect(self._on_confirmation_clicked)
            self.buttons.append(button)
            layout.addWidget(button)
    
    def _on_confirmation_clicked(self) -> None:
        """确认按钮点击处理"""
        self.result = True
        self.accept()


class DialogFactory:
    """对话框启动器"""
    
    @staticmethod
    def create_loading_dialog(parent: Optional[QWidget] = None) -> LoadingDialog:
        """创建加载对话框"""
        return LoadingDialog(parent)
    
    @staticmethod
    def create_page_offset_dialog(parent: Optional[QWidget] = None, 
                                 pdf_name: str = "", user_page: str = "", 
                                 pdf_path: str = "") -> PageOffsetDialog:
        """创建页码偏移对话框"""
        return PageOffsetDialog(parent, pdf_name, user_page, pdf_path)
    
    @staticmethod
    def create_clear_confirmation_dialog(parent: Optional[QWidget] = None) -> ClearConfirmationDialog:
        """创建清空确认对话框"""
        return ClearConfirmationDialog(parent)
    
    @staticmethod
    def create_closing_dialog(parent: Optional[QWidget] = None) -> ClosingDialog:
        """创建关闭确认对话框"""
        return ClosingDialog(parent)


#沟槽的向后兼容
def show_loading_dialog(parent: Optional[QWidget] = None) -> LoadingDialog:
    """显示加载对话框（向后兼容）"""
    return DialogFactory.create_loading_dialog(parent)


def show_page_offset_dialog(parent: Optional[QWidget] = None, pdf_name: str = "", 
                           user_page: str = "", pdf_path: str = "") -> PageOffsetDialog:
    """显示页码偏移对话框（向后兼容）"""
    return DialogFactory.create_page_offset_dialog(parent, pdf_name, user_page, pdf_path)


def show_clear_confirmation_dialog(parent: Optional[QWidget] = None) -> ClearConfirmationDialog:
    """显示清空确认对话框（向后兼容）"""
    return DialogFactory.create_clear_confirmation_dialog(parent)


def show_closing_dialog(parent: Optional[QWidget] = None) -> ClosingDialog:
    """显示关闭确认对话框（向后兼容）"""
    return DialogFactory.create_closing_dialog(parent)


#检查模式
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    mode=int(input("检查模式\n输入需要检查的窗口\n1-加载框\n2-页码偏移\n3-清空确认\n4-关闭确认"))
    #创建对话框
    if mode == 1:
        loading_dialog = DialogFactory.create_loading_dialog()
        loading_dialog.show()
        QTimer.singleShot(2000, loading_dialog.close)
        QTimer.singleShot(2000, app.quit)
    elif mode == 2:
        loading_dialog = DialogFactory.create_page_offset_dialog()
        loading_dialog.show()
        QTimer.singleShot(10000, loading_dialog.close)
        QTimer.singleShot(10000, app.quit)
    elif mode == 3:
        loading_dialog = DialogFactory.create_clear_confirmation_dialog()
        loading_dialog.show()
        QTimer.singleShot(10000, loading_dialog.close)
        QTimer.singleShot(10000, app.quit)
    else:
        loading_dialog = DialogFactory.create_closing_dialog()
        loading_dialog.show()
        QTimer.singleShot(10000, loading_dialog.close)
        QTimer.singleShot(10000, app.quit)
    
    
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    print(0)
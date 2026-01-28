# coding=utf-8
import sys
import os
import random
from typing import Optional
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, 
    QMessageBox, QVBoxLayout, QHBoxLayout, QDialog, QLabel, 
     QLineEdit, QFormLayout, QSpinBox, QCheckBox, QScrollArea
)
from PyQt5.QtCore import Qt, QTimer, QRect
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QPixmap, QImage

from misc_func import SettingsManager



class AnimationConfig:
    """动画配置"""
    ANIMATION_DURATION = 35  # 动画更新间隔(毫秒)
    WIDGET_SIZE = 80  # 动画部件尺寸
    RECT_MARGIN = 10  # 矩形边距
    PEN_WIDTH = 10  # 画笔宽度
    START_ANGLE_MULTIPLIER = 16  # 起始角度乘数
    SPAN_ANGLE = 270 * 16  # 跨度角度


class AnimationWidget(QWidget):
    """动画部件"""
    
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
    """样式管理器"""
    
    @staticmethod
    def _get_background_color() -> str:
        """获取用户设置的背景颜色"""
        
        try:
            settings_manager = SettingsManager()
            return settings_manager.get_Custom_value("background_color", "#D2D4D3")
        except:
            pass
        return "#D2D4D3"
    
    @staticmethod
    def get_loading_dialog_style() -> str:
        """获取加载对话框样式"""
        background_color = DialogStyleManager._get_background_color()
        return f"""
            QDialog {{background-color: {background_color};}}
            QLabel {{font-family: "微软雅黑"; font-size: 16px; color: #333333;}}
        """
    
    @staticmethod
    def get_page_offset_dialog_style() -> str:
        """获取页码偏移对话框样式"""
        background_color = DialogStyleManager._get_background_color()
        return f"""
            QDialog {{background-color: {background_color};}}
            QPushButton {{
                font-family: "微软雅黑"; background-color: white; color: black;
                border: 2px solid gray; border-radius: 5px; font-weight: bold; padding: 5px;
            }}
            QPushButton:hover {{background-color: #f0f0f0;}}
            QLabel {{font-family: "微软雅黑"; font-size: 14px;}}
            QLineEdit {{
                font-family: "微软雅黑"; background-color: white; color: black;
                border: 2px solid gray; border-radius: 5px; padding: 5px;
            }}
        """
    
    @staticmethod
    def get_confirmation_dialog_style() -> str:
        """获取确认对话框样式"""
        background_color = DialogStyleManager._get_background_color()
        return f"""
            QDialog {{background-color: {background_color};}}
            QPushButton {{
                font-family: "微软雅黑"; background-color: white; color: black;
                font-size: 10px; padding: 1px;
            }}
            QPushButton:hover {{background-color: #f0f0f0;}}
            QLabel {{color: red; font-family: "微软雅黑"; font-size: 24px; font-weight: bold;}}
        """
    
    @staticmethod
    def get_closing_dialog_style() -> str:
        """获取关闭对话框样式"""
        background_color = DialogStyleManager._get_background_color()
        return f"""
            QDialog {{background-color: {background_color};}}
            QPushButton {{
                font-family: "微软雅黑"; background-color: white; color: black;
                font-size: 24px; padding: 1px;
            }}
            QPushButton:hover {{background-color: #f0f0f0;}}
            QLabel {{color: red; font-family: "微软雅黑"; font-size: 24px; font-weight: bold;}}
        """


class LoadingDialog(QDialog):
    """加载对话框
    
    用于显示加载动画和提示信息的模态对话框。
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.angle = 0
        self._init_ui()
        self._update_fonts()
        
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
    
    def _update_fonts(self) -> None:
        """更新字体大小"""
        current_width = self.width()
        current_height = self.height()
        
        min_font_size = 12
        max_font_size = 24
        default_width = 300
        default_height = 200
        
        width_ratio = current_width / default_width
        height_ratio = current_height / default_height
        ratio = (width_ratio + height_ratio) / 2
        
        font_size = min_font_size + (max_font_size - min_font_size) * (ratio - 1)
        font_size = max(min_font_size, min(max_font_size, font_size))
        
        try:
            settings_manager = SettingsManager()
            global_font = settings_manager.Custom.get_value("global_font", "微软雅黑")
        except:
            global_font = "微软雅黑"
        
        font = QFont(global_font, int(font_size))
        self.text_label.setFont(font)
    
    def resizeEvent(self, event) -> None:
        """处理窗口大小变化事件"""
        super().resizeEvent(event)
        self._update_fonts()
    
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

    def set_message(self, message: str) -> None:
        """设置加载对话框的提示信息"""
        self.text_label.setText(message)


class PageOffsetDialog(QDialog):
    """页码偏移对话框"""
    
    def __init__(self, parent: Optional[QWidget] = None, pdf_name: str = "", 
                 user_page: str = "", pdf_path: str = ""):
        super().__init__(parent)
        self.pdf_name = pdf_name
        self.user_page = user_page
        self.pdf_path = pdf_path
        self.actual_page = ""
        self.pdf_opened = False
        self._init_ui()
        self._update_fonts()
        
    def _init_ui(self) -> None:
        """初始化UI"""
        self.setWindowTitle("页码偏移量设置")
        self.setFixedSize(450, 250)
        self.setStyleSheet(DialogStyleManager.get_page_offset_dialog_style())
        
        layout = QVBoxLayout()
        
        # 信息显示
        self.info_label = QLabel(
            f"PDF文件: {self.pdf_name}\n\n"
            f"您输入的页码: {self.user_page}\n\n"
            "请查看PDF文件，确定该页在PDF中的实际页码:"
        )
        self.info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.info_label)
        
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
    
    def _update_fonts(self) -> None:
        """更新字体大小"""
        current_width = self.width()
        current_height = self.height()
        
        min_font_size = 10
        max_font_size = 20
        default_width = 450
        default_height = 250
        
        width_ratio = current_width / default_width
        height_ratio = current_height / default_height
        ratio = (width_ratio + height_ratio) / 2
        
        font_size = min_font_size + (max_font_size - min_font_size) * (ratio - 1)
        font_size = max(min_font_size, min(max_font_size, font_size))
        
        try:
            settings_manager = SettingsManager()
            global_font = settings_manager.Custom.get_value("global_font", "微软雅黑")
        except:
            global_font = "微软雅黑"
        
        font = QFont(global_font, int(font_size))
        
        self.info_label.setFont(font)
        self.page_input.setFont(font)
        self.open_pdf_button.setFont(font)
        self.confirm_button.setFont(font)
    
    def resizeEvent(self, event) -> None:
        """处理窗口大小变化事件"""
        super().resizeEvent(event)
        self._update_fonts()
    
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
            if sys.platform == "win32":  # Windows
                os.startfile(pdf_path)
            elif sys.platform == "darwin":  # Mac
                os.system(f"open '{pdf_path}'")
            else:  # Linux
                os.system(f"xdg-open '{pdf_path}'")
        except Exception as e:
            # 打开PDF文件失败，静默处理
            pass
    
    def _confirm(self) -> None:
        """确认按钮处理"""
        page_text = self.page_input.text().strip()
        if page_text and page_text.isdigit():
            self.actual_page = page_text
            self.accept()
        else:
            QMessageBox.warning(self, "提示", "请输入有效的页码")


class ClearConfirmationDialog(QDialog):
    """清空确认对话框
    
    用于确认用户是否要清空内容的对话框，包含随机排列的是/否按钮以防止误操作。
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.result = False
        self.buttons = []
        self._init_ui()
        self._update_fonts()
        
    def _init_ui(self) -> None:
        """初始化UI"""
        self.setWindowTitle("确认清空")
        self.setFixedSize(400, 200)
        self.setStyleSheet(DialogStyleManager.get_confirmation_dialog_style())
        
        layout = QVBoxLayout()
        self.label = QLabel(
            "确认清空吗？\n"
            "（若点击文本输入与导入界面\n"
            "右上角的关闭按钮\n"
            "则会先清除后退出）"
        )
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)
        
        #随机按钮布局
        button_layout = QHBoxLayout()
        self._create_random_buttons(button_layout)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def _update_fonts(self) -> None:
        """更新字体大小"""
        current_width = self.width()
        current_height = self.height()
        
        min_font_size = 16
        max_font_size = 32
        default_width = 400
        default_height = 200
        
        width_ratio = current_width / default_width
        height_ratio = current_height / default_height
        ratio = (width_ratio + height_ratio) / 2
        
        font_size = min_font_size + (max_font_size - min_font_size) * (ratio - 1)
        font_size = max(min_font_size, min(max_font_size, font_size))
        
        try:
            settings_manager = SettingsManager()
            global_font = settings_manager.Custom.get_value("global_font", "微软雅黑")
        except:
            global_font = "微软雅黑"
        
        font = QFont(global_font, int(font_size))
        self.label.setFont(font)
        
        button_font_size = int(font_size * 0.5)
        button_font = QFont(global_font, button_font_size)
        for button in self.buttons:
            button.setFont(button_font)
    
    def resizeEvent(self, event) -> None:
        """处理窗口大小变化事件"""
        super().resizeEvent(event)
        self._update_fonts()
    
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



class ClearConfirmationDialog(QDialog):
    """清空确认对话框
    
    用于确认用户是否要清空内容的对话框，包含随机排列的是/否按钮以防止误操作。
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.result = False
        self.buttons = []
        self._init_ui()
        self._update_fonts()
    
    def _init_ui(self) -> None:
        """初始化UI"""
        self.setWindowTitle("确认清空")
        self.setFixedSize(400, 200)
        self.setStyleSheet(DialogStyleManager.get_confirmation_dialog_style())
        
        layout = QVBoxLayout()
        self.label = QLabel(
            "确认清空吗？\n"
            "（若点击文本输入与导入界面\n"
            "右上角的关闭按钮\n"
            "则会先清除后退出）"
        )
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)
        
        #随机按钮布局
        button_layout = QHBoxLayout()
        self._create_random_buttons(button_layout)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def _update_fonts(self) -> None:
        """更新字体大小"""
        current_width = self.width()
        current_height = self.height()
        
        min_font_size = 16
        max_font_size = 32
        default_width = 400
        default_height = 200
        
        width_ratio = current_width / default_width
        height_ratio = current_height / default_height
        ratio = (width_ratio + height_ratio) / 2
        
        font_size = min_font_size + (max_font_size - min_font_size) * (ratio - 1)
        font_size = max(min_font_size, min(max_font_size, font_size))
        
        try:
            settings_manager = SettingsManager()
            global_font = settings_manager.Custom.get_value("global_font", "微软雅黑")
        except:
            global_font = "微软雅黑"
        
        font = QFont(global_font, int(font_size))
        self.label.setFont(font)
        
        button_font_size = int(font_size * 0.5)
        button_font = QFont(global_font, button_font_size)
        for button in self.buttons:
            button.setFont(button_font)
    
    def resizeEvent(self, event) -> None:
        """处理窗口大小变化事件"""
        super().resizeEvent(event)
        self._update_fonts()
    
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


class MultiImageImportDialog(QDialog):
    """多图片导入对话框"""

    def __init__(self, parent: Optional[QWidget] = None, image_paths: list[str] = None):
        super().__init__(parent)
        self.image_paths = image_paths if image_paths is not None else []
        self.result_image_paths = []  # 存储最终要导入的图片路径
        self.current_preview_index = 0
        self.image_widgets = [] # 存储每个图片的checkbox, label, spinbox
        self._init_ui()
        self._update_ui_visibility()
        self._display_image(self.current_preview_index)

    def _init_ui(self) -> None:
        """初始化UI"""
        self.setWindowTitle("多图片导入与排序")
        self.setFixedSize(800, 700)
        self.setStyleSheet(DialogStyleManager.get_page_offset_dialog_style()) # 复用页码偏移对话框的样式

        main_layout = QVBoxLayout()

        # 图片预览部分
        preview_group_box = QWidget()
        preview_layout = QHBoxLayout(preview_group_box)
        
        self.image_preview_label = QLabel("这里显示用户选择的图片")
        self.image_preview_label.setAlignment(Qt.AlignCenter)
        self.image_preview_label.setFixedSize(400, 300)
        self.image_preview_label.setStyleSheet("border: 1px solid gray; background-color: #f0f0f0;")
        preview_layout.addWidget(self.image_preview_label)

        # 图片选择按钮
        image_select_button_layout = QVBoxLayout()
        self.image_select_buttons = []
        for i in range(5):
            btn = QPushButton(f"图片 {i+1}", self)
            btn.clicked.connect(lambda checked, index=i: self._display_image(index))
            self.image_select_buttons.append(btn)
            image_select_button_layout.addWidget(btn)
        preview_layout.addLayout(image_select_button_layout)
        main_layout.addWidget(QLabel("图片预览"))
        main_layout.addWidget(preview_group_box)

        # 图片排序部分
        sort_content_widget = QWidget()
        self.sort_layout = QVBoxLayout(sort_content_widget)
        self.image_sort_entries = [] # 存储 (checkbox, filename_label, spinbox)
        
        for i in range(5):
            h_layout = QHBoxLayout()
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            filename_label = QLabel(f"图片 {i+1} 文件名")
            spinbox = QSpinBox()
            spinbox.setMinimum(1)
            spinbox.setMaximum(5)
            spinbox.setValue(i + 1)
            
            checkbox.stateChanged.connect(lambda state, idx=i: self._on_checkbox_state_changed(state, idx))
            spinbox.valueChanged.connect(lambda value, idx=i: self._on_spinbox_value_changed(value, idx))

            h_layout.addWidget(checkbox)
            h_layout.addWidget(filename_label)
            h_layout.addWidget(spinbox)
            h_layout.addStretch()
            
            widget_container = QWidget()
            widget_container.setLayout(h_layout)
            self.image_sort_entries.append((checkbox, filename_label, spinbox, widget_container))
            self.sort_layout.addWidget(widget_container)
        
        main_layout.addWidget(QLabel("图片排序"))
        main_layout.addWidget(sort_content_widget)

        # 底部按钮
        bottom_button_layout = QHBoxLayout()
        self.exit_button = QPushButton("退出")
        self.exit_button.clicked.connect(self.reject)
        self.start_import_button = QPushButton("开始导入")
        self.start_import_button.clicked.connect(self._start_import)
        bottom_button_layout.addStretch()
        bottom_button_layout.addWidget(self.exit_button)
        bottom_button_layout.addWidget(self.start_import_button)
        main_layout.addLayout(bottom_button_layout)

        self.setLayout(main_layout)

    def _display_image(self, index: int) -> None:
        """显示指定索引的图片"""
        if 0 <= index < len(self.image_paths):
            self.current_preview_index = index
            image_path = self.image_paths[index]
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                # 保持图片比例，缩放以适应 QLabel
                scaled_pixmap = pixmap.scaled(
                    self.image_preview_label.size(), 
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                )
                self.image_preview_label.setPixmap(scaled_pixmap)
                self.image_preview_label.setText("") # 清除占位文本
            else:
                self.image_preview_label.setText("无法加载图片")
        else:
            self.image_preview_label.setText("没有图片可供预览")

    def _update_ui_visibility(self) -> None:
        """根据图片数量更新UI元素的可见性"""
        num_images = len(self.image_paths)

        # 更新图片选择按钮和排序条目
        for i in range(5):
            # 图片选择按钮
            if i < num_images:
                self.image_select_buttons[i].setVisible(True)
                filename = os.path.basename(self.image_paths[i])
                self.image_select_buttons[i].setText(f"图片 {i+1}: {filename}")
            else:
                self.image_select_buttons[i].setVisible(False)

            # 图片排序条目
            checkbox, filename_label, spinbox, container = self.image_sort_entries[i]
            if i < num_images:
                container.setVisible(True)
                filename = os.path.basename(self.image_paths[i])
                filename_label.setText(filename)
                spinbox.setMaximum(num_images) # 根据实际图片数量设置最大值
            else:
                container.setVisible(False)

    def _on_checkbox_state_changed(self, state: int, index: int) -> None:
        """处理复选框状态变化"""
        checkbox, filename_label, spinbox, container = self.image_sort_entries[index]
        is_checked = (state == Qt.Checked)
        filename_label.setEnabled(is_checked)
        spinbox.setEnabled(is_checked)
        self._rearrange_spinbox_values()

    def _on_spinbox_value_changed(self, value: int, index: int) -> None:
        """处理SpinBox值变化"""
        # 避免在重新排列时触发多次
        if not hasattr(self, '_rearranging') or not self._rearranging:
            self._rearrange_spinbox_values()

    def _rearrange_spinbox_values(self) -> None:
        """重新排列所有启用SpinBox的值，确保顺序和唯一性"""
        self._rearranging = True # 设置标志，防止递归触发

        enabled_entries = []
        for i, (checkbox, label, spinbox, container) in enumerate(self.image_sort_entries):
            if checkbox.isChecked():
                enabled_entries.append((spinbox.value(), i, checkbox, label, spinbox, container))
        
        # 按照当前spinbox值排序，然后是原始索引
        enabled_entries.sort(key=lambda x: (x[0], x[1]))

        # 重新分配1到N的顺序值
        for new_order, entry_tuple in enumerate(enabled_entries):
            original_index = entry_tuple[1]
            spinbox = entry_tuple[4]
            spinbox.setValue(new_order + 1)
            spinbox.setMaximum(len(enabled_entries)) # 更新最大值

        # 重新排序UI中的widget
        for i in reversed(range(self.sort_layout.count())):
            widget = self.sort_layout.itemAt(i).widget()
            if widget:
                self.sort_layout.removeWidget(widget)
        
        # 按照新的顺序添加widget
        # enabled_entries 已经按照新的顺序值排序
        for entry_tuple in enabled_entries:
            container = entry_tuple[5]
            self.sort_layout.addWidget(container)
        
        # 将未启用的widget添加到末尾
        for i, (checkbox, label, spinbox, container) in enumerate(self.image_sort_entries):
            if not checkbox.isChecked():
                self.sort_layout.addWidget(container)

        self._rearranging = False # 重置标志

    def _start_import(self) -> None:
        """开始导入按钮点击处理"""
        # 收集排序后的图片路径
        self.result_image_paths = []
        
        # 获取所有启用的图片及其对应的排序值
        import_candidates = []
        for i, (checkbox, label, spinbox, container) in enumerate(self.image_sort_entries):
            if checkbox.isChecked():
                import_candidates.append((spinbox.value(), self.image_paths[i]))
        
        # 按照排序值进行排序
        import_candidates.sort(key=lambda x: x[0])
        
        # 提取排序后的图片路径
        self.result_image_paths = [path for order, path in import_candidates]
        
        if not self.result_image_paths:
            QMessageBox.warning(self, "提示", "请至少选择一张图片进行导入。")
            return
            
        self.accept()



    def _update_ui_visibility(self) -> None:
        """根据图片数量更新UI可见性"""
        num_images = len(self.image_paths)
        for i in range(5):
            is_visible = i < num_images
            self.image_select_buttons[i].setVisible(is_visible)
            self.image_sort_entries[i][0].setVisible(is_visible) # checkbox
            self.image_sort_entries[i][1].setVisible(is_visible) # filename_label
            self.image_sort_entries[i][2].setVisible(is_visible) # spinbox

            if is_visible:
                filename = os.path.basename(self.image_paths[i])
                self.image_select_buttons[i].setText(filename)
                self.image_sort_entries[i][1].setText(filename)
                self.image_sort_entries[i][2].setMaximum(num_images) # 设置spinbox的最大值

    def _display_image(self, index: int) -> None:
        """显示指定索引的图片"""
        if 0 <= index < len(self.image_paths):
            self.current_preview_index = index
            image_path = self.image_paths[index]
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                # 缩放图片以适应 QLabel
                scaled_pixmap = pixmap.scaled(self.image_preview_label.size(), 
                                              Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.image_preview_label.setPixmap(scaled_pixmap)
            else:
                self.image_preview_label.setText("无法加载图片")
        else:
            self.image_preview_label.setText("未选择图片")
            self.image_preview_label.clear() # 清除之前的图片

    def _on_checkbox_state_changed(self, state: int, index: int) -> None:
        """处理复选框状态变化"""
        # 启用/禁用对应的spinbox
        self.image_sort_entries[index][2].setEnabled(state == Qt.Checked)


    def _on_spinbox_value_changed(self, value: int, index: int) -> None:
        """处理SpinBox值变化"""
        # 重新调整排序，确保顺序连续且有效






    def _start_import(self) -> None:
        """开始导入按钮点击处理"""
        self.result_image_paths = []
        
        # 收集所有已启用并带有顺序的图片路径
        enabled_images_with_order = []
        for i, (checkbox, _, spinbox, _) in enumerate(self.image_sort_entries):
            if checkbox.isChecked() and i < len(self.image_paths):
                enabled_images_with_order.append((self.image_paths[i], spinbox.value()))
        
        if not enabled_images_with_order:
            QMessageBox.warning(self, "警告", "请至少选择一张图片进行导入。")
            return

        # 校验顺序是否连续且唯一
        orders = [order for _, order in enabled_images_with_order]
        if len(orders) != len(set(orders)):
            QMessageBox.warning(self, "警告", "图片顺序不能重复，请检查。")
            return
        
        expected_orders = list(range(1, len(orders) + 1))
        if sorted(orders) != expected_orders:
            QMessageBox.warning(self, "警告", f"图片顺序必须是连续的，从1到{len(orders)}。当前顺序为: {sorted(orders)}")
            return

        # 按照校验后的顺序进行排序
        enabled_images_with_order.sort(key=lambda x: x[1])
        
        # 提取排序后的文件路径
        self.result_image_paths = [path for path, _ in enabled_images_with_order]
        
        self.accept() # 关闭对话框并返回Accepted

    def get_selected_image_paths(self) -> list[str]:
        """获取用户选择并排序后的图片路径"""
        return self.result_image_paths
    """对话框工厂"""
    
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




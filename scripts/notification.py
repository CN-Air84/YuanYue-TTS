# coding=utf-8
"""
通知系统模块

提供美观的桌面通知功能，支持多种消息类型和动画效果。
"""

from PyQt5.QtWidgets import QWidget, QLabel
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve, QPoint, QObject
from PyQt5.QtGui import QFont, QMouseEvent
from debug_logger import debug_logger, LogLevel

# ===== 常量定义 =====
# 动画时长（毫秒）
ANIMATION_DURATION_APPEAR = 400  # 出现动画时长
ANIMATION_DURATION_DISAPPEAR = 400  # 消失动画时长
ANIMATION_DURATION_MOVE = 500  # 上移动画时长

# 提示框位置（相对于主窗口的 m, n 坐标）
NOTIFICATION_POSITION_M = 12  # m 坐标
NOTIFICATION_POSITION_N = 12.75  # n 坐标

# 提示框尺寸比例（相对于"生成预览"按钮）
NOTIFICATION_WIDTH_RATIO = 1  # 宽度比例
NOTIFICATION_HEIGHT_RATIO = 0.45  # 高度比例

# 最大可见消息数
MAX_VISIBLE_NOTIFICATIONS = 3

# 消息偏移量（n 单位）
NOTIFICATION_OFFSET_N = 1.125

# 消息间隔（n 单位）
NOTIFICATION_SPACING_N = 1

# 默认自动关闭时间（毫秒）
DEFAULT_AUTO_CLOSE_TIME = 3000

# 手势滑动阈值
SWIPE_THRESHOLD_RATIO = 0.3  # 滑动距离阈值（相对于消息框宽度的比例）
SWIPE_MIN_DISTANCE = 30  # 最小滑动距离（像素）
SWIPE_EDGE_THRESHOLD_RATIO = 0.6  # 超出边缘阈值（相对于消息框宽度的比例）
# ===== 常量定义结束 =====


class Notification(QWidget):
    """
    消息通知组件
    
    提供带有动画效果的桌面通知功能，支持手势操作和自定义样式。
    """
    
    closed = pyqtSignal()  # 关闭信号
    
    def __init__(self, parent=None):
        """
        初始化通知组件
        
        Args:
            parent: 父窗口对象
        """
        super().__init__(parent)
        debug_logger.output("notification.py", LogLevel.INFO, "正在初始化 Notification 组件", fold_code="NOTIFICATION_INIT")
        self.parent_window = parent
        self.auto_close_time = DEFAULT_AUTO_CLOSE_TIME
        self.target_position = QPoint(0, 0)
        self.is_appearing = False
        self.is_disappearing = False
        self.is_moving = False
        self.base_offset = 0  # 基础偏移量
        
        # 点击穿透状态
        self.click_through_enabled = True
        self.ctrl_pressed = False
        
        # 手势滑动相关变量
        self.drag_start_pos = None
        self.drag_current_pos = None
        self.is_dragging = False
        self.drag_start_time = None
        self.original_position = None
        
        self._init_ui()
        self._init_animations()
        
    def _init_ui(self):
        """初始化用户界面"""
        debug_logger.output("notification.py", LogLevel.INFO, "正在初始化 Notification UI", fold_code="NOTIFICATION_INIT")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        # 创建消息标签
        self.message_label = QLabel(self)
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setWordWrap(True)
        
        # 设置字体
        font = QFont("微软雅黑", 9)
        self.message_label.setFont(font)
        
        # 自动关闭定时器
        self.close_timer = QTimer(self)
        self.close_timer.timeout.connect(self._auto_close)
        
    def _init_animations(self):
        """初始化动画效果"""
        debug_logger.output("notification.py", LogLevel.INFO, "正在初始化 Notification 动画", fold_code="NOTIFICATION_INIT")
        # 出现动画 - 位置和透明度
        self.appear_position_animation = QPropertyAnimation(self, b"pos")
        self.appear_position_animation.setDuration(ANIMATION_DURATION_APPEAR)
        self.appear_position_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.appear_position_animation.finished.connect(self._on_appear_finished)
        
        # 消失动画 - 位置和透明度
        self.disappear_position_animation = QPropertyAnimation(self, b"pos")
        self.disappear_position_animation.setDuration(ANIMATION_DURATION_DISAPPEAR)
        self.disappear_position_animation.setEasingCurve(QEasingCurve.InCubic)
        self.disappear_position_animation.finished.connect(self._on_disappear_finished)
        
        # 上移动画 - 只改变位置，不改变透明度
        self.move_position_animation = QPropertyAnimation(self, b"pos")
        self.move_position_animation.setDuration(ANIMATION_DURATION_MOVE)
        self.move_position_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.move_position_animation.finished.connect(self._on_move_finished)
        
    def show_message(self, message, message_type="info", auto_close_time=DEFAULT_AUTO_CLOSE_TIME):
        """
        显示消息通知
        
        Args:
            message (str): 消息内容
            message_type (str): 消息类型 - "info", "warning", "error"
            auto_close_time (int): 自动关闭时间(毫秒)
        """
        debug_logger.output("notification.py", LogLevel.INFO, f"显示通知消息: [{message_type}] {message[:30]}...", fold_code="NOTIFICATION_SHOW")
        self.auto_close_time = auto_close_time
        
        # 从个性化设置中获取颜色
        colors = self._get_notification_colors()
        color = colors.get(message_type, colors["info"])
        
        # 更新样式
        self.message_label.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                color: white;
                border-radius: 8px;
                padding: 8px;
                font-family: "微软雅黑";
            }}
        """)
        
        self.message_label.setText(message)
        
        # 调整大小和位置
        self._adjust_size_and_position()
        
        # 设置初始状态 - 在窗口右侧外，透明度为0
        start_pos = self._get_start_position()
        self.move(start_pos)
        self.setWindowOpacity(0.0)
        
        # 显示消息
        self.show()
        
        # 确保主窗口保持焦点
        if self.parent_window:
            self.parent_window.activateWindow()
        
        # 启动出现动画
        self._start_appear_animation()
        
        # 启动自动关闭定时器
        if auto_close_time > 0:
            debug_logger.output("notification.py", LogLevel.INFO, f"启动自动关闭定时器: {auto_close_time}ms", fold_code="NOTIFICATION_SHOW")
            self.close_timer.start(auto_close_time)
    
    def _get_notification_colors(self):
        """从个性化设置中获取通知颜色配置"""
        colors = {
            "info": "#3498db",      # 默认蓝色
            "warning": "#f0da12",   # 默认黄色  
            "error": "#db3444"      # 默认红色
        }
        
        # 如果父窗口存在且有设置管理器，尝试从个性化设置中获取颜色
        if self.parent_window and hasattr(self.parent_window, 'settings_manager'):
            settings_manager = self.parent_window.settings_manager
            
            # 获取个性化设置中的颜色
            info_color = settings_manager.Custom.get_value("notification_info_color", colors["info"])
            warning_color = settings_manager.Custom.get_value("notification_warning_color", colors["warning"])
            error_color = settings_manager.Custom.get_value("notification_error_color", colors["error"])
            
            debug_logger.output("notification.py", LogLevel.INFO, f"从设置加载通知颜色: info={info_color}, warning={warning_color}, error={error_color}", fold_code="NOTIFICATION_SHOW")
            
            colors.update({
                "info": info_color,
                "warning": warning_color,
                "error": error_color
            })
        
        return colors
    
    def _get_start_position(self):
        """
        获取动画起始位置（窗口右侧外）
        
        Returns:
            QPoint: 起始位置坐标
        """
        if not self.parent_window:
            debug_logger.output("notification.py", LogLevel.WARNING, "未设置父窗口，无法计算起始位置", fold_code="NOTIFICATION_SHOW")
            return QPoint(0, 0)
            
        # 获取父窗口的位置和大小
        parent_rect = self.parent_window.geometry()
        parent_x = parent_rect.x()
        parent_width = parent_rect.width()
        
        # 计算起始位置（窗口右侧外）
        start_x = parent_x + parent_width
        start_y = self.target_position.y()
        
        return QPoint(start_x, start_y)
    
    def _get_end_position(self):
        """
        获取动画结束位置（窗口右侧外）
        
        Returns:
            QPoint: 结束位置坐标
        """
        if not self.parent_window:
            debug_logger.output("notification.py", LogLevel.WARNING, "未设置父窗口，无法计算结束位置", fold_code="NOTIFICATION_SHOW")
            return QPoint(0, 0)
            
        # 获取父窗口的位置和大小
        parent_rect = self.parent_window.geometry()
        parent_x = parent_rect.x()
        parent_width = parent_rect.width()
        
        # 计算结束位置（窗口右侧外）
        end_x = parent_x + parent_width
        end_y = self.target_position.y()
        
        return QPoint(end_x, end_y)
    
    def _start_appear_animation(self):
        """启动出现动画效果"""
        debug_logger.output("notification.py", LogLevel.INFO, "启动出现动画", fold_code="NOTIFICATION_ANIM")
        self.is_appearing = True
        
        # 设置动画参数
        self.appear_position_animation.setStartValue(self._get_start_position())
        self.appear_position_animation.setEndValue(self.target_position)
        
        # 启动位置动画
        self.appear_position_animation.start()
        
        # 启动透明度动画
        self._start_opacity_animation(0.0, 1.0, ANIMATION_DURATION_APPEAR, self._on_appear_finished)
    
    def _start_opacity_animation(self, start_opacity, end_opacity, duration, finish_callback):
        """
        启动透明度动画
        
        Args:
            start_opacity (float): 起始透明度
            end_opacity (float): 结束透明度
            duration (int): 动画持续时间
            finish_callback (callable): 动画完成回调函数
        """
        debug_logger.output("notification.py", LogLevel.INFO, f"启动透明度动画: {start_opacity} -> {end_opacity}, 耗时: {duration}ms", fold_code="NOTIFICATION_ANIM")
        # 用 QPropertyAnimation 做透明度动画
        # 这名字怎么这么长
        self.opacity_animation = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_animation.setDuration(duration)
        self.opacity_animation.setStartValue(start_opacity)
        self.opacity_animation.setEndValue(end_opacity)
        self.opacity_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.opacity_animation.finished.connect(finish_callback)
        self.opacity_animation.start()
    
    def _start_disappear_animation(self):
        """启动消失动画效果"""
        debug_logger.output("notification.py", LogLevel.INFO, "启动消失动画", fold_code="NOTIFICATION_ANIM")
        self.is_disappearing = True
        
        # 设置动画参数
        self.disappear_position_animation.setStartValue(self.pos())
        self.disappear_position_animation.setEndValue(self._get_end_position())
        
        # 启动位置动画
        self.disappear_position_animation.start()
        
        # 启动透明度动画
        self._start_opacity_animation(1.0, 0.0, ANIMATION_DURATION_DISAPPEAR, self._on_disappear_finished)
    
    def _start_move_animation(self, new_target_position):
        """
        启动上移动画效果
        
        Args:
            new_target_position (QPoint): 新的目标位置
        """
        if self.is_disappearing:
            return
            
        debug_logger.output("notification.py", LogLevel.INFO, f"启动上移动画, 目标位置: {new_target_position}", fold_code="NOTIFICATION_ANIM")
        self.is_moving = True
        self.target_position = new_target_position
        
        # 设置动画参数
        self.move_position_animation.setStartValue(self.pos())
        self.move_position_animation.setEndValue(self.target_position)
        
        # 启动位置动画
        self.move_position_animation.start()
    
    def _on_appear_finished(self):
        """出现动画完成回调"""
        debug_logger.output("notification.py", LogLevel.INFO, "出现动画已完成", fold_code="NOTIFICATION_ANIM")
        self.is_appearing = False
        # 修复透明度问题：确保动画结束后不透明度为100%
        self.setWindowOpacity(1.0)
    
    def _on_disappear_finished(self):
        """消失动画完成回调"""
        debug_logger.output("notification.py", LogLevel.INFO, "消失动画已完成，关闭通知", fold_code="NOTIFICATION_ANIM")
        self.is_disappearing = False
        self.close()
        self.closed.emit()
    
    def _on_move_finished(self):
        """上移动画完成回调"""
        debug_logger.output("notification.py", LogLevel.INFO, "上移动画已完成", fold_code="NOTIFICATION_ANIM")
        self.is_moving = False
    
    def _adjust_size_and_position(self):
        """调整消息框大小和位置"""
        if not self.parent_window:
            return
            
        # 计算消息框大小（基于生成预览按钮的尺寸）
        preview_button = None
        try:
            preview_button = self.parent_window.generation_page.preview_control.preview_button
        except AttributeError:
            # 找不到preview_button就换招
            try:
                # 尝试直接通过当前页面获取
                current_page = self.parent_window.stacked_widget.currentWidget()
                if hasattr(current_page, 'preview_control'):
                    preview_button = current_page.preview_control.preview_button
            except AttributeError:
                pass
        
        if preview_button and preview_button.isVisible():
            button_width = preview_button.width()
            button_height = preview_button.height()
            
            # 计算消息框尺寸
            msg_width = int(button_width * NOTIFICATION_WIDTH_RATIO)
            msg_height = int(button_height * NOTIFICATION_HEIGHT_RATIO)
            debug_logger.output("notification.py", LogLevel.INFO, f"基于预览按钮调整尺寸: {msg_width}x{msg_height}", fold_code="NOTIFICATION_SHOW")
        else:
            # 使用默认大小
            parent_rect = self.parent_window.geometry()
            msg_width = int(parent_rect.width() * 0.3)  # 父窗口宽度的30%
            msg_height = 60  # 默认高度60像素
            debug_logger.output("notification.py", LogLevel.INFO, f"使用默认通知尺寸: {msg_width}x{msg_height}", fold_code="NOTIFICATION_SHOW")
        
        # 设置消息框大小
        self.message_label.setFixedSize(msg_width, msg_height)
        self.setFixedSize(msg_width, msg_height)
        
        # 计算目标位置
        self._update_position()
    
    def _update_position(self):
        """更新位置 - 相对于父窗口的位置"""
        if not self.parent_window:
            return
            
        # 获取父窗口的位置和大小
        parent_rect = self.parent_window.geometry()
        parent_x = parent_rect.x()
        parent_y = parent_rect.y()
        parent_width = parent_rect.width()
        parent_height = parent_rect.height()
        
        # 计算渲染区宽度（选项卡栏右边界到窗口右边界）
        # 选项卡栏宽度为窗口宽度的10%
        tab_bar_width = int(parent_width * 0.1)
        render_area_width = parent_width - tab_bar_width
        
        # 计算 n 和 m 值（以渲染区为参考）
        n = render_area_width / 16
        m = parent_height / 16
        
        # 计算相对于父窗口的位置
        pos_x = parent_x + int(NOTIFICATION_POSITION_M * n)
        pos_y = parent_y + int(NOTIFICATION_POSITION_N * m) + self.base_offset
        
        # 保存目标位置
        self.target_position = QPoint(pos_x, pos_y)
        
        # 如果不在动画中，直接移动到位
        if not self.is_appearing and not self.is_disappearing and not self.is_moving:
            self.move(self.target_position)
    
    def set_position_offset(self, offset):
        """
        设置位置偏移量
        
        Args:
            offset (int): 偏移量值
        """
        debug_logger.output("notification.py", LogLevel.INFO, f"设置位置偏移量: {offset}", fold_code="NOTIFICATION_SHOW")
        self.base_offset = offset
        
        # 计算新的目标位置
        if not self.parent_window:
            return
            
        parent_rect = self.parent_window.geometry()
        parent_x = parent_rect.x()
        parent_y = parent_rect.y()
        parent_width = parent_rect.width()
        parent_height = parent_rect.height()
        
        # 计算渲染区宽度（选项卡栏右边界到窗口右边界）
        # 选项卡栏宽度为窗口宽度的10%
        tab_bar_width = int(parent_width * 0.1)
        render_area_width = parent_width - tab_bar_width
        
        # 计算 n 和 m 值（以渲染区为参考）
        n = render_area_width / 16
        m = parent_height / 16
        
        new_pos_x = parent_x + int(NOTIFICATION_POSITION_M * n)
        new_pos_y = parent_y + int(NOTIFICATION_POSITION_N * m) + offset
        
        new_target_position = QPoint(new_pos_x, new_pos_y)
        
        # 如果不在动画中，启动上移动画
        if not self.is_appearing and not self.is_disappearing and not self.is_moving:
            self._start_move_animation(new_target_position)
    
    def update_position_immediately(self):
        """立即更新位置（不带动画效果）"""
        debug_logger.output("notification.py", LogLevel.INFO, "立即更新位置（无动画）", fold_code="NOTIFICATION_SHOW")
        # 停止所有可能的位置动画
        if self.is_appearing:
            self.appear_position_animation.stop()
        if self.is_disappearing:
            self.disappear_position_animation.stop()
        if self.is_moving:
            self.move_position_animation.stop()
            
        # 重置状态
        self.is_appearing = False
        self.is_disappearing = False
        self.is_moving = False
        
        # 立即更新位置
        self._update_position()
        self.move(self.target_position)
    
    def start_disappear_animation(self):
        """开始消失动画效果"""
        if not self.is_disappearing and not self.is_appearing:
            self._auto_close()
    
    def _auto_close(self):
        """自动关闭消息"""
        if self.is_disappearing:
            return
            
        debug_logger.output("notification.py", LogLevel.INFO, "自动关闭消息", fold_code="NOTIFICATION_SHOW")
        self.close_timer.stop()
        self._start_disappear_animation()
    
    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """
        鼠标双击事件处理
        
        Args:
            event (QMouseEvent): 鼠标事件对象
        """
        if event.button() == Qt.LeftButton:
            debug_logger.output("notification.py", LogLevel.INFO, "检测到双击消息，触发关闭", fold_code="NOTIFICATION_EVENT")
            self._auto_close()
    
    def closeEvent(self, event):
        """
        窗口关闭事件处理
        
        Args:
            event (QCloseEvent): 关闭事件对象
        
        这函数注释格式是真够麻烦的 
        """
        debug_logger.output("notification.py", LogLevel.INFO, "Notification 窗口正在关闭", fold_code="NOTIFICATION_EVENT")
        self.close_timer.stop()
        if self.is_appearing:
            self.appear_position_animation.stop()
            if hasattr(self, 'opacity_animation'):
                self.opacity_animation.stop()
        if self.is_disappearing:
            self.disappear_position_animation.stop()
            if hasattr(self, 'opacity_animation'):
                self.opacity_animation.stop()
        if self.is_moving:
            self.move_position_animation.stop()
        self.closed.emit()
        if self.parent_window:
            self.parent_window.activateWindow()
            self.parent_window.setFocus()
        event.accept()
    
    # ===== 点击穿透和手势滑动功能 =====
    
    def set_click_through_enabled(self, enabled):
        """
        设置点击穿透是否启用
        
        Args:
            enabled (bool): 是否启用点击穿透
        """
        debug_logger.output("notification.py", LogLevel.INFO, f"设置点击穿透: {enabled}", fold_code="NOTIFICATION_EVENT")
        self.click_through_enabled = enabled
    
    def update_click_through_state(self):
        """更新点击穿透状态"""
        # 如果Ctrl键按下，禁用点击穿透；否则启用
        effective_click_through = self.click_through_enabled and not self.ctrl_pressed
        
        # 设置窗口属性
        if effective_click_through:
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        else:
            self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
            
        debug_logger.output("notification.py", LogLevel.INFO, f"更新点击穿透状态: effective={effective_click_through} (enabled={self.click_through_enabled}, ctrl={self.ctrl_pressed})", fold_code="NOTIFICATION_EVENT")
    
    def keyPressEvent(self, event):
        """
        键盘按下事件处理
        
        Args:
            event (QKeyEvent): 键盘事件对象
        """
        if event.key() == Qt.Key_Control:
            self.ctrl_pressed = True
            self.update_click_through_state()
        super().keyPressEvent(event)
    
    def keyReleaseEvent(self, event):
        """
        键盘释放事件处理
        
        Args:
            event (QKeyEvent): 键盘事件对象
        """
        if event.key() == Qt.Key_Control:
            self.ctrl_pressed = False
            self.update_click_through_state()
        super().keyReleaseEvent(event)
    
    def mousePressEvent(self, event: QMouseEvent):
        """
        鼠标按下事件处理 - 用于手势滑动
        
        Args:
            event (QMouseEvent): 鼠标事件对象
        """
        if event.button() == Qt.LeftButton and not self.ctrl_pressed:
            debug_logger.output("notification.py", LogLevel.INFO, "检测到鼠标按下，开始处理滑动", fold_code="NOTIFICATION_EVENT")
            self.drag_start_pos = event.globalPos()
            self.drag_current_pos = event.globalPos()
            self.is_dragging = True
            self.original_position = self.pos()
            
            # 停止自动关闭计时器
            self.close_timer.stop()
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """
        鼠标移动事件处理 - 用于手势滑动
        
        Args:
            event (QMouseEvent): 鼠标事件对象
        """
        if self.is_dragging and not self.ctrl_pressed:
            self.drag_current_pos = event.globalPos()
            
            # 计算拖动距离
            drag_distance = self.drag_current_pos.x() - self.drag_start_pos.x()
            
            # 如果向右拖动，更新位置
            if drag_distance > 0:
                new_x = self.original_position.x() + drag_distance
                self.move(new_x, self.original_position.y())
                
                # 计算透明度变化（越靠近边缘越透明）
                if self.parent_window:
                    parent_right = self.parent_window.geometry().right()
                    current_right = new_x + self.width()
                    
                    # 当消息框开始超出主窗口边界时，逐渐降低透明度
                    if current_right > parent_right:
                        overlap = current_right - parent_right
                        max_overlap = self.width() * SWIPE_EDGE_THRESHOLD_RATIO
                        opacity = max(0.3, 1.0 - (overlap / max_overlap))
                        self.setWindowOpacity(opacity)
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """
        鼠标释放事件处理 - 用于手势滑动
        
        Args:
            event (QMouseEvent): 鼠标事件对象
        """
        if event.button() == Qt.LeftButton and self.is_dragging and not self.ctrl_pressed:
            debug_logger.output("notification.py", LogLevel.INFO, "检测到鼠标释放，结束滑动处理", fold_code="NOTIFICATION_EVENT")
            self.is_dragging = False
            
            # 计算滑动距离
            drag_distance = self.drag_current_pos.x() - self.drag_start_pos.x()
            
            # 计算动态阈值（基于消息框宽度）
            dynamic_threshold = max(SWIPE_MIN_DISTANCE, self.width() * SWIPE_THRESHOLD_RATIO)
            
            # 检查是否超出主窗口边界
            is_beyond_edge = False
            if self.parent_window:
                parent_right = self.parent_window.geometry().right()
                current_right = self.x() + self.width()
                edge_threshold = self.width() * SWIPE_EDGE_THRESHOLD_RATIO
                is_beyond_edge = (current_right - parent_right) > edge_threshold
            
            # 检查是否满足滑动消失条件
            if (drag_distance > dynamic_threshold or is_beyond_edge) and not self.is_disappearing:
                # 向右滑动满足条件，触发消失动画
                debug_logger.output("notification.py", LogLevel.INFO, f"滑动满足消失条件 (distance={drag_distance}, beyond_edge={is_beyond_edge})", fold_code="NOTIFICATION_EVENT")
                self._start_swipe_disappear_animation()
            else:
                # 不满足条件，回到原位
                debug_logger.output("notification.py", LogLevel.INFO, f"滑动不满足消失条件，返回原位 (distance={drag_distance})", fold_code="NOTIFICATION_EVENT")
                self._start_return_animation()
                
                # 重新启动自动关闭计时器
                if self.auto_close_time > 0:
                    self.close_timer.start(self.auto_close_time)
    
    def _start_swipe_disappear_animation(self):
        """启动滑动消失动画效果"""
        debug_logger.output("notification.py", LogLevel.INFO, "启动滑动消失动画", fold_code="NOTIFICATION_ANIM")
        # 计算目标位置（完全滑出屏幕右侧）
        if self.parent_window:
            parent_right = self.parent_window.geometry().right()
            target_x = parent_right + self.width()
        else:
            target_x = self.x() + self.width() * 2
            
        target_pos = QPoint(target_x, self.y())
        
        # 创建滑动消失动画
        self.swipe_animation = QPropertyAnimation(self, b"pos")
        self.swipe_animation.setDuration(200)
        self.swipe_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.swipe_animation.setStartValue(self.pos())
        self.swipe_animation.setEndValue(target_pos)
        self.swipe_animation.finished.connect(self._on_swipe_finished)
        self.swipe_animation.start()
        
        # 同时淡出
        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setDuration(200)
        self.fade_animation.setStartValue(self.windowOpacity())
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.start()
    
    def _on_swipe_finished(self):
        """滑动消失动画完成回调"""
        debug_logger.output("notification.py", LogLevel.INFO, "滑动消失动画已完成", fold_code="NOTIFICATION_ANIM")
        self.close()
        self.closed.emit()
    
    def _start_return_animation(self):
        """启动返回原位的动画效果"""
        debug_logger.output("notification.py", LogLevel.INFO, "启动返回原位动画", fold_code="NOTIFICATION_ANIM")
        return_animation = QPropertyAnimation(self, b"pos")
        return_animation.setDuration(300)
        return_animation.setEasingCurve(QEasingCurve.OutCubic)
        return_animation.setStartValue(self.pos())
        return_animation.setEndValue(self.original_position)
        return_animation.start()
        
        # 同时恢复透明度
        opacity_animation = QPropertyAnimation(self, b"windowOpacity")
        opacity_animation.setDuration(300)
        opacity_animation.setStartValue(self.windowOpacity())
        opacity_animation.setEndValue(1.0)
        opacity_animation.start()


class NotificationManager(QObject):
    """
    消息管理器
    
    管理多个通知消息的显示、位置和生命周期。
    """
    
    def __init__(self, parent_window):
        """
        初始化消息管理器
        
        Args:
            parent_window: 父窗口对象
        """
        super().__init__()
        debug_logger.output("notification.py", LogLevel.INFO, "正在初始化 NotificationManager", fold_code="NOTIFICATION_MANAGER")
        self.parent_window = parent_window
        self.notifications = []
        self.max_visible = MAX_VISIBLE_NOTIFICATIONS
        
        # 监听父窗口移动和调整大小事件
        if parent_window:
            parent_window.installEventFilter(self)
    
    def show_message(self, message, message_type="info", auto_close_time=DEFAULT_AUTO_CLOSE_TIME):
        """
        显示消息通知
        
        Args:
            message (str): 消息内容
            message_type (str): 消息类型 - "I"(info), "W"(warning), "E"(error)
            auto_close_time (int): 自动关闭时间(毫秒)
        """
        # 转换消息类型代码
        type_map = {
            "I": "info",
            "W": "warning", 
            "E": "error"
        }
        actual_type = type_map.get(message_type, message_type)
        debug_logger.output("notification.py", LogLevel.INFO, f"NotificationManager 请求显示消息: [{actual_type}] {message[:30]}...", fold_code="NOTIFICATION_MANAGER")
        
        # 创建新消息
        notification = Notification(self.parent_window)
        notification.show_message(message, actual_type, auto_close_time)
        notification.closed.connect(lambda: self._remove_notification(notification))
        
        # 添加到消息列表
        self.notifications.append(notification)
        
        # 立即更新所有消息位置
        self._update_positions_immediately()
        
        # 如果超过最大可见数，让最早的消息开始退出动画
        if len(self.notifications) > self.max_visible:
            debug_logger.output("notification.py", LogLevel.INFO, f"当前通知数量({len(self.notifications)})超过最大可见数({self.max_visible})，触发旧通知关闭", fold_code="NOTIFICATION_MANAGER")
            # 找到最早的消息（不在动画中的第一个消息）
            for old_notification in self.notifications:
                if not old_notification.is_appearing and not old_notification.is_disappearing:
                    old_notification.start_disappear_animation()
                    break
    
    def _remove_notification(self, notification):
        """
        移除指定消息
        
        Args:
            notification (Notification): 要移除的通知对象
        """
        if notification in self.notifications:
            debug_logger.output("notification.py", LogLevel.INFO, "NotificationManager 移除已关闭的通知", fold_code="NOTIFICATION_MANAGER")
            self.notifications.remove(notification)
            self._update_positions_immediately()
    
    def _update_positions_immediately(self):
        """立即更新所有消息位置（包括正在动画中的消息）"""
        if not self.parent_window:
            return
            
        # 获取父窗口的位置和大小
        parent_rect = self.parent_window.geometry()
        parent_width = parent_rect.width()
        
        # 计算渲染区宽度（选项卡栏右边界到窗口右边界）
        # 选项卡栏宽度为窗口宽度的10%
        tab_bar_width = int(parent_width * 0.1)
        render_area_width = parent_width - tab_bar_width
        
        # 计算 n 值（以渲染区为参考）
        n = render_area_width / 16
        
        debug_logger.output("notification.py", LogLevel.INFO, f"NotificationManager 正在批量更新 {len(self.notifications)} 个通知的位置", fold_code="NOTIFICATION_MANAGER")
        # 从最新的消息开始排列
        for i, notification in enumerate(reversed(self.notifications)):
            if i >= self.max_visible:
                break
                
            # 每个消息向上偏移
            offset = -i * int(NOTIFICATION_SPACING_N * n)
            notification.set_position_offset(offset)
    
    def update_all_positions_immediately(self):
        """立即更新所有消息框的位置（不带动画效果）"""
        if not self.parent_window:
            return
            
        # 获取父窗口的位置和大小
        parent_rect = self.parent_window.geometry()
        parent_width = parent_rect.width()
        
        # 计算渲染区宽度（选项卡栏右边界到窗口右边界）
        # 选项卡栏宽度为窗口宽度的10%
        tab_bar_width = int(parent_width * 0.1)
        render_area_width = parent_width - tab_bar_width
        
        # 计算 n 值（以渲染区为参考）
        n = render_area_width / 16
        
        debug_logger.output("notification.py", LogLevel.INFO, f"NotificationManager 正在立即批量更新 {len(self.notifications)} 个通知的位置（无动画）", fold_code="NOTIFICATION_MANAGER")
        # 更新所有消息框的位置
        for i, notification in enumerate(reversed(self.notifications)):
            if i >= self.max_visible:
                break
                
            # 每个消息向上偏移
            offset = -i * int(NOTIFICATION_SPACING_N * n)
            notification.base_offset = offset
            
            # 立即更新位置（不带动画）
            notification.update_position_immediately()
    
    def close_all(self):
        """关闭所有消息框"""
        debug_logger.output("notification.py", LogLevel.INFO, f"NotificationManager 正在关闭所有通知 (数量: {len(self.notifications)})", fold_code="NOTIFICATION_MANAGER")
        # 复制列表以避免在迭代时修改
        notifications_copy = self.notifications.copy()
        for notification in notifications_copy:
            notification.close()
        self.notifications.clear()
    
    def eventFilter(self, obj, event):
        """
        事件过滤器，用于监听父窗口移动和调整大小事件
        
        Args:
            obj: 事件对象
            event: 事件类型
            
        Returns:
            bool: 是否继续处理事件
        """
        from PyQt5.QtCore import QEvent
        if obj == self.parent_window and (event.type() == QEvent.Move or event.type() == QEvent.Resize):
            # 父窗口移动或调整大小时，立即更新所有消息位置（不带动画）
            self.update_all_positions_immediately()
        return super().eventFilter(obj, event)


class NotificationFactory:
    """
    通知工厂类
    
    提供创建不同类型通知的便捷方法。
    """
    
    @staticmethod
    def create_info_notification(manager, message, auto_close_time=DEFAULT_AUTO_CLOSE_TIME):
        """
        创建信息类型通知
        """
        debug_logger.output("notification.py", LogLevel.INFO, f"工厂创建信息通知: {message[:30]}...", fold_code="NOTIFICATION_MANAGER")
        manager.show_message(message, "info", auto_close_time)
    
    @staticmethod
    def create_warning_notification(manager, message, auto_close_time=DEFAULT_AUTO_CLOSE_TIME):
        """
        创建警告类型通知
        """
        debug_logger.output("notification.py", LogLevel.INFO, f"工厂创建警告通知: {message[:30]}...", fold_code="NOTIFICATION_MANAGER")
        manager.show_message(message, "warning", auto_close_time)
    
    @staticmethod
    def create_error_notification(manager, message, auto_close_time=DEFAULT_AUTO_CLOSE_TIME):
        """
        创建错误类型通知
        """
        debug_logger.output("notification.py", LogLevel.INFO, f"工厂创建错误通知: {message[:30]}...", fold_code="NOTIFICATION_MANAGER")
        manager.show_message(message, "error", auto_close_time)
    
    @staticmethod
    def create_short_notification(manager, message, message_type="info"):
        """
        创建短时通知（1.5秒）
        """
        debug_logger.output("notification.py", LogLevel.INFO, f"工厂创建短时通知: {message[:30]}...", fold_code="NOTIFICATION_MANAGER")
        manager.show_message(message, message_type, 1500)
    
    @staticmethod
    def create_long_notification(manager, message, message_type="info"):
        """
        创建长时通知（5秒）
        """
        debug_logger.output("notification.py", LogLevel.INFO, f"工厂创建长时通知: {message[:30]}...", fold_code="NOTIFICATION_MANAGER")
        manager.show_message(message, message_type, 5000)


# 向后兼容的便捷函数
def show_notification(manager, message, message_type="I", auto_close_time=DEFAULT_AUTO_CLOSE_TIME):
    """
    显示通知的便捷函数（向后兼容）
    """
    debug_logger.output("notification.py", LogLevel.INFO, f"调用向后兼容通知函数: {message[:30]}...", fold_code="NOTIFICATION_MANAGER")
    manager.show_message(message, message_type, auto_close_time)

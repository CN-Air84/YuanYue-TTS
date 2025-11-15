import sys
import os
from PyQt5.QtWidgets import QWidget, QLabel, QApplication
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect, QPoint, QObject
from PyQt5.QtGui import QFont, QMouseEvent

'''
本段代码几乎全部由DeepSeek编写，
感谢小鲸鱼 =）
'''

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
    """消息通知组件"""
    
    # 定义信号
    closed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
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
        """初始化UI"""
        # 修复窗口层级问题：使用Dialog标志，保持在应用程序窗口前但不全局置顶
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
        """初始化动画"""
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
        """显示消息
        
        Args:
            message: 消息内容
            message_type: 消息类型 - "info", "warning", "error"
            auto_close_time: 自动关闭时间(毫秒)
        """
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
        
        # 启动出现动画
        self._start_appear_animation()
        
        # 启动自动关闭定时器
        if auto_close_time > 0:
            self.close_timer.start(auto_close_time)
    
    def _get_notification_colors(self):
        """从个性化设置中获取通知颜色"""
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
            
            colors.update({
                "info": info_color,
                "warning": warning_color,
                "error": error_color
            })
        
        return colors
    
    def _get_start_position(self):
        """获取动画起始位置（窗口右侧外）"""
        if not self.parent_window:
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
        """获取动画结束位置（窗口右侧外）"""
        if not self.parent_window:
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
        """启动出现动画"""
        self.is_appearing = True
        
        # 设置动画参数
        self.appear_position_animation.setStartValue(self._get_start_position())
        self.appear_position_animation.setEndValue(self.target_position)
        
        # 启动位置动画
        self.appear_position_animation.start()
        
        # 启动透明度动画
        self._start_opacity_animation(0.0, 1.0, ANIMATION_DURATION_APPEAR, self._on_appear_finished)
    
    def _start_opacity_animation(self, start_opacity, end_opacity, duration, finish_callback):
        """启动透明度动画"""
        # 使用QPropertyAnimation进行透明度动画
        self.opacity_animation = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_animation.setDuration(duration)
        self.opacity_animation.setStartValue(start_opacity)
        self.opacity_animation.setEndValue(end_opacity)
        self.opacity_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.opacity_animation.finished.connect(finish_callback)
        self.opacity_animation.start()
    
    def _start_disappear_animation(self):
        """启动消失动画"""
        self.is_disappearing = True
        
        # 设置动画参数
        self.disappear_position_animation.setStartValue(self.pos())
        self.disappear_position_animation.setEndValue(self._get_end_position())
        
        # 启动位置动画
        self.disappear_position_animation.start()
        
        # 启动透明度动画
        self._start_opacity_animation(1.0, 0.0, ANIMATION_DURATION_DISAPPEAR, self._on_disappear_finished)
    
    def _start_move_animation(self, new_target_position):
        """启动上移动画"""
        if self.is_disappearing:
            return
            
        self.is_moving = True
        self.target_position = new_target_position
        
        # 设置动画参数
        self.move_position_animation.setStartValue(self.pos())
        self.move_position_animation.setEndValue(self.target_position)
        
        # 启动位置动画
        self.move_position_animation.start()
    
    def _on_appear_finished(self):
        """出现动画完成"""
        self.is_appearing = False
        # 修复透明度问题：确保动画结束后不透明度为100%
        self.setWindowOpacity(1.0)
        
    def _on_disappear_finished(self):
        """消失动画完成"""
        self.is_disappearing = False
        self.close()
        self.closed.emit()
    
    def _on_move_finished(self):
        """上移动画完成"""
        self.is_moving = False
    
    def _adjust_size_and_position(self):
        """调整大小和位置"""
        if not self.parent_window:
            return
            
        # 计算消息框大小（基于生成预览按钮的尺寸）
        preview_button = self.parent_window.generation_page.preview_control.preview_button
        if preview_button:
            button_width = preview_button.width()
            button_height = preview_button.height()
            
            # 计算消息框尺寸
            msg_width = int(button_width * NOTIFICATION_WIDTH_RATIO)
            msg_height = int(button_height * NOTIFICATION_HEIGHT_RATIO)
            
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
        
        # 计算 n 和 m 值
        n = parent_width / 16
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
        """设置位置偏移"""
        self.base_offset = offset
        
        # 计算新的目标位置
        if not self.parent_window:
            return
            
        parent_rect = self.parent_window.geometry()
        parent_x = parent_rect.x()
        parent_y = parent_rect.y()
        parent_width = parent_rect.width()
        parent_height = parent_rect.height()
        
        n = parent_width / 16
        m = parent_height / 16
        
        new_pos_x = parent_x + int(NOTIFICATION_POSITION_M * n)
        new_pos_y = parent_y + int(NOTIFICATION_POSITION_N * m) + offset
        
        new_target_position = QPoint(new_pos_x, new_pos_y)
        
        # 如果不在动画中，启动上移动画
        if not self.is_appearing and not self.is_disappearing and not self.is_moving:
            self._start_move_animation(new_target_position)
    
    def update_position_immediately(self):
        """立即更新位置（不带动画）"""
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
        """开始消失动画"""
        if not self.is_disappearing and not self.is_appearing:
            self._auto_close()
    
    def _auto_close(self):
        """自动关闭消息"""
        if self.is_disappearing:
            return
            
        self.close_timer.stop()
        self._start_disappear_animation()
    
    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """双击关闭消息"""
        if event.button() == Qt.LeftButton:
            self._auto_close()
    
    def closeEvent(self, event):
        """关闭事件"""
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
        event.accept()
    
    # ===== 点击穿透和手势滑动功能 =====
    
    def set_click_through_enabled(self, enabled):
        """设置点击穿透是否启用"""
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
    
    def keyPressEvent(self, event):
        """键盘按下事件"""
        if event.key() == Qt.Key_Control:
            self.ctrl_pressed = True
            self.update_click_through_state()
        super().keyPressEvent(event)
    
    def keyReleaseEvent(self, event):
        """键盘释放事件"""
        if event.key() == Qt.Key_Control:
            self.ctrl_pressed = False
            self.update_click_through_state()
        super().keyReleaseEvent(event)
    
    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下事件 - 用于手势滑动"""
        if event.button() == Qt.LeftButton and not self.ctrl_pressed:
            self.drag_start_pos = event.globalPos()
            self.drag_current_pos = event.globalPos()
            self.is_dragging = True
            self.original_position = self.pos()
            
            # 停止自动关闭计时器
            self.close_timer.stop()
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动事件 - 用于手势滑动"""
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
        """鼠标释放事件 - 用于手势滑动"""
        if event.button() == Qt.LeftButton and self.is_dragging and not self.ctrl_pressed:
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
                self._start_swipe_disappear_animation()
            else:
                # 不满足条件，回到原位
                self._start_return_animation()
                
                # 重新启动自动关闭计时器
                if self.auto_close_time > 0:
                    self.close_timer.start(self.auto_close_time)
    
    def _start_swipe_disappear_animation(self):
        """启动滑动消失动画"""
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
        """滑动消失动画完成"""
        self.close()
        self.closed.emit()
    
    def _start_return_animation(self):
        """启动返回原位的动画"""
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
    """消息管理器"""
    
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.notifications = []
        self.max_visible = MAX_VISIBLE_NOTIFICATIONS
        
        # 监听父窗口移动和调整大小事件
        if parent_window:
            parent_window.installEventFilter(self)
    
    def show_message(self, message, message_type="info", auto_close_time=DEFAULT_AUTO_CLOSE_TIME):
        """显示消息
        
        Args:
            message: 消息内容
            message_type: 消息类型 - "I"(info), "W"(warning), "E"(error)
            auto_close_time: 自动关闭时间(毫秒)
        """
        # 转换消息类型代码
        type_map = {
            "I": "info",
            "W": "warning", 
            "E": "error"
        }
        actual_type = type_map.get(message_type, "info")
        
        # 创建新消息
        notification = Notification(self.parent_window)
        notification.show_message(message, actual_type, auto_close_time)
        notification.closed.connect(lambda: self._remove_notification(notification))
        
        # 添加到消息列表
        self.notifications.append(notification)
        
        # 立即更新所有消息位置（包括正在进入动画的消息）
        self._update_positions_immediately()
        
        # 如果超过最大可见数，让最早的消息开始退出动画
        if len(self.notifications) > self.max_visible:
            # 找到最早的消息（不在动画中的第一个消息）
            for old_notification in self.notifications:
                if not old_notification.is_appearing and not old_notification.is_disappearing:
                    old_notification.start_disappear_animation()
                    break
    
    def _remove_notification(self, notification):
        """移除消息"""
        if notification in self.notifications:
            self.notifications.remove(notification)
            self._update_positions_immediately()
    
    def _update_positions_immediately(self):
        """立即更新所有消息位置（包括正在动画中的消息）"""
        if not self.parent_window:
            return
            
        # 获取父窗口的位置和大小
        parent_rect = self.parent_window.geometry()
        parent_width = parent_rect.width()
        
        # 计算 n 值
        n = parent_width / 16
        
        # 从最新的消息开始排列
        for i, notification in enumerate(reversed(self.notifications)):
            if i >= self.max_visible:
                break
                
            # 每个消息向上偏移
            offset = -i * int(NOTIFICATION_SPACING_N * n)
            notification.set_position_offset(offset)
    
    def update_all_positions_immediately(self):
        """立即更新所有消息框的位置（不带动画）"""
        if not self.parent_window:
            return
            
        # 获取父窗口的位置和大小
        parent_rect = self.parent_window.geometry()
        parent_width = parent_rect.width()
        
        # 计算 n 值
        n = parent_width / 16
        
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
        # 复制列表以避免在迭代时修改
        notifications_copy = self.notifications.copy()
        for notification in notifications_copy:
            notification.close()
        self.notifications.clear()
    
    def eventFilter(self, obj, event):
        """事件过滤器，用于监听父窗口移动和调整大小事件"""
        from PyQt5.QtCore import QEvent
        if obj == self.parent_window and (event.type() == QEvent.Move or event.type() == QEvent.Resize):
            # 父窗口移动或调整大小时，立即更新所有消息位置（不带动画）
            self.update_all_positions_immediately()
        return super().eventFilter(obj, event)


class NotificationFactory:
    """通知工厂类 - 提供创建通知的便捷方法"""
    
    @staticmethod
    def create_info_notification(manager, message, auto_close_time=DEFAULT_AUTO_CLOSE_TIME):
        """创建信息通知"""
        manager.show_message(message, "info", auto_close_time)
    
    @staticmethod
    def create_warning_notification(manager, message, auto_close_time=DEFAULT_AUTO_CLOSE_TIME):
        """创建警告通知"""
        manager.show_message(message, "warning", auto_close_time)
    
    @staticmethod
    def create_error_notification(manager, message, auto_close_time=DEFAULT_AUTO_CLOSE_TIME):
        """创建错误通知"""
        manager.show_message(message, "error", auto_close_time)
    
    @staticmethod
    def create_short_notification(manager, message, message_type="info"):
        """创建短时通知（1.5秒）"""
        manager.show_message(message, message_type, 1500)
    
    @staticmethod
    def create_long_notification(manager, message, message_type="info"):
        """创建长时通知（5秒）"""
        manager.show_message(message, message_type, 5000)


# 向后兼容的便捷函数
def show_notification(manager, message, message_type="I", auto_close_time=DEFAULT_AUTO_CLOSE_TIME):
    """显示通知的便捷函数（向后兼容）"""
    manager.show_message(message, message_type, auto_close_time)

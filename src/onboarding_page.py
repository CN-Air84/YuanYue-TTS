# coding=utf-8
import os
import sys
import math
import subprocess
import contextlib
import importlib
import io

def _optional_import(module_name: str, silence: bool = False):
    try:
        if silence:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                return importlib.import_module(module_name)
        return importlib.import_module(module_name)
    except Exception:
        return None


cv2 = None
pygame = None
from PyQt5.QtWidgets import (QWidget, QLabel, QVBoxLayout, QGraphicsOpacityEffect, 
                             QApplication, QFrame, QPushButton, QScrollArea, 
                             QDialog, QHBoxLayout, QSizePolicy, QLineEdit, QGraphicsDropShadowEffect,
                              QComboBox, QFontComboBox, QCheckBox, QSpinBox, QMessageBox)
from PyQt5.QtCore import (Qt, QTimer, QPropertyAnimation, QEasingCurve, 
                          pyqtSignal, QRect, QPoint, QSize, QParallelAnimationGroup,
                          QAbstractAnimation, QMimeData, QThread)
from PyQt5.QtGui import (QPainter, QColor, QPen, QFont, QBrush, QPainterPath, 
                         QMouseEvent, QPixmap, QCursor, QFontDatabase,
                         QDrag, QImage)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget

import requests
from misc_func import get_app_base_path, SettingsManager
from debug_logger import debug_logger, LogLevel
from resource_urls import get_resource_url

class LoadingSpinner(QWidget):
    """Windows 10 风格的圆环旋转加载动画"""
    completion_finished = pyqtSignal()  # 完成动画结束信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(64, 64)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_angle)
        self.timer.start(16)  # ~60 FPS
        
        self.dots = []
        for i in range(5):
            self.dots.append({'angle': -i * 20, 'speed': 0})
        
        # 完成动画相关状态
        self.is_completing = False  # 是否正在执行完成动画
        self.completion_stage = 0  # 0: 连线渐显, 1: 旋转两圈, 2: 变绿, 3: 圆环到勾的过渡, 4: 画勾
        self.line_opacity = 0.0  # 连线透明度
        self.extra_rotations = 0  # 额外旋转的圈数
        self.green_progress = 0.0  # 变绿进度 0-1
        self.morph_progress = 0.0  # 圆环变形到勾的进度 0-1
        self.checkmark_progress = 0.0  # 勾的绘制进度 0-1
        self.completion_start_angle = 0  # 开始完成动画时的角度

    def showEvent(self, event):
        self.timer.start(16)
        super().showEvent(event)

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def start_completion_animation(self):
        """开始完成动画"""
        self.is_completing = True
        self.completion_stage = 0
        self.line_opacity = 0.0
        self.extra_rotations = 0
        self.green_progress = 0.0
        self.morph_progress = 0.0
        self.checkmark_progress = 0.0
        self.completion_start_angle = self.angle
        debug_logger.output("onboarding_page.py", LogLevel.INFO, "开始完成动画", fold_code="ONBOARD_ANIM")

    def update_angle(self):
        if not self.is_completing:
            # 正常加载动画
            self.angle = (self.angle + 5) % 360
        else:
            # 完成动画逻辑
            if self.completion_stage == 0:
                # 阶段0: 连线渐显 (0.5秒)
                self.line_opacity += 0.016 / 0.5  # 16ms per frame
                if self.line_opacity >= 1.0:
                    self.line_opacity = 1.0
                    self.completion_stage = 1
                    debug_logger.output("onboarding_page.py", LogLevel.INFO, "连线渐显完成，开始旋转", fold_code="ONBOARD_ANIM")
                self.angle = (self.angle + 5) % 360
                
            elif self.completion_stage == 1:
                # 阶段1: 继续旋转两圈
                self.angle = (self.angle + 5) % 360
                if self.angle < (self.completion_start_angle + 10) % 360:
                    self.extra_rotations += 1
                    if self.extra_rotations >= 2:
                        self.completion_stage = 2
                        debug_logger.output("onboarding_page.py", LogLevel.INFO, "旋转两圈完成，开始变绿", fold_code="ONBOARD_ANIM")
                        
            elif self.completion_stage == 2:
                # 阶段2: 转到225度并变绿
                self.angle = (self.angle + 5) % 360
                # 当角度接近225度时开始变绿
                if 220 <= self.angle <= 230:
                    self.green_progress += 0.05
                    if self.green_progress >= 1.0:
                        self.green_progress = 1.0
                        self.completion_stage = 3
                        debug_logger.output("onboarding_page.py", LogLevel.INFO, "变绿完成，开始圆环变形", fold_code="ONBOARD_ANIM")
                        
            elif self.completion_stage == 3:
                # 阶段3: 圆环变形到勾的形状 (0.3秒)
                self.morph_progress += 0.016 / 0.3
                if self.morph_progress >= 1.0:
                    self.morph_progress = 1.0
                    self.completion_stage = 4
                    debug_logger.output("onboarding_page.py", LogLevel.INFO, "圆环变形完成，开始画勾", fold_code="ONBOARD_ANIM")
                        
            elif self.completion_stage == 4:
                # 阶段4: 画勾
                self.checkmark_progress += 0.02
                if self.checkmark_progress >= 1.0:
                    self.checkmark_progress = 1.0
                    self.timer.stop()
                    debug_logger.output("onboarding_page.py", LogLevel.INFO, "完成动画结束", fold_code="ONBOARD_ANIM")
                    QTimer.singleShot(500, self.completion_finished.emit)
                    
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        center_x = self.width() / 2
        center_y = self.height() / 2
        radius = 24  # 圆的半径，直径=48
        dot_radius = 3
        
        # 计算颜色（蓝色到绿色的渐变）
        if self.is_completing and self.green_progress > 0:
            # 从蓝色 (66, 133, 244) 渐变到绿色 (76, 175, 80)
            r = int(66 + (76 - 66) * self.green_progress)
            g = int(133 + (175 - 133) * self.green_progress)
            b = int(244 + (80 - 244) * self.green_progress)
            color = QColor(r, g, b)
        else:
            color = QColor(66, 133, 244)
        
        if self.completion_stage < 3:
            # 阶段0-2: 绘制旋转的圆环
            painter.translate(center_x, center_y)
            painter.rotate(self.angle)
            
            # 绘制点
            for i in range(5):
                painter.save()
                current_angle = -i * 25
                painter.rotate(current_angle)
                painter.translate(radius, 0)
                
                painter.setPen(Qt.NoPen)
                painter.setBrush(color)
                painter.drawEllipse(QPoint(0, 0), dot_radius, dot_radius)
                painter.restore()
            
            # 绘制连线（完成动画时）
            if self.is_completing and self.line_opacity > 0:
                painter.resetTransform()
                painter.translate(center_x, center_y)
                painter.rotate(self.angle)
                
                # 设置连线的透明度和颜色
                line_color = QColor(color)
                line_color.setAlphaF(self.line_opacity)
                # 连线宽度等于圆点直径 (dot_radius * 2 = 6)
                painter.setPen(QPen(line_color, dot_radius * 2))
                
                # 绘制连接所有点的曲线
                path = QPainterPath()
                for i in range(5):
                    angle_rad = math.radians(-i * 25)
                    x = radius * math.cos(angle_rad)
                    y = radius * math.sin(angle_rad)
                    if i == 0:
                        path.moveTo(x, y)
                    else:
                        path.lineTo(x, y)
                painter.drawPath(path)
                
        elif self.completion_stage == 3:
            # 阶段3: 圆环变形到勾的过渡动画
            painter.translate(center_x, center_y)
            
            # 勾的坐标（边界框为48x48，与圆直径相同）
            # 调整勾的坐标使其完全在48x48的边界框内
            # 勾的形状：左下(-16, 4) -> 中间(-4, 16) -> 右上(20, -20)
            # 缩放到48x48边界框内：乘以系数使最大范围为48
            scale = 0.6  # 缩放系数，使勾的视觉大小合适
            check_p1_x = -16 * scale  # 左下起点
            check_p1_y = 4 * scale
            check_p2_x = -4 * scale   # 中间转折点
            check_p2_y = 16 * scale
            check_p3_x = 20 * scale   # 右上终点
            check_p3_y = -20 * scale
            
            # 使用morph_progress进行插值
            t = self.morph_progress
            # 使用更平滑的缓动函数
            t_eased = t * t * t * (t * (t * 6 - 15) + 10)  # smootherstep
            
            # 绘制变形中的路径
            painter.setPen(QPen(color, dot_radius * 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.setBrush(Qt.NoBrush)
            
            # 创建圆形路径（作为起始形状）
            # 将圆周分成多个点进行采样
            num_points = 100  # 增加采样点数使变形更平滑
            
            path = QPainterPath()
            
            for i in range(num_points):
                # 圆上的参数 t_circle: 0 到 1
                t_circle = i / num_points
                angle_rad = t_circle * 2 * math.pi
                
                # 圆上的点
                circle_x = radius * math.cos(angle_rad)
                circle_y = radius * math.sin(angle_rad)
                
                # 将圆周参数映射到勾的路径参数
                # 勾有两段：第一段从p1到p2，第二段从p2到p3
                # 将圆周的0-0.3映射到第一段，0.3-1.0映射到第二段
                if t_circle < 0.3:
                    # 第一段：左下到中间
                    segment_t = t_circle / 0.3
                    target_x = check_p1_x + (check_p2_x - check_p1_x) * segment_t
                    target_y = check_p1_y + (check_p2_y - check_p1_y) * segment_t
                else:
                    # 第二段：中间到右上
                    segment_t = (t_circle - 0.3) / 0.7
                    target_x = check_p2_x + (check_p3_x - check_p2_x) * segment_t
                    target_y = check_p2_y + (check_p3_y - check_p2_y) * segment_t
                
                # 在圆和勾之间插值
                final_x = circle_x * (1 - t_eased) + target_x * t_eased
                final_y = circle_y * (1 - t_eased) + target_y * t_eased
                
                if i == 0:
                    path.moveTo(final_x, final_y)
                else:
                    path.lineTo(final_x, final_y)
            
            # 闭合路径（在变形早期阶段）
            if t_eased < 0.5:
                path.closeSubpath()
            
            painter.drawPath(path)
                
        else:
            # 阶段4: 绘制勾（带绘制进度）
            painter.translate(center_x, center_y)
            
            # 绘制勾的路径（边界框为48x48，与圆直径相同）
            check_color = QColor(76, 175, 80)  # 绿色
            painter.setPen(QPen(check_color, dot_radius * 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            
            # 使用与阶段3相同的勾坐标
            scale = 0.6
            p1_x = -16 * scale  # 左下起点
            p1_y = 4 * scale
            p2_x = -4 * scale   # 中间转折点
            p2_y = 16 * scale
            p3_x = 20 * scale   # 右上终点
            p3_y = -20 * scale
            
            path = QPainterPath()
            
            # 根据进度绘制勾
            if self.checkmark_progress <= 0.4:
                # 前40%绘制第一段（左下到中间）
                progress = self.checkmark_progress / 0.4
                current_x = p1_x + (p2_x - p1_x) * progress
                current_y = p1_y + (p2_y - p1_y) * progress
                path.moveTo(p1_x, p1_y)
                path.lineTo(current_x, current_y)
            else:
                # 第一段已完成
                path.moveTo(p1_x, p1_y)
                path.lineTo(p2_x, p2_y)
                
                # 后60%绘制第二段（中间到右上）
                progress = (self.checkmark_progress - 0.4) / 0.6
                current_x = p2_x + (p3_x - p2_x) * progress
                current_y = p2_y + (p3_y - p2_y) * progress
                path.lineTo(current_x, current_y)
            
            painter.drawPath(path)
        
        painter.end()

class DownloadWorker(QThread):
    download_finished = pyqtSignal(bool, str, str)
    
    def __init__(self, url, save_path, file_type, filename):
        super().__init__()
        self.url = url
        self.save_path = save_path
        self.file_type = file_type
        self.filename = filename
        self.is_stopped = False
    
    def run(self):
        try:
            debug_logger.output("onboarding_page.py", LogLevel.INFO, f"开始下载: {self.url}", fold_code="ONBOARD_DL")
            response = requests.get(self.url, timeout=60, stream=True)
            response.raise_for_status()
            
            with open(self.save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.is_stopped:
                        debug_logger.output("onboarding_page.py", LogLevel.INFO, f"下载 {self.filename} 已被停止", fold_code="ONBOARD_DL")
                        return
                    if chunk:
                        f.write(chunk)
            
            debug_logger.output("onboarding_page.py", LogLevel.INFO, f"文件 {self.filename} 下载完成", fold_code="ONBOARD_DL")
            self.download_finished.emit(True, self.file_type, self.filename)
        except Exception as e:
            if not self.is_stopped:
                debug_logger.output("onboarding_page.py", LogLevel.WARNING, f"文件 {self.filename} 下载失败: {e}", fold_code="ONBOARD_DL")
                self.download_finished.emit(False, self.file_type, self.filename)

    def stop(self):
        self.is_stopped = True

class LoadingScene(QWidget):
    finished = pyqtSignal()
    skip_requested = pyqtSignal(int) # New signal to request skipping to a specific scene
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.download_workers = []  # 存储所有下载线程
        self.completed_downloads = 0  # 已完成的下载数量
        self.total_downloads = 0  # 总下载数量
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        self.spinner = LoadingSpinner()
        layout.addWidget(self.spinner, 0, Qt.AlignCenter)
        
        self.label = QLabel("Loading...")
        self.label.setFont(QFont("Segoe UI", 12))
        self.label.setStyleSheet("color: #666;")
        layout.addWidget(self.label, 0, Qt.AlignCenter)
        
        # Skip Button
        self.skip_button = QPushButton("»", self)
        self.skip_button.setFixedSize(60, 60)
        self.skip_button.setCursor(Qt.PointingHandCursor)
        
        font = QFont("HarmonyOS Sans SC", 24, QFont.Bold)
        if not QFontDatabase().families().__contains__("HarmonyOS Sans SC"):
            font = QFont("微软雅黑", 24, QFont.Bold)
            debug_logger.output("onboarding_page.py", LogLevel.WARNING, "HarmonyOS Sans SC 字体未加载，使用 微软雅黑 作为替代", fold_code="ONBOARD_FONT")
        self.skip_button.setFont(font)
        
        self.skip_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; /* Green */
                color: white;
                border-radius: 30px; /* Circular */
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #66BB6A;
            }
        """)
        self.skip_button.clicked.connect(self.on_skip_button_clicked)
        
        # Position the skip button at the bottom right
        # This needs to be done after the layout is set up or in resizeEvent
        self.skip_button.move(self.width() - self.skip_button.width() - 20, 
                              self.height() - self.skip_button.height() - 20)
        
    def resizeEvent(self, event):
        # Reposition the skip button on resize
        self.skip_button.move(self.width() - self.skip_button.width() - 20, 
                              self.height() - self.skip_button.height() - 20)
        super().resizeEvent(event)

    def on_skip_button_clicked(self):
        debug_logger.output("onboarding_page.py", LogLevel.INFO, "跳过按钮被点击，停止所有下载任务", fold_code="ONBOARD_DL")
        
        # Stop all download workers
        for worker in self.download_workers:
            if worker.isRunning():
                worker.stop()
        
        # Wait for all threads to finish
        for worker in self.download_workers:
            worker.wait()
        
        # Clear the workers list
        self.download_workers.clear()
        
        # Emit signal to skip to LogoScene (index 2)
        self.skip_requested.emit(2) # Assuming LogoScene is at index 2
        
    def start_download(self):
        """开始并行下载所有资源"""
        cache_dir = os.path.join(get_app_base_path(), "cache")
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
            
        # 视频链接
        video_url = get_resource_url('release', 'intro_video')
        # 图标链接
        icon_url = get_resource_url('icon', 'icon')
        
        download_tasks = []  # 存储所有下载任务
        
        # 字体文件下载链接
        font_urls = {
            "OpenSymbol": get_resource_url('font', 'OpenSymbol'),
            "HarmonyOS Sans SC Black": get_resource_url('font', 'HarmonyOS_Sans_SC_Black'),
            "HarmonyOS Sans SC": get_resource_url('font', 'HarmonyOS_Sans_SC'),
            "HarmonyOS Sans SC Medium": get_resource_url('font', 'HarmonyOS_Sans_SC_Medium'),
            "HarmonyOS Sans SC Thin": get_resource_url('font', 'HarmonyOS_Sans_SC_Thin')
        }

        # 检查并添加需要下载的字体
        for font_name, font_url in font_urls.items():
            if not self.is_font_installed(font_name):
                if font_url:
                    font_filename = f"{font_name.replace(' ', '_')}.ttf"
                    download_tasks.append({
                        'url': font_url,
                        'filename': font_filename,
                        'type': 'font'
                    })
                else:
                    debug_logger.output("onboarding_page.py", LogLevel.WARNING, f"字体 {font_name} 未安装且下载链接为空", fold_code="ONBOARD_FONT")
            else:
                debug_logger.output("onboarding_page.py", LogLevel.INFO, f"字体 {font_name} 已安装", fold_code="ONBOARD_FONT")
        
        # 添加视频下载任务
        video_path = os.path.join(cache_dir, 'intro_1.mov')
        if video_url and not os.path.exists(video_path):
            download_tasks.append({
                'url': video_url,
                'filename': 'intro_1.mov',
                'type': 'video'
            })
            debug_logger.output("onboarding_page.py", LogLevel.INFO, "视频文件不存在，添加到下载队列", fold_code="ONBOARD_DL")
        elif os.path.exists(video_path):
            debug_logger.output("onboarding_page.py", LogLevel.INFO, "视频文件已存在，跳过下载", fold_code="ONBOARD_DL")
            
        # 添加图标下载任务
        icon_path = os.path.join(cache_dir, 'icon.png')
        if icon_url and not os.path.exists(icon_path):
            download_tasks.append({
                'url': icon_url,
                'filename': 'icon.png',
                'type': 'image'
            })
            debug_logger.output("onboarding_page.py", LogLevel.INFO, "图标文件不存在，添加到下载队列", fold_code="ONBOARD_DL")
        elif os.path.exists(icon_path):
            debug_logger.output("onboarding_page.py", LogLevel.INFO, "图标文件已存在，跳过下载", fold_code="ONBOARD_DL")
            
        if not download_tasks:
            debug_logger.output("onboarding_page.py", LogLevel.WARNING, "没有需要下载的资源，播放完成动画后进入下一场景", fold_code="ONBOARD_DL")
            self.label.setText("准备就绪！")
            # 即使没有下载任务，也播放完成动画
            self.spinner.start_completion_animation()
            self.spinner.completion_finished.connect(self.finished.emit)
            return

        # 设置总下载数量
        self.total_downloads = len(download_tasks)
        self.completed_downloads = 0
        
        debug_logger.output("onboarding_page.py", LogLevel.INFO, f"开始并行下载 {self.total_downloads} 个资源", fold_code="ONBOARD_DL")
        
        # 为每个任务创建并启动下载线程
        for task in download_tasks:
            save_path = os.path.join(cache_dir, task['filename'])
            
            worker = DownloadWorker(
                url=task['url'],
                save_path=save_path,
                file_type=task['type'],
                filename=task['filename']
            )
            worker.download_finished.connect(self.on_download_finished)
            self.download_workers.append(worker)
            worker.start()  # 立即启动线程
            
        # 更新加载提示
        self.label.setText(f"正在下载资源... (0/{self.total_downloads})")
        
    def is_font_installed(self, font_name):
        """检查系统是否已安装指定字体"""
        return QFontDatabase().families().__contains__(font_name)

    def on_download_finished(self, success, file_type, filename):
        """单个下载完成的回调"""
        if success:
            debug_logger.output("onboarding_page.py", LogLevel.INFO, f"文件 {filename} 下载完成", fold_code="ONBOARD_DL")
            
            # 如果是字体文件，立即安装
            if file_type == 'font':
                font_path = os.path.join(get_app_base_path(), "cache", filename)
                if os.path.exists(font_path):
                    font_id = QFontDatabase.addApplicationFont(font_path)
                    if font_id != -1:
                        debug_logger.output("onboarding_page.py", LogLevel.INFO, f"字体 {filename} 安装成功", fold_code="ONBOARD_FONT")
                    else:
                        debug_logger.output("onboarding_page.py", LogLevel.WARNING, f"字体 {filename} 安装失败", fold_code="ONBOARD_FONT")
                else:
                    debug_logger.output("onboarding_page.py", LogLevel.WARNING, f"下载的字体文件 {font_path} 不存在", fold_code="ONBOARD_FONT")
        else:
            debug_logger.output("onboarding_page.py", LogLevel.WARNING, f"文件 {filename} 下载失败", fold_code="ONBOARD_DL")
        
        # 更新已完成数量
        self.completed_downloads += 1
        self.label.setText(f"正在下载资源... ({self.completed_downloads}/{self.total_downloads})")
        
        # 检查是否所有下载都已完成
        if self.completed_downloads >= self.total_downloads:
            debug_logger.output("onboarding_page.py", LogLevel.INFO, "所有资源下载完成，开始完成动画", fold_code="ONBOARD_DL")
            self.label.setText("下载完成！")
            # 启动完成动画
            self.spinner.start_completion_animation()
            # 连接完成信号 - 只在动画完成后才切换场景
            self.spinner.completion_finished.connect(self.finished.emit)

class ControlOverlay(QFrame):
    """视频播放时的悬浮控制窗"""
    rate_changed = pyqtSignal(float)
    skip_clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(240)
        self.setFixedHeight(180) 
        self.setStyleSheet("""
            ControlOverlay {
                background-color: rgba(255, 255, 255, 0.95);
                border-radius: 12px;
                border: 1px solid #ddd;
            }
            QScrollBar:vertical {
                border: none;
                background: #f0f0f0;
                width: 8px;
                margin: 0px; 
            }
            QScrollBar::handle:vertical {
                background: #ccc;
                min-height: 20px;
                border-radius: 4px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("播放控制")
        title.setFont(QFont("微软雅黑", 12, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(title)
        
        desc = QLabel("长按屏幕已暂停播放。\n您可以调整播放速度或跳过介绍。")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; font-size: 12px;")
        content_layout.addWidget(desc)
        
        self.btn_2x = QPushButton("2.0x 倍速播放")
        self.btn_2x.setCheckable(True)
        self.btn_2x.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ddd;
                padding: 8px;
                border-radius: 6px;
            }
            QPushButton:checked {
                background-color: #4285f4;
                color: white;
                border-color: #4285f4;
            }
        """)
        self.btn_2x.clicked.connect(self.toggle_speed)
        content_layout.addWidget(self.btn_2x)
        
        content_layout.addSpacing(100)
        
        btn_skip = QPushButton("跳过动画")
        btn_skip.setCursor(Qt.PointingHandCursor)
        btn_skip.setStyleSheet("""
            QPushButton {
                background-color: white;
                border: 1px solid #ff4d4f;
                color: #ff4d4f;
                padding: 8px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #fff1f0;
            }
        """)
        btn_skip.clicked.connect(self.skip_clicked.emit)
        content_layout.addWidget(btn_skip)
        
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)
        
    def toggle_speed(self, checked):
        rate = 2.0 if checked else 1.0
        self.rate_changed.emit(rate)

class VideoScene(QWidget):
    finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #e5e8ef;")
        
        self.video_label = QLabel(self)
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: #e5e8ef;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.video_label)
        
        self.overlay = ControlOverlay(self)
        self.overlay.hide()
        self.overlay.rate_changed.connect(self.set_playback_rate)
        self.overlay.skip_clicked.connect(self.skip_video)
        
        self.long_press_timer = QTimer(self)
        self.long_press_timer.setInterval(500)
        self.long_press_timer.setSingleShot(True)
        self.long_press_timer.timeout.connect(self.on_long_press)
        
        self.is_pressing = False
        self.press_start_pos = None
        
        # OpenCV & Playback
        self.cap = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_frame)
        self.fps = 30
        self.is_paused = False
        self.playback_rate = 1.0

    def load_video(self):
        try:
            global cv2
            global pygame

            if cv2 is None:
                cv2 = _optional_import("cv2", silence=True)
            if pygame is None:
                pygame = _optional_import("pygame")

            if cv2 is None:
                debug_logger.output("onboarding_page.py", LogLevel.WARNING, "CV2 不可用，跳过开场视频", fold_code="ONBOARD_VIDEO")
                self.finished.emit()
                return

            video_path = os.path.join(get_app_base_path(), "cache", "intro_1.mov")
            video_path = os.path.abspath(video_path)
            
            if os.path.exists(video_path):
                debug_logger.output("onboarding_page.py", LogLevel.INFO, f"Loading video with CV2: {video_path}", fold_code="ONBOARD_VIDEO")
                
                # Audio (Pygame)
                try:
                    if pygame is not None:
                        pygame.mixer.init()
                        pygame.mixer.music.load(video_path)
                        pygame.mixer.music.play()
                        debug_logger.output("onboarding_page.py", LogLevel.INFO, "Audio started with Pygame", fold_code="ONBOARD_AUDIO")
                except Exception as e:
                    debug_logger.output("onboarding_page.py", LogLevel.WARNING, f"Pygame audio failed: {e}", fold_code="ONBOARD_AUDIO")
                
                # Video (CV2)
                self.cap = cv2.VideoCapture(video_path)
                if not self.cap.isOpened():
                    raise Exception("Could not open video file")
                    
                self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
                self.timer.start(int(1000 / self.fps))
                
            else:
                debug_logger.output("onboarding_page.py", LogLevel.WARNING, f"Video file not found at: {video_path}", fold_code="ONBOARD_VIDEO")
                self.finished.emit()
        except Exception as e:
            debug_logger.output("onboarding_page.py", LogLevel.ERROR, f"Error loading video: {str(e)}", fold_code="ONBOARD_VIDEO")
            self.finished.emit()

    def next_frame(self):
        if self.is_paused:
            return
            
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                # Convert BGR to RGB
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = frame.shape
                bytes_per_line = ch * w
                q_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
                
                # Scale to fit window
                scaled_pixmap = QPixmap.fromImage(q_img).scaled(
                    self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                self.video_label.setPixmap(scaled_pixmap)
            else:
                # End of video
                self.cap.release()
                self.timer.stop()
                try:
                    if pygame is not None:
                        pygame.mixer.music.stop()
                        pygame.mixer.quit()
                except:
                    pass
                self.finished.emit()

    def set_playback_rate(self, rate):
        self.playback_rate = rate
        if self.fps > 0:
            new_interval = int(1000 / (self.fps * rate))
            self.timer.start(new_interval)
        
        # Unpause if paused by overlay
        self.is_paused = False
        self.overlay.hide()
        
        # Audio handling for 2x
        # Pygame mixer music doesn't support speed change well. 
        # We might need to stop audio if speed is not 1.0 to avoid desync annoyance
        if rate != 1.0:
            if pygame is not None and pygame.mixer.get_init():
                pygame.mixer.music.pause()
        else:
            if pygame is not None and pygame.mixer.get_init():
                pygame.mixer.music.unpause()

    def skip_video(self):
        self.timer.stop()
        if self.cap:
            self.cap.release()
        try:
            if pygame is not None:
                pygame.mixer.music.stop()
                pygame.mixer.quit()
        except:
            pass
        self.finished.emit()

    def on_long_press(self):
        if self.is_pressing:
            self.is_paused = True
            if pygame is not None and pygame.mixer.get_init():
                pygame.mixer.music.pause()
                
            x = (self.width() - self.overlay.width()) // 2
            y = (self.height() - self.overlay.height()) // 2
            self.overlay.move(x, y)
            self.overlay.show()
            self.overlay.raise_()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.is_pressing = True
            self.press_start_pos = event.pos()
            self.long_press_timer.start()
            
            if self.overlay.isVisible() and not self.overlay.geometry().contains(event.pos()):
                self.overlay.hide()
                self.is_paused = False
                if pygame is not None and pygame.mixer.get_init():
                    if self.playback_rate == 1.0: # Only unpause audio if normal speed
                        pygame.mixer.music.unpause()
                    # If 2x, audio remains paused/muted

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.is_pressing = False
            self.long_press_timer.stop()

    def resizeEvent(self, event):
        if self.overlay.isVisible():
             x = (self.width() - self.overlay.width()) // 2
             y = (self.height() - self.overlay.height()) // 2
             self.overlay.move(x, y)
        super().resizeEvent(event)

class NavButton(QPushButton):
    def __init__(self, is_next=True, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 60)
        self.setCursor(Qt.PointingHandCursor)
        
        # 尝试加载 OpenSymbol 字体
        font = QFont("OpenSymbol", 24)
        if not QFontDatabase().families().__contains__("OpenSymbol"):
            font = QFont("Segoe UI", 24) # Fallback
            debug_logger.output("onboarding_page.py", LogLevel.WARNING, "OpenSymbol 字体未加载，使用 Segoe UI 作为替代", fold_code="ONBOARD_FONT")
        
        self.setFont(font)
        
        if is_next:
            self.setText("→")
            self.setStyleSheet("""
                QPushButton {
                    background-color: #4285f4;
                    color: white;
                    border-radius: 30px;
                    font-weight: bold;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #3367d6;
                }
            """)
        else:
            self.setText("←")
            self.setStyleSheet("""
                QPushButton {
                    background-color: #e0e0e0;
                    color: #555;
                    border-radius: 30px;
                    font-weight: bold;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #d0d0d0;
                }
            """)

class LogoScene(QWidget):
    next_clicked = pyqtSignal()
    prev_clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(30)
        
        # Icon
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(180, 180)
        self.icon_label.setAlignment(Qt.AlignCenter)
        
        # 初始显示灰色占位符
        self.icon_label.setStyleSheet("background-color: #e0e0e0;")
            
        layout.addStretch(1)
        layout.addWidget(self.icon_label, 0, Qt.AlignCenter)
        
        # Title
        title = QLabel("源悦TTS")
        title.setFont(QFont("微软雅黑", 36, QFont.Bold))
        title.setStyleSheet("color: #333;")
        self._logo_title = title
        layout.addWidget(title, 0, Qt.AlignCenter)
        
        # Nav Button Container
        nav_container = QWidget()
        nav_layout = QHBoxLayout(nav_container)
        nav_layout.setSpacing(20)
        
        self.btn_prev = NavButton(is_next=False)
        self.btn_prev.clicked.connect(self.prev_clicked.emit)
        
        self.btn_next = NavButton(is_next=True)
        self.btn_next.clicked.connect(self.next_clicked.emit)
        
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.btn_next)
        
        layout.addWidget(nav_container, 0, Qt.AlignCenter)
        layout.addStretch(1)
        
        # Version Info (Bottom Right)
        version_text = "版本号|发布日期"
        try:
            root_widget = self.window()
            if root_widget and hasattr(root_widget, "version_info"):
                v = root_widget.version_info
                version_text = f"{v.version()}|{v.update_date()}"
        except:
            pass
            
        ver_label = QLabel(version_text)
        ver_label.setStyleSheet("color: #888; font-size: 14px;")
        
        # Using a separate layout for bottom positioning
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        bottom_layout.addWidget(ver_label)
        bottom_layout.setContentsMargins(0, 0, 20, 20)
        
        # We need to overlay this bottom layout or add it to main layout
        # Since main layout is centered, adding it to main layout might not push it to very bottom
        # Let's add it to main layout but ensure stretches are correct
        layout.addLayout(bottom_layout)
        
    def showEvent(self, event):
        """场景显示时重新加载图标"""
        super().showEvent(event)
        self.load_icon()
        
    def load_icon(self):
        """加载图标图片"""
        icon_path = os.path.join(get_app_base_path(), "cache", "icon.png")
        
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                self.icon_label.setPixmap(pixmap.scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self.icon_label.setStyleSheet("")  # 清除灰色背景
                debug_logger.output("onboarding_page.py", LogLevel.INFO, "Logo 图标加载成功", fold_code="ONBOARD_LOGO")
            else:
                debug_logger.output("onboarding_page.py", LogLevel.WARNING, f"Logo 图标文件损坏: {icon_path}", fold_code="ONBOARD_LOGO")
        else:
            debug_logger.output("onboarding_page.py", LogLevel.WARNING, f"Logo 图标文件不存在: {icon_path}", fold_code="ONBOARD_LOGO")

class SettingsScene(QWidget):
    next_clicked = pyqtSignal()
    prev_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 40, 40, 20)
        main_layout.setSpacing(0)

        header_layout = QVBoxLayout()
        header_layout.setAlignment(Qt.AlignCenter)

        page_title = QLabel("AI 模型设置")
        page_title_font = QFont("HarmonyOS Sans SC Medium", 28, QFont.Bold)
        if not QFontDatabase().families().__contains__("HarmonyOS Sans SC Medium"):
            page_title_font = QFont("微软雅黑", 28, QFont.Bold)
        page_title.setFont(page_title_font)
        page_title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("请配置一个支持多模态输入的AI模型，以使用AI图像导入等功能。")
        subtitle_font = QFont("HarmonyOS Sans SC", 14)
        if not QFontDatabase().families().__contains__("HarmonyOS Sans SC"):
            subtitle_font = QFont("微软雅黑", 14)
        subtitle.setFont(subtitle_font)
        subtitle.setStyleSheet("color: #555;")
        subtitle.setAlignment(Qt.AlignCenter)

        header_layout.addWidget(page_title)
        header_layout.addSpacing(10)
        header_layout.addWidget(subtitle)

        main_layout.addLayout(header_layout)
        main_layout.addSpacing(20)

        from ai_settings_ui import AddModelWidget
        from ai_settings_store import CustomAIModelStore
        self.store = CustomAIModelStore()
        self.add_page = AddModelWidget(self.store)
        self.add_page.input_scene.setCurrentIndex(1)
        self.add_page.input_scene.hide()
        for lb in self.add_page.findChildren(QLabel):
            if lb.text() == "使用场景 *":
                lb.hide()
                break
        self.add_page.submit_btn.setText("保存并应用模型")
        self.add_page.submit_btn.clicked.disconnect()
        self.add_page.submit_btn.clicked.connect(self._on_save_and_apply)
        self.add_page.layout().setContentsMargins(0, 0, 0, 0)
        for sa in self.add_page.findChildren(QScrollArea):
            sa.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        main_layout.addWidget(self.add_page, 1)

        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(20)

        self.btn_prev = NavButton(is_next=False)
        self.btn_prev.clicked.connect(self.prev_clicked.emit)

        self.btn_next = NavButton(is_next=True)
        self.btn_next.clicked.connect(self.next_clicked.emit)

        nav_layout.addStretch()
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.btn_next)
        nav_layout.addStretch()

        main_layout.addSpacing(10)
        main_layout.addLayout(nav_layout)

    def _on_save_and_apply(self):
        data = self.add_page._validate()
        if not data:
            return
        data["scene"] = "vision"
        if self.add_page._editing_id:
            self.add_page.store.update_model(self.add_page._editing_id, data)
            model_id = self.add_page._editing_id
        else:
            m = self.add_page.store.add_model(data)
            model_id = m["id"]
        self.add_page.store.reload()
        self.add_page.store.set_active_id("vision", model_id)
        self.add_page._refresh_provider_candidates()
        self.add_page._clear_form()
        self._show_notification()

    def _show_notification(self):
        notification = QFrame(self)
        notification.setStyleSheet("""
            QFrame {
                background-color: #323232;
                border-radius: 12px;
            }
        """)
        notification.setFixedSize(420, 130)
        layout = QVBoxLayout(notification)
        layout.setContentsMargins(20, 15, 20, 15)

        ratio = max(0.65, min(1.5, (self.width() / 1080 + self.height() / 720) / 2))
        title_size = max(10, int(16 * ratio))
        hint_size = max(8, int(12 * ratio))

        title = QLabel("✓ 模型已保存并应用")
        title.setFont(QFont("微软雅黑", title_size, QFont.Bold))
        title.setStyleSheet("color: #4CAF50; border: none;")
        title.setAlignment(Qt.AlignCenter)
        hint = QLabel("如需修改，请前往 设置 → AI设置 → 选择模型\n长按卡片以编辑")
        hint.setFont(QFont("微软雅黑", hint_size))
        hint.setStyleSheet("color: #ccc; border: none;")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(hint)

        notification.move((self.width() - 420) // 2, (self.height() - 130) // 2)
        notification.show()
        notification.raise_()

        opacity = QGraphicsOpacityEffect(notification)
        notification.setGraphicsEffect(opacity)
        fade = QPropertyAnimation(opacity, b"opacity")
        fade.setDuration(400)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)

        def cleanup():
            notification.deleteLater()

        fade.finished.connect(cleanup)
        QTimer.singleShot(3500, fade.start)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "add_page") and hasattr(self.add_page, "apply_ui_metrics"):
            from ai_settings_ui import compute_ai_ui_metrics, DEFAULT_METRICS
            metrics = compute_ai_ui_metrics(self.width(), self.height(), "微软雅黑")
            self.add_page.apply_ui_metrics(metrics)
            self.add_page._metrics = dict(DEFAULT_METRICS)
            self.add_page._metrics.update(metrics)

class FontScene(QWidget):
    next_clicked = pyqtSignal()
    prev_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 40, 40, 20)
        main_layout.setSpacing(0)

        header_layout = QVBoxLayout()
        header_layout.setAlignment(Qt.AlignCenter)

        page_title = QLabel("基本设置")
        page_title_font = QFont("HarmonyOS Sans SC Medium", 28, QFont.Bold)
        if not QFontDatabase().families().__contains__("HarmonyOS Sans SC Medium"):
            page_title_font = QFont("微软雅黑", 28, QFont.Bold)
        page_title.setFont(page_title_font)
        page_title.setAlignment(Qt.AlignCenter)
        page_title.setStyleSheet("color: #333;")

        subtitle = QLabel("配置全局字体和在线资源源。")
        subtitle_font = QFont("HarmonyOS Sans SC", 14)
        if not QFontDatabase().families().__contains__("HarmonyOS Sans SC"):
            subtitle_font = QFont("微软雅黑", 14)
        subtitle.setFont(subtitle_font)
        subtitle.setStyleSheet("color: #555;")
        subtitle.setAlignment(Qt.AlignCenter)

        header_layout.addWidget(page_title)
        header_layout.addSpacing(10)
        header_layout.addWidget(subtitle)

        main_layout.addLayout(header_layout)
        main_layout.addSpacing(20)

        from custom_page import FontSettingsGroup
        self.font_group = FontSettingsGroup(self)
        self.font_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: none;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 0px;
                padding: 0px;
            }
            QLabel {
                background-color: transparent;
            }
        """)
        self.font_group.min_font_size.hide()
        self.font_group.max_font_size.hide()
        for lb in self.font_group.findChildren(QLabel):
            if lb.text() in ("最小字号:", "最大字号:"):
                lb.hide()
        base_font = QFont("微软雅黑", 22)
        for w in self.font_group.findChildren(QWidget):
            if isinstance(w, QFontComboBox):
                w.setObjectName("locked_font_combo")
                existing = w.styleSheet() or ""
                w.setStyleSheet(existing + "\nQFontComboBox#locked_font_combo { font-size: 12pt; }")
                continue
            w.setFont(base_font)
        main_layout.addWidget(self.font_group)

        # Resource source card
        resource_card = QFrame()
        resource_card.setStyleSheet("""
            QFrame {
                background-color: #e6e8eb;
                border-radius: 16px;
            }
        """)
        resource_layout = QHBoxLayout(resource_card)
        resource_layout.setContentsMargins(20, 16, 20, 16)
        resource_layout.setSpacing(15)

        resource_icon = QLabel("🌐")
        resource_icon.setFont(QFont("Segoe UI Emoji", 24))
        resource_icon.setStyleSheet("background: transparent; border: none;")

        resource_text_layout = QVBoxLayout()
        resource_text_layout.setSpacing(4)
        resource_title = QLabel("在线消息源")
        resource_title.setFont(QFont("微软雅黑", 14, QFont.Bold))
        resource_desc = QLabel("选择从何处获取应用所需的在线资源。")
        resource_desc.setFont(QFont("微软雅黑", 11))
        resource_desc.setStyleSheet("color: #666;")
        resource_text_layout.addWidget(resource_title)
        resource_text_layout.addWidget(resource_desc)

        self.resource_source_combo = QComboBox()
        self.resource_source_combo.addItem("GitHub（默认）", "github")
        self.resource_source_combo.addItem("Gitee（国内镜像）", "gitee")
        self.resource_source_combo.addItem("自定义源", "custom")
        self.resource_source_combo.setMinimumWidth(150)
        self.resource_source_combo.setStyleSheet("""
            QComboBox {
                background-color: white;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                padding: 2px 8px;
            }
            QComboBox:focus {
                border: 1px solid #4A90E2;
            }
            QComboBox::drop-down {
                width: 24px;
                border: none;
                border-left: 1px solid #E0E0E0;
            }
            QComboBox::drop-down:hover {
                background-color: #4A90E2;
            }
            QComboBox::down-arrow {
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #666;
            }
            QComboBox::drop-down:hover QComboBox::down-arrow {
                border-top-color: white;
            }
        """)

        from resource_urls import ResourceURLManager
        current_source = ResourceURLManager.get_current_source()
        idx = self.resource_source_combo.findData(current_source)
        if idx >= 0:
            self.resource_source_combo.setCurrentIndex(idx)

        self.resource_source_combo.currentIndexChanged.connect(self._on_resource_source_changed)

        resource_layout.addWidget(resource_icon)
        resource_layout.addLayout(resource_text_layout, 1)
        resource_layout.addWidget(self.resource_source_combo)

        main_layout.addSpacing(15)
        main_layout.addWidget(resource_card)
        main_layout.addStretch(1)

        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(20)

        self.btn_prev = NavButton(is_next=False)
        self.btn_prev.clicked.connect(self.prev_clicked.emit)

        self.btn_next = NavButton(is_next=True)
        self.btn_next.clicked.connect(self.next_clicked.emit)

        nav_layout.addStretch()
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.btn_next)
        nav_layout.addStretch()

        main_layout.addSpacing(10)
        main_layout.addLayout(nav_layout)

    def _on_resource_source_changed(self, index):
        source = self.resource_source_combo.itemData(index)
        if not source:
            return
        SettingsManager().Custom.set_value("resource_source", source)
        from resource_urls import ResourceURLManager
        ResourceURLManager.set_source(source)


class HotkeyScene(QWidget):
    next_clicked = pyqtSignal()
    prev_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 40, 40, 20)
        main_layout.setSpacing(0)

        header_layout = QVBoxLayout()
        header_layout.setAlignment(Qt.AlignCenter)

        page_title = QLabel("快捷键设置")
        page_title_font = QFont("HarmonyOS Sans SC Medium", 28, QFont.Bold)
        if not QFontDatabase().families().__contains__("HarmonyOS Sans SC Medium"):
            page_title_font = QFont("微软雅黑", 28, QFont.Bold)
        page_title.setFont(page_title_font)
        page_title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("自定义全局快捷键。")
        subtitle_font = QFont("HarmonyOS Sans SC", 14)
        if not QFontDatabase().families().__contains__("HarmonyOS Sans SC"):
            subtitle_font = QFont("微软雅黑", 14)
        subtitle.setFont(subtitle_font)
        subtitle.setStyleSheet("color: #555;")
        subtitle.setAlignment(Qt.AlignCenter)

        header_layout.addWidget(page_title)
        header_layout.addSpacing(10)
        header_layout.addWidget(subtitle)

        main_layout.addLayout(header_layout)
        main_layout.addSpacing(20)

        from custom_page import HotkeyControlWidget
        self.hotkey_group = HotkeyControlWidget(self)
        base_font = QFont("微软雅黑", 12)
        for w in [self.hotkey_group] + self.hotkey_group.findChildren(QWidget):
            w.setFont(base_font)
        main_layout.addWidget(self.hotkey_group, 1)

        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(20)

        self.btn_prev = NavButton(is_next=False)
        self.btn_prev.clicked.connect(self.prev_clicked.emit)

        self.btn_next = NavButton(is_next=True)
        self.btn_next.clicked.connect(self.next_clicked.emit)

        nav_layout.addStretch()
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.btn_next)
        nav_layout.addStretch()

        main_layout.addSpacing(10)
        main_layout.addLayout(nav_layout)


class DraggableButton(QPushButton):
    """可拖拽排序的按钮"""
    visibility_changed = pyqtSignal(str, bool) # Signal for visibility change
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setAcceptDrops(True)
        self.setAcceptDrops(True)
        self.setStyleSheet("""
            QPushButton {
                background-color: white;
                border: 2px solid #aaa;
                border-radius: 6px;
                color: #333;
            }
            QPushButton:hover {
                border-color: #4285f4;
            }
        """)
        
        # 尝试使用 HarmonyOS Sans SC 字体
        font = QFont("HarmonyOS Sans SC", 12)
        if not QFontDatabase().families().__contains__("HarmonyOS Sans SC"):
            font = QFont("微软雅黑", 12)
        self.setFont(font)
        
        self.drag_start_pos = None
        self.is_visible = True # New attribute to track visibility
        self.update_style() # Apply initial style based on visibility

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return
        if not self.drag_start_pos:
            return
        if (event.pos() - self.drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.text())
        drag.setMimeData(mime_data)
        
        # 拖拽时的预览图
        pixmap = QPixmap(self.size())
        self.render(pixmap)
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.pos())
        
        # 开始拖拽
        self.hide() # 拖拽时隐藏原按钮
        drop_action = drag.exec_(Qt.MoveAction)
        debug_logger.output("onboarding_page.py", LogLevel.DEBUG, f"Drag for {self.text()} finished with action: {drop_action}", fold_code="ONBOARD_DRAG")
        self.show() # 拖拽结束显示

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_visible = not self.is_visible
            self.update_style()
            self.visibility_changed.emit(self.text(), self.is_visible)
        super().mouseDoubleClickEvent(event)

    def update_style(self):
        if self.is_visible:
            self.setStyleSheet("""
                QPushButton {
                    background-color: white;
                    border: 2px solid #aaa;
                    border-radius: 6px;
                    color: #333;
                }
                QPushButton:hover {
                    border-color: #4285f4;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #f0f0f0; /* Grayed out background */
                    border: 2px solid #ccc;
                    border-radius: 6px;
                    color: #999; /* Lighter text color */
                    text-decoration: line-through; /* Strikethrough text */
                }
                QPushButton:hover {
                    border-color: #ccc;
                }
            """)

class FifthScene(QWidget):
    finished = pyqtSignal()
    prev_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 40, 40, 40)
        
        # Header
        header_layout = QVBoxLayout()
        header_layout.setAlignment(Qt.AlignCenter)
        
        page_title = QLabel("选项卡设置")
        page_title_font = QFont("HarmonyOS Sans SC Medium", 28, QFont.Bold)
        if not QFontDatabase().families().__contains__("HarmonyOS Sans SC Medium"):
            page_title_font = QFont("微软雅黑", 28, QFont.Bold)
            debug_logger.output("onboarding_page.py", LogLevel.WARNING, "HarmonyOS Sans SC Medium 字体未加载，使用 微软雅黑 作为替代", fold_code="ONBOARD_FONT")
        page_title.setFont(page_title_font)
        page_title.setAlignment(Qt.AlignCenter)
        
        subtitle = QLabel("配置左侧选项卡栏中的各个选项卡入口。")
        subtitle_font = QFont("HarmonyOS Sans SC", 14)
        if not QFontDatabase().families().__contains__("HarmonyOS Sans SC"):
            subtitle_font = QFont("微软雅黑", 14)
        subtitle.setFont(subtitle_font)
        subtitle.setStyleSheet("color: #555;")
        subtitle.setAlignment(Qt.AlignCenter)
        
        header_layout.addWidget(page_title)
        header_layout.addSpacing(10)
        header_layout.addWidget(subtitle)
        
        main_layout.addStretch(1)
        main_layout.addLayout(header_layout)
        main_layout.addSpacing(40)
        
        # Card 1: Initial Tab
        card1 = self.create_card()
        card1_layout = QHBoxLayout(card1)
        card1_layout.setContentsMargins(20, 20, 20, 20)
        card1_layout.setSpacing(20)
        
        icon1 = QLabel("🏠") # Emoji placeholder
        icon1.setFont(QFont("Segoe UI Emoji", 32))
        icon1.setStyleSheet("background: transparent; border: none;")
        
        text_layout1 = QVBoxLayout()
        title1 = QLabel("起始选项卡")
        title1_font = QFont("HarmonyOS Sans SC Medium", 12, QFont.Bold)
        if not QFontDatabase().families().__contains__("HarmonyOS Sans SC Medium"):
             title1_font = QFont("微软雅黑", 12, QFont.Bold)
        title1.setFont(title1_font)
        title1.setStyleSheet("background: transparent; border: none;")
        
        desc1 = QLabel("选择从程序启动时显示的选项卡。")
        desc1_font = QFont("HarmonyOS Sans SC", 10)
        if not QFontDatabase().families().__contains__("HarmonyOS Sans SC"):
             desc1_font = QFont("微软雅黑", 10)
        desc1.setFont(desc1_font)
        desc1.setStyleSheet("color: #666; background: transparent; border: none;")
        
        text_layout1.addWidget(title1)
        text_layout1.addWidget(desc1)
        
        self.combo_initial = QComboBox()
        self.combo_initial.addItems(["欢迎", "听写", "设置", "个性化", "杂项", "流媒体", "插件"
        ])
        self.combo_initial.setFixedWidth(120)
        self.combo_initial.setFont(desc1_font)
        self.combo_initial.setStyleSheet("""
            QComboBox {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 5px;
                background: white;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #666;
                width: 0;
                height: 0;
                margin-right: 5px;
            }
        """)
        
        card1_layout.addWidget(icon1)
        card1_layout.addLayout(text_layout1, 1)
        card1_layout.addWidget(self.combo_initial)
        
        main_layout.addWidget(card1)
        main_layout.addSpacing(20)
        
        # Card 2: Tab Sorting & Visibility
        card2 = self.create_card()
        card2_layout = QVBoxLayout(card2)
        card2_layout.setContentsMargins(20, 20, 20, 20)
        
        top_layout2 = QHBoxLayout()
        top_layout2.setSpacing(20)
        
        icon2 = QLabel("📝") # Emoji placeholder
        icon2.setFont(QFont("Segoe UI Emoji", 32))
        icon2.setStyleSheet("background: transparent; border: none;")
        
        text_layout2 = QVBoxLayout()
        title2 = QLabel("选项卡排序与可见性设置")
        title2.setFont(title1_font)
        title2.setStyleSheet("background: transparent; border: none;")
        
        desc2 = QLabel("设置选项卡的排列顺序并使选项卡隐藏/显示。\n您可以拖拽以修改排序，也可以双击以修改可见性。")
        desc2.setFont(desc1_font)
        desc2.setStyleSheet("color: #666; background: transparent; border: none;")
        
        text_layout2.addWidget(title2)
        text_layout2.addWidget(desc2)
        
        top_layout2.addWidget(icon2)
        top_layout2.addLayout(text_layout2, 1)
        
        card2_layout.addLayout(top_layout2)
        card2_layout.addSpacing(20)
        
        # Draggable Buttons Container
        self.buttons_container = QWidget()
        self.buttons_layout = QHBoxLayout(self.buttons_container)
        self.buttons_layout.setSpacing(10)
        self.buttons_layout.setContentsMargins(0, 0, 0, 0)
        
        tabs = ["欢迎", "听写", "设置", "个性化", "杂项", "流媒体", "插件"
        ]
        self.drag_buttons = []
        for tab_name in tabs:
            btn = DraggableButton(tab_name)
            self.buttons_layout.addWidget(btn)
            self.drag_buttons.append(btn)
        
        self.buttons_layout.addStretch() # 使按钮靠左排布
            
        # Enable dropping on the container
        self.buttons_container.setAcceptDrops(True)
        self.buttons_container.dragEnterEvent = self.container_dragEnterEvent
        self.buttons_container.dragMoveEvent = self.container_dragMoveEvent
        self.buttons_container.dropEvent = self.container_dropEvent
        
        card2_layout.addWidget(self.buttons_container)
        
        main_layout.addWidget(card2)
        main_layout.addSpacing(40)
        
        # Footer & Nav
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(20)
        
        self.btn_prev = NavButton(is_next=False)
        self.btn_prev.clicked.connect(self.prev_clicked.emit)
        
        self.btn_finish = NavButton(is_next=True)
        # Assuming "→" button finishes the tutorial as it's the last scene
        self.btn_finish.clicked.connect(self.save_and_next)
        
        nav_layout.addStretch()
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.btn_finish)
        nav_layout.addStretch()
        
        main_layout.addLayout(nav_layout)
        main_layout.addStretch(1)

    def create_card(self):
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #e6e8eb; 
                border-radius: 16px;
                border: 2px solid #888;
            }
        """)
        # Drop shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 30))
        shadow.setOffset(0, 4)
        card.setGraphicsEffect(shadow)
        return card

    def container_dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def container_dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
            
            # Simple visual feedback: find where it would be dropped
            pos = event.pos()
            # Calculate index based on x position
            # This is a simplified logic
            
    def container_dropEvent(self, event):
        if event.mimeData().hasText():
            text = event.mimeData().text()
            source_btn = None
            for btn in self.drag_buttons:
                if btn.text() == text: # Don't check isVisible() here, it's hidden during drag
                    source_btn = btn
                    break
            
            if source_btn:
                # Remove the source button from its current position in the list
                self.drag_buttons.remove(source_btn)

                # Find drop index based on mouse position relative to other buttons
                drop_x = event.pos().x()
                target_index = 0
                
                # Iterate through the current widgets in the layout to find the insertion point
                # We need to consider only DraggableButton widgets, ignoring the stretch
                current_x = 0
                for i, btn in enumerate(self.drag_buttons):
                    if drop_x > current_x + btn.width() / 2:
                        target_index = i + 1
                    current_x += btn.width() + self.buttons_layout.spacing()
                
                # Insert the source button at the calculated target index
                self.drag_buttons.insert(target_index, source_btn)
                
                # Clear the layout and re-add buttons in the new order
                # Remove all widgets and the stretch from the layout
                while self.buttons_layout.count():
                    item = self.buttons_layout.takeAt(0)
                    if item.widget():
                        item.widget().setParent(None)
                    else: # It's a stretch item
                        del item

                for btn in self.drag_buttons:
                    self.buttons_layout.addWidget(btn)
                
                self.buttons_layout.addStretch() # Re-add the stretch to keep buttons left-aligned
                
                source_btn.show() # Make sure the button is visible again
                
            event.acceptProposedAction()

    def save_and_next(self):
        # Save settings logic here
        # 1. Initial tab
        initial_tab_map = {
            "欢迎": "welcome",
            "听写": "dictation",
            "设置": "settings",
            "个性化": "personalization",
            "杂项": "misc",
            "流媒体": "streaming",
            "插件": "plugins",
        }
        selected_text = self.combo_initial.currentText()
        initial_tab = initial_tab_map.get(selected_text, "welcome")
        SettingsManager().Custom.set_value('initial_tab', initial_tab)
        
        # 2. Tab Order & Visibility
        tab_order_map = {
            "欢迎": "welcome",
            "听写": "dictation",
            "设置": "settings",
            "个性化": "personalization",
            "杂项": "misc",
            "流媒体": "streaming",
            "插件": "plugins",
        }
        
        ordered_tabs = []
        visible_tabs = []
        for btn in self.drag_buttons:
             key = tab_order_map.get(btn.text())
             if key:
                 ordered_tabs.append(key)
                 if btn.is_visible:
                     visible_tabs.append(key)
        
        SettingsManager().Custom.set_value('tab_order', ','.join(ordered_tabs))
        SettingsManager().Custom.set_value('tab_visibility', ','.join(visible_tabs))
        
        debug_logger.output("onboarding_page.py", LogLevel.INFO, "选项卡设置已保存", fold_code="ONBOARD_SAVE")
        self.finished.emit()

class ShortcutOption(QWidget):
    """快捷方式选项组件"""
    def __init__(self, title, subtitle, checked=False, parent=None):
        super().__init__(parent)
        self.setup_ui(title, subtitle, checked)

    def setup_ui(self, title, subtitle, checked):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)

        # Checkbox
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(checked)
        self.checkbox.setCursor(Qt.PointingHandCursor)
        # Style the checkbox to look modern
        self.checkbox.setStyleSheet("""
            QCheckBox::indicator {
                width: 24px;
                height: 24px;
                border: 2px solid #aaa;
                border-radius: 4px;
                background: white;
            }
            QCheckBox::indicator:checked {
                background-color: #4285f4;
                border-color: #4285f4;
                image: url(none); /* We will draw the checkmark or rely on default but colored */
            }
             QCheckBox::indicator:checked:hover {
                background-color: #3367d6;
                border-color: #3367d6;
            }
        """)
        # Note: Standard QCheckBox checkmark might be invisible if we just set background color.
        # Let's trust the default style with color tweaks or use a standard one.
        # Simpler style to ensure visibility:
        self.checkbox.setStyleSheet("""
             QCheckBox::indicator {
                width: 20px;
                height: 20px;
            }
        """)
        
        layout.addWidget(self.checkbox)

        # Text Layout
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        
        title_label = QLabel(title)
        title_font = QFont("HarmonyOS Sans SC", 12, QFont.Bold)
        if not QFontDatabase().families().__contains__("HarmonyOS Sans SC"):
            title_font = QFont("微软雅黑", 12, QFont.Bold)
        title_label.setFont(title_font)
        
        subtitle_label = QLabel(subtitle)
        subtitle_font = QFont("HarmonyOS Sans SC", 10)
        if not QFontDatabase().families().__contains__("HarmonyOS Sans SC"):
            subtitle_font = QFont("微软雅黑", 10)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setStyleSheet("color: #666;")
        
        text_layout.addWidget(title_label)
        text_layout.addWidget(subtitle_label)
        
        layout.addLayout(text_layout)
        layout.addStretch() # Push everything to left
        
    def is_checked(self):
        return self.checkbox.isChecked()

class SixthScene(QWidget):
    finished = pyqtSignal()
    prev_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 40, 40, 40)
        
        # Header
        header_layout = QVBoxLayout()
        header_layout.setAlignment(Qt.AlignCenter)
        
        page_title = QLabel("快捷方式")
        page_title_font = QFont("HarmonyOS Sans SC Black", 28, QFont.Bold)
        if not QFontDatabase().families().__contains__("HarmonyOS Sans SC Black"):
            page_title_font = QFont("微软雅黑", 28, QFont.Bold)
        page_title.setFont(page_title_font)
        page_title.setAlignment(Qt.AlignCenter)
        
        subtitle = QLabel("在其他位置添加快捷方式。")
        subtitle_font = QFont("HarmonyOS Sans SC", 14)
        if not QFontDatabase().families().__contains__("HarmonyOS Sans SC"):
            subtitle_font = QFont("微软雅黑", 14)
        subtitle.setFont(subtitle_font)
        subtitle.setStyleSheet("color: #555;")
        subtitle.setAlignment(Qt.AlignCenter)
        
        header_layout.addWidget(page_title)
        header_layout.addSpacing(10)
        header_layout.addWidget(subtitle)
        
        main_layout.addStretch(1)
        main_layout.addLayout(header_layout)
        main_layout.addSpacing(40)
        
        # Card
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #e6e8eb; 
                border-radius: 16px;
            }
        """)
        
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(40, 30, 40, 30)
        card_layout.setSpacing(40)
        
        # Option 1: Desktop
        self.opt_desktop = ShortcutOption(
            "创建桌面快捷方式", 
            "在桌面上添加软件快捷方式。",
            checked=True
        )
        
        # Option 2: Start Menu
        self.opt_start_menu = ShortcutOption(
            "创建开始菜单快捷方式", 
            "在开始菜单上添加软件快捷方式。",
            checked=False
        )
        
        card_layout.addWidget(self.opt_desktop)
        # Vertical divider line
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("background-color: #ccc; max-width: 1px;")
        card_layout.addWidget(line)
        card_layout.addWidget(self.opt_start_menu)
        
        main_layout.addWidget(card)
        main_layout.addSpacing(40)
        
        # Footer & Nav
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(20)
        
        self.btn_prev = NavButton(is_next=False)
        self.btn_prev.clicked.connect(self.prev_clicked.emit)
        
        self.btn_finish = NavButton(is_next=True)
        self.btn_finish.clicked.connect(self.save_and_finish)
        
        nav_layout.addStretch()
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.btn_finish)
        
        main_layout.addLayout(nav_layout)
        main_layout.addStretch(1)

    def save_and_finish(self):
        if getattr(sys, 'frozen', False): # Check if running as a bundled executable
            try:
                from win32com.client import Dispatch
                
                # Get the path of the executable
                app_path = sys.executable
                app_dir = os.path.dirname(app_path)
                
                shell = Dispatch('WScript.Shell')
                
                if self.opt_desktop.is_checked():
                    desktop_path = shell.SpecialFolders("Desktop")
                    shortcut_path = os.path.join(desktop_path, "源悦TTS.lnk")
                    shortcut = shell.CreateShortCut(shortcut_path)
                    shortcut.TargetPath = app_path
                    shortcut.WorkingDirectory = app_dir
                    shortcut.save()
                    debug_logger.output("onboarding_page.py", LogLevel.INFO, "已创建桌面快捷方式", fold_code="ONBOARD_SHORTCUT")
                    
                if self.opt_start_menu.is_checked():
                    start_menu_path = shell.SpecialFolders("Programs") # Start Menu/Programs
                    shortcut_path = os.path.join(start_menu_path, "源悦TTS.lnk")
                    shortcut = shell.CreateShortCut(shortcut_path)
                    shortcut.TargetPath = app_path
                    shortcut.WorkingDirectory = app_dir
                    shortcut.save()
                    debug_logger.output("onboarding_page.py", LogLevel.INFO, "已创建开始菜单快捷方式", fold_code="ONBOARD_SHORTCUT")
                    
            except Exception as e:
                debug_logger.output("onboarding_page.py", LogLevel.ERROR, f"创建快捷方式失败: {str(e)}", fold_code="ONBOARD_ERROR")
        else:
            # Running in development environment
            QMessageBox.information(self, "提示", "当前处于开发环境，不执行快捷方式创建操作。")
            debug_logger.output("onboarding_page.py", LogLevel.INFO, "开发环境，跳过快捷方式创建", fold_code="ONBOARD_SHORTCUT")
        
        self.finished.emit()

class FinalScene(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(40)
        
        # Top Icon (Simulated with QPushButton for clickability)
        self.btn_top_check = QPushButton("✔") 
        self.btn_top_check.setFixedSize(100, 100)
        self.btn_top_check.setCursor(Qt.PointingHandCursor)
        self.btn_top_check.setStyleSheet("""
            QPushButton {
                background-color: #00C853; 
                color: white;
                border-radius: 16px;
                font-size: 60px;
                border: none;
                font-family: "Segoe UI Emoji";
            }
            QPushButton:hover {
                background-color: #00E676;
            }
        """)
        self.btn_top_check.clicked.connect(self.finish_onboarding_and_quit)
        layout.addWidget(self.btn_top_check, 0, Qt.AlignCenter)

        # Title
        title = QLabel("完成")
        title_font = QFont("HarmonyOS Sans SC Black", 36, QFont.Bold)
        if not QFontDatabase().families().__contains__("HarmonyOS Sans SC Black"):
            title_font = QFont("微软雅黑", 36, QFont.Bold)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title, 0, Qt.AlignCenter)

        # Text Layout
        text_layout = QVBoxLayout()
        text_layout.setSpacing(20)
        
        desc = QLabel("恭喜！应用的基本设置已完成，感谢您选用源悦TTS。")
        desc_font = QFont("HarmonyOS Sans SC", 16)
        if not QFontDatabase().families().__contains__("HarmonyOS Sans SC"):
            desc_font = QFont("微软雅黑", 16)
        desc.setFont(desc_font)
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("color: #333;")
        
        instr = QLabel("点击【✅】以结束设置向导，请手动启动程序。")
        instr.setFont(desc_font)
        instr.setAlignment(Qt.AlignCenter)
        instr.setStyleSheet("color: #333;")
        
        text_layout.addWidget(desc)
        text_layout.addWidget(instr)
        layout.addLayout(text_layout)
        
        layout.addSpacing(40)

        # Bottom Button (Circular check)
        self.btn_bottom_check = QPushButton("✔")
        self.btn_bottom_check.setFixedSize(80, 80)
        self.btn_bottom_check.setCursor(Qt.PointingHandCursor)
        self.btn_bottom_check.setStyleSheet("""
            QPushButton {
                background-color: #00C853;
                color: white;
                border-radius: 40px;
                font-size: 40px;
                border: none;
                font-family: "Segoe UI Emoji";
            }
            QPushButton:hover {
                background-color: #00E676;
            }
        """)
        self.btn_bottom_check.clicked.connect(self.finish_onboarding_and_quit)
        layout.addWidget(self.btn_bottom_check, 0, Qt.AlignCenter)
        
        layout.addStretch(1)

    def finish_onboarding_and_quit(self):
        SettingsManager().set_is_first_run(False)

        dialog = QMessageBox(self)
        dialog.setWindowTitle("在线资源加载")
        dialog.setText("正在下载语音列表…")
        dialog.setStandardButtons(QMessageBox.NoButton)
        dialog.setModal(True)
        dialog.show()
        QApplication.processEvents()

        voicelist_path = os.path.join(get_app_base_path(), 'cache', 'voicelist.txt')
        url = get_resource_url('release', 'voicelist')

        if url and not os.path.exists(voicelist_path):
            try:
                from requests import get as http_get
                resp = http_get(url, timeout=60, stream=True)
                resp.raise_for_status()
                os.makedirs(os.path.dirname(voicelist_path), exist_ok=True)
                with open(voicelist_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                debug_logger.output("onboarding_page.py", LogLevel.INFO, "语音列表下载完成", fold_code="ONBOARD_DL")
            except Exception as e:
                debug_logger.output("onboarding_page.py", LogLevel.WARNING, f"语音列表下载失败: {e}", fold_code="ONBOARD_DL")

        dialog.accept()
        debug_logger.output("onboarding_page.py", LogLevel.INFO, "设置向导完成，应用程序退出", fold_code="ONBOARD_FINISH")
        QApplication.quit()

class OnboardingPage(QWidget):
    tutorial_finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scenes = []
        self.current_index = -1
        self.is_animating = False
        
        # 1. Loading Scene
        self.loading_scene = LoadingScene(self)
        self.loading_scene.finished.connect(self.next_scene)
        self.loading_scene.skip_requested.connect(self.jump_to_scene) # Connect skip signal
        self.scenes.append(self.loading_scene)
        
        # 2. Video Scene
        self.video_scene = VideoScene(self)
        self.video_scene.finished.connect(self.next_scene)
        self.scenes.append(self.video_scene)
        
        # 3. Logo Scene
        self.logo_scene = LogoScene(self)
        self.logo_scene.next_clicked.connect(self.next_scene)
        self.logo_scene.prev_clicked.connect(self.prev_scene)
        self.scenes.append(self.logo_scene)
        
        # 4. AI Model Settings
        self.settings_scene = SettingsScene(self)
        self.settings_scene.next_clicked.connect(self.next_scene)
        self.settings_scene.prev_clicked.connect(self.prev_scene)
        self.scenes.append(self.settings_scene)
        
        # 5. Font Settings
        self.font_scene = FontScene(self)
        self.font_scene.next_clicked.connect(self.next_scene)
        self.font_scene.prev_clicked.connect(self.prev_scene)
        self.scenes.append(self.font_scene)
        
        # 6. Hotkey Settings
        self.hotkey_scene = HotkeyScene(self)
        self.hotkey_scene.next_clicked.connect(self.next_scene)
        self.hotkey_scene.prev_clicked.connect(self.prev_scene)
        self.scenes.append(self.hotkey_scene)
        
        # 7. Fifth Scene (Tab Settings)
        self.fifth_scene = FifthScene(self)
        self.fifth_scene.finished.connect(self.next_scene) 
        self.fifth_scene.prev_clicked.connect(self.prev_scene)
        self.scenes.append(self.fifth_scene)
        
        # 8. Sixth Scene (Shortcuts)
        self.sixth_scene = SixthScene(self)
        self.sixth_scene.finished.connect(self.next_scene) # Changed from finish_tutorial to next_scene
        self.sixth_scene.prev_clicked.connect(self.prev_scene)
        self.scenes.append(self.sixth_scene)
        
        # 9. Final Scene
        self.final_scene = FinalScene(self)
        self.scenes.append(self.final_scene)
        
        # Init
        for scene in self.scenes:
            scene.hide()
            
        self.scenes[0].show()
        self.current_index = 0
        
        # Start download
        QTimer.singleShot(500, self.loading_scene.start_download)

    def next_scene(self):
        if self.is_animating: return
        next_idx = self.current_index + 1
        if next_idx >= len(self.scenes):
            self.finish_tutorial()
            return
        self.transition_to(next_idx, direction="forward")
        
    def prev_scene(self):
        if self.is_animating: return
        prev_idx = self.current_index - 1
        if prev_idx < 0: return # Should not happen if logic is correct
        
        # Special case: If going back to video scene, reload video
        if isinstance(self.scenes[prev_idx], VideoScene):
            self.scenes[prev_idx].load_video()
            
        self.transition_to(prev_idx, direction="backward")

    def jump_to_scene(self, target_index):
        if self.is_animating: return
        if target_index < 0 or target_index >= len(self.scenes):
            debug_logger.output("onboarding_page.py", LogLevel.WARNING, f"尝试跳转到无效场景索引: {target_index}", fold_code="ONBOARD_SKIP")
            return
        
        debug_logger.output("onboarding_page.py", LogLevel.INFO, f"跳过至场景索引: {target_index}", fold_code="ONBOARD_SKIP")
        
        # Stop video if currently in video scene
        if isinstance(self.scenes[self.current_index], VideoScene):
            self.scenes[self.current_index].skip_video()
            
        self.transition_to(target_index, direction="forward")

    def transition_to(self, next_idx, direction="forward"):
        self.is_animating = True
        current_scene = self.scenes[self.current_index]
        next_scene = self.scenes[next_idx]
        
        next_scene.show()
        next_scene.raise_()
        
        duration = 750
        width = self.width()
        
        self.anim_group = QParallelAnimationGroup()
        
        # Config based on direction
        if direction == "forward":
            start_pos_curr = QPoint(0, 0)
            end_pos_curr = QPoint(-width, 0)
            start_pos_next = QPoint(width, 0)
            end_pos_next = QPoint(0, 0)
        else: # backward
            start_pos_curr = QPoint(0, 0)
            end_pos_curr = QPoint(width, 0)
            start_pos_next = QPoint(-width, 0)
            end_pos_next = QPoint(0, 0)
            
        # Opacity (current)
        self.eff_curr = QGraphicsOpacityEffect(current_scene)
        current_scene.setGraphicsEffect(self.eff_curr)
        anim_opacity_curr = QPropertyAnimation(self.eff_curr, b"opacity")
        anim_opacity_curr.setDuration(duration)
        anim_opacity_curr.setStartValue(1.0)
        anim_opacity_curr.setEndValue(0.0)
        anim_opacity_curr.setEasingCurve(QEasingCurve.InOutQuad)
        self.anim_group.addAnimation(anim_opacity_curr)
        
        # Position (current)
        anim_pos_curr = QPropertyAnimation(current_scene, b"pos")
        anim_pos_curr.setDuration(duration)
        anim_pos_curr.setStartValue(start_pos_curr)
        anim_pos_curr.setEndValue(end_pos_curr)
        anim_pos_curr.setEasingCurve(QEasingCurve.InOutQuad)
        self.anim_group.addAnimation(anim_pos_curr)
        
        # Opacity (next)
        self.eff_next = QGraphicsOpacityEffect(next_scene)
        next_scene.setGraphicsEffect(self.eff_next)
        anim_opacity_next = QPropertyAnimation(self.eff_next, b"opacity")
        anim_opacity_next.setDuration(duration)
        anim_opacity_next.setStartValue(0.0)
        anim_opacity_next.setEndValue(1.0)
        anim_opacity_next.setEasingCurve(QEasingCurve.InOutQuad)
        self.anim_group.addAnimation(anim_opacity_next)
        
        # Position (next)
        anim_pos_next = QPropertyAnimation(next_scene, b"pos")
        anim_pos_next.setDuration(duration)
        anim_pos_next.setStartValue(start_pos_next)
        anim_pos_next.setEndValue(end_pos_next)
        anim_pos_next.setEasingCurve(QEasingCurve.InOutQuad)
        self.anim_group.addAnimation(anim_pos_next)
        
        self.anim_group.finished.connect(lambda: self.on_transition_finished(next_idx))
        self.anim_group.start()

    def on_transition_finished(self, next_idx):
        self.is_animating = False
        prev_scene = self.scenes[self.current_index]
        prev_scene.hide()
        prev_scene.move(0, 0)
        prev_scene.setGraphicsEffect(None)
        
        next_scene = self.scenes[next_idx]
        next_scene.setGraphicsEffect(None)
        
        self.current_index = next_idx
        
        if isinstance(next_scene, VideoScene):
            next_scene.load_video()

    def finish_tutorial(self):
        debug_logger.output("onboarding_page.py", LogLevel.INFO, "新手引导结束", fold_code="ONBOARD_FINISH")
        SettingsManager().set_is_first_run(False)
        self.tutorial_finished.emit()

    def _apply_font_scale(self):
        ratio = max(0.65, min(1.5, (self.width() / 1080 + self.height() / 720) / 2))

        for scene in self.scenes:
            if isinstance(scene, LogoScene):
                targets = [scene] + scene.findChildren((QLabel, QPushButton))
            else:
                targets = [scene] + scene.findChildren((QLabel, QPushButton, QComboBox, QLineEdit, QCheckBox, QSpinBox))

            for w in targets:
                if isinstance(scene, LogoScene) and w is getattr(scene, '_logo_title', None):
                    continue
                if w.objectName() == "locked_font_combo":
                    continue
                orig = getattr(w, '_orig_ps', None)
                if orig is None:
                    ps = w.font().pointSize()
                    if ps <= 0:
                        continue
                    w._orig_ps = ps
                    orig = ps
                n = max(8, int(orig * ratio))
                if n != w.font().pointSize():
                    f = w.font()
                    f.setPointSize(n)
                    w.setFont(f)

    def resizeEvent(self, event):
        self.setMinimumSize(0, 0)
        for scene in self.scenes:
            scene.resize(self.size())
        super().resizeEvent(event)
        self._apply_font_scale()

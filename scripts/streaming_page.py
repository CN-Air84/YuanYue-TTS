# coding=utf-8
import os
import sys
import random
import json
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, 
                             QListWidget, QListWidgetItem, QLabel, QScrollArea, QFrame,
                             QInputDialog, QMessageBox, QMenu, QSlider, QSizePolicy)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt5.QtGui import QFont, QIcon
from debug_logger import debug_logger, LogLevel
from music_NCM import MusicSubsystem, MusicTrack
from misc_func import SettingsManager
from shared_memory_manager import get_shared_memory_manager

class SongItemWidget(QFrame):
    """
    单个歌曲条目组件。
    包含四个独立按钮：播放、歌曲名、作者、时长。
    """
    play_clicked = pyqtSignal(int)    # 发送点击的序号
    artist_clicked = pyqtSignal(str) # 发送点击的作者名
    add_to_queue_requested = pyqtSignal(object) # 请求添加到播放列表
    delete_requested = pyqtSignal(int) # 请求删除歌曲 (1-based index)

    def __init__(self, index, track: MusicTrack, is_queue=False, parent=None):
        super().__init__(parent)
        self.index = index
        self.track = track
        self.is_queue = is_queue
        self.init_ui()

    def init_ui(self):
        # 获取用户设置的字体
        settings_manager = SettingsManager()
        font_family = settings_manager.get_Custom_value("global_font", "微软雅黑")

        self.setFixedHeight(70) 
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: transparent;
                margin: 0px;
                font-family: "{font_family}";
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(10)

        # 1.5倍缩放的基础样式
        SONG_BTN_STYLE = """
            QPushButton {
                background-color: rgb(255,255,255);
                font: 16pt "HarmonyOS Sans";
                border-radius: 8px;
                border: 1px solid gray;
            }
            QPushButton:hover { background-color: #f0f0f0; }
            QPushButton:pressed { background-color: #e0e0e0; }
        """

        # 1. 功能按钮 (搜索时为+，加到列表；列表内为-，从列表移除)
        if self.is_queue:
            self.action_btn = QPushButton("-")
            self.action_btn.setToolTip("从列表中移除")
            btn_color_style = "background-color: rgb(255, 120, 120); color: white; border: 1px solid #CC0000;"
        else:
            self.action_btn = QPushButton("+")
            self.action_btn.setToolTip("添加到播放列表")
            btn_color_style = "background-color: white; color: #333333; border: 1px solid gray;"

        self.action_btn.setObjectName("action_btn")
        self.action_btn.setFixedSize(45, 45)
        self.action_btn.setCursor(Qt.PointingHandCursor)
        self.action_btn.setStyleSheet(SONG_BTN_STYLE + f"QPushButton {{ font-size: 22px; font-weight: bold; {btn_color_style} }}")
        
        if self.is_queue:
            self.action_btn.clicked.connect(lambda: self.delete_requested.emit(self.index))
        else:
            self.action_btn.clicked.connect(lambda: self.add_to_queue_requested.emit(self.track))
        
        layout.addWidget(self.action_btn)

        # 2. 歌曲名称按钮 (2倍: 14*2=28px)
        name_frame = QFrame()
        name_frame.setFixedHeight(50)
        name_frame.setStyleSheet("background-color: white; border-radius: 8px; border: 1px solid gray;")
        name_frame.setCursor(Qt.PointingHandCursor)
        name_layout = QHBoxLayout(name_frame)
        name_layout.setContentsMargins(15, 0, 15, 0)
        self.name_label = ElidedLabel(self.track.name)
        self.name_label.setToolTip(self.track.name)
        self.name_label.setStyleSheet(f"font-weight: bold; font-size: 18px; background: transparent; font-family: '{font_family}'; border: none;")
        self.name_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        name_layout.addWidget(self.name_label)
        name_frame.mousePressEvent = lambda e: self.play_clicked.emit(self.index)
        layout.addWidget(name_frame, 4)

        # 3. 歌曲作者按钮 (2倍: 13*2=26px)
        artist_frame = QFrame()
        artist_frame.setFixedHeight(50)
        artist_frame.setStyleSheet("background-color: white; border-radius: 8px; border: 1px solid gray;")
        artist_frame.setCursor(Qt.PointingHandCursor)
        artist_layout = QHBoxLayout(artist_frame)
        artist_layout.setContentsMargins(15, 0, 15, 0)
        self.artist_label = ElidedLabel(self.track.artist)
        self.artist_label.setToolTip(self.track.artist)
        self.artist_label.setStyleSheet(f"font-size: 16px; color: #555555; background: transparent; font-family: '{font_family}'; border: none;")
        self.artist_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        artist_layout.addWidget(self.artist_label)
        artist_frame.mousePressEvent = lambda e: self.artist_clicked.emit(self.track.artist)
        layout.addWidget(artist_frame, 2)

        # 4. 歌曲时长按钮
        duration_sec = self.track.duration // 1000
        duration_str = f"{duration_sec // 60:02d}:{duration_sec % 60:02d}"
        self.duration_btn = QPushButton(duration_str)
        self.duration_btn.setObjectName("duration_btn")
        self.duration_btn.setFixedWidth(80) 
        self.duration_btn.setFixedHeight(50)
        self.duration_btn.setCheckable(False)
        self.duration_btn.setStyleSheet(SONG_BTN_STYLE + "QPushButton { font-size: 13px; color: #555555; }")
        layout.addWidget(self.duration_btn)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)


    def _show_context_menu(self, pos):
        """显示右键菜单"""
        menu = QMenu(self)
        add_action = menu.addAction("添加到播放列表")
        delete_action = menu.addAction("从列表中移除")
        
        action = menu.exec_(self.mapToGlobal(pos))
        
        if action == add_action:
            self.add_to_queue_requested.emit(self.track)
        elif action == delete_action:
            self.delete_requested.emit(self.index)


class VolumePopup(QFrame):
    """音量调节悬浮窗"""
    volumeChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 获取用户设置的字体
        settings_manager = SettingsManager()
        self.font_family = settings_manager.get_Custom_value("global_font", "微软雅黑")
        
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setFixedSize(50, 250) # 拉长高度，提供更精准的控制体验
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #F0F0F0;
                border: 1px solid #CCCCCC;
                border-radius: 8px;
                font-family: "{self.font_family}";
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 10) # 减小边距，给滑动条更多空间
        layout.setSpacing(5)

        # 百分比显示
        self.percent_label = QLabel("100%")
        self.percent_label.setFixedHeight(20) # 固定标签高度
        self.percent_label.setAlignment(Qt.AlignCenter)
        self.percent_label.setStyleSheet(f"border: none; font-size: 11px; color: #333333; font-family: '{self.font_family}';")
        layout.addWidget(self.percent_label)

        # 垂直音量条
        self.slider = QSlider(Qt.Vertical)
        self.slider.setRange(0, 100)
        self.slider.setValue(100)
        self.slider.setCursor(Qt.PointingHandCursor)
        self.slider.setStyleSheet("""
            QSlider::groove:vertical {
                background: white;
                width: 6px;
                border-radius: 3px;
            }
            QSlider::handle:vertical {
                background: #555555;
                height: 14px;
                width: 14px;
                margin: 0 -4px;
                border-radius: 7px;
            }
        """)
        self.slider.valueChanged.connect(self._on_value_changed)
        layout.addWidget(self.slider, 1, Qt.AlignHCenter) # 给予拉伸因子1并保持水平居中

    def _on_value_changed(self, val):
        self.percent_label.setText(f"{val}%")
        self.volumeChanged.emit(val)

    def set_value(self, val):
        self.slider.setValue(val)
        self.percent_label.setText(f"{val}%")


class VolumeButton(QPushButton):
    """支持长按的按钮基类"""
    longPressed = pyqtSignal()

    def __init__(self, text, parent=None, interval=800):
        super().__init__(text, parent)
        self.long_press_timer = QTimer(self)
        self.long_press_timer.setSingleShot(True)
        self.long_press_timer.setInterval(interval)
        self.long_press_timer.timeout.connect(self._on_long_press)
        self._is_long_press = False

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_long_press = False
            self.long_press_timer.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.long_press_timer.stop()
        if self._is_long_press:
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _on_long_press(self):
        self._is_long_press = True
        self.longPressed.emit()



class ScrollingLabel(QLabel):
    """
    实现文本自动横向滚动的 QLabel。
    当文本宽度超过控件宽度时，文本将自动滚动。
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setContentsMargins(0, 0, 0, 0)
        self.original_text = ""
        self.current_offset = 0
        self.scroll_timer = QTimer(self)
        self.scroll_timer.setInterval(400) # 减慢到原先的 0.25 倍 (100 -> 400)
        self.scroll_timer.timeout.connect(self._scroll_text)
        self.font_metrics = None

    def set_scrolling_text(self, text: str):
        """设置要滚动的文本"""
        self.original_text = text
        self.current_offset = 0
        self.update_text_display()

    def update_text_display(self):
        """根据当前偏移量更新显示的文本"""
        if not self.font_metrics:
            self.font_metrics = self.fontMetrics()

        widget_width = self.width() - self.contentsMargins().left() - self.contentsMargins().right()
        text_width = self.font_metrics.width(self.original_text)

        if text_width <= widget_width:
            # 文本未超出，停止滚动，显示完整文本
            super().setText(self.original_text)
            self.scroll_timer.stop()
        else:
            # 文本超出，开始滚动
            if not self.scroll_timer.isActive():
                self.scroll_timer.start()
            
            # 计算当前显示的文本段
            display_text = self.original_text[self.current_offset:]
            super().setText(display_text)

    def _scroll_text(self):
        """定时器触发，滚动文本"""
        if not self.font_metrics:
            self.font_metrics = self.fontMetrics()

        widget_width = self.width() - self.contentsMargins().left() - self.contentsMargins().right()
        text_text = self.original_text
        text_width = self.font_metrics.width(text_text)

        if text_width <= widget_width:
            self.scroll_timer.stop()
            super().setText(self.original_text)
            self.current_offset = 0
            return

        self.current_offset += 1
        
        # 判定循环条件：
        # 如果剩余文本极短（比如只剩最后 3-5 个字还没完全消失），就重置回开头。
        # 这里用文本长度 (len) 来粗略判断，比直接计算像素更符合字符切片逻辑。
        if self.current_offset >= len(text_text) - 1:
            self.current_offset = 0 # 回到开头
        
        self.update_text_display()

    def resizeEvent(self, event):
        """窗口大小改变时重新计算滚动"""
        super().resizeEvent(event)
        self.font_metrics = self.fontMetrics() # 字体可能随大小改变
        self.update_text_display()

class ElidedLabel(QLabel):
    """
    自动在末尾显示省略号(...)的 QLabel。
    """
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setMinimumWidth(1)
        self._full_text = text

    def set_elided_text(self, text):
        self._full_text = text
        self.update_elided_text()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_elided_text()

    def update_elided_text(self):
        metrics = self.fontMetrics()
        elided = metrics.elidedText(self._full_text, Qt.ElideRight, self.width())
        super().setText(elided)


class StreamingPage(QWidget):
    """
    流媒体选项卡页面。
    实现搜索、歌单显示、歌曲播放等功能。
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.subsystem = MusicSubsystem()
        self.settings_manager = SettingsManager()
        
        # 默认播放列表数据
        self.queue_tracks = self._load_queue_tracks()
        
        self.playlists = self._load_playlists()
        
        # 加载记忆的播放模式
        saved_mode = self.settings_manager.get_Custom_value("music_play_mode", "0")
        try:
            self.subsystem.set_play_mode(int(saved_mode))
        except:
            self.subsystem.set_play_mode(0)
        
        # 音量状态
        self.current_volume = 100
        self.pre_mute_volume = 100
        self.is_muted = False
        
        # 分页状态
        self.current_keyword = ""
        self.current_offset = 0
        
        self.init_ui()
        
        # 状态更新定时器
        self.status_timer = QTimer(self)
        self.status_timer.setInterval(500)
        self.status_timer.timeout.connect(self.update_playback_status)
        self.status_timer.start()
        
        # 订阅设置变更信号
        self.shared_manager = get_shared_memory_manager()
        self.shared_manager.settings_changed.connect(self._on_settings_changed)
        
        debug_logger.info("StreamingPage", "流媒体页面已初始化。")
        
    def _on_settings_changed(self, section, data):
        """处理自定义设置更改，动态更新主容器颜色"""
        if section == 'custom':
            left_bg = data.get('stream_left_bg_color')
            if left_bg and hasattr(self, 'left_outer'):
                self.left_outer.setStyleSheet(f"QFrame {{ background-color: {left_bg}; border-radius: 12px; }}")
            
            right_bg = data.get('stream_right_bg_color')
            if right_bg and hasattr(self, 'song_scroll') and hasattr(self, 'song_container'):
                self.song_scroll.setStyleSheet(f"""
                    QScrollArea {{
                        background-color: {right_bg};
                        border-radius: 10px;
                        border: none;
                    }}
                """)
                self.song_container.setStyleSheet(f"background-color: {right_bg}; border-radius: 10px;")
            
            bottom_bg = data.get('stream_bottom_bg_color')
            if bottom_bg and hasattr(self, 'player_bar'):
                self.player_bar.setStyleSheet(f"""
                    QFrame {{
                        background-color: {bottom_bg};
                        border-radius: 10px;
                    }}
                """)
                
            lyrics_bg = data.get('stream_lyrics_bg_color')
            if lyrics_bg and hasattr(self, 'lyrics_label'):
                font_family = self.settings_manager.get_Custom_value("global_font", "微软雅黑")
                self.lyrics_label.setStyleSheet(f"""
                    color: #333333;
                    font-size: 21px;
                    font-family: '{font_family}';
                    background-color: {lyrics_bg};
                    border-radius: 8px;
                    padding: 8px 15px;
                """)

    def init_ui(self):
        # 获取全局字体设置
        font_family = self.settings_manager.get_Custom_value("global_font", "微软雅黑")
        self.setStyleSheet(f"font-family: '{font_family}';")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(10)

        # --- 顶部搜索栏 ---
        search_layout = QHBoxLayout()
        search_layout.setSpacing(12)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search for...")
        self.search_input.setFixedHeight(65) # 从45增加
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #D3D3D3;
                border: 1px solid #AAAAAA;
                border-radius: 8px;
                padding-left: 15px;
                font-size: 24px;
                font-family: '{font_family}';
            }}
        """)
        self.search_input.returnPressed.connect(self.handle_search)
        
        search_layout.addWidget(self.search_input)
        
        # 搜索按钮：白底，蓝图标，带边框
        self.search_btn = QPushButton("🔍")
        self.search_btn.setFixedSize(65, 65) # 45 * 1.5
        self.search_btn.setCursor(Qt.PointingHandCursor)
        self.search_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: white;
                border: 1px solid #AAAAAA;
                border-radius: 8px;
                font-size: 30px;
                color: #0078D7;
                font-family: '{font_family}';
            }}
            QPushButton:hover {{ background-color: #f8f8f8; }}
        """)
        self.search_btn.clicked.connect(self.handle_search)
        search_layout.addWidget(self.search_btn)

        main_layout.addLayout(search_layout)

        # --- 中间内容区 ---
        content_layout = QHBoxLayout()
        content_layout.setSpacing(10)

        # === 左侧歌单栏 — 全部包在一个大圆角灰色容器里 ===
        PLAYLIST_BTN_H = 60 # 从40增加
        PLAYLIST_SPACING = 8
        PLAYLIST_PADDING = 10
        VISIBLE_COUNT = 4
        scroll_h = VISIBLE_COUNT * PLAYLIST_BTN_H + (VISIBLE_COUNT - 1) * PLAYLIST_SPACING + 2 * PLAYLIST_PADDING

        # 外层统一容器（灰色圆角框，宽度固定）
        left_bg = self.settings_manager.Custom.get_value("stream_left_bg_color", "#B0B0B0")
        self.left_outer = QFrame()
        self.left_outer.setFixedWidth(180) 
        self.left_outer.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding) # 纵向拉伸
        self.left_outer.setStyleSheet(f"QFrame {{ background-color: {left_bg}; border-radius: 12px; }}")
        left_outer_layout = QVBoxLayout(self.left_outer)
        left_outer_layout.setContentsMargins(10, 10, 10, 10)
        left_outer_layout.setSpacing(8)

        # 内部：滚动歌单列表
        self.playlist_container = QWidget()
        self.playlist_container.setStyleSheet("background-color: transparent;")
        self.playlist_layout = QVBoxLayout(self.playlist_container)
        self.playlist_layout.setContentsMargins(0, 0, 0, 0)
        self.playlist_layout.setSpacing(PLAYLIST_SPACING)

        self.playlist_scroll = QScrollArea()
        self.playlist_scroll.setWidgetResizable(True)
        # self.playlist_scroll.setFixedHeight(scroll_h) # 不固定高度，允许拉伸
        self.playlist_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.playlist_scroll.setStyleSheet("""
            QScrollArea { border: none; background-color: transparent; }
            QScrollBar:vertical { width: 8px; background: transparent; border-radius: 4px; }
            QScrollBar::handle:vertical { background: #888888; border-radius: 4px; }
        """)
        self.playlist_scroll.setWidget(self.playlist_container)

        self.update_playlist_display()

        left_outer_layout.addWidget(self.playlist_scroll)

        # 弹簧，将底部按钮压到容器最下方，确保整体对齐
        left_outer_layout.addStretch(1)

        # 分隔线
        sep_line = QFrame()
        sep_line.setFrameShape(QFrame.HLine)
        sep_line.setStyleSheet("color: #999999;")
        left_outer_layout.addWidget(sep_line)

        # 底部：歌单管理 + 添加歌单 (1.5倍字体)
        BOTTOM_BTN_STYLE = f"""
            QPushButton {{
                background-color: white;
                border-radius: 8px;
                border: 1px solid #BBBBBB;
                font-weight: bold;
                font-size: 21px;
                font-family: '{font_family}';
            }}
            QPushButton:hover {{ background-color: #e8e8e8; }}
        """

        self.manage_btn = QPushButton("歌单管理")
        self.manage_btn.setFixedHeight(60)
        self.manage_btn.setCursor(Qt.PointingHandCursor)
        self.manage_btn.setStyleSheet(BOTTOM_BTN_STYLE)
        self.manage_btn.clicked.connect(self.show_playlist_menu)

        self.add_btn = QPushButton("添加歌单")
        self.add_btn.setFixedHeight(60)
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setStyleSheet(BOTTOM_BTN_STYLE)
        self.add_btn.clicked.connect(self.handle_add_playlist)

        left_outer_layout.addWidget(self.manage_btn)
        left_outer_layout.addWidget(self.add_btn)

        # left_panel_container 纵向拉伸以填满
        left_panel_container = QVBoxLayout()
        left_panel_container.setContentsMargins(0, 0, 0, 0)
        left_panel_container.setSpacing(0)
        left_panel_container.addWidget(self.left_outer, 1) # 1 表示拉伸

        # === 右侧歌曲显示区（含标题） ===
        right_panel = QVBoxLayout()
        right_panel.setContentsMargins(0, 0, 0, 0)
        right_panel.setSpacing(6)

        # 列表标题与一键播放按钮布局
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(10)

        self.list_title_label = QLabel("列表标题")
        self.list_title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.list_title_label.setFixedHeight(36) # 24 * 1.5
        self.list_title_label.setStyleSheet(f"font-weight: bold; font-size: 21px; padding-left: 4px; font-family: '{font_family}'; color: #333333;")
        title_layout.addWidget(self.list_title_label)

        # 一键播放按钮
        self.play_all_btn = VolumeButton("▶ 一键播放")
        self.play_all_btn.setFixedSize(140, 36)
        self.play_all_btn.setCursor(Qt.PointingHandCursor)
        self.play_all_btn.setToolTip("点击一键播放，长按切换模式")
        self.play_all_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #0078D7;
                color: white;
                border-radius: 6px;
                font-size: 16px;
                font-weight: bold;
                font-family: '{font_family}';
            }}
            QPushButton:hover {{ background-color: #0086F0; }}
            QPushButton:pressed {{ background-color: #005A9E; }}
        """)
        self.play_all_btn.clicked.connect(self.handle_play_all)
        self.play_all_btn.longPressed.connect(self.show_mode_menu)
        title_layout.addWidget(self.play_all_btn)
        title_layout.addStretch(1)

        right_panel.addLayout(title_layout)

        right_bg = self.settings_manager.Custom.get_value("stream_right_bg_color", "#A0A0A0")
        
        self.song_scroll = QScrollArea()
        self.song_scroll.setWidgetResizable(True)
        self.song_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.song_scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: {right_bg};
                border-radius: 10px;
                border: none;
            }}
        """)
        
        self.song_container = QWidget()
        self.song_container.setStyleSheet(f"background-color: {right_bg}; border-radius: 10px;")
        self.song_layout = QVBoxLayout(self.song_container)
        self.song_layout.setAlignment(Qt.AlignTop)
        self.song_layout.setContentsMargins(6, 6, 6, 6)
        self.song_layout.setSpacing(4)
        self.song_scroll.setWidget(self.song_container)

        right_panel.addWidget(self.song_scroll, 1)

        content_layout.addLayout(left_panel_container)
        content_layout.addLayout(right_panel, 1)
        main_layout.addLayout(content_layout, 1)

        # --- 底部播放控制栏 ---
        # 布局：
        #   上行：[歌词区] | [分隔] | [歌名/作者] | [⏮ ▶ ⏭] | [🔊]
        #   下行：[————————————————进度条————————————————]
        bottom_bg = self.settings_manager.Custom.get_value("stream_bottom_bg_color", "#B0B0B0")
        
        self.player_bar = QFrame()
        self.player_bar.setFixedHeight(120) # 稍微增加高度 (110 -> 120)
        self.player_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {bottom_bg};
                border-radius: 10px;
            }}
        """)
        # 外层竖向布局
        player_outer = QVBoxLayout(self.player_bar)
        player_outer.setContentsMargins(15, 8, 15, 12) # 增加底边距 (8 -> 12)，抬高底部元素
        player_outer.setSpacing(4)

        # 上行
        player_layout = QHBoxLayout()
        player_layout.setSpacing(12)

        # 左：歌词显示区域（固定宽度为歌曲栏宽度的约 1/2）
        lyrics_bg = self.settings_manager.Custom.get_value("stream_lyrics_bg_color", "#9E9E9E")
        self.lyrics_label = ScrollingLabel()
        self.lyrics_label.set_scrolling_text("正在加载歌词...")
        self.lyrics_label.setFixedWidth(380) # 固定宽度
        self.lyrics_label.setStyleSheet(f"""
            color: #333333;
            font-size: 21px;
            font-family: '{font_family}';
            background-color: {lyrics_bg};
            border-radius: 8px;
            padding: 8px 15px;
        """)
        self.lyrics_label.setAlignment(Qt.AlignCenter)
        player_layout.addWidget(self.lyrics_label)

        # 分隔 (重新补上被误删的垂直分割线)
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFixedWidth(2)
        sep.setStyleSheet("color: #999999; margin: 10px 0;")
        player_layout.addWidget(sep)

        # 歌曲信息 (恢复 ScrollingLabel 并限制最大宽度，防止侵占左侧歌词区)
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        info_layout.setContentsMargins(5, 0, 5, 0)
        
        self.cur_song_label = ScrollingLabel()
        self.cur_song_label.setFixedHeight(33)
        self.cur_song_label.setFixedWidth(200) # 限制宽度，确保不会挤压左侧 380px 的歌词区
        self.cur_song_label.setStyleSheet(f"font-weight: bold; font-size: 20px; font-family: '{font_family}'; background: transparent;")
        self.cur_song_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        
        self.cur_artist_label = ScrollingLabel()
        self.cur_artist_label.setFixedHeight(27)
        self.cur_artist_label.setFixedWidth(200)
        self.cur_artist_label.setStyleSheet(f"color: #555555; font-size: 17px; font-family: '{font_family}'; background: transparent;")
        self.cur_artist_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        
        info_layout.addWidget(self.cur_song_label)
        info_layout.addWidget(self.cur_artist_label)
        player_layout.addLayout(info_layout) # 移除 stretch，使其紧贴左侧

        # 控制按钮 ⏮ ▶ ⏭ (图标保持原本设定的 54x54，但字体字号放大点)
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(12)
        self.prev_btn = QPushButton("prev")
        self.play_pause_btn = QPushButton("▶")
        self.next_btn = QPushButton("next")

        CTRL_BTN_STYLE = """
            QPushButton {
                background-color: rgb(255,255,255);
                font: 16pt "Segoe UI Symbol", "HarmonyOS Sans";
                color: #0078D7;
                border-radius: 8px;
                border: 1px solid gray;
            }
            QPushButton:hover { background-color: #f0f0f0; }
            QPushButton:pressed { background-color: #e0e0e0; }
        """
        # 使用纯字符并将颜色设为蓝色，并附加 \uFE0E 强制系统以文本模式（非 Emoji）渲染
        self.prev_btn.setText("\u23EE\uFE0E")
        self.play_pause_btn.setText("\u25B6\uFE0E")
        self.next_btn.setText("\u23ED\uFE0E")
        
        for btn in [self.prev_btn, self.play_pause_btn, self.next_btn]:
            btn.setFixedSize(54, 54)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(CTRL_BTN_STYLE)

        self.prev_btn.clicked.connect(self.subsystem.prev_song)
        self.play_pause_btn.clicked.connect(self.handle_play_pause)
        self.next_btn.clicked.connect(self.subsystem.next_song)

        ctrl_layout.addWidget(self.prev_btn)
        ctrl_layout.addWidget(self.play_pause_btn)
        ctrl_layout.addWidget(self.next_btn)
        player_layout.addLayout(ctrl_layout)
        
        # 增加末尾弹簧，将曲名和按钮全部推向左侧（紧贴歌词区）
        player_layout.addStretch(1)

        # 音量悬浮窗（先构造，音量按钮需引用它）
        self.volume_popup = VolumePopup(self)
        self.volume_popup.volumeChanged.connect(self.handle_volume_change)

        player_outer.addLayout(player_layout)

        # 下行：[进度条(拉长)] [🔊 音量按钮]
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)
        bottom_row.setAlignment(Qt.AlignVCenter) # 确保子控件（音量按钮与进度条）垂直居中对齐
        
        # 移除左侧弹簧，使进度条靠左对齐并拉长

        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setRange(0, 1000)
        self.progress_slider.setCursor(Qt.PointingHandCursor)
        self.progress_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: none;
                height: 6px;
                background: white;
                margin: 2px 0;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #555555;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #333333;
                border: none;
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
        """)
        self.progress_slider.sliderMoved.connect(self.handle_seek)
        bottom_row.addWidget(self.progress_slider, 1)

        # 音量控制按钮（底行右侧，与控制按钮相同样式 54x54）
        self.volume_btn = VolumeButton("🔊")
        self.volume_btn.setFixedSize(54, 54)
        self.volume_btn.setCursor(Qt.PointingHandCursor)
        self.volume_btn.setStyleSheet(CTRL_BTN_STYLE)
        self.volume_btn.clicked.connect(self.show_volume_popup)
        self.volume_btn.longPressed.connect(self.toggle_mute)
        bottom_row.addWidget(self.volume_btn)

        player_outer.addLayout(bottom_row)

        main_layout.addWidget(self.player_bar)



    def update_playback_status(self):
        """更新播放状态 (定时触发)"""
        if not self.subsystem.current_track:
            self.cur_song_label.set_scrolling_text("未在播放")
            self.cur_artist_label.set_scrolling_text("-")
            return

        track = self.subsystem.current_track
        if getattr(self.cur_song_label, 'original_text', '') != track.name:
            self.cur_song_label.set_scrolling_text(track.name)
        if getattr(self.cur_artist_label, 'original_text', '') != track.artist:
            self.cur_artist_label.set_scrolling_text(track.artist)

        # 更新歌词显示
        lyrics_list = track.parsed_lyrics
        if lyrics_list:
            pos_ms = self.subsystem.player.get_pos()
            # 找到当前应该显示的歌词行
            current_text = ""
            # 逆向遍历可能更快找到当前行
            for i in range(len(lyrics_list) - 1, -1, -1):
                if lyrics_list[i][0] <= pos_ms:
                    current_text = lyrics_list[i][1]
                    break
            
            if not current_text:
                current_text = "..."
                 
            if getattr(self.lyrics_label, 'original_text', '') != current_text:
                self.lyrics_label.set_scrolling_text(current_text)
        else:
            # 尝试后台加载
            self.subsystem.get_current_lyrics()
            if getattr(self.lyrics_label, 'original_text', '') != "暂无歌词":
                self.lyrics_label.set_scrolling_text("暂无歌词")

        # 更新播放/暂停按钮图标 (使用 \uFE0E 强制非 Emoji 模式，确保无杂色背景)
        if self.subsystem.player.is_playing:
            if self.subsystem.player.is_paused:
                self.play_pause_btn.setText("\u25B6\uFE0E")
            else:
                self.play_pause_btn.setText("\u23F8\uFE0E")
        else:
            self.play_pause_btn.setText("\u25B6\uFE0E")

        # 更新进度条
        if self.subsystem.player.is_playing and not self.subsystem.player.is_paused:
            pos_ms = self.subsystem.player.get_pos()
            total_ms = track.duration
            if total_ms > 0:
                progress = int((pos_ms / total_ms) * 1000)
                # 只有在用户没拖动时才自动更新
                if not self.progress_slider.isSliderDown():
                    self.progress_slider.setValue(progress)

    def handle_play_pause(self):
        """处理播放/暂停点击"""
        if not self.subsystem.player.is_playing:
            # 如果没在播，默认播当前列表第一首
            self.subsystem.play_by_index(1)
        else:
            if self.subsystem.player.is_paused:
                self.subsystem.resume()
            else:
                self.subsystem.pause()

    def handle_seek(self, value):
        """处理进度条跳转"""
        if self.subsystem.current_track:
            total_ms = self.subsystem.current_track.duration
            target_ms = int((value / 1000.0) * total_ms)
            self.subsystem.player.set_pos(target_ms)

    def show_volume_popup(self):
        """显示音量调节悬浮窗"""
        # 计算显示位置：按钮上方
        btn_pos = self.volume_btn.mapToGlobal(self.volume_btn.rect().topLeft())
        popup_x = btn_pos.x() + (self.volume_btn.width() - self.volume_popup.width()) // 2
        popup_y = btn_pos.y() - self.volume_popup.height() - 5
        
        self.volume_popup.set_value(self.current_volume)
        self.volume_popup.move(popup_x, popup_y)
        self.volume_popup.show()

    def handle_volume_change(self, value):
        """处理音量改变"""
        self.current_volume = value
        self.is_muted = (value == 0)
        self._apply_volume()

    def toggle_mute(self):
        """长按切换静音"""
        if self.is_muted:
            self.current_volume = self.pre_mute_volume if self.pre_mute_volume > 0 else 50
            self.is_muted = False
            debug_logger.info("StreamingPage", f"恢复音量: {self.current_volume}%")
        else:
            self.pre_mute_volume = self.current_volume
            self.current_volume = 0
            self.is_muted = True
            debug_logger.info("StreamingPage", "已静音")
        
        self.volume_popup.set_value(self.current_volume)
        self._apply_volume()

    def _apply_volume(self):
        """应用当前音量到子系统"""
        # 更新按钮图标
        if self.is_muted:
            self.volume_btn.setText("🔇")
        elif self.current_volume < 30:
            self.volume_btn.setText("🔈")
        elif self.current_volume < 70:
            self.volume_btn.setText("🔉")
        else:
            self.volume_btn.setText("🔊")
            
        self.subsystem.set_volume(self.current_volume / 100.0)

    def handle_play_all(self):
        """处理一键播放"""
        if not self.subsystem.current_list:
            QMessageBox.information(self, "提示", "当前列表为空，请先搜索或选择歌单。")
            return
            
        debug_logger.info("StreamingPage", f"触发一键播放，当前模式: {self.subsystem.play_mode}")
        self.subsystem.play_all()

    def show_mode_menu(self):
        """长按一键播放，弹出播放模式选择菜单"""
        menu = QMenu(self)
        
        modes = [
            (0, "🔁 列表循环"),
            (1, "🔂 单曲循环"),
            (2, "🔀 随机播放")
        ]
        
        actions = []
        for code, name in modes:
            action = menu.addAction(name)
            action.setCheckable(True)
            if self.subsystem.play_mode == code:
                action.setChecked(True)
            actions.append((action, code))
            
        # 弹出菜单
        selected_action = menu.exec_(self.play_all_btn.mapToGlobal(self.play_all_btn.rect().bottomLeft()))
        
        if selected_action:
            for action, code in actions:
                if action == selected_action:
                    self.subsystem.set_play_mode(code)
                    # 保存播放模式记忆
                    self.settings_manager.set_Custom_value("music_play_mode", str(code))
                    mode_name = next(m[1] for m in modes if m[0] == code)
                    debug_logger.info("StreamingPage", f"已切换播放模式并记忆: {mode_name}")
                    break

    def _load_playlists(self):
        """从设置加载歌单"""
        playlists_data = self.settings_manager.get_Custom_value("music_playlists", "")
        # 始终包含一个虚拟的“播放列表”项
        result = [{"name": "播放列表", "url": "internal://queue"}]
        
        if not playlists_data:
            return result
            
        # 格式: Name|URL;Name|URL
        items = playlists_data.split(";")
        for item in items:
            if "|" in item:
                name, url = item.split("|", 1)
                # 过滤掉重复的播放列表（如果用户手动添加了同名的）
                if name != "播放列表":
                    result.append({"name": name, "url": url})
        return result

    def _load_queue_tracks(self):
        """加载保存的播放列表歌曲数据"""
        data = self.settings_manager.get_Custom_value("music_queue_data", "")
        if not data: return []
        try:
            tracks_json = json.loads(data)
            return [MusicTrack(**t) for t in tracks_json]
        except:
            return []

    def _save_queue_tracks(self):
        """保存播放列表歌曲数据"""
        tracks_data = []
        for t in self.queue_tracks:
            tracks_data.append({
                "song_id": t.song_id,
                "name": t.name,
                "artist": t.artist,
                "album": t.album,
                "duration": t.duration
            })
        self.settings_manager.set_Custom_value("music_queue_data", json.dumps(tracks_data))

    def _save_playlists(self):
        """保存歌单到设置"""
        # 排除内部播放列表后再保存
        persistent = [p for p in self.playlists if p['url'] != "internal://queue"]
        data = ";".join([f"{p['name']}|{p['url']}" for p in persistent])
        self.settings_manager.set_Custom_value("music_playlists", data)

    def update_playlist_display(self):
        """更新左侧歌单列表显示"""
        # 清空布局
        while self.playlist_layout.count():
            item = self.playlist_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.spacerItem():
                pass # takeAt 已经将其移出布局

        # 检查数量以应用居中逻辑
        playlist_count = len(self.playlists)
        
        # 歌单列表始终靠上对齐，由 QScrollArea 提供滚动
        self.playlist_layout.setAlignment(Qt.AlignTop)
        
        for i, p in enumerate(self.playlists):
            btn = self._create_playlist_button(i, p['name'])
            self.playlist_layout.addWidget(btn)
        
        # 添加一个伸缩器，确保内容靠上
        self.playlist_layout.addStretch(1)

    def _create_playlist_button(self, index, name):
        """创建歌单按钮"""
        # 获取当前字体
        font_family = self.settings_manager.get_Custom_value("global_font", "微软雅黑")
        
        btn = QPushButton(name)
        btn.setFixedHeight(40)
        btn.setFixedWidth(160)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: white;
                border-radius: 5px;
                border: 1px solid #BBBBBB;
                padding: 5px;
                font-size: 21px; 
                font-family: '{font_family}';
            }}
            QPushButton:hover {{
                background-color: #f0f0f0;
            }}
            QPushButton:pressed {{
                background-color: #e0e0e0;
            }}
        """)
        btn.clicked.connect(lambda checked, idx=index: self.handle_playlist_click(idx))
        return btn

    def handle_search(self):
        """处理搜索请求"""
        keyword = self.search_input.text().strip()
        if not keyword:
            return
        
        self.current_keyword = keyword
        self.current_offset = 0
        debug_logger.info("StreamingPage", f"执行新搜索: {keyword}")
        results = self.subsystem.search(keyword, offset=0)
        self.display_songs(results, clear=True)
        self.list_title_label.setText(f"搜索结果——{keyword}")

    def handle_next_page(self):
        """处理下一页"""
        self.current_offset += 30
        debug_logger.info("StreamingPage", f"加载下一页，偏移量: {self.current_offset}")
        results = self.subsystem.search(self.current_keyword, offset=self.current_offset)
        self.display_songs(results, clear=False)
        self.list_title_label.setText(f"搜索结果——{self.current_keyword} (第 {self.current_offset // 30 + 1} 页)")

    def handle_artist_search(self, artist_name):
        """点击作者，搜索该作者的歌曲"""
        self.search_input.setText(artist_name)
        self.handle_search()
        self.list_title_label.setText(f"搜索结果——{artist_name}")

    def handle_playlist_click(self, index):
        """处理点击歌单"""
        if index < 0 or index >= len(self.playlists):
            return
            
        playlist = self.playlists[index]
        debug_logger.info("StreamingPage", f"切换至歌单: {playlist['name']}")
        
        self.current_keyword = "" # 歌单模式下清除搜索关键词
        
        # 特殊处理内部播放列表
        if playlist['url'] == "internal://queue":
            self.subsystem.current_list = self.queue_tracks
            self.display_songs(self.queue_tracks, clear=True)
            self.list_title_label.setText("播放列表")
            return

        # 导入网易云歌单
        if self.subsystem.import_playlist(playlist['url']):
            self.display_songs(self.subsystem.current_list, clear=True)
            self.list_title_label.setText(f"歌单——{playlist['name']}")
        else:
            QMessageBox.warning(self, "错误", "无法导入该歌单，请检查链接是否正确。")

    def handle_add_to_queue(self, track):
        """添加到播放列表"""
        # 检查是否已存在
        if any(t.song_id == track.song_id for t in self.queue_tracks):
            debug_logger.info("StreamingPage", f"歌曲已在列表中: {track.name}")
            return
            
        self.queue_tracks.append(track)
        self._save_queue_tracks()
        debug_logger.info("StreamingPage", f"已添加到播放列表: {track.name}")
        
        # 如果当前正显示“播放列表”，刷新显示
        if self.subsystem.current_list is self.queue_tracks:
            self.display_songs(self.queue_tracks, clear=True)

    def handle_delete_song(self, index):
        """处理删除歌曲请求 (1-based index)"""
        if not self.subsystem.current_list:
            return
            
        # 确认删除 (可选，为了流畅性可以不加，这里加上确认)
        track = self.subsystem.current_list[index-1]
        
        # 从子系统中移除 (会自动处理 index 和 随机序列)
        self.subsystem.remove_track_by_index(index)
        
        # 如果当前是“播放列表”模式，同步更新持久化数据
        if self.subsystem.current_list is self.queue_tracks:
            self._save_queue_tracks()
            
        # 重新刷新显示列表
        self.display_songs(self.subsystem.current_list, clear=True)
        debug_logger.info("StreamingPage", f"已从当前列表移除歌曲: {track.name}")
        
        # 更新标题，确保显示的是当前列表的最新状态
        if self.subsystem.current_list is self.queue_tracks:
            self.list_title_label.setText("播放列表")
        elif self.current_keyword:
            self.list_title_label.setText(f"搜索结果——{self.current_keyword}")
        else:
            # 找到当前歌单的名称
            current_playlist_name = "未知歌单"
            for p in self.playlists:
                if self.subsystem.current_list == self.subsystem.import_playlist(p['url']): # 这种比较方式不严谨，但目前可用
                    current_playlist_name = p['name']
                    break
            self.list_title_label.setText(f"歌单——{current_playlist_name}")

    def display_songs(self, tracks, clear=True):
        """在右侧区域显示歌曲列表"""
        if clear:
            # 清除现有内容
            while self.song_layout.count():
                item = self.song_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        else:
            # 如果不清除，则先移除旧的“下一页”按钮（如果有）
            for i in range(self.song_layout.count()):
                widget = self.song_layout.itemAt(i).widget()
                if isinstance(widget, QPushButton) and widget.text() == "加载更多 (下一页)":
                    widget.deleteLater()
                    break

        # 添加新歌曲
        start_idx = len(self.subsystem.current_list) - len(tracks) + 1 if not clear else 1
        is_queue_view = (self.subsystem.current_list is self.queue_tracks)
        
        for i, track in enumerate(tracks, start_idx):
            widget = SongItemWidget(i, track, is_queue=is_queue_view)
            widget.play_clicked.connect(self.subsystem.play_by_index)
            widget.artist_clicked.connect(self.handle_artist_search)
            widget.add_to_queue_requested.connect(self.handle_add_to_queue) # 连接右键菜单/按钮的添加信号
            widget.delete_requested.connect(self.handle_delete_song) # 连接右键菜单/按钮的删除信号
            self.song_layout.addWidget(widget)

        # 如果是搜索模式且有结果，添加“下一页”按钮
        if self.current_keyword and len(tracks) >= 30:
            # 获取当前字体
            font_family = self.settings_manager.get_Custom_value("global_font", "微软雅黑")
            
            next_page_btn = QPushButton("加载更多 (下一页)")
            next_page_btn.setFixedHeight(50)
            next_page_btn.setMinimumWidth(0) # 允许缩小
            next_page_btn.setCursor(Qt.PointingHandCursor)
            next_page_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #f0f0f0;
                    border-radius: 8px;
                    border: 1px dashed #aaaaaa;
                    font-weight: bold;
                    color: #555555;
                    margin: 10px 5px;
                    font-family: '{font_family}';
                }}
                QPushButton:hover {{
                    background-color: #e0e0e0;
                }}
            """)
            next_page_btn.clicked.connect(self.handle_next_page)
            self.song_layout.addWidget(next_page_btn)

    def handle_add_playlist(self):
        """处理添加歌单"""
        name, ok1 = QInputDialog.getText(self, "添加歌单", "请输入歌单名称:")
        if not ok1 or not name: return
        
        url, ok2 = QInputDialog.getText(self, "添加歌单", "请输入网易云歌单链接:")
        if not ok2 or not url: return
        
        self.playlists.append({"name": name, "url": url})
        self._save_playlists()
        self.update_playlist_display()
        debug_logger.info("StreamingPage", f"已添加歌单: {name}")

    def show_playlist_menu(self):
        """显示歌单管理菜单"""
        menu = QMenu(self)
        delete_action = menu.addAction("删除歌单...")
        clear_action = menu.addAction("清空所有歌单")
        
        action = menu.exec_(self.manage_btn.mapToGlobal(self.manage_btn.rect().bottomLeft()))
        
        if action == delete_action:
            # 弹出一个选择框来删除 (过滤掉内置播放列表)
            names = [p['name'] for p in self.playlists if p['url'] != "internal://queue"]
            if not names: return
            name, ok = QInputDialog.getItem(self, "删除歌单", "选择要删除的歌单:", names, 0, False)
            if ok and name:
                self.playlists = [p for p in self.playlists if p['name'] != name]
                self._save_playlists()
                self.update_playlist_display()
        elif action == clear_action:
            if QMessageBox.question(self, "确认", "确定要清空所有自定义歌单吗？") == QMessageBox.Yes:
                # 保留内置播放列表
                self.playlists = [p for p in self.playlists if p['url'] == "internal://queue"]
                self._save_playlists()
                self.update_playlist_display()

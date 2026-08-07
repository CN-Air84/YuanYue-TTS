# coding=utf-8
import os
import random
import requests
import threading
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGridLayout, QScrollArea, QFrame,
    QApplication
)
from PyQt5.QtCore import Qt, QTimer, QUrl, pyqtSignal, QEasingCurve, pyqtProperty
from PyQt5.QtGui import (
    QFont, QPixmap, QDesktopServices, QFontDatabase, QRawFont
)
try:
    from PyQt5.QtCore import QPropertyAnimation
except ImportError:
    QPropertyAnimation = None

from debug_logger import debug_logger, LogLevel
from misc_func import SettingsManager, get_app_base_path
import mp_about
from network_latency_checker import NetworkLatencyChecker
from resource_urls import get_resource_url
from theme_page_adapter import (
    configure_semantic_surface,
    configure_theme_card,
    configure_transparent_container,
    configure_transparent_root,
    set_transparent_scroll_content,
)


SLOGAN_TEXT = "源悦TTS，与你共鸣。"
SLOGAN_HAN_CHARACTERS = tuple(dict.fromkeys(
    character for character in SLOGAN_TEXT
    if "\u3400" <= character <= "\u9fff"
))
CHINESE_WRITING_SYSTEMS = (
    QFontDatabase.SimplifiedChinese,
    QFontDatabase.TraditionalChinese,
)


def _font_supports_slogan(font_family):
    """Return whether a family contains every Han glyph used by the slogan."""
    try:
        raw_font = QRawFont.fromFont(QFont(font_family))
        return raw_font.isValid() and all(
            raw_font.supportsCharacter(ord(character))
            for character in SLOGAN_HAN_CHARACTERS
        )
    except (RuntimeError, TypeError):
        return False


def discover_chinese_font_families(font_database=None):
    """Discover installed Chinese-capable font families without a whitelist."""
    font_db = font_database or QFontDatabase()
    discovered = []
    for writing_system in CHINESE_WRITING_SYSTEMS:
        discovered.extend(font_db.families(writing_system))

    # Qt may return duplicate localized family names for different styles.
    unique_families = list(dict.fromkeys(
        str(family).strip() for family in discovered if str(family).strip()
    ))
    verified_families = [
        family for family in unique_families
        if _font_supports_slogan(family)
    ]

    # If glyph probing is unavailable on a platform, Qt's writing-system
    # classification is still a better fallback than a hard-coded list.
    return verified_families or unique_families


class ClickableLabel(QLabel):
    """可点击的标签，用于切换字体；支持打字机动画与缩放反馈"""
    clicked = pyqtSignal()

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)

        # 打字机动画状态
        self._full_text = text
        self._typewriter_timer = QTimer(self)
        self._typewriter_timer.timeout.connect(self._on_typewriter_tick)
        self._typewriter_pos = 0

        # 缩放动画状态（通过自定义属性 scaleFactor 驱动 paintEvent 缩放）
        self._scale = 1.0
        self._scale_anim = None

    # ---------- 打字机动画 ----------
    def play_typewriter(self, text=None, interval_ms=60):
        """逐字显示文本

        Args:
            text: 要显示的完整文本（默认沿用当前 full_text）
            interval_ms: 每个字的间隔毫秒
        """
        if text is not None:
            self._full_text = text
        self._typewriter_pos = 0
        super().setText("")
        self._typewriter_timer.start(interval_ms)

    def _on_typewriter_tick(self):
        self._typewriter_pos += 1
        super().setText(self._full_text[:self._typewriter_pos])
        if self._typewriter_pos >= len(self._full_text):
            self._typewriter_timer.stop()

    # ---------- 缩放动画 ----------
    @pyqtProperty(float)
    def scaleFactor(self):
        return self._scale

    @scaleFactor.setter
    def scaleFactor(self, value):
        self._scale = value
        self.update()

    def play_pop(self, peak=1.18, duration_ms=380):
        """轻微缩放反馈：放大后回弹到原始大小"""
        if QPropertyAnimation is None:
            return
        if self._scale_anim is not None and self._scale_anim.state() == QPropertyAnimation.Running:
            self._scale_anim.stop()
        anim = QPropertyAnimation(self, b"scaleFactor", self)
        anim.setDuration(duration_ms)
        anim.setStartValue(self._scale)
        anim.setKeyValueAt(0.35, peak)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutBack)
        anim.start()
        self._scale_anim = anim

    def setText(self, text):
        self._full_text = text
        super().setText(text)

    def paintEvent(self, event):
        """按 scaleFactor 围绕中心缩放绘制文本"""
        from PyQt5.QtGui import QPainter
        if abs(self._scale - 1.0) < 1e-3:
            # 未缩放时使用原生绘制，保留 QLabel 的全部默认行为
            super().paintEvent(event)
            return
        # 缩放时自己绘制文本，确保缩放视觉生效
        painter = QPainter(self)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        painter.translate(cx, cy)
        painter.scale(self._scale, self._scale)
        painter.translate(-cx, -cy)
        # 应用当前字体与样式表颜色
        painter.setFont(self.font())
        text = self.text()
        flags = int(self.alignment()) | Qt.AlignVCenter
        painter.drawText(self.rect(), flags, text)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

class WelcomePage(QWidget):
    # 用于异步更新UI的信号
    intro_loaded = pyqtSignal(str)
    echo_zen_loaded = pyqtSignal(list)
    image_downloaded = pyqtSignal(str, str) # tag, local_path
    slogan_fonts_loaded = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        configure_transparent_root(self)
        debug_logger.output("welcome_page.py", LogLevel.INFO, "Initializing WelcomePage...", fold_code="WELCOME_INIT")
        self.parent_window = parent
        self.settings_manager = SettingsManager()
        
        # 获取配置
        self.global_font = self.settings_manager.get_Custom_value('global_font', '微软雅黑')
        self.bg_color = self.settings_manager.get_Custom_value('background_color', '#E5E8EF')
        
        # 缓存目录
        self.cache_dir = os.path.join(get_app_base_path(), "cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # 数据初始化
        self.echo_zen_lines = ["加载中..."]
        self.intro_text = "加载中..."
        self.current_slogan_font_name = self.global_font
        self._slogan_font_families = []
        self._slogan_font_discovery_started = False
        self._slogan_font_changed_by_user = False
        
        # Logo相关
        self.original_logo_pixmap = None  # 保存原始Logo图片
        
        # 初始化网络延迟检测器
        self.latency_checker = NetworkLatencyChecker()
        self.latency_checker.latency_updated.connect(self._on_latency_updated)
        self._closing = False
        
        # 初始化UI
        self.init_ui()
        
        # 启动时钟
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_time)
        self.timer.start(1000)
        self._update_time()
        
        # 连接信号
        self.intro_loaded.connect(self._on_intro_loaded)
        self.echo_zen_loaded.connect(self._on_echo_zen_loaded)
        self.image_downloaded.connect(self._on_image_downloaded)
        self.slogan_fonts_loaded.connect(self._on_slogan_fonts_loaded)
        
        # 获取版本信息
        self._load_version_info()
        
        # 异步加载数据
        self._start_async_loading()

        # 静默扫描本机中文字体，避免阻塞欢迎页首屏
        self._start_slogan_font_discovery()
        
        # 随机切换标语字体（初始化不播放动画）
        self._change_slogan_font(animate=False)
        
        # 启动网络延迟检测
        self.latency_checker.check_once()  # 立即检测一次
        self.latency_checker.start_checking(interval=30)  # 每30秒检测一次

    def _connect_shared_memory_signals(self):
        """连接共享内存信号"""
        from shared_memory_manager import get_shared_memory_manager
        self.shared_manager = get_shared_memory_manager()
        self.shared_manager.settings_changed.connect(self._on_settings_changed_from_shared_memory)

    def init_ui(self):
        """初始化UI界面 - 采用白底卡片风格"""
        # 主布局使用垂直布局，将Logo和内容区分开
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(20)
        
        # 1. 顶部 Logo 横幅（横向居中）
        self.logo_card = QFrame()
        configure_transparent_container(self.logo_card)
        self.logo_card.setStyleSheet("background-color: transparent; border: none;")
        logo_main_layout = QVBoxLayout(self.logo_card)
        logo_main_layout.setContentsMargins(0, 0, 0, 0)
        logo_main_layout.setSpacing(0)

        # Logo 部分（横向居中）
        logo_container = QWidget()
        configure_transparent_container(logo_container)
        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(0, 0, 0, 0)

        self.logo_label = QLabel()
        configure_semantic_surface(self.logo_label)
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.logo_label.setMinimumHeight(180)
        self.logo_label.setText("正在获取 Logo...")
        logo_layout.addWidget(self.logo_label)

        logo_main_layout.addWidget(logo_container)

        self.main_layout.addWidget(self.logo_card)
        
        # 2. 中间内容网格
        content_widget = QWidget()
        configure_transparent_container(content_widget)
        self.grid_layout = QGridLayout(content_widget)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(20)
        
        # 2.1 标语卡片 (左上)
        self.slogan_card = QFrame()
        self.slogan_card.setObjectName("whiteCard")
        configure_theme_card(self.slogan_card)
        slogan_layout = QVBoxLayout(self.slogan_card)
        self.slogan_label = ClickableLabel(SLOGAN_TEXT)
        self.slogan_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.slogan_label.clicked.connect(self._change_slogan_font)
        slogan_layout.addWidget(self.slogan_label)
        self.grid_layout.addWidget(self.slogan_card, 0, 0)
        
        # 2.2 状态卡片 (左中 - 时钟)
        self.status_card = QFrame()
        self.status_card.setObjectName("whiteCard")
        configure_theme_card(self.status_card)
        status_layout = QVBoxLayout(self.status_card)
        status_layout.setSpacing(10)
        status_layout.setAlignment(Qt.AlignCenter)
        
        self.date_display = QLabel("2024年01月01日 星期一")
        self.date_display.setObjectName("dateDisplay")
        self.date_display.setAlignment(Qt.AlignCenter)
        
        self.time_display = QLabel("00:00:00")
        self.time_display.setObjectName("clockDisplay")
        self.time_display.setAlignment(Qt.AlignCenter)
        
        status_layout.addStretch()
        status_layout.addWidget(self.date_display)
        status_layout.addWidget(self.time_display)
        status_layout.addStretch()
        
        self.grid_layout.addWidget(self.status_card, 1, 0)
        
        # 2.3 回声树洞卡片 (左下)
        self.echo_card = QFrame()
        self.echo_card.setObjectName("whiteCard")
        configure_theme_card(self.echo_card)
        echo_layout = QVBoxLayout(self.echo_card)
        
        self.echo_title = QLabel("回声树洞:")
        self.echo_title.setObjectName("echoTitle")
        self.echo_title.setStyleSheet("font-weight: bold; color: #555;")
        self.echo_content = QLabel("正在从网络获取句子...")
        self.echo_content.setObjectName("echoContent")
        self.echo_content.setWordWrap(True)
        self.echo_content.setMinimumHeight(60)
        self.echo_content.setAlignment(Qt.AlignTop)
        
        self.change_echo_btn = QPushButton("换一句")
        self.change_echo_btn.clicked.connect(self._random_echo_zen)
        self.change_echo_btn.setFixedWidth(80)
        self.change_echo_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; }"
        )
        
        echo_layout.addWidget(self.echo_title)
        echo_layout.addWidget(self.echo_content)
        echo_layout.addWidget(self.change_echo_btn, 0, Qt.AlignRight)
        self.grid_layout.addWidget(self.echo_card, 2, 0)
        
        # 2.4 公告栏卡片 (占满右侧三行)
        self.intro_card = QFrame()
        self.intro_card.setObjectName("whiteCard")
        configure_theme_card(self.intro_card)
        intro_layout = QVBoxLayout(self.intro_card)

        self.intro_title = QLabel("公告栏")
        self.intro_title.setObjectName("introTitle")
        self.intro_title.setStyleSheet("font-weight: bold; font-size: 18px; color: #333;")
        
        self.scroll_area = QScrollArea()
        configure_transparent_container(self.scroll_area)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background-color: transparent; border: none;")
        
        self.intro_label = QLabel("正在获取公告...")
        self.intro_label.setWordWrap(True)
        self.intro_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.intro_label.setStyleSheet(
            "line-height: 1.5; color: #444; "
            "background: transparent; border: none;"
        )
        set_transparent_scroll_content(self.scroll_area, self.intro_label)

        # 在线服务可用性检测徽章（紧凑横向格式，放在简介与底部信息栏之间）
        self.network_status_card = QFrame()
        self.network_status_card.setObjectName("networkStatusBadge")
        configure_theme_card(self.network_status_card)
        self.network_status_card.setStyleSheet(
            "#networkStatusBadge { background-color: transparent; border: none; }"
        )
        network_layout = QHBoxLayout(self.network_status_card)
        network_layout.setContentsMargins(12, 6, 12, 6)
        network_layout.setSpacing(8)
        network_layout.setAlignment(Qt.AlignVCenter)

        # Github 延迟
        github_dot = QLabel("●")
        github_dot.setObjectName("githubDot")
        github_dot.setStyleSheet("color: #E74C3C; background: transparent; border: none;")
        network_layout.addWidget(github_dot)
        github_label = QLabel("Github")
        github_label.setStyleSheet("color: #555; background: transparent; border: none;")
        network_layout.addWidget(github_label)
        self.github_latency = QLabel("999ms")
        self.github_latency.setObjectName("latencyValue")
        self.github_latency.setStyleSheet("font-weight: bold; color: #E74C3C; background: transparent; border: none;")
        network_layout.addWidget(self.github_latency)

        # 分隔
        sep = QLabel("|")
        sep.setStyleSheet("color: #CCC; background: transparent; border: none;")
        network_layout.addWidget(sep)

        # 国内资源延迟
        domestic_dot = QLabel("●")
        domestic_dot.setObjectName("domesticDot")
        domestic_dot.setStyleSheet("color: #27AE60; background: transparent; border: none;")
        network_layout.addWidget(domestic_dot)
        domestic_label = QLabel("国内")
        domestic_label.setStyleSheet("color: #555; background: transparent; border: none;")
        network_layout.addWidget(domestic_label)
        self.domestic_latency = QLabel("16ms")
        self.domestic_latency.setObjectName("latencyValue")
        self.domestic_latency.setStyleSheet("font-weight: bold; color: #27AE60; background: transparent; border: none;")
        network_layout.addWidget(self.domestic_latency)

        network_layout.addStretch()

        # 底部信息栏 (版本、Github、更新)
        info_footer_container = QVBoxLayout()
        info_footer_container.setSpacing(5)
        
        # 第一行: 程序版本 (靠右)
        version_row = QHBoxLayout()
        self.version_display = QLabel("程序版本: 【未知】")
        self.version_display.setObjectName("versionDisplay")
        version_row.addStretch()
        version_row.addWidget(self.version_display)
        
        # 第二行: 按钮 (靠右)
        btns_row = QHBoxLayout()
        self.github_btn = QPushButton("Github 主页")
        self.github_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(get_resource_url('repo'))))
        
        self.update_btn = QPushButton("检查更新")
        self.update_btn.clicked.connect(self._check_updates)
        for btn in (self.github_btn, self.update_btn):
            btn.setStyleSheet("QPushButton { background: transparent; border: none; }")
        
        btns_row.addStretch()
        btns_row.addWidget(self.github_btn)
        btns_row.addWidget(self.update_btn)
        
        info_footer_container.addLayout(version_row)
        info_footer_container.addLayout(btns_row)
        
        intro_layout.addWidget(self.intro_title)
        intro_layout.addWidget(self.scroll_area, stretch=1)
        intro_layout.addWidget(self.network_status_card)
        intro_layout.addLayout(info_footer_container)
        
        self.grid_layout.addWidget(self.intro_card, 0, 1, 3, 1)
        
        # Keep the left cards at a fixed 1:2:2 height ratio so the time panel
        # cannot squeeze the slogan card.
        self.grid_layout.setColumnStretch(0, 4)
        self.grid_layout.setColumnStretch(1, 6)
        self.grid_layout.setRowStretch(0, 1)
        self.grid_layout.setRowStretch(1, 2)
        self.grid_layout.setRowStretch(2, 2)
        
        self.main_layout.addWidget(content_widget)
        
        self._apply_styles()

    def _apply_styles(self):
        """应用白底卡片样式表"""
        # 获取卡片背景颜色和文字颜色
        card_bg = self.settings_manager.get_Custom_value('card_background_color', '#F5F8FF')
        text_color = self.settings_manager.get_Custom_value('text_color', '#333333')
        
        # 背景色设置
        self.setStyleSheet(f"""
            WelcomePage {{
                background-color: {self.bg_color};
            }}
            QFrame#whiteCard {{
                background-color: {card_bg};
                border: 1px solid #E0E0E0;
                border-radius: 12px;
            }}
            QLabel {{
                font-family: "{self.global_font}";
                color: {text_color};
                background-color: transparent; /* 文字背景透明，跟随卡片 */
            }}
            #clockDisplay {{
                font-weight: bold;
                color: {text_color};
                margin: 5px 0;
                border-radius: 8px;
            }}
            #dateDisplay {{
                color: {text_color};
            }}
            QPushButton {{
                background-color: #FFFFFF;
                color: {text_color};
                border: 1px solid #DCDFE6;
                border-radius: 6px;
                padding: 6px 12px;
                font-family: "{self.global_font}";
            }}
            QPushButton:hover {{
                background-color: #F5F7FA;
                border-color: #409EFF;
                color: #409EFF;
            }}
        """)
        
        # 标语标签特殊样式 - 使用 ID 确保优先级，且不在此处设置字体
        self.slogan_label.setObjectName("sloganLabel")
        self.slogan_label.setStyleSheet(f"font-weight: bold; color: {text_color}; background: transparent; border: none;")

    def resizeEvent(self, event):
        """窗口大小改变事件"""
        debug_logger.output("welcome_page.py", LogLevel.INFO, f"欢迎页面大小调整: {self.width()}x{self.height()}", fold_code="WELCOME_INIT")
        super().resizeEvent(event)
        self._update_fonts()

    def _update_fonts(self):
        """动态更新字体大小 - 参考 generation_page 算法"""
        debug_logger.output("welcome_page.py", LogLevel.INFO, "正在动态计算 UI 字体缩放适配", fold_code="WELCOME_INIT")
        if not self.parent_window:
            return
            
        current_width = self.parent_window.width()
        current_height = self.parent_window.height()
        
        # 字体缩放算法
        min_font_size = 22
        max_font_size = 42
        default_width = 1080
        default_height = 720
        
        width_ratio = current_width / default_width
        height_ratio = current_height / default_height
        ratio = (width_ratio + height_ratio) / 2
        
        base_font_size = min_font_size + (max_font_size - min_font_size) * (ratio - 1)
        base_font_size = max(min_font_size, min(max_font_size, base_font_size))
        
        # 基础字号
        font_base = int(base_font_size * 0.45) # 约 10-18px
        font_large = int(base_font_size * 1.0) # 约 22-42px
        font_title = int(base_font_size * 0.6) # 约 13-25px
        font_slogan = int(base_font_size * 0.75 * 2.25) # 调整为 225%
        
        # 应用字体
        self.global_font = self.settings_manager.get_Custom_value('global_font', '微软雅黑')
        
        # 1. 标语 - 使用 setStyleSheet 动态更新字体以确保覆盖通用 QLabel 样式
        self.slogan_label.setStyleSheet(f"""
            #sloganLabel {{
                font-family: "{self.current_slogan_font_name}";
                font-size: {font_slogan}px;
                font-weight: bold;
                color: #1A1A1A;
                background: transparent;
                border: none;
            }}
        """)
        
        # 2. 时钟与日期
        self.time_display.setFont(QFont(self.global_font, font_large, QFont.Bold))
        self.date_display.setFont(QFont(self.global_font, font_base + 2))
        self.version_display.setFont(QFont(self.global_font, font_base))
        
        # 3. 标题
        title_font = QFont(self.global_font, font_title, QFont.Bold)
        self.echo_title.setFont(title_font)
        self.intro_title.setFont(title_font)
        
        # 4. 内容与按钮
        content_font = QFont(self.global_font, font_base)
        self.echo_content.setFont(content_font)
        self.intro_label.setFont(content_font)
        
        self.github_btn.setFont(content_font)
        self.update_btn.setFont(content_font)
        self.change_echo_btn.setFont(content_font)
        
        # 5. 在线服务可用性徽章（紧凑横向格式）
        badge_title_font = QFont(self.global_font, font_base, QFont.Bold)
        badge_value_font = QFont(self.global_font, font_base, QFont.Bold)
        badge_content_font = QFont(self.global_font, max(8, font_base - 1))

        # 查找徽章中的标题、圆点和标签
        if hasattr(self, 'network_status_card'):
            for child in self.network_status_card.findChildren(QLabel):
                if child.objectName() == "networkTitle":
                    child.setFont(badge_title_font)
                elif child.objectName() == "latencyValue":
                    child.setFont(badge_value_font)
                elif child.objectName() in ("githubDot", "domesticDot"):
                    child.setFont(QFont(self.global_font, font_base - 2, QFont.Bold))
                else:
                    child.setFont(badge_content_font)
        
        # 调整Logo大小
        self._scale_logo()

        # 按窗口宽度锁定左侧三卡片宽度（避免动画期间被缩窄）
        self._update_left_card_widths()

    def _update_left_card_widths(self):
        """按窗口宽度 × 固定比率实时计算并锁定左侧三卡片宽度

        左侧列原本占网格约 40%（列拉伸权重 4 : 6）。
        此处在动画期间（以及正常情况下）用 setFixedWidth 锁死宽度，
        避免 slogan_label 的 paintEvent 缩放导致网格重新分配空间。
        """
        if not self.parent_window:
            return
        # 左侧列固定占窗口宽度的 40%，并留出主布局左右边距 + 列间距
        margin_total = 40  # main_layout 左右边距 20*2
        available = max(200, self.parent_window.width() - margin_total)
        left_ratio = 0.40  # 与 setColumnStretch(0,4) / setColumnStretch(1,6) 一致
        # 减去一列间距（grid spacing 20）以贴近实际可用宽度
        col_w = int(available * left_ratio)
        col_w = max(160, col_w)
        for card in (self.slogan_card, self.status_card, self.echo_card):
            card.setFixedWidth(col_w)

    def _update_time(self):
        """更新时间显示"""
        now = datetime.now()
        time_str = now.strftime("%H:%M:%S")
        week_days = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        date_str = now.strftime("%Y年%m月%d日 ") + week_days[now.weekday()]
        
        self.time_display.setText(time_str)
        self.date_display.setText(date_str)

    def _load_version_info(self):
        """加载版本信息"""
        version = "未知"
        try:
            if self.parent_window and hasattr(self.parent_window, "version_info"):
                version = self.parent_window.version_info.version()
        except Exception as e:
            debug_logger.output("welcome_page.py", LogLevel.ERROR, f"加载版本信息失败: {e}")
            
        self.version_display.setText(f"程序版本: 【{version}】")

    def _check_updates(self):
        """检查更新"""
        debug_logger.output("welcome_page.py", LogLevel.INFO, "点击检查更新按钮", fold_code="WELCOME_UI")
        try:
            about_dialog = mp_about.AboutDialog(self)
            about_dialog.on_button_1_clicked()
        except Exception as e:
            debug_logger.output("welcome_page.py", LogLevel.ERROR, f"调用更新方法失败: {e}")

    def _change_slogan_font(self, animate=True):
        """更换标语的中文字体

        Args:
            animate: 是否触发打字机 + 缩放动画（点击时为 True，初始化设为 False）
        """
        if animate:
            self._slogan_font_changed_by_user = True

        valid_fonts = self._slogan_font_families or [self.global_font]
        alternatives = [
            family for family in valid_fonts
            if family != self.current_slogan_font_name
        ]
        self.current_slogan_font_name = random.choice(alternatives or valid_fonts)
        debug_logger.output("welcome_page.py", LogLevel.INFO, f"Slogan font changed to: {self.current_slogan_font_name}", fold_code="WELCOME_FONT")
        self._update_fonts()

        # 触发输入动画：打字机逐字显示 + 轻微缩放反馈
        if animate:
            full_text = self.slogan_label._full_text
            self.slogan_label.play_typewriter(text=full_text, interval_ms=55)
            self.slogan_label.play_pop(peak=1.18, duration_ms=400)

    def _start_slogan_font_discovery(self):
        """Scan the local Qt font database once without blocking the UI."""
        if self._slogan_font_discovery_started:
            return
        self._slogan_font_discovery_started = True
        threading.Thread(
            target=self._discover_slogan_fonts_task,
            daemon=True,
            name="slogan-font-discovery",
        ).start()

    def _discover_slogan_fonts_task(self):
        try:
            font_families = discover_chinese_font_families()
            self.slogan_fonts_loaded.emit(font_families)
        except RuntimeError:
            # The page may have been destroyed while the background scan ran.
            return
        except Exception as error:
            debug_logger.output(
                "welcome_page.py",
                LogLevel.WARNING,
                f"Failed to discover Chinese fonts: {error}",
                fold_code="WELCOME_FONT",
            )

    def _on_slogan_fonts_loaded(self, font_families):
        if self._closing or not font_families:
            return
        self._slogan_font_families = list(font_families)
        debug_logger.output(
            "welcome_page.py",
            LogLevel.INFO,
            f"Discovered {len(font_families)} Chinese slogan fonts",
            fold_code="WELCOME_FONT",
        )
        if not self._slogan_font_changed_by_user:
            self._change_slogan_font(animate=False)
    
    def _start_async_loading(self):
        """开始异步加载网络数据"""
        debug_logger.output("welcome_page.py", LogLevel.INFO, "Starting asynchronous data loading...", fold_code="WELCOME_ASYNC")
        # 1. 加载 Logo
        logo_url = get_resource_url('logo')
        logo_path = os.path.join(self.cache_dir, "logo_banner.png")
        if os.path.exists(logo_path):
            debug_logger.output("welcome_page.py", LogLevel.INFO, "Using cached logo banner", fold_code="WELCOME_ASYNC")
            self._display_logo(logo_path)
        else:
            self._download_image_async(logo_url, logo_path, "logo")
            
        # 2. 加载回声树洞
        threading.Thread(target=self._fetch_echo_zen_task, daemon=True).start()
        
        # 3. 加载公告
        threading.Thread(target=self._fetch_intro_task, daemon=True).start()

    def _get_download_url(self, original_url):
        """获取下载URL (支持加速)"""
        try:
            github_acceleration = self.settings_manager.get_github_acceleration()
        except:
            github_acceleration = 0
        
        final_url = original_url
        
        # 根据资源源进行不同的 URL 转换
        from resource_urls import ResourceURLManager
        current_source = ResourceURLManager.get_current_source()
        
        if current_source == 'github':
            # GitHub: 将 blob URL 转换为 raw URL
            if "github.com" in original_url and "blob" in original_url:
                final_url = original_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
        elif current_source == 'gitee':
            # Gitee: 将 blob URL 转换为 raw URL
            if "gitee.com" in original_url and "blob" in original_url:
                final_url = original_url.replace("/blob/", "/raw/")
        elif current_source == 'custom':
            # Custom: 自建源的 URL 转换（待实现）
            # 等官网建好后根据实际 URL 格式修改
            pass
        
        # 应用镜像加速（仅 GitHub）
        if current_source == 'github' and github_acceleration > 0:
            mirrors = {
                1: "https://ghfast.top/",
                2: "https://gh-proxy.org/",
                3: "https://hk.gh-proxy.org/",
                4: "https://edgeone.gh-proxy.org/"
            }
            mirror_prefix = mirrors.get(github_acceleration, "")
            if mirror_prefix:
                final_url = mirror_prefix + final_url
        
        return final_url

    def _download_image_async(self, url, local_path, tag):
        """异步下载图片"""
        def task():
            try:
                final_url = self._get_download_url(url)
                debug_logger.output("welcome_page.py", LogLevel.INFO, f"Downloading image ({tag}) from: {final_url}", fold_code="WELCOME_ASYNC")
                response = requests.get(final_url, timeout=10)
                if response.status_code == 200:
                    with open(local_path, 'wb') as f:
                        f.write(response.content)
                    debug_logger.output("welcome_page.py", LogLevel.INFO, f"Image downloaded successfully: {tag}", fold_code="WELCOME_ASYNC")
                    self.image_downloaded.emit(tag, local_path)
                else:
                    debug_logger.output("welcome_page.py", LogLevel.WARNING, f"Failed to download image ({tag}), status code: {response.status_code}", fold_code="WELCOME_ASYNC")
            except Exception as e:
                debug_logger.output("welcome_page.py", LogLevel.ERROR, f"Error downloading image ({tag}): {str(e)}", fold_code="WELCOME_ASYNC")
        
        threading.Thread(target=task, daemon=True).start()

    def _fetch_echo_zen_task(self):
        """获取回声树洞"""
        try:
            url = get_resource_url('doc', 'echo_zen')
            debug_logger.output("welcome_page.py", LogLevel.INFO, "Fetching echo zen quotes...", fold_code="WELCOME_ASYNC")
            response = requests.get(url, timeout=10)
            response.encoding = 'utf-8'
            if response.status_code == 200:
                import re
                text = re.sub('<[^<]+?>', '', response.text)
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                if lines:
                    debug_logger.output("welcome_page.py", LogLevel.INFO, f"Fetched {len(lines)} echo zen quotes", fold_code="WELCOME_ASYNC")
                    self.echo_zen_loaded.emit(lines)
            else:
                debug_logger.output("welcome_page.py", LogLevel.WARNING, f"Failed to fetch echo zen, status code: {response.status_code}", fold_code="WELCOME_ASYNC")
        except Exception as e:
            debug_logger.output("welcome_page.py", LogLevel.ERROR, f"Error fetching echo zen: {str(e)}", fold_code="WELCOME_ASYNC")

    def _fetch_intro_task(self):
        """获取公告"""
        try:
            url = get_resource_url('doc', 'intro')
            debug_logger.output("welcome_page.py", LogLevel.INFO, "Fetching program intro...", fold_code="WELCOME_ASYNC")
            response = requests.get(url, timeout=10)
            response.encoding = 'utf-8'
            if response.status_code == 200:
                import re
                text = re.sub('<[^<]+?>', '', response.text)
                debug_logger.output("welcome_page.py", LogLevel.INFO, "Program intro fetched successfully", fold_code="WELCOME_ASYNC")
                self.intro_loaded.emit(text.strip())
            else:
                debug_logger.output("welcome_page.py", LogLevel.WARNING, f"Failed to fetch intro, status code: {response.status_code}", fold_code="WELCOME_ASYNC")
        except Exception as e:
            debug_logger.output("welcome_page.py", LogLevel.ERROR, f"Error fetching intro: {str(e)}", fold_code="WELCOME_ASYNC")

    def _on_intro_loaded(self, text):
        self.intro_text = text
        self.intro_label.setText(text)

    def _on_echo_zen_loaded(self, lines):
        self.echo_zen_lines = lines
        self._random_echo_zen()

    def _random_echo_zen(self):
        if self.echo_zen_lines:
            self.echo_content.setText(random.choice(self.echo_zen_lines))

    def _on_image_downloaded(self, tag, path):
        if tag == "logo":
            self._display_logo(path)

    def _display_logo(self, path):
        """显示Logo图片"""
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            # 保存原始pixmap供后续缩放使用
            self.original_logo_pixmap = pixmap
            # 初始缩放
            self._scale_logo()
    
    def _scale_logo(self):
        """根据当前窗口大小缩放Logo"""
        if self.original_logo_pixmap is None or self.original_logo_pixmap.isNull():
            return
        
        if not self.parent_window:
            # 如果没有父窗口，使用默认高度
            scaled_pixmap = self.original_logo_pixmap.scaledToHeight(180, Qt.SmoothTransformation)
            self.logo_label.setPixmap(scaled_pixmap)
            self.logo_label.setText("")
            return
        
        # 根据窗口大小计算Logo高度
        current_height = self.parent_window.height()
        default_height = 720
        
        # Logo高度基准为180px，随窗口高度缩放
        base_logo_height = 180
        height_ratio = current_height / default_height
        logo_height = int(base_logo_height * height_ratio)
        
        # 限制Logo高度范围（最小120px，最大300px）
        logo_height = max(120, min(300, logo_height))
        
        # 缩放Logo
        scaled_pixmap = self.original_logo_pixmap.scaledToHeight(logo_height, Qt.SmoothTransformation)
        self.logo_label.setPixmap(scaled_pixmap)
        self.logo_label.setText("")
        
        # 更新Logo标签的最小高度
        self.logo_label.setMinimumHeight(logo_height)
        
        debug_logger.output("welcome_page.py", LogLevel.DEBUG, 
                          f"Logo缩放: 高度={logo_height}px (比例={height_ratio:.2f})", 
                          fold_code="WELCOME_LOGO")

    def _reload_page(self, settings_data):
        """重新加载页面以应用最新设置"""
        debug_logger.output("welcome_page.py", LogLevel.INFO, "Reloading WelcomePage with new settings...", fold_code="WELCOME_RELOAD")
        try:
            # 更新颜色设置
            if settings_data:
                if 'global_font' in settings_data:
                    self.global_font = settings_data['global_font']
                if 'background_color' in settings_data:
                    self.bg_color = settings_data['background_color']
                
            self._apply_styles()
            self._update_fonts()
        except Exception as e:
            debug_logger.output("welcome_page.py", LogLevel.ERROR, f"欢迎页面重新加载失败: {e}", fold_code="WELCOME_RELOAD")

    def _on_settings_changed_from_shared_memory(self, page_name, settings_data):
        """从共享内存接收设置变化"""
        # 如果是个性化设置更改，或者包含背景颜色、卡片背景颜色、文字颜色更改
        if page_name in ["custom", "custom_page"] or any(k in settings_data for k in ["background_color", "card_background_color", "text_color"]):
            debug_logger.output("welcome_page.py", LogLevel.INFO, f"Settings change received from shared memory (source: {page_name})", fold_code="WELCOME_RELOAD")
            self._reload_page(settings_data)
    
    def _on_latency_updated(self, server_name, latency_ms, success, status):
        """网络延迟更新回调
        
        Args:
            server_name: 服务器名称 ('baidu' 或 'github')
            latency_ms: 延迟毫秒数
            success: 是否成功连接
            status: 状态描述 ('正常', '超时', 'DNS错误', '错误')
        """
        if self._closing:
            return
        # 根据状态设置显示文本和颜色
        if not success:
            color = "#E74C3C"  # 红色 - 失败
            if status == "超时":
                text = "超时"
            elif status == "DNS错误":
                text = "DNS错误"
            else:
                text = "连接失败"
        elif latency_ms < 100:
            color = "#27AE60"  # 绿色 - 良好
            text = f"{latency_ms}ms"
        elif latency_ms < 300:
            color = "#F39C12"  # 橙色 - 一般
            text = f"{latency_ms}ms"
        else:
            color = "#E74C3C"  # 红色 - 较差
            text = f"{latency_ms}ms"
        
        # 更新对应的标签
        if server_name == 'github':
            self.github_latency.setText(text)
            self.github_latency.setStyleSheet(f"font-weight: bold; color: {color};")
        elif server_name == 'baidu':
            self.domestic_latency.setText(text)
            self.domestic_latency.setStyleSheet(f"font-weight: bold; color: {color};")
        
        debug_logger.output("welcome_page.py", LogLevel.DEBUG, 
                          f"更新 {server_name} 延迟显示: {text} ({color})", 
                          fold_code="WELCOME_NET")
    
    def closeEvent(self, event):
        """窗口关闭事件 - 停止网络检测"""
        self._closing = True
        if hasattr(self, 'latency_checker'):
            self.latency_checker.stop_checking()
            QApplication.processEvents()
        super().closeEvent(event)

# coding=utf-8
import os
import random
import requests
import threading
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QGridLayout, QScrollArea, QFrame,
    QSizePolicy, QApplication, QSpacerItem, QToolButton
)
from PyQt5.QtCore import Qt, QTimer, QUrl, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QPixmap, QDesktopServices, QFontDatabase, QIcon

from debug_logger import debug_logger, LogLevel
from misc_func import SettingsManager, get_app_base_path
import mp_about

class ClickableLabel(QLabel):
    """可点击的标签，用于切换字体"""
    clicked = pyqtSignal()
    
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

class WelcomePage(QWidget):
    # 用于异步更新UI的信号
    intro_loaded = pyqtSignal(str)
    echo_zen_loaded = pyqtSignal(list)
    image_downloaded = pyqtSignal(str, str) # tag, local_path

    def __init__(self, parent=None):
        super().__init__(parent)
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
        
        # 获取版本信息
        self._load_version_info()
        
        # 异步加载数据
        self._start_async_loading()
        
        # 随机切换标语字体
        self._change_slogan_font()

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
        
        # 1. 顶部 Logo 横幅
        self.logo_card = QFrame()
        self.logo_card.setStyleSheet("background-color: transparent; border: none;")
        logo_layout = QVBoxLayout(self.logo_card)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        
        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.logo_label.setMinimumHeight(180)
        self.logo_label.setText("正在获取 Logo...")
        logo_layout.addWidget(self.logo_label)
        self.main_layout.addWidget(self.logo_card)
        
        # 2. 中间内容网格
        content_widget = QWidget()
        self.grid_layout = QGridLayout(content_widget)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(20)
        
        # 2.1 标语卡片 (左上)
        self.slogan_card = QFrame()
        self.slogan_card.setObjectName("whiteCard")
        slogan_layout = QVBoxLayout(self.slogan_card)
        self.slogan_label = ClickableLabel("源悦TTS，与你共鸣。")
        self.slogan_label.setAlignment(Qt.AlignCenter)
        self.slogan_label.clicked.connect(self._change_slogan_font)
        slogan_layout.addWidget(self.slogan_label)
        self.grid_layout.addWidget(self.slogan_card, 0, 0)
        
        # 2.2 导航按钮卡片 (右上)
        self.nav_card = QFrame()
        self.nav_card.setObjectName("whiteCard")
        nav_layout = QHBoxLayout(self.nav_card)
        nav_layout.setContentsMargins(15, 15, 15, 15)
        nav_layout.setSpacing(20)
        
        self.btn_dictation = self._create_nav_button("听写", "https://CN-Air84.github.io/YuanYue-TTS/ico/Dictation.png", 1)
        self.btn_settings = self._create_nav_button("设置", "https://CN-Air84.github.io/YuanYue-TTS/ico/Settings.png", 2)
        self.btn_misc = self._create_nav_button("杂项", "https://CN-Air84.github.io/YuanYue-TTS/ico/Misc.png", 4)
        
        nav_layout.addWidget(self.btn_dictation)
        nav_layout.addWidget(self.btn_settings)
        nav_layout.addWidget(self.btn_misc)
        self.grid_layout.addWidget(self.nav_card, 0, 1)
        
        # 2.3 状态卡片 (左中 - 时钟)
        self.status_card = QFrame()
        self.status_card.setObjectName("whiteCard")
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
        
        # 2.4 回声树洞卡片 (左下)
        self.echo_card = QFrame()
        self.echo_card.setObjectName("whiteCard")
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
        
        echo_layout.addWidget(self.echo_title)
        echo_layout.addWidget(self.echo_content)
        echo_layout.addWidget(self.change_echo_btn, 0, Qt.AlignRight)
        self.grid_layout.addWidget(self.echo_card, 2, 0)
        
        # 2.5 程序简介卡片 (右侧大卡片)
        self.intro_card = QFrame()
        self.intro_card.setObjectName("whiteCard")
        intro_layout = QVBoxLayout(self.intro_card)
        
        self.intro_title = QLabel("程序简介")
        self.intro_title.setObjectName("introTitle")
        self.intro_title.setStyleSheet("font-weight: bold; font-size: 18px; color: #333;")
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background-color: transparent; border: none;")
        
        self.intro_label = QLabel("正在从网络获取简介...")
        self.intro_label.setWordWrap(True)
        self.intro_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.intro_label.setStyleSheet("line-height: 1.5; color: #444;")
        self.scroll_area.setWidget(self.intro_label)
        
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
        self.github_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/CN-Air84/YuanYue-TTS")))
        
        self.update_btn = QPushButton("检查更新")
        self.update_btn.clicked.connect(self._check_updates)
        
        btns_row.addStretch()
        btns_row.addWidget(self.github_btn)
        btns_row.addWidget(self.update_btn)
        
        info_footer_container.addLayout(version_row)
        info_footer_container.addLayout(btns_row)
        
        intro_layout.addWidget(self.intro_title)
        intro_layout.addWidget(self.scroll_area)
        intro_layout.addLayout(info_footer_container)
        
        self.grid_layout.addWidget(self.intro_card, 1, 1, 2, 1)
        
        # 设置权重 - 标语(Row0)和树洞(Row2)高度减到80%，时钟(Row1)加高
        # 原先: Row 0: 1, Row 1: 2, Row 2: 2
        # 调整后: Row 0: 0.8, Row 1: 2.4, Row 2: 1.6
        self.grid_layout.setColumnStretch(0, 4)
        self.grid_layout.setColumnStretch(1, 6)
        self.grid_layout.setRowStretch(0, 8)  # 0.8 * 10
        self.grid_layout.setRowStretch(1, 24) # 2.4 * 10
        self.grid_layout.setRowStretch(2, 16) # 1.6 * 10
        
        self.main_layout.addWidget(content_widget)
        
        self._apply_styles()

    def _create_nav_button(self, text, icon_url, tab_index):
        """创建导航按钮 - 图标在文字上方"""
        btn = QToolButton()
        btn.setText(text)
        btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        btn.setFixedSize(110, 110)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda: self._switch_tab(tab_index))
        btn.setObjectName("navButton")
        
        # 异步下载图标
        icon_path = os.path.join(self.cache_dir, f"{text}.png")
        if os.path.exists(icon_path):
            btn.setIcon(QIcon(icon_path))
            btn.setIconSize(QSize(48, 48))
        else:
            self._download_image_async(icon_url, icon_path, f"icon_{text}")
            
        return btn

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
            /* 导航按钮样式 */
            QToolButton#navButton {{
                background-color: transparent;
                border: none;
                border-radius: 12px;
                font-weight: bold;
                color: {text_color};
                font-family: "{self.global_font}";
                padding: 5px;
            }}
            QToolButton#navButton:hover {{
                background-color: rgba(255, 255, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.3);
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
        
        # 5. 导航按钮
        nav_font = QFont(self.global_font, font_base + 2, QFont.Bold)
        self.btn_dictation.setFont(nav_font)
        self.btn_settings.setFont(nav_font)
        self.btn_misc.setFont(nav_font)
        
        # 调整导航按钮图标大小 - 放大为原先的 133%
        icon_size = int(48 * 1.33 * ratio)
        self.btn_dictation.setIconSize(QSize(icon_size, icon_size))
        self.btn_settings.setIconSize(QSize(icon_size, icon_size))
        self.btn_misc.setIconSize(QSize(icon_size, icon_size))
        
        # 调整按钮大小
        btn_size = int(110 * ratio)
        self.btn_dictation.setFixedSize(btn_size, btn_size)
        self.btn_settings.setFixedSize(btn_size, btn_size)
        self.btn_misc.setFixedSize(btn_size, btn_size)

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

    def _switch_tab(self, index):
        """切换选项卡"""
        debug_logger.output("welcome_page.py", LogLevel.INFO, f"点击导航按钮，尝试切换到 Tab 索引: {index}", fold_code="WELCOME_UI")
        if self.parent_window and hasattr(self.parent_window, 'tab_manager'):
            self.parent_window.tab_manager.switch_to_tab(index)

    def _check_updates(self):
        """检查更新"""
        debug_logger.output("welcome_page.py", LogLevel.INFO, "点击检查更新按钮", fold_code="WELCOME_UI")
        try:
            about_dialog = mp_about.AboutDialog(self)
            about_dialog.on_button_1_clicked()
        except Exception as e:
            debug_logger.output("welcome_page.py", LogLevel.ERROR, f"调用更新方法失败: {e}")

    def _change_slogan_font(self):
        """更换标语的中文字体"""
        chinese_fonts = [
            "微软雅黑", "Microsoft YaHei", "宋体", "SimSun", "黑体", "SimHei", 
            "楷体", "KaiTi", "仿宋", "FangSong", "新宋体", "NSimSun",
            "华文宋体", "STSong", "华文黑体", "STHeiti", "华文楷体", "STKaiti",
            "华文仿宋", "STFangsong", "Arial Unicode MS"
        ]
        font_db = QFontDatabase()
        available = font_db.families()
        valid_fonts = [f for f in chinese_fonts if f in available]
        
        if not valid_fonts:
            valid_fonts = ["Arial", "Helvetica", "Sans-serif"]
            
        self.current_slogan_font_name = random.choice(valid_fonts)
        debug_logger.output("welcome_page.py", LogLevel.INFO, f"Slogan font changed to: {self.current_slogan_font_name}", fold_code="WELCOME_FONT")
        self._update_fonts()
    
    def _start_async_loading(self):
        """开始异步加载网络数据"""
        debug_logger.output("welcome_page.py", LogLevel.INFO, "Starting asynchronous data loading...", fold_code="WELCOME_ASYNC")
        # 1. 加载 Logo
        logo_url = "https://github.com/CN-Air84/YuanYue-TTS/blob/main/docs/icon_full_1080%20_inside.png?raw=true"
        logo_path = os.path.join(self.cache_dir, "logo_banner.png")
        if os.path.exists(logo_path):
            debug_logger.output("welcome_page.py", LogLevel.INFO, "Using cached logo banner", fold_code="WELCOME_ASYNC")
            self._display_logo(logo_path)
        else:
            self._download_image_async(logo_url, logo_path, "logo")
            
        # 2. 加载回声树洞
        threading.Thread(target=self._fetch_echo_zen_task, daemon=True).start()
        
        # 3. 加载程序简介
        threading.Thread(target=self._fetch_intro_task, daemon=True).start()

    def _get_download_url(self, original_url):
        """获取下载URL (支持加速)"""
        try:
            github_acceleration = self.settings_manager.get_github_acceleration()
        except:
            github_acceleration = 0
        
        final_url = original_url
        if "github.com" in original_url and "blob" in original_url:
            final_url = original_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
        
        mirrors = {
            1: "https://ghfast.top/",
            2: "https://gh-proxy.org/",
            3: "https://hk.gh-proxy.org/",
            4: "https://edgeone.gh-proxy.org/"
        }
        return mirrors.get(github_acceleration, "") + final_url

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
            url = "https://CN-Air84.github.io/YuanYue-TTS/docs/echo_zen.html"
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
        """获取程序简介"""
        try:
            url = "https://CN-Air84.github.io/YuanYue-TTS/docs/intro.html"
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
        elif tag.startswith("icon_"):
            btn_name = tag.replace("icon_", "")
            icon = QIcon(path)
            if btn_name == "听写":
                self.btn_dictation.setIcon(icon)
            elif btn_name == "设置":
                self.btn_settings.setIcon(icon)
            elif btn_name == "杂项":
                self.btn_misc.setIcon(icon)
            # 图标大小在 _update_fonts 中统一处理

    def _display_logo(self, path):
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            # 缩放到 Logo 标签高度
            scaled_pixmap = pixmap.scaledToHeight(180, Qt.SmoothTransformation)
            self.logo_label.setPixmap(scaled_pixmap)
            self.logo_label.setText("")

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

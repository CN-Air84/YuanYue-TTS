# coding=utf-8
import os
import sys
import requests
import time
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QHBoxLayout, QWidget, 
    QPushButton, QGridLayout, QMessageBox, QApplication
)
from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QFont, QPixmap, QDesktopServices
from debug_logger import debug_logger, LogLevel

try:
    from misc_func import SettingsManager, get_app_base_path
    SETTINGS_AVAILABLE = True
except ImportError:
    SETTINGS_AVAILABLE = False
    # 如果导入失败，定义一个后备方案
    def get_app_base_path():
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(__file__))

try:
    from iw_dialogs import LoadingDialog
    DIALOGS_AVAILABLE = True
except ImportError:
    DIALOGS_AVAILABLE = False

# 关于页面按钮文字和链接
ABOUT_BUTTON_TEXTS = ["Github主页", "Github更新", "", "", "", ""]
ABOUT_BUTTON_URLS = [
    "https://github.com/CN-Air84/YuanYue-TTS",
    "https://github.com/CN-Air84/YuanYue-TTS/releases",
    "",
    "",
    "",
    ""
]

class AboutDialog(QDialog):
    """关于对话框 - 显示程序信息和开发者信息"""
    
    def __init__(self, parent=None):
        """
        初始化关于对话框
        
        Args:
            parent: 父窗口
        """
        super().__init__(parent)
        debug_logger.output("mp_about.py", LogLevel.INFO, "正在初始化关于对话框", fold_code="ABOUT_INIT")
        self.parent_window = parent
        self.setWindowTitle("关于")
        self.resize(1080, 1200)
        self.setFixedSize(1080, 1080)
        
        # 初始化缓存相关属性
        self._cached_release_info = None
        self._cache_timeout = 300  # 5分钟缓存
        
        self._get_version_info()
        
        from misc_func import SettingsManager
        settings_manager = SettingsManager()
        self.global_font = settings_manager.get_Custom_value('global_font', '微软雅黑')
        self.min_font_size = int(settings_manager.get_Custom_value('min_font_size', '22'))
        self.max_font_size = int(settings_manager.get_Custom_value('max_font_size', '42'))
        
        background_color_hex = settings_manager.get_Custom_value('background_color', '#E5E8EF')
        self.text_color = settings_manager.get_Custom_value('text_color', '#333333')
        
        # 连接设置变更信号
        if hasattr(self.parent_window, 'shared_memory_manager'):
            self.parent_window.shared_memory_manager.settings_changed.connect(self._on_settings_changed)
        
        r = int(background_color_hex[1:3], 16)
        g = int(background_color_hex[3:5], 16)
        b = int(background_color_hex[5:7], 16)
        r = min(255, r + 16)
        g = min(255, g + 16)
        b = min(255, b + 16)
        self.left_background_color = f"#{r:02x}{g:02x}{b:02x}"
        
        self.image_url = "https://github.com/CN-Air84/YuanYue-TTS/blob/main/docs/icon_full_1080%20_inside.png?raw=true"
        self.cache_dir = os.path.join(get_app_base_path(), "cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.image_path = os.path.join(self.cache_dir, "icon_full_1080.png")
        
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # 移除了标题，直接显示图片和内容
        
        # 图片显示区域
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setFixedHeight(300)
        layout.addWidget(self.image_label)
        
        # 图片和正文之间的间距 - 原来的1/3
        image_content_spacer = QWidget()
        image_content_spacer.setFixedHeight(0)  # 原来是弹性的，现在用固定小间距
        layout.addWidget(image_content_spacer)
        
        # 正文区域 - 左右布局
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)
        
        # 左侧主要介绍
        left_content_text = (
            "源悦TTS，\n"
            "一款以学生为本、由学生研发、为学生而生的文本转语音程序。\n"
            '——————————————————\n'
            '大部分外围设施（尤其是官网）还未准备好，望各位谅解。\n'
            '此版本为测试版，仍有部分功能未适配/实现，望各位谅解。\n'
            '——————————————————\n'
            '我们接受但不推荐您以金钱赞助本程序。\n点个Star或者Fork来支持我们吧！\n'
            '——————————————————\n'
            #'您可以查看\ngithub.com/CN-Air84/CN-Air84/blob/main/README.md\n以加入我们的开发组或内测用户团。\n'
            #'目前开发组或用户团不计划扩招。\n'
            #'——————————————————\n'
            '本程序修改了并使用知名开源项目tchMaterial_parser，\n也即国家中小学智慧教育平台电子课本下载工具的相关代码。\n感谢原作者happycola233的贡献。\n'
            '——————————————————\n'
            '您可以在项目主页找到本程序的所有相关信息，\n包括使用说明、更新日志、源代码等。\n'
            '本项目基于Apache2.0协议开源，\n您可在遵守协议前提下自由使用、修改和分发本程序及源码。'
        )
        self.left_content_label = QLabel(left_content_text)
        self.left_content_label.setAlignment(Qt.AlignCenter)
        self.left_content_label.setWordWrap(True)
        content_layout.addWidget(self.left_content_label)
        
        # 右侧版本信息
        right_content_text = (
            f"by Air84\n"
            f"版本号:{self.version}\n"
            f"更新日期:{self.version_date}\n"
            f"更新内容:\n{self.update_content}"
        )
        
        self.right_content_label = QLabel(right_content_text)
        self.right_content_label.setAlignment(Qt.AlignCenter)
        self.right_content_label.setWordWrap(True)
        self.right_content_label.setMaximumWidth(int(self.width() / 3))
        content_layout.addWidget(self.right_content_label)
        
        layout.addLayout(content_layout)
        
        # 下方弹簧，让按钮在底部
        layout.addStretch(1)

        # 按钮区域
        button_layout = QGridLayout()
        self.buttons = []
        
        for i, text in enumerate(ABOUT_BUTTON_TEXTS):
            button = QPushButton(text)
            row = i // 2
            col = i % 2
            button_layout.addWidget(button, row, col)
            self.buttons.append(button)
            
            if i == 0:
                button.clicked.connect(self.on_button_0_clicked)
            elif i == 1:
                button.clicked.connect(self.on_button_1_clicked)
            elif i == 2:
                button.clicked.connect(self.on_button_2_clicked)
            elif i == 3:
                button.clicked.connect(self.on_button_3_clicked)
            elif i == 4:
                button.clicked.connect(self.on_button_4_clicked)
            elif i == 5:
                button.clicked.connect(self.on_button_5_clicked)
        
        layout.addLayout(button_layout)
        
        # 关闭按钮
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)
        # 将关闭按钮添加到 self.buttons 以便统一更新样式
        self.buttons.append(close_button)
        
        self.setLayout(layout)
        
        # 应用动态样式
        self._apply_dynamic_styles()
        
        # 加载图片
        self._load_about_image()
        
        self._update_fonts()
    
    def _on_settings_changed(self, section, key, value):
        """处理设置变更"""
        if section == 'Custom' and key == 'text_color':
            self.text_color = value
            self._apply_dynamic_styles()

    def _apply_dynamic_styles(self):
        """应用动态样式（主要用于文字颜色更新）"""
        debug_logger.output("mp_about.py", LogLevel.INFO, "正在应用关于对话框动态样式", fold_code="ABOUT_UI")
        from misc_func import SettingsManager
        settings_manager = SettingsManager()
        background_color_hex = settings_manager.get_Custom_value('background_color', '#E5E8EF')
        
        self.setStyleSheet(f"""
            QDialog {{background-color: {background_color_hex};}}
            QPushButton {{
                font-family: "{self.global_font}"; background-color: white; color: {self.text_color};
                border: 2px solid gray; border-radius: 5px; font-weight: bold; padding: 5px;
            }}
            QPushButton:hover {{background-color: #f0f0f0;}}
            QLabel {{font-family: "{self.global_font}"; background-color: transparent; color: {self.text_color};}}
        """)
        
        if hasattr(self, 'image_label'):
            self.image_label.setStyleSheet(f"background-color: {self.left_background_color}; border-radius: 15px;")
            
        if hasattr(self, 'left_content_label'):
            self.left_content_label.setStyleSheet(f"""
                QLabel {{
                    background-color: {self.left_background_color};
                    color: {self.text_color};
                    border-radius: 15px;
                    padding: 20px;
                }}
            """)
            
        if hasattr(self, 'right_content_label'):
            self.right_content_label.setStyleSheet(f"""
                QLabel {{
                    background-color: white;
                    color: {self.text_color};
                    border-radius: 15px;
                    padding: 20px;
                }}
            """)
            
        if hasattr(self, 'buttons'):
            for button in self.buttons:
                button.setStyleSheet(f"""
                    QPushButton {{
                        font-family: "{self.global_font}"; background-color: white; color: {self.text_color};
                        border: 2px solid gray; border-radius: 5px; font-weight: bold; padding: 8px;
                    }}
                    QPushButton:hover {{background-color: #f0f0f0;}}
                """)

    def _load_about_image(self):
        """加载关于页面图片"""
        if os.path.exists(self.image_path):
            self._display_image()
        else:
            self._download_image()
    
    def _download_image(self):
        """后台静默下载图片"""
        debug_logger.output("mp_about.py", LogLevel.INFO, f"尝试下载关于页面图片: {self.image_url}", fold_code="ABOUT_IMG")
        def download_thread():
            try:
                final_url = self._get_download_url(self.image_url)
                debug_logger.output("mp_about.py", LogLevel.INFO, f"正在从 {final_url} 下载图片", fold_code="ABOUT_IMG")
                response = requests.get(final_url, timeout=30)
                if response.status_code == 200:
                    with open(self.image_path, 'wb') as f:
                        f.write(response.content)
                    debug_logger.output("mp_about.py", LogLevel.INFO, f"图片下载成功并保存至: {self.image_path}", fold_code="ABOUT_IMG")
                    QTimer.singleShot(0, self._display_image)
                else:
                    debug_logger.output("mp_about.py", LogLevel.WARNING, f"下载图片失败，状态码: {response.status_code}", fold_code="ABOUT_IMG")
            except Exception as e:
                debug_logger.output("mp_about.py", LogLevel.ERROR, f"下载图片过程中发生异常: {str(e)}", fold_code="ABOUT_IMG")
        
        import threading
        thread = threading.Thread(target=download_thread, daemon=True)
        thread.start()
    
    def _display_image(self):
        """显示图片"""
        debug_logger.output("mp_about.py", LogLevel.INFO, "正在显示关于页面图片", fold_code="ABOUT_IMG")
        if os.path.exists(self.image_path):
            pixmap = QPixmap(self.image_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(1080, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.image_label.setPixmap(scaled_pixmap)
                debug_logger.output("mp_about.py", LogLevel.INFO, "图片显示成功", fold_code="ABOUT_IMG")
            else:
                debug_logger.output("mp_about.py", LogLevel.WARNING, "图片文件无效，无法显示", fold_code="ABOUT_IMG")
        else:
            debug_logger.output("mp_about.py", LogLevel.WARNING, "图片文件不存在", fold_code="ABOUT_IMG")
    
    def _get_version_info(self):
        """从VersionInfos获取版本信息"""
        debug_logger.output("mp_about.py", LogLevel.INFO, "正在获取版本信息", fold_code="ABOUT_VER")
        self.version = "未知版本"
        self.version_date = "未知日期"
        self.update_content = ""
        
        try:
            import sys
            main_module = sys.modules.get('__main__')
            if hasattr(main_module, 'version_info'):
                version_info = main_module.version_info
                print_source = "__main__"
            else:
                try:
                    from main_window_package import version_info
                    print_source = "main_window_package"
                except ImportError:
                    from main_window import version_info
                    print_source = "main_window"
            
            self.version = version_info.version()
            self.version_date = version_info.update_date()
            self.update_content = version_info.update_content()
            debug_logger.output("mp_about.py", LogLevel.INFO, f"从 {print_source} 获取到版本: {self.version}", fold_code="ABOUT_VER")
        except Exception as e:
            debug_logger.output("mp_about.py", LogLevel.WARNING, f"无法获取版本信息: {e}", fold_code="ABOUT_VER")
    
    def _update_fonts(self):
        """更新界面字体大小"""
        current_width = self.width()
        current_height = self.height()
        debug_logger.output("mp_about.py", LogLevel.INFO, f"正在更新关于对话框字体, 尺寸: {current_width}x{current_height}", fold_code="ABOUT_UI")
        
        DEFAULT_WIDTH = 1280
        DEFAULT_HEIGHT = 1080
        MIN_FONT_SIZE = self.min_font_size
        MAX_FONT_SIZE = self.max_font_size
        
        width_ratio = current_width / DEFAULT_WIDTH
        height_ratio = current_height / DEFAULT_HEIGHT
        ratio = (width_ratio + height_ratio) / 2
        
        base_font_size = (MIN_FONT_SIZE + 
                         (MAX_FONT_SIZE - MIN_FONT_SIZE) * (ratio - 1))
        base_font_size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, base_font_size))
        
        base_font_size = int(base_font_size)
        font_size = int(base_font_size * 0.48)
        title_font_size = int(font_size * 1.5)
        
        # title_font = QFont(self.global_font, title_font_size)
        # title_font.setBold(True)
        
        content_font = QFont(self.global_font, font_size)
        button_font = QFont(self.global_font, font_size)
        
        self.left_content_label.setFont(content_font)
        self.right_content_label.setFont(content_font)
        
        for button in self.buttons:
            button.setFont(button_font)
    
    def open_url(self, index):
        """
        打开指定索引的URL
        
        Args:
            index (int): URL索引
        """
        if index < len(ABOUT_BUTTON_URLS) and ABOUT_BUTTON_URLS[index]:
            QDesktopServices.openUrl(QUrl(ABOUT_BUTTON_URLS[index]))
    
    def on_button_0_clicked(self):
        if ABOUT_BUTTON_URLS[0]:
            QDesktopServices.openUrl(QUrl(ABOUT_BUTTON_URLS[0]))
    
    def get_latest_github_release(self):
        """
        获取GitHub最新版本号和下载链接，跳过包含'pre'的预发布版本
        
        Returns:
            dict: 包含tag_name、browser_download_url、has_pre_release和pre_release_tag_name的字典，失败返回None
        """
        debug_logger.output("mp_about.py", LogLevel.INFO, "正在请求 GitHub 获取最新发布版本", fold_code="ABOUT_GH")
        # 检查缓存是否有效（5分钟内）
        if self._cached_release_info:
            cached_time = self._cached_release_info.get('timestamp', 0)
            if time.time() - cached_time < self._cache_timeout:
                debug_logger.output("mp_about.py", LogLevel.INFO, "使用缓存的 GitHub 版本信息", fold_code="ABOUT_GH")
                return self._cached_release_info
        
        # 首先尝试获取所有发布版本
        url = "https://api.github.com/repos/CN-Air84/YuanYue-TTS/releases"
        try:
            # 添加必要的请求头
            headers = {
                'Accept': 'application/vnd.github+json',
                'User-Agent': 'YuanYue-TTS-Update-Checker'
            }
            
            debug_logger.output("mp_about.py", LogLevel.INFO, f"正在从 {url} 获取发布版本列表", fold_code="ABOUT_GH")
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                releases = response.json()
                debug_logger.output("mp_about.py", LogLevel.INFO, f"成功获取发布版本列表, 共 {len(releases)} 个", fold_code="ABOUT_GH")
                
                # 过滤掉预发布版本，找到最新的稳定版本
                stable_releases = []
                pre_releases = []
                
                for release in releases:
                    tag_name = release.get('tag_name', '')
                    # 检查是否为预发布版本（名称包含'pre'或是prerelease标记）
                    is_pre_release = release.get('prerelease', False) or 'pre' in tag_name.lower()
                    
                    if is_pre_release:
                        pre_releases.append(release)
                    else:
                        stable_releases.append(release)
                
                # 如果没有稳定版本，使用最新的预发布版本
                if not stable_releases and pre_releases:
                    latest_release = pre_releases[0]
                    debug_logger.output("mp_about.py", LogLevel.INFO, f"未找到稳定版本, 使用最新的预发布版本: {latest_release.get('tag_name')}", fold_code="ABOUT_GH")
                elif stable_releases:
                    latest_release = stable_releases[0]
                    debug_logger.output("mp_about.py", LogLevel.INFO, f"找到最新的稳定版本: {latest_release.get('tag_name')}", fold_code="ABOUT_GH")
                else:
                    debug_logger.output("mp_about.py", LogLevel.WARNING, "GitHub 仓库没有任何发布版本", fold_code="ABOUT_GH")
                    return None
                
                # 获取下载链接
                assets = latest_release.get('assets', [])
                download_url = assets[0].get('browser_download_url', '') if assets else ''
                
                # 检查是否有更新的预发布版本
                has_pre_release = bool(pre_releases)
                pre_release_tag_name = pre_releases[0].get('tag_name', '') if pre_releases else ''
                
                # 缓存结果（5分钟）
                self._cached_release_info = {
                    'tag_name': latest_release['tag_name'],
                    'browser_download_url': download_url,
                    'has_pre_release': has_pre_release,
                    'pre_release_tag_name': pre_release_tag_name,
                    'timestamp': time.time()
                }
                
                return self._cached_release_info
                
            elif response.status_code == 403 and 'rate limit' in response.text.lower():
                debug_logger.output("mp_about.py", LogLevel.WARNING, "GitHub API 速率限制, 尝试备用方案", fold_code="ABOUT_GH")
                return self._get_latest_release_fallback()
            else:
                debug_logger.output("mp_about.py", LogLevel.ERROR, f"获取 GitHub 版本信息失败, 状态码: {response.status_code}", fold_code="ABOUT_GH")
                return self._get_latest_release_fallback()
        except Exception as e:
            debug_logger.output("mp_about.py", LogLevel.ERROR, f"获取 GitHub 版本信息异常: {str(e)}", fold_code="ABOUT_GH")
            return self._get_latest_release_fallback()
    
    def _get_latest_release_fallback(self):
        """
        备用方案：使用GitHub的latest端点获取最新版本（速率限制更宽松）
        
        Returns:
            dict: 包含tag_name、browser_download_url、has_pre_release和pre_release_tag_name的字典，失败返回None
        """
        debug_logger.output("mp_about.py", LogLevel.INFO, "正在尝试 GitHub 备用获取方案", fold_code="ABOUT_GH")
        url = "https://api.github.com/repos/CN-Air84/YuanYue-TTS/releases/latest"
        try:
            headers = {
                'Accept': 'application/vnd.github+json',
                'User-Agent': 'YuanYue-TTS-Update-Checker'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                release_info = response.json()
                assets = release_info.get('assets', [])
                download_url = assets[0].get('browser_download_url', '') if assets else ''
                
                # 检查这个最新版本是否为预发布版本
                tag_name = release_info.get('tag_name', '')
                is_pre_release = release_info.get('prerelease', False) or 'pre' in tag_name.lower()
                
                debug_logger.output("mp_about.py", LogLevel.INFO, f"备用方案获取成功: {tag_name}", fold_code="ABOUT_GH")
                return {
                    'tag_name': tag_name,
                    'browser_download_url': download_url,
                    'has_pre_release': is_pre_release,  # 如果最新版本就是预发布版本
                    'pre_release_tag_name': tag_name if is_pre_release else ''
                }
            elif response.status_code == 403:
                debug_logger.output("mp_about.py", LogLevel.ERROR, "GitHub API 速率限制, 备用方案亦无法获取", fold_code="ABOUT_GH")
                return None
            else:
                debug_logger.output("mp_about.py", LogLevel.ERROR, f"备用方案获取失败, 状态码: {response.status_code}", fold_code="ABOUT_GH")
                return None
        except Exception as e:
            debug_logger.output("mp_about.py", LogLevel.ERROR, f"备用方案获取异常: {str(e)}", fold_code="ABOUT_GH")
            return None
    
    def _get_download_url(self, original_url):
        """根据加速选项获取下载URL"""
        debug_logger.output("mp_about.py", LogLevel.INFO, f"正在处理加速 URL: {original_url[:50]}...", fold_code="ABOUT_GH")
        from misc_func import SettingsManager
        settings_manager = SettingsManager()
        github_acceleration = settings_manager.get_github_acceleration() if settings_manager else 0
        
        acc_url = original_url
        if github_acceleration == 1:
            acc_url = f"https://ghfast.top/{original_url}"
        elif github_acceleration == 2:
            acc_url = f"https://gh-proxy.org/{original_url}"
        elif github_acceleration == 3:
            acc_url = f"https://hk.gh-proxy.org/{original_url}"
        elif github_acceleration == 4:
            acc_url = f"https://edgeone.gh-proxy.org/{original_url}"
            
        if acc_url != original_url:
            debug_logger.output("mp_about.py", LogLevel.INFO, f"已应用加速, 最终 URL: {acc_url[:50]}...", fold_code="ABOUT_GH")
        return acc_url
    
    def compare_versions(self, version1, version2):
        """
        比较两个版本号
        
        Args:
            version1 (str): 版本号1
            version2 (str): 版本号2
        
        Returns:
            int: 1表示version1>version2, -1表示version1<version2, 0表示相等, -2表示无法比较(默认无需更新)
        """
        try:
            v1_parts = version1.replace('v', '').split('.')
            v2_parts = version2.replace('v', '').split('.')
            
            max_len = max(len(v1_parts), len(v2_parts))
            v1_parts.extend(['0'] * (max_len - len(v1_parts)))
            v2_parts.extend(['0'] * (max_len - len(v2_parts)))
            
            for v1, v2 in zip(v1_parts, v2_parts):
                try:
                    v1_num = int(v1)
                    v2_num = int(v2)
                    if v1_num > v2_num:
                        return 1
                    elif v1_num < v2_num:
                        return -1
                except (ValueError, TypeError):
                    # 如果无法转换为数字，直接比较字符串
                    if v1 > v2:
                        return 1
                    elif v1 < v2:
                        return -1
            
            return 0
        except Exception:
            # 任何异常都返回-2，表示无法比较，默认无需更新
            return -2
    
    def on_button_1_clicked(self):
        if not DIALOGS_AVAILABLE:
            QMessageBox.warning(self, "错误", "加载对话框模块未找到")
            return
        
        loading_dialog = LoadingDialog(self)
        loading_dialog.text_label.setText("正在检查更新...")
        loading_dialog.show()
        
        QApplication.processEvents()
        
        try:
            release_info = self.get_latest_github_release()
            
            if release_info is None:
                QMessageBox.warning(self, "检查更新", "无法获取最新版本信息，可能是网络连接问题或GitHub API速率限制。\n\n建议：\n1. 检查网络连接\n2. 稍后重试\n3. 手动访问GitHub发布页查看更新")
                return
            
            latest_version = release_info['tag_name']
            download_url = release_info['browser_download_url']
            
            comparison = self.compare_versions(latest_version, self.version)
            
            if comparison == -2:
                # 构建版本检查提示文本
                version_check_text = (f"当前版本：{self.version}\n"
                                    f"最新版本：{latest_version}\n\n"
                                    "版本号格式无法识别，暂不检测更新。\n"
                                    "如有需要，请手动检查项目主页。")
                
                # 如果有预发布版本，添加提示
                if release_info.get('has_pre_release'):
                    version_check_text += "\n（最新release为广泛内测版本，可以前往github发布页进行下载）"
                
                QMessageBox.information(self, "版本检查", version_check_text)
            elif comparison > 0:
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("发现新版本")
                msg_box.setText(f"最新公测版本：{latest_version}\n当前版本：{self.version}\n\n检测结果：发现新版本可用")
                msg_box.setInformativeText("是否立即下载更新？")
                msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                msg_box.setDefaultButton(QMessageBox.Yes)
                
                yes_button = msg_box.button(QMessageBox.Yes)
                yes_button.setText("立即下载")
                
                no_button = msg_box.button(QMessageBox.No)
                no_button.setText("暂不更新")
                
                result = msg_box.exec_()
                
                if result == QMessageBox.Yes:
                    if not download_url:
                        QMessageBox.warning(self, "下载失败", "未找到可用的下载链接。")
                        return
                    
                    try:
                        from multi_thread_downloader import download
                        from misc_func import SettingsManager, get_app_base_path
                        
                        settings_manager = SettingsManager()
                        thread_num = settings_manager.get_download_thread_num() if settings_manager else 5
                        
                        final_download_url = self._get_download_url(download_url)
                        
                        # 使用 get_app_base_path 获取程序实际所在目录，避免 PyInstaller 打包后的 _MEI 路径问题
                        downloads_dir = get_app_base_path()
                        
                        filename = f"{latest_version}.exe"
                        save_path = os.path.join(downloads_dir, filename)
                        
                        success = download(
                            url=final_download_url,
                            save_dir=downloads_dir,
                            filename=filename,
                            thread_num=thread_num,
                            verify_ssl=False
                        )
                        
                        if success:
                            QMessageBox.information(self, "下载完成", f"文件已保存至：\n{save_path}\n\n即将启动新版本...")
                            
                            import subprocess
                            import sys
                            
                            try:
                                subprocess.Popen([save_path])
                                sys.exit(0)
                            except Exception as e:
                                QMessageBox.warning(self, "启动失败", f"文件下载成功，但启动失败：{str(e)}\n\n请手动运行新版本程序。")
                        else:
                            QMessageBox.critical(self, "下载失败", "下载过程中出现错误，请检查网络连接。")
                            
                    except ImportError:
                        QMessageBox.critical(self, "错误", "多线程下载模块未找到")
                    except Exception as e:
                        QMessageBox.critical(self, "错误", f"下载失败：{str(e)}")
            else:
                # 构建"无需更新"提示文本
                no_update_text = f"最新版本：{latest_version}\n当前版本：{self.version}\n\n检测结果：当前已是最新版本"
                
                # 如果有预发布版本，添加提示
                if release_info.get('has_pre_release'):
                    no_update_text += f"\n\n（另：最新发行版为广泛内测版本，可以前往github发布页进行手动下载）"
                
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("检查更新")
                msg_box.setText(no_update_text)
                msg_box.setInformativeText("无需更新")
                msg_box.setStandardButtons(QMessageBox.Ok)
                msg_box.exec_()
        finally:
            loading_dialog.close()
    
    def on_button_2_clicked(self):
        pass
    
    def on_button_3_clicked(self):
        pass
    
    def on_button_4_clicked(self):
        pass
    
    def on_button_5_clicked(self):
        pass

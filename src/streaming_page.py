# coding=utf-8
import os
import sys
import random
import json
import threading
import time
from collections import deque
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
                             QListWidget, QListWidgetItem, QLabel, QScrollArea, QFrame,
                             QInputDialog, QMessageBox, QMenu, QSlider, QSizePolicy,
                             QGraphicsBlurEffect, QCheckBox, QApplication, QGridLayout,
                             QLayout)
from PyQt5.QtCore import (Qt, pyqtSignal, QSize, QTimer, QRect, QEvent, QPoint, QObject)
from PyQt5.QtGui import (QFont, QIcon, QPainter, QPalette, QFontMetrics, QPixmap,
                         QColor, QPainterPath, QBrush, QPen)
from debug_logger import debug_logger, LogLevel
from music_NCM import MusicSubsystem, MusicTrack
from misc_func import SettingsManager
from shared_memory_manager import get_shared_memory_manager
from responsive_ui import UniformUiScaler
from theme_page_adapter import (
    configure_independent_surface,
    configure_material_overlay,
    configure_semantic_surface,
    configure_theme_card,
    configure_transparent_container,
    configure_transparent_root,
    set_transparent_scroll_content,
)

# 二维码登录所需
try:
    import qrcode
    from io import BytesIO
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False

# 网易云登录 API（延后捕获异常，避免未安装 pyncm 时整个页面无法加载）
try:
    import pyncm
    import pyncm.apis.login
    PYNCM_LOGIN_AVAILABLE = True
except Exception:
    PYNCM_LOGIN_AVAILABLE = False


class QrCodeLoginDialog(QWidget):
    """网易云登录/账号悬浮面板。

    全屏覆盖父窗口：背景半透明黑幕 + 模糊，居中白色卡片。
    两种模式：
      - mode="login"（默认）：左侧 3/4 扫码登录 + 右侧 1/4 账号信息
      - mode="account"：左侧 3/4 账号详情（大头像/昵称/UID/VIP）+ 右侧 1/4 操作按钮

    扫码轮询状态码：
      802 → 等待扫码
      803 → 已扫码，等待手机确认
      800 → 二维码过期
      200 → 登录成功
    """
    # 面板关闭时发射（此时对象仍存活，父级可安全查询登录状态）
    closed = pyqtSignal()
    # 请求从外部切换到登录模式（account 面板中的"切换账号"按钮）
    switch_to_login_requested = pyqtSignal()
    # 请求登出（account 面板中的"登出"按钮）
    logout_requested = pyqtSignal()
    POLL_INTERVAL = 2000
    EXPIRE_SECONDS = 300

    def __init__(self, parent=None, overlay_target=None, mode="login"):
        super().__init__(parent)
        configure_material_overlay(self)
        self.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)
        self.setObjectName("login_overlay")

        self._mode = mode  # "login" | "account"
        self.unikey = ""
        self._elapsed = 0
        self._closing = False    # 正在关闭（避免重复触发）

        # 获取用户配置的全局字体（与 PlaylistManagePanel 保持一致）
        self.settings_manager = SettingsManager()
        self.font_family = self.settings_manager.get_Custom_value("global_font", "微软雅黑")

        # overlay_target：要覆盖的目标 widget（如 stacked_widget）。
        # 悬浮窗的 parent 必须是主窗口（保证 resize 跟随），
        # 但几何跟随 overlay_target（只覆盖内容区，不含 tab 栏）。
        # 若未指定，则退化为覆盖 parent。
        if overlay_target is not None:
            self._overlay_target = overlay_target
        elif parent is not None:
            self._overlay_target = parent
        else:
            self._overlay_target = None

        # —— 自身作为半透明深色遮罩层 ——
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 160);")
        self._apply_target_geometry()

        # —— 外层布局 ——
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setAlignment(Qt.AlignCenter)

        # 卡片：圆角白色面板
        self._card = QFrame()
        configure_theme_card(self._card, preserve_outline=True)
        self._card.setObjectName("login_card")
        self._card.setFixedSize(780, 600)
        self._card.setStyleSheet(f"""
            #login_card {{
                background-color: rgba(255, 255, 255, 252);
                border-radius: 20px;
                font-family: '{self.font_family}';
            }}
        """)
        outer.addWidget(self._card)

        card_layout = QHBoxLayout(self._card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # —— 竖向分隔线 ——
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet("color: #e0e0e0; background: #e0e0e0;")

        # 头像下载线程句柄与缓存（避免重复下载）
        self._avatar_thread = None
        self._last_avatar_url = ""

        # —— 轮询定时器 ——
        self._timer = QTimer(self)
        self._timer.setInterval(self.POLL_INTERVAL)
        self._timer.timeout.connect(self._poll_status)

        # 根据模式构建不同布局
        if self._mode == "account":
            self._build_account_mode(card_layout, sep)
        else:
            self._build_login_mode(card_layout, sep)

        # 卡片置于背景层之上
        self._card.raise_()

        # 监听父窗口（主窗口）的大小变化，使遮罩跟随缩放。
        if parent is not None:
            parent.installEventFilter(self)
        if self._overlay_target is not None and self._overlay_target is not parent:
            self._overlay_target.installEventFilter(self)

    # ==================== 布局构建 ====================

    def _build_login_mode(self, card_layout, sep):
        """构建 login 模式布局：左侧扫码(3/4) + 分隔线 + 右侧信息(1/4)。"""
        # —— 左侧：扫码登录区（占 3/4） ——
        self._qr_panel = QFrame()
        self._qr_panel.setStyleSheet("background: transparent;")
        left_layout = QVBoxLayout(self._qr_panel)
        left_layout.setContentsMargins(45, 45, 22, 45)
        left_layout.setSpacing(21)
        left_layout.setAlignment(Qt.AlignCenter)

        self._title_label = QLabel("扫码登录/切换网易云音乐账号")
        self._title_label.setAlignment(Qt.AlignCenter)
        self._title_label.setStyleSheet(f"font-size: 33px; font-weight: bold; color: #222; background: transparent; font-family: '{self.font_family}';")
        left_layout.addWidget(self._title_label)

        # QR 码显示标签
        self._qr_label = QLabel()
        configure_semantic_surface(self._qr_label)
        self._qr_label.setAlignment(Qt.AlignCenter)
        self._qr_label.setFixedSize(294, 294)
        self._qr_label.setStyleSheet("background: #ffffff; border-radius: 12px;")
        left_layout.addWidget(self._qr_label)

        self._status_label = QLabel("正在生成二维码...")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet(f"font-size: 22px; color: #666; background: transparent; font-family: '{self.font_family}';")
        left_layout.addWidget(self._status_label)

        self._countdown_label = QLabel()
        self._countdown_label.setAlignment(Qt.AlignCenter)
        self._countdown_label.setStyleSheet(f"font-size: 19px; color: #999; background: transparent; font-family: '{self.font_family}';")
        left_layout.addWidget(self._countdown_label)

        card_layout.addWidget(self._qr_panel, 3)
        card_layout.addWidget(sep)

        # —— 右侧：用户信息区（占 1/4） ——
        self._user_info_panel = QFrame()
        self._user_info_panel.setStyleSheet("background: transparent;")
        right_layout = QVBoxLayout(self._user_info_panel)
        right_layout.setContentsMargins(22, 45, 45, 45)
        right_layout.setSpacing(14)
        right_layout.setAlignment(Qt.AlignCenter)

        info_title = QLabel("当前账号")
        info_title.setAlignment(Qt.AlignCenter)
        info_title.setStyleSheet(f"font-size: 24px; font-weight: bold; color: #222; background: transparent; font-family: '{self.font_family}';")
        right_layout.addWidget(info_title)

        self._avatar_label = QLabel()
        configure_semantic_surface(self._avatar_label)
        self._avatar_label.setAlignment(Qt.AlignCenter)
        self._avatar_label.setFixedSize(120, 120)
        self._avatar_label.setStyleSheet("""
            QLabel {
                background: #f0f0f0;
                border-radius: 60px;
                border: 1px solid #ddd;
            }
        """)
        right_layout.addWidget(self._avatar_label)

        self._nickname_label = QLabel("未登录")
        self._nickname_label.setAlignment(Qt.AlignCenter)
        self._nickname_label.setStyleSheet(f"font-size: 21px; font-weight: bold; color: #333; background: transparent; font-family: '{self.font_family}';")
        self._nickname_label.setWordWrap(True)
        right_layout.addWidget(self._nickname_label)

        self._vip_label = QLabel("")
        self._vip_label.setAlignment(Qt.AlignCenter)
        self._vip_label.setStyleSheet(f"font-size: 17px; color: #c0392b; background: transparent; font-family: '{self.font_family}';")
        right_layout.addWidget(self._vip_label)

        self._uid_label = QLabel("")
        self._uid_label.setAlignment(Qt.AlignCenter)
        self._uid_label.setStyleSheet(f"font-size: 15px; color: #888; background: transparent; font-family: '{self.font_family}';")
        right_layout.addWidget(self._uid_label)

        right_layout.addStretch(1)

        cancel_btn = self._make_button("关 闭", "#f0f0f0", "#e0e0e0", "#ccc", 54)
        cancel_btn.clicked.connect(self._close_panel)
        right_layout.addWidget(cancel_btn)

        card_layout.addWidget(self._user_info_panel, 1)

    def _build_account_mode(self, card_layout, sep):
        """构建 account 模式布局：左侧账号详情(3/4) + 分隔线 + 右侧操作按钮(1/4)。"""
        # —— 左侧：账号详情展示（占 3/4） ——
        left_panel = QFrame()
        left_panel.setStyleSheet("background: transparent;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(60, 55, 30, 45)
        left_layout.setSpacing(18)
        left_layout.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)

        title = QLabel("网易云音乐")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"font-size: 30px; font-weight: bold; color: #222; background: transparent; font-family: '{self.font_family}';")
        left_layout.addWidget(title)

        # 大头像
        self._avatar_label = QLabel()
        configure_semantic_surface(self._avatar_label)
        self._avatar_label.setAlignment(Qt.AlignCenter)
        self._avatar_label.setFixedSize(180, 180)
        self._avatar_label.setStyleSheet("""
            QLabel {
                background: #f0f0f0;
                border-radius: 90px;
                border: 2px solid #e0e0e0;
            }
        """)
        left_layout.addWidget(self._avatar_label)

        # 昵称
        self._nickname_label = QLabel("加载中...")
        self._nickname_label.setAlignment(Qt.AlignCenter)
        self._nickname_label.setStyleSheet(f"font-size: 28px; font-weight: bold; color: #333; background: transparent; font-family: '{self.font_family}';")
        self._nickname_label.setWordWrap(True)
        left_layout.addWidget(self._nickname_label)

        # VIP 状态
        self._vip_label = QLabel("")
        self._vip_label.setAlignment(Qt.AlignCenter)
        self._vip_label.setStyleSheet(f"font-size: 20px; color: #c0392b; background: transparent; font-family: '{self.font_family}';")
        left_layout.addWidget(self._vip_label)

        # UID
        self._uid_label = QLabel("")
        self._uid_label.setAlignment(Qt.AlignCenter)
        self._uid_label.setStyleSheet(f"font-size: 18px; color: #888; background: transparent; font-family: '{self.font_family}';")
        left_layout.addWidget(self._uid_label)

        left_layout.addStretch(1)

        card_layout.addWidget(left_panel, 3)
        card_layout.addWidget(sep)

        # —— 右侧：操作按钮区（占 1/4） ——
        right_panel = QFrame()
        right_panel.setStyleSheet("background: transparent;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(22, 55, 45, 55)
        right_layout.setSpacing(24)
        right_layout.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)

        switch_btn = self._make_button("🔄 切换账号", "#0078D7", "#006abc", "#0078D7", 70, "white", 22)
        switch_btn.clicked.connect(self._close_panel)  # 先关闭本面板
        switch_btn.clicked.connect(lambda: self.switch_to_login_requested.emit())
        right_layout.addWidget(switch_btn)

        logout_btn = self._make_button("🚪 登出", "#d9534f", "#c9302c", "#d9534f", 70, "white", 22)
        logout_btn.clicked.connect(self._close_panel)  # 先关闭本面板
        logout_btn.clicked.connect(lambda: self.logout_requested.emit())
        right_layout.addWidget(logout_btn)

        right_layout.addStretch(1)

        cancel_btn = self._make_button("关 闭", "#f0f0f0", "#e0e0e0", "#ccc", 54)
        cancel_btn.clicked.connect(self._close_panel)
        right_layout.addWidget(cancel_btn)

        card_layout.addWidget(right_panel, 1)

    # ==================== 通用工具 ====================

    def _make_button(self, text, bg, hover_bg, border_color, height, color="#333333", font_size=21):
        """创建统一风格的按钮。"""
        btn = QPushButton(text)
        btn.setFixedHeight(height)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {color};
                border: 1px solid {border_color};
                border-radius: 8px;
                font-size: {font_size}px;
                font-family: '{self.font_family}';
            }}
            QPushButton:hover {{ background-color: {hover_bg}; }}
        """)
        return btn

    def _apply_target_geometry(self):
        """将悬浮窗几何对齐到 overlay_target（转换到主窗口坐标系）。"""
        target = self._overlay_target
        parent = self.parent()
        if target is None or parent is None:
            return
        # target 可能就是 parent（主窗口），也可能在 parent 内部偏移（如 stacked_widget）
        if target is parent:
            self.setGeometry(parent.rect())
        else:
            # 将 target 在 parent 中的相对几何映射过来
            top_left = target.mapTo(parent, QPoint(0, 0))
            self.setGeometry(QRect(top_left, target.size()))

    def eventFilter(self, obj, event):
        """监听主窗口 / overlay_target 的 Resize / Move，使悬浮窗跟随缩放与位移。

        注意时序：主窗口 resize 时，本 eventFilter 先于主窗口自身的
        resizeEvent() 触发，此时 stacked_widget 的 setGeometry() 尚未执行，
        overlay_target 的几何仍是旧值。因此用 QTimer.singleShot(0, ...)
        将几何更新推迟到当前事件循环结束后执行，确保读到的是更新后的几何。
        """
        if event.type() in (QEvent.Resize, QEvent.Move):
            QTimer.singleShot(0, self._apply_target_geometry)
        return super().eventFilter(obj, event)

    def showEvent(self, event):
        """面板显示时：对齐 overlay_target 几何，根据模式执行不同初始化。"""
        super().showEvent(event)
        self._apply_target_geometry()
        # 确保卡片在最上层
        card = self.findChild(QFrame, "login_card")
        if card is not None:
            card.raise_()

        # 刷新账号信息区（两种模式都需要）
        self.refresh_user_info()

        if self._mode == "login":
            # 登录模式：生成二维码
            if not self._generate_qrcode():
                self._status_label.setText("二维码生成失败，请关闭后重试。")

    def _fade_out_and_close(self):
        """关闭面板（无动画，直接关闭）。"""
        if self._closing:
            return
        self._closing = True
        self._timer.stop()
        self._do_real_close()

    def _do_real_close(self):
        """动画结束后真正关闭并发射信号。"""
        # 移除 eventFilter
        parent = self.parent()
        for target in set([parent, self._overlay_target]):
            if target is not None:
                try:
                    target.removeEventFilter(self)
                except RuntimeError:
                    pass
        self.closed.emit()
        self.close()

    def resizeEvent(self, event):
        """自身大小变化时无需额外处理（遮罩由自身 stylesheet 覆盖）。"""
        super().resizeEvent(event)

    # ---------- 扫码登录 ----------

    def _generate_qrcode(self) -> bool:
        """向网易云请求 unikey 并生成二维码图片，缩放填满标签。"""
        try:
            resp = pyncm.apis.login.LoginQrcodeUnikey()
            self.unikey = resp.get("unikey", "")
            if not self.unikey:
                return False
            qr_url = pyncm.apis.login.GetLoginQRCodeUrl(self.unikey)
        except Exception as e:
            debug_logger.error("QrCodeLoginDialog", f"获取二维码 unikey 失败: {str(e)}")
            return False

        try:
            qr = qrcode.QRCode(version=1, box_size=10, border=2,
                               error_correction=qrcode.constants.ERROR_CORRECT_M)
            qr.add_data(qr_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            pixmap = QPixmap()
            pixmap.loadFromData(buf.read(), "PNG")
            # 缩放到标签大小，保持长宽比，平滑缩放
            scaled = pixmap.scaled(
                self._qr_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self._qr_label.setPixmap(scaled)
        except Exception as e:
            debug_logger.error("QrCodeLoginDialog", f"生成二维码图片失败: {str(e)}")
            return False

        self._status_label.setText("请使用网易云音乐 APP 扫描二维码")
        self._update_countdown()
        self._timer.start()
        return True

    def _poll_status(self):
        """轮询扫码状态。"""
        self._elapsed += self.POLL_INTERVAL // 1000
        self._update_countdown()

        try:
            resp = pyncm.apis.login.LoginQrcodeCheck(self.unikey)
        except Exception as e:
            debug_logger.warning("QrCodeLoginDialog", f"轮询扫码状态异常: {str(e)}")
            return

        code = resp.get("code", -1)
        debug_logger.info("QrCodeLoginDialog", f"扫码状态码: {code}")

        if code == 800:
            self._timer.stop()
            self._status_label.setText("二维码已过期")
            self._status_label.setStyleSheet(f"font-size: 22px; color: #d9534f; background: transparent; font-family: '{self.font_family}';")
        elif code == 802:
            self._status_label.setText("已扫码，请在手机上确认登录")
            self._status_label.setStyleSheet(f"font-size: 22px; color: #5bc0de; background: transparent; font-family: '{self.font_family}';")
        elif code == 803:
            self._status_label.setText("授权成功，正在登录...")
            self._status_label.setStyleSheet(f"font-size: 22px; color: #5cb85c; background: transparent; font-family: '{self.font_family}';")
            self._finish_login()
        elif code == 200 or code == 502:
            self._status_label.setText("登录成功！")
            self._status_label.setStyleSheet(f"font-size: 22px; color: #5cb85c; background: transparent; font-family: '{self.font_family}';")
            self._finish_login()

    def _finish_login(self):
        """扫码登录成功。

        关键修复：pyncm 的 LoginQrcodeCheck 只会把 cookie 写入 session.cookies，
        但不会调用 WriteLoginInfo() 来更新 session.login_info。
        而 session.logged_in / uid / nickname / vipType 等属性完全依赖
        login_info["success"]，不看 cookie。因此必须显式调用 GetCurrentLoginStatus
        拿到登录态响应，再 WriteLoginInfo 写入，否则 is_logged_in() 永远返回 False。
        """
        self._timer.stop()
        try:
            resp = pyncm.apis.login.GetCurrentLoginStatus()
            # 只在响应确实带账号信息时才写入，避免覆盖已有登录态
            if resp and (resp.get("code") == 200) and (
                resp.get("account") or resp.get("profile")
            ):
                pyncm.WriteLoginInfo(resp)
                debug_logger.info("QrCodeLoginDialog",
                                  f"扫码登录态已写入 session，uid={pyncm.GetCurrentSession().uid}")
            else:
                debug_logger.warning("QrCodeLoginDialog",
                                     f"GetCurrentLoginStatus 未返回账号信息: {resp}")
        except Exception as e:
            debug_logger.error("QrCodeLoginDialog", f"写入登录态失败: {str(e)}")
        # 刷新右侧账号信息区
        self.refresh_user_info()
        self._close_panel()

    def _update_countdown(self):
        """更新倒计时显示。"""
        remaining = max(0, self.EXPIRE_SECONDS - self._elapsed)
        mins = remaining // 60
        secs = remaining % 60
        self._countdown_label.setText(f"二维码 {mins}:{secs:02d} 后失效")

    # ---------- 用户信息展示 ----------

    def refresh_user_info(self):
        """刷新账号信息区：昵称 / VIP / UID / 头像。

        登录前显示「未登录」占位；登录后从 provider 拉取详细资料。
        头像通过后台线程下载，避免阻塞 UI。
        """
        # 通过 pyncm 全局会话判断登录态（面板是独立 widget，不持有 subsystem）。
        try:
            import pyncm as _pyncm
            session = _pyncm.GetCurrentSession()
            logged_in = bool(getattr(session, "logged_in", False))
        except Exception:
            logged_in = False

        if not logged_in or not PYNCM_LOGIN_AVAILABLE:
            self._nickname_label.setText("未登录")
            self._vip_label.setText("")
            self._uid_label.setText("")
            self._avatar_label.setPixmap(QPixmap())  # 清空头像
            self._last_avatar_url = ""
            return

        # 直接构造一个临时 provider 调用 get_user_detail（自带缓存）。
        detail = {}
        try:
            from music_NCM import NeteaseMusicProvider
            provider = NeteaseMusicProvider()
            detail = provider.get_user_detail() or {}
        except Exception as e:
            debug_logger.warning("QrCodeLoginDialog", f"获取用户资料失败: {str(e)}")

        nickname = detail.get("nickname") or "网易云音乐用户"
        uid = detail.get("uid")
        vip_type = detail.get("vip_type", 0)
        avatar_url = detail.get("avatar_url", "")

        self._nickname_label.setText(nickname)
        self._vip_label.setText(self._format_vip_type(vip_type))
        self._uid_label.setText(f"UID: {uid}" if uid else "")

        # 头像异步加载（account 模式用 180px，login 模式用 120px）
        if avatar_url and avatar_url != self._last_avatar_url:
            self._last_avatar_url = avatar_url
            avatar_size = self._avatar_label.width()
            self._fetch_avatar_async(avatar_url, max(avatar_size, 120))

    @staticmethod
    def _format_vip_type(vip_type) -> str:
        """把网易云 vipType 数字格式化为可读文本。"""
        try:
            vt = int(vip_type)
        except (TypeError, ValueError):
            return ""
        # 常见取值：0=非会员, 1=黑胶VIP(旧), 11=黑胶VIP, 12=豪华VIP, 13=音乐人等
        mapping = {
            0: "",
            1: "♬ 黑胶VIP",
            11: "♬ 黑胶VIP",
            12: "♛ 豪华VIP",
            13: "✦ 音乐人",
        }
        return mapping.get(vt, f"VIP{vt}")

    def _fetch_avatar_async(self, url: str, size: int = 120):
        """后台线程下载头像图片，完成后回到主线程设置到 _avatar_label。"""
        # 复用现有线程（若还在跑就不重复启动）
        if self._avatar_thread is not None and self._avatar_thread.is_alive():
            return

        def _worker():
            try:
                import requests
                resp = requests.get(url, timeout=8)
                resp.raise_for_status()
                data = resp.content
                pixmap = QPixmap()
                pixmap.loadFromData(data)
                if pixmap.isNull():
                    return
                # 裁剪为圆形（贴到透明 QPixmap 上）
                scaled = pixmap.scaled(size, size, Qt.KeepAspectRatioByExpanding,
                                       Qt.SmoothTransformation)
                # 居中裁剪到正方形
                if scaled.width() > size or scaled.height() > size:
                    x = (scaled.width() - size) // 2
                    y = (scaled.height() - size) // 2
                    scaled = scaled.copy(x, y, size, size)
                rounded = self._make_rounded(scaled, size)
                # 通过 QTimer 投递回主线程设置
                QTimer.singleShot(0, lambda: self._apply_avatar(rounded))
            except Exception as e:
                debug_logger.warning("QrCodeLoginDialog", f"下载头像失败: {str(e)}")

        import threading
        self._avatar_thread = threading.Thread(target=_worker, daemon=True)
        self._avatar_thread.start()

    @staticmethod
    def _make_rounded(pixmap: QPixmap, size: int) -> QPixmap:
        """把方形 QPixmap 裁剪为圆形（透明背景）。"""
        out = QPixmap(size, size)
        out.fill(Qt.transparent)
        painter = QPainter(out)
        painter.setRenderHint(QPainter.Antialiasing, True)
        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()
        return out

    def _apply_avatar(self, pixmap: QPixmap):
        """主线程中安全地把头像 pixmap 设置到 label。"""
        try:
            if not pixmap.isNull():
                self._avatar_label.setPixmap(pixmap)
        except RuntimeError:
            # 面板可能已被销毁
            pass

    # ---------- 关闭 ----------

    def mousePressEvent(self, event):
        """点击卡片外的空白区域（即遮罩区域）时，关闭悬浮窗。
        卡片是独立子 widget，会自行接收点击事件，不会触发本方法。
        """
        card = self.findChild(QFrame, "login_card")
        if card is not None:
            # 点击位置落在卡片内 → 不处理
            if card.geometry().contains(event.pos()):
                super().mousePressEvent(event)
                return
        # 点击落在遮罩空白区 → 渐隐关闭
        if event.button() == Qt.LeftButton:
            self._fade_out_and_close()
        else:
            super().mousePressEvent(event)

    def _close_panel(self):
        """关闭面板（统一走渐隐动画）。"""
        self._fade_out_and_close()

    def closeEvent(self, event):
        """真正关闭时：停止轮询、移除事件过滤器。closed 信号由 _do_real_close 发射。"""
        self._timer.stop()
        parent = self.parent()
        if parent is not None:
            try:
                parent.removeEventFilter(self)
            except Exception:
                pass
        super().closeEvent(event)

    def keyPressEvent(self, event):
        """按 Esc 关闭面板。"""
        if event.key() == Qt.Key_Escape:
            self._close_panel()
        else:
            super().keyPressEvent(event)


class PlaylistManagePanel(QWidget):
    """歌单管理悬浮面板。

    全屏覆盖父窗口：背景半透明黑幕 + 模糊，居中白色卡片，
    内含歌单列表（支持勾选）、添加/编辑/删除/合并操作。
    """

    closed = pyqtSignal()
    # 操作信号
    playlist_add_requested = pyqtSignal(str, str)       # (name, url)
    playlist_delete_requested = pyqtSignal(str)        # name
    playlist_edit_requested = pyqtSignal(str, str, str) # (old_name, new_name, new_url)
    playlist_merge_requested = pyqtSignal(str, list)    # (new_name, [url1, url2, ...])
    playlist_clear_requested = pyqtSignal()            # 清空所有

    def __init__(self, playlists, parent=None, overlay_target=None):
        """
        Args:
            playlists: 当前歌单列表 List[Dict[name, url]]
            parent: 父窗口（应为顶层主窗口，保证 resize 跟随）
            overlay_target: 要覆盖的目标 widget（如 stacked_widget），
                           遮罩几何将跟随该 widget，而非覆盖整个 parent。
                           若未指定，则退化为覆盖 parent。
        """
        super().__init__(parent)
        configure_material_overlay(self)
        self.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)
        self.setObjectName("playlist_manage_overlay")

        self._closing = False

        # overlay_target 处理（同 QrCodeLoginDialog）
        if overlay_target is not None:
            self._overlay_target = overlay_target
        elif parent is not None:
            self._overlay_target = parent
        else:
            self._overlay_target = None

        # 获取样式配置
        self.settings_manager = SettingsManager()
        self.font_family = self.settings_manager.get_Custom_value("global_font", "微软雅黑")

        # —— 自身作为半透明深色遮罩层 ——
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 160);")
        self._apply_target_geometry()

        # 外层布局（居中卡片）
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setAlignment(Qt.AlignCenter)

        # 卡片容器
        # 高度由 780 减至 680，避免字号放大后在较小窗口中显示不全；
        # 实际显示时还会按遮罩可用高度二次约束（见 _constrain_card_height）。
        self._card = QFrame()
        configure_theme_card(self._card, preserve_outline=True)
        self._card.setObjectName("manage_card")
        self._card.setFixedSize(780, 680)
        self._card.setStyleSheet(f"""
            #manage_card {{
                background-color: rgba(255, 255, 255, 252);
                border-radius: 20px;
            }}
        """)
        outer.addWidget(self._card)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(36, 30, 36, 30)
        card_layout.setSpacing(18)

        # —— 标题行：左侧标题 + 右侧关闭按钮 ——
        title_row = QHBoxLayout()
        title_row.setSpacing(0)

        title_label = QLabel("歌单管理")
        title_label.setStyleSheet(f"""
            font-size: 33px;
            font-weight: bold;
            color: #222;
            background: transparent;
            font-family: '{self.font_family}';
        """)
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title_row.addWidget(title_label)
        title_row.addStretch(1)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(48, 48)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #EEEEEE;
                border: none;
                border-radius: 24px;
                font-size: 24px;
                color: #666;
            }
            QPushButton:hover {
                background-color: #DDDDDD;
                color: #333;
            }
        """)
        close_btn.clicked.connect(self._close_panel)
        title_row.addWidget(close_btn)
        card_layout.addLayout(title_row)

        # —— 操作按钮行：添加歌单 + 合并选中 ——
        action_row = QHBoxLayout()
        action_row.setSpacing(10)

        self._add_btn = QPushButton("+ 添加歌单")
        self._add_btn.setFixedHeight(57)
        self._add_btn.setCursor(Qt.PointingHandCursor)
        self._add_btn.setStyleSheet(self._action_btn_style("#4A90E2", "#357ABD"))
        self._add_btn.clicked.connect(self._toggle_add_area)
        action_row.addWidget(self._add_btn)

        self._merge_btn = QPushButton("合并选中")
        self._merge_btn.setFixedHeight(57)
        self._merge_btn.setCursor(Qt.PointingHandCursor)
        self._merge_btn.setEnabled(False)
        self._merge_btn.setStyleSheet(self._action_btn_style_disabled())
        self._merge_btn.clicked.connect(self._on_merge_clicked)
        action_row.addWidget(self._merge_btn)

        action_row.addStretch(1)
        card_layout.addLayout(action_row)

        # —— 添加歌单内联输入区（默认隐藏） ——
        self._add_area = QFrame()
        self._add_area.setVisible(False)
        self._add_area.setStyleSheet("background: transparent;")
        add_layout = QVBoxLayout(self._add_area)
        add_layout.setContentsMargins(0, 0, 0, 0)
        add_layout.setSpacing(8)

        name_input = QLineEdit()
        name_input.setPlaceholderText("歌单名称")
        name_input.setStyleSheet(self._input_style())
        name_input.setObjectName("add_name_input")
        add_layout.addWidget(name_input)

        url_input = QLineEdit()
        url_input.setPlaceholderText("网易云歌单链接")
        url_input.setStyleSheet(self._input_style())
        url_input.setObjectName("add_url_input")
        add_layout.addWidget(url_input)

        add_confirm_row = QHBoxLayout()
        add_confirm_row.setSpacing(8)
        add_confirm_row.addStretch(1)
        confirm_btn = QPushButton("确认添加")
        confirm_btn.setFixedSize(135, 48)
        confirm_btn.setCursor(Qt.PointingHandCursor)
        confirm_btn.setStyleSheet(self._small_btn_style("#4A90E2"))
        confirm_btn.clicked.connect(self._on_add_confirmed)
        add_confirm_row.addWidget(confirm_btn)
        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedSize(90, 48)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(self._small_btn_style("#999999"))
        cancel_btn.clicked.connect(self._toggle_add_area)
        add_confirm_row.addWidget(cancel_btn)
        add_layout.addLayout(add_confirm_row)

        card_layout.addWidget(self._add_area)

        # —— 分隔线 ——
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #DDDDDD; max-height: 1px;")
        card_layout.addWidget(sep)

        # —— 歌单列表（可滚动） ——
        self._list_container = QWidget()
        self._list_container.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(4)
        self._list_layout.setAlignment(Qt.AlignTop)

        self._list_scroll = QScrollArea()
        self._list_scroll.setWidgetResizable(True)
        self._list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { width: 6px; background: transparent; border-radius: 3px; }
            QScrollBar::handle:vertical { background: #BBBBBB; border-radius: 3px; }
        """)
        self._list_scroll.setWidget(self._list_container)
        card_layout.addWidget(self._list_scroll, 1)

        # —— 底部：清空所有歌单 ——
        bottom_row = QHBoxLayout()
        bottom_row.addStretch(1)
        clear_btn = QPushButton("清空所有歌单")
        clear_btn.setFixedSize(160, 51)
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setStyleSheet(self._small_btn_style("#E74C3C"))
        clear_btn.clicked.connect(self._on_clear_all)
        bottom_row.addWidget(clear_btn)
        card_layout.addLayout(bottom_row)

        # 监听父窗口（主窗口）与 overlay_target 的大小变化，使遮罩跟随缩放
        if parent is not None:
            parent.installEventFilter(self)
        if self._overlay_target is not None and self._overlay_target is not parent:
            self._overlay_target.installEventFilter(self)

        # 填充歌单列表
        self._playlist_items = []  # 存储每个歌单行的组件引用
        self._build_playlist_list(playlists)

    # —— 样式辅助方法 ——

    def _action_btn_style(self, bg, hover_bg):
        return f"""
            QPushButton {{
                background-color: {bg};
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 21px;
                font-weight: bold;
                padding: 0 24px;
                font-family: '{self.font_family}';
            }}
            QPushButton:hover {{ background-color: {hover_bg}; }}
            QPushButton:disabled {{ background-color: #CCCCCC; color: #888; }}
        """

    def _action_btn_style_disabled(self):
        return self._action_btn_style("#CCCCCC", "#CCCCCC")

    def _small_btn_style(self, bg_color):
        hover = self._lighten(bg_color, 20)
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: white;
                border: none;
                border-radius: 9px;
                font-size: 20px;
                font-weight: bold;
                font-family: '{self.font_family}';
            }}
            QPushButton:hover {{ background-color: {hover}; }}
        """

    def _input_style(self):
        return f"""
            QLineEdit {{
                border: 1px solid #D0D0D0;
                border-radius: 9px;
                padding: 9px 15px;
                font-size: 21px;
                background: #FFFFFF;
                color: #333;
                font-family: '{self.font_family}';
            }}
            QLineEdit:focus {{ border-color: #4A90E2; }}
        """

    @staticmethod
    def _lighten(hex_color, amount):
        """将十六进制颜色变亮"""
        hex_color = hex_color.lstrip("#")
        r = min(255, int(hex_color[0:2], 16) + amount)
        g = min(255, int(hex_color[2:4], 16) + amount)
        b = min(255, int(hex_color[4:6], 16) + amount)
        return f"#{r:02x}{g:02x}{b:02x}"

    # —— 歌单列表构建 ——

    def _build_playlist_list(self, playlists):
        """根据歌单数据重新构建列表"""
        # 清空现有列表
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._playlist_items = []

        for i, p in enumerate(playlists):
            is_internal = (p['url'] == "internal://queue")
            row_widget = self._create_playlist_row(i, p['name'], p['url'], is_internal)
            self._list_layout.addWidget(row_widget)
            self._playlist_items.append({
                "widget": row_widget,
                "checkbox": row_widget.findChild(QCheckBox, f"cb_{i}"),
                "name_label": row_widget.findChild(QLabel, f"name_{i}"),
                "name": p['name'],
                "url": p['url'],
                "is_internal": is_internal,
            })

        self._list_layout.addStretch(1)
        self._update_merge_btn_state()

    def _create_playlist_row(self, index, name, url, is_internal):
        """创建单行歌单条目：checkbox + 名称 + 编辑/删除按钮"""
        row = QFrame()
        configure_theme_card(row, preserve_outline=True)
        row.setStyleSheet("""
            QFrame {
                background-color: #F8F9FA;
                border-radius: 8px;
            }
        """)
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(15, 12, 15, 12)
        row_layout.setSpacing(8)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)
        row_layout.addLayout(content_layout)

        # 复选框
        cb = QCheckBox()
        cb.setObjectName(f"cb_{index}")
        if is_internal:
            cb.setEnabled(False)
            cb.setChecked(False)
        cb.stateChanged.connect(lambda state, idx=index: self._on_checkbox_changed(idx, state))
        content_layout.addWidget(cb)

        # 歌单名称
        name_label = QLabel(name)
        name_label.setObjectName(f"name_{index}")
        name_label.setStyleSheet(f"""
            background: transparent;
            border: none;
            color: {'#999999' if is_internal else '#333333'};
            font-size: 22px;
            font-family: '{self.font_family}';
        """)
        content_layout.addWidget(name_label, 1)

        if not is_internal:
            # 编辑按钮
            edit_btn = QPushButton("编辑")
            edit_btn.setFixedSize(60, 42)
            edit_btn.setCursor(Qt.PointingHandCursor)
            edit_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #E8E8E8;
                    border: none;
                    border-radius: 8px;
                    font-size: 18px;
                    color: #555;
                    font-family: '{self.font_family}';
                }}
                QPushButton:hover {{ background-color: #D8D8D8; }}
            """)
            edit_btn.clicked.connect(lambda checked, n=name, u=url, w=row: self._toggle_edit_area(w, n, u))
            content_layout.addWidget(edit_btn)

            # 删除按钮
            del_btn = QPushButton("删除")
            del_btn.setFixedSize(60, 42)
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #FDE8E8;
                    border: none;
                    border-radius: 8px;
                    font-size: 18px;
                    color: #E74C3C;
                    font-family: '{self.font_family}';
                }}
                QPushButton:hover {{ background-color: #FBD0D0; }}
            """)
            del_btn.clicked.connect(lambda checked, n=name: self._on_delete_clicked(n))
            content_layout.addWidget(del_btn)

        return row

    # —— 事件处理 ——

    def _apply_target_geometry(self):
        """将悬浮窗几何对齐到 overlay_target（转换到主窗口坐标系）。"""
        target = self._overlay_target
        parent = self.parent()
        if target is None or parent is None:
            return
        if target is parent:
            self.setGeometry(parent.rect())
        else:
            top_left = target.mapTo(parent, QPoint(0, 0))
            self.setGeometry(QRect(top_left, target.size()))

    def showEvent(self, event):
        """面板显示时：对齐 overlay_target 几何。"""
        super().showEvent(event)
        self._apply_target_geometry()
        self._constrain_card_height()
        # 确保卡片在最上层
        if self._card is not None:
            self._card.raise_()

    def _constrain_card_height(self):
        """约束卡片高度：不超过遮罩可用高度（上下各留 24px 边距）。

        卡片宽度保持固定 780；高度取 min(设定高度, 遮罩高度 - 48)，
        防止字号放大后卡片超出父遮罩导致显示不全。
        """
        if self._card is None:
            return
        target = self._overlay_target
        parent = self.parent()
        if target is None or parent is None:
            return
        available_h = target.size().height()
        max_h = max(360, available_h - 48)  # 至少保留 360px 可用高度
        self._card.setFixedHeight(min(680, max_h))

    def resizeEvent(self, event):
        """自身大小变化时无需额外处理（遮罩由自身 stylesheet 覆盖）。"""
        super().resizeEvent(event)
        self._constrain_card_height()

    def eventFilter(self, obj, event):
        """监听主窗口 / overlay_target 的 Resize / Move，使悬浮窗跟随缩放与位移。

        注意时序：主窗口 resize 时，本 eventFilter 先于主窗口自身的
        resizeEvent() 触发，此时 stacked_widget 的 setGeometry() 尚未执行，
        overlay_target 的几何仍是旧值。因此用 QTimer.singleShot(0, ...)
        将几何更新推迟到当前事件循环结束后执行，确保读到的是更新后的几何。
        """
        if event.type() in (QEvent.Resize, QEvent.Move):
            QTimer.singleShot(0, self._apply_target_geometry)
            QTimer.singleShot(0, self._constrain_card_height)
        return False

    def keyPressEvent(self, event):
        """按 Esc 关闭面板。"""
        if event.key() == Qt.Key_Escape:
            self._close_panel()
        else:
            super().keyPressEvent(event)

    def _close_panel(self):
        if self._closing:
            return
        self._closing = True
        # 移除 eventFilter
        parent = self.parent()
        for target in set([parent, self._overlay_target]):
            if target is not None:
                try:
                    target.removeEventFilter(self)
                except RuntimeError:
                    pass
        self.hide()
        self.closed.emit()
        self.deleteLater()

    # —— 添加歌单 ——

    def _toggle_add_area(self):
        """显示/隐藏添加歌单的输入区域"""
        visible = self._add_area.isVisible()
        self._add_area.setVisible(not visible)
        if not visible:
            # 清空输入
            name_input = self._add_area.findChild(QLineEdit, "add_name_input")
            url_input = self._add_area.findChild(QLineEdit, "add_url_input")
            if name_input:
                name_input.clear()
                name_input.setFocus()
            if url_input:
                url_input.clear()

    def _on_add_confirmed(self):
        """确认添加歌单"""
        name_input = self._add_area.findChild(QLineEdit, "add_name_input")
        url_input = self._add_area.findChild(QLineEdit, "add_url_input")
        name = name_input.text().strip() if name_input else ""
        url = url_input.text().strip() if url_input else ""
        if not name or not url:
            QMessageBox.warning(self, "提示", "请填写歌单名称和链接。")
            return
        self.playlist_add_requested.emit(name, url)
        self._add_area.setVisible(False)

    # —— 删除歌单 ——

    def _on_delete_clicked(self, name):
        """删除单个歌单（带确认）"""
        ret = QMessageBox.question(
            self, "确认删除", f"确定要删除歌单「{name}」吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if ret == QMessageBox.Yes:
            self.playlist_delete_requested.emit(name)

    # —— 清空所有歌单 ——

    def _on_clear_all(self):
        """清空所有自定义歌单"""
        ret = QMessageBox.question(
            self, "确认", "确定要清空所有自定义歌单吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if ret == QMessageBox.Yes:
            self.playlist_clear_requested.emit()

    # —— 编辑歌单 ——

    def _toggle_edit_area(self, row_widget, current_name, current_url):
        """在歌单行下方展开/收起编辑区域"""
        # 查找是否已有编辑区域
        existing = row_widget.findChild(QFrame, "edit_area")
        if existing is not None:
            existing.deleteLater()
            return

        edit_area = QFrame(row_widget)
        edit_area.setObjectName("edit_area")
        edit_area.setStyleSheet("background: transparent;")
        edit_layout = QVBoxLayout(edit_area)
        edit_layout.setContentsMargins(36, 4, 10, 4)
        edit_layout.setSpacing(6)

        name_edit = QLineEdit(current_name)
        name_edit.setPlaceholderText("歌单名称")
        name_edit.setStyleSheet(self._input_style())
        name_edit.setFixedHeight(45)
        edit_layout.addWidget(name_edit)

        url_edit = QLineEdit(current_url)
        url_edit.setPlaceholderText("网易云歌单链接")
        url_edit.setStyleSheet(self._input_style())
        url_edit.setFixedHeight(45)
        edit_layout.addWidget(url_edit)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        btn_row.addStretch(1)
        save_btn = QPushButton("保存")
        save_btn.setFixedSize(90, 39)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet(self._small_btn_style("#4A90E2"))
        save_btn.clicked.connect(lambda: self._on_edit_saved(
            current_name, name_edit.text().strip(), url_edit.text().strip(), edit_area
        ))
        btn_row.addWidget(save_btn)
        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedSize(75, 39)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(self._small_btn_style("#999999"))
        cancel_btn.clicked.connect(lambda: edit_area.deleteLater())
        btn_row.addWidget(cancel_btn)
        edit_layout.addLayout(btn_row)

        # 追加到主操作行下方，保持两个编辑框可用的横向空间。
        row_layout = row_widget.layout()
        row_layout.addWidget(edit_area)

    def _on_edit_saved(self, old_name, new_name, new_url, edit_area):
        """保存编辑结果"""
        if not new_name or not new_url:
            QMessageBox.warning(self, "提示", "名称和链接不能为空。")
            return
        edit_area.deleteLater()
        self.playlist_edit_requested.emit(old_name, new_name, new_url)

    # —— 合并歌单 ——

    def _on_checkbox_changed(self, index, state):
        """勾选状态变化时更新合并按钮可用性"""
        self._update_merge_btn_state()

    def _update_merge_btn_state(self):
        """检查勾选数量，启用/禁用合并按钮"""
        checked = sum(1 for item in self._playlist_items
                      if item["checkbox"].isChecked() and not item["is_internal"])
        if checked >= 2:
            self._merge_btn.setEnabled(True)
            self._merge_btn.setStyleSheet(self._action_btn_style("#4A90E2", "#357ABD"))
        else:
            self._merge_btn.setEnabled(False)
            self._merge_btn.setStyleSheet(self._action_btn_style_disabled())

    def _on_merge_clicked(self):
        """点击合并选中"""
        selected = [item for item in self._playlist_items
                    if item["checkbox"].isChecked() and not item["is_internal"]]
        if len(selected) < 2:
            return

        # 在卡片内弹出输入新歌单名称
        names = ", ".join(item["name"] for item in selected)
        new_name, ok = QInputDialog.getText(
            self, "合并歌单",
            f"将合并以下歌单：\n{names}\n\n请输入新歌单名称："
        )
        if not ok or not new_name.strip():
            return

        urls = [item["url"] for item in selected]
        self.playlist_merge_requested.emit(new_name.strip(), urls)


class SongItemWidget(QFrame):
    """
    单个歌曲条目组件。
    歌曲名负责播放；右侧作者与时长合并为“作者 | 时长”，
    点击作者名称打开歌曲详情面板，时长保持只读。
    """
    play_clicked = pyqtSignal(int)    # 发送点击的序号
    details_requested = pyqtSignal(object)  # 请求打开歌曲详情面板 (track)
    add_to_queue_requested = pyqtSignal(object) # 请求添加到播放列表
    delete_requested = pyqtSignal(int) # 请求删除歌曲 (1-based index)

    def __init__(self, index, track: MusicTrack, is_queue=False, parent=None):
        super().__init__(parent)
        configure_transparent_container(self)
        self.index = index
        self.track = track
        self.is_queue = is_queue
        self.init_ui()

    def init_ui(self):
        # 获取用户设置的字体
        settings_manager = SettingsManager()
        font_family = settings_manager.get_Custom_value("global_font", "微软雅黑")

        self.setFixedHeight(50)
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: transparent;
                margin: 0px;
                font-family: "{font_family}";
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
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

        configure_semantic_surface(self.action_btn)

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

        # 3. “作者 | 时长”信息栏。作者可滚动且可点击打开详情面板，
        #    分隔符和时长固定、不可点击。
        duration_sec = self.track.duration // 1000
        duration_str = f"{duration_sec // 60:02d}:{duration_sec % 60:02d}"
        self.artist_duration_frame = QFrame()
        self.artist_duration_frame.setObjectName("artist_duration_frame")
        self.artist_duration_frame.setFixedHeight(50)
        self.artist_duration_frame.setStyleSheet("""
            QFrame#artist_duration_frame {
                background-color: white;
                border-radius: 8px;
                border: 1px solid gray;
            }
        """)
        artist_duration_layout = QHBoxLayout(self.artist_duration_frame)
        artist_duration_layout.setContentsMargins(15, 0, 12, 0)
        artist_duration_layout.setSpacing(6)

        self.artist_label = ScrollingLabel(scroll_interval_ms=60)
        self.artist_label.set_scrolling_text(self.track.artist)
        self.artist_label.setCursor(Qt.PointingHandCursor)
        self.artist_label.setToolTip("点击查看歌曲详情")
        self.artist_label.installEventFilter(self)
        self.artist_label.setStyleSheet(
            f"font-size: 16px; color: #555555; background: transparent; "
            f"font-family: '{font_family}'; border: none;"
        )
        self.artist_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        artist_duration_layout.addWidget(self.artist_label, 1)

        self.separator_label = QLabel("|")
        self.separator_label.setObjectName("artist_duration_separator")
        self.separator_label.setFixedWidth(10)
        self.separator_label.setAlignment(Qt.AlignCenter)
        self.separator_label.setStyleSheet(
            f"font-size: 14px; color: #777777; background: transparent; "
            f"font-family: '{font_family}'; border: none;"
        )
        artist_duration_layout.addWidget(self.separator_label)

        self.duration_label = QLabel(duration_str)
        self.duration_label.setObjectName("duration_label")
        self.duration_label.setFixedWidth(48)
        self.duration_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.duration_label.setStyleSheet(
            f"font-size: 13px; color: #555555; background: transparent; "
            f"font-family: '{font_family}'; border: none;"
        )
        artist_duration_layout.addWidget(self.duration_label)

        layout.addWidget(self.artist_duration_frame, 3)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def eventFilter(self, watched, event):
        """点击作者名称时请求打开歌曲详情面板。"""
        if (
            watched is self.artist_label
            and event.type() == QEvent.MouseButtonRelease
            and event.button() == Qt.LeftButton
        ):
            self.details_requested.emit(self.track)
            return True
        return super().eventFilter(watched, event)


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
        configure_independent_surface(self)
        
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
    实现文本自动横向滚动的 QLabel（marquee 风格，像素级平移）。
    当文本宽度超过控件宽度时，文本整体向左平移滚动以完整展示。
    普通文本循环滚动；带显示时长的歌词单次滚动并停留在末尾。

    滚动轨迹（以超长歌词 "There's a Peeping Tom sat outside my window" 为例）：
      初始态：文本左对齐贴左侧  -> "There's a Peep"
      中途：   整体左移           -> "e's a Peeping To"
      结尾态：尾部贴右、左侧留白 -> "dow"（左侧已移出，右侧空）
      首尾留白后无缝循环回到初始态。
    """
    # 滚动一个“完整周期”所需的像素位移：
    #   offset 从 0 增长到 (text_width - widget_width + GAP)，
    #   其中 GAP 为结尾态与下一轮初始态之间的留白，保证视觉上有停顿且循环衔接自然。
    # 每次定时器触发移动 STEP_PX 个像素。
    STEP_PX = 2
    GAP_PX = 40  # 首尾留白宽度（约为控件宽度的一部分，给结尾态一个停顿）
    DEFAULT_SCROLL_INTERVAL_MS = 400
    MIN_TIMED_SCROLL_INTERVAL_MS = 16
    SCROLL_SPEED_MULTIPLIER = 1.25

    def __init__(self, parent=None, scroll_interval_ms=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setContentsMargins(0, 0, 0, 0)
        self.original_text = ""
        self.offset_px = 0          # 当前像素位移（>= 0）
        self._text_end_offset = 0   # 文本尾部刚好进入可视区域时的位移
        self._max_offset = 0        # 一个周期内的最大位移
        self._display_duration_ms = None
        self._scroll_deadline = None
        self._remaining_scroll_time_ms = None
        self._scroll_step_px = self.STEP_PX
        try:
            interval_ms = int(scroll_interval_ms)
        except (TypeError, ValueError, OverflowError):
            interval_ms = self.DEFAULT_SCROLL_INTERVAL_MS
        self._default_scroll_interval_ms = max(16, interval_ms)
        self.scroll_timer = QTimer(self)
        self.scroll_timer.setInterval(self._default_scroll_interval_ms)
        self.scroll_timer.timeout.connect(self._scroll_text)
        # paintEvent moves glyphs without changing QLabel.text().
        self.setProperty("themeGlowContentRevision", self.offset_px)
        self._paused = False        # 外部可暂停（鼠标悬停时停下方便阅读）
        self._overflow = False      # 当前文本是否判定为“超长”

    def set_scrolling_text(self, text: str, display_duration_ms=None):
        """设置文本；传入显示时长时，在该时长内单次滚动到文本末尾。"""
        self.original_text = text
        self.offset_px = 0
        self._set_display_duration(display_duration_ms)
        self.setProperty("themeGlowContentRevision", self.offset_px)
        super().setText(text)  # 始终同步到 QLabel 内部文本，保证未超长时 paintEvent 能渲染
        self.update_text_display()

    def _set_display_duration(self, display_duration_ms):
        try:
            duration_ms = int(display_duration_ms)
        except (TypeError, ValueError, OverflowError):
            duration_ms = 0
        self._display_duration_ms = duration_ms if duration_ms > 0 else None
        self._scroll_deadline = None
        self._remaining_scroll_time_ms = None
        if self._display_duration_ms is None:
            return

        target_scroll_ms = self._display_duration_ms / self.SCROLL_SPEED_MULTIPLIER
        if self._paused:
            self._remaining_scroll_time_ms = target_scroll_ms
        else:
            self._scroll_deadline = time.monotonic() + target_scroll_ms / 1000.0

    def _remaining_timed_scroll_ms(self):
        if self._display_duration_ms is None:
            return None
        if self._scroll_deadline is not None:
            return max(0.0, (self._scroll_deadline - time.monotonic()) * 1000.0)
        return max(0.0, self._remaining_scroll_time_ms or 0.0)

    def _recompute_overflow(self):
        """重新计算是否超长与一个周期的最大位移。
        超长判定算法：文本像素宽度 > 控件可用宽度。
        """
        fm = self.fontMetrics()
        margins = self.contentsMargins()
        widget_width = self.width() - margins.left() - margins.right()
        # 控件尚未布局时 widget_width 可能为 0 或很小，此时不做判定
        if widget_width <= 0:
            self._overflow = False
            self._text_end_offset = 0
            self._max_offset = 0
            return
        text_width = fm.width(self.original_text)
        self._overflow = text_width > widget_width
        self._text_end_offset = max(0, text_width - widget_width)
        self._max_offset = self._text_end_offset + self.GAP_PX if self._overflow else 0

    def _update_scroll_interval(self):
        """按歌词剩余显示时长计算速度；普通文本继续使用原固定间隔。"""
        self._scroll_step_px = self.STEP_PX
        if self._display_duration_ms is None or not self._overflow:
            self.scroll_timer.setInterval(self._default_scroll_interval_ms)
            return

        remaining_offset = max(0, self._text_end_offset - self.offset_px)
        remaining_scroll_ms = self._remaining_timed_scroll_ms()
        if remaining_offset == 0 or remaining_scroll_ms is None:
            return
        if remaining_scroll_ms <= 0:
            self._scroll_step_px = max(self.STEP_PX, remaining_offset)
            self.scroll_timer.setInterval(1)
            return

        base_tick_count = (remaining_offset + self.STEP_PX - 1) // self.STEP_PX
        ideal_interval_ms = remaining_scroll_ms / max(1, base_tick_count)
        if ideal_interval_ms >= self.MIN_TIMED_SCROLL_INTERVAL_MS:
            self.scroll_timer.setInterval(int(ideal_interval_ms))
            return

        if remaining_scroll_ms < self.MIN_TIMED_SCROLL_INTERVAL_MS:
            self._scroll_step_px = remaining_offset
            self.scroll_timer.setInterval(max(1, int(remaining_scroll_ms)))
            return

        available_ticks = max(1, int(remaining_scroll_ms / self.MIN_TIMED_SCROLL_INTERVAL_MS))
        self._scroll_step_px = max(
            self.STEP_PX,
            (remaining_offset + available_ticks - 1) // available_ticks,
        )
        self.scroll_timer.setInterval(self.MIN_TIMED_SCROLL_INTERVAL_MS)

    def is_overflow(self) -> bool:
        return self._overflow

    def update_text_display(self):
        """外部调用的兼容入口（保留旧 API）。"""
        self._recompute_overflow()
        self._update_scroll_interval()
        if not self._overflow:
            self.scroll_timer.stop()
            self.offset_px = 0
            self.setProperty("themeGlowContentRevision", self.offset_px)
        elif self._display_duration_ms is not None and (
            self.offset_px >= self._text_end_offset
            or self._remaining_timed_scroll_ms() <= 0
        ):
            self.scroll_timer.stop()
            self.offset_px = self._text_end_offset
            self._scroll_deadline = None
            self._remaining_scroll_time_ms = 0
            self.setProperty("themeGlowContentRevision", self.offset_px)
        elif not self._paused and not self.scroll_timer.isActive():
            self.scroll_timer.start()
        self.update()

    def pause_scroll(self):
        """暂停滚动（鼠标悬停时调用，方便完整阅读）。文本不超长时无副作用。"""
        if not self._paused and self._display_duration_ms is not None:
            self._remaining_scroll_time_ms = self._remaining_timed_scroll_ms()
            self._scroll_deadline = None
        self._paused = True
        if self.scroll_timer.isActive():
            self.scroll_timer.stop()

    def resume_scroll(self):
        """恢复滚动（鼠标离开时调用）。"""
        was_paused = self._paused
        self._paused = False
        if was_paused and self._display_duration_ms is not None:
            remaining_scroll_ms = self._remaining_scroll_time_ms or 0
            if remaining_scroll_ms > 0:
                self._scroll_deadline = time.monotonic() + remaining_scroll_ms / 1000.0
            self._update_scroll_interval()
        timed_scroll_finished = (
            self._display_duration_ms is not None
            and self.offset_px >= self._text_end_offset
        )
        if self._overflow and not timed_scroll_finished and not self.scroll_timer.isActive():
            self.scroll_timer.start()

    def _scroll_text(self):
        """定时器触发：按当前步长平移；定时歌词停在末尾，普通文本循环。"""
        if not self._overflow:
            self.scroll_timer.stop()
            self.offset_px = 0
            self.update()
            return

        self.offset_px += self._scroll_step_px
        if self._display_duration_ms is not None and self.offset_px >= self._text_end_offset:
            self.offset_px = self._text_end_offset
            self.scroll_timer.stop()
            self._scroll_deadline = None
            self._remaining_scroll_time_ms = 0
        elif self.offset_px >= self._max_offset:
            self.offset_px = 0  # 回到初始态（文本左对齐贴左侧），无缝循环
        self.setProperty("themeGlowContentRevision", self.offset_px)
        self.update()

    def paintEvent(self, event):
        """按当前 offset_px 平移绘制文本，实现像素级 marquee 滚动。
        不超长时退化为普通的左对齐静态绘制。
        """
        if not self._overflow:
            # 未超长：交给 QLabel 默认绘制（完整居左显示）
            super().paintEvent(event)
            return

        fm = self.fontMetrics()
        margins = self.contentsMargins()
        x_start = margins.left() - self.offset_px  # 文本起点随 offset 向左移
        y = (self.height() + fm.ascent() - fm.descent()) // 2

        painter = QPainter(self)
        painter.setFont(self.font())
        # 文字颜色：优先用 QPalette 文字色，保证与样式表 color 一致
        painter.setPen(self.palette().color(QPalette.WindowText))

        # 直接绘制完整文本，超出控件区域的部分由 Qt 自动裁剪
        painter.drawText(x_start, y, self.original_text)
        painter.end()

    def resizeEvent(self, event):
        """窗口大小改变时重新计算滚动范围并启动/停止滚动"""
        super().resizeEvent(event)
        # 用 update_text_display 统一处理：重新判定 overflow、启动/停止 timer、重绘
        self.update_text_display()

    def changeEvent(self, event):
        """字号变化后使用当前字体重新判定文本是否溢出。"""
        super().changeEvent(event)
        if event.type() == QEvent.FontChange and hasattr(self, "scroll_timer"):
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


class ElidedButton(QPushButton):
    '''Button that preserves its full command text while drawing an ellipsis.'''

    def __init__(self, text='', parent=None):
        super().__init__('', parent)
        self._full_text = ''
        self.set_elided_text(text)

    def set_elided_text(self, text):
        self._full_text = str(text or '')
        self.setToolTip(self._full_text)
        self.setAccessibleName(self._full_text)
        self._update_elided_text()

    def _update_elided_text(self):
        available_width = max(1, self.width() - 24)
        elided = self.fontMetrics().elidedText(
            self._full_text,
            Qt.ElideRight,
            available_width,
        )
        super().setText(elided)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_elided_text()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.FontChange:
            self._update_elided_text()


class SongInfoPanel(QWidget):
    """歌曲详情悬浮面板，交互样式与歌单管理面板一致。

    全屏半透明遮罩 + 居中卡片：歌曲名、作者按钮列表（每人一个搜索按钮）、
    时长/专辑/发行时间/别名/音轨等元数据。点击作者按钮按该名称搜索。
    """

    artist_clicked = pyqtSignal(str)

    def __init__(self, parent=None, overlay_target=None):
        super().__init__(parent)
        configure_material_overlay(self)
        self.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)
        self.setObjectName("song_info_overlay")

        if overlay_target is not None:
            self._overlay_target = overlay_target
        elif parent is not None:
            self._overlay_target = parent
        else:
            self._overlay_target = None

        self._closing = False
        self._track = None
        self.settings_manager = SettingsManager()
        self.font_family = self.settings_manager.get_Custom_value(
            "global_font", "微软雅黑"
        )

        # —— 自身作为半透明深色遮罩层 ——
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 160);")
        self._apply_target_geometry()

        if self._overlay_target is not None and self._overlay_target is not parent:
            self._overlay_target.installEventFilter(self)

        # 外层布局（居中卡片）
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setAlignment(Qt.AlignCenter)

        self._card = QFrame()
        configure_theme_card(self._card, preserve_outline=True)
        self._card.setObjectName("song_info_card")
        self._card.setFixedSize(560, 600)
        self._card.setStyleSheet("""
            #song_info_card {
                background-color: rgba(255, 255, 255, 252);
                border-radius: 20px;
            }
        """)
        outer.addWidget(self._card)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(30, 26, 30, 24)
        card_layout.setSpacing(12)

        # 标题行：左侧歌曲名 + 右侧关闭按钮
        title_row = QHBoxLayout()
        title_row.setSpacing(0)

        self.title_label = ElidedLabel()
        self.title_label.setObjectName("song_info_title")
        self.title_label.setFixedHeight(42)
        self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.title_label.setStyleSheet(
            f"font-size: 31px; font-weight: bold; color: #222; "
            f"background: transparent; font-family: '{self.font_family}';"
        )
        title_row.addWidget(self.title_label, 1)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("song_info_close_button")
        close_btn.setFixedSize(44, 44)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(
            f"QPushButton {{ background-color: #EEEEEE; border: none; "
            f"border-radius: 22px; font-size: 24px; color: #666; "
            f"font-family: '{self.font_family}'; }}"
            f"QPushButton:hover {{ background-color: #DDDDDD; color: #333; }}"
        )
        close_btn.clicked.connect(self._close_panel)
        title_row.addWidget(close_btn)
        card_layout.addLayout(title_row)

        author_caption = QLabel("作者")
        author_caption.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: #444; "
            f"background: transparent; font-family: '{self.font_family}';"
        )
        card_layout.addWidget(author_caption)

        self.authors_scroll = QScrollArea()
        self.authors_scroll.setWidgetResizable(True)
        self.authors_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.authors_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.authors_scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { width: 8px; background: transparent; border-radius: 4px; }
            QScrollBar::handle:vertical { background: #AAAAAA; border-radius: 4px; min-height: 30px; }
        """)
        self.authors_container = QWidget()
        self.authors_container.setStyleSheet("background: transparent;")
        self.authors_layout = QVBoxLayout(self.authors_container)
        self.authors_layout.setContentsMargins(0, 0, 0, 0)
        self.authors_layout.setSpacing(6)
        self.authors_scroll.setWidget(self.authors_container)
        card_layout.addWidget(self.authors_scroll, 1)

        self.metadata_layout = QGridLayout()
        self.metadata_layout.setContentsMargins(0, 4, 0, 0)
        self.metadata_layout.setHorizontalSpacing(14)
        self.metadata_layout.setVerticalSpacing(8)
        self.metadata_layout.setColumnStretch(1, 1)
        card_layout.addLayout(self.metadata_layout)

        self.metadata_values = {}
        self.hide()

    @staticmethod
    def _format_duration(duration_ms):
        try:
            seconds = max(0, int(duration_ms or 0) // 1000)
        except (TypeError, ValueError, OverflowError):
            seconds = 0
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    @staticmethod
    def _format_release_date(release_time_ms):
        try:
            timestamp = int(release_time_ms)
            if timestamp <= 0:
                raise ValueError
            return datetime.fromtimestamp(timestamp / 1000).strftime("%Y-%m-%d")
        except (OSError, OverflowError, TypeError, ValueError):
            return "暂无数据"

    @staticmethod
    def _format_track_position(track):
        parts = []
        disc_number = str(getattr(track, "disc_number", "") or "").strip()
        track_number = getattr(track, "track_number", None)
        if disc_number:
            parts.append(f"CD {disc_number}")
        if track_number:
            parts.append(f"第 {track_number} 轨")
        return " · ".join(parts)

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def set_track(self, track):
        self._track = track
        title = str(getattr(track, "name", "") or "未知歌曲")
        self.title_label.set_elided_text(title)
        self.title_label.setToolTip(title)

        self._clear_layout(self.authors_layout)
        artist_names = list(getattr(track, "artist_names", []) or [])
        if not artist_names:
            fallback = str(getattr(track, "artist", "") or "").strip()
            artist_names = [fallback] if fallback else []

        for artist_name in artist_names:
            button = ElidedButton(artist_name)
            configure_semantic_surface(button)
            button.setObjectName("song_info_artist_button")
            button.setProperty("artistName", artist_name)
            button.setCursor(Qt.PointingHandCursor)
            button.setFixedHeight(36)
            button.setToolTip(f"搜索作者：{artist_name}")
            button.setStyleSheet(
                f"QPushButton#song_info_artist_button {{ background-color: "
                f"rgba(236, 243, 250, 245); color: #1f4f78; border: 1px solid "
                f"#8ea8be; border-radius: 6px; padding: 0px 12px; text-align: left; "
                f"font-size: 17px; font-family: '{self.font_family}'; }}"
                f"QPushButton#song_info_artist_button:hover {{ background-color: "
                f"#dcecf8; border-color: #4d7fa5; }}"
                f"QPushButton#song_info_artist_button:pressed {{ background-color: "
                f"#c8dfef; }}"
            )
            button.clicked.connect(
                lambda _checked=False, name=artist_name: self.artist_clicked.emit(name)
            )
            self.authors_layout.addWidget(button)
        self.authors_layout.addStretch(1)

        self._clear_layout(self.metadata_layout)
        self.metadata_values = {}
        metadata = [
            ("时长", self._format_duration(getattr(track, "duration", 0))),
            ("专辑", str(getattr(track, "album", "") or "暂无数据")),
            (
                "发行时间",
                self._format_release_date(getattr(track, "release_time_ms", None)),
            ),
        ]

        aliases = list(getattr(track, "aliases", []) or [])
        if aliases:
            metadata.append(("别名", " / ".join(aliases)))
        track_position = self._format_track_position(track)
        if track_position:
            metadata.append(("音轨", track_position))

        for row, (key, value) in enumerate(metadata):
            key_label = QLabel(key)
            key_label.setStyleSheet(
                f"font-size: 15px; color: #68717b; background: transparent; "
                f"font-family: '{self.font_family}';"
            )
            value_label = ElidedLabel(value)
            value_label.setToolTip(value)
            value_label.setStyleSheet(
                f"font-size: 17px; color: #2e343a; background: transparent; "
                f"font-family: '{self.font_family}';"
            )
            self.metadata_layout.addWidget(key_label, row, 0, Qt.AlignTop)
            self.metadata_layout.addWidget(value_label, row, 1)
            self.metadata_values[key] = value_label

    def show_panel(self):
        """打开面板：对齐遮罩几何并确保卡片置顶。"""
        self._closing = False
        self._apply_target_geometry()
        self._constrain_card_height()
        self.show()
        self.raise_()
        if self._card is not None:
            self._card.raise_()

    def _apply_target_geometry(self):
        """将悬浮窗几何对齐到 overlay_target（转换到父窗口坐标系）。"""
        target = self._overlay_target
        parent = self.parent()
        if target is None or parent is None:
            return
        if target is parent:
            self.setGeometry(parent.rect())
        else:
            top_left = target.mapTo(parent, QPoint(0, 0))
            self.setGeometry(QRect(top_left, target.size()))

    def _constrain_card_height(self):
        """约束卡片高度，避免在小窗口中超出遮罩。"""
        if self._card is None:
            return
        target = self._overlay_target
        parent = self.parent()
        if target is None or parent is None:
            return
        available_h = target.size().height()
        max_h = max(360, available_h - 48)
        self._card.setFixedHeight(min(600, max_h))

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_target_geometry()
        self._constrain_card_height()
        if self._card is not None:
            self._card.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._constrain_card_height()

    def eventFilter(self, obj, event):
        """监听 overlay_target 的 Resize / Move，使遮罩跟随缩放与位移。"""
        if event.type() in (QEvent.Resize, QEvent.Move):
            QTimer.singleShot(0, self._apply_target_geometry)
            QTimer.singleShot(0, self._constrain_card_height)
        return False

    def keyPressEvent(self, event):
        """按 Esc 关闭面板。"""
        if event.key() == Qt.Key_Escape:
            self._close_panel()
        else:
            super().keyPressEvent(event)

    def _close_panel(self):
        if self._closing:
            return
        self._closing = True
        self.hide()
        self._closing = False


class _PlaylistLoadSignals(QObject):
    """把后台歌单加载结果安全地投递回 Qt 主线程。"""

    completed = pyqtSignal(int, str, object)
    failed = pyqtSignal(int, str)


class CircularLoadingIndicator(QWidget):
    """A lightweight, paint-only spinner that keeps Qt's event loop responsive."""

    def __init__(self, accent_color, parent=None):
        super().__init__(parent)
        configure_semantic_surface(self)
        self.setAccessibleName("歌单加载进度")
        self.setFixedSize(42, 42)
        self._angle = 0
        self._accent = QColor(accent_color)
        if not self._accent.isValid():
            self._accent = QColor("#3E76D1")
        self._timer = QTimer(self)
        self._timer.setInterval(32)
        self._timer.timeout.connect(self._advance)

    def start(self):
        if not self._timer.isActive():
            self._timer.start()
        self.update()

    def stop(self):
        self._timer.stop()

    def _advance(self):
        self._angle = (self._angle + 11) % 360
        self.update()

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        stroke = max(3, int(round(min(self.width(), self.height()) * 0.095)))
        bounds = self.rect().adjusted(stroke, stroke, -stroke, -stroke)

        track_color = QColor(self._accent)
        track_color.setAlpha(48)
        track_pen = QPen(track_color, stroke)
        track_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(track_pen)
        painter.drawEllipse(bounds)

        arc_color = QColor(self._accent)
        arc_color.setAlpha(245)
        arc_pen = QPen(arc_color, stroke)
        arc_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(arc_pen)
        painter.drawArc(bounds, (90 - self._angle) * 16, -270 * 16)


class PlaylistLoadingOverlay(QWidget):
    """Panel-scoped dimmer with a themed material loading card."""

    def __init__(self, parent, font_family, accent_color, text_color):
        super().__init__(parent)
        configure_material_overlay(self)
        self.setObjectName("playlist_loading_overlay")
        self.setAccessibleName("歌单加载状态")
        self.setFocusPolicy(Qt.NoFocus)
        self.setAutoFillBackground(False)
        self._target = parent
        self._target.installEventFilter(self)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setAlignment(Qt.AlignCenter)

        self.card = QFrame(self)
        configure_theme_card(self.card, preserve_outline=True)
        self.card.setObjectName("playlist_loading_card")
        self.card.setProperty("themeCornerRadius", 8.0)
        self.card.setFixedSize(184, 118)
        self.card.setStyleSheet("""
            #playlist_loading_card {
                background-color: rgba(248, 250, 252, 242);
                border: 1px solid rgba(255, 255, 255, 170);
                border-radius: 8px;
            }
        """)
        outer.addWidget(self.card)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(20, 16, 20, 14)
        card_layout.setSpacing(9)
        card_layout.setAlignment(Qt.AlignCenter)

        self.spinner = CircularLoadingIndicator(accent_color, self.card)
        card_layout.addWidget(self.spinner, 0, Qt.AlignCenter)

        self.label = QLabel("正在加载歌单", self.card)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(
            f"#playlist_loading_card QLabel {{ color: {text_color}; "
            f"font-size: 14px; font-family: '{font_family}'; }}"
        )
        card_layout.addWidget(self.label)

        self.setGeometry(self._target.rect())
        self.hide()

    def show_loading(self, playlist_name=""):
        self.setToolTip(playlist_name)
        self.setGeometry(self._target.rect())
        self.show()
        self.raise_()
        self.spinner.start()

    def hide_loading(self):
        self.spinner.stop()
        self.hide()
        self.setToolTip("")

    def hideEvent(self, event):
        self.spinner.stop()
        super().hideEvent(event)

    def eventFilter(self, watched, event):
        if watched is self._target and event.type() in {
            QEvent.Resize,
            QEvent.Show,
            QEvent.LayoutRequest,
        }:
            self.setGeometry(self._target.rect())
            if self.isVisible():
                self.raise_()
        return super().eventFilter(watched, event)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 174))


class StreamingPage(QWidget):
    """
    流媒体选项卡页面。
    实现搜索、歌单显示、歌曲播放等功能。
    """
    SONG_ROW_GAP = 8
    SONG_RENDER_BATCH_SIZE = 4
    SONG_DISPOSE_BATCH_SIZE = 8
    SONG_RENDER_INTERVAL_MS = 1

    def __init__(self, parent=None):
        super().__init__(parent)
        configure_transparent_root(self)
        self.parent_window = parent
        self.subsystem = MusicSubsystem()
        self.settings_manager = SettingsManager()

        self._playlist_load_request_id = 0
        self._playlist_load_thread = None
        self._playlist_prefetch_thread = None
        self._playlist_load_signals = _PlaylistLoadSignals(self)
        self._playlist_load_signals.completed.connect(self._on_playlist_load_completed)
        self._playlist_load_signals.failed.connect(self._on_playlist_load_failed)
        self._active_playlist_name = ""
        self._song_render_request_id = None
        self._song_render_tracks = []
        self._song_render_next_index = 0
        self._song_render_disposals = deque()
        self._song_render_timer = QTimer(self)
        self._song_render_timer.setSingleShot(True)
        self._song_render_timer.timeout.connect(self._render_next_song_batch)
        
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
        self._active_lyric_line_key = None
        
        self.init_ui()
        # The main window's 1080x720 baseline leaves roughly 960x720 for the
        # stacked page after the navigation rail. Keep every fixed metric in
        # this page on the same scale as that content area grows.
        self._ui_scaler = UniformUiScaler(self, base_width=960, base_height=720)
        self._apply_responsive_scale()
        
        # 状态更新定时器
        self.status_timer = QTimer(self)
        self.status_timer.setInterval(500)
        self.status_timer.timeout.connect(self.update_playback_status)
        self.status_timer.start()

        # 启动时自动恢复网易云登录会话
        self._restore_login_session()

        # 订阅设置变更信号
        self.shared_manager = get_shared_memory_manager()
        self.shared_manager.settings_changed.connect(self._on_settings_changed)
        
        debug_logger.info("StreamingPage", "流媒体页面已初始化。")
        
    def _apply_responsive_scale(self):
        """Scale fixed page metrics from the 960x720 design baseline."""
        scaler = getattr(self, "_ui_scaler", None)
        if scaler is not None:
            scaler.apply(self.width(), self.height())
        if hasattr(self, "song_layout"):
            # Keep list density stable while the row controls scale with the page.
            self.song_layout.setSpacing(self.SONG_ROW_GAP)

    def _set_responsive_style(self, widget, style):
        """Update page-owned QSS without losing its unscaled baseline."""
        scaler = getattr(self, "_ui_scaler", None)
        if scaler is None:
            widget.setStyleSheet(style)
        else:
            scaler.set_base_style(widget, style)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive_scale()

    def closeEvent(self, event):
        self._playlist_load_request_id += 1
        self._cancel_song_render()
        if hasattr(self, "playlist_loading_overlay"):
            self.playlist_loading_overlay.hide_loading()
        if hasattr(self, "status_timer"):
            self.status_timer.stop()
        if hasattr(self, "_song_info_panel") and self._song_info_panel is not None:
            self._song_info_panel.hide()
        super().closeEvent(event)

    def _on_settings_changed(self, section, data):
        """处理自定义设置更改，动态更新面板颜色

        左/右/底面板跟随卡片背景色 (card_background_color)，
        歌词区跟随组件背景色 (component_background_color)。
        """
        if section != 'custom':
            return

        changed_keys = set(data.keys()) if isinstance(data, dict) else set()

        # 1. 卡片背景色 → 左/右/底面板
        if 'card_background_color' in changed_keys:
            card_bg = data.get('card_background_color')
            if card_bg and getattr(self, "theme_service", None) is None:
                if hasattr(self, 'left_outer'):
                    self._set_responsive_style(
                        self.left_outer,
                        f"QFrame {{ background-color: {card_bg}; border-radius: 12px; }}",
                    )

                if hasattr(self, 'song_scroll') and hasattr(self, 'song_container'):
                    self._set_responsive_style(self.song_scroll, f"""
                        QScrollArea {{
                            background-color: {card_bg};
                            border-radius: 10px;
                            border: none;
                        }}
                    """)
                    self._set_responsive_style(
                        self.song_container,
                        f"background-color: {card_bg}; border-radius: 10px;",
                    )

                if hasattr(self, 'player_bar'):
                    self._set_responsive_style(self.player_bar, f"""
                        QFrame {{
                            background-color: {card_bg};
                            border-radius: 10px;
                        }}
                    """)

        # 2. 组件背景色 → 歌词区
        if 'component_background_color' in changed_keys:
            component_bg = data.get('component_background_color')
            if component_bg and hasattr(self, 'lyrics_label'):
                font_family = self.settings_manager.get_Custom_value("global_font", "微软雅黑")
                self._set_responsive_style(self.lyrics_label, f"""
                    color: #333333;
                    font-size: 21px;
                    font-family: '{font_family}';
                    background-color: {component_bg};
                    border-radius: 8px;
                    padding: 8px 15px;
                """)

    # ---------- 网易云登录 ----------

    def _restore_login_session(self):
        """启动时从设置中恢复网易云登录会话。"""
        if not PYNCM_LOGIN_AVAILABLE:
            return
        try:
            session_dump = self.settings_manager.streaming.get_value("ncm_session", "")
            if session_dump:
                self.subsystem.provider.restore_session(session_dump)
        except Exception as e:
            debug_logger.warning("StreamingPage", f"恢复登录会话失败: {str(e)}")
        finally:
            self.update_login_btn()

    def update_login_btn(self):
        """根据登录状态更新登录按钮文字。"""
        if not PYNCM_LOGIN_AVAILABLE:
            self.login_btn.setText("👤 登录不可用")
            self.login_btn.setEnabled(False)
            return
        info = self.subsystem.provider.get_login_info()
        if info and info.get("nickname"):
            self.login_btn.setText(f"👤 {info['nickname']}")
        else:
            self.login_btn.setText("👤 登录")

    def show_login_menu(self):
        """点击登录/账号按钮：弹出悬浮面板。
        已登录 → account 模式（展示账号详情 + 切换/登出按钮）
        未登录 → login 模式（扫码登录）
        """
        self._open_login_panel(mode="account" if self.subsystem.provider.is_logged_in() else "login")

    def _open_login_panel(self, mode="login"):
        """打开登录/账号悬浮面板。

        mode="login"：扫码登录面板
        mode="account"：已登录态账号信息面板
        """
        if not PYNCM_LOGIN_AVAILABLE:
            QMessageBox.warning(self, "不可用", "pyncm 登录模块不可用。")
            return
        # 同一时间只允许一个面板
        if hasattr(self, "_login_panel") and self._login_panel is not None:
            self._login_panel.close()

        if mode == "account":
            # 已登录态：只展示账号信息，不需要 qrcode
            self._login_panel = QrCodeLoginDialog(
                self.window(), overlay_target=self.parent(), mode="account"
            )
        else:
            if not QRCODE_AVAILABLE:
                QMessageBox.warning(self, "不可用", "qrcode 库未安装，无法生成二维码。")
                return
            self._login_panel = QrCodeLoginDialog(
                self.window(), overlay_target=self.parent(), mode="login"
            )

        # 面板关闭后检查登录结果
        self._login_panel.closed.connect(self._on_login_panel_closed)
        # account 模式下的信号
        self._login_panel.switch_to_login_requested.connect(self._on_switch_account_requested)
        self._login_panel.logout_requested.connect(self._do_logout)
        self._login_panel.show()

    def _on_login_panel_closed(self):
        """登录面板关闭后，仅 login 模式下检查是否登录成功并持久化。"""
        panel = self._login_panel
        self._login_panel = None
        # account 模式面板关闭不需要持久化或弹"登录成功"
        if panel is None or getattr(panel, '_mode', '') != 'login':
            return
        if self.subsystem.provider.is_logged_in():
            self._on_login_success()

    def _on_login_success(self):
        """登录成功后的统一处理：持久化会话 + 更新 UI。"""
        try:
            session_dump = self.subsystem.provider.dump_session()
            if session_dump:
                self.settings_manager.streaming.set_value("ncm_session", session_dump)
                debug_logger.info("StreamingPage", "登录会话已持久化。")
        except Exception as e:
            debug_logger.error("StreamingPage", f"持久化登录会话失败: {str(e)}")
        self.update_login_btn()
        info = self.subsystem.provider.get_login_info()
        if info.get("nickname"):
            QMessageBox.information(self, "登录成功", f"欢迎，{info['nickname']}！")

    def _on_switch_account_requested(self):
        """account 面板中点击「切换账号」后，重新打开扫码登录面板。"""
        self._open_login_panel(mode="login")

    def _do_logout(self):
        """执行登出。"""
        ret = QMessageBox.question(self, "确认", "确定要登出网易云账号吗？")
        if ret != QMessageBox.Yes:
            return
        try:
            self.subsystem.provider.logout()
        except Exception:
            pass
        try:
            self.settings_manager.streaming.set_value("ncm_session", "")
        except Exception:
            pass
        self.update_login_btn()
        QMessageBox.information(self, "已登出", "已退出网易云账号。")

    def init_ui(self):
        # 获取全局字体设置
        font_family = self.settings_manager.get_Custom_value("global_font", "微软雅黑")
        accent_color = self.settings_manager.get_Custom_value(
            "highlight_button_color", "#3E76D1"
        )
        text_color = self.settings_manager.get_Custom_value("text_color", "#202A35")
        self.setObjectName("streaming_page_root")
        self.setStyleSheet(
            f"#streaming_page_root {{ font-family: '{font_family}'; }}"
        )

        main_layout = QVBoxLayout(self)
        # Scaled child minima must not prevent the page from receiving a later
        # smaller geometry; resizeEvent needs that geometry to scale them down.
        main_layout.setSizeConstraint(QLayout.SetNoConstraint)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(10)

        # --- 顶部搜索栏 ---
        search_layout = QHBoxLayout()
        search_layout.setSpacing(12)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search for...")
        self.search_input.setFixedSize(225, 65)
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

        # 登录按钮（未登录显示"登录"，已登录显示昵称）
        search_layout.addStretch(1)
        self.login_btn = QPushButton("👤 登录")
        self.login_btn.setFixedHeight(50)
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: white;
                border: 1px solid #AAAAAA;
                border-radius: 25px;
                padding: 0 20px;
                font-size: 18px;
                color: #333333;
                font-family: '{font_family}';
            }}
            QPushButton:hover {{ background-color: #f0f0f0; }}
        """)
        self.login_btn.clicked.connect(self.show_login_menu)
        search_layout.addWidget(self.login_btn)

        main_layout.addLayout(search_layout)

        # --- 中间内容区 ---
        content_layout = QHBoxLayout()
        content_layout.setSpacing(10)

        # === 左侧歌单栏 — 全部包在一个大圆角灰色容器里 ===
        card_bg = self.settings_manager.get_Custom_value("card_background_color", "#F5F8FF")
        self.left_outer = QFrame()
        configure_theme_card(self.left_outer, preserve_outline=True)
        self.left_outer.setFixedWidth(180)
        self.left_outer.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)  # 纵向拉伸
        self.left_outer.setStyleSheet(f"QFrame {{ background-color: {card_bg}; border-radius: 12px; }}")
        left_outer_layout = QVBoxLayout(self.left_outer)
        left_outer_layout.setContentsMargins(10, 10, 10, 10)
        left_outer_layout.setSpacing(8)

        # 内部：滚动歌单列表，视口占满面板顶部到分割线之间的全部高度
        self.playlist_container = QWidget()
        configure_transparent_container(self.playlist_container)
        self.playlist_layout = QVBoxLayout(self.playlist_container)
        self.playlist_layout.setContentsMargins(0, 0, 0, 0)
        self.playlist_layout.setSpacing(8)

        self.playlist_scroll = QScrollArea()
        self.playlist_scroll.setWidgetResizable(True)
        self.playlist_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.playlist_scroll.setStyleSheet("""
            QScrollArea { border: none; background-color: transparent; }
            QScrollBar:vertical { width: 8px; background: transparent; border-radius: 4px; }
            QScrollBar::handle:vertical { background: #888888; border-radius: 4px; }
        """)
        set_transparent_scroll_content(self.playlist_scroll, self.playlist_container)

        self.update_playlist_display()

        # 列表区域拉伸填满可用高度；歌单数量超出视口时由滚动区滚动
        left_outer_layout.addWidget(self.playlist_scroll, 1)

        # 分隔线
        sep_line = QFrame()
        sep_line.setFrameShape(QFrame.HLine)
        sep_line.setStyleSheet("color: #999999;")
        left_outer_layout.addWidget(sep_line)

        # 底部：歌单管理 (1.5倍字体)
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

        left_outer_layout.addWidget(self.manage_btn)

        # left_panel_container 纵向拉伸以填满
        left_panel_container = QVBoxLayout()
        left_panel_container.setContentsMargins(0, 0, 0, 0)
        left_panel_container.setSpacing(0)
        left_panel_container.addWidget(self.left_outer, 1) # 1 表示拉伸

        # === 右侧歌曲显示区（含标题） ===
        self.right_panel_container = QWidget()
        configure_transparent_container(self.right_panel_container)
        right_panel = QVBoxLayout(self.right_panel_container)
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

        self.song_scroll = QScrollArea()
        configure_theme_card(self.song_scroll, preserve_outline=True)
        configure_transparent_container(self.song_scroll)
        self.song_scroll.setWidgetResizable(True)
        self.song_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.song_scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
        """)

        self.song_container = QWidget()
        configure_transparent_container(self.song_container)
        self.song_layout = QVBoxLayout(self.song_container)
        self.song_layout.setAlignment(Qt.AlignTop)
        self.song_layout.setContentsMargins(6, 6, 6, 6)
        self.song_layout.setSpacing(self.SONG_ROW_GAP)
        set_transparent_scroll_content(self.song_scroll, self.song_container)

        right_panel.addWidget(self.song_scroll, 1)

        self.playlist_loading_overlay = PlaylistLoadingOverlay(
            self.right_panel_container,
            font_family,
            accent_color,
            text_color,
        )
        # Keep the previous attribute as a compatibility alias for page tests
        # and integrations that only inspect loading visibility.
        self.playlist_loading_widget = self.playlist_loading_overlay

        content_layout.addLayout(left_panel_container)
        content_layout.addWidget(self.right_panel_container, 1)
        main_layout.addLayout(content_layout, 1)

        # --- 底部播放控制栏 ---
        # 布局：
        #   上行：[歌词区] | [分隔] | [歌名/作者] | [⏮ ▶ ⏭] | [🔊]
        #   下行：[————————————————进度条————————————————]
        bottom_bg = card_bg
        
        self.player_bar = QFrame()
        configure_theme_card(self.player_bar, preserve_outline=True)
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

        # 左：歌词显示区域（使用组件背景色）
        lyrics_bg = self.settings_manager.get_Custom_value("component_background_color", "#ffffff")
        self.lyrics_label = ScrollingLabel()
        configure_semantic_surface(self.lyrics_label)
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
        self.lyrics_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
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
        self.progress_slider.setFixedHeight(20)
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



    @staticmethod
    def _resolve_lyric_line(lyrics_list, pos_ms, track_duration):
        """返回当前歌词的索引、文本和从当前播放位置起的剩余显示时长。"""
        current_index = None
        for index in range(len(lyrics_list) - 1, -1, -1):
            if lyrics_list[index][0] <= pos_ms:
                current_index = index
                break

        if current_index is None:
            return None, "...", None

        line_start_ms, current_text = lyrics_list[current_index]
        line_end_ms = next(
            (
                timestamp_ms
                for timestamp_ms, _ in lyrics_list[current_index + 1:]
                if timestamp_ms > line_start_ms
            ),
            track_duration,
        )
        try:
            remaining_ms = line_end_ms - pos_ms if line_end_ms is not None else 0
        except (TypeError, ValueError):
            remaining_ms = 0
        return current_index, current_text or "...", remaining_ms if remaining_ms > 0 else None

    def update_playback_status(self):
        """更新播放状态 (定时触发)"""
        if not self.subsystem.current_track:
            self._active_lyric_line_key = None
            self.lyrics_label.pause_scroll()
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
            lyric_index, current_text, display_duration_ms = self._resolve_lyric_line(
                lyrics_list,
                pos_ms,
                track.duration,
            )
            line_key = (
                id(track),
                getattr(self.subsystem.player, "current_play_id", None),
                lyric_index,
            )
            if (
                self._active_lyric_line_key != line_key
                or getattr(self.lyrics_label, 'original_text', '') != current_text
            ):
                self.lyrics_label.set_scrolling_text(current_text, display_duration_ms)
                self._active_lyric_line_key = line_key
        else:
            # 尝试后台加载
            self._active_lyric_line_key = None
            self.subsystem.get_current_lyrics()
            if getattr(self.lyrics_label, 'original_text', '') != "暂无歌词":
                self.lyrics_label.set_scrolling_text("暂无歌词")

        if self.subsystem.player.is_playing and not self.subsystem.player.is_paused:
            self.lyrics_label.resume_scroll()
        else:
            self.lyrics_label.pause_scroll()

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
                self.lyrics_label.resume_scroll()
            else:
                self.subsystem.pause()
                self.lyrics_label.pause_scroll()

    def handle_seek(self, value):
        """处理进度条跳转"""
        if self.subsystem.current_track:
            total_ms = self.subsystem.current_track.duration
            target_ms = int((value / 1000.0) * total_ms)
            self.subsystem.player.set_pos(target_ms)
            self._active_lyric_line_key = None

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
            # 首次使用：注入预设歌单并持久化保存
            presets = self._get_preset_playlists()
            for p in presets:
                result.append({"name": p["name"], "url": p["url"]})
            # 持久化（排除内部播放列表）
            data = ";".join([f"{p['name']}|{p['url']}" for p in presets])
            self.settings_manager.set_Custom_value("music_playlists", data)
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

    def _get_preset_playlists(self):
        """内置预设歌单（网易云歌单）"""
        return [
            {"name": "自然白噪音",   "url": "https://music.163.com/playlist?id=2845772415"},
            {"name": "LoFi HipHop", "url": "https://music.163.com/playlist?id=2540031947"},
            {"name": "影视飓风《样片日记》旅行bgm", "url": "https://music.163.com/playlist?id=9360572545"},
            {"name": "劲爆音游曲",   "url": "https://music.163.com/playlist?id=7625727312"},
        ]

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
        tracks_data = [t.to_dict() for t in self.queue_tracks]
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
        """创建歌单按钮。
        
        歌单名嵌入 ScrollingLabel：当文本像素宽度超过按钮可用宽度（算法判定为“超长”）时，
        自动横向滚动以完整展示；否则原样完整显示。滚动动画复用歌词展示框（ScrollingLabel）逻辑。
        鼠标悬停时暂停滚动，便于阅读。
        """
        # 获取当前字体
        font_family = self.settings_manager.get_Custom_value("global_font", "微软雅黑")
        
        btn = QPushButton()
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

        # 用 ScrollingLabel 承载歌单名，实现“超长滚动、否则完整显示”
        label = ScrollingLabel(btn)
        label.set_scrolling_text(name)
        # 与按钮内边距/字体保持一致，确保超长判定准确
        label.setStyleSheet(f"""
            ScrollingLabel {{
                background-color: transparent;
                border: none;
                color: #333333;
                font-size: 21px;
                font-family: '{font_family}';
                padding: 0px;
            }}
        """)
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        # 将 label 铺满按钮内容区，宽高跟随按钮
        layout = QHBoxLayout(btn)
        layout.setContentsMargins(8, 0, 8, 0)  # 留出左右内边距，避免文字贴边
        layout.setSpacing(0)
        layout.addWidget(label)

        # 鼠标悬停/离开按钮时控制滚动：悬停暂停，离开恢复（仅超长时实际生效）
        btn.enterEvent = lambda e: label.pause_scroll()
        btn.leaveEvent = lambda e: label.resume_scroll()

        btn.clicked.connect(lambda checked, idx=index: self.handle_playlist_click(idx))
        return btn

    def handle_search(self):
        """处理搜索请求"""
        keyword = self.search_input.text().strip()
        if not keyword:
            return

        self._cancel_pending_playlist_load()
        self.current_keyword = keyword
        self._active_playlist_name = ""
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
        self._hide_song_info()
        self.search_input.setText(artist_name)
        self.handle_search()
        self.list_title_label.setText(f"搜索结果——{artist_name}")

    def _show_song_info(self, track):
        """打开歌曲详情悬浮面板（样式与歌单管理面板一致）。"""
        if track is None:
            return
        if not hasattr(self, "_song_info_panel") or self._song_info_panel is None:
            self._song_info_panel = SongInfoPanel(
                self.window(), overlay_target=self.parent()
            )
            self._song_info_panel.artist_clicked.connect(
                self._handle_popup_artist_search
            )
        self._song_info_panel.set_track(track)
        self._song_info_panel.show_panel()

    def _hide_song_info(self):
        if hasattr(self, "_song_info_panel") and self._song_info_panel is not None:
            self._song_info_panel.hide()

    def _handle_popup_artist_search(self, artist_name):
        self._hide_song_info()
        self.handle_artist_search(artist_name)

    def handle_playlist_click(self, index):
        """处理点击歌单"""
        if index < 0 or index >= len(self.playlists):
            return
            
        playlist = self.playlists[index]
        debug_logger.info("StreamingPage", f"切换至歌单: {playlist['name']}")
        
        self.current_keyword = "" # 歌单模式下清除搜索关键词
        
        # 特殊处理内部播放列表
        if playlist['url'] == "internal://queue":
            self._cancel_pending_playlist_load()
            self.subsystem.activate_playlist(self.queue_tracks)
            self.display_songs(self.queue_tracks, clear=True)
            self.list_title_label.setText("播放列表")
            self._active_playlist_name = "播放列表"
            return

        # 合并歌单与普通歌单使用同一后台加载链路。
        if playlist['url'].startswith("merged://"):
            source_urls = playlist['url'][len("merged://"):].split("||")
        else:
            source_urls = [playlist['url']]

        self._start_playlist_load(playlist['name'], source_urls)

    def _start_playlist_load(self, playlist_name, source_urls):
        """启动歌单加载，点击处理函数本身不执行任何网络请求。"""
        self._playlist_load_request_id += 1
        request_id = self._playlist_load_request_id
        self._cancel_song_render()
        self._set_playlist_loading(True, playlist_name)

        worker = threading.Thread(
            target=self._load_playlist_worker,
            args=(request_id, playlist_name, tuple(source_urls)),
            daemon=True,
            name=f"playlist-loader-{request_id}",
        )
        self._playlist_load_thread = worker
        worker.start()

    def _load_playlist_worker(self, request_id, playlist_name, source_urls):
        """后台加载一个或多个歌单；链接预取不阻塞列表交付。"""
        try:
            tracks = []
            seen_ids = set()
            for source_url in source_urls:
                for track in self.subsystem.load_playlist_tracks(source_url):
                    if track.song_id in seen_ids:
                        continue
                    seen_ids.add(track.song_id)
                    tracks.append(track)

            if not tracks:
                self._playlist_load_signals.failed.emit(
                    request_id,
                    "无法导入该歌单，请检查链接或网络连接。",
                )
                return

            self._playlist_load_signals.completed.emit(request_id, playlist_name, tracks)
        except Exception as exc:
            debug_logger.error("StreamingPage", f"后台加载歌单失败: {str(exc)}")
            self._playlist_load_signals.failed.emit(request_id, "加载歌单时发生错误，请稍后重试。")

    def _on_playlist_load_completed(self, request_id, playlist_name, tracks):
        """只应用最新一次选择的歌单，过期线程结果直接丢弃。"""
        if request_id != self._playlist_load_request_id:
            return

        self.subsystem.activate_playlist(tracks)
        self.list_title_label.setText(f"歌单——{playlist_name}")
        self._active_playlist_name = playlist_name
        self._start_playlist_prefetch(request_id, tracks)
        self._begin_song_render(request_id, playlist_name, tracks)
        debug_logger.info(
            "StreamingPage",
            f"歌单数据加载完成，开始分批渲染: {playlist_name}，共 {len(tracks)} 首",
        )

    def _start_playlist_prefetch(self, request_id, tracks):
        """预取首批播放链接，但不再把它作为歌单可见的前置条件。"""
        snapshot = tuple(tracks[:5])
        worker = threading.Thread(
            target=self.subsystem.prefetch_tracks,
            args=(snapshot, 5),
            daemon=True,
            name=f"playlist-prefetch-{request_id}",
        )
        self._playlist_prefetch_thread = worker
        worker.start()

    def _begin_song_render(self, request_id, playlist_name, tracks):
        """Render a large playlist in bounded batches on the GUI event loop."""
        self._cancel_song_render()
        self.song_scroll.setUpdatesEnabled(False)
        while self.song_layout.count():
            item = self.song_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                self._song_render_disposals.append(widget)

        self.song_scroll.verticalScrollBar().setValue(0)
        self._song_render_request_id = request_id
        self._song_render_playlist_name = playlist_name
        self._song_render_tracks = list(tracks)
        self._song_render_next_index = 0
        self._song_render_timer.start(self.SONG_RENDER_INTERVAL_MS)

    def _render_next_song_batch(self):
        request_id = self._song_render_request_id
        if request_id is None or request_id != self._playlist_load_request_id:
            self._cancel_song_render()
            return

        for _ in range(self.SONG_DISPOSE_BATCH_SIZE):
            if not self._song_render_disposals:
                break
            self._song_render_disposals.popleft().deleteLater()

        start = self._song_render_next_index
        end = min(start + self.SONG_RENDER_BATCH_SIZE, len(self._song_render_tracks))
        for offset in range(start, end):
            self._append_song_widget(
                offset + 1,
                self._song_render_tracks[offset],
                is_queue_view=False,
                apply_scale=True,
            )
        self._song_render_next_index = end

        if end < len(self._song_render_tracks) or self._song_render_disposals:
            self._song_render_timer.start(self.SONG_RENDER_INTERVAL_MS)
            return

        playlist_name = self._song_render_playlist_name
        track_count = len(self._song_render_tracks)
        self._cancel_song_render()
        if request_id == self._playlist_load_request_id:
            self._set_playlist_loading(False)
            debug_logger.info(
                "StreamingPage",
                f"歌单后台加载完成: {playlist_name}，共 {track_count} 首",
            )

    def _cancel_song_render(self):
        self._song_render_timer.stop()
        if hasattr(self, "song_scroll"):
            self.song_scroll.setUpdatesEnabled(True)
            self.song_scroll.viewport().update()
        self._song_render_request_id = None
        self._song_render_playlist_name = ""
        self._song_render_tracks = []
        self._song_render_next_index = 0

    def _on_playlist_load_failed(self, request_id, message):
        """在主线程收尾失败状态。"""
        if request_id != self._playlist_load_request_id:
            return

        self._cancel_song_render()
        self._set_playlist_loading(False)
        QMessageBox.warning(self, "错误", message)

    def _cancel_pending_playlist_load(self):
        """使仍在执行的请求失效；网络线程结束后不会覆盖当前页面。"""
        self._playlist_load_request_id += 1
        self._cancel_song_render()
        self._set_playlist_loading(False)

    def _set_playlist_loading(self, loading, playlist_name=""):
        """切换非模态加载状态，页面其余控件保持可响应。"""
        if loading:
            self.playlist_loading_overlay.show_loading(playlist_name)
        else:
            self.playlist_loading_overlay.hide_loading()
        self.play_all_btn.setEnabled(not loading)

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
            current_playlist_name = self._active_playlist_name or "未知歌单"
            self.list_title_label.setText(f"歌单——{current_playlist_name}")

    def display_songs(self, tracks, clear=True):
        """在右侧区域显示歌曲列表"""
        self._hide_song_info()
        self._cancel_song_render()
        while self._song_render_disposals:
            self._song_render_disposals.popleft().deleteLater()
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
            self._append_song_widget(i, track, is_queue_view=is_queue_view)

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

        # ??/??????????????????????
        self._apply_responsive_scale()

    def _append_song_widget(self, index, track, *, is_queue_view, apply_scale=False):
        widget = SongItemWidget(index, track, is_queue=is_queue_view)
        widget.play_clicked.connect(self.subsystem.play_by_index)
        widget.details_requested.connect(self._show_song_info)
        widget.add_to_queue_requested.connect(self.handle_add_to_queue)
        widget.delete_requested.connect(self.handle_delete_song)
        self.song_layout.addWidget(widget)
        if apply_scale:
            scaler = getattr(self, "_ui_scaler", None)
            if scaler is not None and abs(scaler.scale - 1.0) >= 0.0001:
                scaler.apply_subtree(widget)
        return widget

    def show_playlist_menu(self):
        """打开歌单管理悬浮面板"""
        # 同一时间只允许一个面板
        if hasattr(self, "_manage_panel") and self._manage_panel is not None:
            self._manage_panel.close()
        # 挂到顶层主窗口下：QStackedWidget 的 page 不随主窗口 resize，
        # 挂到主窗口下才能正确跟随窗口缩放。
        # overlay_target = self.parent()（即 stacked_widget），
        # 遮罩只覆盖内容区域，不含左侧 tab 栏。
        self._manage_panel = PlaylistManagePanel(self.playlists, self.window(), overlay_target=self.parent())
        # 连接操作信号
        self._manage_panel.playlist_add_requested.connect(self._on_playlist_added)
        self._manage_panel.playlist_delete_requested.connect(self._on_playlist_deleted)
        self._manage_panel.playlist_edit_requested.connect(self._on_playlist_edited)
        self._manage_panel.playlist_merge_requested.connect(self._on_playlists_merged)
        self._manage_panel.playlist_clear_requested.connect(self._on_playlists_cleared)
        self._manage_panel.closed.connect(self._on_manage_panel_closed)
        self._manage_panel.show()

    def _on_manage_panel_closed(self):
        """歌单管理面板关闭后的清理"""
        self._manage_panel = None

    def _on_playlist_added(self, name, url):
        """处理悬浮窗发起的添加歌单请求"""
        self.playlists.append({"name": name, "url": url})
        self._save_playlists()
        self.update_playlist_display()
        debug_logger.info("StreamingPage", f"已添加歌单: {name}")

    def _on_playlist_deleted(self, name):
        """处理悬浮窗发起的删除歌单请求"""
        self.playlists = [p for p in self.playlists if p['name'] != name]
        self._save_playlists()
        self.update_playlist_display()
        debug_logger.info("StreamingPage", f"已删除歌单: {name}")

    def _on_playlist_edited(self, old_name, new_name, new_url):
        """处理悬浮窗发起的编辑歌单请求"""
        for p in self.playlists:
            if p['name'] == old_name:
                p['name'] = new_name
                p['url'] = new_url
                break
        self._save_playlists()
        self.update_playlist_display()
        debug_logger.info("StreamingPage", f"已编辑歌单: {old_name} -> {new_name}")

    def _on_playlists_merged(self, new_name, urls):
        """处理悬浮窗发起的合并歌单请求
        
        将多个歌单 URL 合并为一个特殊格式的歌单，URL 格式为：
        merged://url1||url2||url3
        点击时依次从所有源加载歌曲并合并去重。
        """
        merged_url = "merged://" + "||".join(urls)
        self.playlists.append({"name": new_name, "url": merged_url})
        self._save_playlists()
        self.update_playlist_display()
        debug_logger.info("StreamingPage", f"已合并创建歌单: {new_name}，包含 {len(urls)} 个源")

    def _on_playlists_cleared(self):
        """处理悬浮窗发起的清空所有歌单请求"""
        self.playlists = [p for p in self.playlists if p['url'] == "internal://queue"]
        self._save_playlists()
        self.update_playlist_display()
        debug_logger.info("StreamingPage", "已清空所有自定义歌单")

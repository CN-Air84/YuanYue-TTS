# coding=utf-8
import sys
import json
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QLineEdit, QPushButton, QGroupBox, QFormLayout,
    QSpinBox, QDoubleSpinBox, QScrollArea, QCheckBox, QSlider, QFileDialog,
    QStackedWidget, QButtonGroup, QGraphicsOpacityEffect, QFrame, QSizePolicy,
    QGridLayout, QApplication, QSplitter, QMessageBox
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QObject, QEvent, QVariantAnimation, pyqtProperty, 
    QPropertyAnimation, QParallelAnimationGroup, QEasingCurve, QUrl, QTimer,
    QMimeData
)
from PyQt5.QtGui import QFont, QColor, QDesktopServices, QDrag, QPixmap

from misc_func import SettingsManager, CustomConfig
from shared_memory_manager import get_shared_memory_manager
from debug_logger import debug_logger, LogLevel

_AI_MANAGER_MODULE = None


def _get_ai_manager_module():
    """按需加载 ai_manager，避免设置页模块导入时拉起重依赖。"""
    global _AI_MANAGER_MODULE
    if _AI_MANAGER_MODULE is None:
        import ai_manager as ai_manager_module
        _AI_MANAGER_MODULE = ai_manager_module
    return _AI_MANAGER_MODULE


class WheelEventFilter(QObject):
    """鼠标滚轮事件过滤器 - 禁止通过滚轮改变数值"""
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel:
            return True
        return False


class SmoothButton(QPushButton):
    """平滑变色动画按钮"""
    def __init__(self, text, btn_type="normal", parent=None):
        super().__init__(text, parent)
        self.btn_type = btn_type
        self.setCheckable(True)
        
        self.normal_bg = QColor(255, 255, 255)
        self.normal_color = QColor(0, 0, 0)
        self.normal_border = QColor("gray")
        
        if btn_type == "tab_level1" or btn_type == "tab_level2":
            self.checked_bg = QColor(85, 85, 255)
            self.checked_color = QColor(255, 255, 255)
            self.checked_border = QColor("gray")
            self.radius = 5
            self.padding = "8px 16px"
        elif btn_type == "model":
            self.checked_bg = QColor(0, 255, 0)
            self.checked_color = QColor(0, 0, 0)
            self.checked_border = QColor("#D0D0D0")
            self.radius = 4
            self.padding = "12px"
        elif btn_type == "action":
            self.normal_bg = QColor(85, 170, 255) 
            self.normal_color = QColor(255, 255, 255)
            self.normal_border = QColor("gray")
            self.checked_bg = self.normal_bg
            self.checked_color = self.normal_color
            self.checked_border = self.normal_border
            self.radius = 5
            self.padding = "8px 16px"
            self.setCheckable(False)
        else:
            self.checked_bg = QColor(230, 230, 230)
            self.checked_color = QColor(0, 0, 0)
            self.checked_border = QColor("gray")
            self.radius = 5
            self.padding = "8px 16px"
            
        self._bg_color = self.checked_bg if self.isChecked() else self.normal_bg
        self._text_color = self.checked_color if self.isChecked() else self.normal_color
        
        self.bg_anim = QVariantAnimation(self)
        self.bg_anim.setDuration(250)
        self.bg_anim.valueChanged.connect(self._on_bg_changed)
        
        self.color_anim = QVariantAnimation(self)
        self.color_anim.setDuration(250)
        self.color_anim.valueChanged.connect(self._on_color_changed)
        
        self.toggled.connect(self._on_toggled)
        self._update_stylesheet()
        
    def _on_toggled(self, checked):
        if self.btn_type == "action": return
        self.bg_anim.stop()
        self.color_anim.stop()
        
        self.bg_anim.setStartValue(self._bg_color)
        self.bg_anim.setEndValue(self.checked_bg if checked else self.normal_bg)
        
        self.color_anim.setStartValue(self._text_color)
        self.color_anim.setEndValue(self.checked_color if checked else self.normal_color)
        
        self.bg_anim.start()
        self.color_anim.start()

    def _on_bg_changed(self, color):
        self._bg_color = color
        self._update_stylesheet()
        
    def _on_color_changed(self, color):
        self._text_color = color
        self._update_stylesheet()
        
    def _update_stylesheet(self):
        border_color = self.checked_border.name() if self.isChecked() else self.normal_border.name()
        if self.btn_type == "model":
            border_color = "#D0D0D0"
        
        css = f"""
            QPushButton {{
                background-color: {self._bg_color.name()};
                color: {self._text_color.name()};
                border: 1px solid {border_color};
                border-radius: {self.radius}px;
                padding: {self.padding};
            }}
        """
        self.setStyleSheet(css)


class StyledContainer(QFrame):
    """带圆角白底灰边的容器"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            StyledContainer {
                background-color: #FFFFFF;
                border: 1px solid #D0D0D0;
                border-radius: 5px;
            }
        """)

class ApiKeyConfigWidget(QWidget):
    """API Key 配置页面"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings_manager = SettingsManager()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #D0D0D0;
                border-radius: 8px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        frame_layout = QVBoxLayout(frame)
        
        form_layout = QFormLayout()
        form_layout.setSpacing(20)
        form_layout.setContentsMargins(20, 20, 20, 20)
        
        providers = [
            ("智谱AI开放平台", "api_key_ChatGLM", "https://www.bigmodel.cn/invite?icode=%2FveqUy%2BfLWQAs9oUDFwAmZmwcr074zMJTpgMb8zZZvg%3D"),
            ("阿里云百炼", "api_key_Qwen", "https://bailian.console.aliyun.com/"),
            ("Kimi开放平台", "api_key_KIMI", "https://platform.moonshot.cn/"),
            ("Minimax开放平台", "api_key_Minimax", "https://platform.minimaxi.com/"),
            ("Mimo开放平台", "api_key_Mimo", "https://platform.xiaomimimo.com/")
        ]
        
        self.inputs = {}
        for name, key, url in providers:
            row_layout = QHBoxLayout()
            row_layout.setSpacing(10)
            
            inp = QLineEdit()
            inp.setText(self.settings_manager.get_api_key(key))
            inp.textChanged.connect(lambda text, k=key: self.settings_manager.set_api_key(k, text))
            inp.setStyleSheet("""
                QLineEdit {
                    background-color: rgb(255, 255, 255);
                    border: 1px solid #D0D0D0;
                    border-radius: 4px;
                    padding: 8px;
                }
            """)
            self.inputs[key] = inp
            
            btn = SmoothButton("注册并获取API Key", btn_type="action")
            btn.clicked.connect(lambda checked, u=url: QDesktopServices.openUrl(QUrl(u)))
            
            row_layout.addWidget(inp)
            row_layout.addWidget(btn)
            
            label = QLabel(name + ":")
            form_layout.addRow(label, row_layout)
            
        frame_layout.addLayout(form_layout)
        
        hint = QLabel("后期还将逐步支持智谱国际（Z.ai）、Kimi国际、Minimax国际、阶跃星辰、Deepseek、华为盘古、阿里云魔搭、腾讯云、火山引擎、硅基流动等各大平台，感谢您的理解与支持。")
        hint.setAlignment(Qt.AlignCenter)
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #666666; margin-top: 20px;")
        frame_layout.addWidget(hint)
        
        layout.addWidget(frame)
        layout.addStretch()


class AiModelConfigWidget(QWidget):
    """AI模型设置页面"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings_manager = SettingsManager()
        self.ai_module = _get_ai_manager_module()
        self.current_scene = self.ai_module.AIScene.CHAT
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 0)
        
        # --- Left Panel ---
        self.left_panel_container = StyledContainer()
        left_panel = QVBoxLayout(self.left_panel_container)
        left_panel.setContentsMargins(10, 10, 10, 10)
        left_panel.setSpacing(10)
        
        # Providers (可不选 + 不可多选)
        self.providers = {
            "智谱AI": "ChatGLM",
            "阿里云百炼": "Qwen",
            "Kimi": "KIMI",
            "Minimax": "Minimax",
            "其他": "Mimo"
        }
        self.provider_btns = {}
        for name, pid in self.providers.items():
            btn = SmoothButton(name, "tab_level2")
            btn.clicked.connect(lambda checked, p=pid: self._on_provider_clicked(p, checked))
            left_panel.addWidget(btn)
            self.provider_btns[pid] = btn
            
        left_panel.addSpacing(20)
        
        # Tiers (必选 + 可多选)
        self.tiers = {
            "永久免费": self.ai_module.ModelTier.FREE,
            "限时免费": self.ai_module.ModelTier.LIMITED_FREE,
            "常态收费": self.ai_module.ModelTier.PAID
        }
        self.tier_btns = {}
        for i, (name, tier) in enumerate(self.tiers.items()):
            btn = SmoothButton(name, "tab_level2")
            btn.clicked.connect(lambda checked, t=tier: self._on_tier_clicked(t, checked))
            left_panel.addWidget(btn)
            self.tier_btns[tier] = btn
            
        self.tier_btns[self.ai_module.ModelTier.FREE].setChecked(True)
        left_panel.addStretch()
        
        layout.addWidget(self.left_panel_container, 1)
        
        # --- Right Panel ---
        self.right_panel_container = StyledContainer()
        right_panel_layout = QVBoxLayout(self.right_panel_container)
        right_panel_layout.setContentsMargins(10, 10, 10, 10)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { 
                background: #F5F5F5; width: 12px; margin: 0px; border-radius: 6px; 
            } 
            QScrollBar::handle:vertical { 
                background: #C0C0C0; min-height: 30px; border-radius: 6px; margin: 2px; 
            } 
            QScrollBar::handle:vertical:hover { background: #A0A0A0; } 
            QScrollBar::handle:vertical:pressed { background: #808080; } 
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; background: none; } 
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; } 
        """)
        
        self.models_container = QWidget()
        self.models_layout = QVBoxLayout(self.models_container)
        self.models_layout.setSpacing(10)
        self.models_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.models_container)
        
        right_panel_layout.addWidget(self.scroll_area)
        layout.addWidget(self.right_panel_container, 3)
        self._update_models()
        
    def set_scene(self, scene):
        self.current_scene = scene
        self._update_models()
        
    def _on_provider_clicked(self, pid, checked):
        if checked:
            # 实现不可多选：如果当前选中了某一个，把其他的取消选中
            for p, btn in self.provider_btns.items():
                if p != pid and btn.isChecked():
                    btn.setChecked(False)
        self._update_models()
        
    def _on_tier_clicked(self, tier, checked):
        if not checked:
            # 实现必选：如果取消后一个都没选中，则强制恢复选中
            has_checked = any(btn.isChecked() for btn in self.tier_btns.values())
            if not has_checked:
                self.tier_btns[tier].setChecked(True)
                return
        self._update_models()
        
    def _update_models(self):
        # Clear existing models
        while self.models_layout.count():
            item = self.models_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        selected_providers = [pid for pid, btn in self.provider_btns.items() if btn.isChecked()]
        if not selected_providers:
            selected_providers = list(self.providers.values())
            
        selected_tiers = [tier for tier, btn in self.tier_btns.items() if btn.isChecked()]
                
        models_to_show = []
        for provider in selected_providers:
            if provider in self.ai_module.MODELS and self.current_scene.value in self.ai_module.MODELS[provider]:
                for model in self.ai_module.MODELS[provider][self.current_scene.value]:
                    if model.tier in selected_tiers:
                        models_to_show.append(model)
                        
        scene_key = f"ai_model_{self.current_scene.value}"
        saved_provider = self.settings_manager.Custom.get_value(f"{scene_key}_provider", "")
        saved_model = self.settings_manager.Custom.get_value(f"{scene_key}_model", "")
        
        # 如果没有保存的设置且是 TTS 场景，默认选择 edge-tts
        if not saved_provider and not saved_model and self.current_scene == self.ai_module.AIScene.TTS:
            saved_provider = "MS"
            saved_model = "edge-tts"
            self.settings_manager.Custom.set_value(f"{scene_key}_provider", saved_provider)
            self.settings_manager.Custom.set_value(f"{scene_key}_model", saved_model)
        
        self.model_btn_group = QButtonGroup(self)
        self.model_btn_group.setExclusive(True)
        self.model_btn_group.buttonClicked.connect(self._on_model_selected)
        
        for i, model in enumerate(models_to_show):
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            
            provider_label = QLabel(model.provider)
            provider_label.setAlignment(Qt.AlignCenter)
            provider_label.setFont(self.font())
            
            btn_text = model.name
            if model.warning:
                btn_text += f" ({model.warning})"
                
            btn = SmoothButton(btn_text, "model")
            btn.setProperty("model_data", model)
            btn.setFont(self.font())
            
            if model.provider == saved_provider and model.name == saved_model:
                btn.setChecked(True)
                
            self.model_btn_group.addButton(btn, i)
            
            row_layout.addWidget(provider_label, 1)
            row_layout.addWidget(btn, 3)
            
            self.models_layout.addWidget(row_widget)
            
    def _on_model_selected(self, btn):
        model = btn.property("model_data")
        if not model: return
        scene_key = f"ai_model_{self.current_scene.value}"
        self.settings_manager.Custom.set_value(f"{scene_key}_provider", model.provider)
        self.settings_manager.Custom.set_value(f"{scene_key}_model", model.name)
        
        # 广播TTS模型配置变更
        if self.current_scene == self.ai_module.AIScene.TTS:
            from shared_memory_manager import get_shared_memory_manager
            shared_manager = get_shared_memory_manager()
            shared_manager.broadcast_settings_change('ai_model_tts', {
                'provider': model.provider,
                'model': model.name
            })
            debug_logger.output("settings_page.py", LogLevel.INFO, 
                f"已广播TTS模型变更: {model.provider} - {model.name}", 
                fold_code="SETTINGS_TTS")
            
            # 显示重启提示
            QMessageBox.information(
                self,
                "需要重启",
                "TTS模型配置已保存。\n\n为使更改生效，请重启软件。",
                QMessageBox.Ok
            )


class DefaultVoiceSettingsTab(QWidget):
    """默认音色设置选项卡"""
    
    # TTS提供商映射
    PROVIDER_MAPPING = {
        "MS": ["Microsoft", "edge-tts"],  # EdgeTTS使用MS作为provider
        "ChatGLM": ["ChatGLM"],
        "Qwen": ["Qwen"],
        "KIMI": ["KIMI"],
        "Minimax": ["Minimax"],
        "Mimo": ["Mimo"]
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings_manager = SettingsManager()
        self.voice_data = []
        self.current_provider = "MS"  # 默认EdgeTTS
        self.current_model = None  # 当前选中的模型
        self.column_count = 2
        self.provider_btns = {}
        self.model_btns = {}
        self.voice_btn_groups = {}
        self.ai_module = _get_ai_manager_module()
        self.ai_manager = self.ai_module.get_ai_manager()  # 获取 ai_manager 实例
        self.current_font = None  # 保存当前字体
        
        self._load_voice_data()
        self._init_ui()
        
    def _init_ui(self):
        """初始化UI布局"""
        # 使用QSplitter实现可拖拽调整的布局
        self.splitter = QSplitter(Qt.Horizontal, self)
        self.splitter.setHandleWidth(3)
        self.splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #D0D0D0;
            }
            QSplitter::handle:hover {
                background-color: #A0A0A0;
            }
        """)
        
        # 创建三个面板：提供商、模型、音色
        self.provider_panel = self._create_provider_panel()
        self.model_panel = self._create_model_panel()
        self.voice_panel = self._create_voice_panel()
        
        self.splitter.addWidget(self.provider_panel)
        self.splitter.addWidget(self.model_panel)
        self.splitter.addWidget(self.voice_panel)
        
        # 设置最小宽度
        self.provider_panel.setMinimumWidth(100)
        self.model_panel.setMinimumWidth(100)
        self.voice_panel.setMinimumWidth(200)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(self.splitter)
        
        # 初始化显示EdgeTTS的模型列表
        self._update_model_list()
        
        # 计算并设置初始宽度
        QTimer.singleShot(0, self._adjust_panel_widths)
        
    def _load_voice_data(self):
        """从cache/voiceList.txt加载音色数据"""
        try:
            with open("cache/voiceList.txt", "r", encoding="utf-8") as f:
                voices = []
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        voice = json.loads(line)
                        voices.append(voice)
                    except json.JSONDecodeError as e:
                        debug_logger.output(
                            "settings_page.py",
                            LogLevel.WARNING,
                            f"跳过无效的音色数据行: {e}",
                            fold_code="VOICE_SETTINGS"
                        )
                self.voice_data = voices
        except FileNotFoundError:
            debug_logger.output(
                "settings_page.py",
                LogLevel.ERROR,
                "voiceList.txt文件不存在",
                fold_code="VOICE_SETTINGS"
            )
            self.voice_data = []
        except Exception as e:
            debug_logger.output(
                "settings_page.py",
                LogLevel.ERROR,
                f"加载音色数据失败: {e}",
                fold_code="VOICE_SETTINGS"
            )
            self.voice_data = []
            
    def _adjust_panel_widths(self):
        """使用固定百分比设置面板宽度"""
        if not hasattr(self, 'splitter'):
            return
            
        total_width = self.splitter.width()
        if total_width <= 0:
            return
        
        # 使用固定百分比：提供商10%，模型15%，音色75%
        provider_width = int(total_width * 0.10)
        model_width = int(total_width * 0.15)
        voice_width = int(total_width * 0.75)
        
        # 确保最小宽度
        provider_width = max(provider_width, 100)
        model_width = max(model_width, 100)
        voice_width = max(voice_width, 200)
        
        # 设置splitter尺寸
        self.splitter.setSizes([provider_width, model_width, voice_width])
    
    def _calculate_panel_width(self, buttons):
        """计算面板所需的最小宽度以完整显示所有按钮文本"""
        if not buttons:
            return 100
        
        max_width = 100
        font = self.current_font if self.current_font else self.font()
        
        from PyQt5.QtGui import QFontMetrics
        fm = QFontMetrics(font)
        
        for btn in buttons:
            try:
                # 检查按钮是否已被删除
                if btn is None:
                    continue
                # 尝试访问按钮，如果已删除会抛出RuntimeError
                text = btn.text()
                # 计算文本宽度，加上按钮的padding和边框
                text_width = fm.width(text)
                # 按钮有padding: 8px 16px，边框1px，加上一些余量
                button_width = text_width + 32 + 2 + 20  # padding + border + margin
                max_width = max(max_width, button_width)
            except RuntimeError:
                # 按钮已被删除，跳过
                continue
        
        # 加上面板的margins (10px * 2)
        return max_width + 20
            
    def _filter_voices_by_provider(self, provider_id):
        """根据提供商ID和模型名称筛选音色列表"""
        if not self.current_model:
            return []
            
        keywords = self.PROVIDER_MAPPING.get(provider_id, [])
        if not keywords:
            return []
        
        filtered = []
        for voice in self.voice_data:
            belonging_model = voice.get("belongingModel", "")
            # 模糊匹配提供商
            provider_match = any(kw.lower() in belonging_model.lower() for kw in keywords)
            # 模糊匹配模型名称
            model_match = self.current_model.lower() in belonging_model.lower()
            
            if provider_match and model_match:
                filtered.append(voice)
        
        return filtered
        
    def _create_provider_panel(self):
        """创建左侧TTS提供商面板"""
        provider_panel_container = StyledContainer()
        provider_layout = QVBoxLayout(provider_panel_container)
        provider_layout.setContentsMargins(10, 10, 10, 10)
        provider_layout.setSpacing(10)
        
        # TTS提供商按钮
        providers = [
            ("EdgeTTS", "MS"),
            ("智谱AI", "ChatGLM"),
            ("阿里云百炼", "Qwen"),
            ("Kimi", "KIMI"),
            ("Minimax", "Minimax"),
            ("其他", "Mimo")
        ]
        
        self.provider_btn_group = QButtonGroup(self)
        self.provider_btn_group.setExclusive(True)
        
        for i, (name, pid) in enumerate(providers):
            btn = SmoothButton(name, "tab_level2")
            btn.clicked.connect(lambda checked, p=pid: self._on_provider_clicked(p, checked))
            provider_layout.addWidget(btn)
            self.provider_btns[pid] = btn
            self.provider_btn_group.addButton(btn, i)
        
        # 默认选中EdgeTTS
        self.provider_btns["MS"].setChecked(True)
        
        provider_layout.addStretch()
        return provider_panel_container
        
    def _create_model_panel(self):
        """创建中间模型选择面板"""
        model_panel_container = StyledContainer()
        model_layout = QVBoxLayout(model_panel_container)
        model_layout.setContentsMargins(10, 10, 10, 10)
        model_layout.setSpacing(10)
        
        # 模型列表容器（使用滚动区域）
        self.model_scroll_area = QScrollArea()
        self.model_scroll_area.setWidgetResizable(True)
        self.model_scroll_area.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { 
                background: #F5F5F5; width: 12px; margin: 0px; border-radius: 6px; 
            } 
            QScrollBar::handle:vertical { 
                background: #C0C0C0; min-height: 30px; border-radius: 6px; margin: 2px; 
            } 
            QScrollBar::handle:vertical:hover { background: #A0A0A0; } 
            QScrollBar::handle:vertical:pressed { background: #808080; } 
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; background: none; } 
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; } 
        """)
        
        self.model_list_container = QWidget()
        self.model_list_layout = QVBoxLayout(self.model_list_container)
        self.model_list_layout.setSpacing(10)
        self.model_list_layout.setAlignment(Qt.AlignTop)
        self.model_list_layout.setContentsMargins(0, 0, 0, 0)
        
        self.model_scroll_area.setWidget(self.model_list_container)
        model_layout.addWidget(self.model_scroll_area)
        
        return model_panel_container
        
    def _create_voice_panel(self):
        """创建右侧音色网格面板"""
        voice_panel_container = StyledContainer()
        voice_layout = QVBoxLayout(voice_panel_container)
        voice_layout.setContentsMargins(10, 10, 10, 10)
        voice_layout.setSpacing(10)
        
        # 顶部控制栏
        control_bar = QHBoxLayout()
        control_bar.addStretch()
        
        # 列数设置
        self.col_label = QLabel("列数:")
        if self.current_font:
            self.col_label.setFont(self.current_font)
        self.col_spinbox = QSpinBox()
        self.col_spinbox.setRange(1, 4)
        self.col_spinbox.setValue(2)
        self.col_spinbox.valueChanged.connect(self._on_column_count_changed)
        if self.current_font:
            self.col_spinbox.setFont(self.current_font)
        
        control_bar.addWidget(self.col_label)
        control_bar.addWidget(self.col_spinbox)
        
        voice_layout.addLayout(control_bar)
        
        # 滚动区域
        self.voice_scroll_area = QScrollArea()
        self.voice_scroll_area.setWidgetResizable(True)
        self.voice_scroll_area.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { 
                background: #F5F5F5; width: 12px; margin: 0px; border-radius: 6px; 
            } 
            QScrollBar::handle:vertical { 
                background: #C0C0C0; min-height: 30px; border-radius: 6px; margin: 2px; 
            } 
            QScrollBar::handle:vertical:hover { background: #A0A0A0; } 
            QScrollBar::handle:vertical:pressed { background: #808080; } 
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; background: none; } 
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; } 
        """)
        
        # 音色网格容器
        self.voice_grid_container = QWidget()
        self.voice_grid_layout = QGridLayout(self.voice_grid_container)
        self.voice_grid_layout.setSpacing(10)
        self.voice_grid_layout.setAlignment(Qt.AlignTop)
        
        self.voice_scroll_area.setWidget(self.voice_grid_container)
        voice_layout.addWidget(self.voice_scroll_area)
        
        return voice_panel_container
        
    def _on_provider_clicked(self, provider_id, checked):
        """处理TTS提供商按钮点击事件"""
        if checked:
            self.current_provider = provider_id
            self.current_model = None  # 切换提供商时清空模型选择
            self._update_model_list()
            
    def _on_model_clicked(self, model_name, checked):
        """处理模型按钮点击事件"""
        if checked:
            self.current_model = model_name
            self._save_default_model(self.current_provider, model_name)
            self._update_voice_grid()
            
    def _update_model_list(self):
        """更新模型列表显示"""
        # 清空现有模型按钮
        while self.model_list_layout.count():
            item = self.model_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 清空模型按钮引用字典
        self.model_btns.clear()
        
        # EdgeTTS特殊处理：直接显示EdgeTTS选项
        if self.current_provider == "MS":
            btn = SmoothButton("EdgeTTS", "tab_level2")
            if self.current_font:
                btn.setFont(self.current_font)
            btn.clicked.connect(lambda checked: self._on_model_clicked("edge-tts", checked))
            self.model_list_layout.addWidget(btn)
            self.model_btns["edge-tts"] = btn
            
            self.model_btn_group = QButtonGroup(self)
            self.model_btn_group.setExclusive(True)
            self.model_btn_group.addButton(btn, 0)
            
            # 默认选中EdgeTTS
            btn.setChecked(True)
            self.current_model = "edge-tts"
            self._update_voice_grid()
            # 重新计算面板宽度
            QTimer.singleShot(0, self._adjust_panel_widths)
            return
        
        # 获取当前提供商的TTS模型列表
        models = self.ai_manager.get_models_by_scene(self.ai_module.AIScene.TTS, provider=self.current_provider)
        
        if not models:
            # 显示空状态
            empty_label = QLabel("该提供商暂无TTS模型")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #666666;")
            if self.current_font:
                empty_label.setFont(self.current_font)
            self.model_list_layout.addWidget(empty_label)
            self._update_voice_grid()  # 清空音色列表
            return
        
        # 创建模型按钮组
        self.model_btn_group = QButtonGroup(self)
        self.model_btn_group.setExclusive(True)
        
        # 加载已保存的默认模型
        saved_model = self._load_default_model(self.current_provider)
        
        # 创建模型按钮
        for i, model in enumerate(models):
            btn = SmoothButton(model.name, "tab_level2")
            if self.current_font:
                btn.setFont(self.current_font)
            btn.clicked.connect(lambda checked, m=model.name: self._on_model_clicked(m, checked))
            self.model_list_layout.addWidget(btn)
            self.model_btns[model.name] = btn
            self.model_btn_group.addButton(btn, i)
            
            # 恢复选中状态
            if model.name == saved_model:
                btn.setChecked(True)
                self.current_model = model.name
        
        # 如果没有保存的模型，默认选中第一个
        if not saved_model and models:
            self.model_btns[models[0].name].setChecked(True)
            self.current_model = models[0].name
        
        # 更新音色列表
        self._update_voice_grid()
        
        # 重新计算面板宽度
        QTimer.singleShot(0, self._adjust_panel_widths)
            
    def _on_column_count_changed(self, count):
        """处理列数设置变更"""
        self.column_count = count
        self._update_voice_grid()
        
    def _create_voice_button(self, voice_data):
        """创建音色按钮，动态处理可选字段"""
        voice_id = voice_data.get("voiceID", "")
        voice_name = voice_data.get("voiceName", "Unknown")
        lang = voice_data.get("Lang")
        gender = voice_data.get("gender")
        
        # 动态构建显示文本
        if lang and gender:
            display_text = f"{voice_name} [{lang}|{gender}]"
        elif lang:
            display_text = f"{voice_name} [{lang}]"
        else:
            display_text = f"{voice_name} ({voice_id})"
        
        btn = SmoothButton(display_text, "model")
        if self.current_font:
            btn.setFont(self.current_font)
        btn.setProperty("voice_id", voice_id)
        return btn
        
    def _update_voice_grid(self):
        """更新音色网格显示"""
        # 清空现有网格
        while self.voice_grid_layout.count():
            item = self.voice_grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 如果没有选中模型，显示提示
        if not self.current_model:
            empty_label = QLabel("请先选择模型")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #666666;")
            if self.current_font:
                empty_label.setFont(self.current_font)
            self.voice_grid_layout.addWidget(
                empty_label, 0, 0, 1, self.column_count
            )
            return
        
        # 获取筛选后的音色列表
        voices = self._filter_voices_by_provider(self.current_provider)
        
        if not voices:
            # 显示空状态
            empty_label = QLabel("该模型暂无可用音色")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #666666;")
            if self.current_font:
                empty_label.setFont(self.current_font)
            self.voice_grid_layout.addWidget(
                empty_label, 0, 0, 1, self.column_count
            )
            return
        
        # 创建或获取按钮组（使用provider+model作为key）
        btn_group_key = f"{self.current_provider}_{self.current_model}"
        if btn_group_key not in self.voice_btn_groups:
            self.voice_btn_groups[btn_group_key] = QButtonGroup(self)
            self.voice_btn_groups[btn_group_key].setExclusive(True)
            self.voice_btn_groups[btn_group_key].buttonClicked.connect(
                self._on_voice_selected
            )
        
        btn_group = self.voice_btn_groups[btn_group_key]
        
        # 加载已保存的默认音色
        saved_voice_id = self._load_default_voice(self.current_provider, self.current_model)
        
        # 按网格排列音色按钮
        for i, voice in enumerate(voices):
            row = i // self.column_count
            col = i % self.column_count
            
            btn = self._create_voice_button(voice)
            btn_group.addButton(btn, i)
            
            # 恢复选中状态
            if voice.get("voiceID") == saved_voice_id:
                btn.setChecked(True)
            
            self.voice_grid_layout.addWidget(btn, row, col)
            
    def _on_voice_selected(self, btn):
        """处理音色按钮选择事件"""
        voice_id = btn.property("voice_id")
        if voice_id and self.current_model:
            self._save_default_voice(self.current_provider, self.current_model, voice_id)
            
    def _save_default_voice(self, provider_id, model_name, voice_id):
        """保存默认音色设置"""
        key = f"default_voice_{provider_id}_{model_name}"
        self.settings_manager.Custom.set_value(key, voice_id)
        
    def _load_default_voice(self, provider_id, model_name):
        """加载默认音色设置"""
        key = f"default_voice_{provider_id}_{model_name}"
        return self.settings_manager.Custom.get_value(key, None)
        
    def _save_default_model(self, provider_id, model_name):
        """保存默认模型设置"""
        key = f"default_model_{provider_id}"
        self.settings_manager.Custom.set_value(key, model_name)
        
    def _load_default_model(self, provider_id):
        """加载默认模型设置"""
        key = f"default_model_{provider_id}"
        return self.settings_manager.Custom.get_value(key, None)
        
    def set_font(self, font):
        """更新所有UI元素的字体"""
        self.current_font = font  # 保存当前字体
        
        def set_font_recursive(widget):
            widget.setFont(font)
            for child in widget.findChildren(QWidget):
                set_font_recursive(child)
        
        set_font_recursive(self)


class AiSettingsTab(QWidget):
    """AI设置总容器，处理Level2/Level3选项卡动画"""
    def __init__(self, parent=None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 0)
        
        # --- Top Bar (Level 2 & 3 Tabs) ---
        top_bar = QHBoxLayout()
        
        self.left_container = StyledContainer()
        left_layout = QHBoxLayout(self.left_container)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(10)
        
        self.btn_api_key = SmoothButton("API Key配置", "tab_level2")
        self.btn_ai_model = SmoothButton("AI模型设置", "tab_level2")
        self.btn_default_voice = SmoothButton("默认音色设置", "tab_level2")
        self.btn_api_key.setChecked(True)
        
        self.level2_group = QButtonGroup(self)
        self.level2_group.addButton(self.btn_api_key, 0)
        self.level2_group.addButton(self.btn_ai_model, 1)
        self.level2_group.addButton(self.btn_default_voice, 2)
        self.level2_group.buttonClicked[int].connect(self._on_level2_changed)
        
        left_layout.addStretch()
        left_layout.addWidget(self.btn_api_key)
        left_layout.addWidget(self.btn_ai_model)
        left_layout.addWidget(self.btn_default_voice)
        left_layout.addStretch()
        
        self.right_container = StyledContainer()
        self.right_container.setMaximumWidth(0)
        right_layout = QHBoxLayout(self.right_container)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(10)
        
        self.btn_chat = SmoothButton("文->文", "tab_level2")
        self.btn_vision = SmoothButton("图->文", "tab_level2")
        self.btn_tts = SmoothButton("文->音", "tab_level2")
        self.btn_chat.setChecked(True)
        
        self.level3_group = QButtonGroup(self)
        self.level3_group.addButton(self.btn_chat, 0)
        self.level3_group.addButton(self.btn_vision, 1)
        self.level3_group.addButton(self.btn_tts, 2)
        self.level3_group.buttonClicked[int].connect(self._on_level3_changed)
        
        right_layout.addWidget(self.btn_chat)
        right_layout.addWidget(self.btn_vision)
        right_layout.addWidget(self.btn_tts)
        
        self.right_opacity = QGraphicsOpacityEffect(self.right_container)
        self.right_opacity.setOpacity(0)
        self.right_container.setGraphicsEffect(self.right_opacity)
        
        top_bar.addWidget(self.left_container, 1)
        top_bar.addWidget(self.right_container, 0)
        
        layout.addLayout(top_bar)
        
        # --- Stacked Content ---
        self.stacked_widget = QStackedWidget()
        self.api_key_page = ApiKeyConfigWidget(self)
        self.ai_model_page = AiModelConfigWidget(self)
        self.default_voice_page = DefaultVoiceSettingsTab(self)
        
        self.stacked_widget.addWidget(self.api_key_page)
        self.stacked_widget.addWidget(self.ai_model_page)
        self.stacked_widget.addWidget(self.default_voice_page)
        
        layout.addWidget(self.stacked_widget)
        
        # 添加渐隐渐显动画
        self.stacked_opacity_effect = QGraphicsOpacityEffect(self.stacked_widget)
        self.stacked_widget.setGraphicsEffect(self.stacked_opacity_effect)
        self.stacked_opacity_effect.setEnabled(False)
        self.fade_animation = QPropertyAnimation(self.stacked_opacity_effect, b"opacity")
        self.fade_animation.setDuration(200) # 动画时长
        self.fade_animation.setEasingCurve(QEasingCurve.InOutQuad) # 平滑过渡
        self.fade_animation.finished.connect(self._on_fade_animation_finished)
        self.target_stacked_index = 0 # 记录目标索引
        
        # --- Animations ---
        self.right_width_anim = QPropertyAnimation(self.right_container, b"maximumWidth")
        self.right_width_anim.setEasingCurve(QEasingCurve.InOutCubic)
        self.right_width_anim.setDuration(500)
        
        self.fade_anim = QPropertyAnimation(self.right_opacity, b"opacity")
        self.fade_anim.setDuration(300)
        
        self.is_showing_right = False
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.is_showing_right:
            total_width = self.width()
            target_width = max(350, int(total_width * 0.5))
            self.right_container.setMaximumWidth(target_width)

    def _on_level2_changed(self, index):
        if self.stacked_widget.currentIndex() == index:
            return # 如果已经是当前页面，不执行动画

        self.target_stacked_index = index
        self.stacked_opacity_effect.setEnabled(True)
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.start()
        
        if index == 1: # AI模型设置
            self.is_showing_right = True
            
            # 动态计算目标宽度，预留左侧足够空间
            total_width = self.width()
            target_width = max(350, int(total_width * 0.4))
            
            self.right_width_anim.setStartValue(self.right_container.width())
            self.right_width_anim.setEndValue(target_width)
            self.right_width_anim.start()
            QTimer.singleShot(250, self._start_fade_in)
        else: # API Key配置 或 默认音色设置
            self.is_showing_right = False
            self.fade_anim.stop()
            self.fade_anim.setStartValue(self.right_opacity.opacity())
            self.fade_anim.setEndValue(0)
            self.fade_anim.start()
            
            self.right_width_anim.setStartValue(self.right_container.width())
            self.right_width_anim.setEndValue(0)
            self.right_width_anim.start()
            
    def _on_fade_animation_finished(self):
        if self.stacked_opacity_effect.opacity() == 0.0: # 渐隐结束
            self.stacked_widget.setCurrentIndex(self.target_stacked_index)
            self.fade_animation.setStartValue(0.0)
            self.fade_animation.setEndValue(1.0)
            self.fade_animation.start()
        else: # 渐显结束
            self.stacked_opacity_effect.setEnabled(False) # 动画完成
            
    def _start_fade_in(self):
        if self.stacked_widget.currentIndex() == 1 and self.is_showing_right:
            self.fade_anim.stop()
            self.fade_anim.setStartValue(self.right_opacity.opacity())
            self.fade_anim.setEndValue(1)
            self.fade_anim.start()
            
    def hide_right_panel(self):
        """由外部调用，隐藏右侧面板时执行渐隐动画"""
        if self.is_showing_right:
            self.is_showing_right = False
            self.fade_anim.stop()
            self.fade_anim.setStartValue(self.right_opacity.opacity())
            self.fade_anim.setEndValue(0)
            self.fade_anim.start()
            
            self.right_width_anim.setStartValue(self.right_container.width())
            self.right_width_anim.setEndValue(0)
            self.right_width_anim.start()
            
    def show_right_panel_if_needed(self):
        """由外部调用，恢复右侧面板时执行渐显动画"""
        if self.stacked_widget.currentIndex() == 1 and not self.is_showing_right:
            self.is_showing_right = True
            
            # 动态计算目标宽度
            total_width = self.width()
            target_width = max(350, int(total_width * 0.4))
            
            self.right_width_anim.setStartValue(self.right_container.width())
            self.right_width_anim.setEndValue(target_width)
            self.right_width_anim.start()
            QTimer.singleShot(250, self._start_fade_in)

    def _on_level3_changed(self, index):
        ai_module = _get_ai_manager_module()
        scenes = [ai_module.AIScene.CHAT, ai_module.AIScene.VISION, ai_module.AIScene.TTS]
        self.ai_model_page.set_scene(scenes[index])


# --- 兼容原有设置分组，稍作修改以适应新UI ---

class DownloadSettingsGroup(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings_manager = SettingsManager()
        self.wheel_filter = WheelEventFilter()
        self._init_styles()
        self._init_ui()
        self._load_settings()
        self._connect_signals()

    def _init_styles(self):
        self.STYLES = {
            'container': '''
                background-color: rgb(255, 255, 255);
                border-radius: 5px;
            ''',
            'input': '''
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                padding: 4px;
                selection-background-color: #4A90E2;
            ''',
            'select_button': '''
                background-color: rgb(125, 125, 255);
                border-radius: 5px;
                border: 1px solid gray;
                color:rgb(255, 255, 255);
            ''',
            'slider': '''
                QSlider::groove:horizontal {
                    background: #E0E0E0;
                    height: 16px;
                    border-radius: 6px;
                }
                QSlider::sub-page:horizontal {
                    background: #4A90E2;
                    border-radius: 3px;
                }
                QSlider::handle:horizontal {
                    background: white;
                    width: 12px;
                    height: 10px;
                    border-radius: 8px;
                    border: 2px solid #4A90E2;
                }
                QSlider::handle:horizontal:hover {
                    background: #F0F8FF;
                    border: 2px solid #357ABD;
                }
                QSlider::handle:horizontal:pressed {
                    background: #4A90E2;
                    border: 2px solid #357ABD;
                }
            ''',
            'label': '''
                border: none;
                background: transparent;
            ''',
            'combo': '''
                QComboBox {
                    background-color: white;
                    border: 1px solid #E0E0E0;
                    border-radius: 4px;
                    padding: 2px 8px;
                    min-height: 16px;
                    min-width: 80px;
                }
                QComboBox:focus {
                    border: 1px solid #4A90E2;
                }
                QComboBox::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: center right;
                    width: 24px;
                    border: none;
                    border-left: 1px solid #E0E0E0;
                    border-top-right-radius: 4px;
                    border-bottom-right-radius: 4px;
                }
                QComboBox::drop-down:hover {
                    background-color: #4A90E2;
                    border-left: 1px solid #4A90E2;
                }
                QComboBox::down-arrow {
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 6px solid #666;
                    width: 0px;
                    height: 0px;
                }
                QComboBox::drop-down:hover QComboBox::down-arrow {
                    border-top-color: white;
                }
                QComboBox QAbstractItemView {
                    background-color: white;
                    border: 1px solid #E0E0E0;
                    border-radius: 4px;
                    padding: 2px;
                    outline: none;
                    selection-background-color: #4A90E2;
                    selection-color: white;
                    alternate-background-color: #F9F9F9;
                }
                QComboBox QAbstractItemView::item {
                    height: 26px;
                    padding: 0 8px;
                    border-radius: 3px;
                    margin: 1px 2px;
                }
                QComboBox QAbstractItemView::item:hover {
                    background-color: #F0F8FF;
                    color: #333;
                }
            '''
        }
        # The container itself is styled by the scroll area, so we don't set it here.
        # self.setStyleSheet(self.STYLES['container'])

    def _init_ui(self):
        # Use a frame to hold the content and apply the container style
        container_frame = QFrame(self)
        container_frame.setStyleSheet(self.STYLES['container'])
        
        # Main layout for the DownloadSettingsGroup, which will contain the frame
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container_frame)

        layout = QFormLayout(container_frame)
        layout.setSpacing(28)
        layout.setContentsMargins(30, 20, 30, 20)

        # Download Threads
        thread_layout = QHBoxLayout()
        
        self.thread_min_label = QLabel("1")
        self.thread_min_label.setStyleSheet(self.STYLES['label'])
        
        self.thread_slider = QSlider(Qt.Horizontal)
        self.thread_slider.setRange(1, 32)
        self.thread_slider.setStyleSheet(self.STYLES['slider'])
        self.thread_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.thread_slider.setMinimumHeight(50)
        
        self.thread_max_label = QLabel("32")
        self.thread_max_label.setStyleSheet(self.STYLES['label'])
        
        self.thread_input = QLineEdit()
        self.thread_input.setFixedWidth(100)
        self.thread_input.setAlignment(Qt.AlignCenter)
        self.thread_input.setStyleSheet(self.STYLES['input'])

        thread_layout.addWidget(self.thread_min_label)
        thread_layout.addWidget(self.thread_slider)
        thread_layout.addWidget(self.thread_max_label)
        thread_layout.addWidget(self.thread_input)
        
        threads_label = QLabel("下载线程数:")
        threads_label.setStyleSheet(self.STYLES['label'])
        layout.addRow(threads_label, thread_layout)

        # Default Save Path
        self.save_path_display = QLineEdit()
        self.save_path_display.setReadOnly(True)
        self.save_path_display.setText("未实现")
        # 修改样式以预留右侧按钮空间
        path_style = self.STYLES['input'].replace('padding: 4px;', 'padding: 4px; padding-right: 75px;')
        self.save_path_display.setStyleSheet(path_style)
        
        self.save_path_button = QPushButton("选择路径", self.save_path_display)
        self.save_path_button.setCursor(Qt.PointingHandCursor)
        self.save_path_button.setEnabled(False)
        self.save_path_button.setStyleSheet('''
            QPushButton {
                background-color: #55aaff;
                border-radius: 4px;
                color: white;
                border: none;
            }
            QPushButton:hover {
                background-color: #4499ee;
            }
            QPushButton:disabled {
                background-color: #aaccff;
            }
        ''')
        
        inner_layout = QHBoxLayout(self.save_path_display)
        inner_layout.setContentsMargins(0, 0, 2, 0)
        self.save_path_button.setFixedSize(70, 26)
        inner_layout.addWidget(self.save_path_button, 0, Qt.AlignRight | Qt.AlignVCenter)
        
        save_path_label = QLabel("默认保存路径:")
        save_path_label.setStyleSheet(self.STYLES['label'])
        layout.addRow(save_path_label, self.save_path_display)

        # Github Mirror
        self.github_mirror_combo = QComboBox()
        self.github_mirror_combo.addItems([
            "直接从github服务器获取（海外首选）",
            "ghfast（中国大陆首选）",
            "ghproxy 主站（CloudFlare CDN，大陆备用）",
            "ghproxy HK（港澳台首选）",
            "ghproxy edgeone（备用）"
        ])
        self.github_mirror_combo.installEventFilter(self.wheel_filter)
        self.github_mirror_combo.setStyleSheet(self.STYLES['combo'])
        
        github_mirror_label = QLabel("Github下载加速源:")
        github_mirror_label.setStyleSheet(self.STYLES['label'])
        layout.addRow(github_mirror_label, self.github_mirror_combo)

        # 置底最大下载线程数：添加弹性空间
        spacer_widget = QWidget()
        spacer_widget.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        layout.addRow(spacer_widget)

        # Max Download Threads Input
        self.max_threads_input = QLineEdit()
        self.max_threads_input.setFixedWidth(75)
        self.max_threads_input.setStyleSheet(self.STYLES['input'])
        
        max_threads_label = QLabel("最大下载线程数:")
        max_threads_label.setStyleSheet(self.STYLES['label'])
        layout.addRow(max_threads_label, self.max_threads_input)

    def _connect_signals(self):
        self.thread_slider.valueChanged.connect(self._on_slider_changed)
        self.thread_input.editingFinished.connect(self._on_thread_input_editing_finished)
        self.max_threads_input.editingFinished.connect(self._on_max_threads_editing_finished)
        self.github_mirror_combo.currentTextChanged.connect(self._on_github_mirror_changed)

    def _on_slider_changed(self, value):
        self.thread_input.setText(str(value))
        self.settings_manager.Custom.set_value("download_threads", str(value))
        
    def _on_thread_input_editing_finished(self):
        text = self.thread_input.text()
        try:
            value = int(text)
            if 1 <= value <= self.thread_slider.maximum():
                self.thread_slider.setValue(value)
            else:
                self.thread_input.setText(str(self.thread_slider.value()))
        except (ValueError, TypeError):
            self.thread_input.setText(str(self.thread_slider.value()))

    def _on_max_threads_editing_finished(self):
        text = self.max_threads_input.text()
        try:
            value = int(text)
            if not (1 <= value <= 100):
                old_max = self.thread_slider.maximum()
                self.max_threads_input.setText(str(old_max))
                return

            self.thread_slider.setRange(1, value)
            self.thread_max_label.setText(str(value))
            self.settings_manager.Custom.set_value("max_download_threads", str(value))

        except (ValueError, TypeError):
            old_max = self.thread_slider.maximum()
            self.max_threads_input.setText(str(old_max))

    def _on_github_mirror_changed(self, text):
        selected_text = self.github_mirror_combo.currentText()
        self.settings_manager.Custom.set_value("github_mirror", selected_text)

    def _load_settings(self):
        max_download_threads_str = self.settings_manager.Custom.get_value("max_download_threads", "32")
        try:
            max_thread_val = int(max_download_threads_str)
            if not 1 <= max_thread_val <= 100:
                max_thread_val = 32
        except (ValueError, TypeError):
            max_thread_val = 32
        
        self.max_threads_input.setText(str(max_thread_val))
        self.thread_slider.setRange(1, max_thread_val)
        self.thread_max_label.setText(str(max_thread_val))

        download_threads_str = self.settings_manager.Custom.get_value("download_threads", "16")
        try:
            thread_val = int(download_threads_str)
            if not 1 <= thread_val <= max_thread_val:
                thread_val = min(16, max_thread_val)
        except (ValueError, TypeError):
            thread_val = min(16, max_thread_val)
            
        self.thread_slider.setValue(thread_val)
        self.thread_input.setText(str(thread_val))


class OnlineImportSettingsGroup(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings_manager = SettingsManager()
        self.wheel_filter = WheelEventFilter()
        self._init_styles()
        self._init_ui()
        self._load_settings()

    def _init_styles(self):
        self.STYLES = {
            'container': '''
                background-color: rgb(255, 255, 255);
                border-radius: 5px;
                border: 1px solid #D0D0D0;
            ''',
            'label': '''
                border: none;
                background: transparent;
            ''',
            'combo': '''
                QComboBox {
                    background-color: white;
                    border: 1px solid #E0E0E0;
                    border-radius: 4px;
                    padding: 4px 8px;
                    min-height: 20px;
                    min-width: 80px;
                }
                QComboBox:focus {
                    border: 1px solid #4A90E2;
                }
                QComboBox::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: center right;
                    width: 24px;
                    border: none;
                    border-left: 1px solid #E0E0E0;
                    border-top-right-radius: 4px;
                    border-bottom-right-radius: 4px;
                }
                QComboBox::drop-down:hover {
                    background-color: #4A90E2;
                    border-left: 1px solid #4A90E2;
                }
                QComboBox::down-arrow {
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 6px solid #666;
                    width: 0px;
                    height: 0px;
                }
                QComboBox::drop-down:hover QComboBox::down-arrow {
                    border-top-color: white;
                }
                QComboBox QAbstractItemView {
                    background-color: white;
                    border: 1px solid #E0E0E0;
                    border-radius: 4px;
                    padding: 2px;
                    outline: none;
                    selection-background-color: #4A90E2;
                    selection-color: white;
                    alternate-background-color: #F9F9F9;
                }
                QComboBox QAbstractItemView::item {
                    height: 26px;
                    padding: 0 8px;
                    border-radius: 3px;
                    margin: 1px 2px;
                }
                QComboBox QAbstractItemView::item:hover {
                    background-color: #F0F8FF;
                    color: #333;
                }
            '''
        }

    def _init_ui(self):
        container_frame = QFrame(self)
        container_frame.setStyleSheet(self.STYLES['container'])
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container_frame)

        layout = QFormLayout(container_frame)
        layout.setSpacing(28)
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.import_mode_combo = QComboBox()
        self.import_mode_combo.addItem("GitHub导入模式", "github")
        self.import_mode_combo.addItem("智慧教育平台导入模式", "sei")
        self.import_mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.import_mode_combo.setStyleSheet(self.STYLES['combo'])
        self.import_mode_combo.installEventFilter(self.wheel_filter)

        import_mode_label = QLabel("在线导入模式:")
        import_mode_label.setStyleSheet(self.STYLES['label'])
        layout.addRow(import_mode_label, self.import_mode_combo)

    def _on_mode_changed(self, index):
        mode_data = self.import_mode_combo.itemData(index)
        self.settings_manager.set_online_import_mode(mode_data == "sei")
        
    def _load_settings(self):
        is_sei_mode = self.settings_manager.get_online_import_mode()
        idx = self.import_mode_combo.findData("sei" if is_sei_mode else "github")
        if idx >= 0: self.import_mode_combo.setCurrentIndex(idx)


class DraggableTabButton(QPushButton):
    def __init__(self, text, tab_name, parent=None):
        super().__init__(text, parent)
        self.tab_name = tab_name
        self.setMinimumSize(80, 35)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAcceptDrops(True)
        self.setStyleSheet("""
            QPushButton {
                background-color: white;
                border: 1px solid #A0A0A0;
                border-radius: 4px;
                color: #333;
            }
        """)
        self.drag_start_pos = None

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
        mime_data.setText(self.tab_name)
        drag.setMimeData(mime_data)
        
        pixmap = QPixmap(self.size())
        self.render(pixmap)
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.pos())
        
        self.hide()
        drop_action = drag.exec_(Qt.MoveAction)
        self.show()

class VerticalDragContainer(QWidget):
    order_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.v_layout = QVBoxLayout(self)
        self.v_layout.setSpacing(10)
        self.v_layout.setContentsMargins(0, 0, 0, 0)
        self.v_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.setAcceptDrops(True)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.drag_buttons = []
        
    def add_button(self, btn):
        self.drag_buttons.append(btn)
        self.v_layout.addWidget(btn)
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasText():
            tab_name = event.mimeData().text()
            source_btn = None
            for btn in self.drag_buttons:
                if btn.tab_name == tab_name:
                    source_btn = btn
                    break
            
            if source_btn:
                self.drag_buttons.remove(source_btn)
                
                drop_y = event.pos().y()
                target_index = 0
                current_y = 0
                
                for i, btn in enumerate(self.drag_buttons):
                    if drop_y > current_y + btn.height() / 2:
                        target_index = i + 1
                    current_y += btn.height() + self.v_layout.spacing()
                    
                self.drag_buttons.insert(target_index, source_btn)
                
                while self.v_layout.count():
                    item = self.v_layout.takeAt(0)
                    if item.widget():
                        item.widget().setParent(None)
                
                for btn in self.drag_buttons:
                    self.v_layout.addWidget(btn)
                    
                source_btn.show()
                self.order_changed.emit()
            event.acceptProposedAction()

class VisibilityButton(QPushButton):
    visibility_toggled = pyqtSignal(str, bool)
    
    def __init__(self, text, tab_name, is_visible, parent=None):
        super().__init__(text, parent)
        self.tab_name = tab_name
        self.is_visible = is_visible
        self.setMinimumSize(120, 60)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.update_style()
        self.clicked.connect(self.on_click)
        
    def on_click(self):
        if self.tab_name == 'settings':
            return
            
        self.is_visible = not self.is_visible
        self.update_style()
        self.visibility_toggled.emit(self.tab_name, self.is_visible)
        
    def update_style(self):
        if self.is_visible:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #55aaff;
                    color: white;
                    border: 1px solid #4499ee;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #66bbff;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #f5f5f5;
                    color: #999;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #e8e8e8;
                }
            """)

class TabSettingsGroup(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings_manager = SettingsManager()
        self.available_tabs = {
            'welcome': '欢迎',
            'dictation': '听写',
            'settings': '设置',
            'personalization': '个性化',
            'misc': '杂项',
            'streaming': '流媒体'
        }
        self.tab_order = []
        self.tab_visibility = []
        self.wheel_filter = WheelEventFilter()
        
        self.STYLES = {
            'container': '''
                background-color: rgb(255, 255, 255);
                border-radius: 5px;
            ''',
            'label': '''
                border: none;
                background: transparent;
            ''',
            'combo': '''
                QComboBox {
                    background-color: white;
                    border: 1px solid #E0E0E0;
                    border-radius: 4px;
                    padding: 2px 8px;
                    min-height: 28px;
                }
                QComboBox:focus {
                    border: 1px solid #4A90E2;
                }
                QComboBox::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: center right;
                    width: 24px;
                    border: none;
                    border-left: 1px solid #E0E0E0;
                    border-top-right-radius: 4px;
                    border-bottom-right-radius: 4px;
                }
                QComboBox::drop-down:hover {
                    background-color: #4A90E2;
                    border-left: 1px solid #4A90E2;
                }
                QComboBox::down-arrow {
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 6px solid #666;
                    width: 0px;
                    height: 0px;
                }
                QComboBox::drop-down:hover QComboBox::down-arrow {
                    border-top-color: white;
                }
                QComboBox QAbstractItemView {
                    background-color: white;
                    border: 1px solid #E0E0E0;
                    border-radius: 4px;
                    padding: 2px;
                    outline: none;
                    selection-background-color: #4A90E2;
                    selection-color: white;
                }
            '''
        }
        
        self._init_ui()
        self._load_settings()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(20)

        # --- Left Panel ---
        left_container = QFrame()
        left_container.setStyleSheet(self.STYLES['container'])
        left_container.setMinimumWidth(150)
        left_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(20, 30, 20, 30)
        left_layout.setSpacing(10)
        left_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        sort_title = QLabel("选项卡排序:")
        sort_title.setStyleSheet("font-weight: bold; border: none; background: transparent; color: black;")
        sort_title.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(sort_title)

        sort_subtitle = QLabel("上下拖动以排序")
        sort_subtitle.setStyleSheet("color: #666; border: none; background: transparent;")
        sort_subtitle.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(sort_subtitle)
        
        left_layout.addSpacing(15)

        self.drag_container_frame = QFrame()
        self.drag_container_frame.setStyleSheet("""
            QFrame {
                background-color: #F5F5F5;
                border-radius: 6px;
            }
        """)
        self.drag_container_frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        drag_frame_layout = QVBoxLayout(self.drag_container_frame)
        drag_frame_layout.setContentsMargins(10, 15, 10, 15)
        
        self.drag_container = VerticalDragContainer()
        self.drag_container.order_changed.connect(self._on_order_changed)
        self.drag_container.setStyleSheet("border: none;")
        drag_frame_layout.addWidget(self.drag_container)
        
        left_layout.addWidget(self.drag_container_frame)
        left_layout.addStretch()

        # --- Right Panel ---
        right_container = QFrame()
        right_container.setStyleSheet(self.STYLES['container'])
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(40, 50, 40, 40)
        right_layout.setSpacing(50)
        right_layout.setAlignment(Qt.AlignTop)

        # Row 1: Initial Tab
        initial_tab_layout = QHBoxLayout()
        initial_tab_label = QLabel("起始选项卡:")
        initial_tab_label.setStyleSheet("border: none; background: transparent; color: black;")
        initial_tab_label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        
        self.initial_tab_combo = QComboBox()
        self.initial_tab_combo.setStyleSheet(self.STYLES['combo'])
        self.initial_tab_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.initial_tab_combo.setMinimumWidth(200)
        self.initial_tab_combo.currentIndexChanged.connect(self._save_settings)
        self.initial_tab_combo.installEventFilter(self.wheel_filter)
        
        initial_tab_layout.addWidget(initial_tab_label)
        initial_tab_layout.addWidget(self.initial_tab_combo)
        initial_tab_layout.addStretch()
        
        right_layout.addLayout(initial_tab_layout)

        # Row 2: Visibility
        visibility_layout = QHBoxLayout()
        visibility_layout.setAlignment(Qt.AlignTop)
        
        vis_label_layout = QVBoxLayout()
        vis_label_layout.setAlignment(Qt.AlignTop)
        vis_label_layout.setSpacing(5)
        vis_title = QLabel("修改选项卡可见性:")
        vis_title.setStyleSheet("border: none; background: transparent; color: black;")
        vis_subtitle = QLabel("单击以修改")
        vis_subtitle.setStyleSheet("color: #666; border: none; background: transparent;")
        
        vis_label_container = QWidget()
        vis_label_container.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        v_lbl_layout = QVBoxLayout(vis_label_container)
        v_lbl_layout.setContentsMargins(0, 0, 0, 0)
        v_lbl_layout.addWidget(vis_title)
        v_lbl_layout.addWidget(vis_subtitle)
        v_lbl_layout.addStretch()
        
        self.visibility_grid = QGridLayout()
        self.visibility_grid.setVerticalSpacing(5)
        self.visibility_grid.setHorizontalSpacing(5)
        
        visibility_layout.addWidget(vis_label_container)
        visibility_layout.addLayout(self.visibility_grid)
        visibility_layout.addStretch()

        right_layout.addLayout(visibility_layout)
        right_layout.addStretch()

        main_layout.addWidget(left_container)
        main_layout.addWidget(right_container, 1)

    def _load_settings(self):
        order_str = self.settings_manager.get_Custom_value("tab_order", "welcome,dictation,settings,personalization,misc,streaming")
        self.tab_order = [t.strip() for t in order_str.split(',') if t.strip() and t.strip() in self.available_tabs]
        for name in self.available_tabs:
            if name not in self.tab_order:
                self.tab_order.append(name)
        
        visibility_str = self.settings_manager.get_Custom_value("tab_visibility", "welcome,dictation,settings,personalization,misc,streaming")
        self.tab_visibility = [t.strip() for t in visibility_str.split(',') if t.strip() and t.strip() in self.available_tabs]
        
        if 'settings' not in self.tab_visibility:
            self.tab_visibility.append('settings')
            self._save_settings()

        self._refresh_ui()

    def _refresh_ui(self):
        while self.drag_container.v_layout.count():
            item = self.drag_container.v_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self.drag_container.drag_buttons.clear()

        for name in self.tab_order:
            display_name = self.available_tabs.get(name, name)
            btn = DraggableTabButton(display_name, name)
            self.drag_container.add_button(btn)

        while self.visibility_grid.count():
            item = self.visibility_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        fixed_order = ["welcome", "dictation", "settings", "personalization", "misc", "streaming"]
        row, col = 0, 0
        for name in fixed_order:
            if name not in self.available_tabs: continue
            display_name = self.available_tabs.get(name, name)
            is_vis = (name in self.tab_visibility)
            btn = VisibilityButton(display_name, name, is_vis)
            btn.visibility_toggled.connect(self._on_visibility_changed)
            self.visibility_grid.addWidget(btn, row, col)
            col += 1
            if col > 2:
                col = 0
                row += 1

        self._update_initial_tab_combo()

    def _update_initial_tab_combo(self):
        current_selection = self.settings_manager.get_Custom_value("initial_tab", "welcome")
        self.initial_tab_combo.blockSignals(True)
        self.initial_tab_combo.clear()
        
        for name in self.tab_order:
            if name in self.tab_visibility:
                self.initial_tab_combo.addItem(self.available_tabs[name], name)
        
        idx = self.initial_tab_combo.findData(current_selection)
        if idx >= 0:
            self.initial_tab_combo.setCurrentIndex(idx)
        else:
            if self.initial_tab_combo.count() > 0:
                self.initial_tab_combo.setCurrentIndex(0)
                self.initial_tab_combo.blockSignals(False)
                self._save_settings()
                self.initial_tab_combo.blockSignals(True)
            
        self.initial_tab_combo.blockSignals(False)

    def _on_order_changed(self):
        new_order = [btn.tab_name for btn in self.drag_container.drag_buttons]
        self.tab_order = new_order
        self._update_initial_tab_combo()
        self._save_settings()

    def _on_visibility_changed(self, name, is_visible):
        if is_visible:
            if name not in self.tab_visibility:
                self.tab_visibility.append(name)
        else:
            if name in self.tab_visibility:
                self.tab_visibility.remove(name)
        self._update_initial_tab_combo()
        self._save_settings()

    def _save_settings(self):
        self.settings_manager.set_Custom_value("tab_order", ",".join(self.tab_order))
        self.settings_manager.set_Custom_value("tab_visibility", ",".join(self.tab_visibility))
        if self.initial_tab_combo.currentData():
            self.settings_manager.set_Custom_value("initial_tab", self.initial_tab_combo.currentData())


class SettingsPage(QWidget):
    """主设置页面"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.settings_manager = SettingsManager()
        self._init_ui()
        self._update_fonts()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # --- Top Navigation ---
        self.top_nav_container = StyledContainer()
        top_nav_layout = QHBoxLayout(self.top_nav_container)
        top_nav_layout.setContentsMargins(20, 20, 20, 20)
        top_nav_layout.setSpacing(20)
        
        self.btn_ai = SmoothButton("AI设置", "tab_level1")
        self.btn_download = SmoothButton("下载设置", "tab_level1")
        self.btn_import = SmoothButton("在线导入设置", "tab_level1")
        self.btn_tab = SmoothButton("选项卡设置", "tab_level1")
        
        self.btn_ai.setChecked(True)
        
        self.level1_group = QButtonGroup(self)
        self.level1_group.addButton(self.btn_ai, 0)
        self.level1_group.addButton(self.btn_download, 1)
        self.level1_group.addButton(self.btn_import, 2)
        self.level1_group.addButton(self.btn_tab, 3)
        self.level1_group.buttonClicked[int].connect(self._on_level1_changed)
        
        top_nav_layout.addStretch()
        top_nav_layout.addWidget(self.btn_ai)
        top_nav_layout.addWidget(self.btn_download)
        top_nav_layout.addWidget(self.btn_import)
        top_nav_layout.addWidget(self.btn_tab)
        top_nav_layout.addStretch()
        
        main_layout.addWidget(self.top_nav_container)
        
        # --- Stacked Content ---
        self.stacked_widget = QStackedWidget()
        
        self.ai_settings_tab = AiSettingsTab(self)
        
        self.download_scroll = QScrollArea()
        self.download_scroll.setWidgetResizable(True)
        self.download_scroll.setFrameShape(QFrame.NoFrame)
        self.download_group = DownloadSettingsGroup(self)
        self.download_scroll.setWidget(self.download_group)
        
        self.import_scroll = QScrollArea()
        self.import_scroll.setWidgetResizable(True)
        self.import_scroll.setFrameShape(QFrame.NoFrame)
        self.online_import_group = OnlineImportSettingsGroup(self)
        self.import_scroll.setWidget(self.online_import_group)
        
        self.tab_scroll = QScrollArea()
        self.tab_scroll.setWidgetResizable(True)
        self.tab_scroll.setFrameShape(QFrame.NoFrame)
        self.tab_settings_group = TabSettingsGroup(self)
        self.tab_scroll.setWidget(self.tab_settings_group)
        
        self.stacked_widget.addWidget(self.ai_settings_tab)
        self.stacked_widget.addWidget(self.download_scroll)
        self.stacked_widget.addWidget(self.import_scroll)
        self.stacked_widget.addWidget(self.tab_scroll)
        
        main_layout.addWidget(self.stacked_widget)
        
        # 添加渐隐渐显动画
        self.stacked_opacity_effect = QGraphicsOpacityEffect(self.stacked_widget)
        self.stacked_widget.setGraphicsEffect(self.stacked_opacity_effect)
        self.stacked_opacity_effect.setEnabled(False)
        self.fade_animation = QPropertyAnimation(self.stacked_opacity_effect, b"opacity")
        self.fade_animation.setDuration(200) # 动画时长
        self.fade_animation.setEasingCurve(QEasingCurve.InOutQuad) # 平滑过渡
        self.fade_animation.finished.connect(self._on_fade_animation_finished)
        self.target_stacked_index = 0 # 记录目标索引
        
    def resizeEvent(self, event):
        self._update_fonts()
        super().resizeEvent(event)
        
    def _on_level1_changed(self, index):
        if self.stacked_widget.currentIndex() == index:
            return
        self.target_stacked_index = index
        self.stacked_opacity_effect.setEnabled(True)
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.start()

        # 一级选项卡切换时，使用带有动画的方法，使其与整体渐变效果同步进行
        if index != 0:
            self.ai_settings_tab.hide_right_panel()
        else:
            self.ai_settings_tab.show_right_panel_if_needed()

    def _on_fade_animation_finished(self):
        if self.stacked_opacity_effect.opacity() == 0.0:
            self.stacked_widget.setCurrentIndex(self.target_stacked_index)
            self.fade_animation.setStartValue(0.0)
            self.fade_animation.setEndValue(1.0)
            self.fade_animation.start()
        else:
            self.stacked_opacity_effect.setEnabled(False)

    def update_fonts(self, font):
        self._update_fonts()
        
    def _update_fonts(self):
        if not self.parent_window: return
        
        current_width = self.parent_window.width()
        current_height = self.parent_window.height()
        ratio = (current_width / 1080 + current_height / 720) / 2
        
        base_font_size = 22 + (42 - 22) * (ratio - 1)
        base_font_size = max(22, min(42, int(base_font_size)))
        
        global_font_name = self.settings_manager.Custom.get_value("global_font", "微软雅黑")
        base_font = QFont(global_font_name, int(base_font_size * 0.5))
        
        # 递归应用字体，不使用样式表中的font属性
        def set_font_recursive(widget):
            widget.setFont(base_font)
            for child in widget.findChildren(QWidget):
                child.setFont(base_font)
                
        set_font_recursive(self)
        
        # 更新DefaultVoiceSettingsTab的字体
        if hasattr(self, 'ai_settings_tab') and hasattr(self.ai_settings_tab, 'default_voice_page'):
            self.ai_settings_tab.default_voice_page.set_font(base_font)

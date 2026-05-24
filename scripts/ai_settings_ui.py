# coding=utf-8
"""AI 设置页：添加模型 / 选择模型。"""
from typing import Any, Dict, List, Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit,
    QPushButton, QFormLayout, QScrollArea, QFrame, QSizePolicy,
    QStackedWidget, QButtonGroup, QMessageBox, QInputDialog,
    QCompleter, QGridLayout, QDialog, QDialogButtonBox, QGraphicsOpacityEffect,
    QApplication,
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve, QEvent
from PyQt5.QtGui import QFont

from ai_settings_store import (
    CustomAIModelStore, SCENES, SCENE_LABELS,
    EDGE_TTS_MODEL, EDGE_TTS_SENTINEL, EDGE_TTS_VOICE_MODEL,
    get_default_edgetts_voice_id, set_default_edgetts_voice_id,
)
from misc_func import SettingsManager
from settings_page import SmoothButton, StyledContainer


# 与 custom_page.CustomPage 一致的全局字号缩放参数
_MIN_FONT_PX = 22
_MAX_FONT_PX = 42
_DEFAULT_WIDTH = 1080
_DEFAULT_HEIGHT = 720


def _calc_base_font_px(width: int, height: int) -> int:
    """与 custom_page._update_fonts 相同的 base_font_size 算法（结果为 px 档位）。"""
    width_ratio = width / _DEFAULT_WIDTH
    height_ratio = height / _DEFAULT_HEIGHT
    ratio = (width_ratio + height_ratio) / 2
    base = _MIN_FONT_PX + (_MAX_FONT_PX - _MIN_FONT_PX) * (ratio - 1)
    return int(max(_MIN_FONT_PX, min(_MAX_FONT_PX, base)))


def compute_ai_ui_metrics(width: int, height: int, font_name: str = "微软雅黑") -> Dict[str, Any]:
    """
    字号与 custom_page 同源：1080×720 时为 22px，随窗口放大至 42px。
    界面内各级文字均不低于 22px。
    """
    base = _calc_base_font_px(width, height)
    pad = max(8, int(base * 0.36))
    return {
        "font_name": font_name,
        "base_font_px": base,
        "input_font_px": base,
        "input_height": max(40, int(base * 1.65)),
        "chip_font_px": base,
        "section_font_px": base,
        "hint_font_px": base,
        "status_font_px": base,
        "card_title_px": base,
        "card_sub_px": base,
        "card_tag_px": base,
        "group_info_px": base,
        "input_pad_v": pad,
        "input_pad_h": pad,
        "chip_radius": max(10, int(base * 0.45)),
        "add_btn_size": max(_MIN_FONT_PX, int(base * 1.45)),
    }


def _metrics_font(m: Dict[str, Any], px_key: str = "input_font_px") -> QFont:
    size = max(_MIN_FONT_PX, int(m.get(px_key, m.get("base_font_px", _MIN_FONT_PX))))
    return QFont(m["font_name"], size)


def style_input(m: Dict[str, Any]) -> str:
    pv, ph = m["input_pad_v"], m["input_pad_h"]
    fs = m["input_font_px"]
    return (
        f"QLineEdit, QComboBox {{ padding: {pv}px {ph}px; border: 1px solid #D0D0D0; "
        f"border-radius: 4px; font-size: {fs}px; background: #fff; }}"
        "QLineEdit:focus, QComboBox:focus { border-color: #5566FF; }"
    )


def style_chip_button(m: Dict[str, Any]) -> str:
    fs = m["chip_font_px"]
    r = m["chip_radius"]
    pv, ph = m["input_pad_v"], m["input_pad_h"]
    return (
        f"QPushButton {{ background: #E8EEFF; color: #3344AA; border-radius: {r}px; "
        f"padding: {pv}px {ph}px; font-size: {fs}px; border: none; }}"
    )


def style_section(m: Dict[str, Any]) -> str:
    return (
        f"font-weight: bold; font-size: {m['section_font_px']}px; "
        "color: #333; padding: 4px 0; border: none; background: transparent;"
    )


def style_form_label(m: Dict[str, Any]) -> str:
    return (
        f"font-size: {m['input_font_px']}px; color: #333; "
        "border: none; background: transparent;"
    )


def style_hint(m: Dict[str, Any]) -> str:
    return f"color: #888; font-size: {m['hint_font_px']}px; border: none; background: transparent;"


def style_status(m: Dict[str, Any]) -> str:
    return f"color: #00AA55; font-size: {m['status_font_px']}px; border: none; background: transparent;"


def apply_input_metrics(widget: QWidget, m: Dict[str, Any]):
    """统一设置输入/下拉框高度与字号。"""
    if widget is None:
        return
    h = m["input_height"]
    ss = style_input(m)
    f = _metrics_font(m)
    if isinstance(widget, (QLineEdit, QComboBox)):
        widget.setStyleSheet(ss)
        widget.setMinimumHeight(h)
        widget.setFont(f)
    elif isinstance(widget, list):
        for w in widget:
            apply_input_metrics(w, m)


DEFAULT_METRICS = compute_ai_ui_metrics(1080, 720)

KNOWN_PROVIDER_URLS = {
    "OpenAI": "https://api.openai.com/v1",
    "Anthropic": "https://api.anthropic.com",
    "DeepSeek": "https://api.deepseek.com",
    "智谱AI": "https://open.bigmodel.cn/api/paas/v4",
    "阿里云百炼": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "Kimi": "https://api.moonshot.cn/v1",
    "Minimax": "https://api.minimax.chat/v1",
    "SiliconFlow": "https://api.siliconflow.cn/v1",
    "Ollama": "http://localhost:11434/v1",
    "vLLM": "http://localhost:8000/v1",
}


class TabCompleteLineEdit(QLineEdit):
    """支持 Tab 从候选列表补全并触发回调。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._candidates: List[str] = []
        self._on_tab_complete = None

    def set_candidates(self, items: List[str]):
        self._candidates = items
        comp = QCompleter(items)
        comp.setCaseSensitivity(Qt.CaseInsensitive)
        comp.setFilterMode(Qt.MatchContains)
        comp.setCompletionMode(QCompleter.PopupCompletion)
        self.setCompleter(comp)

    def set_tab_handler(self, handler):
        self._on_tab_complete = handler

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Tab and self._on_tab_complete:
            text = self.text().strip()
            match = self._find_match(text)
            if match and self._on_tab_complete(match):
                event.accept()
                return
        super().keyPressEvent(event)

    def _find_match(self, text: str) -> Optional[str]:
        if not text:
            return self._candidates[0] if self._candidates else None
        lower = text.lower()
        for c in self._candidates:
            if c.lower() == lower:
                return c
        for c in self._candidates:
            if lower in c.lower() or c.lower().startswith(lower):
                return c
        return None


class TagChipBar(QWidget):
    tags_changed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._metrics = dict(DEFAULT_METRICS)
        self._tags: List[str] = []
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)
        self._input = QLineEdit()
        self._input.setPlaceholderText("输入标签后回车或点击添加")
        self._input.returnPressed.connect(self._add_from_input)
        self._add_btn = QPushButton("+")
        self._add_btn.clicked.connect(self._add_from_input)
        self._layout.addWidget(self._input, 1)
        self._layout.addWidget(self._add_btn)
        self.apply_ui_metrics(self._metrics)

    def apply_ui_metrics(self, metrics: Dict[str, Any]):
        self._metrics = dict(metrics)
        apply_input_metrics(self._input, self._metrics)
        sz = self._metrics["add_btn_size"]
        self._add_btn.setFixedSize(sz, sz)
        fs = self._metrics["chip_font_px"]
        r = sz // 2
        self._add_btn.setStyleSheet(
            f"QPushButton {{ background: #5566FF; color: white; border-radius: {r}px; "
            f"font-size: {fs}px; font-weight: bold; border: none; }}"
            "QPushButton:hover { background: #4455EE; }"
        )
        self._add_btn.setFont(_metrics_font(self._metrics, "chip_font_px"))
        self._rebuild_chips()

    def get_tags(self) -> List[str]:
        return list(self._tags)

    def set_tags(self, tags: List[str]):
        self._tags = [t.strip() for t in tags if t and str(t).strip()]
        self._rebuild_chips()

    def clear_tags(self):
        self.set_tags([])

    def _add_from_input(self):
        text = self._input.text().strip()
        if not text:
            return
        if text not in self._tags:
            self._tags.append(text)
            self._rebuild_chips()
            self.tags_changed.emit(self.get_tags())
        self._input.clear()

    def _remove(self, tag: str):
        if tag in self._tags:
            self._tags.remove(tag)
            self._rebuild_chips()
            self.tags_changed.emit(self.get_tags())

    def _rebuild_chips(self):
        while self._layout.count() > 2:
            item = self._layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for tag in self._tags:
            chip = QPushButton(tag)
            chip.setStyleSheet(style_chip_button(self._metrics))
            chip.setFont(_metrics_font(self._metrics, "chip_font_px"))
            chip.setCursor(Qt.PointingHandCursor)
            chip.setToolTip("点击移除")
            chip.clicked.connect(lambda _c, t=tag: self._remove(t))
            self._layout.insertWidget(self._layout.count() - 2, chip)


class EdgeTtsCard(QFrame):
    """文->音内置 EdgeTTS，默认选中且暂不可切换。"""

    def __init__(self, metrics: Dict[str, Any], parent=None):
        super().__init__(parent)
        self._metrics = dict(metrics)
        self.setCursor(Qt.ArrowCursor)
        self.setToolTip("系统默认语音合成，暂不可切换")
        self._title = QLabel("EdgeTTS")
        self._prov = QLabel("Microsoft")
        self._badge = QLabel("系统默认 · 暂不可切换")
        self._build_chrome()
        lay = QVBoxLayout(self)
        pad = max(8, self._metrics["input_pad_h"])
        lay.setContentsMargins(pad + 4, pad + 2, pad + 4, pad + 2)
        lay.addWidget(self._title)
        lay.addWidget(self._prov)
        lay.addWidget(self._badge)

    def _build_chrome(self):
        m = self._metrics
        self.setStyleSheet("""
            EdgeTtsCard {
                background: #F0FFF4;
                border: 2px solid #00CC66;
                border-radius: 8px;
            }
        """)
        self._title.setStyleSheet(
            f"font-weight: bold; font-size: {m['card_title_px']}px; "
            "border: none; background: transparent;"
        )
        self._title.setFont(_metrics_font(m, "card_title_px"))
        self._prov.setStyleSheet(
            f"color: #666; font-size: {m['card_sub_px']}px; border: none; background: transparent;"
        )
        self._prov.setFont(_metrics_font(m, "card_sub_px"))
        tpx = m["card_tag_px"]
        self._badge.setStyleSheet(
            f"color: #448855; font-size: {tpx}px; border: none; background: transparent;"
        )
        self._badge.setFont(_metrics_font(m, "card_tag_px"))

    def apply_ui_metrics(self, metrics: Dict[str, Any]):
        self._metrics = dict(metrics)
        self._build_chrome()


class ModelCard(QFrame):
    clicked = pyqtSignal(str)
    long_pressed = pyqtSignal(str)

    LONG_MS = 550

    def __init__(
        self,
        model: Dict,
        active: bool,
        metrics: Dict[str, Any],
        parent=None,
        *,
        selectable: bool = True,
    ):
        super().__init__(parent)
        self._metrics = dict(metrics)
        self._selectable = selectable
        self.model_id = model.get("id", "")
        self.setCursor(Qt.PointingHandCursor if selectable else Qt.ArrowCursor)
        self._title = QLabel(model.get("model", "未命名"))
        self._prov = QLabel(model.get("provider", "") or "—")
        self._tag_labels: List[QLabel] = []
        self._build_chrome(active)
        lay = QVBoxLayout(self)
        pad = max(8, self._metrics["input_pad_h"])
        lay.setContentsMargins(pad + 4, pad + 2, pad + 4, pad + 2)
        lay.addWidget(self._title)
        lay.addWidget(self._prov)
        tags = model.get("tags") or []
        if tags:
            tag_row = QHBoxLayout()
            tag_row.setSpacing(4)
            tpx = self._metrics["card_tag_px"]
            tpv = max(1, self._metrics["input_pad_v"] // 2)
            for t in tags[:4]:
                lb = QLabel(t)
                lb.setStyleSheet(
                    f"background: #E8EEFF; color: #4455AA; border-radius: 6px; "
                    f"padding: {tpv}px {tpv + 4}px; font-size: {tpx}px; "
                    "border: none; background-color: #E8EEFF;"
                )
                lb.setFont(_metrics_font(self._metrics, "card_tag_px"))
                self._tag_labels.append(lb)
                tag_row.addWidget(lb)
            if len(tags) > 4:
                extra = QLabel(f"+{len(tags)-4}")
                extra.setStyleSheet(
                    f"color: #666; font-size: {tpx}px; border: none; background: transparent;"
                )
                tag_row.addWidget(extra)
            tag_row.addStretch()
            wrap = QWidget()
            wrap.setLayout(tag_row)
            lay.addWidget(wrap)
        self._press_timer = QTimer(self)
        self._press_timer.setSingleShot(True)
        self._press_timer.timeout.connect(self._emit_long)
        self._long_fired = False

    def _build_chrome(self, active: bool):
        if not self._selectable:
            border, bg = "#E8E8E8", "#F8F8F8"
            hover = ""
        else:
            border = "#00CC66" if active else "#E0E0E0"
            bg = "#F0FFF4" if active else "#FFFFFF"
            hover = "ModelCard:hover { border-color: #8899FF; }"
        self.setStyleSheet(f"""
            ModelCard {{
                background: {bg};
                border: 2px solid {border};
                border-radius: 8px;
            }}
            {hover}
        """)
        m = self._metrics
        self._title.setStyleSheet(
            f"font-weight: bold; font-size: {m['card_title_px']}px; "
            "border: none; background: transparent;"
        )
        self._title.setFont(_metrics_font(m, "card_title_px"))
        self._prov.setStyleSheet(
            f"color: #666; font-size: {m['card_sub_px']}px; border: none; background: transparent;"
        )
        self._prov.setFont(_metrics_font(m, "card_sub_px"))

    def apply_ui_metrics(self, metrics: Dict[str, Any], active: bool):
        self._metrics = dict(metrics)
        self._build_chrome(active)

    def mousePressEvent(self, event):
        if not self._selectable:
            return
        if event.button() == Qt.LeftButton:
            self._long_fired = False
            self._press_timer.start(self.LONG_MS)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if not self._selectable:
            return
        self._press_timer.stop()
        if event.button() == Qt.LeftButton and not self._long_fired:
            self.clicked.emit(self.model_id)
        super().mouseReleaseEvent(event)

    def _emit_long(self):
        self._long_fired = True
        self.long_pressed.emit(self.model_id)


class AddModelWidget(QWidget):
    model_saved = pyqtSignal()

    def __init__(self, store: CustomAIModelStore, parent=None):
        super().__init__(parent)
        self.store = store
        self._editing_id: Optional[str] = None
        self._metrics = dict(DEFAULT_METRICS)
        self._scaled_inputs: List[QWidget] = []
        self._scaled_labels: List[QLabel] = []
        self._init_ui()
        self._refresh_provider_candidates()

    def apply_ui_metrics(self, metrics: Dict[str, Any]):
        self._metrics = dict(metrics)
        apply_input_metrics(self._scaled_inputs, self._metrics)
        for lb in self._scaled_labels:
            if lb.property("hint_label"):
                lb.setStyleSheet(style_hint(self._metrics))
                lb.setFont(_metrics_font(self._metrics, "hint_font_px"))
            elif lb.property("form_label"):
                lb.setStyleSheet(style_form_label(self._metrics))
                lb.setFont(_metrics_font(self._metrics))
            else:
                lb.setStyleSheet(style_section(self._metrics))
                lb.setFont(_metrics_font(self._metrics, "section_font_px"))
        self.tag_bar.apply_ui_metrics(self._metrics)

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setSpacing(12)


        form_box = StyledContainer()
        form = QFormLayout(form_box)
        form.setContentsMargins(20, 16, 20, 16)
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignRight)

        def _form_label(text: str) -> QLabel:
            lb = QLabel(text)
            lb.setProperty("form_label", True)
            self._scaled_labels.append(lb)
            return lb

        self.input_provider = TabCompleteLineEdit()
        self.input_provider.set_tab_handler(self._tab_provider)
        self._scaled_inputs.append(self.input_provider)
        form.addRow(_form_label("服务商 *"), self.input_provider)

        self.input_base_url = QLineEdit()
        self._scaled_inputs.append(self.input_base_url)
        form.addRow(_form_label("请求地址 *"), self.input_base_url)

        proto_row = QHBoxLayout()
        self.input_protocol = QComboBox()
        self.input_protocol.addItems(["openai", "anthropic"])
        self.input_protocol.setEnabled(False)
        self._scaled_inputs.append(self.input_protocol)
        proto_row.addWidget(self.input_protocol)
        proto_row.addStretch()
        form.addRow(_form_label("协议格式 *"), proto_row)

        self.input_model = QLineEdit()
        self._scaled_inputs.append(self.input_model)
        form.addRow(_form_label("模型名称 *"), self.input_model)

        self.input_scene = QComboBox()
        for sk in SCENES:
            self.input_scene.addItem(SCENE_LABELS[sk], sk)
        self._scaled_inputs.append(self.input_scene)
        form.addRow(_form_label("使用场景 *"), self.input_scene)

        self.input_api_key = TabCompleteLineEdit()
        self.input_api_key.setEchoMode(QLineEdit.Password)
        self.input_api_key.set_tab_handler(self._tab_api_key)
        self._scaled_inputs.append(self.input_api_key)
        form.addRow(_form_label("API 密钥 *"), self.input_api_key)

        layout.addWidget(form_box)

        tag_title = QLabel("标签（可选，便于搜索与分组）")
        self._scaled_labels.append(tag_title)
        layout.addWidget(tag_title)
        self.tag_bar = TagChipBar()
        layout.addWidget(self.tag_bar)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.submit_btn = SmoothButton("保存模型", btn_type="action")
        self.submit_btn.clicked.connect(self._on_submit)
        self.cancel_btn = SmoothButton("取消编辑", btn_type="action")
        self.cancel_btn.clicked.connect(self._cancel_edit)
        self.cancel_btn.hide()
        self.delete_btn = SmoothButton("删除模型", btn_type="action")
        self.delete_btn.clicked.connect(self._on_delete)
        self.delete_btn.hide()
        btn_row.addWidget(self.delete_btn)
        btn_row.addWidget(self.submit_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)
        layout.addStretch()

        outer.addWidget(scroll)
        self.apply_ui_metrics(self._metrics)

    def _refresh_provider_candidates(self):
        profiles = self.store.get_provider_profiles()
        names = list(profiles.keys())
        for k in KNOWN_PROVIDER_URLS:
            if k not in names:
                names.append(k)
        self.input_provider.set_candidates(sorted(set(names), key=str.lower))

    def _tab_provider(self, name: str) -> bool:
        self.input_provider.setText(name)
        profiles = self.store.get_provider_profiles()
        if name in profiles:
            p = profiles[name]
            self.input_base_url.setText(p.get("base_url", ""))
            idx = self.input_protocol.findText(p.get("protocol", "openai"))
            if idx >= 0:
                self.input_protocol.setCurrentIndex(idx)
        elif name in KNOWN_PROVIDER_URLS:
            if not self.input_base_url.text().strip():
                self.input_base_url.setText(KNOWN_PROVIDER_URLS[name])
        return True

    def _tab_api_key(self, _match: str) -> bool:
        prov = self.input_provider.text().strip()
        profiles = self.store.get_provider_profiles()
        if prov in profiles and profiles[prov].get("api_key"):
            self.input_api_key.setText(profiles[prov]["api_key"])
            return True
        return False

    def _validate(self) -> Optional[Dict]:
        provider = self.input_provider.text().strip()
        base_url = self.input_base_url.text().strip()
        
        # 避免用户在地址后补齐 chat/completions 导致 OpenAI SDK 拼接重复
        if base_url.endswith("/chat/completions"):
            base_url = base_url[:-17]
        elif base_url.endswith("chat/completions"):
            base_url = base_url[:-16]
            
        protocol = self.input_protocol.currentText().strip()
        model = self.input_model.text().strip()
        api_key = self.input_api_key.text().strip()
        scene = self.input_scene.currentData()

        missing = []
        if not provider:
            missing.append("服务商")
        if not base_url:
            missing.append("请求地址")
        if not protocol:
            missing.append("协议格式")
        if not model:
            missing.append("模型名称")
        if not scene:
            missing.append("使用场景")
        if not api_key:
            missing.append("API 密钥")
        if missing:
            QMessageBox.warning(self, "请完善信息", "以下必填项未填写：\n" + "、".join(missing))
            return None

        return {
            "provider": provider,
            "base_url": base_url,
            "protocol": protocol,
            "model": model,
            "api_key": api_key,
            "scene": scene,
            "tags": self.tag_bar.get_tags(),
        }

    def _on_submit(self):
        data = self._validate()
        if not data:
            return
        if self._editing_id:
            self.store.update_model(self._editing_id, data)
        else:
            self.store.add_model(data)
        self.store.reload()
        self._refresh_provider_candidates()
        self._clear_form()
        self.model_saved.emit()

    def _cancel_edit(self):
        self._editing_id = None
        self.submit_btn.setText("保存模型")
        self.cancel_btn.hide()
        self.delete_btn.hide()
        self._clear_form()

    def _clear_form(self):
        self.input_provider.clear()
        self.input_base_url.clear()
        self.input_model.clear()
        self.input_api_key.clear()
        self.input_scene.setCurrentIndex(0)
        self.input_protocol.setCurrentIndex(0)
        self.tag_bar.clear_tags()

    def _on_delete(self):
        if not self._editing_id:
            return
        m = self.store.get_model_by_id(self._editing_id)
        name = m.get("model", "") if m else ""
        reply = QMessageBox.question(
            self, "删除模型",
            f"确定删除模型「{name}」？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.store.delete_model(self._editing_id)
            self.store.reload()
            self._refresh_provider_candidates()
            self._cancel_edit()
            self.model_saved.emit()

    def load_model_for_edit(self, model_id: str):
        m = self.store.get_model_by_id(model_id)
        if not m:
            return
        self._editing_id = model_id
        self.delete_btn.show()
        self.input_provider.setText(m.get("provider", ""))
        self.input_base_url.setText(m.get("base_url", ""))
        self.input_model.setText(m.get("model", ""))
        self.input_api_key.setText(m.get("api_key", ""))
        idx = self.input_protocol.findText(m.get("protocol", "openai"))
        if idx >= 0:
            self.input_protocol.setCurrentIndex(idx)
        scene = m.get("scene", "chat")
        si = self.input_scene.findData(scene)
        if si >= 0:
            self.input_scene.setCurrentIndex(si)
        self.tag_bar.set_tags(m.get("tags", []))
        self.submit_btn.setText("更新模型")
        self.cancel_btn.show()


class CreateGroupDialog(QDialog):
    def __init__(self, store: CustomAIModelStore, metrics: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.store = store
        self._metrics = dict(metrics)
        self._inputs: List[QWidget] = []
        self._labels: List[QLabel] = []
        self.setWindowTitle("创建模型组")
        self.setMinimumWidth(420)
        lay = QVBoxLayout(self)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("模型组名称")
        self._inputs.append(self.name_edit)
        name_lbl = QLabel("名称")
        self._labels.append(name_lbl)
        lay.addWidget(name_lbl)
        lay.addWidget(self.name_edit)
        self.scene_combos = {}
        for sk in SCENES:
            sl = QLabel(SCENE_LABELS[sk])
            self._labels.append(sl)
            lay.addWidget(sl)
            combo = QComboBox()
            self._inputs.append(combo)
            combo.addItem("（不选择）", "")
            for m in store.models_for_scene(sk):
                label = f"{m.get('model')} — {m.get('provider', '')}"
                combo.addItem(label, m.get("id"))
            self.scene_combos[sk] = combo
            lay.addWidget(combo)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self.apply_ui_metrics(self._metrics)

    def apply_ui_metrics(self, metrics: Dict[str, Any]):
        self._metrics = dict(metrics)
        apply_input_metrics(self._inputs, self._metrics)
        for lb in self._labels:
            lb.setStyleSheet(style_section(self._metrics))
            lb.setFont(_metrics_font(self._metrics, "section_font_px"))

    def group_data(self):
        return (
            self.name_edit.text().strip(),
            self.scene_combos["chat"].currentData(),
            self.scene_combos["vision"].currentData(),
            self.scene_combos["tts"].currentData(),
        )


class EdgeTtsDefaultVoiceWidget(QWidget):
    """默认音色配置：布局与听写页 VoiceListWidget 一致。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings_manager = SettingsManager()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        box = StyledContainer()
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(8, 8, 8, 8)
        from generation_page_neo import VoiceListWidget
        self.voice_list = VoiceListWidget(self)
        self._voice_scroll = self.voice_list.findChild(QScrollArea)
        if self._voice_scroll:
            self._voice_scroll.viewport().installEventFilter(self)
        self.voice_list.voice_selected.connect(self._on_voice_selected)
        box_layout.addWidget(self.voice_list)
        layout.addWidget(box)
        self.setMinimumHeight(260)

    def reload_voices(self):
        self.voice_list.load_voices(EDGE_TTS_VOICE_MODEL, auto_select_default=False)
        saved = get_default_edgetts_voice_id(self.settings_manager)
        if saved:
            self.voice_list.select_voice(saved)

    def _on_voice_selected(self, voice_id: str):
        set_default_edgetts_voice_id(voice_id, self.settings_manager)

    def eventFilter(self, obj, event):
        if hasattr(self, '_voice_scroll') and self._voice_scroll and obj == self._voice_scroll.viewport() and event.type() == QEvent.Wheel:
            scroll_area = self.parent()
            while scroll_area and not isinstance(scroll_area, QScrollArea):
                scroll_area = scroll_area.parent()
            
            if scroll_area:
                vbar = scroll_area.verticalScrollBar()
                if vbar:
                    delta = event.angleDelta().y()
                    inner_vbar = self._voice_scroll.verticalScrollBar()
                    
                    if delta > 0:  # 向上滚动
                        if inner_vbar and inner_vbar.value() > inner_vbar.minimum():
                            # 内层可以向上滚动，优先滚动内层（默认音色栏）
                            return super().eventFilter(obj, event)
                        elif vbar.value() > vbar.minimum():
                            # 内层已到顶，滚动外层页面
                            QApplication.sendEvent(scroll_area.verticalScrollBar(), event)
                            return True
                    elif delta < 0:  # 向下滚动
                        if vbar.value() < vbar.maximum():
                            # 外层没到底，优先滚动外层页面
                            QApplication.sendEvent(scroll_area.verticalScrollBar(), event)
                            return True
                        else:
                            # 外层到底了，滚动内层
                            return super().eventFilter(obj, event)
        return super().eventFilter(obj, event)

    def apply_ui_metrics(self, metrics: Dict[str, Any]):
        self.voice_list.set_font(_metrics_font(metrics))


class SelectModelWidget(QWidget):
    edit_model_requested = pyqtSignal(str)

    def __init__(self, store: CustomAIModelStore, parent=None):
        super().__init__(parent)
        self.store = store
        self._tag_filter = ""
        self._metrics = dict(DEFAULT_METRICS)
        self._scaled_inputs: List[QWidget] = []
        self._scaled_labels: List[QLabel] = []
        self._scene_titles: Dict[str, QLabel] = {}
        self._init_ui()

    def apply_ui_metrics(self, metrics: Dict[str, Any]):
        self._metrics = dict(metrics)
        apply_input_metrics(self._scaled_inputs, self._metrics)
        for lb in self._scaled_labels:
            if lb.property("hint_label"):
                lb.setStyleSheet(style_hint(self._metrics))
                lb.setFont(_metrics_font(self._metrics, "hint_font_px"))
            elif lb.property("status_label"):
                lb.setStyleSheet(style_status(self._metrics))
                lb.setFont(_metrics_font(self._metrics, "status_font_px"))
            else:
                lb.setStyleSheet(style_section(self._metrics))
                lb.setFont(_metrics_font(self._metrics, "section_font_px"))
        for lb in self._scene_titles.values():
            lb.setStyleSheet(style_section(self._metrics))
            lb.setFont(_metrics_font(self._metrics, "section_font_px"))
        if hasattr(self, "_edge_voice_panel"):
            self._edge_voice_panel.apply_ui_metrics(self._metrics)
        self._rebuild_scene_cards()
        self._rebuild_groups()
        if hasattr(self, "_edge_voice_panel"):
            if self.store.is_edgetts_active_tts():
                self._edge_voice_panel.setVisible(True)
                self._tts_voice_title.setVisible(True)
                self._edge_voice_panel.reload_voices()
            else:
                self._edge_voice_panel.setVisible(False)
                self._tts_voice_title.setVisible(False)

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(10)

        search_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索标签…")
        self._scaled_inputs.append(self.search_edit)
        self.search_edit.textChanged.connect(self._on_search_changed)
        search_row.addWidget(self.search_edit, 1)
        outer.addLayout(search_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self._scroll_body = QWidget()
        self._body_layout = QVBoxLayout(self._scroll_body)
        self._body_layout.setSpacing(16)
        scroll.setWidget(self._scroll_body)
        outer.addWidget(scroll)

        grp_header = QHBoxLayout()
        grp_title = QLabel("模型组")
        self._scaled_labels.append(grp_title)
        grp_header.addWidget(grp_title)
        grp_header.addStretch()
        add_grp_btn = SmoothButton("新建模型组", btn_type="action")
        add_grp_btn.clicked.connect(self._create_group)
        grp_header.addWidget(add_grp_btn)
        self._body_layout.addLayout(grp_header)
        self._groups_container = QVBoxLayout()
        self._groups_container.setSpacing(8)
        self._body_layout.addLayout(self._groups_container)

        self._scene_grids: Dict[str, QGridLayout] = {}
        self._scene_status: Dict[str, QLabel] = {}
        for sk in SCENES:
            sec = QHBoxLayout()
            title = QLabel(SCENE_LABELS[sk])
            self._scene_titles[sk] = title
            sec.addWidget(title)
            status = QLabel("")
            status.setProperty("status_label", True)
            self._scene_status[sk] = status
            self._scaled_labels.append(status)
            sec.addWidget(status)
            sec.addStretch()
            self._body_layout.addLayout(sec)
            grid_wrap = QWidget()
            grid = QGridLayout(grid_wrap)
            grid.setSpacing(10)
            self._scene_grids[sk] = grid
            self._body_layout.addWidget(grid_wrap)
            if sk == "tts":
                self._tts_voice_title = QLabel("默认音色")
                self._scaled_labels.append(self._tts_voice_title)
                self._body_layout.addWidget(self._tts_voice_title)
                self._edge_voice_panel = EdgeTtsDefaultVoiceWidget()
                self._body_layout.addWidget(self._edge_voice_panel)

        hint = QLabel("单击选择当前场景模型；长按约 0.5 秒可编辑配置。")
        hint.setProperty("hint_label", True)
        self._scaled_labels.append(hint)
        self._body_layout.addWidget(hint)
        self._body_layout.addStretch()
        self.apply_ui_metrics(self._metrics)
        if hasattr(self, "_edge_voice_panel"):
            self._edge_voice_panel.reload_voices()

    def refresh(self):
        self.store.reload()
        self.store.apply_edgetts_tts_selection(broadcast=False)
        for sk in SCENES:
            if sk in self._scene_status:
                if sk == "tts":
                    self._scene_status[sk].setText(f"当前：{EDGE_TTS_MODEL}")
                else:
                    active = self.store.get_active_model(sk)
                    self._scene_status[sk].setText(
                        f"当前：{active.get('model', '')}" if active else ""
                    )
        self._rebuild_groups()
        self._rebuild_scene_cards()

    def _on_search_changed(self, text: str):
        self._tag_filter = text.strip().lower()
        self._rebuild_scene_cards()
        self._rebuild_groups()

    def _model_passes_filter(self, m: Dict) -> bool:
        if not self._tag_filter:
            return True
        tags = [t.lower() for t in m.get("tags", [])]
        return any(self._tag_filter in t for t in tags)

    def _clear_layout(self, layout: QGridLayout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _rebuild_scene_cards(self):
        for sk, grid in self._scene_grids.items():
            self._clear_layout(grid)
            cols = 3
            if sk == "tts":
                self.store.apply_edgetts_tts_selection(broadcast=False)
                edge = EdgeTtsCard(self._metrics)
                grid.addWidget(edge, 0, 0)
                models = [
                    m for m in self.store.models_for_scene(sk)
                    if self._model_passes_filter(m)
                ]
                for i, m in enumerate(models):
                    idx = i + 1
                    card = ModelCard(
                        m, False, self._metrics, selectable=False,
                    )
                    card.setToolTip("文->音暂仅支持 EdgeTTS，自定义 TTS 模型稍后开放")
                    card.long_pressed.connect(self.edit_model_requested.emit)
                    grid.addWidget(card, idx // cols, idx % cols)
                continue

            models = [m for m in self.store.models_for_scene(sk) if self._model_passes_filter(m)]
            active_id = self.store.get_active_id(sk)
            for i, m in enumerate(models):
                card = ModelCard(m, m.get("id") == active_id, self._metrics)
                card.clicked.connect(lambda mid, s=sk: self._select_model(s, mid))
                card.long_pressed.connect(self.edit_model_requested.emit)
                grid.addWidget(card, i // cols, i % cols)
            if not models:
                empty = QLabel("暂无模型，请先在「添加模型」中配置")
                empty.setProperty("hint_label", True)
                empty.setStyleSheet(style_hint(self._metrics))
                empty.setFont(_metrics_font(self._metrics))
                grid.addWidget(empty, 0, 0, 1, cols)

    def _select_model(self, scene: str, model_id: str):
        if scene == "tts":
            return
        self.store.set_active_id(scene, model_id)
        self.refresh()

    def _rebuild_groups(self):
        while self._groups_container.count():
            item = self._groups_container.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        for g in self.store.groups:
            if self._tag_filter:
                ids = [g.get(sk) for sk in SCENES]
                models = [self.store.get_model_by_id(i) for i in ids if i]
                if not any(
                    self._model_passes_filter(m) for m in models if m
                ):
                    continue
            row = QFrame()
            row.setStyleSheet(
                "QFrame { background: #FAFBFF; border: 1px solid #D8DEFF; border-radius: 8px; }"
            )
            h = QHBoxLayout(row)
            h.setContentsMargins(12, 8, 12, 8)
            parts = []
            for sk in SCENES:
                if sk == "tts":
                    parts.append(f"{SCENE_LABELS[sk]}: {EDGE_TTS_MODEL}（固定）")
                    continue
                mid = g.get(sk, "")
                m = self.store.get_model_by_id(mid) if mid else None
                parts.append(
                    f"{SCENE_LABELS[sk]}: {m.get('model', '—') if m else '—'}"
                )
            info = QLabel(f"「{g.get('name', '')}」\n" + "  ·  ".join(parts))
            gpx = self._metrics["group_info_px"]
            gpv = self._metrics["input_pad_v"]
            gph = self._metrics["input_pad_h"]
            info.setStyleSheet(
                f"border: none; background: transparent; font-size: {gpx}px;"
            )
            info.setFont(_metrics_font(self._metrics, "group_info_px"))
            h.addWidget(info, 1)
            use_btn = SmoothButton("一键启用", btn_type="action")
            use_btn.clicked.connect(lambda _c, gid=g.get("id"): self._activate_group(gid))
            del_btn = QPushButton("删除")
            del_btn.setStyleSheet(
                f"QPushButton {{ color: #AA4444; border: 1px solid #CCAAAA; "
                f"border-radius: 4px; padding: {gpv}px {gph}px; background: white; "
                f"font-size: {gpx}px; }}"
            )
            del_btn.setFont(_metrics_font(self._metrics, "group_info_px"))
            del_btn.clicked.connect(lambda _c, gid=g.get("id"): self._delete_group(gid))
            h.addWidget(use_btn)
            h.addWidget(del_btn)
            self._groups_container.addWidget(row)

        if not self.store.groups:
            empty_g = QLabel("暂无模型组，可一键启用三个场景的模型配置。")
            empty_g.setProperty("hint_label", True)
            empty_g.setStyleSheet(style_hint(self._metrics))
            empty_g.setFont(_metrics_font(self._metrics))
            self._groups_container.addWidget(empty_g)

    def _activate_group(self, group_id: str):
        if self.store.activate_group(group_id):
            self.refresh()

    def _delete_group(self, group_id: str):
        reply = QMessageBox.question(
            self, "删除模型组", "确定删除该模型组？（不会删除其中的模型）",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.store.delete_group(group_id)
            self.refresh()

    def _create_group(self):
        dlg = CreateGroupDialog(self.store, self._metrics, self)
        if dlg.exec_() != QDialog.Accepted:
            return
        name, chat_id, vision_id, tts_id = dlg.group_data()
        if not name:
            QMessageBox.warning(self, "提示", "请填写模型组名称")
            return
        if not any((chat_id, vision_id, tts_id)):
            QMessageBox.warning(self, "提示", "请至少为一个场景选择模型")
            return
        self.store.add_group(name, chat_id or "", vision_id or "", tts_id or "")
        self.refresh()


def _window_for_scale(widget: QWidget):
    w = widget
    while w is not None:
        if hasattr(w, "parent_window") and getattr(w, "parent_window", None):
            return w.parent_window
        if w.parent() is None and w.isWindow():
            return w
        w = w.parent()
    return widget.window() if widget else None


class AiSettingsTab(QWidget):
    """AI 设置：四级选项卡「添加模型」「选择模型」。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.store = CustomAIModelStore()
        self._metrics = dict(DEFAULT_METRICS)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(10)

        tab_bar = StyledContainer()
        tab_lay = QHBoxLayout(tab_bar)
        tab_lay.setContentsMargins(12, 10, 12, 10)
        tab_lay.setSpacing(10)

        self.btn_add = SmoothButton("添加模型", "tab_level2")
        self.btn_select = SmoothButton("选择模型", "tab_level2")
        self.btn_add.setChecked(True)
        self.level4_group = QButtonGroup(self)
        self.level4_group.addButton(self.btn_add, 0)
        self.level4_group.addButton(self.btn_select, 1)
        self.level4_group.buttonClicked[int].connect(self._on_tab_changed)

        tab_lay.addStretch()
        tab_lay.addWidget(self.btn_add)
        tab_lay.addWidget(self.btn_select)
        tab_lay.addStretch()
        layout.addWidget(tab_bar)

        self.stack = QStackedWidget()
        self.add_page = AddModelWidget(self.store)
        self.select_page = SelectModelWidget(self.store)
        self.stack.addWidget(self.add_page)
        self.stack.addWidget(self.select_page)
        layout.addWidget(self.stack)

        # 添加渐隐渐显动画
        self.stacked_opacity_effect = QGraphicsOpacityEffect(self.stack)
        self.stack.setGraphicsEffect(self.stacked_opacity_effect)
        self.stacked_opacity_effect.setEnabled(False)
        self.fade_animation = QPropertyAnimation(self.stacked_opacity_effect, b"opacity")
        self.fade_animation.setDuration(200) # 动画时长
        self.fade_animation.setEasingCurve(QEasingCurve.InOutQuad) # 平滑过渡
        self.fade_animation.finished.connect(self._on_fade_animation_finished)
        self.target_stacked_index = 0 # 记录目标索引

        self.add_page.model_saved.connect(self._on_model_saved)
        self.select_page.edit_model_requested.connect(self._open_edit)
        self.store.apply_edgetts_tts_selection(broadcast=False)
        QTimer.singleShot(0, self.update_ui_scale)

    def update_ui_scale(self, main_window=None):
        win = main_window or _window_for_scale(self)
        if win is None:
            return
        font_name = SettingsManager().Custom.get_value("global_font", "微软雅黑")
        self._metrics = compute_ai_ui_metrics(
            win.width(), win.height(), font_name
        )
        if hasattr(self, "add_page"):
            self.add_page.apply_ui_metrics(self._metrics)
        if hasattr(self, "select_page"):
            self.select_page.apply_ui_metrics(self._metrics)
        # 四级选项卡（添加模型/选择模型）字号由 SettingsPage._update_fonts 递归设置，不在此覆盖

    def resizeEvent(self, event):
        self.update_ui_scale()
        super().resizeEvent(event)

    def _on_tab_changed(self, index: int):
        if self.stack.currentIndex() == index:
            return
        self.target_stacked_index = index
        self.stacked_opacity_effect.setEnabled(True)
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.start()

    def _on_fade_animation_finished(self):
        if self.stacked_opacity_effect.opacity() == 0.0:
            self.stack.setCurrentIndex(self.target_stacked_index)
            if self.target_stacked_index == 1:
                self.select_page.refresh()
            self.fade_animation.setStartValue(0.0)
            self.fade_animation.setEndValue(1.0)
            self.fade_animation.start()
        else:
            self.stacked_opacity_effect.setEnabled(False)

    def _on_model_saved(self):
        self.select_page.refresh()

    def _open_edit(self, model_id: str):
        self.btn_add.setChecked(True)
        self.stack.setCurrentIndex(0)
        self.add_page.load_model_for_edit(model_id)

    def hide_right_panel(self):
        pass

    def show_right_panel_if_needed(self):
        pass

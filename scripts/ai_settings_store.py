# coding=utf-8
"""自定义 AI 模型配置的读写与迁移。"""
import json
import uuid
from typing import Any, Dict, List, Optional

from misc_func import SettingsManager

SCENES = ("chat", "vision", "tts")
SCENE_LABELS = {"chat": "文->文", "vision": "图->文", "tts": "文->音"}
LABEL_TO_SCENE = {v: k for k, v in SCENE_LABELS.items()}

SETTINGS_MODELS_KEY = "custom_ai_models"
SETTINGS_GROUPS_KEY = "ai_model_groups"
ACTIVE_KEY_FMT = "ai_active_custom_{scene}"

# 文->音：EdgeTTS 为系统内置项（非 custom_ai_models 条目）
EDGE_TTS_SENTINEL = "__edge_tts__"
EDGE_TTS_LEGACY_PROVIDER_KEY = "ai_model_tts_provider"
EDGE_TTS_LEGACY_MODEL_KEY = "ai_model_tts_model"
EDGE_TTS_PROVIDER = "MS"
EDGE_TTS_MODEL = "edge-tts"
EDGE_TTS_VOICE_MODEL = "Microsoft/edge-tts"
DEFAULT_VOICE_KEY_MS = "default_voice_MS_edge-tts"
DEFAULT_VOICE_KEY_LEGACY = "default_voice_edgetts"
DEFAULT_EDGE_VOICE_FALLBACK = "zh-CN-Yunyang"


def get_default_edgetts_voice_id(settings_manager: Optional[SettingsManager] = None) -> str:
    sm = settings_manager or SettingsManager()
    voice = sm.Custom.get_value(DEFAULT_VOICE_KEY_MS, "")
    if not voice:
        voice = sm.Custom.get_value(DEFAULT_VOICE_KEY_LEGACY, "")
    return voice or DEFAULT_EDGE_VOICE_FALLBACK


def set_default_edgetts_voice_id(voice_id: str, settings_manager: Optional[SettingsManager] = None) -> None:
    sm = settings_manager or SettingsManager()
    sm.Custom.set_value(DEFAULT_VOICE_KEY_MS, voice_id)
    sm.Custom.set_value(DEFAULT_VOICE_KEY_LEGACY, voice_id)


def _new_id() -> str:
    return str(uuid.uuid4())


def normalize_model(raw: Dict[str, Any]) -> Dict[str, Any]:
    """补齐 id、tags 等字段。"""
    m = dict(raw)
    if not m.get("id"):
        m["id"] = _new_id()
    m.setdefault("provider", "")
    m.setdefault("base_url", "")
    m.setdefault("protocol", "openai")
    m.setdefault("model", "")
    m.setdefault("api_key", "")
    m.setdefault("scene", "chat")
    tags = m.get("tags")
    if not isinstance(tags, list):
        m["tags"] = []
    else:
        m["tags"] = [str(t).strip() for t in tags if str(t).strip()]
    return m


class CustomAIModelStore:
    def __init__(self, settings_manager: Optional[SettingsManager] = None):
        self.settings = settings_manager or SettingsManager()
        self.models: List[Dict[str, Any]] = []
        self.groups: List[Dict[str, Any]] = []
        self.reload()

    def reload(self):
        self.models = self._load_models()
        self.groups = self._load_groups()

    def _load_models(self) -> List[Dict[str, Any]]:
        try:
            data = self.settings.Custom.get_value(SETTINGS_MODELS_KEY, "")
            if not data:
                return []
            items = json.loads(data)
            if not isinstance(items, list):
                return []
            models = [normalize_model(x) for x in items if isinstance(x, dict)]
            if any(isinstance(x, dict) and not x.get("id") for x in items):
                self.models = models
                self.save_models()
            return models
        except Exception:
            return []

    def _load_groups(self) -> List[Dict[str, Any]]:
        try:
            data = self.settings.Custom.get_value(SETTINGS_GROUPS_KEY, "")
            if not data:
                return []
            items = json.loads(data)
            if not isinstance(items, list):
                return []
            out = []
            for g in items:
                if not isinstance(g, dict):
                    continue
                out.append({
                    "id": g.get("id") or _new_id(),
                    "name": str(g.get("name", "未命名组")).strip() or "未命名组",
                    "chat": g.get("chat", ""),
                    "vision": g.get("vision", ""),
                    "tts": g.get("tts", ""),
                })
            return out
        except Exception:
            return []

    def save_models(self):
        self.settings.Custom.set_value(
            SETTINGS_MODELS_KEY,
            json.dumps(self.models, ensure_ascii=False),
        )

    def save_groups(self):
        self.settings.Custom.set_value(
            SETTINGS_GROUPS_KEY,
            json.dumps(self.groups, ensure_ascii=False),
        )

    def get_model_by_id(self, model_id: str) -> Optional[Dict[str, Any]]:
        for m in self.models:
            if m.get("id") == model_id:
                return m
        return None

    def find_index(self, model_id: str) -> int:
        for i, m in enumerate(self.models):
            if m.get("id") == model_id:
                return i
        return -1

    def add_model(self, data: Dict[str, Any]) -> Dict[str, Any]:
        m = normalize_model(data)
        if not m.get("id"):
            m["id"] = _new_id()
        self.models.append(m)
        self.save_models()
        return m

    def update_model(self, model_id: str, data: Dict[str, Any]) -> bool:
        idx = self.find_index(model_id)
        if idx < 0:
            return False
        kept_id = self.models[idx]["id"]
        m = normalize_model(data)
        m["id"] = kept_id
        self.models[idx] = m
        self.save_models()
        return True

    def delete_model(self, model_id: str) -> bool:
        idx = self.find_index(model_id)
        if idx < 0:
            return False
        self.models.pop(idx)
        self.save_models()
        for scene in SCENES:
            if self.get_active_id(scene) == model_id:
                self.set_active_id(scene, "")
        for g in self.groups:
            for sk in SCENES:
                if g.get(sk) == model_id:
                    g[sk] = ""
        self.save_groups()
        return True

    def models_for_scene(self, scene: str) -> List[Dict[str, Any]]:
        return [m for m in self.models if m.get("scene") == scene]

    def all_tags(self) -> List[str]:
        tags = set()
        for m in self.models:
            for t in m.get("tags", []):
                tags.add(t)
        return sorted(tags)

    def get_provider_profiles(self) -> Dict[str, Dict[str, str]]:
        """按服务商聚合最近一次配置，供 Tab 补全。"""
        profiles: Dict[str, Dict[str, str]] = {}
        for m in self.models:
            name = (m.get("provider") or "").strip()
            if not name:
                continue
            profiles[name] = {
                "provider": name,
                "base_url": m.get("base_url", ""),
                "protocol": m.get("protocol", "openai"),
                "api_key": m.get("api_key", ""),
            }
        return profiles

    def get_active_id(self, scene: str) -> str:
        return self.settings.Custom.get_value(ACTIVE_KEY_FMT.format(scene=scene), "") or ""

    def set_active_id(self, scene: str, model_id: str):
        self.settings.Custom.set_value(ACTIVE_KEY_FMT.format(scene=scene), model_id or "")

    def get_active_model(self, scene: str) -> Optional[Dict[str, Any]]:
        if scene == "tts" and self.is_edgetts_active_tts():
            return {
                "id": EDGE_TTS_SENTINEL,
                "provider": "Microsoft",
                "model": EDGE_TTS_MODEL,
                "scene": "tts",
            }
        mid = self.get_active_id(scene)
        if not mid:
            return None
        return self.get_model_by_id(mid)

    def is_edgetts_active_tts(self) -> bool:
        """文->音是否使用 EdgeTTS（当前强制默认）。"""
        mid = self.get_active_id("tts")
        return not mid or mid == EDGE_TTS_SENTINEL

    def apply_edgetts_tts_selection(self, broadcast: bool = True) -> None:
        """选中 EdgeTTS 并写入 TTS 路由所需的 legacy 配置（与 backup 一致）。"""
        self.set_active_id("tts", EDGE_TTS_SENTINEL)
        self.settings.Custom.set_value(EDGE_TTS_LEGACY_PROVIDER_KEY, EDGE_TTS_PROVIDER)
        self.settings.Custom.set_value(EDGE_TTS_LEGACY_MODEL_KEY, EDGE_TTS_MODEL)
        if broadcast:
            try:
                from shared_memory_manager import get_shared_memory_manager
                get_shared_memory_manager().broadcast_settings_change(
                    "ai_model_tts",
                    {"provider": EDGE_TTS_PROVIDER, "model": EDGE_TTS_MODEL},
                )
            except Exception:
                pass

    def activate_group(self, group_id: str) -> bool:
        grp = None
        for g in self.groups:
            if g.get("id") == group_id:
                grp = g
                break
        if not grp:
            return False
        for scene in SCENES:
            if scene == "tts":
                self.apply_edgetts_tts_selection(broadcast=True)
                continue
            mid = grp.get(scene, "")
            if mid and self.get_model_by_id(mid):
                self.set_active_id(scene, mid)
        return True

    def add_group(self, name: str, chat_id: str, vision_id: str, tts_id: str) -> Dict[str, Any]:
        g = {
            "id": _new_id(),
            "name": name.strip() or "未命名组",
            "chat": chat_id,
            "vision": vision_id,
            "tts": tts_id,
        }
        self.groups.append(g)
        self.save_groups()
        return g

    def delete_group(self, group_id: str) -> bool:
        before = len(self.groups)
        self.groups = [g for g in self.groups if g.get("id") != group_id]
        if len(self.groups) < before:
            self.save_groups()
            return True
        return False

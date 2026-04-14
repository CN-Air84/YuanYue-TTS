# coding=utf-8
import base64
import os
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any

try:
    from debug_logger import debug_logger, LogLevel
except ImportError:
    class LogLevel:
        INFO = 1
        WARNING = 2
        ERROR = 3
    def debug_logger_output(module, level, msg, fold_code=""):
        print(f"[{module}] {msg}")
    debug_logger = type('obj', (object,), {'output': staticmethod(debug_logger_output)})()

try:
    from misc_func import SettingsManager
    SETTINGS_AVAILABLE = True
except ImportError:
    SETTINGS_AVAILABLE = False


class AIScene(Enum):
    """AI应用场景枚举"""
    CHAT = "chat"           # 正常对话
    VISION = "vision"       # 图片识别
    TTS = "tts"             # 文字转语音（仅负责模型选择，实际合成由TTSManager）
    # STT = "stt"           # 语音转文字（暂时隐藏）


class ModelTier(Enum):
    """模型梯队枚举"""
    FREE = "free"                    # 第一梯队·完全免费
    LIMITED_FREE = "limited_free"    # 第二梯队·限时免费
    PAID = "paid"                    # 第三梯队·常态收费


@dataclass
class AIModel:
    """AI模型信息"""
    name: str                # 模型名称
    provider: str            # 提供商
    tier: ModelTier          # 所属梯队
    scene: AIScene           # 适用场景
    tts_group: Optional[str] = None  # TTS分组（仅TTS场景用）
    warning: Optional[str] = None     # 警告信息


# ========== 完整模型注册表 ==========

MODELS = {
    # ========== 第一梯队·完全免费 ==========
    "ChatGLM": {
        "chat": [
            AIModel("GLM-4.7-Flash", "ChatGLM", ModelTier.FREE, AIScene.CHAT),
            AIModel("GLM-4-Flash-250414", "ChatGLM", ModelTier.FREE, AIScene.CHAT),
        ],
        "vision": [
            AIModel("GLM-4.6V-Flash", "ChatGLM", ModelTier.FREE, AIScene.VISION),
            AIModel("GLM-4.1V-Thinking-Flash", "ChatGLM", ModelTier.FREE, AIScene.VISION),
            AIModel("GLM-4V-Flash", "ChatGLM", ModelTier.FREE, AIScene.VISION),
        ],
        "tts": [
        ],
    },
    
    # ========== 第二梯队·限时免费 ==========
    "Qwen": {
        "chat": [
            AIModel("qwen3-max", "Qwen", ModelTier.LIMITED_FREE, AIScene.CHAT),
            AIModel("qwen3-max-2026-01-23", "Qwen", ModelTier.LIMITED_FREE, AIScene.CHAT),
            AIModel("qwen3-max-2025-09-23", "Qwen", ModelTier.LIMITED_FREE, AIScene.CHAT),
            AIModel("qwen3-max-preview", "Qwen", ModelTier.LIMITED_FREE, AIScene.CHAT),
            AIModel("qwen-max", "Qwen", ModelTier.LIMITED_FREE, AIScene.CHAT),
            AIModel("qwen-max-latest", "Qwen", ModelTier.LIMITED_FREE, AIScene.CHAT),
            AIModel("qwen-max-2025-01-25", "Qwen", ModelTier.LIMITED_FREE, AIScene.CHAT),
            AIModel("qwen-max-2024-09-19", "Qwen", ModelTier.LIMITED_FREE, AIScene.CHAT),
            AIModel("qwen-max-2024-04-28", "Qwen", ModelTier.LIMITED_FREE, AIScene.CHAT),
            AIModel("qwen3.5-plus", "Qwen", ModelTier.LIMITED_FREE, AIScene.CHAT),
            AIModel("qwen3.5-plus-2026-02-15", "Qwen", ModelTier.LIMITED_FREE, AIScene.CHAT),
            AIModel("qwen-plus", "Qwen", ModelTier.LIMITED_FREE, AIScene.CHAT),
            AIModel("qwen-plus-latest", "Qwen", ModelTier.LIMITED_FREE, AIScene.CHAT),
            AIModel("qwen-plus-2025-12-01", "Qwen", ModelTier.LIMITED_FREE, AIScene.CHAT),
            AIModel("qwen-plus-2025-09-11", "Qwen", ModelTier.LIMITED_FREE, AIScene.CHAT),
            AIModel("qwen-plus-2025-07-28", "Qwen", ModelTier.LIMITED_FREE, AIScene.CHAT),
            AIModel("qwen-plus-2025-07-14", "Qwen", ModelTier.LIMITED_FREE, AIScene.CHAT),
            AIModel("qwen-plus-2025-04-28", "Qwen", ModelTier.LIMITED_FREE, AIScene.CHAT),
            AIModel("qwen-plus-2025-01-25", "Qwen", ModelTier.LIMITED_FREE, AIScene.CHAT),
            AIModel("qwen3.5-flash", "Qwen", ModelTier.LIMITED_FREE, AIScene.CHAT),
            AIModel("qwen3.5-flash-2026-02-23", "Qwen", ModelTier.LIMITED_FREE, AIScene.CHAT),
            AIModel("qwen-flash", "Qwen", ModelTier.LIMITED_FREE, AIScene.CHAT),
            AIModel("qwen-flash-2025-07-28", "Qwen", ModelTier.LIMITED_FREE, AIScene.CHAT),
        ],
        "vision": [
            # OCR专精
            AIModel("qwen-vl-ocr", "Qwen", ModelTier.LIMITED_FREE, AIScene.VISION),
            AIModel("qwen-vl-ocr-latest", "Qwen", ModelTier.LIMITED_FREE, AIScene.VISION),
            AIModel("qwen-vl-ocr-2025-11-20", "Qwen", ModelTier.LIMITED_FREE, AIScene.VISION),
            AIModel("qwen-vl-ocr-2025-08-28", "Qwen", ModelTier.LIMITED_FREE, AIScene.VISION),
            AIModel("qwen-vl-ocr-2025-04-13", "Qwen", ModelTier.LIMITED_FREE, AIScene.VISION),
            AIModel("qwen-vl-ocr-2024-10-28", "Qwen", ModelTier.LIMITED_FREE, AIScene.VISION),
            # 标准视觉
            AIModel("qvq-max", "Qwen", ModelTier.LIMITED_FREE, AIScene.VISION),
            AIModel("qvq-max-latest", "Qwen", ModelTier.LIMITED_FREE, AIScene.VISION),
            AIModel("qvq-max-2025-05-15", "Qwen", ModelTier.LIMITED_FREE, AIScene.VISION),
            AIModel("qvq-max-2025-03-25", "Qwen", ModelTier.LIMITED_FREE, AIScene.VISION),
            AIModel("qvq-plus", "Qwen", ModelTier.LIMITED_FREE, AIScene.VISION),
            AIModel("qvq-plus-latest", "Qwen", ModelTier.LIMITED_FREE, AIScene.VISION),
            AIModel("qvq-plus-2025-05-15", "Qwen", ModelTier.LIMITED_FREE, AIScene.VISION),
            AIModel("qwen3-vl-plus", "Qwen", ModelTier.LIMITED_FREE, AIScene.VISION),
            AIModel("qwen3-vl-plus-2025-12-19", "Qwen", ModelTier.LIMITED_FREE, AIScene.VISION),
            AIModel("qwen3-vl-plus-2025-09-23", "Qwen", ModelTier.LIMITED_FREE, AIScene.VISION),
            AIModel("qwen3-vl-flash", "Qwen", ModelTier.LIMITED_FREE, AIScene.VISION),
            AIModel("qwen3-vl-flash-2026-01-22", "Qwen", ModelTier.LIMITED_FREE, AIScene.VISION),
            AIModel("qwen3-vl-flash-2025-10-15", "Qwen", ModelTier.LIMITED_FREE, AIScene.VISION),
        ],
        "tts": [
            # instruct组
            AIModel("qwen3-tts-instruct-flash", "Qwen", ModelTier.LIMITED_FREE, AIScene.TTS, tts_group="instruct"),
            AIModel("qwen3-tts-instruct-flash-2026-01-26", "Qwen", ModelTier.LIMITED_FREE, AIScene.TTS, tts_group="instruct"),
            # vd组
            AIModel("qwen3-tts-vd-2026-01-26", "Qwen", ModelTier.LIMITED_FREE, AIScene.TTS, tts_group="vd"),
            # vc组
            AIModel("qwen3-tts-vc-2026-01-22", "Qwen", ModelTier.LIMITED_FREE, AIScene.TTS, tts_group="vc"),
            # 标准组
            AIModel("qwen3-tts-flash", "Qwen", ModelTier.LIMITED_FREE, AIScene.TTS, tts_group="standard"),
            AIModel("qwen3-tts-flash-2025-11-27", "Qwen", ModelTier.LIMITED_FREE, AIScene.TTS, tts_group="standard"),
            AIModel("qwen3-tts-flash-2025-09-18", "Qwen", ModelTier.LIMITED_FREE, AIScene.TTS, tts_group="standard"),
            AIModel("qwen-tts", "Qwen", ModelTier.LIMITED_FREE, AIScene.TTS, tts_group="standard"),
            AIModel("qwen-tts-latest", "Qwen", ModelTier.LIMITED_FREE, AIScene.TTS, tts_group="standard"),
            AIModel("qwen-tts-2025-05-22", "Qwen", ModelTier.LIMITED_FREE, AIScene.TTS, tts_group="standard"),
            AIModel("qwen-tts-2025-04-10", "Qwen", ModelTier.LIMITED_FREE, AIScene.TTS, tts_group="standard"),
        ],
    },
    
    # ========== 第三梯队·常态收费 ==========
    "KIMI": {
        "chat": [
            AIModel("kimi-k2.5", "KIMI", ModelTier.PAID, AIScene.CHAT),
            AIModel("kimi-k2-0905-preview", "KIMI", ModelTier.PAID, AIScene.CHAT),
            AIModel("kimi-k2-0711-preview", "KIMI", ModelTier.PAID, AIScene.CHAT),
            AIModel("kimi-k2-turbo-preview", "KIMI", ModelTier.PAID, AIScene.CHAT),
            AIModel("kimi-k2-thinking", "KIMI", ModelTier.PAID, AIScene.CHAT),
            AIModel("kimi-k2-thinking-turbo", "KIMI", ModelTier.PAID, AIScene.CHAT),
        ],
        "vision": [
            AIModel("kimi-k2.5", "KIMI", ModelTier.PAID, AIScene.VISION),
        ],
    },
    
    "Minimax": {
        "chat": [
            AIModel("MiniMax-M2.7", "Minimax", ModelTier.PAID, AIScene.CHAT),
            AIModel("MiniMax-M2.5", "Minimax", ModelTier.PAID, AIScene.CHAT),
            AIModel("MiniMax-M2.7-highspeed", "Minimax", ModelTier.PAID, AIScene.CHAT),
            AIModel("MiniMax-M2.5-highspeed", "Minimax", ModelTier.PAID, AIScene.CHAT),
            AIModel("MiniMax-M2.1", "Minimax", ModelTier.PAID, AIScene.CHAT),
            AIModel("MiniMax-M2.1-highspeed", "Minimax", ModelTier.PAID, AIScene.CHAT),
            AIModel("MiniMax-M2", "Minimax", ModelTier.PAID, AIScene.CHAT),
        ],
        "tts": [
            AIModel("speech-2.8-turbo", "Minimax", ModelTier.PAID, AIScene.TTS),
            AIModel("speech-2.6-turbo", "Minimax", ModelTier.PAID, AIScene.TTS),
            AIModel("speech-02-turbo", "Minimax", ModelTier.PAID, AIScene.TTS),
            AIModel("speech-2.8-hd", "Minimax", ModelTier.PAID, AIScene.TTS),
            AIModel("speech-2.6-hd", "Minimax", ModelTier.PAID, AIScene.TTS),
            AIModel("speech-02-hd", "Minimax", ModelTier.PAID, AIScene.TTS),
        ],
    },
    
    "ChatGLM_Paid": {
        "chat": [
            AIModel("GLM-5", "ChatGLM", ModelTier.PAID, AIScene.CHAT),
            AIModel("GLM-4.7", "ChatGLM", ModelTier.PAID, AIScene.CHAT),
            AIModel("GLM-4.6", "ChatGLM", ModelTier.PAID, AIScene.CHAT),
            AIModel("GLM-4.5", "ChatGLM", ModelTier.PAID, AIScene.CHAT),
        ],
        "vision": [
            AIModel("GLM-OCR", "ChatGLM", ModelTier.PAID, AIScene.VISION),
            AIModel("GLM-4.6V", "ChatGLM", ModelTier.PAID, AIScene.VISION),
            AIModel("GLM-4.1V-Thinking", "ChatGLM", ModelTier.PAID, AIScene.VISION),
        ],
        "tts": [
            AIModel("GLM-TTS", "ChatGLM", ModelTier.PAID, AIScene.TTS),
        ],
    },
    
    "Mimo": {
        "chat": [
            AIModel("Mimo-V2-Omni", "Mimo", ModelTier.PAID, AIScene.CHAT),
        ],
        "vision": [
            AIModel("Mimo-V2-Omni", "Mimo", ModelTier.PAID, AIScene.VISION),
        ],
        "tts": [
            AIModel("edge-tts", "Microsoft", ModelTier.FREE, AIScene.TTS),
            AIModel("MiMo-V2-TTS", "Mimo", ModelTier.LIMITED_FREE, AIScene.TTS),
        ],
    },
}


# ========== 提供商配置 ==========

PROVIDER_CONFIG = {
    "ChatGLM": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
        "api_key_name": "api_key_ChatGLM",
    },
    "Qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/",
        "api_key_name": "api_key_Qwen",
    },
    "KIMI": {
        "base_url": "https://api.moonshot.cn/v1/",
        "api_key_name": "api_key_KIMI",
    },
    "Minimax": {
        "base_url": "https://api.minimaxi.com/v1/",
        "api_key_name": "api_key_Minimax",
    },
    "Mimo": {
        "base_url": "https://api.xiaomimimo.com/v1/",
        "api_key_name": "api_key_Mimo",
    },
}


@dataclass
class AIRequest:
    """AI请求数据类"""
    prompt: str
    scene: AIScene = AIScene.CHAT
    image_path: Optional[str] = None
    image_base64: Optional[str] = None  # 预编码的base64图片（避免重复编码）
    model: Optional[str] = None
    provider: Optional[str] = None
    tier: Optional[ModelTier] = None
    tts_group: Optional[str] = None  # TTS分组筛选
    save_path: Optional[str] = None


@dataclass
class AIResponse:
    """AI响应数据类"""
    text: str = ""
    audio_path: Optional[str] = None
    model_used: Optional[str] = None
    provider_used: Optional[str] = None
    success: bool = True
    error: Optional[str] = None


class AIManager:
    """统一AI数据交换管理器"""
    
    def __init__(self):
        if SETTINGS_AVAILABLE:
            self.settings_manager = SettingsManager()
        else:
            self.settings_manager = None
        
        # 缓存客户端实例
        self._clients: Dict[str, Any] = {}
    
    def chat(self, request: AIRequest) -> AIResponse:
        """执行对话/视觉识别请求"""
        debug_logger.output("ai_manager.py", LogLevel.INFO, 
            f"AIManager 收到请求: scene={request.scene.value}, "
            f"prompt长度={len(request.prompt)}, image={request.image_path}, "
            f"provider={request.provider}, model={request.model}", 
            fold_code="AI_REQUEST")
        
        # 1. 选择模型
        model_info = self._select_model(request)
        if not model_info:
            raise ValueError(f"未找到合适的模型: scene={request.scene.value}, "
                           f"provider={request.provider}, tier={request.tier}")
        
        if request.scene == AIScene.TTS:
            debug_logger.output("ai_manager.py", LogLevel.INFO, 
                f"TTS模型已选择: {model_info.name} ({model_info.provider}), "
                f"实际合成由TTSManager负责", 
                fold_code="AI_TTS_SELECT")
            return AIResponse(
                text="",
                model_used=model_info.name,
                provider_used=model_info.provider
            )

        # 2. 获取API Key
        api_key = self._get_api_key(model_info.provider)
        if not api_key:
            raise ValueError(f"未配置 {model_info.provider} API Key，请在设置中配置")
        
        # 3. 获取客户端
        client = self._get_client(model_info.provider, api_key)
        
        # 4. 构建消息
        messages = self._build_messages(request)
        
        # 5. 执行请求
        response = client.chat.completions.create(
            model=model_info.name,
            messages=messages,
            max_tokens=1000
        )
        
        text = response.choices[0].message.content
        
        debug_logger.output("ai_manager.py", LogLevel.INFO, 
            f"AI 响应: text长度={len(text)}, model={model_info.name}", 
            fold_code="AI_RESPONSE")
        
        return AIResponse(
            text=text,
            model_used=model_info.name,
            provider_used=model_info.provider
        )

    def resolve_model(self, request: AIRequest) -> Optional[AIModel]:
        """仅解析模型，不执行实际请求"""
        return self._select_model(request)
    
    def _select_model(self, request: AIRequest) -> Optional[AIModel]:
        """根据请求条件选择合适的模型"""
        
        # 构建可选模型列表
        candidates = []
        
        # 遍历所有提供商
        for provider_key, scenes in MODELS.items():
            # 确定提供商名称（去掉_Paid后缀）
            actual_provider = provider_key.replace("_Paid", "")

            # 获取对应场景的模型列表
            scene_key = request.scene.value
            if scene_key not in scenes:
                continue
            
            for model in scenes[scene_key]:
                if request.provider and request.provider not in {actual_provider, model.provider}:
                    continue

                # 筛选梯队
                if request.tier and request.tier != model.tier:
                    continue
                
                # 筛选TTS分组
                if request.scene == AIScene.TTS and request.tts_group:
                    if model.tts_group != request.tts_group:
                        continue
                
                candidates.append(model)
        
        if not candidates:
            debug_logger.output("ai_manager.py", LogLevel.WARNING, 
                f"未找到匹配的模型: scene={request.scene.value}, "
                f"provider={request.provider}, tier={request.tier}", 
                fold_code="AI_MODEL_SELECT")
            return None
        
        # 如果指定了模型名称，优先使用
        if request.model:
            for model in candidates:
                if model.name == request.model:
                    return model
                    
        # 如果未指定，尝试从设置中读取
        if not request.model and self.settings_manager:
            scene_key = f"ai_model_{request.scene.value}"
            saved_provider = self.settings_manager.Custom.get_value(f"{scene_key}_provider", "")
            saved_model = self.settings_manager.Custom.get_value(f"{scene_key}_model", "")
            if saved_provider and saved_model:
                for model in candidates:
                    if model.provider == saved_provider and model.name == saved_model:
                        debug_logger.output("ai_manager.py", LogLevel.INFO, 
                            f"从设置读取默认模型: {saved_model} ({saved_provider})", 
                            fold_code="AI_MODEL_SELECT")
                        return model
            if saved_provider or saved_model:
                debug_logger.output("ai_manager.py", LogLevel.WARNING, 
                    f"保存的默认模型未命中，将回退自动选择: {saved_model} ({saved_provider})", 
                    fold_code="AI_MODEL_SELECT")
        
        # 默认返回第一个（按梯队优先级：FREE > LIMITED_FREE > PAID）
        tier_priority = {
            ModelTier.FREE: 0,
            ModelTier.LIMITED_FREE: 1,
            ModelTier.PAID: 2
        }
        
        candidates.sort(key=lambda m: tier_priority.get(m.tier, 999))
        selected = candidates[0]
        
        debug_logger.output("ai_manager.py", LogLevel.INFO, 
            f"自动选择模型: {selected.name} ({selected.provider}), "
            f"梯队: {selected.tier.value}", 
            fold_code="AI_MODEL_SELECT")
        
        return selected
    
    def _get_api_key(self, provider: str) -> str:
        """获取API Key"""
        config = PROVIDER_CONFIG.get(provider)
        if not config:
            debug_logger.output("ai_manager.py", LogLevel.ERROR, 
                f"不支持的提供商: {provider}", 
                fold_code="AI_API_KEY")
            return ""
        
        api_key_name = config.get("api_key_name", f"api_key_{provider}")
        
        if self.settings_manager:
            return self.settings_manager.get_api_key(api_key_name)
        
        debug_logger.output("ai_manager.py", LogLevel.WARNING, 
            f"SettingsManager不可用，无法获取API Key: {provider}", 
            fold_code="AI_API_KEY")
        return ""
    
    def _get_client(self, provider: str, api_key: str):
        """获取或创建OpenAI客户端"""
        cache_key = f"{provider}_{api_key[:8]}"  # 使用provider和api_key前8位作为缓存键
        
        if cache_key in self._clients:
            return self._clients[cache_key]
        
        config = PROVIDER_CONFIG.get(provider)
        if not config:
            raise ValueError(f"不支持的 AI 提供商: {provider}")

        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url=config["base_url"]
        )
        
        self._clients[cache_key] = client
        return client
    
    def _build_messages(self, request: AIRequest) -> list:
        """构建消息列表"""
        content = []
        
        content.append({"type": "text", "text": request.prompt})
        
        # 优先使用预编码的base64图片，否则从文件读取
        if request.image_base64:
            base64_image = request.image_base64
        elif request.image_path:
            base64_image = self._encode_image(request.image_path)
        else:
            base64_image = None
        
        if base64_image:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            })
        
        return [{"role": "user", "content": content}]
    
    def _encode_image(self, image_path: str) -> str:
        """将图片编码为base64格式"""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')
    
    def get_models_by_scene(self, scene: AIScene, 
                           provider: Optional[str] = None,
                           tier: Optional[ModelTier] = None,
                           tts_group: Optional[str] = None) -> List[AIModel]:
        """获取指定场景的模型列表（用于UI展示）"""
        result = []
        
        for provider_key, scenes in MODELS.items():
            actual_provider = provider_key.replace("_Paid", "")
            
            scene_key = scene.value
            if scene_key not in scenes:
                continue
            
            for model in scenes[scene_key]:
                if provider and provider not in {actual_provider, model.provider}:
                    continue

                # 筛选梯队
                if tier and tier != model.tier:
                    continue
                
                # 筛选TTS分组
                if scene == AIScene.TTS and tts_group:
                    if model.tts_group != tts_group:
                        continue
                
                result.append(model)
        
        return result
    
    def get_tts_groups(self) -> List[Dict[str, str]]:
        """获取TTS模型分组信息（用于UI展示）"""
        return [
            {
                "id": "instruct",
                "name": "instruct组",
                "description": "指令控制组，共享10000字免费额度"
            },
            {
                "id": "vd",
                "name": "vd组",
                "description": "语音变声组，共享10000字免费额度"
            },
            {
                "id": "vc",
                "name": "vc组",
                "description": "声音转换组，共享10000字免费额度"
            },
            {
                "id": "standard",
                "name": "标准组",
                "description": "标准TTS组，共享10000字免费额度"
            },
        ]
    
    def get_configured_providers(self, scene: AIScene) -> List[str]:
        """获取已配置API Key的提供商列表"""
        configured = []
        for provider in PROVIDER_CONFIG.keys():
            api_key = self._get_api_key(provider)
            if api_key:
                # 检查该提供商是否有该场景的模型
                models = self.get_models_by_scene(scene, provider=provider)
                if models:
                    configured.append(provider)
        return configured
    
    def get_default_model(self, scene: AIScene) -> Optional[AIModel]:
        """获取指定场景的默认模型（已配置且可用）"""
        configured_providers = self.get_configured_providers(scene)
        
        if not configured_providers:
            return None
        
        # 优先使用用户上次选择的模型
        if self.settings_manager:
            scene_key = f"ai_model_{scene.value}"
            saved_provider = self.settings_manager.Custom.get_value(f"{scene_key}_provider", "")
            saved_model = self.settings_manager.Custom.get_value(f"{scene_key}_model", "")
            
            if saved_provider and saved_model:
                models = self.get_models_by_scene(scene, provider=saved_provider)
                for model in models:
                    if model.name == saved_model:
                        return model
        
        # 否则返回第一个已配置的免费模型
        for provider in configured_providers:
            models = self.get_models_by_scene(scene, provider=provider, tier=ModelTier.FREE)
            if models:
                return models[0]
        
        # 如果没有免费模型，返回第一个已配置的模型
        for provider in configured_providers:
            models = self.get_models_by_scene(scene, provider=provider)
            if models:
                return models[0]
        
        return None


_ai_manager = None

def get_ai_manager() -> AIManager:
    """获取AIManager单例实例"""
    global _ai_manager
    if _ai_manager is None:
        _ai_manager = AIManager()
    return _ai_manager

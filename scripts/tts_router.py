# coding=utf-8
"""
TTS Router - 统一TTS接口路由器

根据用户配置动态路由到不同的TTS服务提供商（EdgeTTS、智谱AI、阿里云百炼、Kimi、Minimax）
"""

from dataclasses import dataclass
from typing import Optional
from debug_logger import debug_logger, LogLevel

try:
    from misc_func import SettingsManager
    SETTINGS_AVAILABLE = True
except ImportError:
    SETTINGS_AVAILABLE = False


@dataclass
class TTSGenerationConfig:
    """统一的TTS生成配置"""
    content: str
    voice: str
    speed: int
    pitch: int
    volume: int
    save_path: str
    stretch_factor: float = 1.0
    stretch_enabled: bool = False


class TTSRouter:
    """TTS路由器 - 根据用户配置路由到对应的TTS服务"""
    
    def __init__(self):
        if SETTINGS_AVAILABLE:
            self.settings_manager = SettingsManager()
        else:
            self.settings_manager = None
        
        # 缓存生成器实例
        self._edge_generator = None
        self._ai_generators = {}
        
        # 缓存的提供商信息（用于检测变更）
        self._cached_provider = None
        self._cached_model = None
    
    def get_selected_provider(self) -> str:
        """获取用户选择的TTS提供商"""
        if not self.settings_manager:
            debug_logger.output("tts_router.py", LogLevel.WARNING,
                "SettingsManager不可用，默认使用EdgeTTS",
                fold_code="TTS_ROUTER")
            return "EdgeTTS"
        
        # 从设置中读取用户选择的TTS模型
        provider = self.settings_manager.Custom.get_value("ai_model_tts_provider", "")
        model = self.settings_manager.Custom.get_value("ai_model_tts_model", "")
        
        # 检测配置是否变更
        if provider != self._cached_provider or model != self._cached_model:
            debug_logger.output("tts_router.py", LogLevel.INFO,
                f"检测到TTS配置变更: {self._cached_provider}/{self._cached_model} -> {provider}/{model}",
                fold_code="TTS_ROUTER")
            self._cached_provider = provider
            self._cached_model = model
        
        debug_logger.output("tts_router.py", LogLevel.INFO,
            f"用户选择的TTS: provider={provider}, model={model}",
            fold_code="TTS_ROUTER")
        
        # 如果用户选择了AI模型，返回对应的提供商
        if provider and model:
            # 检查是否是EdgeTTS
            if model == "edge-tts" or provider == "Microsoft":
                return "EdgeTTS"
            # 其他AI提供商
            return provider
        
        # 默认使用EdgeTTS
        return "EdgeTTS"
    
    def generate_audio(self, config: TTSGenerationConfig) -> bool:
        """
        生成音频 - 根据用户配置路由到对应的TTS服务
        
        Args:
            config: TTS生成配置
            
        Returns:
            bool: 生成是否成功
        """
        provider = self.get_selected_provider()
        
        debug_logger.output("tts_router.py", LogLevel.INFO,
            f"路由TTS请求到: {provider}",
            fold_code="TTS_ROUTER")
        
        if provider == "EdgeTTS":
            return self._generate_with_edgetts(config)
        elif provider in ["ChatGLM", "Qwen", "KIMI", "Minimax", "Mimo"]:
            return self._generate_with_ai_provider(provider, config)
        else:
            debug_logger.output("tts_router.py", LogLevel.ERROR,
                f"不支持的TTS提供商: {provider}，回退到EdgeTTS",
                fold_code="TTS_ROUTER")
            return self._generate_with_edgetts(config)
    
    def _generate_with_edgetts(self, config: TTSGenerationConfig) -> bool:
        """使用EdgeTTS生成音频"""
        if self._edge_generator is None:
            from edge_audio_generator import AudioGenerator
            self._edge_generator = AudioGenerator()
            debug_logger.output("tts_router.py", LogLevel.INFO,
                "延迟加载EdgeTTS AudioGenerator",
                fold_code="TTS_ROUTER")
        
        # 转换为EdgeTTS的GenerationConfig
        from edge_audio_generator import GenerationConfig as EdgeGenerationConfig
        edge_config = EdgeGenerationConfig(
            content=config.content,
            voice=config.voice,
            speed=config.speed,
            pitch=config.pitch,
            volume=config.volume,
            save_path=config.save_path,
            stretch_factor=config.stretch_factor,
            stretch_enabled=config.stretch_enabled
        )
        
        return self._edge_generator.generate_audio(edge_config)
    
    def _generate_with_ai_provider(self, provider: str, config: TTSGenerationConfig) -> bool:
        """使用AI提供商生成音频"""
        try:
            from ai_manager import get_ai_manager, AIRequest, AIScene
            
            ai_manager = get_ai_manager()
            
            # 获取用户选择的TTS模型
            model = None
            if self.settings_manager:
                model = self.settings_manager.Custom.get_value("ai_model_tts_model", "")
            
            # 创建AI请求
            request = AIRequest(
                prompt=config.content,
                scene=AIScene.TTS,
                provider=provider,
                model=model if model else None,
                save_path=config.save_path
            )
            
            debug_logger.output("tts_router.py", LogLevel.INFO,
                f"使用{provider}生成TTS: model={model}",
                fold_code="TTS_ROUTER")
            
            # 调用AI Manager生成音频
            # 注意：当前ai_manager.chat()对TTS场景只返回模型信息，不实际生成音频
            # 这里需要实际的TTS生成实现
            response = ai_manager.chat(request)
            
            if response.success:
                debug_logger.output("tts_router.py", LogLevel.INFO,
                    f"TTS生成成功: provider={response.provider_used}, model={response.model_used}",
                    fold_code="TTS_ROUTER")
                # TODO: 实际的AI TTS生成需要调用对应的API
                # 目前ai_manager对TTS场景只返回模型选择，不实际生成音频
                # 这里暂时返回False，表示AI TTS生成尚未实现
                debug_logger.output("tts_router.py", LogLevel.WARNING,
                    f"AI TTS生成尚未实现，回退到EdgeTTS",
                    fold_code="TTS_ROUTER")
                return self._generate_with_edgetts(config)
            else:
                debug_logger.output("tts_router.py", LogLevel.ERROR,
                    f"TTS生成失败: {response.error}",
                    fold_code="TTS_ROUTER")
                return False
                
        except Exception as e:
            debug_logger.output("tts_router.py", LogLevel.ERROR,
                f"AI TTS生成出错: {e}，回退到EdgeTTS",
                fold_code="TTS_ROUTER")
            return self._generate_with_edgetts(config)


# 全局单例
_tts_router = None

def get_tts_router() -> TTSRouter:
    """获取TTS路由器单例"""
    global _tts_router
    if _tts_router is None:
        _tts_router = TTSRouter()
    return _tts_router

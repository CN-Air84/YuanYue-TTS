# coding=utf-8
"""
TTS Router - 统一TTS接口路由器

根据用户配置动态路由到不同的TTS服务提供商（EdgeTTS、智谱AI、阿里云百炼、Kimi、Minimax）
支持插件动态注册TTS引擎
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional as Opt
from debug_logger import debug_logger, LogLevel

try:
    from misc_func import SettingsManager
    _SETTINGS_AVAILABLE = True
except ImportError:
    _SETTINGS_AVAILABLE = False


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
        if _SETTINGS_AVAILABLE:
            self.settings_manager: Opt[Any] = SettingsManager()
        else:
            self.settings_manager: Opt[Any] = None
        
        # 缓存生成器实例
        self._edge_generator: Opt[Any] = None
        self._ai_generators: Dict[str, Any] = {}
        
        # 缓存的提供商信息（用于检测变更）
        self._cached_provider: Opt[str] = None
        self._cached_model: Opt[str] = None
        
        # 动态注册的插件TTS引擎
        self._dynamic_engines: Dict[str, Any] = {}  # {engine_id: engine_class}
        self._dynamic_engine_instances: Dict[str, Any] = {}  # {engine_id: engine_instance}
        
        # 音色列表缓存
        self._voice_cache: Dict[str, List[Any]] = {}  # {engine_id: [VoiceInfo]}
    
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
        
        # 优先检查动态注册的插件引擎
        if model in self._dynamic_engines:
            debug_logger.output("tts_router.py", LogLevel.INFO,
                f"使用动态注册的插件引擎: {model}",
                fold_code="TTS_ROUTER")
            return f"plugin:{model}"
        
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
        
        # 检查是否是插件引擎
        if provider.startswith("plugin:"):
            engine_id = provider[7:]  # 移除 "plugin:" 前缀
            return self._generate_with_dynamic_engine(engine_id, config)
        elif provider == "EdgeTTS":
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
    
    def _generate_with_dynamic_engine(self, engine_id: str, config: TTSGenerationConfig) -> bool:
        """
        使用动态注册的插件引擎生成音频
        
        Args:
            engine_id: 引擎ID
            config: TTS生成配置
            
        Returns:
            生成是否成功
        """
        try:
            # 检查引擎是否已注册
            if engine_id not in self._dynamic_engines:
                debug_logger.output("tts_router.py", LogLevel.ERROR,
                    f"插件引擎未注册: {engine_id}，回退到EdgeTTS",
                    fold_code="TTS_ROUTER")
                return self._generate_with_edgetts(config)
            
            # 获取或创建引擎实例
            if engine_id not in self._dynamic_engine_instances:
                engine_class = self._dynamic_engines[engine_id]
                self._dynamic_engine_instances[engine_id] = engine_class()
                debug_logger.output("tts_router.py", LogLevel.INFO,
                    f"创建插件引擎实例: {engine_id}",
                    fold_code="TTS_ROUTER")
            
            engine = self._dynamic_engine_instances[engine_id]
            
            # 调用引擎的 synthesize 方法
            debug_logger.output("tts_router.py", LogLevel.INFO,
                f"使用插件引擎生成音频: {engine_id}",
                fold_code="TTS_ROUTER")
            
            audio_path = engine.synthesize(
                text=config.content,
                voice=config.voice,
                speed=config.speed,
                pitch=config.pitch,
                volume=config.volume,
                save_path=config.save_path
            )
            
            if audio_path:
                debug_logger.output("tts_router.py", LogLevel.INFO,
                    f"插件引擎生成成功: {audio_path}",
                    fold_code="TTS_ROUTER")
                return True
            else:
                debug_logger.output("tts_router.py", LogLevel.ERROR,
                    f"插件引擎生成失败，回退到EdgeTTS",
                    fold_code="TTS_ROUTER")
                return self._generate_with_edgetts(config)
                
        except Exception as e:
            debug_logger.output("tts_router.py", LogLevel.ERROR,
                f"插件引擎生成出错: {e}，回退到EdgeTTS",
                fold_code="TTS_ROUTER")
            return self._generate_with_edgetts(config)
    
    def get_voices(self, engine_id: Opt[str] = None, use_cache: bool = True) -> List[Any]:
        """
        获取引擎的音色列表
        
        Args:
            engine_id: 引擎ID，如果为None则使用当前选择的引擎
            use_cache: 是否使用缓存
            
        Returns:
            音色列表
        """
        try:
            # 如果未指定引擎，使用当前选择的引擎
            if engine_id is None:
                provider = self.get_selected_provider()
                if provider.startswith("plugin:"):
                    engine_id = provider[7:]
                else:
                    # 非插件引擎，返回空列表
                    debug_logger.output("tts_router.py", LogLevel.INFO,
                        f"非插件引擎，不支持 get_voices: {provider}",
                        fold_code="TTS_ROUTER")
                    return []
            
            # 检查引擎是否已注册
            if engine_id not in self._dynamic_engines:
                debug_logger.output("tts_router.py", LogLevel.WARNING,
                    f"引擎未注册: {engine_id}",
                    fold_code="TTS_ROUTER")
                return []
            
            # 检查缓存
            if use_cache and engine_id in self._voice_cache:
                debug_logger.output("tts_router.py", LogLevel.INFO,
                    f"使用缓存的音色列表: {engine_id}",
                    fold_code="TTS_ROUTER")
                return self._voice_cache[engine_id]
            
            # 获取或创建引擎实例
            if engine_id not in self._dynamic_engine_instances:
                engine_class = self._dynamic_engines[engine_id]
                self._dynamic_engine_instances[engine_id] = engine_class()
                debug_logger.output("tts_router.py", LogLevel.INFO,
                    f"创建插件引擎实例: {engine_id}",
                    fold_code="TTS_ROUTER")
            
            engine = self._dynamic_engine_instances[engine_id]
            
            # 获取音色列表
            voices = engine.get_voices()
            
            # 缓存音色列表
            self._voice_cache[engine_id] = voices
            
            debug_logger.output("tts_router.py", LogLevel.INFO,
                f"获取音色列表成功: {engine_id}, 共 {len(voices)} 个音色",
                fold_code="TTS_ROUTER")
            
            return voices
            
        except Exception as e:
            debug_logger.output("tts_router.py", LogLevel.ERROR,
                f"获取音色列表失败: {e}",
                fold_code="TTS_ROUTER")
            return []
    
    def refresh_voices(self, engine_id: Opt[str] = None) -> bool:
        """
        刷新音色列表缓存
        
        Args:
            engine_id: 引擎ID，如果为None则刷新所有引擎
            
        Returns:
            刷新是否成功
        """
        try:
            if engine_id is None:
                # 刷新所有引擎的缓存
                self._voice_cache.clear()
                debug_logger.output("tts_router.py", LogLevel.INFO,
                    "清空所有音色列表缓存",
                    fold_code="TTS_ROUTER")
                return True
            else:
                # 刷新指定引擎的缓存
                if engine_id in self._voice_cache:
                    del self._voice_cache[engine_id]
                    debug_logger.output("tts_router.py", LogLevel.INFO,
                        f"清空音色列表缓存: {engine_id}",
                        fold_code="TTS_ROUTER")
                
                # 重新获取音色列表
                self.get_voices(engine_id, use_cache=False)
                return True
                
        except Exception as e:
            debug_logger.output("tts_router.py", LogLevel.ERROR,
                f"刷新音色列表失败: {e}",
                fold_code="TTS_ROUTER")
            return False
    
    def register_dynamic_engine(self, engine_id: str, engine_class: Any) -> bool:
        """
        注册动态TTS引擎（插件引擎）
        
        Args:
            engine_id: 引擎唯一标识符
            engine_class: 引擎类（必须实现 TTSEngineInterface）
            
        Returns:
            注册是否成功
        """
        try:
            # 验证引擎ID不为空
            if not engine_id:
                debug_logger.output("tts_router.py", LogLevel.ERROR,
                    "Engine ID cannot be empty",
                    fold_code="TTS_ROUTER")
                return False
            
            # 检查引擎ID是否已存在
            if engine_id in self._dynamic_engines:
                debug_logger.output("tts_router.py", LogLevel.WARNING,
                    f"Engine ID already registered: {engine_id}",
                    fold_code="TTS_ROUTER")
                return False
            
            # 验证引擎类实现了 TTSEngineInterface
            try:
                from tts_engine_interface import TTSEngineInterface
                if not issubclass(engine_class, TTSEngineInterface):
                    debug_logger.output("tts_router.py", LogLevel.ERROR,
                        f"Engine class must implement TTSEngineInterface: {engine_class}",
                        fold_code="TTS_ROUTER")
                    return False
            except Exception as e:
                debug_logger.output("tts_router.py", LogLevel.ERROR,
                    f"Error validating engine class: {e}",
                    fold_code="TTS_ROUTER")
                return False
            
            # 注册引擎
            self._dynamic_engines[engine_id] = engine_class
            
            debug_logger.output("tts_router.py", LogLevel.INFO,
                f"Successfully registered dynamic TTS engine: {engine_id}",
                fold_code="TTS_ROUTER")
            return True
            
        except Exception as e:
            debug_logger.output("tts_router.py", LogLevel.ERROR,
                f"Error registering dynamic engine {engine_id}: {e}",
                fold_code="TTS_ROUTER")
            return False
    
    def unregister_dynamic_engine(self, engine_id: str) -> bool:
        """
        注销动态TTS引擎（插件引擎）
        
        Args:
            engine_id: 引擎唯一标识符
            
        Returns:
            注销是否成功
        """
        try:
            # 检查引擎是否存在
            if engine_id not in self._dynamic_engines:
                debug_logger.output("tts_router.py", LogLevel.WARNING,
                    f"Engine ID not found: {engine_id}",
                    fold_code="TTS_ROUTER")
                return False
            
            # 注销引擎
            del self._dynamic_engines[engine_id]
            
            # 清理引擎实例
            if engine_id in self._dynamic_engine_instances:
                del self._dynamic_engine_instances[engine_id]
                debug_logger.output("tts_router.py", LogLevel.INFO,
                    f"Cleaned up engine instance: {engine_id}",
                    fold_code="TTS_ROUTER")
            
            # 清理音色缓存
            if engine_id in self._voice_cache:
                del self._voice_cache[engine_id]
                debug_logger.output("tts_router.py", LogLevel.INFO,
                    f"Cleaned up voice cache: {engine_id}",
                    fold_code="TTS_ROUTER")
            
            debug_logger.output("tts_router.py", LogLevel.INFO,
                f"Successfully unregistered dynamic TTS engine: {engine_id}",
                fold_code="TTS_ROUTER")
            return True
            
        except Exception as e:
            debug_logger.output("tts_router.py", LogLevel.ERROR,
                f"Error unregistering dynamic engine {engine_id}: {e}",
                fold_code="TTS_ROUTER")
            return False
    
    def get_dynamic_engines(self) -> Dict[str, Any]:
        """
        获取所有动态注册的TTS引擎
        
        Returns:
            动态引擎字典 {engine_id: engine_class}
        """
        return self._dynamic_engines.copy()


# 全局单例
_tts_router = None

def get_tts_router() -> TTSRouter:
    """获取TTS路由器单例"""
    global _tts_router
    if _tts_router is None:
        _tts_router = TTSRouter()
    return _tts_router
